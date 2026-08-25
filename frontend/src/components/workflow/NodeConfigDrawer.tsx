/**
 * 节点配置抽屉 — 点击节点时弹出，编辑节点配置
 * LLM 节点采用 Dify 风格布局
 */
import React, { useEffect, useMemo, useState } from 'react'
import {
  Drawer, Form, Input, Select, InputNumber, Button, Space,
  Switch, Divider, Typography, Tabs, Tag, Slider, Card, Tooltip, Popover,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, SettingOutlined,
  ThunderboltOutlined, LinkOutlined, InfoCircleOutlined,
  ClearOutlined, FunctionOutlined, CopyOutlined,
  CaretRightOutlined, CaretDownOutlined, HolderOutlined,
} from '@ant-design/icons'
import { WorkflowNode, NodeType, NodeData } from '../../services/workflow'
import { toolsApi, ToolData } from '../../services/tools'

const { TextArea } = Input
const { Text } = Typography

interface NodeConfigDrawerProps {
  node: WorkflowNode | null
  open: boolean
  onClose: () => void
  onSave: (nodeId: string, data: { label: string; config: Record<string, any> }) => void
  /** 工作流中所有上游节点，用于上下文变量选择 */
  upstreamNodes?: Array<{ id: string; data: NodeData; type?: string }>
}

