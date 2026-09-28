/**
 * 笔记时间线
 *
 * 汇总单个资源的便签与导出图，点击回跳到原文位置（文档页码 / 视频时间点）。
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Empty, Spin } from 'antd'
import { DeleteOutlined, EnvironmentOutlined, PictureOutlined } from '@ant-design/icons'
import learningApi from '../../services/learning'
import type { LearningNote } from '../../types/learning'
import { formatClock, formatRelativeTime } from '../../utils/format'

interface NoteTimelineProps {
  resourceId: number
  /** 文档：跳转到页码 */
  onJump?: (pageIndex: number) => void
  /** 视频：跳转到时间点 */
  onJumpToTime?: (ms: number) => void
}

const NoteTimeline: React.FC<NoteTimelineProps> = ({ resourceId, onJump, onJumpToTime }) => {
  const [notes, setNotes] = useState<LearningNote[]>([])
  const [loading, setLoading] = useState(true)
  const [previews, setPreviews] = useState<Record<number, string>>({})

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      learningApi.listNotes(resourceId, 'text'),
      learningApi.listNotes(resourceId, 'export'),
    ])
      .then(([textNotes, exportNotes]) => {
        const merged = [...textNotes, ...exportNotes].sort(
          (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
        )
        setNotes(merged)

        // 导出图需要带鉴权头，逐张换成本地 blob URL
        exportNotes.forEach((note) => {
          const name = (note.file_url ?? '').split('/').pop()
          if (!name) return
          learningApi
            .fetchAssetBlob(resourceId, name)
            .then((url) => setPreviews((prev) => ({ ...prev, [note.id]: url })))
            .catch((error) => console.error('加载导出图失败', error))
        })
      })
      .catch((error) => console.error('加载笔记失败', error))
      .finally(() => setLoading(false))
  }, [resourceId])

  useEffect(() => {
    load()
  }, [load])

  const handleDelete = (noteId: number) => {
    learningApi
      .deleteNote(noteId)
      .then(() => {
        setNotes((prev) => prev.filter((item) => item.id !== noteId))
      })
      .catch((error) => console.error('删除笔记失败', error))
  }

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Spin />
      </div>
    )
  }

  if (notes.length === 0) {
    return (
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={<span className="text-slate-400">还没有笔记，标注或写下第一条批注吧</span>}
      />
    )
  }

  return (
    <ul className="space-y-3">
      {notes.map((note) => {
        const color = (note.payload?.color as string) || '#6366F1'
        const preview = previews[note.id]
        const positionLabel =
          note.page_index !== null && note.page_index !== undefined
            ? `第 ${note.page_index + 1} 页`
            : typeof note.position_ms === 'number'
              ? formatClock(note.position_ms)
              : ''

        return (
          <li
            key={note.id}
            className="group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-shadow hover:shadow-md"
          >
            {preview && (
              <img src={preview} alt="导出图" className="max-h-40 w-full object-cover" />
            )}

            <div className="flex gap-2 p-3">
              <span
                className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: color }}
              />
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex items-center gap-2 text-xs text-slate-400">
                  <span>{formatRelativeTime(note.created_at)}</span>
                  {positionLabel && (
                    <span className="flex items-center gap-1 text-indigo-500">
                      <EnvironmentOutlined />
                      {positionLabel}
                    </span>
                  )}
                  {note.kind === 'export' && (
                    <span className="flex items-center gap-1 text-slate-400">
                      <PictureOutlined />
                      截图
                    </span>
                  )}
                </div>

                <p className="whitespace-pre-wrap break-words text-sm text-slate-700">
                  {note.content || '（无正文）'}
                </p>

                <div className="mt-2 flex items-center gap-2">
                  {note.page_index !== null && note.page_index !== undefined && onJump && (
                    <button
                      type="button"
                      onClick={() => onJump(note.page_index as number)}
                      className="h-9 rounded-lg bg-indigo-50 px-3 text-xs text-indigo-600 transition-colors hover:bg-indigo-100"
                    >
                      跳转到该页
                    </button>
                  )}
                  {typeof note.position_ms === 'number' && onJumpToTime && (
                    <button
                      type="button"
                      onClick={() => onJumpToTime(note.position_ms as number)}
                      className="h-9 rounded-lg bg-indigo-50 px-3 text-xs text-indigo-600 transition-colors hover:bg-indigo-100"
                    >
                      跳转到该时间点
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label="删除笔记"
                    onClick={() => handleDelete(note.id)}
                    className="ml-auto flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                  >
                    <DeleteOutlined />
                  </button>
                </div>
              </div>
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export default NoteTimeline
