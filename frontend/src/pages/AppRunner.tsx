import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Input,
  Button,
  Typography,
  Tag,
  Avatar,
  Spin,
  message,
  Popconfirm,
  Collapse,
} from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  ArrowLeftOutlined,
  SettingOutlined,
  DeleteOutlined,
  PlusOutlined,
  MessageOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  BookOutlined,
  ToolOutlined,
  PaperClipOutlined,
} from '@ant-design/icons';
import { chatbotApi, ChatRequest } from '@/services/chatbot';
import { agentApi, AgentChatRequest } from '@/services/agent';
import { appsApi, AppData } from '@/services/apps';
import { workflowApi } from '@/services/workflow';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// 工具调用记录类型
interface ToolCallRecord {
  id: string;
  messageId: string;
  tool: string;
  tool_call_id?: string;
  input: string;
  output: string;
  thought?: string;
  status: 'success' | 'error' | 'running';
  duration?: number;
  timestamp: Date;
}

// 消息内容块类型
interface MessageBlock {
  type: 'thinking' | 'tool' | 'text';
  content?: string;
  toolCalls?: ToolCallRecord[];
}

// 扩展消息类型
interface ExtendedMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  citations?: Array<{
    content: string;
    knowledge_base: string;
    score: number;
    document_name?: string;
  }>;
  tool_calls?: ToolCallRecord[];
  quick_links?: Array<{
    title: string;
    url: string;
    snippet?: string;
  }>;
  metadata?: Record<string, any>;
  blocks?: MessageBlock[];
}

interface SessionData {
  id: string;
  title: string;
  conversation_id?: number;
  messages: ExtendedMessage[];
  createdAt: Date;
  updatedAt: Date;
}

// 按时间分组会话
const groupSessions = (sessions: SessionData[]) => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);

  const groups: { label: string; items: SessionData[] }[] = [];
  const pinned: SessionData[] = [];
  const todayItems: SessionData[] = [];
  const monthItems: SessionData[] = [];
  const olderItems: Map<string, SessionData[]> = new Map();

  for (const s of sessions) {
    const d = s.updatedAt;
    if (d >= today) {
      todayItems.push(s);
    } else if (d >= thirtyDaysAgo) {
      monthItems.push(s);
    } else {
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (!olderItems.has(key)) olderItems.set(key, []);
      olderItems.get(key)!.push(s);
    }
  }

  if (pinned.length) groups.push({ label: '置顶', items: pinned });
  if (todayItems.length) groups.push({ label: '今天', items: todayItems });
  if (monthItems.length) groups.push({ label: '30 天内', items: monthItems });
  // 按时间倒序输出更早的分组
  const sortedKeys = Array.from(olderItems.keys()).sort().reverse();
  for (const key of sortedKeys) {
    const [y, m] = key.split('-');
    groups.push({ label: `${y}-${m}`, items: olderItems.get(key)! });
  }
  return groups;
};

