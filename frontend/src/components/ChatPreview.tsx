/**
 * 聊天调试预览组件
 * 支持实时聊天测试，展示对话历史，显示知识库引用，显示快捷导航链接
 */
import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Input, Button, Avatar, Space, Typography, Spin, Empty, Tag, Collapse } from 'antd';
import {
  SendOutlined,
  UserOutlined,
  RobotOutlined,
  ClearOutlined,
  FileTextOutlined,
  LinkOutlined,
} from '@ant-design/icons';
import { chatbotApi, ChatRequest } from '@/services/chatbot';

const { Text } = Typography;
const { TextArea } = Input;

interface Citation {
  knowledge_base_id: number;
  knowledge_base_name: string;
  document_id?: number;
  document_name: string;
  segment_id?: number;
  content: string;
  score: number;
  page_number?: number;
  header_path?: string;
}

interface QuickLink {
  title: string;
  url: string;
  description: string;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  loading?: boolean;
  citations?: Citation[];
  quick_links?: QuickLink[];
}

interface ChatPreviewProps {
  appId: number;
  config?: {
    variables?: Array<{
      key: string;
      name: string;
      required: boolean;
      default?: string;
    }>;
  };
  inputs?: Record<string, string>;
}

const ChatPreview: React.FC<ChatPreviewProps> = ({ appId, config, inputs }) => {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<number | undefined>();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    // 添加助手消息占位
    const assistantMessageId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        loading: true,
      },
    ]);

    try {
      const request: ChatRequest = {
        query: userMessage.content,
        conversation_id: conversationId,
        inputs: inputs,
        response_mode: 'blocking',
      };

      const response = await chatbotApi.chat(appId, request);

      // 更新会话 ID
      if (!conversationId) {
        setConversationId(response.conversation_id);
      }

      // 提取引用信息
      const citations = response.metadata?.citations || [];

      // 更新助手消息
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? { ...msg, content: response.answer, loading: false, citations }
            : msg
        )
      );
    } catch (error: any) {
      // 显示错误消息
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantMessageId
            ? {
                ...msg,
                content: `错误：${error.message || '发送失败，请重试'}`,
                loading: false,
              }
            : msg
        )
      );
    } finally {
      setLoading(false);
    }
  };

  // 清空对话
  const handleClear = () => {
    setMessages([]);
    setConversationId(undefined);
  };

  // 处理键盘事件
  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 bg-[#fafafa]">
        {messages.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="开始聊天测试"
            className="mt-[40%]"
          />
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex mb-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <Avatar
                  icon={<RobotOutlined />}
                  className="bg-primary mr-2"
                />
              )}
              <div
                className={`max-w-[70%] px-4 py-3 shadow-bubble ${
                  msg.role === 'user'
                    ? 'chat-bubble-user'
                    : 'chat-bubble-assistant'
                }`}
              >
                {msg.loading ? (
                  <Spin size="small" />
                ) : (
                  <>
                    <Text className="whitespace-pre-wrap" style={{ color: 'inherit' }}>
                      {msg.content}
                    </Text>
                    {/* 引用信息 */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div className="mt-3 pt-2 border-t border-gray-200">
                        <Collapse
                          ghost
                          size="small"
                          items={[{
                            key: 'citations',
                            label: (
                              <Text type="secondary" className="text-xs">
                                <FileTextOutlined className="mr-1" />
                                参考来源 ({msg.citations.length})
                              </Text>
                            ),
                            children: (
                              <div className="space-y-2">
                                {msg.citations.map((cite, idx) => (
                                  <div key={idx} className="text-xs bg-gray-50 rounded p-2">
                                    <div className="flex items-center gap-1 mb-1">
                                      <Tag color="blue" className="text-xs mr-1">
                                        {cite.knowledge_base_name}
                                      </Tag>
                                      <Text type="secondary" className="text-xs">
                                        {cite.document_name}
                                      </Text>
                                      {cite.page_number && (
                                        <Tag className="text-xs">P.{cite.page_number}</Tag>
                                      )}
                                      {cite.header_path && (
                                        <Text type="secondary" className="text-xs ml-1">
                                          § {cite.header_path}
                                        </Text>
                                      )}
                                      <Text type="secondary" className="text-xs ml-auto">
                                        {(cite.score * 100).toFixed(1)}%
                                      </Text>
                                    </div>
                                    <Text type="secondary" className="text-xs leading-relaxed">
                                      {cite.content.length > 150
                                        ? cite.content.slice(0, 150) + '...'
                                        : cite.content}
                                    </Text>
                                  </div>
                                ))}
                              </div>
                            ),
                          }]}
                        />
                      </div>
                    )}
                  </>
                )}
              </div>
              {msg.role === 'user' && (
                <Avatar
                  icon={<UserOutlined />}
                  className="bg-green-500 ml-2"
                />
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="p-4 border-t border-border bg-white">
        <Space.Compact className="w-full">
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="输入消息..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
            className="rounded-l-lg"
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
            className="h-auto rounded-r-lg"
          />
        </Space.Compact>
        <div className="mt-2 flex justify-end">
          <Button
            type="text"
            icon={<ClearOutlined />}
            onClick={handleClear}
            disabled={messages.length === 0}
            size="small"
          >
            清空对话
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ChatPreview;
