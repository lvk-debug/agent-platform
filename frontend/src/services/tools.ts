import api from './api'

export interface ToolData {
  id: number
  name: string
  description?: string
  tool_type: 'builtin' | 'plugin' | 'mcp'
  icon?: string
  parameters_schema?: Record<string, any>
  return_schema?: Record<string, any>
  endpoint?: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CreateToolData {
  name: string
  description?: string
  tool_type: 'builtin' | 'plugin' | 'mcp'
  icon?: string
  parameters_schema?: Record<string, any>
  return_schema?: Record<string, any>
  endpoint?: string
  auth_config?: Record<string, any>
}

export interface UpdateToolData {
  name?: string
  description?: string
  icon?: string
  parameters_schema?: Record<string, any>
  return_schema?: Record<string, any>
  endpoint?: string
  auth_config?: Record<string, any>
  is_active?: boolean
}

export const toolsApi = {
  // 获取工具列表
  getTools: () => {
    return api.get<ToolData[]>('/tools/')
  },

  // 获取工具详情
  getTool: (id: number) => {
    return api.get<ToolData>(`/tools/${id}`)
  },

  // 创建工具
  createTool: (data: CreateToolData) => {
    return api.post<ToolData>('/tools/', data)
  },

  // 更新工具
  updateTool: (id: number, data: UpdateToolData) => {
    return api.put<ToolData>(`/tools/${id}`, data)
  },

  // 删除工具
  deleteTool: (id: number) => {
    return api.delete(`/tools/${id}`)
  },
}
