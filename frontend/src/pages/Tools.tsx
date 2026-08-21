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
  Tabs,
  Spin,
  Empty,
  Badge,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ToolOutlined,
  SearchOutlined,
  AppstoreOutlined,
  CloudDownloadOutlined,
  CheckOutlined,
  LinkOutlined,
} from '@ant-design/icons'
import {
  toolsApi,
  ToolData,
  CreateToolData,
  ToolTemplate,
  ToolCategory,
} from '../services/tools'

const { Title, Text, Paragraph } = Typography
const { Option } = Select
const { TextArea } = Input

const Tools: React.FC = () => {
  const [tools, setTools] = useState<ToolData[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [editModalVisible, setEditModalVisible] = useState(false)
  const [exploreModalVisible, setExploreModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const [editForm] = Form.useForm()
  const [selectedTool, setSelectedTool] = useState<ToolData | null>(null)
  const [searchText, setSearchText] = useState('')

  // 探索工具相关状态
  const [templates, setTemplates] = useState<ToolTemplate[]>([])
  const [categories, setCategories] = useState<ToolCategory[]>([])
  const [templatesLoading, setTemplatesLoading] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [templateSearch, setTemplateSearch] = useState('')
  const [installingId, setInstallingId] = useState<string | null>(null)

  // MCP 导入相关状态
  const [mcpImportVisible, setMcpImportVisible] = useState(false)
  const [mcpUrl, setMcpUrl] = useState('')
  const [mcpImporting, setMcpImporting] = useState(false)

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

  // 加载探索工具数据
  const loadExploreData = async () => {
    setTemplatesLoading(true)
    try {
      const [templatesRes, categoriesRes] = await Promise.all([
        toolsApi.getTemplates(),
        toolsApi.getCategories(),
      ])
      setTemplates(templatesRes.data)
      setCategories(categoriesRes.data)
    } catch (error) {
      message.error('加载工具模板失败')
    } finally {
      setTemplatesLoading(false)
    }
  }

  // 打开探索工具弹窗
  const handleOpenExplore = () => {
    setExploreModalVisible(true)
    loadExploreData()
  }

  // 从模板安装工具
  const handleInstall = async (templateId: string) => {
    setInstallingId(templateId)
    try {
      await toolsApi.installFromTemplate(templateId)
      message.success('工具安装成功')
      fetchTools()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '安装失败'
      message.error(detail)
    } finally {
      setInstallingId(null)
    }
  }

  // MCP 导入
  const handleMcpImport = async () => {
    if (!mcpUrl.trim()) {
      message.warning('请输入 MCP Server URL')
      return
    }
    setMcpImporting(true)
    try {
      const response = await toolsApi.importMcp(mcpUrl)
      const count = response.data.length
      if (count > 0) {
        message.success(`成功导入 ${count} 个工具`)
        setMcpImportVisible(false)
        setMcpUrl('')
        fetchTools()
      } else {
        message.warning('未发现可用工具')
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '导入失败'
      message.error(detail)
    } finally {
      setMcpImporting(false)
    }
  }

  const handleCreate = async (values: CreateToolData) => {
    try {
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

  const getToolTypeName = (type: string) => {
    const names: Record<string, string> = {
      builtin: '内置工具',
      plugin: '插件工具',
      mcp: 'MCP工具',
    }
    return names[type] || type
  }

  const getToolTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      builtin: 'blue',
      plugin: 'green',
      mcp: 'purple',
    }
    return colors[type] || 'default'
  }

  // 检查模板是否已安装
  const isInstalled = (templateName: string) => {
    return tools.some((t) => t.name === templateName)
  }

  // 过滤模板
  const filteredTemplates = templates.filter((t) => {
    const matchCategory = selectedCategory === 'all' || t.category === selectedCategory
    const matchSearch =
      !templateSearch ||
      t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
      t.description.toLowerCase().includes(templateSearch.toLowerCase())
    return matchCategory && matchSearch
  })

  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(searchText.toLowerCase()) ||
      tool.description?.toLowerCase().includes(searchText.toLowerCase())
  )

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
        <Space>
          <Button
            icon={<AppstoreOutlined />}
            onClick={handleOpenExplore}
          >
            探索工具
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            添加工具
          </Button>
        </Space>
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

      {/* ============ 探索工具弹窗 ============ */}
      <Modal
        title={
          <Space>
            <AppstoreOutlined />
            <span>探索工具</span>
          </Space>
        }
        open={exploreModalVisible}
        onCancel={() => setExploreModalVisible(false)}
        footer={null}
        width={900}
      >
        {/* 搜索和分类 */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={16}>
            <Input
              placeholder="搜索工具..."
              prefix={<SearchOutlined />}
              value={templateSearch}
              onChange={(e) => setTemplateSearch(e.target.value)}
              allowClear
            />
          </Col>
          <Col span={8}>
            <Select
              value={selectedCategory}
              onChange={setSelectedCategory}
              style={{ width: '100%' }}
            >
              {categories.map((cat) => (
                <Option key={cat.id} value={cat.id}>
                  {cat.icon} {cat.name}
                </Option>
              ))}
            </Select>
          </Col>
        </Row>

        {/* MCP 导入入口 */}
        <Card
          size="small"
          style={{ marginBottom: 16, background: '#f6f8ff', borderColor: '#d6e4ff' }}
          onClick={() => setMcpImportVisible(true)}
        >
          <Space>
            <CloudDownloadOutlined style={{ fontSize: 20, color: '#1677ff' }} />
            <div>
              <Text strong>导入 MCP 工具</Text>
              <div>
                <Text type="secondary">从 MCP Server URL 自动导入工具</Text>
              </div>
            </div>
          </Space>
        </Card>

        {/* 工具模板列表 */}
        {templatesLoading ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
          </div>
        ) : filteredTemplates.length === 0 ? (
          <Empty description="暂无匹配的工具" />
        ) : (
          <Row gutter={[16, 16]}>
            {filteredTemplates.map((template) => {
              const installed = isInstalled(template.name)
              return (
                <Col span={8} key={template.id}>
                  <Card
                    size="small"
                    hoverable
                    style={{ height: '100%' }}
                    actions={[
                      installed ? (
                        <span style={{ color: '#52c41a' }}>
                          <CheckOutlined /> 已安装
                        </span>
                      ) : (
                        <Button
                          type="link"
                          loading={installingId === template.id}
                          onClick={() => handleInstall(template.id)}
                        >
                          安装
                        </Button>
                      ),
                    ]}
                  >
                    <Card.Meta
                      avatar={
                        <span style={{ fontSize: 28 }}>{template.icon}</span>
                      }
                      title={
                        <Space>
                          <Text strong>{template.name}</Text>
                          <Tag color={getToolTypeColor(template.tool_type)}>
                            {getToolTypeName(template.tool_type)}
                          </Tag>
                        </Space>
                      }
                      description={
                        <Paragraph
                          type="secondary"
                          ellipsis={{ rows: 2 }}
                          style={{ marginBottom: 0, fontSize: 12 }}
                        >
                          {template.description}
                        </Paragraph>
                      }
                    />
                  </Card>
                </Col>
              )
            })}
          </Row>
        )}
      </Modal>

      {/* ============ MCP 导入弹窗 ============ */}
      <Modal
        title={
          <Space>
            <LinkOutlined />
            <span>导入 MCP 工具</span>
          </Space>
        }
        open={mcpImportVisible}
        onCancel={() => {
          setMcpImportVisible(false)
          setMcpUrl('')
        }}
        onOk={handleMcpImport}
        confirmLoading={mcpImporting}
        okText="导入"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary">
            输入 MCP Server 的 URL，系统将自动解析并导入可用工具。
          </Text>
        </div>
        <Input
          placeholder="https://mcp.so/server/xxx 或 http://localhost:3000/mcp"
          value={mcpUrl}
          onChange={(e) => setMcpUrl(e.target.value)}
          size="large"
        />
        <div style={{ marginTop: 8 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            支持标准 MCP HTTP 协议和 mcp.so 链接
          </Text>
        </div>
      </Modal>

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
