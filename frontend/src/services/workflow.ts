/**
 * 工作流 API 服务
 */
import api from './api'

// ------------------------------------------------------------------
// 类型定义
// ------------------------------------------------------------------

export type NodeType =
  | 'start'
  | 'end'
  | 'llm'
  | 'knowledge_retrieval'
  | 'condition'
  | 'question_classifier'
  | 'code'
  | 'http'
  | 'tool'
  | 'human_intervention'

export interface NodePosition {
  x: number
  y: number
}

export interface NodeData {
  label: string
  description?: string
  config: Record<string, any>
}

export interface WorkflowNode {
  id: string
  type: NodeType
  position: NodePosition
  data: NodeData
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  targetHandle?: string
  label?: string
}

export interface WorkflowGraph {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

export interface WorkflowConfig {
  graph: WorkflowGraph
  name?: string
  description?: string
  version: number
}

export interface WorkflowRunRequest {
  inputs: Record<string, any>
  thread_id?: string
}

export interface WorkflowRunResponse {
  id: number
  workflow_id: number
  status: string
  inputs?: Record<string, any>
  outputs?: Record<string, any>
  node_runs?: Record<string, any>
  error_message?: string
  started_at?: string
  finished_at?: string
  duration?: number
  created_at: string
}

export interface DSLData {
  name?: string
  description?: string
  version: number
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
}

// ------------------------------------------------------------------
// LLM 节点配置类型
// ------------------------------------------------------------------

export interface LLMContextVariable {
  variable_selector: string[]
  variable_type: string
}

export interface LLMMemoryConfig {
  enabled: boolean
  window: number
  role_prefix: string
}

// ------------------------------------------------------------------
// 问题分类器节点配置类型
// ------------------------------------------------------------------

export interface QuestionClassifierCategory {
  id: string
  name: string
  description: string
}

export interface QuestionClassifierConfig {
  model_id?: number
  model?: string
  input_variable: string
  vision: boolean
  categories: QuestionClassifierCategory[]
  output_key: string
}

export interface LLMNodeConfig {
  model_id?: number
  model?: string
  prompt?: string
  system_prompt?: string
  temperature?: number
  max_tokens?: number
  top_p?: number
  output_key?: string
  context?: LLMContextVariable[]
  memory?: LLMMemoryConfig
  vision?: boolean
  thinking_tag?: boolean
  structured_output?: boolean
  retry_on_failure?: boolean
}

// ------------------------------------------------------------------
// 节点类型元数据
// ------------------------------------------------------------------

export interface NodeTypeMeta {
  type: NodeType
  label: string
  description: string
  icon: string
  color: string
}

export const NODE_TYPES: NodeTypeMeta[] = [
  { type: 'start', label: '开始', description: '工作流入口，定义输入变量', icon: 'PlayCircleOutlined', color: '#52c41a' },
  { type: 'end', label: '结束', description: '工作流出口，定义输出', icon: 'StopOutlined', color: '#ff4d4f' },
  { type: 'llm', label: 'LLM', description: '调用大语言模型', icon: 'RobotOutlined', color: '#1677ff' },
  { type: 'knowledge_retrieval', label: '知识库', description: '从知识库检索相关文档', icon: 'BookOutlined', color: '#722ed1' },
  { type: 'condition', label: '条件分支', description: '根据条件分支执行', icon: 'BranchesOutlined', color: '#1677ff' },
  { type: 'question_classifier', label: '问题分类器', description: '使用 LLM 对输入进行分类', icon: 'AuditOutlined', color: '#13c2c2' },
  { type: 'code', label: '代码', description: '执行自定义代码', icon: 'CodeOutlined', color: '#13c2c2' },
  { type: 'http', label: 'HTTP', description: '发送 HTTP 请求', icon: 'GlobalOutlined', color: '#eb2f96' },
  { type: 'tool', label: '工具', description: '调用已注册的工具', icon: 'ToolOutlined', color: '#595959' },
  { type: 'human_intervention', label: '人工介入', description: '等待人工审批或输入', icon: 'UserOutlined', color: '#1677ff' },
]

// ------------------------------------------------------------------
// API 方法
// ------------------------------------------------------------------

export const workflowApi = {
  /** 获取工作流配置 */
  getConfig: async (appId: number): Promise<WorkflowConfig> => {
    const response = await api.get(`/workflow/${appId}/config`)
    return response.data
  },

  /** 保存工作流配置 */
  updateConfig: async (appId: number, config: WorkflowConfig): Promise<void> => {
    await api.put(`/workflow/${appId}/config`, config)
  },

  /** 执行工作流 */
  run: async (appId: number, request: WorkflowRunRequest): Promise<any> => {
    const response = await api.post(`/workflow/${appId}/run`, request)
    return response.data
  },

  /** 获取运行记录列表 */
  getRuns: async (appId: number, limit: number = 20): Promise<WorkflowRunResponse[]> => {
    const response = await api.get(`/workflow/${appId}/runs`, { params: { limit } })
    return response.data
  },

  /** 获取单次运行详情 */
  getRun: async (appId: number, runId: number): Promise<WorkflowRunResponse> => {
    const response = await api.get(`/workflow/${appId}/runs/${runId}`)
    return response.data
  },

  /** 导出 DSL */
  exportDSL: async (appId: number): Promise<DSLData> => {
    const response = await api.post(`/workflow/${appId}/dsl/export`)
    return response.data.dsl
  },

  /** 导入 DSL */
  importDSL: async (appId: number, dsl: DSLData): Promise<void> => {
    await api.post(`/workflow/${appId}/dsl/import`, { dsl })
  },
}

export default workflowApi
