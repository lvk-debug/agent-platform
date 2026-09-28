import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Card, Input, Button, Space, Typography, Tag, Spin, message, Divider, Timeline, Switch, Form, Select, Tooltip, Breadcrumb } from 'antd';
import { SendOutlined, ClearOutlined, ExperimentOutlined, SettingOutlined, RocketOutlined, ReloadOutlined, InfoCircleOutlined, LinkOutlined } from '@ant-design/icons';
import { agentApi } from '@/services/agent';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface DebugMessage {
  id: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  timestamp: number;
  toolCalls?: ToolCall[];
  metadata?: {
    model?: string;
    tokens?: number;
    latency?: number;
    iterations?: number;
    quick_links?: QuickLink[];
  };
}

interface QuickLink {
  title: string;
  url: string;
  description: string;
}

interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: string;
  status: 'pending' | 'success' | 'error';
  duration?: number;
}

const AgentDebug: React.FC = () => {
  const { appId } = useParams<{ appId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<DebugMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [config, setConfig] = useState<any>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [form] = Form.useForm();

  // 调试配置
  const [debugConfig, setDebugConfig] = useState({
    showMetadata: true,
    showToolCalls: true,
    streamOutput: false,
    maxIterations: 10,
  });

  useEffect(() => {
    if (appId) {
      loadConfig();
    }
  }, [appId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadConfig = async () => {
    try {
      const data = await agentApi.getConfig(Number(appId));
      setConfig(data);

      // 检查模型是否配置
      if (!data.config?.model_id) {
        message.warning('请先在 Agent 编排页面配置模型', 3);
      }
    } catch (error) {
      message.error('加载配置失败');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!inputValue.trim() || loading) return;

    // 检查模型是否配置
    if (!config?.config?.model_id) {
      message.error('请先在 Agent 编排页面配置模型');
      return;
    }

    const userMessage: DebugMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: Date.now(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setLoading(true);

    const startTime = Date.now();

    try {
      const response = await agentApi.chat(Number(appId), {
        query: inputValue,
      });

      const assistantMessage: DebugMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: response.answer,
        timestamp: Date.now(),
        toolCalls: response.intermediate_steps?.map((step: any, idx: number) => ({
          id: idx.toString(),
          name: step.tool,
          input: { query: step.input },
          output: step.output,
          status: 'success' as const,
        })) || [],
        metadata: {
          model: config?.config?.model_name || response.metadata?.model || 'unknown',
          tokens: response.metadata?.total_tokens,
          latency: Date.now() - startTime,
          iterations: response.intermediate_steps?.length || 0,
        },
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (error) {
      const errorMessage: DebugMessage = {
        id: (Date.now() + 1).toString(),
        role: 'system',
        content: `错误: ${error instanceof Error ? error.message : '请求失败'}`,
        timestamp: Date.now(),
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    setMessages([]);
    message.success('已清空对话');
  };

  const renderToolCalls = (toolCalls: ToolCall[]) => {
    if (!debugConfig.showToolCalls || !toolCalls?.length) return null;

    return (
      <div style={{ marginTop: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <ExperimentOutlined /> 工具调用:
        </Text>
        {toolCalls.map((call) => (
          <Timeline.Item
            key={call.id}
            color={call.status === 'success' ? 'green' : call.status === 'error' ? 'red' : 'blue'}
            style={{ marginTop: 4 }}
          >
            <Card size="small" style={{ background: '#f6f6f6' }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space>
                  <Tag color="blue">{call.name}</Tag>
                  <Tag color={call.status === 'success' ? 'green' : call.status === 'error' ? 'red' : 'orange'}>
                    {call.status}
                  </Tag>
                  {call.duration && <Text type="secondary">{call.duration}ms</Text>}
                </Space>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>输入:</Text>
                  <pre style={{ margin: 0, fontSize: 12, background: '#fff', padding: 4, borderRadius: 4 }}>
                    {JSON.stringify(call.input, null, 2)}
                  </pre>
                </div>
                {call.output && (
                  <div>
                    <Text type="secondary" style={{ fontSize: 12 }}>输出:</Text>
                    <pre style={{ margin: 0, fontSize: 12, background: '#fff', padding: 4, borderRadius: 4 }}>
                      {call.output}
                    </pre>
                  </div>
                )}
              </Space>
            </Card>
          </Timeline.Item>
        ))}
      </div>
    );
  };

  const renderMetadata = (metadata: DebugMessage['metadata']) => {
    if (!debugConfig.showMetadata || !metadata) return null;

    return (
      <div style={{ marginTop: 8 }}>
        <Space size={16}>
          {metadata.model && (
            <Tooltip title="使用的模型">
              <Tag icon={<RocketOutlined />}>{metadata.model}</Tag>
            </Tooltip>
          )}
          {metadata.tokens && (
            <Tooltip title="Token 消耗">
              <Tag>Token: {metadata.tokens}</Tag>
            </Tooltip>
          )}
          {metadata.latency && (
            <Tooltip title="响应延迟">
              <Tag>延迟: {metadata.latency}ms</Tag>
            </Tooltip>
          )}
          {metadata.iterations !== undefined && (
            <Tooltip title="Agent 迭代次数">
              <Tag icon={<ReloadOutlined />}>迭代: {metadata.iterations}</Tag>
            </Tooltip>
          )}
        </Space>
      </div>
    );
  };

  const renderQuickLinks = (quickLinks?: QuickLink[]) => {
    if (!quickLinks?.length) return null;

    return (
      <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px dashed #e8e8e8' }}>
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          <LinkOutlined /> 快捷导航：
        </Text>
        <Space size={8} wrap>
          {quickLinks.map((link, index) => (
            <Button
              key={index}
              size="small"
              type="primary"
              ghost
              icon={<LinkOutlined />}
              onClick={() => navigate(link.url)}
              title={link.description}
            >
              {link.title}
            </Button>
          ))}
        </Space>
      </div>
    );
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#f5f5f5' }}>
      {/* 左侧 - 调试配置 */}
      <div style={{ width: 280, padding: 16, background: '#fff', borderRight: '1px solid #e8e8e8' }}>
        <Title level={4}>
          <ExperimentOutlined /> 调试配置
        </Title>

        <Form layout="vertical" form={form}>
          <Form.Item label="显示元数据">
            <Switch
              checked={debugConfig.showMetadata}
              onChange={(checked) => setDebugConfig(prev => ({ ...prev, showMetadata: checked }))}
            />
          </Form.Item>

          <Form.Item label="显示工具调用">
            <Switch
              checked={debugConfig.showToolCalls}
              onChange={(checked) => setDebugConfig(prev => ({ ...prev, showToolCalls: checked }))}
            />
          </Form.Item>

          <Form.Item label="最大迭代次数">
            <Select
              value={debugConfig.maxIterations}
              onChange={(value) => setDebugConfig(prev => ({ ...prev, maxIterations: value }))}
              options={[
                { value: 5, label: '5 次' },
                { value: 10, label: '10 次' },
                { value: 20, label: '20 次' },
                { value: 50, label: '50 次' },
              ]}
            />
          </Form.Item>
        </Form>

        <Divider />

        <Title level={5}>Agent 配置</Title>
        {config ? (
          <Space direction="vertical" size={8} style={{ width: '100%' }}>
            <div>
              <Text type="secondary">模型: </Text>
              {config.config?.model_id ? (
                <Tag color="green">已配置 (ID: {config.config.model_id})</Tag>
              ) : (
                <Tag color="red">未配置</Tag>
              )}
            </div>
            <div>
              <Text type="secondary">提示词:</Text>
              <Paragraph
                ellipsis={{ rows: 3, expandable: true, symbol: '展开' }}
                style={{ margin: 4, fontSize: 12 }}
              >
                {config.config?.prompt?.system_prompt || '未设置'}
              </Paragraph>
            </div>
            <div>
              <Text type="secondary">工具数量: </Text>
              <Tag>{config.config?.tools?.length || 0}</Tag>
            </div>
            <div>
              <Text type="secondary">知识库: </Text>
              <Tag>{config.config?.knowledge_bases?.length || 0}</Tag>
            </div>
          </Space>
        ) : (
          <Spin size="small" />
        )}

        <Divider />

        {/* 调试信息 */}
        <Title level={5}>调试信息</Title>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Button
            block
            size="small"
            onClick={async () => {
              try {
                const data = await agentApi.debugConfig(Number(appId));
                console.log('调试配置:', data);
                message.info(`model_id: ${data.model_id || '未设置'}`);
              } catch (error) {
                console.error('调试配置失败:', error);
                message.error('调试配置失败');
              }
            }}
          >
            检查配置
          </Button>
          <Button
            block
            size="small"
            onClick={async () => {
              try {
                const data = await agentApi.debugModel(Number(appId));
                console.log('调试模型:', data);
                if (data.error) {
                  message.error(data.error);
                } else {
                  message.success(`模型: ${data.model_name} (${data.model_model_id})`);
                }
              } catch (error) {
                console.error('调试模型失败:', error);
                message.error('调试模型失败');
              }
            }}
          >
            测试模型
          </Button>
        </Space>

        <Divider />

        <Title level={5}>快捷测试</Title>
        <Space direction="vertical" size={8} style={{ width: '100%' }}>
          <Button
            block
            onClick={() => setInputValue('你好，请自我介绍一下')}
          >
            自我介绍测试
          </Button>
          <Button
            block
            onClick={() => setInputValue('今天天气怎么样？')}
          >
            工具调用测试
          </Button>
          <Button
            block
            onClick={() => setInputValue('请帮我搜索最新的AI新闻')}
          >
            搜索能力测试
          </Button>
        </Space>
      </div>

      {/* 中间 - 对话区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* 头部 */}
        <div style={{ padding: '12px 24px', background: '#fff', borderBottom: '1px solid #e8e8e8' }}>
          <Breadcrumb
            items={[
              { title: <Link to="/apps">应用</Link> },
              { title: <Link to={`/apps/${appId}/agent`}>Agent 编排</Link> },
              { title: '调试' },
            ]}
            style={{ marginBottom: 8 }}
          />
          <Space>
            <Title level={4} style={{ margin: 0 }}>
              <ExperimentOutlined /> Agent 调试
            </Title>
            <Button icon={<ClearOutlined />} onClick={handleClear}>
              清空对话
            </Button>
            <Link to={`/apps/${appId}/agent`}>
              <Button icon={<SettingOutlined />}>
                编排配置
              </Button>
            </Link>
          </Space>
        </div>

        {/* 消息列表 */}
        <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
          {/* 模型未配置警告 */}
          {config && !config.config?.model_id && (
            <div style={{ marginBottom: 16, padding: 16, background: '#fff7e6', border: '1px solid #ffd591', borderRadius: 8 }}>
              <Space>
                <InfoCircleOutlined style={{ color: '#fa8c16' }} />
                <Text>请先配置模型后再进行调试</Text>
                <Link to={`/apps/${appId}/agent`}>
                  <Button type="primary" size="small">前往配置</Button>
                </Link>
              </Space>
            </div>
          )}

          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '100px 0', color: '#999' }}>
              <ExperimentOutlined style={{ fontSize: 48, marginBottom: 16 }} />
              <div>开始调试 Agent</div>
              <div style={{ fontSize: 12 }}>输入消息测试 Agent 的响应</div>
            </div>
          ) : (
            messages.map((msg) => (
              <div
                key={msg.id}
                style={{
                  marginBottom: 16,
                  display: 'flex',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <div
                  style={{
                    maxWidth: '70%',
                    padding: '12px 16px',
                    borderRadius: 12,
                    background: msg.role === 'user' ? '#1890ff' :
                               msg.role === 'system' ? '#ff4d4f' : '#f0f0f0',
                    color: msg.role === 'user' || msg.role === 'system' ? '#fff' : '#333',
                  }}
                >
                  <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                  {renderToolCalls(msg.toolCalls || [])}
                  {renderMetadata(msg.metadata)}
                  {msg.role === 'assistant' && renderQuickLinks(msg.metadata?.quick_links)}
                  <div style={{ fontSize: 10, marginTop: 8, opacity: 0.6 }}>
                    {new Date(msg.timestamp).toLocaleTimeString()}
                  </div>
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div style={{ padding: 16, background: '#fff', borderTop: '1px solid #e8e8e8' }}>
          <Space.Compact style={{ width: '100%' }}>
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="输入测试消息..."
              autoSize={{ minRows: 1, maxRows: 4 }}
              onPressEnter={(e) => {
                if (!e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
            >
              发送
            </Button>
          </Space.Compact>
          <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
            <InfoCircleOutlined /> 按 Enter 发送，Shift+Enter 换行
          </div>
        </div>
      </div>
    </div>
  );
};

export default AgentDebug;
