/**
 * 坐席工作台
 *
 * 三栏布局：会话队列 / 对话区 / 客户与工单侧栏。
 * 会话是共享池，坐席在这里挑活、接管、AI 先行回答、必要时转人工或建工单。
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Segmented, message as antdMessage } from 'antd'
import ChatPanel from '../../components/support/ChatPanel'
import SupportChatWidget from '../../components/support/SupportChatWidget'
import CustomerPanel from '../../components/support/CustomerPanel'
import CustomerFormModal from '../../components/support/CustomerFormModal'
import SessionList from '../../components/support/SessionList'
import AgentTraceDrawer from '../../components/support/AgentTraceDrawer'
import TicketForm from '../../components/support/TicketForm'
import supportApi from '../../services/support'
import useSupportChat from '../../hooks/useSupportChat'
import type {
  QuickReply,
  SupportOptions,
  SupportReference,
  SupportSession,
} from '../../types/support'

const PAGE_SIZE = 20

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '质量看板', value: '/support/quality' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const AgentWorkspace: React.FC = () => {
  const navigate = useNavigate()

  const [sessions, setSessions] = useState<SupportSession[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('all')
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')

  const [activeId, setActiveId] = useState<number | null>(null)
  const [activeSession, setActiveSession] = useState<SupportSession | null>(null)
  const [traceSession, setTraceSession] = useState<SupportSession | null>(null)

  const [options, setOptions] = useState<SupportOptions | null>(null)
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([])

  const [ticketOpen, setTicketOpen] = useState(false)
  const [customerModal, setCustomerModal] = useState<{
    open: boolean
    mode: 'link' | 'edit'
  }>({ open: false, mode: 'link' })

  const [suggestion, setSuggestion] = useState<{
    content: string
    references: SupportReference[]
    error: string | null
  }>({ content: '', references: [], error: null })
  const [suggesting, setSuggesting] = useState(false)

  const chat = useSupportChat(activeId)

  // 搜索防抖：避免每敲一个字都打一次列表接口
  useEffect(() => {
    const timer = setTimeout(() => setKeyword(keywordInput), 350)
    return () => clearTimeout(timer)
  }, [keywordInput])

  useEffect(() => {
    supportApi
      .options()
      .then(setOptions)
      .catch(() => undefined)
    supportApi
      .listQuickReplies()
      .then((res) => setQuickReplies(res.items || []))
      .catch(() => undefined)
  }, [])

  const loadSessions = useCallback(async () => {
    setLoading(true)
    try {
      const res = await supportApi.listSessions({
        status: statusFilter === 'all' ? undefined : statusFilter,
        keyword: keyword || undefined,
        page,
        page_size: PAGE_SIZE,
      })
      setSessions(res.items || [])
      setTotal(res.meta?.total || 0)
    } catch (err) {
      console.error('加载会话列表失败:', err)
    } finally {
      setLoading(false)
    }
  }, [statusFilter, keyword, page])

  useEffect(() => {
    void loadSessions()
  }, [loadSessions])

  useEffect(() => {
    setPage(1)
  }, [statusFilter, keyword])

  const selectSession = useCallback(async (session: SupportSession) => {
    setActiveId(session.id)
    setActiveSession(session)
    setSuggestion({ content: '', references: [], error: null })
    try {
      const detail = await supportApi.getSession(session.id)
      setActiveSession(detail)
    } catch (err) {
      console.error('加载会话详情失败:', err)
    }
  }, [])

  const refreshActive = useCallback(async () => {
    if (!activeId) return
    try {
      const detail = await supportApi.getSession(activeId)
      setActiveSession(detail)
      setSessions((prev) => prev.map((item) => (item.id === detail.id ? detail : item)))
    } catch (err) {
      console.error('刷新会话失败:', err)
    }
  }, [activeId])

  const handleSend = useCallback(
    (query: string) => {
      chat.send(query)
    },
    [chat]
  )

  // AI 回答会改写会话状态（意图、转人工标记），流式结束后刷新会话与队列。
  // 用 loading 边沿触发而非定时器：定时器时长和真实生成耗时对不齐，会漏刷或空刷。
  const prevLoadingRef = useRef(false)
  useEffect(() => {
    if (prevLoadingRef.current && !chat.loading) {
      void refreshActive()
      void loadSessions()
    }
    prevLoadingRef.current = chat.loading
  }, [chat.loading, refreshActive, loadSessions])

  const handleSendAgent = useCallback(
    async (content: string) => {
      await chat.sendAsAgent(content)
      void refreshActive()
      void loadSessions()
    },
    [chat, refreshActive, loadSessions]
  )

  const handleSwitchMode = useCallback(
    async (mode: 'ai' | 'human') => {
      if (!activeId) return
      try {
        const updated = await supportApi.switchMode(activeId, mode)
        setActiveSession(updated)
        void loadSessions()
      } catch (err) {
        console.error('切换模式失败:', err)
        antdMessage.error('切换模式失败')
      }
    },
    [activeId, loadSessions]
  )

  const handleTakeOver = useCallback(
    async (reason: string) => {
      if (!activeId) return
      const updated = await supportApi.takeOver(activeId, reason)
      setActiveSession(updated)
      antdMessage.success('已接管会话')
      void loadSessions()
    },
    [activeId, loadSessions]
  )

  const handleClose = useCallback(
    async (payload: {
      status: 'resolved' | 'closed'
      satisfaction?: number
      satisfaction_comment?: string
    }) => {
      if (!activeId) return
      const updated = await supportApi.closeSession(activeId, payload)
      setActiveSession(updated)
      antdMessage.success('会话已结束')
      void loadSessions()
    },
    [activeId, loadSessions]
  )

  const handleSuggest = useCallback(async () => {
    if (!activeId) return
    setSuggesting(true)
    setSuggestion({ content: '', references: [], error: null })
    try {
      const res = await supportApi.suggestReply(activeId)
      setSuggestion({
        content: res.content || '',
        references: res.references || [],
        error: res.error || null,
      })
    } catch (err) {
      console.error('获取建议回复失败:', err)
      setSuggestion({ content: '', references: [], error: '获取建议失败' })
    } finally {
      setSuggesting(false)
    }
  }, [activeId])

  const handleCreateSession = useCallback(async () => {
    try {
      const session = await supportApi.createSession({ mode: 'ai' })
      antdMessage.success('已创建新会话')
      setPage(1)
      await loadSessions()
      void selectSession(session)
    } catch (err) {
      console.error('创建会话失败:', err)
      antdMessage.error('创建会话失败')
    }
  }, [loadSessions, selectSession])

  const typeOptions = useMemo(
    () => options?.ticket_types || [],
    [options]
  )
  const priorityOptions = useMemo(() => options?.ticket_priorities || [], [options])

  return (
    <div className="h-full flex flex-col gap-3 py-3">
      <div className="flex justify-center">
        <Segmented
          value="/support"
          options={NAV_ITEMS}
          onChange={(value) => navigate(value as string)}
        />
      </div>

      <div className="flex-1 min-h-0 flex gap-3">
        <div className="w-80 flex-shrink-0">
          <SessionList
            sessions={sessions}
            loading={loading}
            activeId={activeId}
            total={total}
            page={page}
            pageSize={PAGE_SIZE}
            statusFilter={statusFilter}
            keyword={keywordInput}
            statusOptions={options?.session_status || []}
            onStatusChange={setStatusFilter}
            onKeywordChange={setKeywordInput}
            onPageChange={setPage}
            onSelect={selectSession}
            onShowTrace={setTraceSession}
            onCreate={handleCreateSession}
          />
          <AgentTraceDrawer
            open={!!traceSession}
            trace={traceSession?.last_ai_trace}
            onClose={() => setTraceSession(null)}
          />
        </div>

        <div className="flex-1 min-w-0">
          <ChatPanel
            session={activeSession}
            messages={chat.messages}
            loading={chat.loading}
            streaming={chat.loading}
            draftContent={chat.draftContent}
            draftReferences={chat.draftReferences}
            draftMeta={chat.draftMeta}
            draftThoughts={chat.draftThoughts}
            draftToolCalls={chat.draftToolCalls}
            draftTicket={chat.draftTicket}
            suggestHuman={chat.suggestHuman}
            quickReplies={quickReplies}
            suggestion={suggestion}
            suggesting={suggesting}
            onSend={handleSend}
            onSendAgent={handleSendAgent}
            onCancelStream={chat.cancel}
            onSwitchMode={handleSwitchMode}
            onTakeOver={handleTakeOver}
            onSuggest={handleSuggest}
            onDiscardSuggestion={() =>
              setSuggestion({ content: '', references: [], error: null })
            }
            onOpenTicket={() => setTicketOpen(true)}
            onClose={handleClose}
          />
        </div>

        <div className="w-72 flex-shrink-0 bg-white rounded-xl border border-slate-200 overflow-y-auto">
          <CustomerPanel
            sessionId={activeId}
            customerId={activeSession?.customer_id ?? null}
            onChangeCustomer={() =>
              setCustomerModal({ open: true, mode: 'link' })
            }
            onEditCustomer={() => setCustomerModal({ open: true, mode: 'edit' })}
          />
        </div>
      </div>

      <TicketForm
        open={ticketOpen}
        sessionId={activeId}
        defaultCustomerId={activeSession?.customer_id ?? null}
        defaultTitle={
          activeSession?.intent_label
            ? `${activeSession.intent_label}：${activeSession.customer_name || '客户'}的诉求`
            : ''
        }
        typeOptions={typeOptions}
        priorityOptions={priorityOptions}
        onCancel={() => setTicketOpen(false)}
        onCreated={() => {
          setTicketOpen(false)
          void refreshActive()
        }}
      />

      <CustomerFormModal
        open={customerModal.open}
        mode={customerModal.mode}
        sessionId={activeId}
        customerId={activeSession?.customer_id ?? null}
        sourceOptions={options?.customer_sources || []}
        onCancel={() => setCustomerModal({ ...customerModal, open: false })}
        onDone={() => {
          setCustomerModal({ ...customerModal, open: false })
          void refreshActive()
        }}
      />

      {/* 在线客服悬浮入口（右下角） */}
      <SupportChatWidget />
    </div>
  )
}

export default AgentWorkspace
