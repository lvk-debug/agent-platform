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

export interface ToolTemplate {
  id: string
  name: string
  description: string
  category: string
  icon: string
  tool_type: string
}

export interface ToolCategory {
  id: string
  name: string
  icon: string
}

export interface ToolTestResult {
  success: boolean
  output?: any
  error?: string
  duration_ms: number
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

  // ============ 模板 / 安装 / MCP 导入 ============

  // 获取工具模板列表
  getTemplates: () => {
    return api.get<ToolTemplate[]>('/tools/templates')
  },

  // 获取工具分类
  getCategories: () => {
    return api.get<ToolCategory[]>('/tools/templates/categories')
  },

  // 从模板安装工具
  installFromTemplate: (templateId: string) => {
    return api.post<ToolData>(`/tools/install/${templateId}`)
  },

  // 从 MCP Server 导入工具
  importMcp: (url: string) => {
    return api.post<ToolData[]>('/tools/import/mcp', { url })
  },

  // 测试工具执行
  testTool: (id: number, inputData: Record<string, any> = {}, timeout: number = 30) => {
    return api.post<ToolTestResult>(`/tools/${id}/test`, {
      input_data: inputData,
      timeout,
    })
  },
}
