import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Layout,
  Card,
  Input,
  Button,
  List,
  Typography,
  Space,
  Tag,
  Avatar,
  Spin,
  message,
  Empty,
  Popconfirm,
  Drawer,
  Timeline,
  Collapse,
  Badge,
  Tooltip,
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
  ToolOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  BookOutlined,
  LinkOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  BugOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { chatbotApi, ChatRequest, ChatResponse, Conversation, Message as ChatMessage } from '../services/chatbot';
import { agentApi, AgentChatRequest, AgentChatResponse } from '../services/agent';
import { appsApi, AppData } from '../services/apps';

// 工具调用记录类型
interface ToolCallRecord {
  id: string;
  messageId: string;
  tool: string;
  input: string;
  output: string;
  thought?: string;
  status: 'success' | 'error' | 'running';
  duration?: number;
  timestamp: Date;
}

// 扩展消息类型
interface ExtendedMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
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
}

interface SessionData {
  id: string;
  title: string;
  conversation_id?: number;
  messages: ExtendedMessage[];
  createdAt: Date;
  updatedAt: Date;
}

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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  // Agent 运行日志抽屉
  const [logDrawerOpen, setLogDrawerOpen] = useState(false);
  const [selectedMessageLogs, setSelectedMessageLogs] = useState<ToolCallRecord[]>([]);

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
  const handleViewLogs = (message: ExtendedMessage) => {
    const logs = message.tool_calls || [];
    setSelectedMessageLogs(logs);
    setLogDrawerOpen(true);

    // 调试：打印元数据到控制台
    if (message.metadata) {
      console.log('Agent 响应元数据:', message.metadata);
    }
    console.log('Agent 工具调用记录:', logs);
  };

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
      let response: ChatResponse | AgentChatResponse;

      if (app.app_type === 'agent') {
        const request: AgentChatRequest = {
          query,
          conversation_id: currentSession.conversation_id,
        };

        // === 流式 Agent 调用 ===
        const assistantMsgId = (Date.now() + 1).toString();
        const assistantMessage: ExtendedMessage = {
          id: assistantMsgId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
          tool_calls: [],
          metadata: {},
        };

        // 先添加空的助手消息，后续逐步更新
        const streamingMessages = [...updatedMessages, assistantMessage];
        setCurrentSession({
          ...updatedSession,
          messages: streamingMessages,
        });

        let finalConversationId = currentSession.conversation_id;
        let finalMetadata: Record<string, any> = {};

        try {
          for await (const event of agentApi.chatStream(Number(appId), request)) {
            switch (event.event) {
              case 'message': {
                // 逐字追加回答内容
                assistantMessage.content += event.data.content;
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId
                      ? { ...m, content: assistantMessage.content }
                      : m
                  ),
                }));
                break;
              }
              case 'tool_start': {
                // 添加工具调用记录（running 状态）
                const newToolCall: ToolCallRecord = {
                  id: `${assistantMsgId}_tool_${Date.now()}`,
                  messageId: assistantMsgId,
                  tool: event.data.tool,
                  input: event.data.input,
                  output: '',
                  status: 'running',
                  timestamp: new Date(),
                };
                assistantMessage.tool_calls = [...(assistantMessage.tool_calls || []), newToolCall];
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId
                      ? { ...m, tool_calls: [...(m.tool_calls || []), newToolCall] }
                      : m
                  ),
                }));
                break;
              }
              case 'tool_end': {
                // 更新工具调用状态
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m => {
                    if (m.id !== assistantMsgId) return m;
                    const toolCalls = (m.tool_calls || []).map(tc =>
                      tc.tool === event.data.tool && tc.status === 'running'
                        ? { ...tc, output: event.data.output, status: event.data.status || 'success' as const }
                        : tc
                    );
                    return { ...m, tool_calls: toolCalls };
                  }),
                }));
                break;
              }
              case 'thinking': {
                // 思考过程实时显示（追加到内容前面）
                break;
              }
              case 'done': {
                finalConversationId = event.data.conversation_id;
                finalMetadata = event.data.metadata;
                // 更新最终的 metadata 和 tool_calls
                setCurrentSession(prev => {
                  if (!prev) return prev;
                  const finalMessages = prev.messages.map(m =>
                    m.id === assistantMsgId
                      ? {
                          ...m,
                          tool_calls: event.data.intermediate_steps?.map((step: any, index: number) => ({
                            id: `${assistantMsgId}_step_${index}`,
                            messageId: assistantMsgId,
                            tool: step.tool,
                            input: step.input,
                            output: step.output,
                            thought: step.thought,
                            status: step.status || 'success',
                            duration: step.duration,
                            timestamp: new Date(),
                          })) || m.tool_calls,
                          metadata: event.data.metadata,
                        }
                      : m
                  );
                  return {
                    ...prev,
                    messages: finalMessages,
                    conversation_id: event.data.conversation_id,
                  };
                });
                break;
              }
              case 'error': {
                assistantMessage.content = `⚠️ ${event.data.message}`;
                setCurrentSession(prev => ({
                  ...prev!,
                  messages: prev!.messages.map(m =>
                    m.id === assistantMsgId
                      ? { ...m, content: `⚠️ ${event.data.message}` }
                      : m
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
              m.id === assistantMsgId
                ? { ...m, content: `⚠️ 请求失败: ${err.message}` }
                : m
            ),
          }));
        }

        // 更新会话
        const finalSession = {
          ...currentSession,
          conversation_id: finalConversationId,
          title: currentSession.title.startsWith('会话') ?
            query.substring(0, 20) + (query.length > 20 ? '...' : '') :
            currentSession.title,
        };
        setCurrentSession(finalSession);

        const newSessions = sessions.map(s =>
          s.id === finalSession.id ? finalSession : s
        );
        saveSessions(newSessions);

      } else {
        const request: ChatRequest = {
          query,
          conversation_id: currentSession.conversation_id,
        };
        response = await chatbotApi.chat(Number(appId), request);

        const chatResp = response as ChatResponse;
        const assistantMessage: ExtendedMessage = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: chatResp.answer,
          timestamp: new Date(),
          citations: chatResp.metadata?.citations,
        };

        const finalMessages = [...updatedMessages, assistantMessage];
        const finalSession = {
          ...updatedSession,
          messages: finalMessages,
          conversation_id: chatResp.conversation_id,
          title: currentSession.title.startsWith('会话') ?
            query.substring(0, 20) + (query.length > 20 ? '...' : '') :
            currentSession.title,
        };
        setCurrentSession(finalSession);

        const newSessions = sessions.map(s =>
          s.id === finalSession.id ? finalSession : s
        );
        saveSessions(newSessions);
      }
    } catch (error: any) {
      console.error('发送消息失败:', error);
      // 更详细的错误提示
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
    const newSessions = sessions.map(s =>
      s.id === clearedSession.id ? clearedSession : s
    );
    saveSessions(newSessions);
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!app) return null;

  const isAgent = app.app_type === 'agent';

  return (
    <Layout style={{ height: '100vh', background: '#f5f5f5' }}>
      {/* 顶部导航 */}
      <div style={{
        background: '#fff',
        padding: '12px 24px',
        borderBottom: '1px solid #e8e8e8',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <Space>
          <Button
            icon={sidebarCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/apps')}
          >
            返回
          </Button>
          <Typography.Title level={5} style={{ margin: 0 }}>
            {app.name}
          </Typography.Title>
          <Tag color={isAgent ? 'blue' : 'green'}>
            {isAgent ? 'Agent' : '聊天助手'}
          </Tag>
        </Space>
        <Space>
          {currentSession && (
            <Popconfirm
              title="确定清空当前会话？"
              onConfirm={handleClearSession}
            >
              <Button icon={<DeleteOutlined />}>清空会话</Button>
            </Popconfirm>
          )}
          <Button
            icon={<SettingOutlined />}
            onClick={() => navigate(`/apps/${appId}/agent-config`)}
          >
            配置
          </Button>
        </Space>
      </div>

      <Layout style={{ background: '#f5f5f5' }}>
        {/* 会话侧边栏 */}
        {!sidebarCollapsed && (
          <div style={{
            width: 280,
            background: '#fff',
            borderRight: '1px solid #e8e8e8',
            display: 'flex',
            flexDirection: 'column',
          }}>
            <div style={{ padding: '16px', borderBottom: '1px solid #e8e8e8' }}>
              <Button
                type="primary"
                icon={<PlusOutlined />}
                block
                onClick={handleNewSession}
              >
                新建会话
              </Button>
            </div>
            <div style={{ flex: 1, overflow: 'auto' }}>
              <List
                dataSource={sessions}
                renderItem={(session) => (
                  <div
                    style={{
                      padding: '12px 16px',
                      cursor: 'pointer',
                      background: currentSession?.id === session.id ? '#e6f7ff' : 'transparent',
                      borderLeft: currentSession?.id === session.id ? '3px solid #1890ff' : '3px solid transparent',
                      transition: 'all 0.2s',
                    }}
                    onClick={() => handleSwitchSession(session)}
                    onMouseEnter={(e) => {
                      if (currentSession?.id !== session.id) {
                        e.currentTarget.style.background = '#fafafa';
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (currentSession?.id !== session.id) {
                        e.currentTarget.style.background = 'transparent';
                      }
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Space>
                        <MessageOutlined style={{ color: '#1890ff' }} />
                        <Typography.Text strong ellipsis style={{ maxWidth: 150 }}>
                          {session.title}
                        </Typography.Text>
                      </Space>
                      <Popconfirm
                        title="确定删除此会话？"
                        onConfirm={(e) => {
                          e?.stopPropagation();
                          handleDeleteSession(session.id);
                        }}
                        onCancel={(e) => e?.stopPropagation()}
                      >
                        <Button
                          type="text"
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={(e) => e.stopPropagation()}
                        />
                      </Popconfirm>
                    </div>
                    <div style={{ marginTop: 4, fontSize: 12, color: '#999' }}>
                      {session.messages.length} 条消息 · {session.updatedAt.toLocaleDateString()}
                    </div>
                  </div>
                )}
              />
            </div>
          </div>
        )}

        {/* 主内容区 */}
        <Layout style={{ background: '#f5f5f5' }}>
          {/* 消息列表 */}
          <div style={{
            flex: 1,
            overflow: 'auto',
            padding: '24px',
            background: '#f5f5f5',
          }}>
            {!currentSession ? (
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
              }}>
                <Card style={{ textAlign: 'center', maxWidth: 400 }}>
                  <RobotOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 24 }} />
                  <Typography.Title level={4}>开始对话</Typography.Title>
                  <Typography.Text type="secondary">
                    点击"新建会话"开始与 {app.name} 交流
                  </Typography.Text>
                  <div style={{ marginTop: 24 }}>
                    <Button
                      type="primary"
                      size="large"
                      icon={<PlusOutlined />}
                      onClick={handleNewSession}
                    >
                      新建会话
                    </Button>
                  </div>
                </Card>
              </div>
            ) : currentSession.messages.length === 0 ? (
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                height: '100%',
              }}>
                <Card style={{ textAlign: 'center', maxWidth: 400 }}>
                  <RobotOutlined style={{ fontSize: 64, color: '#1890ff', marginBottom: 24 }} />
                  <Typography.Title level={4}>有什么可以帮你的？</Typography.Title>
                  <Typography.Text type="secondary">
                    输入你的问题，开始与 {app.name} 对话
                  </Typography.Text>
                </Card>
              </div>
            ) : (
              <div style={{ maxWidth: 900, margin: '0 auto' }}>
                {currentSession.messages.map((msg) => (
                  <div
                    key={msg.id}
                    style={{
                      display: 'flex',
                      justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                      marginBottom: 24,
                    }}
                  >
                    <div style={{
                      maxWidth: '80%',
                      display: 'flex',
                      gap: 12,
                      flexDirection: msg.role === 'user' ? 'row-reverse' : 'row',
                    }}>
                      <Avatar
                        icon={msg.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                        style={{
                          backgroundColor: msg.role === 'user' ? '#1890ff' : '#52c41a',
                          flexShrink: 0,
                        }}
                      />
                      <div style={{ flex: 1 }}>
                        <Card
                          size="small"
                          style={{
                            background: msg.role === 'user' ? '#1890ff' : '#fff',
                            color: msg.role === 'user' ? '#fff' : 'inherit',
                            borderRadius: 12,
                            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                          }}
                          styles={{
                            body: { padding: '12px 16px' },
                          }}
                        >
                          <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                        </Card>

                        {/* 知识库引用 */}
                        {msg.citations && msg.citations.length > 0 && (
                          <Card
                            size="small"
                            style={{
                              marginTop: 12,
                              background: '#fff',
                              borderRadius: 12,
                              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                            }}
                          >
                            <Collapse
                              ghost
                              items={[
                                {
                                  key: 'citations',
                                  label: (
                                    <Space>
                                      <BookOutlined style={{ color: '#1890ff' }} />
                                      <Typography.Text strong style={{ color: '#1890ff' }}>
                                        知识库引用 ({msg.citations.length})
                                      </Typography.Text>
                                    </Space>
                                  ),
                                  children: (
                                    <List
                                      size="small"
                                      dataSource={msg.citations}
                                      renderItem={(item, index) => (
                                        <List.Item style={{ padding: '8px 0' }}>
                                          <div style={{ width: '100%' }}>
                                            <div style={{ marginBottom: 4 }}>
                                              <Space>
                                                <Tag color="blue">{item.knowledge_base}</Tag>
                                                {item.document_name && (
                                                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                                    📄 {item.document_name}
                                                  </Typography.Text>
                                                )}
                                                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                                  相关度: {(item.score * 100).toFixed(1)}%
                                                </Typography.Text>
                                              </Space>
                                            </div>
                                            <div style={{
                                              background: '#f5f5f5',
                                              padding: 8,
                                              borderRadius: 4,
                                              fontSize: 13,
                                              lineHeight: 1.6,
                                            }}>
                                              {item.content}
                                            </div>
                                          </div>
                                        </List.Item>
                                      )}
                                    />
                                  ),
                                },
                              ]}
                            />
                          </Card>
                        )}

                        {/* 快捷链接 */}
                        {msg.quick_links && msg.quick_links.length > 0 && (
                          <Card
                            size="small"
                            style={{
                              marginTop: 12,
                              background: '#fff',
                              borderRadius: 12,
                              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                            }}
                          >
                            <Space direction="vertical" style={{ width: '100%' }}>
                              <Space>
                                <LinkOutlined style={{ color: '#52c41a' }} />
                                <Typography.Text strong style={{ color: '#52c41a' }}>
                                  相关链接
                                </Typography.Text>
                              </Space>
                              {msg.quick_links.map((link, index) => (
                                <a
                                  key={index}
                                  href={link.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  style={{
                                    display: 'block',
                                    padding: '8px 12px',
                                    background: '#f6ffed',
                                    borderRadius: 6,
                                    border: '1px solid #b7eb8f',
                                    textDecoration: 'none',
                                  }}
                                >
                                  <div style={{ fontWeight: 500, color: '#1890ff' }}>
                                    🔗 {link.title}
                                  </div>
                                  {link.snippet && (
                                    <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                                      {link.snippet}
                                    </div>
                                  )}
                                </a>
                              ))}
                            </Space>
                          </Card>
                        )}

                        {/* Agent 运行日志按钮 - 所有 Agent 回复都显示 */}
                        {isAgent && msg.role === 'assistant' && (
                          <div style={{ marginTop: 8 }}>
                            <Tooltip title="查看 Agent 运行日志">
                              <Button
                                size="small"
                                type="dashed"
                                icon={<BugOutlined />}
                                onClick={() => handleViewLogs(msg)}
                                style={{ color: '#722ed1', borderColor: '#722ed1' }}
                              >
                                运行日志 {msg.tool_calls ? `(${msg.tool_calls.length})` : ''}
                              </Button>
                            </Tooltip>
                          </div>
                        )}

                        <div style={{
                          fontSize: 12,
                          color: '#999',
                          marginTop: 4,
                          textAlign: msg.role === 'user' ? 'right' : 'left',
                        }}>
                          {msg.timestamp.toLocaleTimeString()}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* 输入区域 */}
          {currentSession && (
            <div style={{
              padding: '24px',
              background: '#fff',
              borderTop: '1px solid #e8e8e8',
            }}>
              <div style={{ maxWidth: 900, margin: '0 auto' }}>
                <Space.Compact style={{ width: '100%' }}>
                  <Input.TextArea
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="输入你的问题... (Enter 发送，Shift+Enter 换行)"
                    autoSize={{ minRows: 1, maxRows: 4 }}
                    onPressEnter={(e) => {
                      if (!e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    disabled={sending}
                    style={{ flex: 1 }}
                  />
                  <Button
                    type="primary"
                    icon={sending ? <LoadingOutlined /> : <SendOutlined />}
                    onClick={handleSend}
                    loading={sending}
                    disabled={!inputValue.trim()}
                    style={{ height: 'auto' }}
                  >
                    发送
                  </Button>
                </Space.Compact>
              </div>
            </div>
          )}
        </Layout>
      </Layout>

      {/* Agent 运行日志抽屉 */}
      <Drawer
        title={
          <Space>
            <BugOutlined style={{ color: '#722ed1' }} />
            <span>Agent 运行日志</span>
          </Space>
        }
        placement="right"
        width={600}
        open={logDrawerOpen}
        onClose={() => setLogDrawerOpen(false)}
      >
        {selectedMessageLogs.length === 0 ? (
          <div style={{ padding: 24 }}>
            <Empty description="暂无工具调用记录" />
            <Card size="small" title="调试信息" style={{ marginTop: 16 }}>
              <Typography.Text type="secondary">
                可能原因：<br/>
                1. Agent 未配置工具<br/>
                2. 工具调用未返回 intermediate_steps<br/>
                3. 检查后端日志获取更多信息
              </Typography.Text>
            </Card>
          </div>
        ) : (
          <Timeline
            items={selectedMessageLogs.map((log, index) => ({
              dot: log.status === 'success' ?
                <CheckCircleOutlined style={{ color: '#52c41a' }} /> :
                log.status === 'error' ?
                  <ClockCircleOutlined style={{ color: '#ff4d4f' }} /> :
                  <LoadingOutlined style={{ color: '#1890ff' }} />,
              children: (
                <Card
                  size="small"
                  style={{ marginBottom: 16 }}
                  title={
                    <Space>
                      <Tag color="purple">{log.tool}</Tag>
                      <Badge
                        status={log.status === 'success' ? 'success' : log.status === 'error' ? 'error' : 'processing'}
                        text={log.status === 'success' ? '成功' : log.status === 'error' ? '失败' : '执行中'}
                      />
                      {log.duration && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {log.duration}ms
                        </Typography.Text>
                      )}
                    </Space>
                  }
                >
                  {/* 思考过程 */}
                  {log.thought && (
                    <div style={{
                      marginBottom: 12,
                      padding: '8px 12px',
                      background: '#f0f5ff',
                      borderRadius: 6,
                      border: '1px solid #d6e4ff',
                    }}>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        💭 思考过程:
                      </Typography.Text>
                      <div style={{ marginTop: 4, fontSize: 13, whiteSpace: 'pre-wrap' }}>
                        {log.thought}
                      </div>
                    </div>
                  )}

                  <Collapse
                    ghost
                    size="small"
                    items={[
                      {
                        key: 'input',
                        label: <Typography.Text strong>📥 工具输入</Typography.Text>,
                        children: (
                          <pre style={{
                            background: '#f5f5f5',
                            padding: 12,
                            borderRadius: 6,
                            fontSize: 12,
                            maxHeight: 200,
                            overflow: 'auto',
                            margin: 0,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                          }}>
                            {log.input}
                          </pre>
                        ),
                      },
                      {
                        key: 'output',
                        label: <Typography.Text strong>📤 工具输出</Typography.Text>,
                        children: (
                          <pre style={{
                            background: '#f5f5f5',
                            padding: 12,
                            borderRadius: 6,
                            fontSize: 12,
                            maxHeight: 300,
                            overflow: 'auto',
                            margin: 0,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-all',
                          }}>
                            {log.output}
                          </pre>
                        ),
                      },
                    ]}
                  />

                  <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                    <ClockCircleOutlined /> {log.timestamp.toLocaleTimeString()}
                  </div>
                </Card>
              ),
            }))}
          />
        )}

        {/* 元数据信息 */}
        {currentSession && currentSession.messages.length > 0 && (() => {
          const selectedMsg = currentSession.messages.find(m => m.id === selectedMessageLogs[0]?.messageId);
          const thoughts = selectedMsg?.metadata?.thoughts;
          return (
            <div>
              {/* 思考过程汇总 */}
              {thoughts && thoughts.length > 0 && (
                <Card size="small" title="💭 思考过程" style={{ marginTop: 16 }}>
                  {thoughts.map((thought: string, idx: number) => (
                    <div key={idx} style={{
                      marginBottom: 8,
                      padding: 8,
                      background: '#fffbe6',
                      borderRadius: 4,
                      fontSize: 12,
                    }}>
                      <Typography.Text type="secondary">第 {idx + 1} 步推理：</Typography.Text>
                      <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{thought}</div>
                    </div>
                  ))}
                </Card>
              )}
              <Card size="small" title="📊 响应元数据" style={{ marginTop: 16 }}>
                <Collapse
                  ghost
                  size="small"
                  items={[
                    {
                      key: 'metadata',
                      label: <Typography.Text type="secondary">查看完整元数据</Typography.Text>,
                      children: (
                        <pre style={{
                          background: '#f5f5f5',
                          padding: 12,
                          borderRadius: 6,
                          fontSize: 11,
                          maxHeight: 300,
                          overflow: 'auto',
                          margin: 0,
                        }}>
                          {JSON.stringify(selectedMsg?.metadata || {}, null, 2)}
                        </pre>
                      ),
                    },
                  ]}
                />
              </Card>
            </div>
          );
        })()}
      </Drawer>
    </Layout>
  );
};

export default AppRunner;
