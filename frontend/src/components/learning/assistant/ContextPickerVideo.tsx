/**
 * 视频字幕选择器（@ 面板）
 *
 * 字幕数据直接用页面已加载的 cues，不必再打接口。
 * 长视频字幕可达数千条，故必须支持搜索定位，并对渲染条数设上限。
 */

import React, { useMemo, useState } from 'react'
import { Input } from 'antd'
import type { ContextRef, TranscriptCue } from '../../../types/learning'
import { formatClock } from '../../../utils/format'
import { refKey } from './ContextBar'

/** 单次最多渲染的条数，超出的靠搜索定位，避免一次性铺几千个节点 */
const MAX_VISIBLE = 500

interface ContextPickerVideoProps {
  cues: TranscriptCue[]
  selected: ContextRef[]
  onConfirm: (ref: ContextRef) => void
}

const ContextPickerVideo: React.FC<ContextPickerVideoProps> = ({
  cues,
  selected,
  onConfirm,
}) => {
  const [keyword, setKeyword] = useState('')

  const selectedKeys = useMemo(() => new Set(selected.map(refKey)), [selected])

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return cues
    return cues.filter((cue) => (cue.text || '').toLowerCase().includes(kw))
  }, [cues, keyword])

  const visible = filtered.slice(0, MAX_VISIBLE)

  return (
    <div className="flex h-full flex-col">
      <div className="p-3">
        <Input
          allowClear
          value={keyword}
          onChange={(event) => setKeyword(event.target.value)}
          placeholder="搜索字幕内容"
          className="!h-11"
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
        {visible.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-400">没有匹配的字幕</p>
        ) : (
          visible.map((cue) => {
            const ref: ContextRef = {
              type: 'transcript',
              page_index: null,
              start_ms: cue.start_ms,
              end_ms: cue.end_ms,
            }
            const added = selectedKeys.has(refKey(ref))
            return (
              <button
                key={cue.id || cue.start_ms}
                type="button"
                disabled={added}
                onClick={() => onConfirm(ref)}
                className={`mb-1.5 flex w-full items-start gap-2 rounded-xl px-3 py-2.5 text-left transition-colors ${
                  added
                    ? 'cursor-not-allowed bg-slate-50 text-slate-300'
                    : 'hover:bg-indigo-50'
                }`}
              >
                <span className="w-14 shrink-0 pt-0.5 text-xs text-indigo-500">
                  {formatClock(cue.start_ms)}
                </span>
                <span className="min-w-0 flex-1 text-sm text-slate-700">
                  {cue.text}
                </span>
                {added ? <span className="shrink-0 text-xs">已添加</span> : null}
              </button>
            )
          })
        )}

        {filtered.length > visible.length ? (
          <p className="py-3 text-center text-xs text-slate-400">
            {keyword.trim()
              ? `匹配 ${filtered.length} 条，仅显示前 ${MAX_VISIBLE} 条，请细化关键词`
              : `共 ${filtered.length} 条，仅显示前 ${MAX_VISIBLE} 条，可搜索定位`}
          </p>
        ) : null}
      </div>
    </div>
  )
}

export default ContextPickerVideo
