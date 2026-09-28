/**
 * 智能客服助手类型定义
 *
 * 与后端 app/schemas/support.py 一一对应。
 */

// ---------------- 通用 ----------------

export interface PageMeta {
  total: number
  page: number
  page_size: number
}

export interface SupportReference {
  kb_id?: number | null
  kb_name?: string
  document_id?: number | null
  document_name?: string
  segment_id?: number | null
  content?: string
  score?: number
}

export interface OptionItem {
  value: string
  label: string
}

export interface SupportOptions {
  session_status: OptionItem[]
  intents: OptionItem[]
  ticket_types: OptionItem[]
  ticket_status: OptionItem[]
  ticket_priorities: OptionItem[]
  customer_sources: OptionItem[]
}

// ---------------- 客户 ----------------

export interface SupportCustomer {
  id: number
  name: string
  phone?: string | null
  email?: string | null
  wechat?: string | null
  source: string
  source_label?: string
  remark?: string | null
  tags?: string[] | null
  session_count: number
  ticket_count: number
  last_session_at?: string | null
  created_at: string
  updated_at: string
}

export interface CustomerCreatePayload {
  name: string
  phone?: string
  email?: string
  wechat?: string
  source?: string
  remark?: string
  tags?: string[]
}

export interface CustomerUpdatePayload {
  name?: string
  phone?: string
  email?: string
  wechat?: string
  source?: string
  remark?: string
  tags?: string[]
}

export interface CustomerListResponse {
  items: SupportCustomer[]
  meta: PageMeta
}

// ---------------- 会话 ----------------

export type SessionMode = 'ai' | 'human'
export type SessionStatus = 'open' | 'pending_human' | 'resolved' | 'closed'

export interface SupportSession {
  id: number
  customer_id?: number | null
  customer_name?: string
  title: string
  mode: SessionMode
  status: SessionStatus
  status_label?: string
  intent?: string | null
  intent_label?: string
  intent_confidence: number
  assignee_id?: number | null
  assignee_name?: string
  message_count: number
  last_message_at?: string | null
  last_message_preview: string
  low_confidence_streak: number
  satisfaction?: number | null
  satisfaction_comment?: string | null
  resolved_at?: string | null
  closed_at?: string | null
  created_at: string
  updated_at: string
  // 最新一条 AI 消息的处理轨迹，供会话列表查看运行日志
  last_ai_trace?: SupportMessageTrace | null
}

export interface SessionListResponse {
  items: SupportSession[]
  meta: PageMeta
}

export interface SessionCreatePayload {
  customer_id?: number | null
  visitor_name?: string
  title?: string
  mode?: SessionMode
}

export interface SessionUpdatePayload {
  title?: string
  customer_id?: number | null
  intent?: string
}

export interface SessionClosePayload {
  status?: 'resolved' | 'closed'
  satisfaction?: number
  satisfaction_comment?: string
}

// ---------------- 消息 ----------------

export type MessageRole = 'customer' | 'agent' | 'ai' | 'system'

export interface SupportMessage {
  id: number
  session_id: number
  role: MessageRole
  content: string
  references: SupportReference[]
  intent?: string | null
  intent_label?: string
  confidence?: number | null
  model?: string | null
  tokens_used?: number | null
  latency_ms?: number | null
  error?: string | null
  operator_id?: number | null
  operator_name?: string
  trace?: SupportMessageTrace | null
  created_at: string
}

export interface MessageListResponse {
  session_id: number
  items: SupportMessage[]
}

export interface MessageSendPayload {
  content: string
  role?: 'customer' | 'agent'
  model_id?: number | null
}

export interface MessageSendResponse {
  message: SupportMessage
  session: SupportSession
}

export interface SuggestReplyResponse {
  content: string
  references: SupportReference[]
  error?: string | null
}

// ---------------- 工单 ----------------

export type TicketStatus =
  | 'pending'
  | 'processing'
  | 'resolved'
  | 'rejected'
  | 'closed'

