/**
 * 智能客服助手 API 客户端
 *
 * 与后端 /api/v1/support 下的端点一一对应。
 * 普通请求走 axios 实例（自带 JWT），SSE 走 fetch + ReadableStream：
 * EventSource 不支持自定义 method / body，也不好带鉴权头。
 */

import api from './api'
import { useAuthStore } from '@/stores/auth'
import {
  AnalyticsResponse,
  BusinessData,
  ChatStreamCallbacks,
  CustomerCreatePayload,
  CustomerListResponse,
  CustomerUpdatePayload,
  EvalQueueResponse,
  GenerateKbDocsResponse,
  ManualScorePayload,
  ManualScoreResponse,
  MessageListResponse,
  MessageSendPayload,
  MessageSendResponse,
  QualitySummaryResponse,
  QuickReply,
  QuickReplyCreatePayload,
  SessionClosePayload,
  SessionCreatePayload,
  SessionListResponse,
  SessionUpdatePayload,
  SettingsUpdatePayload,
  SuggestReplyResponse,
  SupportCustomer,
  SupportEvaluation,
  SupportOptions,
  SupportSession,
  SupportSettings,
  SupportTicket,
  TicketCreatePayload,
  TicketDetailResponse,
  TicketListResponse,
  TicketUpdatePayload,
} from '../types/support'

const BASE = '/support'

// ---------------- 列表筛选参数 ----------------

export interface SessionListParams {
  status?: string
  mode?: string
  intent?: string
  assignee_id?: number
  customer_id?: number
  keyword?: string
  page?: number
  page_size?: number
}

export interface CustomerListParams {
  keyword?: string
  source?: string
  page?: number
  page_size?: number
}

export interface TicketListParams {
  status?: string
  type?: string
  priority?: string
  assignee_id?: number
  customer_id?: number
  keyword?: string
  only_overdue?: boolean
  page?: number
  page_size?: number
}

