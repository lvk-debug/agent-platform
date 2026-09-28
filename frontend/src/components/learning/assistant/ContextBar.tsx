/**
 * 上下文标签条
 *
 * 展示本次提问会携带的资源范围：文档为页码、视频为时间戳。
 * 自动带入的「当前位置」同样是一个可删除的标签——把它交还给用户，
 * 而不是悄悄塞进 prompt。
 */

import React from 'react'
import { AtSign, FileText, X } from 'lucide-react'
import type { ContextRef, LearningResource } from '../../../types/learning'
import { formatClock } from '../../../utils/format'

interface ContextBarProps {
  resource: LearningResource
  refs: ContextRef[]
  onRemove: (ref: ContextRef) => void
  onAdd: () => void
}

export const refKey = (ref: ContextRef): string =>
  `${ref.type}-${ref.page_index ?? ref.start_ms ?? 0}`

const refLabel = (ref: ContextRef): string => {
  if (ref.type === 'page') return `第 ${(ref.page_index ?? 0) + 1} 页`
  const start = formatClock(ref.start_ms ?? 0)
  // 单句字幕的时间跨度很短，只在区间有意义时才展示结束时间
  if (ref.end_ms != null && ref.end_ms - (ref.start_ms ?? 0) >= 1000) {
    return `${start} - ${formatClock(ref.end_ms)}`
  }
  return start
}

const ContextBar: React.FC<ContextBarProps> = ({ resource, refs, onRemove, onAdd }) => (
  <div className="flex flex-wrap items-center gap-1.5">
    <span className="flex max-w-[130px] items-center gap-1 text-xs text-slate-400">
      <FileText size={12} className="shrink-0" />
      <span className="truncate">{resource.title}</span>
    </span>

    {refs.map((ref) => (
      <span
        key={refKey(ref)}
        className="inline-flex h-9 items-center gap-1 rounded-full bg-indigo-50 pl-2.5 pr-1 text-xs text-indigo-600"
      >
        {refLabel(ref)}
        <button
          type="button"
          aria-label="移除该上下文"
          onClick={() => onRemove(ref)}
          className="flex h-9 w-7 items-center justify-center rounded-full transition-colors hover:bg-indigo-100"
        >
          <X size={12} />
        </button>
      </span>
    ))}

    <button
      type="button"
      aria-label="添加上下文"
      onClick={onAdd}
      className="inline-flex h-9 items-center gap-1 rounded-full border border-dashed border-slate-300 px-2.5 text-xs text-slate-500 transition-colors hover:border-indigo-400 hover:text-indigo-600"
    >
      <AtSign size={12} />
      添加
    </button>
  </div>
)

export default ContextBar