export interface SupportTicket {
  id: number
  ticket_no: string
  customer_id?: number | null
  customer_name?: string
  session_id?: number | null
  type: string
  type_label?: string
  title: string
  description?: string | null
  status: TicketStatus
  status_label?: string
  priority: string
  priority_label?: string
  assignee_id?: number | null
  assignee_name?: string
  due_at?: string | null
  is_overdue: boolean
  resolved_at?: string | null
  closed_at?: string | null
  created_at: string
  updated_at: string
}

export interface TicketListResponse {
  items: SupportTicket[]
  meta: PageMeta
}

export interface SupportTicketLog {
  id: number
  ticket_id: number
  action: string
  from_status?: string | null
  from_status_label?: string
  to_status?: string | null
  to_status_label?: string
  content?: string | null
  operator_id?: number | null
  operator_name?: string
  created_at: string
}

export interface TicketDetailResponse {
  ticket: SupportTicket
  logs: SupportTicketLog[]
}

export interface TicketCreatePayload {
  customer_id?: number | null
  customer_new?: CustomerCreatePayload | null
  session_id?: number | null
  type?: string
  title: string
  description?: string
  priority?: string
  assignee_id?: number | null
  due_at?: string | null
}

export interface TicketUpdatePayload {
  title?: string
  description?: string
  type?: string
  priority?: string
  assignee_id?: number | null
  due_at?: string | null
}

// ---------------- 机器人配置 ----------------

export interface SupportSettings {
  id: number
  bot_name: string
  system_prompt?: string | null
  model_id?: number | null
  model_name?: string
  knowledge_base_ids: number[]
  knowledge_bases: { id: number; name: string }[]
  search_mode: string
  top_k: number
  score_threshold: number
  enable_rerank: boolean
  temperature: number
  max_tokens: number
  history_turns: number
  human_intents: string[]
  human_keywords: string[]
  low_confidence_threshold: number
  low_confidence_streak: number
  fallback_answer?: string | null
  updated_at?: string | null
}

export interface SettingsUpdatePayload {
  bot_name?: string
  system_prompt?: string
  model_id?: number | null
  knowledge_base_ids?: number[]
  search_mode?: string
  top_k?: number
  score_threshold?: number
  enable_rerank?: boolean
  temperature?: number
  max_tokens?: number
  history_turns?: number
  human_intents?: string[]
  human_keywords?: string[]
  low_confidence_threshold?: number
  low_confidence_streak?: number
  fallback_answer?: string
}

// ---------------- 快捷话术 ----------------

export interface QuickReply {
  id: number
  title: string
  content: string
  category: string
  sort_order: number
  created_at: string
  updated_at: string
}

export interface QuickReplyCreatePayload {
  title: string
  content: string
  category?: string
  sort_order?: number
}

// ---------------- 统计 ----------------

export interface AnalyticsOverview {
  session_total: number
  session_open: number
  session_pending_human: number
  session_resolved: number
  ai_resolve_rate: number
  unresolved_rate: number
  avg_satisfaction: number
  ticket_total: number
  ticket_pending: number
  ticket_overdue: number
  message_total: number
}

export interface TrendPoint {
  date: string
  session_count: number
  message_count: number
  ticket_count: number
}

export interface IntentStatItem {
  intent: string
  label: string
  count: number
  percent: number
}

export interface SatisfactionStatItem {
  score: number
  count: number
}

export interface TicketStatItem {
  status: string
  label: string
  count: number
}

export interface AnalyticsResponse {
  days: number
  overview: AnalyticsOverview
  trend: TrendPoint[]
  intents: IntentStatItem[]
  satisfaction: SatisfactionStatItem[]
  tickets: TicketStatItem[]
}

// ---------------- SSE 回调 ----------------

export interface ChatStreamCallbacks {
  onReferences?: (payload: {
    references: SupportReference[]
    intent: string
    intent_label: string
    confidence: number
    suggest_human: boolean
  }) => void
  onDelta?: (content: string) => void
  onThought?: (payload: AgentTraceStep) => void
  onToolCall?: (payload: AgentToolCall) => void
  onTicket?: (payload: AgentTicketInfo) => void
  onDone?: (payload: { message_id: number; suggest_human: boolean; latency_ms: number }) => void
  onError?: (detail: string) => void
}