const AppRunner: React.FC = () => {
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [app, setApp] = useState<AppData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessions, setSessions] = useState<SessionData[]>([]);
  const [currentSession, setCurrentSession] = useState<SessionData | null>(null);
  const [inputValue, setInputValue] = useState('');
  const [sending, setSending] = useState(false);


  // 会话分组
  const sessionGroups = useMemo(() => groupSessions(sessions), [sessions]);

  // 加载应用信息
  useEffect(() => {
    const loadApp = async () => {
      try {
        const response = await appsApi.getApp(Number(appId));
        setApp(response.data);
      } catch (error: any) {
        console.error('加载应用失败:', error);
        if (error.response?.status === 404) {
          message.error('应用不存在');
        } else {
          message.error('加载应用失败');
        }
        navigate('/apps');
      } finally {
        setLoading(false);
      }
    };
    loadApp();
  }, [appId, navigate]);

  // 加载会话记录
  useEffect(() => {
    if (!appId) return;
    const savedSessions = localStorage.getItem(`app_sessions_${appId}`);
    if (savedSessions) {
      try {
        const parsed = JSON.parse(savedSessions);
        setSessions(parsed.map((s: any) => ({
          ...s,
          createdAt: new Date(s.createdAt),
          updatedAt: new Date(s.updatedAt),
          messages: s.messages.map((m: any) => ({
            ...m,
            timestamp: new Date(m.timestamp),
            tool_calls: m.tool_calls?.map((tc: any) => ({
              ...tc,
              timestamp: new Date(tc.timestamp),
            })),
          })),
        })));
      } catch (e) {
        console.error('Failed to load sessions', e);
      }
    }
  }, [appId]);

  // 保存会话记录
  const saveSessions = (newSessions: SessionData[]) => {
    if (!appId) return;
    localStorage.setItem(`app_sessions_${appId}`, JSON.stringify(newSessions));
    setSessions(newSessions);
  };

  // 创建新会话
  const handleNewSession = () => {
    const newSession: SessionData = {
      id: Date.now().toString(),
      title: `会话 ${sessions.length + 1}`,
      messages: [],
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    const newSessions = [newSession, ...sessions];
    saveSessions(newSessions);
    setCurrentSession(newSession);
  };

  // 切换会话
  const handleSwitchSession = (session: SessionData) => {
    setCurrentSession(session);
  };

  // 删除会话
  const handleDeleteSession = (sessionId: string) => {
    const newSessions = sessions.filter(s => s.id !== sessionId);
    saveSessions(newSessions);
    if (currentSession?.id === sessionId) {
      setCurrentSession(newSessions[0] || null);
    }
  };

  // 滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [currentSession?.messages]);

  // 查看消息的运行日志
  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || !currentSession || !app) return;

    const userMessage: ExtendedMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    const updatedMessages = [...currentSession.messages, userMessage];
    const updatedSession = {
      ...currentSession,
      messages: updatedMessages,
      updatedAt: new Date(),
    };
    setCurrentSession(updatedSession);

    const query = inputValue.trim();
    setInputValue('');
    setSending(true);

    try {
      if (app.app_type === 'agent') {
        const request: AgentChatRequest = {
          query,
          conversation_id: currentSession.conversation_id,
        };

        const assistantMsgId = (Date.now() + 1).toString();
        const assistantMessage: ExtendedMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          tool_calls: [],
          metadata: {},
          blocks: [],
          isStreaming: true,
        };

        const streamingMessages = [...updatedMessages, assistantMessage];
        setCurrentSession({ ...updatedSession, messages: streamingMessages });

        let finalConversationId = currentSession.conversation_id;
        let finalMetadata: Record<string, any> = {};

        // blocks 的本地副本，用于流式更新
        let streamingBlocks: MessageBlock[] = [{
          type: 'thinking',
          content: ''
        }];

        try {
          for await (const event of agentApi.chatStream(Number(appId), request)) {
            switch (event.event) {
              case 'message': {
                const textContent = event.data.content;
                // 移除思考中占位块（LLM 开始输出时占位块已完成使命）
                const thinkBlock = streamingBlocks[0];
                if (thinkBlock?.type === 'thinking') {
                  streamingBlocks = streamingBlocks.slice(1);
                }
                // 追加到最后一个 text block，或创建新 block（必须创建新对象引用）
                const updatedLastBlock = streamingBlocks[streamingBlocks.length - 1];
                if (updatedLastBlock && updatedLastBlock.type === 'text') {
                  const updatedTextBlock = { ...updatedLastBlock, content: (updatedLastBlock.content || '') + textContent };
                  streamingBlocks = [...streamingBlocks.slice(0, -1), updatedTextBlock];
                } else {
                  streamingBlocks = [...streamingBlocks, { type: 'text', content: textContent }];
                }
                assistantMessage.content += textContent;
                assistantMessage.blocks = [...streamingBlocks];
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, content: assistantMessage.content, blocks: [...streamingBlocks] } : m
                  ),
                }));
                break;
              }
              case 'tool_start': {
                const newToolCall: ToolCallRecord = {
                  id: `${assistantMsgId}_tool_${Date.now()}`,
                  messageId: assistantMsgId,
                  tool: event.data.tool,
                  tool_call_id: event.data.tool_call_id,
                  input: event.data.input,
                  output: '',
                  status: 'running',
                  timestamp: new Date(),
                };
                assistantMessage.tool_calls = [...(assistantMessage.tool_calls || []), newToolCall];
                // 追加到最后一个 tool block，或创建新 block（必须创建新对象引用，触发 React 重渲染）
                const lastToolBlock = streamingBlocks[streamingBlocks.length - 1];
                if (lastToolBlock && lastToolBlock.type === 'tool') {
                  const updatedBlock = { ...lastToolBlock, toolCalls: [...(lastToolBlock.toolCalls || []), newToolCall] };
                  streamingBlocks = [...streamingBlocks.slice(0, -1), updatedBlock];
                } else {
                  streamingBlocks = [...streamingBlocks, { type: 'tool', toolCalls: [newToolCall] }];
                }
                assistantMessage.blocks = [...streamingBlocks];
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId
                      ? { ...m, tool_calls: [...(m.tool_calls || []), newToolCall], blocks: [...streamingBlocks] }
                      : m
                  ),
                }));
                break;
              }
              case 'tool_end': {
                const doneToolCallId = event.data.tool_call_id;
                // 用 tool_call_id 精确匹配，回退到 name + running 匹配
                const matchTool = (tc: ToolCallRecord) => {
                  if (doneToolCallId && tc.tool_call_id) return tc.tool_call_id === doneToolCallId;
                  return tc.tool === event.data.tool && tc.status === 'running';
                };
                // 同步更新 streamingBlocks（后续事件依赖此变量的正确引用）
                streamingBlocks = streamingBlocks.map(b => {
                  if (b.type !== 'tool') return b;
                  const updatedToolCalls = (b.toolCalls || []).map(tc =>
                    matchTool(tc) ? { ...tc, output: event.data.output, status: event.data.status || 'success' as const } : tc
                  );
                  return { ...b, toolCalls: updatedToolCalls };
                });
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m => {
                    if (m.id !== assistantMsgId) return m;
                    const toolCalls = (m.tool_calls || []).map(tc =>
                      matchTool(tc) ? { ...tc, output: event.data.output, status: event.data.status || 'success' as const } : tc
                    );
                    return { ...m, tool_calls: toolCalls, blocks: [...streamingBlocks] };
                  }),
                }));
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, blocks: [...streamingBlocks] } : m
                  ),
                }));
                break;
              }
              case 'thinking': {
                const thinkingContent = event.data.content;
                // 追加到最后一个 thinking block，或创建新 block
                const lastThinkBlock = streamingBlocks[streamingBlocks.length - 1];
                if (lastThinkBlock && lastThinkBlock.type === 'thinking') {
                  // 如果是占位块，替换为真实内容
                  const updatedThinkBlock = { ...lastThinkBlock, content: (lastThinkBlock.content || '') + thinkingContent, isPlaceholder: false };
                  streamingBlocks = [...streamingBlocks.slice(0, -1), updatedThinkBlock];
                } else {
                  streamingBlocks = [...streamingBlocks, { type: 'thinking', content: thinkingContent }];
                }
                assistantMessage.blocks = [...streamingBlocks];
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, blocks: [...streamingBlocks] } : m
                  ),
                }));
                break;
              }
              case 'done': {
                finalConversationId = event.data.conversation_id;
                finalMetadata = event.data.metadata;
                setCurrentSession(prev => {
                  if (!prev) return prev;
                  const finalMessages = prev.messages.map(m => {
                    if (m.id !== assistantMsgId) return m;
                    // 构建 tool_call_id → step 映射，用于同步 output
                    const stepMap = new Map<string, any>();
                    (event.data.intermediate_steps || []).forEach((step: any) => {
                      if (step.tool_call_id) stepMap.set(step.tool_call_id, step);
                    });
                    // 保留已有的 tool_calls（含 tool_call_id），仅同步 output
                    const finalToolCalls = (m.tool_calls || []).map(tc => {
                      const step = tc.tool_call_id ? stepMap.get(tc.tool_call_id) : undefined;
                      if (step) {
                        return { ...tc, output: step.output || tc.output, status: step.status || 'success' as const };
                      }
                      return { ...tc, status: 'success' as const };
                    });
                    // done 时同步 blocks 的 output（保留 tool_call_id 和已更新的 status）
                    const updatedBlocks = (m.blocks || []).map(b => {
                      if (b.type !== 'tool') return b;
                      return {
                        ...b,
                        toolCalls: (b.toolCalls || []).map(tc => {
                          const step = tc.tool_call_id ? stepMap.get(tc.tool_call_id) : undefined;
                          if (step) {
                            return { ...tc, output: step.output || tc.output, status: step.status || 'success' as const };
                          }
                          return { ...tc, status: 'success' as const };
                        }),
                      };
                    });
                    return {
                      ...m,
                      content: event.data.answer || m.content,
                      isStreaming: false,
                      tool_calls: finalToolCalls,
                      blocks: updatedBlocks,
                      metadata: event.data.metadata,
                    };
                  });
                  return { ...prev, messages: finalMessages, conversation_id: event.data.conversation_id };
                });
                break;
              }
              case 'error': {
                assistantMessage.content = `⚠️ ${event.data.message}`;
                assistantMessage.isStreaming = false;
                streamingBlocks = [];
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? {
                      ...m,
                      content: `⚠️ ${event.data.message}`,
                      isStreaming: false,
                      blocks: [],
                      // 保留已收集的 tool_calls（执行中途出错时工具调用记录仍有价值）
                      tool_calls: m.tool_calls && m.tool_calls.length > 0 ? m.tool_calls : undefined,
                    } : m
                  ),
                }));
                break;
              }
            }
          }
        } catch (err: any) {
          console.error('Agent 流式调用失败:', err);
          assistantMessage.content = `⚠️ 请求失败: ${err.message}`;
          setCurrentSession(prev => ({
            ...prev!,
            messages: prev!.messages.map(m =>
              m.id === assistantMsgId ? {
                ...m,
                content: `⚠️ 请求失败: ${err.message}`,
                tool_calls: m.tool_calls && m.tool_calls.length > 0 ? m.tool_calls : undefined,
              } : m
            ),
          }));
        }

        setCurrentSession(prev => {
          if (!prev) return prev;
          const finalSession = {
            ...prev,
            conversation_id: finalConversationId,
            title: prev.title.startsWith('会话')
              ? query.substring(0, 20) + (query.length > 20 ? '...' : '')
              : prev.title,
          };
          saveSessions(sessions.map(s => s.id === finalSession.id ? finalSession : s));
          return finalSession;
        });

      } else if (app.app_type === 'workflow') {
        // 工作流流式运行
        const assistantMsgId = (Date.now() + 1).toString();
        const assistantMessage: ExtendedMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          isStreaming: true,
        };
        const streamingMessages = [...updatedMessages, assistantMessage];
        setCurrentSession({ ...updatedSession, messages: streamingMessages });

        try {
          const inputs: Record<string, any> = { user_message: query };

          let llmOutput = '';
          const executionLogs: Array<{node_id:string;type:string;status:string;duration_ms?:number;error?:string}> = [];
          let currentNode = '';
          let finalOutputs: Record<string, any> | null = null;
          let duration: number | undefined;

          const updateMessage = () => {
            let content = '';

            // 正在执行的节点提示
            if (currentNode) {
              content += `⏳ 正在执行: ${currentNode}\n\n`;
            }

            // LLM 输出
            if (llmOutput) {
              content += llmOutput;
            }

            // 执行日志
            if (executionLogs.length > 0) {
              content += '\n\n---\n**执行日志**\n' + executionLogs.map(l => {
                const icon = l.status === 'done' ? '✅' : l.status === 'skipped' ? '⏭️' : '❌';
                const dur = l.duration_ms != null ? ` (${l.duration_ms}ms)` : '';
                const err = l.error ? ` - ${l.error}` : '';
                return `${icon} ${l.node_id} [${l.type}]${dur}${err}`;
              }).join('\n');
            }

            // 完成信息
            if (duration != null) {
              content += `\n总耗时: ${duration}ms`;
            }

            setCurrentSession(prev => {
              if (!prev) return prev;
              return {
                ...prev,
                messages: prev.messages.map(m =>
                  m.id === assistantMsgId ? { ...m, content, isStreaming: true } : m
                ),
              };
            });
          };

          for await (const event of workflowApi.runStream(Number(appId), { inputs })) {
            switch (event.event) {
              case 'node_start':
                currentNode = `${event.data.node_id} [${event.data.type}]`;
                updateMessage();
                break;
              case 'llm_token':
                llmOutput += event.data.token;
                updateMessage();
                break;
              case 'node_log':
                executionLogs.push(event.data);
                currentNode = '';
                updateMessage();
                break;
              case 'done':
                finalOutputs = event.data.outputs;
                duration = event.data.duration;
                // 补全执行日志
                if (event.data.execution_log) {
                  for (const log of event.data.execution_log) {
                    if (!executionLogs.find(l => l.node_id === log.node_id && l.type === log.type)) {
                      executionLogs.push(log);
                    }
                  }
                }
                updateMessage();
                break;
              case 'error':
                throw new Error(event.data.message);
            }
          }

          // 最终结果展示
          let resultText = '';
          if (finalOutputs && Object.keys(finalOutputs).length > 0) {
            const parts = Object.entries(finalOutputs).map(([key, val]) =>
              `**${key}**: ${typeof val === 'string' ? val : JSON.stringify(val, null, 2)}`
            );
            resultText = parts.join('\n\n');
          }

          // 如果没有 LLM 输出但有最终输出，显示最终输出
          if (!llmOutput && resultText) {
            llmOutput = resultText;
          } else if (llmOutput && resultText && resultText !== llmOutput) {
            // 如果有 LLM 输出也有其他输出字段，追加
            llmOutput += '\n\n' + resultText;
          }

          // 构建最终消息内容
          let finalContent = llmOutput || '工作流执行完成（无输出结果）';
          if (executionLogs.length > 0) {
            finalContent += '\n\n---\n**执行日志**\n' + executionLogs.map(l => {
              const icon = l.status === 'done' ? '✅' : l.status === 'skipped' ? '⏭️' : '❌';
              const dur = l.duration_ms != null ? ` (${l.duration_ms}ms)` : '';
              const err = l.error ? ` - ${l.error}` : '';
              return `${icon} ${l.node_id} [${l.type}]${dur}${err}`;
            }).join('\n');
          }
          if (duration != null) {
            finalContent += `\n总耗时: ${duration}ms`;
          }

          setCurrentSession(prev => {
            if (!prev) return prev;
            const finalMessages = prev.messages.map(m =>
              m.id === assistantMsgId ? { ...m, content: finalContent, isStreaming: false } : m
            );
            const finalSession = {
              ...prev,
              messages: finalMessages,
              title: prev.title.startsWith('会话') ? query.substring(0, 20) + (query.length > 20 ? '...' : '') : prev.title,
            };
            saveSessions(sessions.map(s => s.id === finalSession.id ? finalSession : s));
            return finalSession;
          });
        } catch (err: any) {
          const detail = err.message || '执行失败';
          setCurrentSession(prev => ({
            ...prev!,
            messages: prev!.messages.map(m =>
              m.id === assistantMsgId ? { ...m, content: `⚠️ 工作流执行失败: ${detail}`, isStreaming: false } : m
            ),
          }));
        }

      } else {
        // 流式聊天助手调用
        const request: ChatRequest = {
          query,
          conversation_id: currentSession.conversation_id,
        };

        const assistantMsgId = (Date.now() + 1).toString();
        const assistantMessage: ExtendedMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          citations: [],
        };

        const streamingMessages = [...updatedMessages, assistantMessage];
        setCurrentSession({ ...updatedSession, messages: streamingMessages });

        let finalConversationId = currentSession.conversation_id;
        let finalCitations: Array<{ content: string; knowledge_base: string; score: number; document_name?: string }> = [];

        try {
          for await (const event of chatbotApi.chatStream(Number(appId), request)) {
            switch (event.event) {
              case 'message': {
                assistantMessage.content += event.data.content;
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, content: assistantMessage.content } : m
                  ),
                }));
                break;
              }
              case 'done': {
                finalConversationId = event.data.conversation_id;
                finalCitations = event.data.metadata?.citations || [];
                setCurrentSession(prev => {
                  if (!prev) return prev;
                  const finalMessages = prev.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, citations: finalCitations } : m
                  );
                  return { ...prev, messages: finalMessages, conversation_id: event.data.conversation_id };
                });
                break;
              }
              case 'error': {
                assistantMessage.content = `⚠️ ${event.data.message}`;
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId ? { ...m, content: `⚠️ ${event.data.message}` } : m
                  ),
                }));
                break;
              }
            }
          }
        } catch (err: any) {
          console.error('聊天助手流式调用失败:', err);
          assistantMessage.content = `⚠️ 请求失败: ${err.message}`;
          setCurrentSession(prev => ({
            ...prev!,
            messages: prev!.messages.map(m =>
              m.id === assistantMsgId ? { ...m, content: `⚠️ 请求失败: ${err.message}` } : m
            ),
          }));
        }

        setCurrentSession(prev => {
          if (!prev) return prev;
          const finalSession = {
            ...prev,
            conversation_id: finalConversationId,
            title: prev.title.startsWith('会话')
              ? query.substring(0, 20) + (query.length > 20 ? '...' : '')
              : prev.title,
          };
          saveSessions(sessions.map(s => s.id === finalSession.id ? finalSession : s));
          return finalSession;
        });
      }
    } catch (error: any) {
      console.error('发送消息失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '发送失败';
      message.error(`错误: ${errorMsg}`);
    } finally {
      setSending(false);
    }
  };

  // 清空当前会话
  const handleClearSession = () => {
    if (!currentSession) return;
    const clearedSession = {
      ...currentSession,
      messages: [],
      conversation_id: undefined,
      updatedAt: new Date(),
    };
    setCurrentSession(clearedSession);
    saveSessions(sessions.map(s => s.id === clearedSession.id ? clearedSession : s));
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-page">
        <Spin size="large" />
      </div>
    );
  }

  if (!app) return null;

  const isAgent = app.app_type === 'agent';
  const isWorkflow = app.app_type === 'workflow';

  return (
    <div className="flex bg-page overflow-hidden" style={{ height: 'calc(100vh - 32px)' }}>
      {/* ===== 左侧 chatHistory ===== */}
      <div className="w-72 flex-shrink-0 bg-sidebar border-r border-border flex flex-col h-full">
        {/* 顶部：新建对话 */}
        <div className="p-3 border-b border-border">
          <button
            onClick={handleNewSession}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-button
              border border-border text-text-primary hover:bg-gray-50 transition-colors cursor-pointer"
          >
            <PlusOutlined />
            <span>开启新对话</span>
          </button>
        </div>

        {/* 会话列表 */}
        <div className="flex-1 overflow-y-auto py-2">
          {sessionGroups.length === 0 ? (
            <div className="px-4 py-8 text-center text-text-secondary text-sm">
              暂无对话记录
            </div>
          ) : (
            sessionGroups.map(group => (
              <div key={group.label} className="mb-2">
                {/* 分组标题 */}
                <div className="px-4 py-1.5 text-xs text-text-secondary font-medium">
                  {group.label}
                </div>
                {/* 分组内的会话项 */}
                {group.items.map(session => (
                  <div
                    key={session.id}
                    onClick={() => handleSwitchSession(session)}
                    className={`
                      group relative flex items-center gap-2 px-4 py-2.5 mx-2 rounded-lg cursor-pointer
                      transition-colors duration-150
                      ${currentSession?.id === session.id
                        ? 'bg-primary-bg text-primary'
                        : 'text-text-primary hover:bg-gray-100'
                      }
                    `}
                  >
                    <MessageOutlined className="text-sm flex-shrink-0 opacity-60" />
                    <span className="flex-1 text-sm truncate">{session.title}</span>
                    {/* 删除按钮 */}
                    <Popconfirm
                      title="确定删除此会话？"
                      onConfirm={(e) => { e?.stopPropagation(); handleDeleteSession(session.id); }}
                      onCancel={(e) => e?.stopPropagation()}
                    >
                      <DeleteOutlined
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs opacity-0 group-hover:opacity-60 hover:!opacity-100 transition-opacity flex-shrink-0"
                      />
                    </Popconfirm>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
      </div>

      {/* ===== 右侧 chatMain ===== */}
      <div className="flex-1 flex flex-col h-full min-w-0">
        {/* 顶部导航栏 */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-border bg-sidebar flex-shrink-0">
          <div className="flex items-center gap-2">
            <Button
              type="text"
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate('/apps')}
              size="small"
            />
            <Typography.Text strong className="text-base">
              {app.name}
            </Typography.Text>
            <Tag color={isAgent ? 'blue' : isWorkflow ? 'purple' : 'green'} className="!ml-0">
              {isAgent ? 'Agent' : isWorkflow ? '工作流' : '聊天助手'}
            </Tag>
          </div>
          <div className="flex items-center gap-1">
            {currentSession && (
              <Popconfirm title="确定清空当前会话？" onConfirm={handleClearSession}>
                <Button type="text" icon={<DeleteOutlined />} size="small" />
              </Popconfirm>
            )}
            <Button
              type="text"
              icon={<SettingOutlined />}
              size="small"
              onClick={() => navigate(`/apps/${appId}/${isAgent ? 'agent' : isWorkflow ? 'workflow' : 'chatbot'}`)}
            />
          </div>
        </div>

        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto">
          {!currentSession ? (
            /* 无会话：欢迎页 */
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <RobotOutlined className="text-6xl text-primary opacity-80" />
              <Typography.Title level={4} className="!mb-0">
                开始对话
              </Typography.Title>
              <Typography.Text type="secondary">
                点击"开启新对话"开始与 {app.name} 交流
              </Typography.Text>
            </div>
          ) : currentSession.messages.length === 0 ? (
            /* 有会话但无消息 */
            <div className="flex flex-col items-center justify-center h-full gap-4">
              <RobotOutlined className="text-6xl text-primary opacity-80" />
              <Typography.Title level={4} className="!mb-0">
                有什么可以帮你的？
              </Typography.Title>
              <Typography.Text type="secondary">
                输入你的问题，开始与 {app.name} 对话
              </Typography.Text>
            </div>
          ) : (
            /* 消息列表 */
            <div className="max-w-3xl mx-auto py-6 px-4">
              {currentSession.messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 mb-6 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                >
                  {/* 头像 */}
                  <Avatar
                    icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                    className={`flex-shrink-0 ${msg.role === 'user' ? '!bg-primary' : '!bg-green-500'
                      }`}
                  />
                  {/* 内容 */}
                  <div className={`flex flex-col max-w-[80%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                    {/* 消息气泡 */}
                    <div
                      className={`
                        rounded-card px-4 py-3 text-sm leading-relaxed
                        ${msg.role === 'user'
                          ? 'bg-primary text-white rounded-tr-sm'
                          : 'bg-white text-gray-800 rounded-tl-sm shadow-bubble'
                        }
                      `}
                    >
                      {/* 用户消息：纯文本 */}
                      {msg.role === 'user' && (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      )}
                      {/* AI 消息：按 blocks 渲染（思考 → 工具 → 文本） */}
                      {msg.role === 'assistant' && msg.blocks && msg.blocks.length > 0 && (
                        <div className="space-y-3">
                          {msg.blocks.map((block, idx) => {
                            if (block.type === 'thinking') {
                              return (
                                <div className="flex items-center gap-2 text-text-secondary text-sm">
                                  <Spin size="small" />
                                  <span>正在思考...</span>
                                </div>
                              );
                            }
                            if (block.type === 'tool') {
                              return (
                                <div key={idx} className="space-y-2">
                                  {(block.toolCalls || []).map((tc, tcIdx) => (
                                    <div key={tc.tool_call_id || tc.id || tcIdx} className="bg-blue-50 border border-blue-200 rounded-lg p-2.5">
                                      <div className="flex items-center gap-2 mb-1.5">
                                        {tc.status === 'running' && <LoadingOutlined className="text-blue-500 text-xs" />}
                                        {tc.status === 'success' && <CheckCircleOutlined className="text-green-500 text-xs" />}
                                        {tc.status === 'error' && <CloseCircleOutlined className="text-red-500 text-xs" />}
                                        <ToolOutlined className="text-blue-500 text-xs" />
                                        <span className="text-xs font-medium text-blue-800">{tc.tool}</span>
                                        <Tag color={tc.status === 'running' ? 'processing' : tc.status === 'success' ? 'success' : 'error'} className="!text-xs !leading-normal !px-1.5 !py-0">
                                          {tc.status === 'running' ? '执行中...' : tc.status === 'success' ? '完成' : '失败'}
                                        </Tag>
                                      </div>
                                      {(tc.input || tc.output) && (
                                        <Collapse
                                          ghost
                                          size="small"
                                          items={[
                                            ...(tc.input ? [{
                                              key: 'input',
                                              label: <span className="text-xs text-gray-500">输入参数</span>,
                                              children: <pre className="text-xs bg-white p-2 rounded border border-blue-100 overflow-x-auto whitespace-pre-wrap break-all">{tc.input}</pre>,
                                            }] : []),
                                            ...(tc.output ? [{
                                              key: 'output',
                                              label: <span className="text-xs text-gray-500">执行结果</span>,
                                              children: <pre className="text-xs bg-white p-2 rounded border border-blue-100 overflow-x-auto whitespace-pre-wrap break-all">{tc.output}</pre>,
                                            }] : []),
                                          ]}
                                        />
                                      )}
                                    </div>
                                  ))}
                                </div>
                              );
                            }
                            return (
                              <div key={idx} className="markdown-body">
                                <Markdown remarkPlugins={[remarkGfm]}>{block.content || ''}</Markdown>
                                {msg.isStreaming && (
                                  <span className="inline-block w-1.5 h-4 ml-0.5 bg-gray-400 animate-pulse align-text-bottom" />
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                      {/* AI 消息 fallback：无 blocks 时用纯文本，流式时显示思考中 */}
                      {msg.role === 'assistant' && (!msg.blocks || msg.blocks.length === 0) && (
                        <div className="markdown-body">
                          {msg.isStreaming && !msg.content ? (
                            <div className="flex items-center gap-2 text-text-secondary text-sm">
                              <Spin size="small" />
                              <span>正在思考...</span>
                            </div>
                          ) : <Markdown remarkPlugins={[remarkGfm]}>{msg.content || ''}</Markdown>}
                        </div>
                      )}
                    </div>

                    {/* 知识库引用 */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-2 w-full bg-white rounded-card shadow-bubble overflow-hidden">
                        <Collapse
                          ghost
                          size="small"
                          items={[{
                            key: 'citations',
                            label: (
                              <span className="flex items-center gap-1.5 text-primary text-sm font-medium">
                                <BookOutlined />
                                知识库引用 ({msg.citations.length})
                              </span>
                            ),
                            children: (
                              <div className="space-y-2">
                                {msg.citations.map((item, idx) => (
                                  <div key={idx} className="text-sm">
                                    <div className="flex items-center gap-2 mb-1">
                                      <Tag color="blue" className="!text-xs">{item.knowledge_base}</Tag>
                                      {item.document_name && (
                                        <span className="text-xs text-text-secondary">📄 {item.document_name}</span>
                                      )}
                                      <span className="text-xs text-text-secondary">
                                        相关度: {(item.score * 100).toFixed(1)}%
                                      </span>
                                    </div>
                                    <div className="bg-page p-2 rounded text-xs leading-relaxed">
                                      {item.content}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            ),
                          }]}
                        />
                      </div>
                    )}

                    {/* 时间戳 */}
                    <span className="text-xs text-text-secondary mt-1">
                      {msg.timestamp.toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* ===== chatInput 底部输入区域 ===== */}
        {currentSession && (
          <div className="border-t border-border flex-shrink-0">
            <div className="max-w-3xl mx-auto px-4 py-3">
              <div className="flex items-end gap-2 bg-white rounded-xl border border-gray-200 shadow-sm px-3 py-2 focus-within:border-primary focus-within:shadow-md transition-all">
                {/* 附件按钮 */}
                <Button
                  type="text"
                  icon={<PaperClipOutlined />}
                  className="!text-text-secondary hover:!text-text-primary flex-shrink-0 mb-0.5"
                />
                {/* 输入框 */}
                <Input.TextArea
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="请输入消息..."
                  autoSize={{ minRows: 1, maxRows: 6 }}
                  onPressEnter={(e) => {
                    if (!e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                  disabled={sending}
                  variant="borderless"
                  className="!flex-1 !text-sm"
                  styles={{ input: { padding: '4px 0', resize: 'none' } }}
                />
                {/* 发送按钮 */}
                <button
                  onClick={handleSend}
                  disabled={!inputValue.trim() || sending}
                  className={`
                    flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
                    transition-all duration-200 mb-0.5 cursor-pointer
                    ${inputValue.trim() && !sending
                      ? 'bg-primary text-white hover:bg-primary-hover shadow-sm'
                      : 'bg-gray-100 text-gray-300 cursor-not-allowed'
                    }
                  `}
                >
                  {sending ? (
                    <LoadingOutlined className="text-sm" />
                  ) : (
                    <SendOutlined className="text-sm" />
                  )}
                </button>
              </div>
              <div className="text-center mt-1.5">
                <span className="text-xs text-text-secondary opacity-50">
                  内容由 AI 生成，仅供参考
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

    </div>
  );
};

export default AppRunner;
