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
  message,
  Popconfirm,
  Typography,
  Row,
  Col,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ToolOutlined,
  SearchOutlined,
} from '@ant-design/icons'
import { toolsApi, ToolData, CreateToolData } from '../services/tools'

const { Title, Text } = Typography
const { Option } = Select
const { TextArea } = Input

const Tools: React.FC = () => {
  const [tools, setTools] = useState<ToolData[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [selectedTool, setSelectedTool] = useState<ToolData | null>(null)
  const [searchText, setSearchText] = useState('')

  useEffect(() => {
    fetchTools()
  }, [])

  const fetchTools = async () => {
    setLoading(true)
    try {
      const response = await toolsApi.getTools()
      setTools(response.data)
    } catch (error) {
      message.error('获取工具列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: CreateToolData) => {
    try {
      // 处理JSON字段
      const data = {
        ...values,
        parameters_schema: values.parameters_schema
          ? JSON.parse(values.parameters_schema)
          : undefined,
        return_schema: values.return_schema
          ? JSON.parse(values.return_schema)
          : undefined,
        auth_config: values.auth_config
          ? JSON.parse(values.auth_config)
          : undefined,
      }
      await toolsApi.createTool(data)
      message.success('工具创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchTools()
    } catch (error) {
      message.error('创建工具失败，请检查JSON格式是否正确')
    }
  }

  const handleUpdate = async (values: any) => {
    if (!selectedTool) return

    try {
      // 处理JSON字段
      const data = {
        ...values,
        parameters_schema: values.parameters_schema
          ? JSON.parse(values.parameters_schema)
          : undefined,
        return_schema: values.return_schema
          ? JSON.parse(values.return_schema)
          : undefined,
        auth_config: values.auth_config
          ? JSON.parse(values.auth_config)
          : undefined,
      }
      await toolsApi.updateTool(selectedTool.id, data)
      message.success('工具更新成功')
      setEditModalVisible(false)
      editForm.resetFields()
      fetchTools()
    } catch (error) {
      message.error('更新工具失败，请检查JSON格式是否正确')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await toolsApi.deleteTool(id)
      message.success('工具已删除')
      fetchTools()
    } catch (error) {
      message.error('删除工具失败')
    }
  }

  const handleEdit = (tool: ToolData) => {
    setSelectedTool(tool)
    editForm.setFieldsValue({
      name: tool.name,
      description: tool.description,
      tool_type: tool.tool_type,
      icon: tool.icon,
      endpoint: tool.endpoint,
      parameters_schema: tool.parameters_schema
        ? JSON.stringify(tool.parameters_schema, null, 2)
        : undefined,
      return_schema: tool.return_schema
        ? JSON.stringify(tool.return_schema, null, 2)
        : undefined,
    })
    setEditModalVisible(true)
  }

  // 工具类型中文名
  const getToolTypeName = (type: string) => {
    const names: Record<string, string> = {
      builtin: '内置工具',
      plugin: '插件工具',
      mcp: 'MCP工具',
    }
    return names[type] || type
  }

  // 工具类型颜色
  const getToolTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      builtin: 'blue',
      plugin: 'green',
      mcp: 'purple',
    }
    return colors[type] || 'default'
  }

  // 过滤工具
  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(searchText.toLowerCase()) ||
      tool.description?.toLowerCase().includes(searchText.toLowerCase())
  )

  // 表格列定义
  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ToolData) => (
        <Space>
          <ToolOutlined />
          <Text strong>{text}</Text>
          <Tag color={getToolTypeColor(record.tool_type)}>
            {getToolTypeName(record.tool_type)}
          </Tag>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 250,
    },
    {
      title: '类型',
      dataIndex: 'tool_type',
      key: 'tool_type',
      width: 100,
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
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: ToolData) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除此工具吗？"
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

  // 工具表单组件
  const ToolForm: React.FC<{ form: any; onFinish: (values: any) => void }> = ({
    form,
    onFinish,
  }) => (
    <Form form={form} layout="vertical" onFinish={onFinish}>
      <Form.Item
        name="name"
        label="工具名称"
        rules={[{ required: true, message: '请输入工具名称' }]}
      >
        <Input placeholder="请输入工具名称" />
      </Form.Item>

      <Form.Item
        name="tool_type"
        label="工具类型"
        rules={[{ required: true, message: '请选择工具类型' }]}
      >
        <Select>
          <Option value="builtin">内置工具</Option>
          <Option value="plugin">插件工具</Option>
          <Option value="mcp">MCP工具</Option>
        </Select>
      </Form.Item>

      <Form.Item name="description" label="描述">
        <TextArea rows={2} placeholder="请输入工具描述" />
      </Form.Item>

      <Form.Item name="icon" label="图标">
        <Input placeholder="请输入图标URL或图标名称" />
      </Form.Item>

      <Form.Item
        noStyle
        shouldUpdate={(prevValues, currentValues) =>
          prevValues.tool_type !== currentValues.tool_type
        }
      >
        {({ getFieldValue }) =>
          getFieldValue('tool_type') !== 'builtin' && (
            <>
              <Form.Item
                name="endpoint"
                label="端点地址"
                rules={[{ required: true, message: '请输入端点地址' }]}
              >
                <Input placeholder="请输入工具端点地址" />
              </Form.Item>

              <Form.Item name="auth_config" label="认证配置 (JSON)">
                <TextArea rows={3} placeholder='{"api_key": "xxx"}' />
              </Form.Item>
            </>
          )
        }
      </Form.Item>

      <Form.Item name="parameters_schema" label="参数Schema (JSON)">
        <TextArea
          rows={4}
          placeholder='{"type": "object", "properties": {...}}'
        />
      </Form.Item>

      <Form.Item name="return_schema" label="返回值Schema (JSON)">
        <TextArea
          rows={4}
          placeholder='{"type": "object", "properties": {...}}'
        />
      </Form.Item>
    </Form>
  )

  return (
    <div>
      <div className="mb-4 flex justify-between">
        <Title level={4} className="m-0">
          工具管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
        >
          添加工具
        </Button>
      </div>

      {/* 搜索栏 */}
      <Card className="mb-4">
        <Input
          placeholder="搜索工具名称或描述"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
      </Card>

      {/* 工具列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={filteredTools}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      {/* 创建工具弹窗 */}
      <Modal
        title="添加工具"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        footer={[
          <Button
            key="cancel"
            onClick={() => {
              setCreateModalVisible(false)
              createForm.resetFields()
            }}
          >
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={() => createForm.submit()}>
            创建
          </Button>,
        ]}
        width={600}
      >
        <ToolForm form={createForm} onFinish={handleCreate} />
      </Modal>

      {/* 编辑工具弹窗 */}
      <Modal
        title="编辑工具"
        open={editModalVisible}
        onCancel={() => {
          setEditModalVisible(false)
          editForm.resetFields()
          setSelectedTool(null)
        }}
        footer={[
          <Button
            key="cancel"
            onClick={() => {
              setEditModalVisible(false)
              editForm.resetFields()
              setSelectedTool(null)
            }}
          >
            取消
          </Button>,
          <Button key="submit" type="primary" onClick={() => editForm.submit()}>
            保存
          </Button>,
        ]}
        width={600}
      >
        <ToolForm form={editForm} onFinish={handleUpdate} />
      </Modal>
    </div>
  )
}

export default Tools
