/**
 * Hermes Agent API 客户端
 *
 * 职责：
 * 1. 会话管理 API
 * 2. 消息管理 API
 * 3. SSE 流式对话（原生 fetch + ReadableStream）
 */

import api from './api'

// ==================== 类型定义 ====================

export interface HermesSession {
  id: string
  title: string
  model: string
  skills: string[]
  tools: string[]
  created_at: string
  updated_at: string
}

/** 工作助理技能（平台自建，可 CRUD） */
export interface HermesSkill {
  id: string
  name: string
  slug: string
  description: string
  instruction: string
  icon: string
  enabled: boolean
  sort_order: number
  created_at: string
  updated_at: string
}

export interface HermesSkillInput {
  name: string
  slug: string
  description?: string
  instruction?: string
  icon?: string
  enabled?: boolean
  sort_order?: number
}

/** 内置工具（展示 + 偏好注入） */
export interface HermesTool {
  name: string
  label: string
  description: string
}

/** GET /v1/capabilities 代理结果 */
export interface HermesCapabilities {
  object?: string
  platform?: string
  model?: string
  auth?: { type: string; required: boolean }
  features: Record<string, boolean>
}

/** /health/detailed 只读摘要（仅状态与计数） */
export interface HermesHealthDetail {
  status: string
  ready?: boolean
  checks?: Array<{ name: string; status: string }>
  counts?: Record<string, number>
  platform?: string
  model?: string
  profile?: string
  version?: string
}

export interface HermesModel {
  id: string
  name: string
  owned_by: string
}

/** 后台计划任务 */
export interface HermesJob {
  id: string
  name?: string
  prompt?: string
  schedule?: string | { kind?: string; expr?: string; display?: string }
  skills?: string[]
  enabled?: boolean
  paused?: boolean
  status?: string
  last_status?: string
  next_run_at?: string
  created_at?: string
  [key: string]: unknown
}

export interface HermesJobInput {
  prompt: string
  schedule: string
  skills?: string[]
  name?: string
  delivery?: Record<string, unknown>
  model?: string
}

/** 发送消息的附加能力配置 */
export interface ChatStreamOptions {
  model?: string
  skills?: string[]
  tools?: string[]
  /** 随本条消息发送的附件 ID（先经 /attachments 上传拿到） */
  attachmentIds?: number[]
}

export interface HermesMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  tools_used: Array<{
    name: string
    args?: string
    output?: string
  }>
  token_input: number
  token_output: number
  created_at: string
  /** 本条消息附带的附件（仅历史消息由后端填充，用于缩略图展示） */
  attachments?: HermesAttachment[]
}

export interface ChatStreamData {
  session_id?: string
  run_id?: string
  content?: string
  tool_name?: string
  tool_args?: string
  tool_output?: string
  /** 工具调用唯一标识，用于配对 tool_start 与 tool_result */
  tool_call_id?: string
  usage?: Record<string, number>
  tools_used?: string[]
  message?: string
}

/** SSE 事件回调 */
export interface SSEEventCallbacks {
  onMessageStart?: (data: ChatStreamData) => void
  onContentDelta?: (data: ChatStreamData) => void
  onToolStart?: (data: ChatStreamData) => void
  onToolResult?: (data: ChatStreamData) => void
  onMessageEnd?: (data: ChatStreamData) => void
  onError?: (data: ChatStreamData) => void
}

// ==================== API 函数 ====================

/**
 * 获取会话列表
 */
export const getSessions = async (): Promise<HermesSession[]> => {
  const response = await api.get('/hermes/sessions')
  return response.data
}

/**
 * 创建新会话
 */
export const createSession = async (
  title: string = '新会话',
  model: string = '',
  skills: string[] = [],
  tools: string[] = []
): Promise<HermesSession> => {
  const response = await api.post('/hermes/sessions', { title, model, skills, tools })
  return response.data
}

/**
 * 更新会话能力配置（模型 / 技能 / 工具）
 */
export const updateSessionConfig = async (
  sessionId: string,
  config: { model?: string; skills?: string[]; tools?: string[] }
): Promise<HermesSession> => {
  const response = await api.patch(`/hermes/sessions/${sessionId}/config`, config)
  return response.data
}

/**
 * 删除会话
 */
export const deleteSession = async (sessionId: string): Promise<void> => {
  await api.delete(`/hermes/sessions/${sessionId}`)
}

/**
 * 获取会话的消息列表
 */
export const getMessages = async (sessionId: string): Promise<HermesMessage[]> => {
  const response = await api.get(`/hermes/sessions/${sessionId}/messages`)
  return response.data
}

/**
 * 健康检查
 */
export const checkHealth = async (): Promise<{
  status: string
  api_url: string
  error?: string
}> => {
  const response = await api.get('/hermes/health')
  return response.data
}

// ==================== 能力探测 / 模型 / 工具 / 状态 ====================

