import React, { useState, useEffect } from 'react'
import { Card, Button, message, Spin, Row, Col, Space, Breadcrumb, Switch, Input, InputNumber, Typography, Tag, List, Empty } from 'antd'
import { SaveOutlined, SettingOutlined, CommentOutlined, PlusOutlined, DeleteOutlined, ToolOutlined, RobotOutlined, HistoryOutlined, SyncOutlined, FilterOutlined } from '@ant-design/icons'
import { useParams, useNavigate, Link } from 'react-router-dom'
import PromptEditor from '@/components/PromptEditor'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector'
import ModelSelector from '@/components/ModelSelector'
import ModelParametersModal from '@/components/ModelParameters'
import ToolSelector from '@/components/ToolSelector'
import { agentApi, AgentConfig, ToolConfig } from '@/services/agent'
import { ModelParameters as ModelParametersType } from '@/services/chatbot'

const { Text } = Typography

const defaultParameters: ModelParametersType = {
  temperature: 0.7,
  top_p: 1,
  top_k: 1,
  presence_penalty: 0,
  frequency_penalty: 0,
  max_tokens: 2048,
  skip_content_review: false
}

const AgentOrchestration: React.FC = () => {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const [config, setConfig] = useState<AgentConfig>({
    prompt: { system_prompt: '' },
    model_parameters: defaultParameters,
    knowledge_bases: [],
    metadata_filter_enabled: false,
    tools: [],
    memory_enabled: true,
    memory_window: 50,
    max_iterations: 10,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [paramsOpen, setParamsOpen] = useState(false)
  const [toolSelectorOpen, setToolSelectorOpen] = useState(false)
  const [appName, setAppName] = useState('')

  useEffect(() => {
    fetchConfig()
  }, [appId])

  const fetchConfig = async () => {
    if (!appId) return
    setLoading(true)
    try {
      const data = await agentApi.getConfig(Number(appId))
      setAppName(data.app_name)
      setConfig({
        ...data.config,
        model_parameters: data.config.model_parameters || defaultParameters,
        prompt: data.config.prompt || { system_prompt: '' },
        tools: data.config.tools || [],
      })
    } catch (error) {
      console.error('Failed to fetch config:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!appId) return
    setSaving(true)
    try {
      console.log('保存 Agent 配置:', config)
      await agentApi.updateConfig(Number(appId), config)
      message.success('保存成功')
    } catch (error) {
      console.error('保存失败:', error)
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleParamsOk = (params: ModelParametersType) => {
    setConfig({ ...config, model_parameters: params })
    setParamsOpen(false)
  }

  const handleAddTool = () => {
    setToolSelectorOpen(true)
  }

  const handleToolSelectorOk = (tools: ToolConfig[]) => {
    setConfig({ ...config, tools })
    setToolSelectorOpen(false)
  }

  const handleRemoveTool = (toolId: number) => {
    setConfig({
      ...config,
      tools: config.tools.filter(t => t.tool_id !== toolId)
    })
  }

  const handleToggleTool = (toolId: number, enabled: boolean) => {
    setConfig({
      ...config,
      tools: config.tools.map(t =>
        t.tool_id === toolId ? { ...t, enabled } : t
      )
    })
  }

  if (loading) {
    return (
      <div className="text-center py-25">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="h-screen pb-3 flex flex-col">
      <div className="pb-3 border-b border-border">
        <Row justify="space-between" align="middle">
          <Col>
            <Breadcrumb
              items={[
                { title: <Link to="/apps">应用</Link> },
                { title: 'Agent 编排' },
              ]}
            />
          </Col>
          <Col>
            <Space>
              <Button
                icon={<CommentOutlined />}
                onClick={() => navigate(`/apps/${appId}/agent/debug`)}
              >
                调试
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
              >
                保存
              </Button>
            </Space>
          </Col>
        </Row>
      </div>

      <div className="flex-1 bg-page overflow-auto">
        {/* 模型配置 */}
        <Card title="模型配置" className="mb-4"
          extra={
            <Button
              type="link"
              icon={<SettingOutlined />}
              onClick={() => setParamsOpen(true)}
              disabled={!config.model_id}
            >
              参数设置
            </Button>
          }
        >
          <div className="mb-2">选择模型</div>
          <ModelSelector
            value={config.model_id}
            onChange={(modelId) => setConfig({ ...config, model_id: modelId })}
          />
        </Card>

        {/* 提示词设置 */}
        <Card title="提示词" className="mb-4"
          extra={
            <Button type="link" icon={<RobotOutlined />}>
              生成
            </Button>
          }
        >
          <PromptEditor
            systemPrompt={config.prompt?.system_prompt || ''}
            onChange={(systemPrompt) => setConfig({
              ...config,
              prompt: { ...config.prompt, system_prompt: systemPrompt }
            })}
          />
        </Card>

        {/* 知识库设置 */}
        <Card title={
          <Space>
            <span>知识库</span>
            <Text type="secondary" style={{ fontSize: 12 }}>②</Text>
          </Space>
        } className="mb-4"
          extra={
            <Button type="link" icon={<PlusOutlined />}>
              添加
            </Button>
          }
        >
          <KnowledgeBaseSelector
            selected={config.knowledge_bases || []}
            onChange={(knowledge_bases) => setConfig({ ...config, knowledge_bases })}
          />
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid #f0f0f0' }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Space>
                  <FilterOutlined style={{ color: '#fa8c16' }} />
                  <span>元数据过滤</span>
                </Space>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    启用后查询时自动携带元数据过滤条件
                  </Text>
                </div>
              </Col>
              <Col>
                <Switch
                  checked={config.metadata_filter_enabled}
                  onChange={(checked) => setConfig({ ...config, metadata_filter_enabled: checked })}
                  checkedChildren="启用"
                  unCheckedChildren="禁用"
                />
              </Col>
            </Row>
          </div>
        </Card>

        {/* 工具设置 */}
        <Card title={
          <Space>
            <span>工具</span>
            <Text type="secondary" style={{ fontSize: 12 }}>③</Text>
          </Space>
        } className="mb-4"
          extra={
            <Space>
              <Text type="secondary">{config.tools.filter(t => t.enabled).length}/{config.tools.length} 启用</Text>
              <Button type="link" icon={<PlusOutlined />} onClick={handleAddTool}>
                添加
              </Button>
            </Space>
          }
        >
          {config.tools.length === 0 ? (
            <Empty description="暂无工具" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <List
              dataSource={config.tools}
              renderItem={(tool: ToolConfig) => (
                <List.Item
                  actions={[
                    <Switch
                      key="toggle"
                      size="small"
                      checked={tool.enabled}
                      onChange={(checked) => handleToggleTool(tool.tool_id, checked)}
                    />,
                    <Button
                      key="delete"
                      type="text"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveTool(tool.tool_id)}
                    />,
                  ]}
                >
                  <List.Item.Meta
                    avatar={<ToolOutlined style={{ fontSize: 20, color: '#1890ff' }} />}
                    title={tool.name}
                    description={tool.config?.description || '内置工具'}
                  />
                </List.Item>
              )}
            />
          )}
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid #f0f0f0' }}>
            <Row justify="space-between" align="middle">
              <Col>
                <Space>
                  <SyncOutlined style={{ color: '#1890ff' }} />
                  <span>最大工具调用次数</span>
                </Space>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Agent 单次对话最多执行的工具调用轮次，超过后停止
                  </Text>
                </div>
              </Col>
              <Col>
                <Space>
                  <InputNumber
                    min={1}
                    max={50}
                    value={config.max_iterations}
                    onChange={(val) => val && setConfig({ ...config, max_iterations: val })}
                  />
                  <Text type="secondary">次</Text>
                </Space>
              </Col>
            </Row>
          </div>
        </Card>

        {/* 对话记忆 */}
        <Card title={
          <Space>
            <span>对话记忆</span>
            <Text type="secondary" style={{ fontSize: 12 }}>③</Text>
          </Space>
        } className="mb-4">
          <Row justify="space-between" align="middle" className="mb-3">
            <Col>
              <Space>
                <HistoryOutlined style={{ color: config.memory_enabled ? '#1890ff' : '#999' }} />
                <span>启用对话记忆</span>
              </Space>
            </Col>
            <Col>
              <Switch
                checked={config.memory_enabled}
                onChange={(checked) => setConfig({ ...config, memory_enabled: checked })}
                checkedChildren="启用"
                unCheckedChildren="禁用"
              />
            </Col>
          </Row>
          {config.memory_enabled && (
            <Row align="middle" className="mt-2">
              <Col span={6}>
                <Text>记忆窗口长度</Text>
              </Col>
              <Col>
                <Space>
                  <InputNumber
                    min={1}
                    max={500}
                    value={config.memory_window}
                    onChange={(val) => val && setConfig({ ...config, memory_window: val })}
                  />
                  <Text type="secondary">条消息</Text>
                </Space>
              </Col>
            </Row>
          )}
        </Card>
      </div>

      <ModelParametersModal
        open={paramsOpen}
        parameters={config.model_parameters || defaultParameters}
        onOk={handleParamsOk}
        onCancel={() => setParamsOpen(false)}
      />

      <ToolSelector
        open={toolSelectorOpen}
        selected={config.tools}
        onOk={handleToolSelectorOk}
        onCancel={() => setToolSelectorOpen(false)}
      />
    </div>
  )
}

export default AgentOrchestration
