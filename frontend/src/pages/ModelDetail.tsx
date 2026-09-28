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
  InputNumber,
  Switch,
  App,
  Popconfirm,
  Typography,
  Row,
  Col,
  Empty,
  Spin,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ArrowLeftOutlined,
} from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import {
  modelsApi,
  ModelProviderData,
  ModelData,
  CreateModelProviderData,
} from '@/services/models'

const { Title, Text } = Typography

const ModelDetail: React.FC = () => {
  const { providerId } = useParams<{ providerId: string }>()
  const navigate = useNavigate()
  const [provider, setProvider] = useState<ModelProviderData | null>(null)
  const [models, setModels] = useState<ModelData[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [editingModel, setEditingModel] = useState<ModelData | null>(null)
  const [form] = Form.useForm()
  const { message } = App.useApp()

  useEffect(() => {
    if (providerId) {
      fetchProvider()
      fetchModels()
    }
  }, [providerId])

  const fetchProvider = async () => {
    try {
      const response = await modelsApi.getProvider(Number(providerId))
      setProvider(response.data)
    } catch (error) {
      message.error('获取供应商信息失败')
    }
  }

  const fetchModels = async () => {
    setLoading(true)
    try {
      const response = await modelsApi.getModels(Number(providerId))
      setModels(response.data)
    } catch (error) {
      message.error('获取模型列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = () => {
    setEditingModel(null)
    form.resetFields()
    form.setFieldsValue({
      supports_streaming: true,
      supports_function_calling: false,
      default_temperature: 0.7,
      default_max_tokens: 2048,
      is_active: true,
    })
    setModalVisible(true)
  }

  const handleEdit = (record: ModelData) => {
    setEditingModel(record)
    form.setFieldsValue({
      name: record.name,
      model_id: record.model_id,
      description: record.description,
      max_tokens: record.max_tokens,
      supports_streaming: record.supports_streaming,
      supports_function_calling: record.supports_function_calling,
      default_temperature: record.default_temperature,
      default_max_tokens: record.default_max_tokens,
      is_active: record.is_active,
    })
    setModalVisible(true)
  }

  const handleDelete = async (id: number) => {
    try {
      await modelsApi.deleteModel(Number(providerId), id)
      message.success('删除成功')
      fetchModels()
    } catch (error) {
      message.error('删除失败')
    }
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      if (editingModel) {
        await modelsApi.updateModel(Number(providerId), editingModel.id, values)
        message.success('更新成功')
      } else {
        await modelsApi.createModel(Number(providerId), values)
        message.success('创建成功')
      }
      setModalVisible(false)
      fetchModels()
    } catch (error) {
      if (error.errorFields) {
        return
      }
      message.error(editingModel ? '更新失败' : '创建失败')
    }
  }

  const columns = [
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
      render: (text: string) => text || '-',
    },
    {
      title: '最大Token',
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 100,
      render: (value: number) => value || '-',
    },
    {
      title: '流式输出',
      dataIndex: 'supports_streaming',
      key: 'supports_streaming',
      width: 90,
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
      width: 90,
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
      width: 80,
      render: (active: boolean) => (
        <Tag color={active ? 'success' : 'default'}>
          {active ? '启用' : '停用'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: ModelData) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除该模型吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (!provider && !loading) {
    return (
      <div className="text-center py-25">
        <Empty description="供应商不存在" />
        <Button onClick={() => navigate('/models')} className="mt-4">
          返回
        </Button>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-4 flex justify-between items-center">
        <Space>
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/models')}
          >
            返回
          </Button>
          <Title level={4} className="m-0">
            {provider?.name || '加载中...'} - 模型管理
          </Title>
        </Space>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
          添加模型
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={models}
          rowKey="id"
          loading={loading}
          pagination={false}
          locale={{
            emptyText: <Empty description="暂无模型" />,
          }}
        />
      </Card>

      <Modal
        title={editingModel ? '编辑模型' : '添加模型'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => {
          setModalVisible(false)
          setEditingModel(null)
        }}
        width={600}
        okText="确定"
        cancelText="取消"
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="模型名称"
                rules={[{ required: true, message: '请输入模型名称' }]}
              >
                <Input placeholder="例如：GPT-4o" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="model_id"
                label="模型ID"
                rules={[{ required: true, message: '请输入模型ID' }]}
              >
                <Input placeholder="例如：gpt-4o" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="模型描述（可选）" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="max_tokens" label="最大Token数">
                <InputNumber min={1} max={128000} className="w-full" placeholder="例如：128000" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="default_max_tokens" label="默认最大输出Token">
                <InputNumber min={1} max={128000} className="w-full" placeholder="例如：2048" />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="default_temperature" label="默认温度">
                <InputNumber min={0} max={2} step={0.1} className="w-full" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="is_active" label="启用状态" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="supports_streaming" label="支持流式输出" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="supports_function_calling" label="支持函数调用" valuePropName="checked">
                <Switch />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>
    </div>
  )
}

export default ModelDetail
