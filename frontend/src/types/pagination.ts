/**
 * 游标分页请求参数
 */
export interface CursorParams {
  cursor?: number
  limit?: number
}

/**
 * 游标分页响应
 */
export interface CursorResponse<T> {
  items: T[]
  next_cursor: number | null
  has_more: boolean
}
