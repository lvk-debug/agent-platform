/**
 * useSupportChat - 客服会话消息与 AI 流式回答
 *
 * 与 hermes 的 useChatStream 相互独立：后者与 Hermes 的事件协议耦合，
 * 本模块事件为 references / thought / tool_call / ticket / delta / done / error。
 *
 * 四条经验，务必保持：
 * 1. 流式内容用 useRef 累积——回调里读 state 拿到的是闭包旧值；
 * 2. onDone 里先取 ref 再 setState，否则 resetDraft() 已清空，表现为消息「消失」；
 * 3. 发送时本地立刻插一条临时 AI 消息（负 id），流式过程（思考链/工具调用）实时挂上去；
 * 4. Agent 过程（thought/tool_call/ticket）也用 ref 累积，最后并入消息 trace 字段，
 *    历史回看无需重跑即可还原。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import supportApi from '../services/support'
import type {
  AgentTicketInfo,
  AgentToolCall,
  AgentTraceStep,
  SupportMessage,
  SupportMessageTrace,
  SupportReference,
} from '../types/support'

export interface DraftMeta {
  intent: string
  intentLabel: string
  confidence: number
  suggestHuman: boolean
}

const EMPTY_META: DraftMeta = {
  intent: '',
  intentLabel: '',
  confidence: 0,
  suggestHuman: false,
}

const emptyTrace = (): SupportMessageTrace => ({
  steps: [],
  tool_calls: [],
  ticket: null,
})

export function useSupportChat(sessionId: number | null) {
  const [messages, setMessages] = useState<SupportMessage[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [draftContent, setDraftContent] = useState('')
  const [draftReferences, setDraftReferences] = useState<SupportReference[]>([])
  const [draftMeta, setDraftMeta] = useState<DraftMeta>(EMPTY_META)
  const [draftThoughts, setDraftThoughts] = useState<AgentTraceStep[]>([])
  const [draftToolCalls, setDraftToolCalls] = useState<AgentToolCall[]>([])
  const [draftTicket, setDraftTicket] = useState<AgentTicketInfo | null>(null)
  const [suggestHuman, setSuggestHuman] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const controllerRef = useRef<AbortController | null>(null)
  const draftRef = useRef('')
  const refsRef = useRef<SupportReference[]>([])
  const metaRef = useRef<DraftMeta>(EMPTY_META)
  const thoughtsRef = useRef<AgentTraceStep[]>([])
  const toolCallsRef = useRef<AgentToolCall[]>([])
  const ticketRef = useRef<AgentTicketInfo | null>(null)
  const pendingAiIdRef = useRef<number | null>(null)

  const resetDraft = useCallback(() => {
    draftRef.current = ''
    refsRef.current = []
    metaRef.current = EMPTY_META
    thoughtsRef.current = []
    toolCallsRef.current = []
    ticketRef.current = null
    pendingAiIdRef.current = null
    setDraftContent('')
    setDraftReferences([])
    setDraftMeta(EMPTY_META)
    setDraftThoughts([])
    setDraftToolCalls([])
    setDraftTicket(null)
  }, [])

  const loadHistory = useCallback(async () => {
    if (!sessionId) return
    setLoadingHistory(true)
    try {
      const res = await supportApi.listMessages(sessionId)
      setMessages(res.items || [])
    } catch (err) {
      console.error('加载会话消息失败:', err)
    } finally {
      setLoadingHistory(false)
    }
  }, [sessionId])

  // 切换会话时清空，避免上一个会话的残留串台，并加载新会话的历史消息
  useEffect(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    resetDraft()
    setMessages([])
    setError(null)
    setLoading(false)
    setSuggestHuman(false)
    if (sessionId) {
      void loadHistory()
    }
  }, [sessionId, resetDraft, loadHistory])

  /** 把最新累积的 Agent 过程挂到临时 AI 消息上 */
  const patchPending = useCallback((patch: Partial<SupportMessage>) => {
    const id = pendingAiIdRef.current
    if (id == null) return
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...patch } : m)))
  }, [])

  /** AI 流式回答（会话处于 AI 模式） */
  const send = useCallback(
    (query: string, modelId?: number | null) => {
      const text = query.trim()
      if (!text || !sessionId || loading) return

      setError(null)
      setSuggestHuman(false)
      resetDraft()
      const pendingId = -Date.now()
      // AI 占位消息的 id 是 pendingId - 1，ref 必须指向它，
      // 否则流式内容与 trace 会被写进客户消息，导致 AI 气泡一直为空
      pendingAiIdRef.current = pendingId - 1
      setMessages((prev) => [
        ...prev,
        {
          id: pendingId,
          session_id: sessionId,
          role: 'customer',
          content: text,
          references: [],
          created_at: new Date().toISOString(),
        },
        {
          id: pendingId - 1,
          session_id: sessionId,
          role: 'ai',
          content: '',
          references: [],
          trace: emptyTrace(),
          created_at: new Date().toISOString(),
        },
      ])
      setLoading(true)

      const controller = supportApi.chatStream(sessionId, text, modelId, {
        onReferences: (payload) => {
          setSuggestHuman(!!payload.suggest_human)
          refsRef.current = payload.references || []
          metaRef.current = {
            intent: payload.intent || '',
            intentLabel: payload.intent_label || '',
            confidence: payload.confidence || 0,
            suggestHuman: !!payload.suggest_human,
          }
          setDraftReferences(refsRef.current)
          setDraftMeta(metaRef.current)
          const trace = emptyTrace()
          trace.references = payload
          patchPending({ references: payload.references || [], trace })
        },
        onThought: (step) => {
          const next = [...thoughtsRef.current, step]
          thoughtsRef.current = next
          setDraftThoughts(next)
          patchPending({ trace: { ...emptyTrace(), steps: next, tool_calls: toolCallsRef.current, ticket: ticketRef.current } })
        },
        onToolCall: (call) => {
          const next = [...toolCallsRef.current, call]
          toolCallsRef.current = next
          setDraftToolCalls(next)
          patchPending({ trace: { ...emptyTrace(), steps: thoughtsRef.current, tool_calls: next, ticket: ticketRef.current } })
        },
        onTicket: (ticket) => {
          ticketRef.current = ticket
          setDraftTicket(ticket)
          patchPending({ trace: { ...emptyTrace(), steps: thoughtsRef.current, tool_calls: toolCallsRef.current, ticket } })
        },
        onDelta: (chunk) => {
          draftRef.current += chunk
          setDraftContent(draftRef.current)
          patchPending({ content: draftRef.current })
        },
        onDone: ({ message_id }) => {
          const content = draftRef.current
          const references = refsRef.current
          const meta = metaRef.current
          const trace: SupportMessageTrace = {
            steps: thoughtsRef.current,
            tool_calls: toolCallsRef.current,
            ticket: ticketRef.current,
          }
          const id = pendingAiIdRef.current
          setMessages((prev) =>
            prev.map((m) =>
              m.id === id
                ? {
                    ...m,
                    id: message_id,
                    content,
                    references,
                    intent: meta.intent,
                    intent_label: meta.intentLabel,
                    confidence: meta.confidence,
                    trace,
                  }
                : m
            )
          )
          resetDraft()
          setLoading(false)
        },
        onError: (detail) => {
          setError(detail)
          const id = pendingAiIdRef.current
          setMessages((prev) =>
            prev.map((m) => (m.id === id ? { ...m, error: detail } : m))
          )
          resetDraft()
          setLoading(false)
        },
      })
      controllerRef.current = controller
    },
    [sessionId, loading, resetDraft, patchPending]
  )

  /** 坐席人工回复（会话处于人工模式）：非流式，直接落库 */
  const sendAsAgent = useCallback(
    async (content: string) => {
      const text = content.trim()
      if (!text || !sessionId) return null
      setMessages((prev) => [
        ...prev,
        {
          id: -Date.now(),
          session_id: sessionId,
          role: 'agent',
          content: text,
          references: [],
          created_at: new Date().toISOString(),
        },
      ])
      try {
        const res = await supportApi.sendMessage(sessionId, {
          content: text,
          role: 'agent',
        })
        setMessages((prev) => prev.map((item) => (item.id < 0 ? res.message : item)))
        return res
      } catch (err) {
        console.error('发送人工回复失败:', err)
        setError('发送失败，请重试')
        return null
      }
    },
    [sessionId]
  )

  /** 代客录入客户消息 */
  const sendAsCustomer = useCallback(
    async (content: string) => {
      const text = content.trim()
      if (!text || !sessionId) return null
      try {
        const res = await supportApi.sendMessage(sessionId, {
          content: text,
          role: 'customer',
        })
        setMessages((prev) => [...prev, res.message])
        return res
      } catch (err) {
        console.error('录入客户消息失败:', err)
        return null
      }
    },
    [sessionId]
  )

  const appendMessage = useCallback((message: SupportMessage) => {
    setMessages((prev) => [...prev, message])
  }, [])

  const cancel = useCallback(() => {
    controllerRef.current?.abort()
    controllerRef.current = null
    // 已生成的部分保留成一条消息：坐席主动停止，也该看到「答到哪儿了」
    const content = draftRef.current
    const references = refsRef.current
    const id = pendingAiIdRef.current
    if (content || thoughtsRef.current.length || toolCallsRef.current.length) {
      const trace: SupportMessageTrace = {
        steps: thoughtsRef.current,
        tool_calls: toolCallsRef.current,
        ticket: ticketRef.current,
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === id ? { ...m, content, references, trace } : m
        )
      )
    }
    resetDraft()
    setLoading(false)
  }, [resetDraft])

  return {
    messages,
    loading,
    loadingHistory,
    draftContent,
    draftReferences,
    draftMeta,
    draftThoughts,
    draftToolCalls,
    draftTicket,
    suggestHuman,
    error,
    loadHistory,
    send,
    sendAsAgent,
    sendAsCustomer,
    appendMessage,
    cancel,
    setMessages,
  }
}

export default useSupportChat
