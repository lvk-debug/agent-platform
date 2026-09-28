import React, { useEffect, useState } from 'react'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  Select,
  App,
  Popconfirm,
  Typography,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { modelsApi, ModelProviderData, CreateModelProviderData } from '@/services/models'

const { Title, Text } = Typography
const { Option } = Select

const Models: React.FC = () => {
  const navigate = useNavigate()
  const [providers, setProviders] = useState<ModelProviderData[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [editingProvider, setEditingProvider] = useState<ModelProviderData | null>(null)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const { message } = App.useApp()

  useEffect(() => {
    fetchProviders()
  }, [])

  const fetchProviders = async () => {
    setLoading(true)
    try {
      const response = await modelsApi.getProviders()
      setProviders(response.data)
    } catch (error) {
      message.error('获取模型供应商列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: CreateModelProviderData) => {
    try {
      await modelsApi.createProvider(values)
      message.success('模型供应商创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchProviders()
    } catch (error) {
      message.error('创建模型供应商失败')
    }
  }

  const handleEdit = (record: ModelProviderData) => {
    setEditingProvider(record)
    editForm.setFieldsValue({
      name: record.name,
      api_endpoint: record.api_endpoint,
    })
    setEditModalVisible(true)
  }

  const handleUpdate = async (values: any) => {
    if (!editingProvider) return
    try {
      await modelsApi.updateProvider(editingProvider.id, values)
      message.success('更新成功')
      setEditModalVisible(false)
      setEditingProvider(null)
      fetchProviders()
    } catch (error) {
      message.error('更新失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await modelsApi.deleteProvider(id)
      message.success('删除成功')
      fetchProviders()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleManageModels = (record: ModelProviderData) => {
    navigate(`/models/${record.id}`)
  }

  const getProviderTypeName = (type: string) => {
    const names: Record<string, string> = {
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      local: '本地模型',
      custom: '自定义',
    }
    return names[type] || type
  }

  const getProviderTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      openai: 'green',
      anthropic: 'blue',
      local: 'orange',
      custom: 'purple',
    }
    return colors[type] || 'default'
  }

  const columns = [
    {
      title: '供应商名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ModelProviderData) => (
        <Space>
          <ApiOutlined />
          <Text strong>{text}</Text>
          <Tag color={getProviderTypeColor(record.provider_type)}>
            {getProviderTypeName(record.provider_type)}
          </Tag>
        </Space>
      ),
    },
    {
      title: 'API地址',
      dataIndex: 'api_endpoint',
      key: 'api_endpoint',
      ellipsis: true,
      render: (text: string) => text || '-',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 350,
      render: (_: any, record: ModelProviderData) => (
        <Space>
          <Button
            type="link"
            icon={<SettingOutlined />}
            onClick={() => handleManageModels(record)}
          >
            管理模型
          </Button>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除该供应商吗？"
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
          模型供应商管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            createForm.resetFields()
            createForm.setFieldsValue({ provider_type: 'openai' })
            setCreateModalVisible(true)
          }}
        >
          添加供应商
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={providers}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      {/* 创建供应商弹窗 */}
      <Modal
        title="添加模型供应商"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        footer={null}
        width={500}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="name"
            label="供应商名称"
            rules={[{ required: true, message: '请输入供应商名称' }]}
          >
            <Input placeholder="请输入供应商名称" />
          </Form.Item>

          <Form.Item
            name="provider_type"
            label="供应商类型"
            rules={[{ required: true, message: '请选择供应商类型' }]}
          >
            <Select>
              <Option value="openai">OpenAI</Option>
              <Option value="anthropic">Anthropic</Option>
              <Option value="local">本地模型</Option>
              <Option value="custom">自定义</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.provider_type !== currentValues.provider_type
            }
          >
            {({ getFieldValue }) =>
              getFieldValue('provider_type') !== 'local' && (
                <>
                  <Form.Item name="api_endpoint" label="API地址">
                    <Input placeholder="请输入API地址（可选，使用默认地址）" />
                  </Form.Item>

                  <Form.Item
                    name="api_key"
                    label="API Key"
                    rules={[{ required: true, message: '请输入API Key' }]}
                  >
                    <Input.Password placeholder="请输入API Key" />
                  </Form.Item>
                </>
              )
            }
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                添加
              </Button>
              <Button onClick={() => setCreateModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 编辑供应商弹窗 */}
      <Modal
        title="编辑模型供应商"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          setEditingProvider(null)
        }}
        footer={null}
        width={500}
      >
        <Form
          form={editForm}
          layout="vertical"
          onFinish={handleUpdate}
        >
          <Form.Item
            name="name"
            label="供应商名称"
            rules={[{ required: true, message: '请输入供应商名称' }]}
          >
            <Input placeholder="请输入供应商名称" />
          </Form.Item>

          <Form.Item name="api_endpoint" label="API地址">
            <Input placeholder="请输入API地址" />
          </Form.Item>

          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="留空则不修改" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                保存
              </Button>
              <Button onClick={() => setEditModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default Models