/** Hermes API Server 稳定能力清单（后端带缓存） */
export const getCapabilities = async (refresh = false): Promise<HermesCapabilities> => {
  const response = await api.get('/hermes/capabilities', { params: { refresh } })
  return { features: {}, ...response.data }
}

/** 可用模型列表 */
export const getModels = async (
  refresh = false
): Promise<{ model: string; models: HermesModel[] }> => {
  const response = await api.get('/hermes/models', { params: { refresh } })
  return response.data
}

/** 内置工具清单（展示 + 偏好注入） */
export const getTools = async (): Promise<HermesTool[]> => {
  const response = await api.get('/hermes/tools')
  return response.data?.tools || []
}

/** /health/detailed 只读摘要 */
export const getHealthDetail = async (refresh = false): Promise<HermesHealthDetail> => {
  const response = await api.get('/hermes/health/detailed', { params: { refresh } })
  return response.data
}

// ==================== 技能管理 ====================

export const getSkills = async (params?: {
  keyword?: string
  enabled_only?: boolean
}): Promise<HermesSkill[]> => {
  const response = await api.get('/hermes/skills', { params })
  return response.data
}

export const createSkill = async (data: HermesSkillInput): Promise<HermesSkill> => {
  const response = await api.post('/hermes/skills', data)
  return response.data
}

export const updateSkill = async (
  skillId: string,
  data: Partial<HermesSkillInput>
): Promise<HermesSkill> => {
  const response = await api.put(`/hermes/skills/${skillId}`, data)
  return response.data
}

export const deleteSkill = async (skillId: string): Promise<void> => {
  await api.delete(`/hermes/skills/${skillId}`)
}

// ==================== Runs（状态与停止） ====================

export interface HermesRunStatus {
  run_id: string
  session_id: string
  status: string
  external_run_id: string
  token_input: number
  token_output: number
  latency_ms: number
  upstream?: Record<string, unknown>
}

export const getRun = async (runId: string): Promise<HermesRunStatus> => {
  const response = await api.get(`/hermes/runs/${runId}`)
  return response.data
}

/**
 * 停止生成：存在上游 run 时真正中断 agent，否则后端返回 external=false
 */
export const stopRun = async (
  runId: string
): Promise<{ status: string; external: boolean; message?: string }> => {
  const response = await api.post(`/hermes/runs/${runId}/stop`)
  return response.data
}

// ==================== 后台计划任务 ====================

export const getJobs = async (): Promise<HermesJob[]> => {
  const response = await api.get('/hermes/jobs')
  return response.data?.jobs || []
}

export const createJob = async (data: HermesJobInput): Promise<HermesJob> => {
  const response = await api.post('/hermes/jobs', data)
  return response.data
}

export const updateJob = async (
  jobId: string,
  data: Partial<HermesJobInput>
): Promise<HermesJob> => {
  const response = await api.patch(`/hermes/jobs/${jobId}`, data)
  return response.data
}

export const deleteJob = async (jobId: string): Promise<void> => {
  await api.delete(`/hermes/jobs/${jobId}`)
}

export const controlJob = async (
  jobId: string,
  action: 'pause' | 'resume' | 'run'
): Promise<void> => {
  await api.post(`/hermes/jobs/${jobId}/${action}`)
}

// ==================== SSE 流式对话 ====================

/**
 * 分发 SSE 事件到回调
 */
function dispatchEvent(
  eventType: string,
  data: ChatStreamData,
  callbacks: SSEEventCallbacks
): void {
  switch (eventType) {
    case 'message_start':
      callbacks.onMessageStart?.(data)
      break
    case 'content_delta':
      callbacks.onContentDelta?.(data)
      break
    case 'tool_start':
      callbacks.onToolStart?.(data)
      break
    case 'tool_result':
      callbacks.onToolResult?.(data)
      break
    case 'message_end':
      callbacks.onMessageEnd?.(data)
      break
    case 'error':
      callbacks.onError?.(data)
      break
  }
}

/** chatStream 入参（对象化，避免位置参数膨胀） */
export interface ChatStreamParams {
  sessionId: string
  message: string
  callbacks: SSEEventCallbacks
  options?: ChatStreamOptions
  token?: string
}

/**
 * 流式发送消息（原生 fetch + ReadableStream 版本）
 *
 * 使用 fetch + ReadableStream 消费 SSE。
 * token 通过 Authorization header 传递。
 *
 * @returns AbortController，可用于取消请求
 */