const NodeConfigDrawer: React.FC<NodeConfigDrawerProps> = ({ node, open, onClose, onSave, upstreamNodes = [] }) => {
  const [form] = Form.useForm()
  const [activeTab, setActiveTab] = useState('settings')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    input: true,
    output: true,
    errorHandling: false,
  })
  const [availableTools, setAvailableTools] = useState<ToolData[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)

  useEffect(() => {
    if (node) {
      form.setFieldsValue({
        label: node.data.label,
        description: node.data.description,
        ...node.data.config,
      })
    }
  }, [node, form])

  // 加载工具列表（当打开工具节点配置时）
  useEffect(() => {
    if (open && node?.type === 'tool') {
      setToolsLoading(true)
      toolsApi.getTools().then((res) => {
        setAvailableTools(res.data || [])
      }).catch(() => {
        setAvailableTools([])
      }).finally(() => {
        setToolsLoading(false)
      })
    }
  }, [open, node?.type])

  // 监听工具选择变化（用于动态显示参数）
  const selectedToolId = Form.useWatch('tool_id', form)

  const handleSave = () => {
    if (!node) return
    const values = form.getFieldsValue()
    const { label, description, ...config } = values
    onSave(node.id, { label: label || '', config })
    onClose()
  }

  // ------------------------------------------------------------------
  // LLM 节点配置 — Dify 风格
  // ------------------------------------------------------------------
  const renderLLMConfig = () => (
    <>
      {/* 模型 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-red-500">*</span>
          <Text strong>模型</Text>
          <Tooltip title="选择用于此节点的大语言模型">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <div className="flex gap-2">
          <Form.Item name="model_id" noStyle>
            <Select
              placeholder="模型设置"
              className="flex-1"
              allowClear
              showSearch
              optionFilterProp="label"
            >
              {/* TODO: 从后端加载模型列表 */}
              <Select.Option value={1}>GPT-4o</Select.Option>
              <Select.Option value={2}>GPT-4o-mini</Select.Option>
              <Select.Option value={3}>Claude 3.5 Sonnet</Select.Option>
              <Select.Option value={4}>DeepSeek-V3</Select.Option>
            </Select>
          </Form.Item>
          <Tooltip title="模型设置">
            <Button icon={<SettingOutlined />} />
          </Tooltip>
        </div>
      </div>

      {/* 提示词 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <Text strong>提示词</Text>
          <Tooltip title="定义 LLM 的行为指令，可使用 {变量名} 引用上游变量">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="system_prompt" noStyle>
          <TextArea
            rows={3}
            placeholder="你是一个有用的AI助手"
            className="mb-2"
          />
        </Form.Item>
        <Form.Item name="prompt" noStyle>
          <TextArea
            rows={4}
            placeholder="请回答以下问题：{query}"
          />
        </Form.Item>
      </div>

      {/* 上下文 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <LinkOutlined className="text-blue-500" />
          <Text strong>上下文</Text>
          <Tooltip title="添加上游节点的输出作为上下文变量">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.List name="context">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <div key={key} className="flex items-center gap-2 mb-2">
                  <Form.Item {...restField} name={[name, 'variable_selector']} noStyle>
                    <Select
                      placeholder="选择变量"
                      className="flex-1"
                      size="small"
                      allowClear
                    >
                      {upstreamNodes.map((n) => (
                        <Select.Option key={n.id} value={[n.id, 'output']}>
                          {n.data.label || n.id}
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'variable_type']} noStyle initialValue="string">
                    <Select size="small" className="w-24">
                      <Select.Option value="string">String</Select.Option>
                      <Select.Option value="number">Number</Select.Option>
                      <Select.Option value="object">Object</Select.Option>
                      <Select.Option value="array">Array</Select.Option>
                    </Select>
                  </Form.Item>
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => remove(name)}
                  />
                </div>
              ))}
              <Button type="dashed" onClick={() => add()} icon={<PlusOutlined />} block size="small">
                添加上下文
              </Button>
              {fields.length === 0 && (
                <Text type="secondary" className="text-xs block mt-1">
                  要启用上下文功能，请在提示中填写上下文变量。
                </Text>
              )}
            </>
          )}
        </Form.List>
      </div>

      {/* 记忆 */}
      <div className="mb-5">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <ThunderboltOutlined className="text-blue-500" />
            <Text strong>记忆</Text>
            <Tag color="blue" className="ml-1">内置</Tag>
          </div>
          <Form.Item name={['memory', 'enabled']} valuePropName="checked" noStyle initialValue={true}>
            <Switch size="small" />
          </Form.Item>
        </div>
        <Card size="small" className="bg-gray-50 mb-2">
          <div className="flex items-center gap-2 mb-1">
            <Tag color="default">USER</Tag>
            <InfoCircleOutlined className="text-gray-400 text-xs" />
            <span className="text-xs text-gray-500">32</span>
          </div>
          <div className="flex gap-2 text-xs">
            <Tag color="blue">{`{x} query`}</Tag>
            <Tag color="blue">{`{x} files`}</Tag>
          </div>
        </Card>
        <div className="flex items-center gap-2">
          <Text type="secondary" className="text-xs whitespace-nowrap">记忆窗口</Text>
          <Form.Item name={['memory', 'window']} noStyle initialValue={10}>
            <Slider className="flex-1" min={1} max={100} />
          </Form.Item>
          <Form.Item name={['memory', 'window']} noStyle initialValue={10}>
            <InputNumber size="small" className="w-16" min={1} max={100} />
          </Form.Item>
        </div>
      </div>

      <Divider className="my-3" />

      {/* 视觉 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          <Text strong>视觉</Text>
          <Tooltip title="启用视觉功能后，模型可以处理图片输入">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="vision" valuePropName="checked" noStyle>
          <Switch size="small" />
        </Form.Item>
      </div>

      {/* 启用推理标签分离 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          <Text strong>启用推理标签分离</Text>
          <Tooltip title="将模型的推理过程与最终输出分离显示">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="thinking_tag" valuePropName="checked" noStyle>
          <Switch size="small" />
        </Form.Item>
      </div>

      <Divider className="my-3" />

      {/* 输出变量 */}
      <div className="mb-4">
        <div className="flex items-center justify-between mb-2">
          <Text strong>输出变量</Text>
          <div className="flex items-center gap-1">
            <Text type="secondary" className="text-xs">结构化输出</Text>
            <Form.Item name="structured_output" valuePropName="checked" noStyle>
              <Switch size="small" />
            </Form.Item>
          </div>
        </div>
        <Form.Item name="output_key" initialValue="output" noStyle>
          <Input size="small" placeholder="输出键名" />
        </Form.Item>
      </div>

      <Divider className="my-3" />

      {/* 失败时重试 */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-1">
          <Text strong>失败时重试</Text>
          <Tooltip title="当节点执行失败时自动重试">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="retry_on_failure" valuePropName="checked" noStyle>
          <Switch size="small" />
        </Form.Item>
      </div>

      {/* 高级参数 */}
      <Divider className="my-3" />
      <div className="flex items-center gap-1 mb-3">
        <SettingOutlined className="text-gray-400" />
        <Text type="secondary">高级参数</Text>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Text type="secondary" className="text-xs block mb-1">温度</Text>
          <Form.Item name="temperature" initialValue={0.7} noStyle>
            <InputNumber className="w-full" size="small" min={0} max={2} step={0.1} />
          </Form.Item>
        </div>
        <div>
          <Text type="secondary" className="text-xs block mb-1">最大 Token</Text>
          <Form.Item name="max_tokens" initialValue={2048} noStyle>
            <InputNumber className="w-full" size="small" min={1} max={8192} />
          </Form.Item>
        </div>
        <div>
          <Text type="secondary" className="text-xs block mb-1">Top P</Text>
          <Form.Item name="top_p" initialValue={1.0} noStyle>
            <InputNumber className="w-full" size="small" min={0} max={1} step={0.1} />
          </Form.Item>
        </div>
      </div>
    </>
  )

  // ------------------------------------------------------------------
  // 其他节点配置
  // ------------------------------------------------------------------
  const renderStartConfig = () => (
    <Form.Item name="variables" label="输入变量（JSON）">
      <TextArea rows={4} placeholder='[{"key": "query", "type": "string", "required": true}]' />
    </Form.Item>
  )

  const renderEndConfig = () => (
    <Form.Item name="output_keys" label="输出变量键名（逗号分隔）">
      <Input placeholder="output,result" />
    </Form.Item>
  )

  const renderKnowledgeConfig = () => (
    <>
      <Form.Item name="knowledge_base_id" label="知识库 ID">
        <InputNumber className="w-full" min={1} />
      </Form.Item>
      <Form.Item name="query_key" label="查询变量名" initialValue="query">
        <Input />
      </Form.Item>
      <Form.Item name="top_k" label="返回数量" initialValue={5}>
        <InputNumber className="w-full" min={1} max={20} />
      </Form.Item>
      <Form.Item name="score_threshold" label="相似度阈值" initialValue={0.5}>
        <InputNumber className="w-full" min={0} max={1} step={0.05} />
      </Form.Item>
      <Form.Item name="output_key" label="输出键名" initialValue="documents">
        <Input />
      </Form.Item>
      <Divider orientation="left" plain>重排序</Divider>
      <Form.Item name="rerank_enabled" label="启用重排序" valuePropName="checked" initialValue={false}>
        <Switch />
      </Form.Item>
      <Form.Item name="rerank_top_k" label="重排序 Top-K" initialValue={3}>
        <InputNumber className="w-full" min={1} max={20} />
      </Form.Item>
    </>
  )

  const renderConditionConfig = () => {
    // 节点类型中文标签
    const typeLabels: Record<string, string> = {
      llm: 'LLM',
      knowledge_retrieval: '知识检索',
      code: '代码执行',
      start: '用户输入',
      tool: '工具',
      http: 'HTTP 请求',
    }

    // 按节点类型对上游节点分组
    const groupedNodes = useMemo(() => {
      const groups: Record<string, Array<{ id: string; label: string; vars: Array<{ key: string; label: string; type: string }> }> > = {}

      for (const node of upstreamNodes) {
        const nodeType = node.type || 'unknown'
        if (!groups[nodeType]) {
          groups[nodeType] = []
        }
        const outputKey = node.data?.config?.output_key || 'output'
        const vars: Array<{ key: string; label: string; type: string }> = [
          { key: outputKey, label: outputKey, type: 'String' },
        ]
        // LLM 节点额外变量
        if (nodeType === 'llm') {
          vars.push({ key: 'reasoning_content', label: 'reasoning_content', type: 'String' })
          vars.push({ key: 'usage', label: 'usage', type: 'Object' })
        }
        groups[nodeType].push({
          id: node.id,
          label: node.data?.label || node.id,
          vars,
        })
      }
      return groups
    }, [upstreamNodes])

    // 渲染变量选择器下拉内容
    const renderVarDropdown = (onChange: (val: string) => void, currentValue?: string) => (
      <div style={{ maxHeight: 320, overflow: 'auto' }}>
        {Object.entries(groupedNodes).map(([nodeType, nodeList]) => (
          <div key={nodeType}>
            <div style={{
              padding: '6px 12px', fontWeight: 600, fontSize: 12,
              color: '#8c8c8c', background: '#fafafa', borderBottom: '1px solid #f0f0f0',
            }}>
              {typeLabels[nodeType] || nodeType}
            </div>
            {nodeList.map((node) =>
              node.vars.map((v) => (
                <div
                  key={`${node.id}.${v.key}`}
                  onClick={() => { onChange(`${node.id}.${v.key}`) }}
                  style={{
                    padding: '7px 12px', cursor: 'pointer', display: 'flex',
                    justifyContent: 'space-between', alignItems: 'center',
                    background: currentValue === `${node.id}.${v.key}` ? '#e6f4ff' : undefined,
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f5f5f5' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = currentValue === `${node.id}.${v.key}` ? '#e6f4ff' : '' }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{
                      color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace',
                      background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                    }}>{'{x}'}</span>
                    <span style={{ fontSize: 13 }}>{node.label} . {v.label}</span>
                  </span>
                  <span style={{ fontSize: 12, color: '#bfbfbf' }}>{v.type}</span>
                </div>
              ))
            )}
          </div>
        ))}
        {Object.keys(groupedNodes).length === 0 && (
          <div style={{ padding: '16px 12px', textAlign: 'center', color: '#bfbfbf', fontSize: 13 }}>
            暂无可用变量
          </div>
        )}
      </div>
    )

    // 运算符选项
    const operators = [
      { value: 'contains', label: '包含' },
      { value: 'not_contains', label: '不包含' },
      { value: 'equals', label: '等于' },
      { value: 'not_equals', label: '不等于' },
      { value: 'gt', label: '大于' },
      { value: 'lt', label: '小于' },
      { value: 'gte', label: '大于等于' },
      { value: 'lte', label: '小于等于' },
      { value: 'empty', label: '为空' },
      { value: 'not_empty', label: '不为空' },
    ]

    // 条件行渲染
    const renderConditionRow = (
      name: number,
      restField: any,
      label: string,
      labelColor: string,
      canDelete: boolean,
      onRemove?: () => void,
    ) => (
      <div key={name} className="border border-gray-200 rounded-lg mb-3 overflow-hidden">
        {/* 标签头 */}
        <div className="flex items-center justify-between px-3 py-2" style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
          <div className="flex items-center gap-2">
            <span style={{ color: labelColor, fontWeight: 700, fontSize: 13 }}>{label}</span>
            {canDelete && (
              <Tag color="blue" style={{ marginLeft: 4, fontSize: 11 }}>CASE{name + 1}</Tag>
            )}
          </div>
          {canDelete && onRemove && (
            <Button
              type="text" danger size="small" icon={<DeleteOutlined />}
              onClick={onRemove}
            />
          )}
        </div>
        {/* 条件内容 */}
        <div className="p-3">
          <div className="flex items-center gap-2">
            {/* 变量选择器 */}
            <Form.Item {...restField} name={[name, 'variable']} noStyle>
              <Popover
                content={renderVarDropdown(
                  (val: string) => {
                    const fieldsValues = form.getFieldsValue()
                    const branches = fieldsValues.branches || []
                    if (branches[name]) {
                      branches[name].variable = val
                      form.setFieldsValue({ branches })
                    }
                  },
                  form.getFieldValue(['branches', name, 'variable']),
                )}
                trigger="click"
                placement="bottomLeft"
                overlayInnerStyle={{ padding: 0, width: 280 }}
              >
                <div
                  style={{
                    border: '1px solid #d9d9d9', borderRadius: 6, padding: '5px 10px',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                    minWidth: 130, fontSize: 13, background: '#fff',
                  }}
                >
                  <FunctionOutlined style={{ color: '#8c8c8c' }} />
                  <span style={{ color: '#8c8c8c' }}>选择变量</span>
                </div>
              </Popover>
            </Form.Item>

            {/* 运算符 */}
            <Form.Item {...restField} name={[name, 'operator']} noStyle initialValue="contains">
              <Select size="middle" style={{ minWidth: 90 }} popupMatchSelectWidth={false}>
                {operators.map((op) => (
                  <Select.Option key={op.value} value={op.value}>{op.label}</Select.Option>
                ))}
              </Select>
            </Form.Item>

            {/* 值输入 */}
            <Form.Item {...restField} name={[name, 'value']} noStyle>
              <Input placeholder="值" style={{ flex: 1 }} />
            </Form.Item>
          </div>
        </div>
      </div>
    )

    return (
      <Form.List
        name="branches"
        initialValue={[
          { variable: '', operator: 'contains', value: '', branch: 'IF' },
          { variable: '', operator: 'default', value: '', branch: 'ELSE' },
        ]}
      >
        {(fields, { add, remove }) => {
          // 第一个条件是 IF，中间是 ELIF，最后一个是 ELSE
          const ifField = fields[0]
          const elseField = fields[fields.length - 1]
          const elifFields = fields.slice(1, -1)

          return (
            <div>
              {/* IF 块 */}
              {ifField && renderConditionRow(
                ifField.name, ifField, 'IF', '#1677ff', false,
              )}

              {/* ELIF 块 */}
              {elifFields.map((f) => renderConditionRow(
                f.name, f, 'ELIF', '#722ed1', true, () => remove(f.name),
              ))}

              {/* + ELIF 按钮 */}
              {ifField && elseField && (
                <Button
                  type="dashed"
                  onClick={() => {
                    // 在 ELSE 之前插入新条件
                    const elseIdx = elseField.name
                    add(
                      { variable: '', operator: 'contains', value: '', branch: '' },
                      elseIdx,
                    )
                  }}
                  icon={<PlusOutlined />}
                  block
                  className="mb-3"
                  style={{ borderColor: '#722ed1', color: '#722ed1' }}
                >
                  + ELIF
                </Button>
              )}

              {/* ELSE 块 */}
              {elseField && (
                <div className="border border-gray-200 rounded-lg mb-3 overflow-hidden">
                  <div className="flex items-center px-3 py-2" style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                    <span style={{ color: '#fa8c16', fontWeight: 700, fontSize: 13 }}>ELSE</span>
                  </div>
                  <div className="p-3">
                    <div className="text-xs text-gray-400">用于定义当以上条件均不满足时的处理逻辑</div>
                    <Form.Item {...elseField} name={[elseField.name, 'value']} noStyle>
                      <Input placeholder="默认输出值" className="mt-2" />
                    </Form.Item>
                  </div>
                </div>
              )}
            </div>
          )
        }}
      </Form.List>
    )
  }

  const renderCodeConfig = () => (
    <>
      <Form.Item name="language" label="语言" initialValue="python">
        <Select>
          <Select.Option value="python">Python</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="code" label="代码">
        <TextArea
          rows={8}
          placeholder={'# 可用变量: inputs, node_outputs, merged\n# 设置 result 作为输出\nresult = merged.get("query", "").upper()'}
          style={{ fontFamily: 'monospace' }}
        />
      </Form.Item>
      <Form.Item name="output_key" label="输出键名" initialValue="output">
        <Input />
      </Form.Item>
    </>
  )

  const renderHTTPConfig = () => (
    <>
      <Form.Item name="method" label="请求方法" initialValue="GET">
        <Select>
          <Select.Option value="GET">GET</Select.Option>
          <Select.Option value="POST">POST</Select.Option>
          <Select.Option value="PUT">PUT</Select.Option>
          <Select.Option value="DELETE">DELETE</Select.Option>
        </Select>
      </Form.Item>
      <Form.Item name="url" label="URL">
        <Input placeholder="https://api.example.com/endpoint" />
      </Form.Item>
      <Form.Item name="headers" label="请求头（JSON）">
        <TextArea rows={2} placeholder='{"Content-Type": "application/json"}' />
      </Form.Item>
      <Form.Item name="body" label="请求体（JSON）">
        <TextArea rows={3} placeholder='{"key": "value"}' />
      </Form.Item>
      <Form.Item name="timeout" label="超时（秒）" initialValue={30}>
        <InputNumber className="w-full" min={1} max={300} />
      </Form.Item>
      <Form.Item name="output_key" label="输出键名" initialValue="response">
        <Input />
      </Form.Item>
    </>
  )

  // ------------------------------------------------------------------
  // 工具节点配置 — Dify 风格（输入/输出/异常处理）
  // ------------------------------------------------------------------
  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  const renderToolConfig = () => {
    // 从选中的工具加载参数 schema 生成默认输入
    const selectedTool = availableTools.find(t => t.id === selectedToolId)
    const schemaProps = selectedTool?.parameters_schema?.properties || {}
    const schemaRequired = selectedTool?.parameters_schema?.required || []

    const defaultInputs = Object.entries(schemaProps).map(([name, prop]: [string, any]) => ({
      name,
      type: (prop.type === 'integer' || prop.type === 'number') ? 'Number' : 'String',
      required: schemaRequired.includes(name),
    }))

    // 默认输出参数
    const defaultOutputs = [
      { name: 'result', type: 'object' },
    ]

    // 工具类型标签颜色
    const typeColors: Record<string, string> = {
      builtin: 'green',
      plugin: 'blue',
      mcp: 'purple',
    }

    return (
      <>
        {/* 工具选择 */}
        <div className="mb-5">
          <div className="flex items-center gap-1 mb-2">
            <span className="text-red-500">*</span>
            <Text strong>工具</Text>
            <Tooltip title="选择要使用的工具">
              <InfoCircleOutlined className="text-gray-400 text-xs" />
            </Tooltip>
          </div>
          <Form.Item name="tool_id" noStyle>
            <Select
              placeholder={toolsLoading ? "加载中..." : "选择工具"}
              className="w-full"
              showSearch
              optionFilterProp="label"
              loading={toolsLoading}
              notFoundContent={toolsLoading ? "加载中..." : "暂无可用工具，请先在工具管理中安装"}
            >
              {availableTools.map((tool) => (
                <Select.Option key={tool.id} value={tool.id} label={tool.name}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span>{tool.icon || '🔧'}</span>
                      <span>{tool.name}</span>
                    </div>
                    <Tag color={typeColors[tool.tool_type] || 'default'} style={{ marginRight: 0 }}>
                      {tool.tool_type}
                    </Tag>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          {selectedTool?.description && (
            <Text type="secondary" className="text-xs mt-1 block">{selectedTool.description}</Text>
          )}
        </div>

        {/* 输入 Section */}
        <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
            onClick={() => toggleSection('input')}
          >
            <div className="flex items-center gap-2">
              {expandedSections.input ? <CaretDownOutlined /> : <CaretRightOutlined />}
              <Text strong>输入</Text>
            </div>
          </div>
          {expandedSections.input && (
            <div className="p-3 space-y-3">
              <Form.List name="inputs" initialValue={defaultInputs}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => {
                      return (
                        <div key={key} className="flex items-center gap-2">
                          {/* 拖拽手柄 */}
                          <HolderOutlined className="text-gray-300 cursor-move" />

                          {/* 参数名 */}
                          <Form.Item {...restField} name={[name, 'name']} noStyle>
                            <Input size="small" placeholder="参数名" style={{ width: 90 }} />
                          </Form.Item>

                          {/* 必填标记 */}
                          <Form.Item {...restField} name={[name, 'required']} noStyle valuePropName="checked">
                            <Switch size="small" checkedChildren="*" unCheckedChildren="" />
                          </Form.Item>

                          {/* 类型标签 */}
                          <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="String">
                            <Select size="small" style={{ width: 90 }} popupMatchSelectWidth={false}>
                              <Select.Option value="String">String</Select.Option>
                              <Select.Option value="Number">Number</Select.Option>
                              <Select.Option value="Boolean">Boolean</Select.Option>
                              <Select.Option value="Array">Array</Select.Option>
                              <Select.Option value="Object">Object</Select.Option>
                            </Select>
                          </Form.Item>

                          {/* 引用/直接输入选择 */}
                          <Form.Item {...restField} name={[name, 'inputMode']} noStyle initialValue="reference">
                            <Select size="small" style={{ width: 70 }} popupMatchSelectWidth={false}>
                              <Select.Option value="reference">引用</Select.Option>
                              <Select.Option value="direct">直接</Select.Option>
                            </Select>
                          </Form.Item>

                          {/* 变量选择/直接输入 */}
                          <Form.Item {...restField} name={[name, 'value']} noStyle>
                            <Select
                              size="small"
                              placeholder="请选择"
                              className="flex-1"
                              allowClear
                              showSearch
                              optionFilterProp="label"
                            >
                              {upstreamNodes.map((n) => (
                                <Select.Option key={n.id} value={`${n.id}.output`} label={n.data?.label || n.id}>
                                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <span style={{
                                      color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace',
                                      background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                                    }}>{'{x}'}</span>
                                    {n.data?.label || n.id} . output
                                  </span>
                                </Select.Option>
                              ))}
                            </Select>
                          </Form.Item>

                          {/* 删除按钮 */}
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            onClick={() => remove(name)}
                          />
                        </div>
                      )
                    })}
                    <Button
                      type="dashed"
                      onClick={() => add({ name: '', type: 'String', required: false, inputMode: 'reference' })}
                      icon={<PlusOutlined />}
                      block
                      size="small"
                    >
                      添加输入
                    </Button>
                  </>
                )}
              </Form.List>
            </div>
          )}
        </div>

        {/* 输出 Section */}
        <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
            onClick={() => toggleSection('output')}
          >
            <div className="flex items-center gap-2">
              {expandedSections.output ? <CaretDownOutlined /> : <CaretRightOutlined />}
              <Text strong>输出</Text>
            </div>
          </div>
          {expandedSections.output && (
            <div className="p-3">
              <Form.List name="outputs" initialValue={defaultOutputs}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => (
                      <div key={key} className="flex items-center gap-2 mb-2">
                        <HolderOutlined className="text-gray-300 cursor-move" />
                        <Form.Item {...restField} name={[name, 'name']} noStyle>
                          <Input size="small" placeholder="变量名" style={{ width: 100 }} />
                        </Form.Item>
                        <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="string">
                          <Input size="small" placeholder="类型" style={{ width: 100 }} disabled />
                        </Form.Item>
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => remove(name)}
                        />
                      </div>
                    ))}
                    <Button
                      type="dashed"
                      onClick={() => add({ name: '', type: 'string' })}
                      icon={<PlusOutlined />}
                      block
                      size="small"
                    >
                      添加输出
                    </Button>
                  </>
                )}
              </Form.List>
            </div>
          )}
        </div>

        {/* 异常处理 Section */}
        <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
          <div
            className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
            onClick={() => toggleSection('errorHandling')}
          >
            <div className="flex items-center gap-2">
              {expandedSections.errorHandling ? <CaretDownOutlined /> : <CaretRightOutlined />}
              <Text strong>异常处理</Text>
            </div>
            <div onClick={(e: React.MouseEvent) => e.stopPropagation()}>
              <Form.Item name="error_handling_enabled" valuePropName="checked" noStyle>
                <Switch size="small" />
              </Form.Item>
            </div>
          </div>
          {expandedSections.errorHandling && (
            <div className="p-3">
              <div className="mb-3">
                <Text type="secondary" className="text-xs block mb-1">失败时</Text>
                <Form.Item name="error_action" noStyle initialValue="retry">
                  <Select size="small" className="w-full">
                    <Select.Option value="retry">重试</Select.Option>
                    <Select.Option value="skip">跳过</Select.Option>
                    <Select.Option value="fallback">使用默认值</Select.Option>
                    <Select.Option value="stop">终止流程</Select.Option>
                  </Select>
                </Form.Item>
              </div>
              <div className="mb-3">
                <Text type="secondary" className="text-xs block mb-1">重试次数</Text>
                <Form.Item name="retry_count" noStyle initialValue={3}>
                  <InputNumber size="small" className="w-full" min={1} max={10} />
                </Form.Item>
              </div>
              <div>
                <Text type="secondary" className="text-xs block mb-1">超时时间（秒）</Text>
                <Form.Item name="timeout" noStyle initialValue={30}>
                  <InputNumber size="small" className="w-full" min={1} max={300} />
                </Form.Item>
              </div>
            </div>
          )}
        </div>
      </>
    )
  }

  const renderHumanInterventionConfig = () => (
    <>
      <Form.Item name="message" label="提示消息">
        <TextArea rows={2} placeholder="请审批此操作" />
      </Form.Item>
      <Form.Item name="timeout" label="超时时间（秒）" initialValue={300}>
        <InputNumber className="w-full" min={1} max={3600} />
      </Form.Item>
      <Form.Item name="timeout_output" label="超时输出值" initialValue="timeout">
        <Input />
      </Form.Item>
      <Form.Item name="output_key" label="输出键名" initialValue="output">
        <Input />
      </Form.Item>
    </>
  )

  const renderQuestionClassifierConfig = () => (
    <>
      {/* 模型 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-red-500">*</span>
          <Text strong>模型</Text>
          <Tooltip title="选择用于分类的大语言模型">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <div className="flex gap-2">
          <Form.Item name="model_id" noStyle>
            <Select
              placeholder="模型设置"
              className="flex-1"
              allowClear
              showSearch
              optionFilterProp="label"
            >
              <Select.Option value={1}>GPT-4o</Select.Option>
              <Select.Option value={2}>GPT-4o-mini</Select.Option>
              <Select.Option value={3}>Claude 3.5 Sonnet</Select.Option>
              <Select.Option value={4}>DeepSeek-V3</Select.Option>
            </Select>
          </Form.Item>
          <Tooltip title="模型设置">
            <Button icon={<SettingOutlined />} />
          </Tooltip>
        </div>
      </div>

      {/* 输入变量 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-red-500">*</span>
          <Text strong>输入变量</Text>
          <Tooltip title="选择要分类的输入文本变量">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="input_variable" noStyle>
          <Select
            placeholder="选择变量"
            allowClear
            showSearch
          >
            {upstreamNodes.map((n) => (
              <Select.Option key={n.id} value={`${n.id}.output`}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace', background: '#f5f5f5', padding: '1px 4px', borderRadius: 3 }}>{'{x}'}</span>
                  {n.data?.label || n.id} . output
                </span>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
      </div>

      {/* 视觉 */}
      <div className="mb-5 flex items-center justify-between">
        <div className="flex items-center gap-1">
          <Text strong>视觉</Text>
          <Tooltip title="启用后可以处理图片输入">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="vision" valuePropName="checked" noStyle>
          <Switch size="small" />
        </Form.Item>
      </div>

      {/* 分类 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-3">
          <span className="text-red-500">*</span>
          <Text strong>分类</Text>
          <Tooltip title="定义问题的分类类别，每个类别对应一个输出分支">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.List
          name="categories"
          initialValue={[
            { id: '1', name: 'CLASS 1', description: '' },
            { id: '2', name: 'CLASS 2', description: '' },
          ]}
        >
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name, ...restField }) => (
                <div
                  key={key}
                  className="border border-gray-200 rounded-lg mb-3 overflow-hidden"
                >
                  {/* 分类标题栏 */}
                  <div className="flex items-center justify-between px-3 py-2" style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
                    <Form.Item {...restField} name={[name, 'name']} noStyle>
                      <Input
                        placeholder="CLASS"
                        size="small"
                        style={{ width: 140, fontWeight: 600, fontSize: 13 }}
                      />
                    </Form.Item>
                    <div className="flex items-center gap-1">
                      <Tooltip title="变量">
                        <FunctionOutlined className="text-gray-400 text-sm cursor-pointer" />
                      </Tooltip>
                      <Tooltip title="复制">
                        <Button
                          type="text"
                          size="small"
                          icon={<CopyOutlined />}
                          onClick={() => {
                            const current = form.getFieldValue(['categories', name])
                            add({ ...current, id: Date.now().toString() }, name + 1)
                          }}
                        />
                      </Tooltip>
                      {fields.length > 1 && (
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          onClick={() => remove(name)}
                        />
                      )}
                    </div>
                  </div>
                  {/* 分类描述 */}
                  <div className="p-3">
                    <Form.Item {...restField} name={[name, 'description']} noStyle>
                      <TextArea
                        rows={2}
                        placeholder="在这里输入你的主题内容"
                        style={{ fontSize: 13 }}
                      />
                    </Form.Item>
                  </div>
                </div>
              ))}
              <Button
                type="dashed"
                onClick={() => add({ id: Date.now().toString(), name: `CLASS ${fields.length + 1}`, description: '' })}
                icon={<PlusOutlined />}
                block
              >
                添加分类
              </Button>
            </>
          )}
        </Form.List>
      </div>

      {/* 高级设置 */}
      <div className="mb-5">
        <Text strong className="text-gray-500">高级设置</Text>
      </div>

      {/* 输出变量 */}
      <div className="mb-5">
        <Text strong className="text-gray-500">输出变量</Text>
        <div className="mt-2 text-xs text-gray-400">
          输出分类结果到下一个节点
        </div>
      </div>

      <Form.Item name="output_key" label="输出键名" initialValue="classification" hidden>
        <Input />
      </Form.Item>
    </>
  )

  const renderConfigFields = (type: NodeType) => {
    switch (type) {
      case 'start': return renderStartConfig()
      case 'end': return renderEndConfig()
      case 'llm': return renderLLMConfig()
      case 'knowledge_retrieval': return renderKnowledgeConfig()
      case 'condition': return renderConditionConfig()
      case 'code': return renderCodeConfig()
      case 'http': return renderHTTPConfig()
      case 'tool': return renderToolConfig()
      case 'human_intervention': return renderHumanInterventionConfig()
      case 'question_classifier': return renderQuestionClassifierConfig()
      default: return null
    }
  }

  if (!node) return null

  const isLLM = node.type === 'llm'

  // LLM 节点使用 tabs 布局
  const tabItems = [
    {
      key: 'settings',
      label: '设置',
      children: (
        <Form form={form} layout="vertical" className="mt-2">
          {renderConfigFields(node.type)}
        </Form>
      ),
    },
    {
      key: 'lastRun',
      label: '上次运行',
      children: (
        <div className="text-center py-8 text-gray-400">
          暂无运行记录
        </div>
      ),
    },
  ]

  return (
    <Drawer
      title={
        <div className="flex items-center gap-2">
          <span className="text-lg font-medium">{node.data.label || node.type}</span>
        </div>
      }
      placement="right"
      width={isLLM ? 420 : 480}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          <Tooltip title="运行此节点">
            <Button type="text" icon={<ThunderboltOutlined />} />
          </Tooltip>
          <Tooltip title="复制">
            <Button type="text" icon={<ClearOutlined />} />
          </Tooltip>
          <Tooltip title="删除">
            <Button type="text" danger icon={<DeleteOutlined />} />
          </Tooltip>
        </Space>
      }
      footer={
        <div className="flex justify-end gap-2">
          <Button onClick={onClose}>取消</Button>
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
        </div>
      }
    >
      {/* 描述 */}
      <Form form={form} layout="vertical">
        <Form.Item name="description" noStyle>
          <Input placeholder="添加描述..." variant="borderless" className="mb-2" />
        </Form.Item>
      </Form>

      {/* 使用 tabs 或普通配置 */}
      {isLLM ? (
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
          className="node-config-tabs"
        />
      ) : (
        <Form form={form} layout="vertical">
          {renderConfigFields(node.type)}
        </Form>
      )}
    </Drawer>
  )
}

export default NodeConfigDrawer