// ---------------- Agent 过程可视化 ----------------

export interface AgentTraceStep {
  node: string
  summary: string
  duration_ms?: number
  model?: string
  tokens?: number | Record<string, number> | null
  input?: any
  output?: any
}

export interface AgentToolCall {
  name: string
  arguments: Record<string, any>
  result: string
  success: boolean
}

export interface AgentTicketInfo {
  id?: number
  ticket_no: string
  type: string
  type_label?: string
  priority: string
  priority_label?: string
  title: string
  description?: string
  status?: string
  status_label?: string
}

export interface SupportMessageTrace {
  steps: AgentTraceStep[]
  tool_calls: AgentToolCall[]
  ticket?: AgentTicketInfo | null
  references?: {
    references: SupportReference[]
    intent: string
    intent_label: string
    confidence: number
    suggest_human: boolean
  } | null
}

// ---------------- 业务数据（Demo 示例） ----------------

export interface BusinessOrder {
  id: number
  order_no: string
  customer_name: string
  product: string
  amount: number
  status: string
  ordered_at?: string | null
}

export interface BusinessProduct {
  id: number
  product_no: string
  name: string
  price: number
  warranty?: string | null
  category?: string | null
  category_label: string
  description?: string | null
  features: string[]
}

export interface BusinessShipment {
  id: number
  order_no: string
  carrier?: string | null
  tracking_no?: string | null
  current_location?: string | null
  estimated_text?: string | null
  status?: string | null
}

export interface BusinessReturnPolicy {
  id: number
  category: string
  category_label: string
  policy_content: string
}

export interface BusinessData {
  orders: BusinessOrder[]
  products: BusinessProduct[]
  shipments: BusinessShipment[]
  return_policies: BusinessReturnPolicy[]
}

// ---------------- 评测（自动 + 人工） ----------------

export type EvalStatus = 'pending' | 'auto' | 'done'

export interface SupportEvaluation {
  id: number
  message_id: number
  session_id: number
  query?: string | null
  intent?: string | null
  intent_label: string
  auto_scores?: Record<string, number> | null
  auto_overall?: number | null
  auto_reasoning?: string | null
  // DeepEval 自动评测原始结果（当前自动分来源）
  deepeval_scores?: Record<string, number> | null
  deepeval_overall?: number | null
  deepeval_reasoning?: string | null
  manual_scores?: Record<string, number> | null
  manual_overall?: number | null
  annotator_id?: number | null
  annotator_name: string
  comment?: string | null
  status: EvalStatus
  ai_content: string
  created_at: string
  updated_at: string
}

export interface ManualScorePayload {
  message_id: number
  accuracy: number
  helpfulness: number
  safety: number
  fluency: number
  comment?: string
}

export interface ManualScoreResponse {
  ok: boolean
  message_id: number
  status: string
  manual_overall?: number | null
}

export interface EvalQueueItem {
  message_id: number
  session_id: number
  query?: string | null
  ai_preview: string
  intent?: string | null
  intent_label: string
  auto_overall?: number | null
  status: EvalStatus
  created_at: string
}

export interface EvalQueueResponse {
  items: EvalQueueItem[]
  meta: PageMeta
}

export interface QualityOverview {
  total: number
  auto_count: number
  manual_count: number
  pending_count: number
  auto_avg?: number | null
  manual_avg?: number | null
  annotated_rate: number
}

export interface QualityTrendPoint {
  date: string
  count: number
  auto_avg?: number | null
  manual_avg?: number | null
}

export interface QualityIntentItem {
  intent: string
  label: string
  count: number
  auto_avg?: number | null
  manual_avg?: number | null
}

export interface QualitySummaryResponse {
  days: number
  overview: QualityOverview
  trend: QualityTrendPoint[]
  by_intent: QualityIntentItem[]
}

export interface GenerateKbDocsResponse {
  ok: boolean
  knowledge_base_id: number
  knowledge_base_name: string
  documents: { document_id?: number; name: string; status: string; chunk_count?: number; ok?: boolean }[]
  message: string
}
