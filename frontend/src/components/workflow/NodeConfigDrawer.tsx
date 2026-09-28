/**
 * 节点配置抽屉 — 精简外壳，组合各子组件
 */
import React, { useEffect, useState } from 'react'
import { Drawer, Form, Input, Button, Space, Tabs, Tooltip, message } from 'antd'
import {
  DeleteOutlined, ThunderboltOutlined, ClearOutlined,
} from '@ant-design/icons'
import { WorkflowNode, NodeType, NodeData, workflowApi } from '@/services/workflow'
import { toolsApi, ToolData } from '@/services/tools'
import { modelsApi, ModelData } from '@/services/models'
import { knowledgeApi, KnowledgeBaseData } from '@/services/knowledge'

// 节点配置组件
import LLMConfig from './node-configs/LLMConfig'
import StartConfig from './node-configs/StartConfig'
import EndConfig from './node-configs/EndConfig'
import KnowledgeConfig from './node-configs/KnowledgeConfig'
import ConditionConfig from './node-configs/ConditionConfig'
import CodeConfig from './node-configs/CodeConfig'
import HTTPConfig from './node-configs/HTTPConfig'
import ToolConfig from './node-configs/ToolConfig'
import HumanInterventionConfig from './node-configs/HumanInterventionConfig'
import QuestionClassifierConfig from './node-configs/QuestionClassifierConfig'

// 运行 Tab
import LLMRunTab from './node-run-tabs/LLMRunTab'
import KnowledgeRunTab from './node-run-tabs/KnowledgeRunTab'

interface NodeConfigDrawerProps {
  node: WorkflowNode | null
  open: boolean
  onClose: () => void
  onSave: (nodeId: string, data: { label: string; config: Record<string, any> }) => void
  upstreamNodes?: Array<{ id: string; data: NodeData; type?: string }>
  appId?: number
}

