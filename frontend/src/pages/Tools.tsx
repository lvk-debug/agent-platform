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
  Drawer,
  Divider,
  Statistic,
  Tooltip,
  Alert,
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
  PlayCircleOutlined,
  ThunderboltOutlined,
  ApiOutlined,
  ExperimentOutlined,
  FilterOutlined,
} from '@ant-design/icons'
import {
  toolsApi,
  ToolData,
  ToolTemplate,
  ToolCategory,
  ToolTestResult,
} from '@/services/tools'

const { Title, Text, Paragraph } = Typography
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
  const [activeTab, setActiveTab] = useState('installed')

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

  // 测试面板相关状态
  const [testDrawerVisible, setTestDrawerVisible] = useState(false)
  const [testTool, setTestTool] = useState<ToolData | null>(null)
  const [testInput, setTestInput] = useState('{}')
  const [testLoading, setTestLoading] = useState(false)
  const [testResult, setTestResult] = useState<ToolTestResult | null>(null)

  useEffect(() => {
    fetchTools()
  }, [])

  useEffect(() => {
    if (activeTab === 'marketplace') {
      loadExploreData()
    }
  }, [activeTab])

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
    if (templates.length > 0) return // 已加载过
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

  const handleCreate = async (values: any) => {
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
      auth_config: tool.auth_config
        ? JSON.stringify(tool.auth_config, null, 2)
        : undefined,
    })
    setEditModalVisible(true)
  }

  // 打开测试面板
  const handleOpenTest = (tool: ToolData) => {
    setTestTool(tool)
    setTestResult(null)
    // 根据 parameters_schema 生成默认输入
    const schema = tool.parameters_schema as Record<string, any> | undefined
    if (schema?.properties) {
      const defaultInput: Record<string, any> = {}
      Object.entries(schema.properties as Record<string, any>).forEach(
        ([key, prop]) => {
          if (prop.type === 'string') defaultInput[key] = ''
          else if (prop.type === 'integer' || prop.type === 'number')
            defaultInput[key] = 0
          else if (prop.type === 'boolean') defaultInput[key] = false
          else if (prop.type === 'array') defaultInput[key] = []
          else if (prop.type === 'object') defaultInput[key] = {}
        }
      )
      setTestInput(JSON.stringify(defaultInput, null, 2))
    } else {
      setTestInput('{}')
    }
    setTestDrawerVisible(true)
  }

  // 执行测试
  const handleRunTest = async () => {
    if (!testTool) return
    let parsedInput: Record<string, any>
    try {
      parsedInput = JSON.parse(testInput)
    } catch {
      message.error('输入参数 JSON 格式错误')
      return
    }
    setTestLoading(true)
    setTestResult(null)
    try {
      const response = await toolsApi.testTool(testTool.id, parsedInput)
      setTestResult(response.data)
    } catch (error: any) {
      setTestResult({
        success: false,
        error: error?.response?.data?.detail || '测试执行失败',
        duration_ms: 0,
      })
    } finally {
      setTestLoading(false)
    }
  }

  const getToolTypeName = (type: string) => {
    const names: Record<string, string> = {
      builtin: '内置',
      plugin: '插件',
      mcp: 'MCP',
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
    const matchCategory =
      selectedCategory === 'all' || t.category === selectedCategory
    const matchSearch =
      !templateSearch ||
      t.name.toLowerCase().includes(templateSearch.toLowerCase()) ||
      t.description.toLowerCase().includes(templateSearch.toLowerCase())
    return matchCategory && matchSearch
  })

  // 分类计数
  const categoryCounts = templates.reduce(
    (acc, t) => {
      acc[t.category] = (acc[t.category] || 0) + 1
      return acc
    },
    {} as Record<string, number>
  )

  const filteredTools = tools.filter(
    (tool) =>
      tool.name.toLowerCase().includes(searchText.toLowerCase()) ||
      tool.description?.toLowerCase().includes(searchText.toLowerCase())
  )

  // 统计
  const builtinCount = tools.filter((t) => t.tool_type === 'builtin').length
  const pluginCount = tools.filter((t) => t.tool_type === 'plugin').length
  const mcpCount = tools.filter((t) => t.tool_type === 'mcp').length

  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ToolData) => (
        <Space>
          <span style={{ fontSize: 18 }}>{record.icon || '🔧'}</span>
          <Text strong>{text}</Text>
          <Tag color={getToolTypeColor(record.tool_type)} style={{ marginLeft: 4 }}>
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
      width: 300,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (active: boolean) => (
        <Badge
          status={active ? 'success' : 'default'}
          text={active ? '启用' : '停用'}
        />
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 240,
      render: (_: any, record: ToolData) => (
        <Space>
          <Tooltip title="测试工具">
            <Button
              type="text"
              icon={<ExperimentOutlined />}
              style={{ color: '#1677ff' }}
              onClick={() => handleOpenTest(record)}
            />
          </Tooltip>
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

  // ============ 工具市场 Tab ============
  const renderMarketplace = () => (
    <div>
      {/* MCP 导入入口 */}
      <Card
        size="small"
        style={{
          marginBottom: 16,
          background: 'linear-gradient(135deg, #f0f5ff 0%, #e6f7ff 100%)',
          borderColor: '#91d5ff',
        }}
        hoverable
        onClick={() => setMcpImportVisible(true)}
      >
        <Row align="middle" gutter={16}>
          <Col>
            <ApiOutlined style={{ fontSize: 28, color: '#1677ff' }} />
          </Col>
          <Col flex="auto">
            <Text strong style={{ fontSize: 14 }}>导入 MCP 工具</Text>
            <br />
            <Text type="secondary" style={{ fontSize: 12 }}>
              从 MCP Server URL 自动发现并导入工具
            </Text>
          </Col>
          <Col>
            <Button type="primary" size="small" icon={<CloudDownloadOutlined />}>
              导入
            </Button>
          </Col>
        </Row>
      </Card>

      <Row gutter={16}>
        {/* 左侧分类筛选 */}
        <Col span={5}>
          <Card size="small" bodyStyle={{ padding: '12px 0' }}>
            <div style={{ padding: '0 12px 8px', borderBottom: '1px solid #f0f0f0' }}>
              <Text strong style={{ fontSize: 13 }}>
                <FilterOutlined /> 分类
              </Text>
            </div>
            <div style={{ maxHeight: 480, overflowY: 'auto' }}>
              {categories.map((cat) => (
                <div
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  style={{
                    padding: '8px 12px',
                    cursor: 'pointer',
                    background:
                      selectedCategory === cat.id ? '#e6f7ff' : 'transparent',
                    borderLeft:
                      selectedCategory === cat.id
                        ? '3px solid #1677ff'
                        : '3px solid transparent',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    if (selectedCategory !== cat.id)
                      e.currentTarget.style.background = '#fafafa'
                  }}
                  onMouseLeave={(e) => {
                    if (selectedCategory !== cat.id)
                      e.currentTarget.style.background = 'transparent'
                  }}
                >
                  <Space>
                    <span>{cat.icon}</span>
                    <Text
                      style={{
                        fontWeight: selectedCategory === cat.id ? 600 : 400,
                        color: selectedCategory === cat.id ? '#1677ff' : undefined,
                      }}
                    >
                      {cat.name}
                    </Text>
                    {cat.id !== 'all' && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ({categoryCounts[cat.id] || 0})
                      </Text>
                    )}
                    {cat.id === 'all' && (
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        ({templates.length})
                      </Text>
                    )}
                  </Space>
                </div>
              ))}
            </div>
          </Card>
        </Col>

        {/* 右侧工具列表 */}
        <Col span={19}>
          {/* 搜索栏 */}
          <Input
            placeholder="搜索工具名称或描述..."
            prefix={<SearchOutlined />}
            value={templateSearch}
            onChange={(e) => setTemplateSearch(e.target.value)}
            allowClear
            size="large"
            style={{ marginBottom: 16 }}
          />

          {/* 工具网格 */}
          {templatesLoading ? (
            <div style={{ textAlign: 'center', padding: '60px 0' }}>
              <Spin size="large" />
            </div>
          ) : filteredTemplates.length === 0 ? (
            <Empty description="暂无匹配的工具" />
          ) : (
            <Row gutter={[12, 12]}>
              {filteredTemplates.map((template) => {
                const installed = isInstalled(template.name)
                return (
                  <Col span={8} key={template.id}>
                    <Card
                      size="small"
                      hoverable
                      style={{
                        height: '100%',
                        borderColor: installed ? '#b7eb8f' : undefined,
                      }}
                      bodyStyle={{ padding: '12px 16px' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                        <span style={{ fontSize: 28, lineHeight: 1 }}>
                          {template.icon}
                        </span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 6,
                              marginBottom: 4,
                            }}
                          >
                            <Text strong style={{ fontSize: 13 }}>
                              {template.name}
                            </Text>
                            <Tag
                              color={getToolTypeColor(template.tool_type)}
                              style={{ fontSize: 10, lineHeight: '16px', padding: '0 4px' }}
                            >
                              {getToolTypeName(template.tool_type)}
                            </Tag>
                          </div>
                          <Paragraph
                            type="secondary"
                            ellipsis={{ rows: 2 }}
                            style={{ marginBottom: 8, fontSize: 12 }}
                          >
                            {template.description}
                          </Paragraph>
                          {installed ? (
                            <Tag
                              icon={<CheckOutlined />}
                              color="success"
                              style={{ fontSize: 11 }}
                            >
                              已安装
                            </Tag>
                          ) : (
                            <Button
                              type="primary"
                              size="small"
                              ghost
                              loading={installingId === template.id}
                              onClick={() => handleInstall(template.id)}
                            >
                              安装
                            </Button>
                          )}
                        </div>
                      </div>
                    </Card>
                  </Col>
                )
              })}
            </Row>
          )}
        </Col>
      </Row>
    </div>
  )

  // ============ 主渲染 ============
  return (
    <div>
      <div className="mb-4 flex justify-between">
        <Title level={4} className="m-0">
          工具管理
        </Title>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            添加工具
          </Button>
        </Space>
      </div>

      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="已安装工具"
              value={tools.length}
              prefix={<ToolOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="内置工具"
              value={builtinCount}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="插件工具"
              value={pluginCount}
              prefix={<ApiOutlined />}
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="MCP 工具"
              value={mcpCount}
              prefix={<LinkOutlined />}
              valueStyle={{ color: '#722ed1' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Tab 切换 */}
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'installed',
            label: (
              <span>
                <ToolOutlined /> 我的工具
              </span>
            ),
            children: (
              <Card>
                {/* 搜索栏 */}
                <div style={{ marginBottom: 16 }}>
                  <Input
                    placeholder="搜索工具名称或描述"
                    prefix={<SearchOutlined />}
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                    allowClear
                    style={{ maxWidth: 400 }}
                  />
                </div>
                <Table
                  columns={columns}
                  dataSource={filteredTools}
                  rowKey="id"
                  loading={loading}
                  pagination={false}
                />
              </Card>
            ),
          },
          {
            key: 'marketplace',
            label: (
              <span>
                <AppstoreOutlined /> 工具市场
                <Badge
                  count={templates.length}
                  style={{ marginLeft: 6, backgroundColor: '#1677ff' }}
                  size="small"
                />
              </span>
            ),
            children: renderMarketplace(),
          },
        ]}
      />

      {/* ============ 工具测试抽屉 ============ */}
      <Drawer
        title={
          <Space>
            <ExperimentOutlined />
            <span>工具测试 - {testTool?.name}</span>
            {testTool && (
              <Tag color={getToolTypeColor(testTool.tool_type)}>
                {getToolTypeName(testTool.tool_type)}
              </Tag>
            )}
          </Space>
        }
        open={testDrawerVisible}
        onClose={() => {
          setTestDrawerVisible(false)
          setTestTool(null)
          setTestResult(null)
        }}
        width={640}
        extra={
          <Button
            type="primary"
            icon={<PlayCircleOutlined />}
            loading={testLoading}
            onClick={handleRunTest}
          >
            执行测试
          </Button>
        }
      >
        {testTool && (
          <>
            {/* 工具信息 */}
            <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Text type="secondary">工具名称</Text>
                  <br />
                  <Text strong>{testTool.name}</Text>
                </Col>
                <Col span={12}>
                  <Text type="secondary">端点</Text>
                  <br />
                  <Text ellipsis style={{ maxWidth: 200 }}>
                    {testTool.endpoint || '-'}
                  </Text>
                </Col>
              </Row>
              {testTool.description && (
                <>
                  <Divider style={{ margin: '8px 0' }} />
                  <Text type="secondary">{testTool.description}</Text>
                </>
              )}
            </Card>

            {/* 参数 Schema 提示 */}
            {testTool.parameters_schema?.properties && (
              <Card
                size="small"
                title="参数说明"
                style={{ marginBottom: 16 }}
                bodyStyle={{ padding: '8px 12px' }}
              >
                {Object.entries(testTool.parameters_schema.properties).map(
                  ([key, prop]: [string, any]) => (
                    <div key={key} style={{ marginBottom: 4 }}>
                      <Text code>{key}</Text>
                      <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
                        ({prop.type})
                        {testTool.parameters_schema?.required?.includes(key) &&
                          ' *必填'}
                        {prop.description && ` - ${prop.description}`}
                      </Text>
                    </div>
                  )
                )}
              </Card>
            )}

            {/* 输入参数 */}
            <Card
              size="small"
              title="输入参数 (JSON)"
              style={{ marginBottom: 16 }}
            >
              <TextArea
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                rows={6}
                style={{ fontFamily: 'monospace', fontSize: 13 }}
                placeholder='{"key": "value"}'
              />
            </Card>

            {/* 测试结果 */}
            {testResult && (
              <Card
                size="small"
                title={
                  <Space>
                    <span>测试结果</span>
                    {testResult.success ? (
                      <Tag color="success">成功</Tag>
                    ) : (
                      <Tag color="error">失败</Tag>
                    )}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      耗时 {testResult.duration_ms}ms
                    </Text>
                  </Space>
                }
              >
                {testResult.success ? (
                  <pre
                    style={{
                      background: '#f6ffed',
                      border: '1px solid #b7eb8f',
                      borderRadius: 6,
                      padding: 12,
                      maxHeight: 300,
                      overflow: 'auto',
                      fontSize: 12,
                      margin: 0,
                    }}
                  >
                    {typeof testResult.output === 'string'
                      ? testResult.output
                      : JSON.stringify(testResult.output, null, 2)}
                  </pre>
                ) : (
                  <Alert
                    type="error"
                    message="执行失败"
                    description={testResult.error}
                    showIcon
                  />
                )}
              </Card>
            )}
          </>
        )}
      </Drawer>

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
