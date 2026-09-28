/**
 * useLearningChat - 学习助手问答状态与流式接收
 *
 * 与 hermes 的 useChatStream 相互独立：后者的端点与事件结构是 Hermes 专用的，
 * 学习助手的事件是 references / delta / done / error，语义不同，故单独实现。
 *
 * 消息一份在本地（驱动 UI），一份在服务端（持久化），
 * 发送时本地立刻落一条用户消息，保证「提问先显示出来」的跟手感。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import learningApi from '../services/learning'
import type { ChatMessage, ContextRef, LearningReference } from '../types/learning'

export function useLearningChat(resourceId: number) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [draftContent, setDraftContent] = useState('')
  const [draftReferences, setDraftReferences] = useState<LearningReference[]>([])
  const [error, setError] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)
  // 流式内容用 ref 累积：回调里读 state 拿到的是闭包旧值，ref 才是当前值
  const draftRef = useRef('')
  const refsRef = useRef<LearningReference[]>([])

  const resetDraft = useCallback(() => {
    draftRef.current = ''
    refsRef.current = []
    setDraftContent('')
    setDraftReferences([])
  }, [])

  // 切换资源时清空，避免串台
  useEffect(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    resetDraft()
    setMessages([])
    setError(null)
    setLoading(false)
  }, [resourceId, resetDraft])

  const loadHistory = useCallback(async () => {
    setLoadingHistory(true)
    try {
      const res = await learningApi.getChatHistory(resourceId)
      setMessages(res.messages || [])
    } catch (err) {
      console.error('加载问答历史失败:', err)
    } finally {
      setLoadingHistory(false)
    }
  }, [resourceId])

  const send = useCallback(
    (
      query: string,
      position: number,
      modelId?: number | null,
      contextRefs?: ContextRef[]
    ) => {
      const text = query.trim()
      if (!text || loading) return

      setError(null)
      resetDraft()
      setMessages((prev) => [
        ...prev,
        {
          id: -Date.now(),
          role: 'user',
          content: text,
          references: [],
          model: null,
          error: null,
          created_at: new Date().toISOString(),
        },
      ])
      setLoading(true)

      const controller = learningApi.chatStream(
        { resourceId, query: text, position, modelId, contextRefs },
        {
          onReferences: (references) => {
            refsRef.current = references
            setDraftReferences(references)
          },
          onDelta: (chunk) => {
            draftRef.current += chunk
            setDraftContent(draftRef.current)
          },
          onDone: ({ message_id }) => {
            // 必须先取值：setState 的 updater 是延迟执行的，
            // 若在里面读 draftRef.current，等执行时 resetDraft() 已经把它清空了
            // ——表现就是 done 之后消息「消失」（实为空内容的气泡）。
            const content = draftRef.current
            const references = refsRef.current
            setMessages((prev) => [
              ...prev,
              {
                id: message_id,
                role: 'assistant',
                content,
                references,
                model: null,
                error: null,
                created_at: new Date().toISOString(),
              },
            ])
            resetDraft()
            setLoading(false)
          },
          onError: (detail) => {
            setError(detail)
            setMessages((prev) => [
              ...prev,
              {
                id: -Date.now(),
                role: 'assistant',
                content: '',
                references: [],
                model: null,
                error: detail,
                created_at: new Date().toISOString(),
              },
            ])
            resetDraft()
            setLoading(false)
          },
        }
      )
      controllerRef.current = controller
    },
    [resourceId, loading, resetDraft]
  )

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    // 已生成的部分保留成一条消息：用户主动停止，也该看到「回答到哪儿了」
    // 同样要先取值，否则 updater 延迟执行时读到的是已清空的 ref
    const content = draftRef.current
    const references = refsRef.current
    if (content) {
      setMessages((prev) => [
        ...prev,
        {
          id: -Date.now(),
          role: 'assistant',
          content,
          references,
          model: null,
          error: null,
          created_at: new Date().toISOString(),
        },
      ])
    }
    resetDraft()
    setLoading(false)
  }, [resetDraft])

  const clear = useCallback(async () => {
    await learningApi.clearChatHistory(resourceId)
    resetDraft()
    setMessages([])
    setError(null)
  }, [resourceId, resetDraft])

  return {
    messages,
    loading,
    loadingHistory,
    draftContent,
    draftReferences,
    error,
    loadHistory,
    send,
    cancel,
    clear,
  }
}

export default useLearningChat
