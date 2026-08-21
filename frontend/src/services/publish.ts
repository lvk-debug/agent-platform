import api from './api'

export type PublishChannel = 'api' | 'mcp' | 'embed' | 'wechat' | 'h5'

export interface PublishConfig {
  channel: PublishChannel
  enabled: boolean
  config?: Record<string, any>
  api_key?: string
  api_endpoint?: string
  mcp_config?: Record<string, any>
  mcp_command?: string
  embed_code?: string
  embed_url?: string
  wechat_webhook_url?: string
  wechat_guide?: Array<{ step: string; title: string; description: string }>
  h5_url?: string
  created_at?: string
  updated_at?: string
}

export interface PublishConfigListResponse {
  app_id: number
  app_name: string
  configs: PublishConfig[]
}

export const publishApi = {
  // 获取所有渠道配置
  getAll: (appId: number) => {
    return api.get<PublishConfigListResponse>(`/apps/${appId}/publish`)
  },

  // 获取单个渠道配置
  getOne: (appId: number, channel: PublishChannel) => {
    return api.get<PublishConfig>(`/apps/${appId}/publish/${channel}`)
  },

  // 更新渠道配置
  update: (appId: number, channel: PublishChannel, data: { enabled?: boolean; config?: Record<string, any> }) => {
    return api.put<PublishConfig>(`/apps/${appId}/publish/${channel}`, data)
  },

  // 启用渠道
  enable: (appId: number, channel: PublishChannel) => {
    return api.post<PublishConfig>(`/apps/${appId}/publish/${channel}/enable`)
  },

  // 禁用渠道
  disable: (appId: number, channel: PublishChannel) => {
    return api.post<PublishConfig>(`/apps/${appId}/publish/${channel}/disable`)
  },
}
