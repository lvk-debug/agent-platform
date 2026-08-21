import api from './api'
import { CursorParams, CursorResponse } from '../types/pagination'

export interface AppData {
  id: number
  name: string
  description?: string
  app_type: 'chatbot' | 'workflow' | 'agent'
  icon?: string
  status: 'draft' | 'published' | 'disabled'
  config?: Record<string, any>
  version: number
  created_at: string
  updated_at: string
  published_at?: string
}

export interface CreateAppData {
  name: string
  description?: string
  app_type: 'chatbot' | 'workflow' | 'agent'
  icon?: string
  config?: Record<string, any>
}

export interface UpdateAppData {
  name?: string
  description?: string
  icon?: string
  config?: Record<string, any>
  status?: 'draft' | 'published' | 'disabled'
}

export const appsApi = {
  // 获取应用列表（游标分页）
  getApps: (params?: CursorParams & {
    app_type?: string
    status?: string
  }) => {
    return api.get<CursorResponse<AppData>>('/apps/', { params })
  },

  // 获取应用详情
  getApp: (id: number) => {
    return api.get<AppData>(`/apps/${id}`)
  },

  // 创建应用
  createApp: (data: CreateAppData) => {
    return api.post<AppData>('/apps/', data)
  },

  // 更新应用
  updateApp: (id: number, data: UpdateAppData) => {
    return api.put<AppData>(`/apps/${id}`, data)
  },

  // 删除应用
  deleteApp: (id: number) => {
    return api.delete(`/apps/${id}`)
  },

  // 发布应用
  publishApp: (id: number) => {
    return api.post<AppData>(`/apps/${id}/publish`)
  },

  // 获取应用会话列表
  getConversations: (appId: number, params?: { limit?: number; offset?: number }) => {
    return api.get(`/apps/${appId}/conversations`, { params })
  },

  // 获取会话消息列表
  getMessages: (appId: number, conversationId: number) => {
    return api.get(`/apps/${appId}/conversations/${conversationId}/messages`)
  },
}
