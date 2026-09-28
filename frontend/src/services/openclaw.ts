/**
 * 工作助理 - OpenClaw API 服务
 */
import api from './api'

// ==================== 类型定义 ====================

export interface OpenClawSession {
  id: number
  agent_id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface OpenClawMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant' | 'system'
  content: Array<{ type: string; text?: string; image_url?: string }>
  run_id: string | null
  created_at: string
}

export interface ChatStreamData {
  session_id: number
  input: string
  agent_id?: string
}

export interface SSEEvent {
  event: string
  data: string
}

// ==================== API 方法 ====================

/**
 * 获取会话列表
 */
export const getSessions = async (): Promise<OpenClawSession[]> => {
  const response = await api.get('/openclaw/sessions')
  return response.data
}

/**
 * 创建新会话
 */
export const createSession = async (data: {
  agent_id?: string
  title?: string
}): Promise<OpenClawSession> => {
  const response = await api.post('/openclaw/sessions', data)
  return response.data
}

/**
 * 删除会话
 */
export const deleteSession = async (sessionId: number): Promise<void> => {
  await api.delete(`/openclaw/sessions/${sessionId}`)
}

/**
 * 获取会话消息历史
 */
export const getMessages = async (sessionId: number): Promise<OpenClawMessage[]> => {
  const response = await api.get(`/openclaw/sessions/${sessionId}/messages`)
  return response.data
}

/**
 * 取消任务
 */
export const cancelRun = async (runId: string): Promise<void> => {
  await api.post(`/openclaw/runs/${runId}/cancel`)
}

/**
 * 健康检查
 */
export const checkHealth = async (): Promise<{
  status: string
  openclaw_url?: string
  error?: string
}> => {
  const response = await api.get('/openclaw/health')
  return response.data
}

// ==================== SSE 流式聊天 ====================

/**
 * 聊天流式请求（SSE）
 *
 * 使用 fetch + ReadableStream 处理 SSE 流
 * 支持 AbortController 终止
 */
export const chatStream = async (
  data: ChatStreamData,
  signal?: AbortSignal,
  onEvent?: (event: SSEEvent) => void,
  onMessage?: (text: string) => void,
  onError?: (error: string) => void,
  onDone?: () => void
): Promise<void> => {
  const token = (await import('@/stores/auth')).useAuthStore.getState().token

  const response = await fetch('/api/v1/openclaw/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(data),
    signal,
  })

  if (!response.ok) {
    const errorText = await response.text()
    onError?.(`请求失败: ${response.status} ${errorText}`)
    return
  }

  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      let currentEvent = ''

      for (const line of lines) {
        if (line.startsWith('event:')) {
          currentEvent = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          const dataStr = line.slice(5).trim()

          onEvent?.({ event: currentEvent, data: dataStr })

          // 处理完成
          if (currentEvent === 'response.completed' || currentEvent === 'response.done' || dataStr === '[DONE]') {
            onDone?.()
            return
          }

          // 处理错误
          if (currentEvent === 'error') {
            try {
              const errorData = JSON.parse(dataStr)
              onError?.(errorData.error || '未知错误')
            } catch {
              onError?.(dataStr)
            }
            return
          }

          // 流式文本增量（实时渲染）
          if (currentEvent === 'response.output_text.delta') {
            try {
              const deltaData = JSON.parse(dataStr)
              if (deltaData.delta) {
                onMessage?.(deltaData.delta)
              }
            } catch {
              // 忽略解析错误
            }
          }
        }
      }
    }
  } catch (error: any) {
    if (error.name === 'AbortError') {
      // 用户主动取消
      return
    }
    onError?.(error.message || '流读取异常')
  } finally {
    reader.releaseLock()
  }
}
