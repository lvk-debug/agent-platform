/**
 * 学习助手前端类型定义
 *
 * 与后端 app/schemas/learning.py 保持字段一致。
 */

export type ResourceType = 'video' | 'document'
export type ResourceSource = 'youtube' | 'bilibili' | 'upload'
export type ResourceStatus = 'pending' | 'ready' | 'failed' | 'no_subtitle'
export type DocFileType = 'pdf' | 'pptx' | 'epub' | 'markdown'
export type NoteKind = 'draw' | 'text' | 'export'

/** 字幕语言轨道 */
export interface SubtitleTrack {
  lang: string
  name: string
  source: string
  /** 是否为视频原文语言轨道（双语展示时它作为原文那一行） */
  is_original: boolean
}

/** 学习资源 */
export interface LearningResource {
  id: number
  user_id: number
  type: ResourceType
  source: ResourceSource
  title: string
  description: string
  cover_url: string | null
  source_url: string | null
  file_type: DocFileType | null
  file_size: number | null
  page_count: number
  duration_seconds: number
  platform_id: string | null
  subtitle_tracks: SubtitleTrack[] | null
  status: ResourceStatus
  error_message: string | null
  created_at: string
  updated_at: string
  progress_percent: number
  total_seconds: number
  note_count: number
  last_studied_at: string | null
}

/** 资源列表（游标分页） */
export interface ResourceListResponse {
  items: LearningResource[]
  next_cursor: number | null
  has_more: boolean
}

/** 字幕片段 */
export interface TranscriptCue {
  id: number
  seq: number
  start_ms: number
  end_ms: number
  text: string
  language: string
  source: string
  /** 时间对齐的译文（双语展示的副行），空串表示暂无译文 */
  translation: string
}

export interface TranscriptResponse {
  resource_id: number
  language: string
  cues: TranscriptCue[]
  tracks: SubtitleTrack[]
}

/** PPTX 结构化区块 */
export interface PageBlock {
  kind: 'text' | 'image' | 'table'
  text?: string
  src?: string
  x: number
  y: number
  w: number
  h: number
  style?: Record<string, any>
}

/** 文档单页 */
export interface DocumentPage {
  resource_id: number
  file_type: DocFileType
  page_count: number
  page_index: number
  width: number
  height: number
  title: string
  html: string
  raw: string
  blocks: PageBlock[]
}

export interface DocumentOutlineItem {
  title: string
  page_index: number
}

export interface DocumentMeta {
  resource_id: number
  file_type: DocFileType
  page_count: number
  outline: DocumentOutlineItem[]
}

// ------------------------------------------------------------------
// 矢量标注
// ------------------------------------------------------------------

export type AnnotationTool = 'pen' | 'highlighter' | 'arrow' | 'rect' | 'ellipse' | 'text'

/**
 * 画布交互模式（互斥）：
 * - browse 预览：不接管指针，文档可正常滚动、选择文字
 * - draw   画笔：拖拽绘制笔迹/图形；点已有贴纸=选中
 * - text   文本贴纸：点空白=新建；点已有贴纸=选中（不新建）
 *
 * 文本独立成模式而非 draw 下的工具：它的单击语义是"新建"，
 * 与"选中已有贴纸"天然冲突，必须用模式把两者分开。
 */
export type CanvasMode = 'browse' | 'draw' | 'text'

export interface AnnotationPoint {
  x: number
  y: number
}

/** 单个矢量图形，坐标为 0~1 归一化值 */
export interface AnnotationShape {
  id: string
  tool: AnnotationTool
  color: string
  strokeWidth: number
  opacity: number
  points: AnnotationPoint[]
  /** 文本标注的正文（tool === 'text' 时使用，points[0] 为锚点） */
  text?: string
  /** 贴纸旋转角度（度） */
  rotation?: number
  /** 贴纸缩放，默认 1 */
  scaleX?: number
  scaleY?: number
  createdAt: string
}

// ------------------------------------------------------------------
// 笔记
// ------------------------------------------------------------------

export interface LearningNote {
  id: number
  resource_id: number
  kind: NoteKind
  page_index: number | null
  position_ms: number | null
  content: string | null
  payload: Record<string, any> | null
  file_url: string | null
  created_at: string
  updated_at: string
}

