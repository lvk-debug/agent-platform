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
} from 'antd'
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  PlayCircleOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { appsApi, AppData, CreateAppData } from '../services/apps'

const { Title, Text } = Typography
const { Option } = Select

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
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 250,
      render: (_: any, record: AppData) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => {
              if (record.app_type === 'chatbot') {
                navigate(`/apps/${record.id}/chatbot`)
              } else {
                navigate(`/apps/${record.id}`)
              }
            }}
          >
            编辑
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
