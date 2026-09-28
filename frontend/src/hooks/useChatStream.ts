/**
 * useChatStream - Hermes SSE 流式对话 Hook
 *
 * 参考文档: docs/hermes-migration-plan .md - 5.3 useChatStream Hook 完整代码
 *
 * 功能：
 * 1. 发送消息 → SSE 流式接收
 * 2. 实时累积 content
 * 3. 工具调用信息
 * 4. 加载状态
 * 5. 取消请求
 */

import { useState, useCallback, useRef } from 'react'
import {
  chatStream,
  stopRun,
  type ChatStreamOptions,
  type SSEEventCallbacks,
} from '@/services/hermes'

export interface ToolCall {
  name: string
  args?: string
  output?: string
  /** 工具调用唯一标识，用于精确配对 tool_start / tool_result */
  callId?: string
  status: 'running' | 'done'
}

export interface ChatStreamState {
  content: string
  loading: boolean
  error: string | null
  toolsUsed: ToolCall[]
  inputTokens: number
  outputTokens: number
}

export interface UseChatStreamReturn extends ChatStreamState {
  runId: string | null
  send: (params: {
    sessionId: string
    message: string
    token: string
    options?: ChatStreamOptions
    attachmentIds?: number[]
  }) => void
  cancel: () => void
  reset: () => void
}

const initialState: ChatStreamState = {
  content: '',
  loading: false,
  error: null,
  toolsUsed: [],
  inputTokens: 0,
  outputTokens: 0,
}

export function useChatStream(): UseChatStreamReturn {
  const [state, setState] = useState<ChatStreamState>(initialState)
  const [runId, setRunId] = useState<string | null>(null)
  const controllerRef = useRef<AbortController | null>(null)

  const send = useCallback(
    (params: {
      sessionId: string
      message: string
      token: string
      options?: ChatStreamOptions
      attachmentIds?: number[]
    }) => {
      const { sessionId, message, token, options = {}, attachmentIds } = params
      // 如果已有请求，先取消
      if (controllerRef.current) {
        controllerRef.current.abort()
      }

      // 重置状态
      setRunId(null)
      setState({
        ...initialState,
        loading: true,
      })

      const callbacks: SSEEventCallbacks = {
        onMessageStart: (data) => {
          // 记录 run_id，供「停止生成」调用后端 stop 接口
          if (data.run_id) {
            setRunId(data.run_id)
          }
          setState((prev) => ({ ...prev, loading: true }))
        },

        onContentDelta: (data) => {
          setState((prev) => ({
            ...prev,
            content: prev.content + data.content,
          }))
        },

        onToolStart: (data) => {
          setState((prev) => ({
            ...prev,
            toolsUsed: [
              ...prev.toolsUsed,
              {
                name: data.tool_name || '',
                args: data.tool_args || '',
                callId: data.tool_call_id,
                status: 'running' as const,
              },
            ],
          }))
        },

        onToolResult: (data) => {
          setState((prev) => {
            const tools = [...prev.toolsUsed]
            // 优先按 tool_call_id 精确配对，避免同名工具并发时错配；
            // 上游未提供 ID 时回退到同名匹配。
            const lastIdx = data.tool_call_id
              ? tools.findIndex(
                  (t) => t.callId === data.tool_call_id && t.status === 'running'
                )
              : tools.findIndex(
                  (t) => t.name === data.tool_name && t.status === 'running'
                )
            if (lastIdx >= 0) {
              tools[lastIdx] = {
                ...tools[lastIdx],
                output: data.tool_output,
                status: 'done' as const,
              }
            }
            return { ...prev, toolsUsed: tools }
          })
        },

        onMessageEnd: (data) => {
          setState((prev) => ({
            ...prev,
            loading: false,
            inputTokens: data.usage?.prompt_tokens || 0,
            outputTokens: data.usage?.completion_tokens || 0,
          }))
        },

        onError: (data) => {
          setState((prev) => ({
            ...prev,
            loading: false,
            error: data.message || '未知错误',
          }))
        },
      }

      const controller = chatStream({
        sessionId,
        message,
        callbacks,
        options: { ...options, attachmentIds },
        token,
      })
      controllerRef.current = controller
    },
    []
  )

  const cancel = useCallback(() => {
    // 1) 通知后端停止：存在上游 run 时真正中断 agent，否则后端降级处理
    if (runId) {
      stopRun(runId).catch((err) => console.error('停止运行失败:', err))
      setRunId(null)
    }
    // 2) 无论如何都断开本地 SSE，保证界面立即恢复可交互
    if (controllerRef.current) {
      controllerRef.current.abort()
      controllerRef.current = null
    }
    setState((prev) => ({ ...prev, loading: false }))
  }, [runId])

  const reset = useCallback(() => {
    if (controllerRef.current) {
      controllerRef.current.abort()
      controllerRef.current = null
    }
    setRunId(null)
    setState(initialState)
  }, [])

  return {
    ...state,
    runId,
    send,
    cancel,
    reset,
  }
}
