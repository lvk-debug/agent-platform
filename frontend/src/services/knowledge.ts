import api from './api'
import { CursorParams, CursorResponse } from '../types/pagination'

export interface KnowledgeBaseData {
  id: number
  name: string
  description?: string
  kb_type: 'local' | 'external'
  status: 'active' | 'inactive' | 'processing'
  document_count: number
  chunk_count: number
  created_at: string
  updated_at: string
}

export interface CreateKnowledgeBaseData {
  name: string
  description?: string
  kb_type: 'local' | 'external'
  api_endpoint?: string
  api_key?: string
  api_config?: Record<string, any>
}

export interface UpdateKnowledgeBaseData {
  name?: string
  description?: string
  api_endpoint?: string
  api_key?: string
  api_config?: Record<string, any>
}

export interface DocumentData {
  id: number
  knowledge_base_id: number
  name: string
  file_type: string
  file_size?: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  error_message?: string
  created_at: string
  processed_at?: string
}

export interface DocumentSegmentData {
  id: number
  document_id: number
  content: string
  token_count?: number
  position: number
  metadata_?: Record<string, any>
  created_at: string
}

export interface SearchResultItem {
  segment_id: number
  document_id: number
  document_name: string
  content: string
  score: number
  metadata?: Record<string, any>
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
  total: number
}

export const knowledgeApi = {
  // 获取知识库列表（游标分页）
  getKnowledgeBases: (params?: CursorParams) => {
    return api.get<CursorResponse<KnowledgeBaseData>>('/knowledge/', { params })
  },

  // 获取知识库详情
  getKnowledgeBase: (id: number) => {
    return api.get<KnowledgeBaseData>(`/knowledge/${id}`)
  },

  // 创建知识库
  createKnowledgeBase: (data: CreateKnowledgeBaseData) => {
    return api.post<KnowledgeBaseData>('/knowledge/', data)
  },

  // 更新知识库
  updateKnowledgeBase: (id: number, data: UpdateKnowledgeBaseData) => {
    return api.put<KnowledgeBaseData>(`/knowledge/${id}`, data)
  },

  // 删除知识库
  deleteKnowledgeBase: (id: number) => {
    return api.delete(`/knowledge/${id}`)
  },

  // 上传文档
  uploadDocument: (kbId: number, file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post<DocumentData>(`/knowledge/${kbId}/documents`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  // 获取文档列表（游标分页）
  getDocuments: (kbId: number, params?: CursorParams) => {
    return api.get<CursorResponse<DocumentData>>(`/knowledge/${kbId}/documents`, { params })
  },

  // 删除文档
  deleteDocument: (kbId: number, docId: number) => {
    return api.delete(`/knowledge/${kbId}/documents/${docId}`)
  },

  // 获取文档分段列表（游标分页）
  getSegments: (kbId: number, docId: number, params?: CursorParams) => {
    return api.get<CursorResponse<DocumentSegmentData>>(`/knowledge/${kbId}/documents/${docId}/segments`, { params })
  },

  // 重新处理文档
  retryDocument: (kbId: number, docId: number) => {
    return api.post(`/knowledge/${kbId}/documents/${docId}/retry`)
  },

  // 知识库检索
  searchKnowledgeBase: (kbId: number, query: string, top_k?: number, score_threshold?: number) => {
    return api.post<SearchResponse>(`/knowledge/${kbId}/search`, {
      query,
      top_k: top_k ?? 5,
      score_threshold: score_threshold ?? 0,
    })
  },
}