export const chatStream = (params: ChatStreamParams): AbortController => {
  const {
    sessionId,
    message,
    callbacks,
    options = {},
    token = '',
  } = params
  const controller = new AbortController()
  const { model = '', skills = [], tools = [], attachmentIds } = options

  ;(async () => {
    try {
      const response = await fetch(`/api/v1/hermes/sessions/${sessionId}/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          model,
          skills,
          tools,
          attachment_ids: attachmentIds || [],
        }),
        signal: controller.signal,
      })

      if (!response.ok) {
        const errorText = await response.text()
        callbacks.onError?.({ message: `HTTP ${response.status}: ${errorText}` })
        return
      }

      const reader = response.body?.getReader()
      if (!reader) {
        callbacks.onError?.({ message: '无法获取响应流' })
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // 按行解析 SSE
        const lines = buffer.split('\n')
        buffer = lines.pop() || '' // 最后一个可能不完整

        let currentEvent = ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed) continue

          if (trimmed.startsWith('event:')) {
            currentEvent = trimmed.slice(6).trim()
          } else if (trimmed.startsWith('data:')) {
            const dataStr = trimmed.slice(5).trim()
            try {
              const data = JSON.parse(dataStr) as ChatStreamData
              dispatchEvent(currentEvent, data, callbacks)
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        callbacks.onError?.({ message: String(error) })
      }
    }
  })()

  return controller
}

/**
 * 取消进行中的对话
 *
 * 调用后端 /hermes/runs/{id}/stop：
 * - 存在上游 run：真正中断 agent
 * - 否则后端返回 external=false，由调用方降级为中止 SSE 连接
 */
export const cancelRun = async (
  runId: string
): Promise<{ stopped: boolean; message?: string }> => {
  try {
    const result = await stopRun(runId)
    return { stopped: result.external, message: result.message }
  } catch (error) {
    console.error('停止运行失败:', error)
    return { stopped: false, message: '停止失败' }
  }
}

// ==================== 会话附件 ====================

/** 后端返回的附件元信息 */
export interface HermesAttachment {
  id: number
  kind: 'image' | 'document'
  filename: string
  mime_type?: string | null
  file_size: number
  parse_status: 'pending' | 'parsed' | 'failed' | 'skipped'
  parse_error?: string | null
  message_id?: string | null
  preview_url: string
  created_at: string
}

/** 上传附件（multipart）；显式清除 Content-Type，让 axios 自动填 boundary */
export const uploadAttachment = async (file: File): Promise<HermesAttachment> => {
  const form = new FormData()
  form.append('file', file)
  const response = await api.post('/hermes/attachments', form, {
    headers: { 'Content-Type': undefined },
  })
  return response.data
}

/** 删除本人上传的附件 */
export const deleteAttachment = async (id: number): Promise<void> => {
  await api.delete(`/hermes/attachments/${id}`)
}

/** 附件预览/下载地址（GET，需鉴权） */
export const getAttachmentPreviewUrl = (id: number): string =>
  `/api/v1/hermes/attachments/${id}/preview`

/** 列出某会话下的全部附件（历史消息缩略图用） */
export const getSessionAttachments = async (
  sessionId: string
): Promise<HermesAttachment[]> => {
  const response = await api.get('/hermes/attachments', {
    params: { session_id: sessionId },
  })
  return response.data
}

/** 以 blob 形式加载附件预览（图片），避免 token 进入 URL */
export const loadAttachmentBlobUrl = async (
  id: number,
  token: string
): Promise<string> => {
  const response = await api.get(`/hermes/attachments/${id}/preview`, {
    responseType: 'blob',
    headers: { Authorization: `Bearer ${token}` },
  })
  return URL.createObjectURL(response.data)
}

// ==================== 快捷提示词（日常任务） ====================

export interface QuickPrompt {
  id: number
  title: string
  description: string
  content: string
  icon: string
  category: string
  sort_order: number
  is_builtin: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface QuickPromptInput {
  title: string
  content: string
  description?: string
  icon?: string
  category?: string
  sort_order?: number
}

export type QuickPromptUpdate = Partial<QuickPromptInput>

/** 获取可用提示词（内置 + 本人自建） */
export const getQuickPrompts = async (category?: string): Promise<QuickPrompt[]> => {
  const response = await api.get('/hermes/quick-prompts', {
    params: category ? { category } : undefined,
  })
  return response.data
}

export const createQuickPrompt = async (data: QuickPromptInput): Promise<QuickPrompt> => {
  const response = await api.post('/hermes/quick-prompts', data)
  return response.data
}

export const updateQuickPrompt = async (
  id: number,
  data: QuickPromptUpdate
): Promise<QuickPrompt> => {
  const response = await api.put(`/hermes/quick-prompts/${id}`, data)
  return response.data
}

export const deleteQuickPrompt = async (id: number): Promise<void> => {
  await api.delete(`/hermes/quick-prompts/${id}`)
}

/** 初始化内置默认提示词集（可重复调用，按标题去重） */
export const initBuiltinQuickPrompts = async (): Promise<{
  added: number
  total_builtin: number
}> => {
  const response = await api.post('/hermes/quick-prompts/init-builtin')
  return response.data
}
