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
  Row,
  Col,
  Tabs,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  SettingOutlined,
  ApiOutlined,
} from '@ant-design/icons'
import { modelsApi, ModelProviderData, CreateModelProviderData, ModelData } from '../services/models'

const { Title, Text } = Typography
const { Option } = Select
const { TabPane } = Tabs

const Models: React.FC = () => {
  const [providers, setProviders] = useState<ModelProviderData[]>([])
  const [models, setModels] = useState<ModelData[]>([])
  const [loading, setLoading] = useState(false)
  const [createProviderModalVisible, setCreateProviderModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const [selectedProvider, setSelectedProvider] = useState<ModelProviderData | null>(null)
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

  const fetchModels = async (providerId: number) => {
    try {
      const response = await modelsApi.getModels(providerId)
      setModels(response.data)
    } catch (error) {
      message.error('获取模型列表失败')
    }
  }

  const handleCreateProvider = async (values: CreateModelProviderData) => {
    try {
      await modelsApi.createProvider(values)
      message.success('模型供应商创建成功')
      setCreateProviderModalVisible(false)
      createForm.resetFields()
      fetchProviders()
    } catch (error) {
      message.error('创建模型供应商失败')
    }
  }

  // 供应商类型中文名
  const getProviderTypeName = (type: string) => {
    const names: Record<string, string> = {
      openai: 'OpenAI',
      anthropic: 'Anthropic',
      local: '本地模型',
      custom: '自定义',
    }
    return names[type] || type
  }

  // 供应商类型颜色
  const getProviderTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      openai: 'green',
      anthropic: 'blue',
      local: 'orange',
      custom: 'purple',
    }
    return colors[type] || 'default'
  }

  // 供应商表格列
  const providerColumns = [
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
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: ModelProviderData) => (
        <Space>
          <Button
            type="link"
            icon={<SettingOutlined />}
            onClick={() => {
              setSelectedProvider(record)
              fetchModels(record.id)
            }}
          >
            管理模型
          </Button>
        </Space>
      ),
    },
  ]

  // 模型表格列
  const modelColumns = [
    {
      title: '模型名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ModelData) => (
        <Space>
          <Text strong>{text}</Text>
          <Text type="secondary">({record.model_id})</Text>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: '最大Token',
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 100,
    },
    {
      title: '流式输出',
      dataIndex: 'supports_streaming',
      key: 'supports_streaming',
      render: (supports: boolean) => (
        <Tag color={supports ? 'success' : 'default'}>
          {supports ? '支持' : '不支持'}
        </Tag>
      ),
    },
    {
      title: '函数调用',
      dataIndex: 'supports_function_calling',
      key: 'supports_function_calling',
      render: (supports: boolean) => (
        <Tag color={supports ? 'success' : 'default'}>
          {supports ? '支持' : '不支持'}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '启用' : '停用'}
        </Tag>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Title level={4} style={{ margin: 0 }}>
          模型管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateProviderModalVisible(true)}
        >
          添加供应商
        </Button>
      </div>

      <Row gutter={[16, 16]}>
        {/* 供应商列表 */}
        <Col xs={24} lg={selectedProvider ? 10 : 24}>
          <Card title="模型供应商">
            <Table
              columns={providerColumns}
              dataSource={providers}
              rowKey="id"
              loading={loading}
              pagination={false}
              size="small"
            />
          </Card>
        </Col>

        {/* 模型列表 */}
        {selectedProvider && (
          <Col xs={24} lg={14}>
            <Card
              title={`${selectedProvider.name} - 模型列表`}
              extra={
                <Button
                  type="link"
                  onClick={() => setSelectedProvider(null)}
                >
                  关闭
                </Button>
              }
            >
              <Table
                columns={modelColumns}
                dataSource={models}
                rowKey="id"
                pagination={false}
                size="small"
                locale={{
                  emptyText: <Empty description="暂无模型" />,
                }}
              />
            </Card>
          </Col>
        )}
      </Row>

      {/* 创建供应商弹窗 */}
      <Modal
        title="添加模型供应商"
        open={createProviderModalVisible}
        onCancel={() => {
          setCreateProviderModalVisible(false)
          createForm.resetFields()
        }}
        footer={null}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreateProvider}
          initialValues={{ provider_type: 'openai' }}
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
                  <Form.Item
                    name="api_endpoint"
                    label="API地址"
                  >
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
              <Button
                onClick={() => {
                  setCreateProviderModalVisible(false)
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

export default Models
