/**
 * 学习助手 API 客户端
 *
 * 与后端 /api/v1/learning 下的端点一一对应。
 */

import api from './api'
import { useAuthStore } from '@/stores/auth'
import {
  AnnotationShape,
  ChatHistoryResponse,
  ChatStreamCallbacks,
  ChatStreamParams,
  ClearHistoryResponse,
  DocumentMeta,
  DocumentPage,
  LearningNote,
  LearningResource,
  NoteTimelineResponse,
  PageOptionListResponse,
  ProgressReportPayload,
  ProgressResponse,
  RecordResourceItem,
  RecordSessionItem,
  ResourceListResponse,
  StatsResponse,
  SuggestedQuestionsResponse,
  TranscriptResponse,
} from '../types/learning'

const BASE = '/learning'

export interface ListResourcesParams {
  type?: string
  keyword?: string
  sort?: 'recent_studied' | 'recent_created' | 'progress'
  cursor?: number | null
  limit?: number
}

export const learningApi = {
  // ---------------- 资源 ----------------

  listResources(params: ListResourcesParams): Promise<ResourceListResponse> {
    return api.get(`${BASE}/resources`, { params }).then((res) => res.data)
  },

  getResource(resourceId: number): Promise<LearningResource> {
    return api.get(`${BASE}/resources/${resourceId}`).then((res) => res.data)
  },

  importUrl(url: string, languages?: string[]): Promise<LearningResource> {
    return api
      .post(`${BASE}/resources/url`, { url, languages })
      .then((res) => res.data)
  },

  uploadDocument(
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<LearningResource> {
    const form = new FormData()
    form.append('file', file)
    return api
      .post(`${BASE}/resources/document`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 180000,
        onUploadProgress: (event) => {
          if (!onProgress || !event.total) return
          onProgress(Math.round((event.loaded / event.total) * 100))
        },
      })
      .then((res) => res.data)
  },

  updateResource(
    resourceId: number,
    data: { title?: string; description?: string }
  ): Promise<LearningResource> {
    return api.patch(`${BASE}/resources/${resourceId}`, data).then((res) => res.data)
  },

  deleteResource(resourceId: number): Promise<void> {
    return api.delete(`${BASE}/resources/${resourceId}`).then(() => undefined)
  },

  // ---------------- 字幕 ----------------

  getTranscripts(
    resourceId: number,
    language?: string
  ): Promise<TranscriptResponse> {
    return api
      .get(`${BASE}/resources/${resourceId}/transcripts`, { params: { language } })
      .then((res) => res.data)
  },

  uploadSubtitle(
    resourceId: number,
    file: File,
    language = 'manual'
  ): Promise<{ resource_id: number; count: number; language: string }> {
    const form = new FormData()
    form.append('file', file)
    form.append('language', language)
    return api
      .post(`${BASE}/resources/${resourceId}/transcripts/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((res) => res.data)
  },

  // ---------------- 文档 ----------------

  /** PDF 原文件：pdfjs 需要字节流，鉴权后转 blob URL 交给渲染器 */
  async fetchDocumentBlob(resourceId: number): Promise<string> {
    const res = await api.get(`${BASE}/resources/${resourceId}/file`, {
      responseType: 'blob',
    })
    return URL.createObjectURL(res.data)
  },

  getDocumentMeta(resourceId: number): Promise<DocumentMeta> {
    return api.get(`${BASE}/resources/${resourceId}/meta`).then((res) => res.data)
  },

  getDocumentPage(resourceId: number, pageIndex: number): Promise<DocumentPage> {
    return api
      .get(`${BASE}/resources/${resourceId}/pages/${pageIndex}`)
      .then((res) => res.data)
  },

  // ---------------- 笔记 ----------------

  listNotes(
    resourceId: number,
    kind?: string,
    pageIndex?: number
  ): Promise<LearningNote[]> {
    return api
      .get(`${BASE}/resources/${resourceId}/notes`, {
        params: { kind, page_index: pageIndex },
      })
      .then((res) => res.data)
  },

  getDrawPage(resourceId: number, pageIndex: number): Promise<{ shapes: AnnotationShape[] }> {
    return api
      .get(`${BASE}/resources/${resourceId}/notes/draw`, { params: { page_index: pageIndex } })
      .then((res) => res.data)
  },

  saveDrawPage(
    resourceId: number,
    pageIndex: number,
    shapes: AnnotationShape[]
  ): Promise<{ shapes: AnnotationShape[] }> {
    return api
      .post(
        `${BASE}/resources/${resourceId}/notes/draw`,
        { shapes },
        { params: { page_index: pageIndex } }
      )
      .then((res) => res.data)
  },

  createTextNote(payload: {
    resource_id: number
    content: string
    x: number
    y: number
    page_index?: number | null
    position_ms?: number | null
    color: string
  }): Promise<LearningNote> {
    return api
      .post(`${BASE}/resources/${payload.resource_id}/notes/text`, payload)
      .then((res) => res.data)
  },

  createExportNote(payload: {
    resource_id: number
    page_index: number
    image_base64: string
    note?: string
    width?: number
    height?: number
  }): Promise<LearningNote> {
    return api
      .post(`${BASE}/resources/${payload.resource_id}/notes/export`, payload, {
        timeout: 120000,
      })
      .then((res) => res.data)
  },

  updateNote(
    noteId: number,
    data: { content?: string; color?: string; x?: number; y?: number }
  ): Promise<LearningNote> {
    return api.patch(`${BASE}/notes/${noteId}`, data).then((res) => res.data)
  },

  deleteNote(noteId: number): Promise<void> {
    return api.delete(`${BASE}/notes/${noteId}`).then(() => undefined)
  },

  listNoteTimeline(params: {
    kind?: string
    cursor?: number | null
    limit?: number
  }): Promise<NoteTimelineResponse> {
    return api.get(`${BASE}/notes/timeline`, { params }).then((res) => res.data)
  },

  // ---------------- 进度与会话 ----------------

  reportProgress(
    resourceId: number,
    payload: ProgressReportPayload
  ): Promise<ProgressResponse> {
    return api
      .post(`${BASE}/resources/${resourceId}/progress`, payload)
      .then((res) => res.data)
  },

  closeSession(resourceId: number): Promise<void> {
    return api
      .post(`${BASE}/resources/${resourceId}/progress/close`)
      .then(() => undefined)
  },

  listSessions(resourceId: number, limit = 20): Promise<RecordSessionItem[]> {
    return api
      .get(`${BASE}/resources/${resourceId}/sessions`, { params: { limit } })
      .then((res) => res.data)
  },

  // ---------------- 记录与统计 ----------------

  listRecords(limit = 50): Promise<RecordResourceItem[]> {
    return api.get(`${BASE}/records`, { params: { limit } }).then((res) => res.data)
  },

  getStats(heatmapDays = 182): Promise<StatsResponse> {
    return api.get(`${BASE}/stats`, { params: { heatmap_days: heatmapDays } }).then((res) => res.data)
  },

  /** 资源附属图片（导出图/文档内联图）：需带鉴权头，故取 blob 后转本地 URL */
  async fetchAssetBlob(resourceId: number, name: string): Promise<string> {
    const res = await api.get(`${BASE}/assets/${resourceId}/${name}`, {
      responseType: 'blob',
    })
    return URL.createObjectURL(res.data)
  },

  /**
   * 按完整 URL 取资源图片（文档正文里的图片链接）
   *
   * 传入的是后端拼好的 `/api/v1/learning/assets/...`，需剥掉 baseURL 前缀，
   * 否则 axios 会拼成 `/api/v1/api/v1/...`。
   */
  async fetchAssetByUrl(url: string): Promise<string> {
    const path = url.startsWith('/api/v1') ? url.slice('/api/v1'.length) : url
    const res = await api.get(path, { responseType: 'blob' })
    return URL.createObjectURL(res.data)
  },

  // ---------------- AI 问答 ----------------

  getChatHistory(resourceId: number, limit = 100): Promise<ChatHistoryResponse> {
    return api
      .get(`${BASE}/resources/${resourceId}/chat/messages`, { params: { limit } })
      .then((res) => res.data)
  },

  clearChatHistory(resourceId: number): Promise<ClearHistoryResponse> {
    return api
      .delete(`${BASE}/resources/${resourceId}/chat/messages`)
      .then((res) => res.data)
  },

  getSuggestedQuestions(resourceId: number): Promise<SuggestedQuestionsResponse> {
    return api
      .get(`${BASE}/resources/${resourceId}/chat/suggestions`)
      .then((res) => res.data)
  },

  /** 文档分页列表：供 @ 选择器挑选要加入上下文的页 */
  getPageList(resourceId: number): Promise<PageOptionListResponse> {
    return api.get(`${BASE}/resources/${resourceId}/pages`).then((res) => res.data)
  },

  /**
   * AI 问答流式请求（SSE）
   *
   * 不用 EventSource：它需要把 token 拼在 URL 上，且无法自定义 method/body。
   * 这里走 fetch + ReadableStream 手动解析 SSE，返回 AbortController 供「停止生成」。
   */
  chatStream(params: ChatStreamParams, callbacks: ChatStreamCallbacks): AbortController {
    const controller = new AbortController()
    // token 在 Zustand store 里（与 api.ts 的拦截器同源）。
    // 这里不能读 localStorage：store 未必以 'token' 为 key 落盘，读空就等于没带鉴权头 → 401。
    const token = useAuthStore.getState().token

    const handleEvent = (raw: string) => {
      // 单个事件的原始文本：可选的 event: 行 + data: 行
      let eventName = 'message'
      const dataLines: string[] = []
      for (const line of raw.split('\n')) {
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim()
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim())
        }
      }
      if (!dataLines.length) return
      let payload: any = {}
      try {
        payload = JSON.parse(dataLines.join(''))
      } catch {
        return
      }
      if (eventName === 'references') callbacks.onReferences?.(payload.references || [])
      else if (eventName === 'delta') callbacks.onDelta?.(payload.content || '')
      else if (eventName === 'done') callbacks.onDone?.(payload)
      else if (eventName === 'error') callbacks.onError?.(payload.detail || '未知错误')
    }

    const run = async () => {
      const res = await fetch(`/api/v1${BASE}/resources/${params.resourceId}/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: params.query,
          position: params.position,
          model_id: params.modelId ?? null,
          context_refs: params.contextRefs ?? [],
        }),
        signal: controller.signal,
      })

      if (res.status === 401) {
        // fetch 不走 axios 的响应拦截器，这里手动复刻登出行为，避免停留在过期态
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

    run().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      callbacks.onError?.(error instanceof Error ? error.message : '网络异常')
    })

    return controller
  },
}

export default learningApi
