import api from './api'

export interface ModelProviderData {
  id: number
  name: string
  provider_type: 'openai' | 'anthropic' | 'local' | 'custom'
  api_endpoint?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateModelProviderData {
  name: string
  provider_type: 'openai' | 'anthropic' | 'local' | 'custom'
  api_endpoint?: string
  api_key?: string
  api_config?: Record<string, any>
}

export interface UpdateModelProviderData {
  name?: string
  api_endpoint?: string
  api_key?: string
  api_config?: Record<string, any>
  is_active?: boolean
}

export interface ModelData {
  id: number
  provider_id: number
  name: string
  model_id: string
  description?: string
  max_tokens?: number
  supports_streaming: boolean
  supports_function_calling: boolean
  default_temperature: number
  default_max_tokens: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export const modelsApi = {
  // 获取模型供应商列表
  getProviders: () => {
    return api.get<ModelProviderData[]>('/models/providers')
  },

  // 获取供应商详情
  getProvider: (id: number) => {
    return api.get<ModelProviderData>(`/models/providers/${id}`)
  },

  // 创建供应商
  createProvider: (data: CreateModelProviderData) => {
    return api.post<ModelProviderData>('/models/providers', data)
  },

  // 更新供应商
  updateProvider: (id: number, data: UpdateModelProviderData) => {
    return api.put<ModelProviderData>(`/models/providers/${id}`, data)
  },

  // 获取供应商下的模型列表
  getModels: (providerId: number) => {
    return api.get<ModelData[]>(`/models/providers/${providerId}/models`)
  },

  // 获取所有可用模型
  getAllModels: () => {
    return api.get<ModelData[]>('/models/')
  },
}