export interface DrawPageResponse {
  resource_id: number
  page_index: number
  shapes: AnnotationShape[]
}

export interface TextNotePayload {
  resource_id: number
  content: string
  x: number
  y: number
  page_index?: number | null
  position_ms?: number | null
  color: string
}

// ------------------------------------------------------------------
// 进度与记录
// ------------------------------------------------------------------

export interface ProgressReportPayload {
  position: number
  delta_seconds: number
  client_seq: number
  is_finished: boolean
}

export interface ProgressResponse {
  resource_id: number
  position: number
  total_seconds: number
  is_finished: boolean
  percent: number
  updated_at: string | null
}

export interface RecordSessionItem {
  id: number
  started_at: string
  ended_at: string | null
  seconds: number
  start_position: number
  end_position: number
}

export interface RecordResourceItem {
  resource_id: number
  title: string
  type: ResourceType
  source: ResourceSource
  cover_url: string | null
  percent: number
  total_seconds: number
  note_count: number
  last_studied_at: string | null
  is_finished: boolean
  /** AI 问答：提问条数与最近一条提问 */
  qa_count: number
  last_question: string | null
}

export interface HeatmapPoint {
  date: string
  seconds: number
  resource_count: number
  note_count: number
}

export interface WeekdayDistribution {
  weekday: number
  seconds: number
}

export interface StatsOverview {
  week_seconds: number
  week_delta_percent: number
  streak_days: number
  finished_count: number
  note_count: number
  total_seconds: number
}

export interface StatsResponse {
  overview: StatsOverview
  heatmap: HeatmapPoint[]
  weekday_distribution: WeekdayDistribution[]
}

export interface NoteTimelineItem {
  id: number
  resource_id: number
  resource_title: string
  resource_type: ResourceType
  kind: NoteKind
  page_index: number | null
  position_ms: number | null
  content: string | null
  file_url: string | null
  preview_color: string
  created_at: string
}

export interface NoteTimelineResponse {
  items: NoteTimelineItem[]
  next_cursor: number | null
  has_more: boolean
}

// ------------------------------------------------------------------
// AI 问答
// ------------------------------------------------------------------

export type LearningReferenceType = 'page' | 'transcript'

/** 引用来源：文档用页码定位，视频用时间戳定位，点击可跳回原文 */
export interface LearningReference {
  type: LearningReferenceType
  page_index: number | null
  start_ms: number | null
  end_ms: number | null
  title: string
  snippet: string
  score: number
  /** 是否是用户手动 @ 指定的片段（回看历史时可据此高亮） */
  is_pinned?: boolean
}

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: number
  role: ChatRole
  content: string
  references: LearningReference[]
  model: string | null
  error: string | null
  created_at: string
}

export interface ChatHistoryResponse {
  resource_id: number
  messages: ChatMessage[]
}

export interface SuggestedQuestionsResponse {
  resource_id: number
  questions: string[]
}

export interface ClearHistoryResponse {
  deleted: number
}

/**
 * 手动指定的上下文引用（@ 添加）
 *
 * 与 LearningReference 方向相反：后者是回答产生的引用（输出），
 * 这个是用户圈定的输入范围。
 */
export interface ContextRef {
  type: 'page' | 'transcript'
  page_index: number | null
  start_ms: number | null
  end_ms: number | null
}

export interface PageOption {
  page_index: number
  title: string
}

export interface PageOptionListResponse {
  resource_id: number
  items: PageOption[]
}

export interface ChatStreamParams {
  resourceId: number
  query: string
  /** 当前位置：文档为页码，视频为秒 */
  position: number
  modelId?: number | null
  /** 用户手动 @ 的上下文，强制进入并排在最前 */
  contextRefs?: ContextRef[]
}

export interface ChatStreamCallbacks {
  /** 引用来源先于答案返回，可提前渲染、边生成边跳转 */
  onReferences?: (references: LearningReference[]) => void
  onDelta?: (content: string) => void
  onDone?: (payload: { message_id: number; latency_ms: number }) => void
  onError?: (detail: string) => void
}