export const supportApi = {
  // ---------------- 客户 ----------------

  listCustomers(params: CustomerListParams): Promise<CustomerListResponse> {
    return api.get(`${BASE}/customers`, { params }).then((res) => res.data)
  },

  createCustomer(data: CustomerCreatePayload): Promise<SupportCustomer> {
    return api.post(`${BASE}/customers`, data).then((res) => res.data)
  },

  getCustomer(customerId: number): Promise<SupportCustomer> {
    return api.get(`${BASE}/customers/${customerId}`).then((res) => res.data)
  },

  updateCustomer(
    customerId: number,
    data: CustomerUpdatePayload
  ): Promise<SupportCustomer> {
    return api.patch(`${BASE}/customers/${customerId}`, data).then((res) => res.data)
  },

  deleteCustomer(customerId: number): Promise<void> {
    return api.delete(`${BASE}/customers/${customerId}`).then(() => undefined)
  },

  // ---------------- 会话 ----------------

  listSessions(params: SessionListParams): Promise<SessionListResponse> {
    return api.get(`${BASE}/sessions`, { params }).then((res) => res.data)
  },

  createSession(data: SessionCreatePayload): Promise<SupportSession> {
    return api.post(`${BASE}/sessions`, data).then((res) => res.data)
  },

  getSession(sessionId: number): Promise<SupportSession> {
    return api.get(`${BASE}/sessions/${sessionId}`).then((res) => res.data)
  },

  updateSession(
    sessionId: number,
    data: SessionUpdatePayload
  ): Promise<SupportSession> {
    return api.patch(`${BASE}/sessions/${sessionId}`, data).then((res) => res.data)
  },

  deleteSession(sessionId: number): Promise<void> {
    return api.delete(`${BASE}/sessions/${sessionId}`).then(() => undefined)
  },

  takeOver(sessionId: number, reason?: string): Promise<SupportSession> {
    return api
      .post(`${BASE}/sessions/${sessionId}/takeover`, { reason })
      .then((res) => res.data)
  },

  transfer(sessionId: number, assigneeId: number | null): Promise<SupportSession> {
    return api
      .post(`${BASE}/sessions/${sessionId}/transfer`, { assignee_id: assigneeId })
      .then((res) => res.data)
  },

  switchMode(sessionId: number, mode: string): Promise<SupportSession> {
    return api
      .post(`${BASE}/sessions/${sessionId}/mode`, { mode })
      .then((res) => res.data)
  },

  closeSession(
    sessionId: number,
    data: SessionClosePayload
  ): Promise<SupportSession> {
    return api
      .post(`${BASE}/sessions/${sessionId}/close`, data)
      .then((res) => res.data)
  },

  // ---------------- 消息 ----------------

  listMessages(sessionId: number, limit = 200): Promise<MessageListResponse> {
    return api
      .get(`${BASE}/sessions/${sessionId}/messages`, { params: { limit } })
      .then((res) => res.data)
  },

  sendMessage(
    sessionId: number,
    data: MessageSendPayload
  ): Promise<MessageSendResponse> {
    return api
      .post(`${BASE}/sessions/${sessionId}/messages`, data)
      .then((res) => res.data)
  },

  suggestReply(
    sessionId: number,
    modelId?: number | null
  ): Promise<SuggestReplyResponse> {
    return api
      .post(`${BASE}/sessions/${sessionId}/suggest`, { model_id: modelId ?? null })
      .then((res) => res.data)
  },

  /**
   * AI 流式问答
   *
   * 返回 AbortController：调用方用它取消（坐席点「停止」或切换会话时）。
   */
  chatStream(
    sessionId: number,
    query: string,
    modelId: number | null | undefined,
    callbacks: ChatStreamCallbacks
  ): AbortController {
    const controller = new AbortController()
    // token 在 Zustand store 里；不能读 localStorage，store 未必以 'token' 为 key 落盘
    const token = useAuthStore.getState().token

    const handleEvent = (raw: string) => {
      let eventName = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) eventName = line.slice(6).trim()
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      }
      if (!dataLines.length) return
      let payload: any = {}
      try {
        payload = JSON.parse(dataLines.join(''))
      } catch {
        return
      }
      if (eventName === 'references') callbacks.onReferences?.(payload)
      else if (eventName === 'delta') callbacks.onDelta?.(payload.content || '')
      else if (eventName === 'thought') callbacks.onThought?.(payload)
      else if (eventName === 'tool_call') callbacks.onToolCall?.(payload)
      else if (eventName === 'ticket') callbacks.onTicket?.(payload)
      else if (eventName === 'done') callbacks.onDone?.(payload)
      else if (eventName === 'error') callbacks.onError?.(payload.detail || '未知错误')
    }

    const run = async () => {
      const res = await fetch(`/api/v1${BASE}/sessions/${sessionId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query, model_id: modelId ?? null }),
        signal: controller.signal,
      })

      if (res.status === 401) {
        // fetch 不走 axios 拦截器，这里手动复刻登出行为，避免停留在过期态
        useAuthStore.getState().logout()
        window.location.href = '/login'
        callbacks.onError?.('登录已过期，请重新登录')
        return
      }

      if (!res.ok || !res.body) {
        const detail = await res.text().catch(() => '')
        callbacks.onError?.(detail || `请求失败（${res.status}）`)
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        // SSE 以空行分隔事件，逐段切出完整事件后再解析
        let index = buffer.indexOf('\n\n')
        while (index >= 0) {
          handleEvent(buffer.slice(0, index))
          buffer = buffer.slice(index + 2)
          index = buffer.indexOf('\n\n')
        }
      }
      // 收尾：部分实现末尾不补空行
      if (buffer.trim()) handleEvent(buffer)
    }

    run().catch((err: any) => {
      if (err?.name === 'AbortError') return
      console.error('客服流式问答失败:', err)
      callbacks.onError?.('网络异常，请稍后重试')
    })

    return controller
  },

  // ---------------- 工单 ----------------

  listTickets(params: TicketListParams): Promise<TicketListResponse> {
    return api.get(`${BASE}/tickets`, { params }).then((res) => res.data)
  },

  createTicket(data: TicketCreatePayload): Promise<SupportTicket> {
    return api.post(`${BASE}/tickets`, data).then((res) => res.data)
  },

  getTicket(ticketId: number): Promise<TicketDetailResponse> {
    return api.get(`${BASE}/tickets/${ticketId}`).then((res) => res.data)
  },

  updateTicket(
    ticketId: number,
    data: TicketUpdatePayload
  ): Promise<SupportTicket> {
    return api.patch(`${BASE}/tickets/${ticketId}`, data).then((res) => res.data)
  },

  transitionTicket(
    ticketId: number,
    toStatus: string,
    content?: string
  ): Promise<TicketDetailResponse> {
    return api
      .post(`${BASE}/tickets/${ticketId}/transition`, {
        to_status: toStatus,
        content,
      })
      .then((res) => res.data)
  },

  commentTicket(ticketId: number, content: string): Promise<TicketDetailResponse> {
    return api
      .post(`${BASE}/tickets/${ticketId}/comments`, { content })
      .then((res) => res.data)
  },

  deleteTicket(ticketId: number): Promise<void> {
    return api.delete(`${BASE}/tickets/${ticketId}`).then(() => undefined)
  },

  // ---------------- 配置 ----------------

  getSettings(): Promise<SupportSettings> {
    return api.get(`${BASE}/settings`).then((res) => res.data)
  },

  updateSettings(data: SettingsUpdatePayload): Promise<SupportSettings> {
    return api.put(`${BASE}/settings`, data).then((res) => res.data)
  },

  // ---------------- 快捷话术 ----------------

  listQuickReplies(category?: string): Promise<{ items: QuickReply[] }> {
    return api
      .get(`${BASE}/quick-replies`, { params: { category } })
      .then((res) => res.data)
  },

  createQuickReply(data: QuickReplyCreatePayload): Promise<QuickReply> {
    return api.post(`${BASE}/quick-replies`, data).then((res) => res.data)
  },

  deleteQuickReply(replyId: number): Promise<void> {
    return api.delete(`${BASE}/quick-replies/${replyId}`).then(() => undefined)
  },

  // ---------------- 统计与选项 ----------------

  analytics(days = 7): Promise<AnalyticsResponse> {
    return api.get(`${BASE}/analytics`, { params: { days } }).then((res) => res.data)
  },

  options(): Promise<SupportOptions> {
    return api.get(`${BASE}/options`).then((res) => res.data)
  },

  // ---------------- 业务数据（Demo 示例） ----------------

  getBusinessData(): Promise<BusinessData> {
    return api.get(`${BASE}/business-data`).then((res) => res.data)
  },

  resetBusinessData(): Promise<{ ok: true }> {
    return api.post(`${BASE}/business-data/reset`).then((res) => res.data)
  },

  // ---------------- 评测（自动 + 人工） ----------------

  /** 触发单条 AI 回答的自动评测 */
  evaluateMessage(sessionId: number, messageId: number): Promise<SupportEvaluation> {
    return api
      .post(`${BASE}/sessions/${sessionId}/messages/${messageId}/evaluate`)
      .then((res) => res.data)
  },

  /** 自动评测本会话全部未评的 AI 消息，返回处理条数 */
  evaluateSession(sessionId: number): Promise<{ ok: true; done: number }> {
    return api
      .post(`${BASE}/sessions/${sessionId}/messages/evaluate-all`)
      .then((res) => res.data)
  },

  /** 获取单条评测记录（可能 404） */
  getEvaluation(messageId: number): Promise<SupportEvaluation> {
    return api.get(`${BASE}/evaluations/${messageId}`).then((res) => res.data)
  },

  /** 人工标注打分 */
  manualScore(data: ManualScorePayload): Promise<ManualScoreResponse> {
    return api.post(`${BASE}/evaluations/manual`, data).then((res) => res.data)
  },

  /** 待标注队列 */
  evaluationQueue(params: { status?: string; page?: number; page_size?: number } = {}): Promise<EvalQueueResponse> {
    return api.get(`${BASE}/evaluations/queue`, { params }).then((res) => res.data)
  },

  /** 质量看板汇总 */
  qualitySummary(days = 7): Promise<QualitySummaryResponse> {
    return api.get(`${BASE}/evaluations/quality`, { params: { days } }).then((res) => res.data)
  },

  // ---------------- 知识库文档生成 ----------------

  generateKbDocs(): Promise<GenerateKbDocsResponse> {
    return api.post(`${BASE}/generate-kb-docs`).then((res) => res.data)
  },
}

export default supportApi
