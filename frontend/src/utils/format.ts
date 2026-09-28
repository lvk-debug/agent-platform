/**
 * 学习模块的展示格式化工具
 */

/** 毫秒 → mm:ss 或 hh:mm:ss */
export const formatClock = (ms: number): string => {
  const totalSeconds = Math.max(Math.floor(ms / 1000), 0)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (value: number) => String(value).padStart(2, '0')
  return hours > 0
    ? `${hours}:${pad(minutes)}:${pad(seconds)}`
    : `${pad(minutes)}:${pad(seconds)}`
}

/** 秒 → 「1 小时 20 分」 */
export const formatDuration = (seconds: number): string => {
  if (seconds <= 0) return '尚未学习'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours} 小时 ${minutes} 分`
  if (minutes > 0) return `${minutes} 分钟`
  return `${seconds} 秒`
}

/** 秒 → 视频角标用的 mm:ss */
export const formatVideoBadge = (seconds: number): string => formatClock(seconds * 1000)

/** 相对时间：3 分钟前 / 昨天 / 2026-04-01 */
export const formatRelativeTime = (iso: string | null | undefined): string => {
  if (!iso) return '未学习'
  const timestamp = new Date(iso).getTime()
  if (Number.isNaN(timestamp)) return '未学习'

  const diffSeconds = Math.floor((Date.now() - timestamp) / 1000)
  if (diffSeconds < 60) return '刚刚'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)} 分钟前`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)} 小时前`
  if (diffSeconds < 172800) return '昨天'

  const date = new Date(timestamp)
  const sameYear = date.getFullYear() === new Date().getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return sameYear ? `${month}-${day}` : `${date.getFullYear()}-${month}-${day}`
}

/** 文档格式 → 标签配色 */
export const FILE_TYPE_META: Record<string, { label: string; color: string }> = {
  pdf: { label: 'PDF', color: '#EF4444' },
  pptx: { label: 'PPTX', color: '#F59E0B' },
  epub: { label: 'EPUB', color: '#10B981' },
  markdown: { label: 'MD', color: '#6366F1' },
}

/** 平台来源 → 展示名 */
export const SOURCE_LABEL: Record<string, string> = {
  youtube: 'YouTube',
  bilibili: '哔哩哔哩',
  upload: '本地上传',
}