const NodeConfigDrawer: React.FC<NodeConfigDrawerProps> = ({ node, open, onClose, onSave, upstreamNodes = [], appId }) => {
  const [form] = Form.useForm()
  const [activeTab, setActiveTab] = useState('settings')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    input: true, output: true, errorHandling: false,
  })

  // 数据加载
  const [availableTools, setAvailableTools] = useState<ToolData[]>([])
  const [toolsLoading, setToolsLoading] = useState(false)
  const [availableModels, setAvailableModels] = useState<ModelData[]>([])
  const [modelsLoading, setModelsLoading] = useState(false)
  const [availableKBs, setAvailableKBs] = useState<KnowledgeBaseData[]>([])
  const [kbsLoading, setKbsLoading] = useState(false)

  // Form.useWatch
  const watchedOutputType = Form.useWatch('output_type', form) || 'text'
  const selectedToolId = Form.useWatch('tool_id', form)

  // 加载数据
  useEffect(() => {
    if (open && node?.type === 'tool') {
      setToolsLoading(true)
      toolsApi.getTools().then((res) => setAvailableTools(res.data || [])).catch(() => setAvailableTools([])).finally(() => setToolsLoading(false))
    }
  }, [open, node?.type])

  useEffect(() => {
    if (open && (node?.type === 'llm' || node?.type === 'question_classifier')) {
      setModelsLoading(true)
      modelsApi.getAllModels().then((res) => setAvailableModels(res.data || [])).catch(() => setAvailableModels([])).finally(() => setModelsLoading(false))
    }
  }, [open, node?.type])

  useEffect(() => {
    if (open && node?.type === 'knowledge_retrieval') {
      setKbsLoading(true)
      knowledgeApi.getKnowledgeBases({ limit: 100 }).then((res) => setAvailableKBs(res.data?.items || [])).catch(() => setAvailableKBs([])).finally(() => setKbsLoading(false))
    }
  }, [open, node?.type])

  // 表单初始值同步 — 先 reset 再 set，防止上一个节点的残留字段
  useEffect(() => {
    if (open && node) {
      form.resetFields()
      form.setFieldsValue({ ...node.data.config, label: node.data.label, description: node.data.description })
      setActiveTab('settings')
      setLlmRunResult(null)
      setLlmRunUserMessage('')
      setLastRunResults(null)
      setLastRunQuery('')
    }
  }, [open, node, form])

  // ------------------------------------------------------------------
  // LLM 运行调试
  // ------------------------------------------------------------------
  const [llmRunUserMessage, setLlmRunUserMessage] = useState('')
  const [llmRunResult, setLlmRunResult] = useState<any>(null)
  const [llmRunLoading, setLlmRunLoading] = useState(false)

  const handleRunLLMNode = async () => {
    if (!node || node.type !== 'llm' || !appId) return
    const values = form.getFieldsValue()
    const modelId = values.model_id
    const prompt: string = values.prompt || ''
    const userMessage: string = values.user_message || ''
    const outputType = values.output_type || 'text'
    const outputSchema = values.output_schema
    const outputVariables = values.output_variables || []

    if (!modelId) { message.warning('请先选择模型'); return }

    // 解析 output_schema（TextArea 返回字符串，后端期望对象）
    let parsedSchema: Record<string, any> | undefined
    if (outputType === 'structured' && outputSchema) {
      if (typeof outputSchema === 'string') {
        try { parsedSchema = JSON.parse(outputSchema) } catch { message.warning('JSON Schema 格式错误'); return }
      } else {
        parsedSchema = outputSchema
      }
    }

    // 用户消息输入框的内容作为 user_message
    const finalUserMessage = llmRunUserMessage || userMessage

    setLlmRunLoading(true)
    setLlmRunResult(null)
    try {
      const res = await workflowApi.runLLMNode(appId, {
        model_id: modelId,
        prompt,
        user_message: finalUserMessage,
        temperature: values.temperature ?? 0.7,
        max_tokens: values.max_tokens ?? 2048,
        top_p: values.top_p ?? 1.0,
        output_type: outputType,
        output_schema: parsedSchema,
        output_variables: outputType === 'structured' ? outputVariables : undefined,
      })
      setLlmRunResult(res)
    } catch {
      message.error('运行失败，请检查配置')
      setLlmRunResult(null)
    } finally {
      setLlmRunLoading(false)
    }
  }

  // ------------------------------------------------------------------
  // 知识检索运行调试
  // ------------------------------------------------------------------
  const [lastRunQuery, setLastRunQuery] = useState('')
  const [lastRunResults, setLastRunResults] = useState<any>(null)
  const [lastRunLoading, setLastRunLoading] = useState(false)

  const handleRunFromLastTab = async () => {
    if (!node || node.type !== 'knowledge_retrieval') return
    const values = form.getFieldsValue()
    const kbIds = values.knowledge_base_ids || []
    const topK = values.top_k ?? 5
    const scoreThreshold = values.score_threshold ?? 0.5
    const rerankEnabled = values.rerank_enabled ?? false

    // 按换行拆分多条查询
    const queries = lastRunQuery.split('\n').map((s: string) => s.trim()).filter(Boolean)

    if (queries.length === 0) { message.warning('请输入查询文本'); return }
    if (kbIds.length === 0) { message.warning('请先在设置中选择至少一个知识库'); return }

    setLastRunLoading(true)
    setLastRunResults(null)
    try {
      const seen = new Set<string>()
      const allResults: any[] = []
      for (const kbId of kbIds) {
        for (const q of queries) {
          const res = await knowledgeApi.searchKnowledgeBase(kbId, q, topK, scoreThreshold, 'rrf', rerankEnabled)
          if (res.data?.results) {
            for (const r of res.data.results) {
              const key = r.content || ''
              if (!seen.has(key)) {
                seen.add(key)
                allResults.push(r)
              }
            }
          }
        }
      }
      allResults.sort((a: any, b: any) => (b.score || 0) - (a.score || 0))
      setLastRunResults({ queries, results: allResults.slice(0, topK), total: allResults.length })
      setActiveTab('lastRun')
    } catch {
      message.error('运行失败，请检查配置')
      setLastRunResults(null)
    } finally {
      setLastRunLoading(false)
    }
  }

  // ------------------------------------------------------------------
  // 保存
  // ------------------------------------------------------------------
  const handleSave = () => {
    if (!node) return
    const values = form.getFieldsValue()
    const { label, description, ...config } = values
    onSave(node.id, { label: label || node.data.label, config: { ...config, description } })
  }

  // ------------------------------------------------------------------
  // 配置渲染路由
  // ------------------------------------------------------------------
  const renderConfigFields = (type: NodeType) => {
    switch (type) {
      case 'start': return <StartConfig />
      case 'end': return <EndConfig form={form} upstreamNodes={upstreamNodes} />
      case 'llm': return <LLMConfig form={form} upstreamNodes={upstreamNodes} availableModels={availableModels} modelsLoading={modelsLoading} watchedOutputType={watchedOutputType} />
      case 'knowledge_retrieval': return <KnowledgeConfig form={form} upstreamNodes={upstreamNodes} availableKBs={availableKBs} kbsLoading={kbsLoading} />
      case 'condition': return <ConditionConfig form={form} upstreamNodes={upstreamNodes} />
      case 'code': return <CodeConfig />
      case 'http': return <HTTPConfig />
      case 'tool': return <ToolConfig form={form} upstreamNodes={upstreamNodes} availableTools={availableTools} toolsLoading={toolsLoading} selectedToolId={selectedToolId} expandedSections={expandedSections} onToggleSection={(s) => setExpandedSections(prev => ({ ...prev, [s]: !prev[s] }))} />
      case 'human_intervention': return <HumanInterventionConfig />
      case 'question_classifier': return <QuestionClassifierConfig form={form} upstreamNodes={upstreamNodes} availableModels={availableModels} modelsLoading={modelsLoading} />
      default: return null
    }
  }

  // ------------------------------------------------------------------
  // 主渲染
  // ------------------------------------------------------------------
  if (!node) return null

  const isLLM = node.type === 'llm'
  const isKnowledge = node.type === 'knowledge_retrieval'
  const useTabs = isLLM || isKnowledge

  const settingsTab = (
    <Form form={form} layout="vertical" className="mt-2">
      {renderConfigFields(node.type)}
    </Form>
  )

  const tabItems = isLLM ? [
    { key: 'settings', label: '设置', children: settingsTab },
    {
      key: 'lastRun', label: '运行',
      children: (
        <LLMRunTab
          form={form}
          llmRunUserMessage={llmRunUserMessage}
          onUserMessageChange={setLlmRunUserMessage}
          llmRunResult={llmRunResult}
          llmRunLoading={llmRunLoading}
          onRun={handleRunLLMNode}
        />
      ),
    },
  ] : isKnowledge ? [
    { key: 'settings', label: '设置', children: settingsTab },
    {
      key: 'lastRun', label: '运行',
      children: (
        <KnowledgeRunTab
          lastRunQuery={lastRunQuery}
          onQueryChange={setLastRunQuery}
          lastRunResults={lastRunResults}
          lastRunLoading={lastRunLoading}
          onRun={handleRunFromLastTab}
        />
      ),
    },
  ] : [{ key: 'settings', label: '设置', children: settingsTab }]

  return (
    <Drawer
      title={
        <div className="flex flex-col">
          <span className="text-lg font-medium">{node.data.label || node.type}</span>
          {node.data.description && <span className="text-xs text-gray-400">{node.data.description}</span>}
        </div>
      }
      placement="right"
      width={480}
      open={open}
      onClose={onClose}
      extra={
        <Space>
          {useTabs && (
            <Tooltip title="运行此节点">
              <Button type="text" icon={<ThunderboltOutlined />} onClick={() => setActiveTab('lastRun')} />
            </Tooltip>
          )}
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
          <Button type="primary" onClick={handleSave}>保存</Button>
        </div>
      }
    >
      {/* 节点名称 + 描述 */}
      <Form form={form} layout="vertical">
        <Form.Item name="label" noStyle>
          <Input placeholder="节点名称" variant="borderless" className="mb-1 font-medium" />
        </Form.Item>
        <Form.Item name="description" noStyle>
          <Input placeholder="添加描述..." variant="borderless" className="mb-2" />
        </Form.Item>
      </Form>

      {/* 配置内容 */}
      {useTabs ? (
        <Tabs activeKey={activeTab} onChange={setActiveTab} items={tabItems} className="node-config-tabs" />
      ) : (
        settingsTab
      )}
    </Drawer>
  )
}

export default NodeConfigDrawer
