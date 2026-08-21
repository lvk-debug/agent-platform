import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Input,
  Select,
  Modal,
  Form,
  App,
  Popconfirm,
  Typography,
  Row,
  Col,
  Drawer,
  Timeline,
  Collapse,
  Empty,
  Spin,
  Badge,
} from 'antd'
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  DownOutlined,
  ShareAltOutlined,
  RocketOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { appsApi, AppData, CreateAppData } from '../services/apps'

const { Title, Text } = Typography
const { Option } = Select
const { Panel } = Collapse

interface Conversation {
  id: number
  name: string
  app_id: number
  created_at: string
  updated_at: string
  message_count?: number
}

interface Message {
  id: number
  conversation_id: number
  role: 'user' | 'assistant'
  content: string
  tool_calls?: Array<{
    tool: string
    input: string
    output: string
    thought?: string
    status?: 'success' | 'error' | 'running'
    duration?: number
  }>
  metadata?: Record<string, any>
  created_at: string
}

const Apps: React.FC = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [apps, setApps] = useState<AppData[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const [appType, setAppType] = useState<string | undefined>(undefined)
  const [status, setStatus] = useState<string | undefined>(undefined)
  const [searchText, setSearchText] = useState('')
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const { message } = App.useApp()

  // 运行日志相关状态
  const [logDrawerOpen, setLogDrawerOpen] = useState(false)
  const [currentApp, setCurrentApp] = useState<AppData | null>(null)
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(false)
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [messagesLoading, setMessagesLoading] = useState(false)

  // 初始加载 / 筛选条件变化时重新加载
  useEffect(() => {
    setApps([])
    setNextCursor(null)
    setHasMore(false)
    fetchApps(true)
  }, [appType, status])

  // 检查是否需要打开创建弹窗
  useEffect(() => {
    const createType = searchParams.get('create')
    if (createType) {
      createForm.setFieldsValue({ app_type: createType })
      setCreateModalVisible(true)
    }
  }, [searchParams])

  const fetchApps = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? undefined : nextCursor ?? undefined
      const response = await appsApi.getApps({
        cursor,
        limit: 20,
        app_type: appType,
        status: status,
      })
      const { items, next_cursor, has_more } = response.data
      if (reset) {
        setApps(items)
      } else {
        setApps((prev) => [...prev, ...items])
      }
      setNextCursor(next_cursor)
      setHasMore(has_more)
    } catch (error) {
      message.error('获取应用列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: CreateAppData) => {
    try {
      await appsApi.createApp(values)
      message.success('应用创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      // 重新加载列表
      setApps([])
      setNextCursor(null)
      fetchApps(true)
    } catch (error) {
      message.error('创建应用失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await appsApi.deleteApp(id)
      message.success('应用已删除')
      setApps((prev) => prev.filter((app) => app.id !== id))
    } catch (error) {
      message.error('删除应用失败')
    }
  }

  const handlePublish = async (id: number) => {
    try {
      await appsApi.publishApp(id)
      message.success('应用已发布')
      setApps([])
      setNextCursor(null)
      fetchApps(true)
    } catch (error) {
      message.error('发布应用失败')
    }
  }

  // 打开运行日志抽屉
  const handleViewLogs = async (app: AppData) => {
    setCurrentApp(app)
    setLogDrawerOpen(true)
    setSelectedConversation(null)
    setMessages([])
    await fetchConversations(app.id)
  }

  // 获取应用会话列表
  const fetchConversations = async (appId: number) => {
    setConversationsLoading(true)
    try {
      const response = await appsApi.getConversations(appId, { limit: 50 })
      setConversations(response.data.items || [])
    } catch (error) {
      console.error('获取会话列表失败:', error)
      message.error('获取会话列表失败')
    } finally {
      setConversationsLoading(false)
    }
  }

  // 获取会话消息
  const handleSelectConversation = async (conversationId: number) => {
    setSelectedConversation(conversationId)
    setMessagesLoading(true)
    try {
      const response = await appsApi.getMessages(currentApp!.id, conversationId)
      setMessages(response.data.items || [])
    } catch (error) {
      console.error('获取消息列表失败:', error)
      message.error('获取消息列表失败')
    } finally {
      setMessagesLoading(false)
    }
  }

  // 获取工具状态颜色
  const getToolStatusColor = (status?: string) => {
    switch (status) {
      case 'success':
        return 'green'
      case 'error':
        return 'red'
      case 'running':
        return 'blue'
      default:
        return 'gray'
    }
  }

  // 应用类型标签颜色
  const getAppTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      chatbot: 'blue',
      workflow: 'green',
      agent: 'purple',
    }
    return colors[type] || 'default'
  }

  // 应用类型中文名
  const getAppTypeName = (type: string) => {
    const names: Record<string, string> = {
      chatbot: '聊天助手',
      workflow: '工作流',
      agent: 'Agent',
    }
    return names[type] || type
  }

  // 状态标签颜色
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'default',
      published: 'success',
      disabled: 'error',
    }
    return colors[status] || 'default'
  }

  // 状态中文名
  const getStatusName = (status: string) => {
    const names: Record<string, string> = {
      draft: '草稿',
      published: '已发布',
      disabled: '已禁用',
    }
    return names[status] || status
  }

  // 表格列定义
  const columns = [
    {
      title: '应用名称',
      dataIndex: 'name',
      key: 'name',
      width: 100,
      render: (text: string, record: AppData) => (
        <Space>
          <Text strong>{text}</Text>
          <Tag color={getAppTypeColor(record.app_type)}>
            {getAppTypeName(record.app_type)}
          </Tag>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusName(status)}</Tag>
      ),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
      width: 80,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 100,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 300,
      render: (_: any, record: AppData) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => {
              if (record.app_type === 'chatbot') {
                navigate(`/apps/${record.id}/chatbot`)
              } else if (record.app_type === 'workflow') {
                navigate(`/apps/${record.id}/workflow`)
              } else if (record.app_type === 'agent') {
                navigate(`/apps/${record.id}/agent`)
              } else {
                navigate(`/apps/${record.id}`)
              }
            }}
          >
            编辑
          </Button>
          {record.status === 'published' && (
            <Button
              type="link"
              icon={<RocketOutlined />}
              onClick={() => navigate(`/apps/${record.id}/run`)}
              style={{ color: '#52c41a' }}
            >
              运行
            </Button>
          )}
          {record.status === 'published' && (
            <Button
              type="link"
              icon={<ShareAltOutlined />}
              onClick={() => navigate(`/apps/${record.id}/publish`)}
            >
              发布管理
            </Button>
          )}
          <Button
            type="link"
            icon={<FileTextOutlined />}
            onClick={() => handleViewLogs(record)}
            style={{ color: '#722ed1' }}
          >
            运行日志
          </Button>
          {record.status === 'draft' && (
            <Button
              type="link"
              icon={<PlayCircleOutlined />}
              onClick={() => handlePublish(record.id)}
            >
              发布
            </Button>
          )}
          <Popconfirm
            title="确定要删除此应用吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-4 flex justify-between">
        <Title level={4} className="m-0">
          工作室
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
        >
          创建应用
        </Button>
      </div>

      {/* 筛选栏 */}
      <Card className="mb-4">
        <Row gutter={16}>
          <Col xs={24} sm={8}>
            <Input
              placeholder="搜索应用名称"
              prefix={<SearchOutlined />}
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              onPressEnter={() => {
                setApps([])
                setNextCursor(null)
                fetchApps(true)
              }}
            />
          </Col>
          <Col xs={24} sm={8}>
            <Select
              placeholder="应用类型"
              className="w-full"
              allowClear
              value={appType}
              onChange={(value) => setAppType(value)}
            >
              <Option value="chatbot">聊天助手</Option>
              <Option value="workflow">工作流</Option>
              <Option value="agent">Agent</Option>
            </Select>
          </Col>
          <Col xs={24} sm={8}>
            <Select
              placeholder="状态"
              className="w-full"
              allowClear
              value={status}
              onChange={(value) => setStatus(value)}
            >
              <Option value="draft">草稿</Option>
              <Option value="published">已发布</Option>
              <Option value="disabled">已禁用</Option>
            </Select>
          </Col>
        </Row>
      </Card>

      {/* 应用列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={apps}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
        {hasMore && (
          <div className="text-center mt-4">
            <Button
              icon={<DownOutlined />}
              loading={loading}
              onClick={() => fetchApps(false)}
            >
              加载更多
            </Button>
          </div>
        )}
      </Card>

      {/* 运行日志抽屉 */}
      <Drawer
        title={
          <Space>
            <FileTextOutlined />
            <span>运行日志 - {currentApp?.name}</span>
          </Space>
        }
        open={logDrawerOpen}
        onClose={() => {
          setLogDrawerOpen(false)
          setCurrentApp(null)
          setSelectedConversation(null)
          setMessages([])
        }}
        width={800}
      >
        <Row gutter={16} style={{ height: '100%' }}>
          {/* 左侧：会话列表 */}
          <Col span={8} style={{ borderRight: '1px solid #f0f0f0', paddingRight: 16 }}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>会话列表</Text>
            </div>
            <Spin spinning={conversationsLoading}>
              {conversations.length === 0 ? (
                <Empty description="暂无会话记录" />
              ) : (
                <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
                  {conversations.map((conv) => (
                    <Card
                      key={conv.id}
                      size="small"
                      hoverable
                      style={{
                        marginBottom: 8,
                        borderColor: selectedConversation === conv.id ? '#722ed1' : undefined,
                      }}
                      onClick={() => handleSelectConversation(conv.id)}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text ellipsis style={{ maxWidth: 150 }}>
                          {conv.name || `会话 ${conv.id}`}
                        </Text>
                        <Badge count={conv.message_count || 0} style={{ backgroundColor: '#722ed1' }} />
                      </div>
                      <div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(conv.created_at).toLocaleString()}
                        </Text>
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </Spin>
          </Col>

          {/* 右侧：消息详情 */}
          <Col span={16} style={{ paddingLeft: 16 }}>
            <div style={{ marginBottom: 16 }}>
              <Text strong>消息详情</Text>
            </div>
            <Spin spinning={messagesLoading}>
              {!selectedConversation ? (
                <Empty description="请选择一个会话查看消息" />
              ) : messages.length === 0 ? (
                <Empty description="暂无消息" />
              ) : (
                <div style={{ maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>
                  {messages.map((msg) => (
                    <Card
                      key={msg.id}
                      size="small"
                      style={{
                        marginBottom: 12,
                        borderColor: msg.role === 'user' ? '#1890ff' : '#722ed1',
                      }}
                    >
                      <div style={{ marginBottom: 8 }}>
                        <Tag color={msg.role === 'user' ? 'blue' : 'purple'}>
                          {msg.role === 'user' ? '用户' : '助手'}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(msg.created_at).toLocaleString()}
                        </Text>
                      </div>
                      <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>

                      {/* 显示工具调用记录 */}
                      {msg.tool_calls && msg.tool_calls.length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <Collapse size="small">
                            <Panel
                              header={
                                <Space>
                                  <span>工具调用记录</span>
                                  <Badge count={msg.tool_calls.length} style={{ backgroundColor: '#722ed1' }} />
                                </Space>
                              }
                              key="tool_calls"
                            >
                              <Timeline
                                items={msg.tool_calls.map((step, index) => ({
                                  color: getToolStatusColor(step.status),
                                  children: (
                                    <div key={index}>
                                      <div>
                                        <Tag color={getToolStatusColor(step.status)}>{step.tool}</Tag>
                                        {step.duration && (
                                          <Text type="secondary" style={{ fontSize: 12 }}>
                                            ({step.duration}ms)
                                          </Text>
                                        )}
                                      </div>
                                      {step.thought && (
                                        <div style={{ marginTop: 4, color: '#666', fontSize: 12 }}>
                                          💭 {step.thought}
                                        </div>
                                      )}
                                      <div style={{ marginTop: 4 }}>
                                        <Text type="secondary" style={{ fontSize: 12 }}>输入:</Text>
                                        <pre
                                          style={{
                                            background: '#f5f5f5',
                                            padding: 8,
                                            borderRadius: 4,
                                            fontSize: 12,
                                            maxHeight: 100,
                                            overflow: 'auto',
                                          }}
                                        >
                                          {step.input}
                                        </pre>
                                      </div>
                                      {step.output && (
                                        <div style={{ marginTop: 4 }}>
                                          <Text type="secondary" style={{ fontSize: 12 }}>输出:</Text>
                                          <pre
                                            style={{
                                              background: '#f5f5f5',
                                              padding: 8,
                                              borderRadius: 4,
                                              fontSize: 12,
                                              maxHeight: 150,
                                              overflow: 'auto',
                                            }}
                                          >
                                            {step.output}
                                          </pre>
                                        </div>
                                      )}
                                    </div>
                                  ),
                                }))}
                              />
                            </Panel>
                          </Collapse>
                        </div>
                      )}

                      {/* 显示元数据 */}
                      {msg.metadata && Object.keys(msg.metadata).length > 0 && (
                        <div style={{ marginTop: 12 }}>
                          <Collapse size="small">
                            {/* 思考过程 */}
                            {msg.metadata.thoughts && msg.metadata.thoughts.length > 0 && (
                              <Panel
                                header={
                                  <Space>
                                    <span>💭 思考过程</span>
                                    <Badge count={msg.metadata.thoughts.length} style={{ backgroundColor: '#faad14' }} />
                                  </Space>
                                }
                                key="thoughts"
                              >
                                {msg.metadata.thoughts.map((thought: string, idx: number) => (
                                  <div key={idx} style={{ marginBottom: 8, padding: 8, background: '#fffbe6', borderRadius: 4, fontSize: 12 }}>
                                    <Text type="secondary">第 {idx + 1} 步推理：</Text>
                                    <div style={{ whiteSpace: 'pre-wrap', marginTop: 4 }}>{thought}</div>
                                  </div>
                                ))}
                              </Panel>
                            )}
                            <Panel header="📊 响应元数据" key="metadata">
                              <pre
                                style={{
                                  background: '#f5f5f5',
                                  padding: 8,
                                  borderRadius: 4,
                                  fontSize: 12,
                                  maxHeight: 200,
                                  overflow: 'auto',
                                }}
                              >
                                {JSON.stringify(msg.metadata, null, 2)}
                              </pre>
                            </Panel>
                          </Collapse>
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              )}
            </Spin>
          </Col>
        </Row>
      </Drawer>

      {/* 创建应用弹窗 */}
      <Modal
        title="创建应用"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        footer={null}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ app_type: 'chatbot' }}
        >
          <Form.Item
            name="name"
            label="应用名称"
            rules={[{ required: true, message: '请输入应用名称' }]}
          >
            <Input placeholder="请输入应用名称" />
          </Form.Item>

          <Form.Item
            name="app_type"
            label="应用类型"
            rules={[{ required: true, message: '请选择应用类型' }]}
          >
            <Select>
              <Option value="chatbot">聊天助手</Option>
              <Option value="workflow">工作流</Option>
              <Option value="agent">Agent</Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} placeholder="请输入应用描述" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button
                onClick={() => {
                  setCreateModalVisible(false)
                  createForm.resetFields()
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Apps
