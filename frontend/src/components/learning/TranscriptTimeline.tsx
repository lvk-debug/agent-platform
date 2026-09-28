/**
 * 字幕时间轴
 *
 * 长视频字幕可达数千条，这里做三件事保证流畅：
 * 1. react-window 虚拟滚动，只渲染视口内的条目
 * 2. 当前句用二分查找定位（O(log n)），只在跨句时更新索引
 * 3. 搜索过滤在前端 useMemo 派生，不发后端请求
 */

import React, {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react'
import { FixedSizeList, type ListChildComponentProps } from 'react-window'
import { Empty } from 'antd'
import { AimOutlined, SearchOutlined } from '@ant-design/icons'
import type { TranscriptCue } from '../../types/learning'
import { formatClock } from '../../utils/format'

interface TranscriptTimelineProps {
  cues: TranscriptCue[]
  currentMs: number
  onSeek: (startMs: number) => void
  /**
   * 是否在组件内部显示「回到当前句」按钮。
   * 字幕区自带标题栏时由外部渲染该按钮（放在标题右侧），这里传 false。
   */
  showActiveButton?: boolean
}

export interface TranscriptTimelineHandle {
  /** 滚动定位到当前播放的字幕句 */
  scrollToActive: () => void
}

/** 二分查找：返回 start_ms <= currentMs 的最后一条 */
const findActiveIndex = (cues: TranscriptCue[], ms: number): number => {
  let low = 0
  let high = cues.length - 1
  let answer = -1
  while (low <= high) {
    const mid = (low + high) >> 1
    if (cues[mid].start_ms <= ms) {
      answer = mid
      low = mid + 1
    } else {
      high = mid - 1
    }
  }
  return answer
}

/** 把命中的关键词包成 <mark> */
const renderHighlighted = (text: string, keyword: string) => {
  if (!keyword) return text
  const lower = text.toLowerCase()
  const target = keyword.toLowerCase()
  const parts: React.ReactNode[] = []
  let cursor = 0

  while (cursor < text.length) {
    const hit = lower.indexOf(target, cursor)
    if (hit === -1) {
      parts.push(text.slice(cursor))
      break
    }
    if (hit > cursor) parts.push(text.slice(cursor, hit))
    parts.push(
      <mark key={`${hit}-${cursor}`} className="rounded bg-amber-200 px-0.5 text-amber-900">
        {text.slice(hit, hit + target.length)}
      </mark>
    )
    cursor = hit + target.length
  }
  return parts
}

interface RowData {
  cues: TranscriptCue[]
  activeIndex: number
  keyword: string
  onSeek: (startMs: number) => void
}

const Row: React.FC<ListChildComponentProps<RowData>> = ({ index, style, data }) => {
  const cue = data.cues[index]
  const isActive = index === data.activeIndex
  const isPast = index < data.activeIndex

  return (
    <div style={style} className="px-2">
      <button
        type="button"
        onClick={() => data.onSeek(cue.start_ms)}
        className={`group flex w-full gap-3 rounded-xl px-3 py-2.5 text-left transition-colors duration-150 ${
          isActive
            ? 'bg-indigo-50 shadow-[inset_3px_0_0_0_#6366F1]'
            : 'hover:bg-slate-50'
        }`}
      >
        <span
          className={`shrink-0 pt-0.5 font-mono text-xs ${
            isActive ? 'text-indigo-600' : 'text-slate-400'
          }`}
        >
          {formatClock(cue.start_ms)}
        </span>
        <span className="min-w-0 flex-1">
          {/* 原文：双语展示的主行。限高 2 行，配合固定行高避免溢出重叠 */}
          <span
            className={`block line-clamp-2 text-sm leading-6 ${
              isActive
                ? 'font-medium text-indigo-900'
                : isPast
                  ? 'text-slate-400'
                  : 'text-slate-700'
            }`}
          >
            {renderHighlighted(cue.text, data.keyword)}
          </span>
          {/* 译文：有才占一行，没有就不留空白 */}
          {cue.translation ? (
            <span
              className={`mt-0.5 block line-clamp-2 text-sm leading-6 ${
                isActive ? 'text-indigo-500' : isPast ? 'text-slate-300' : 'text-slate-500'
              }`}
            >
              {renderHighlighted(cue.translation, data.keyword)}
            </span>
          ) : null}
        </span>
      </button>
    </div>
  )
}

const TranscriptTimeline = forwardRef<TranscriptTimelineHandle, TranscriptTimelineProps>(
  function TranscriptTimeline(
    { cues, currentMs, onSeek, showActiveButton = true },
    ref
  ) {
  const [keyword, setKeyword] = useState('')
  const [listHeight, setListHeight] = useState(420)
  const listRef = useRef<FixedSizeList>(null)
  const wrapperRef = useRef<HTMLDivElement>(null)

  const filtered = useMemo(() => {
    if (!keyword.trim()) return cues
    const target = keyword.trim().toLowerCase()
    // 双语下原文与译文都要能被搜到
    return cues.filter(
      (cue) =>
        cue.text.toLowerCase().includes(target) ||
        (cue.translation || '').toLowerCase().includes(target)
    )
  }, [cues, keyword])

  const activeIndex = useMemo(() => findActiveIndex(cues, currentMs), [cues, currentMs])

  // 双语每条多占一行，行高必须跟着变，否则会与下一条重叠
  const hasTranslation = useMemo(() => cues.some((cue) => cue.translation), [cues])
  const itemSize = hasTranslation ? 120 : 72

  /**
   * 不做自动跟随滚动：视频播放时列表若持续滚动会打断阅读。
   * 当前句仍会高亮，需要时点「回到当前句」手动定位。
   */
  const scrollToActive = useCallback(() => {
    if (activeIndex < 0) return
    // 搜索态下 activeIndex 是相对全量 cues 的，需换算到过滤后的位置
    const activeCue = cues[activeIndex]
    const target = activeCue ? filtered.indexOf(activeCue) : -1
    if (target >= 0) listRef.current?.scrollToItem(target, 'center')
  }, [activeIndex, cues, filtered])

  // 供外部（字幕标题栏）复用同一定位能力
  useImperativeHandle(ref, () => ({ scrollToActive }), [scrollToActive])

  // 测量可用高度
  useEffect(() => {
    const node = wrapperRef.current
    if (!node) return
    const observer = new ResizeObserver((entries) => {
      const height = entries[0]?.contentRect.height ?? 420
      setListHeight(Math.max(height, 200))
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  // 缓存 itemData，避免每次渲染都让虚拟列表全量重绘
  const itemData: RowData = useMemo(() => {
    const activeCue = cues[activeIndex]
    return {
      cues: filtered,
      activeIndex: activeCue ? filtered.indexOf(activeCue) : -1,
      keyword,
      onSeek,
    }
  }, [cues, filtered, activeIndex, keyword, onSeek])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="mb-3 flex items-center gap-2">
        <div className="relative min-w-0 flex-1">
          <SearchOutlined className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            placeholder="搜索字幕内容"
            className="h-11 w-full rounded-xl border border-slate-200 bg-white pl-9 pr-3 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
        </div>

        {/* 浅色次要按钮：不再悬浮在列表右下角遮挡字幕，也不与正文抢视觉 */}
        {showActiveButton && activeIndex >= 0 && (
          <button
            type="button"
            onClick={scrollToActive}
            className="flex h-11 shrink-0 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-600 shadow-sm transition-colors hover:border-indigo-300 hover:text-indigo-600"
          >
            <AimOutlined />
            回到当前句
          </button>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="flex flex-1 items-center justify-center">
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={
              <span className="text-slate-500">
                {cues.length === 0 ? '该资源暂无字幕' : '没有匹配的字幕'}
              </span>
            }
          />
        </div>
      ) : (
        <div ref={wrapperRef} className="relative min-h-0 flex-1">
          <FixedSizeList
            ref={listRef}
            height={listHeight}
            itemCount={filtered.length}
            itemSize={itemSize}
            width="100%"
            itemData={itemData}
            overscanCount={6}
          >
            {Row}
          </FixedSizeList>
        </div>
      )}
    </div>
  )
  }
)

export default TranscriptTimeline
