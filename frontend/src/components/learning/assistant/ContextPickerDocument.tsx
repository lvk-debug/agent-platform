/**
 * 文档页选择器（@ 面板）
 *
 * 页数据来自后端 learning_page_texts（解析一次后复用），
 * 支持按标题或页码搜索；已添加的页置灰，避免重复。
 */

import React, { useEffect, useMemo, useState } from 'react'
import { Input, Spin } from 'antd'
import learningApi from '../../../services/learning'
import type { ContextRef, LearningResource, PageOption } from '../../../types/learning'
import { refKey } from './ContextBar'

interface ContextPickerDocumentProps {
  resource: LearningResource
  selected: ContextRef[]
  onConfirm: (ref: ContextRef) => void
}

const ContextPickerDocument: React.FC<ContextPickerDocumentProps> = ({
  resource,
  selected,
  onConfirm,
}) => {
  const [pages, setPages] = useState<PageOption[]>([])
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    setLoading(true)
    learningApi
      .getPageList(resource.id)
      .then((res) => setPages(res.items || []))
      .catch((err) => console.error('加载分页列表失败:', err))
      .finally(() => setLoading(false))
  }, [resource.id])

  const selectedKeys = useMemo(() => new Set(selected.map(refKey)), [selected])

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return pages
    return pages.filter(
      (page) =>
        page.title.toLowerCase().includes(kw) || String(page.page_index + 1) === kw
    )
  }, [pages, keyword])

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Spin />
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Input
          allowClear
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜索页标题或页码"
          className="!h-11"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {filtered.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">没有匹配的页</p>
        ) : (
          filtered.map((page) => {
            const ref: ContextRef = {
              type: 'page',
              page_index: page.page_index,
              start_ms: null,
              end_ms: null,
            }
            const added = selectedKeys.has(refKey(ref))
            return (
              <button
                key={page.page_index}
                type="button"
                disabled={added}
                onClick={() => onConfirm(ref)}
                className={`mb-1.5 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-left text-sm transition-colors ${
                  added
                    ? 'cursor-not-allowed bg-slate-50 text-slate-300'
                    : 'hover:bg-indigo-50'
                }`}
              >
                <span className="w-16 shrink-0 text-xs text-slate-400">
                  第 {page.page_index + 1} 页
                </span>
                <span className="min-w-0 flex-1 truncate text-slate-700">
                  {page.title}
                </span>
                {added ? <span className="shrink-0 text-xs">已添加</span> : null}
              </button>
            )
          })
        )}
      </div>
    </div>
  )
}

export default ContextPickerDocument
