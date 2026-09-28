/**
 * 学习资源卡片
 *
 * 命中区域不小于 44px，触屏下 hover 效果退化为 active 态缩放，保证平板可点。
 */

import React from 'react'
import { useNavigate } from 'react-router-dom'
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  DeleteOutlined,
  ExclamationCircleFilled,
  FileTextOutlined,
  MessageOutlined,
  PlayCircleFilled,
  SyncOutlined,
} from '@ant-design/icons'
import type { LearningResource } from '../../types/learning'
import {
  FILE_TYPE_META,
  SOURCE_LABEL,
  formatRelativeTime,
  formatVideoBadge,
} from '../../utils/format'

interface ResourceCardProps {
  resource: LearningResource
  onDelete: (resource: LearningResource) => void
}

const STATUS_BADGE: Record<string, { text: string; className: string; icon: React.ReactNode }> = {
  pending: {
    text: '解析中',
    className: 'bg-indigo-500/15 text-indigo-300',
    icon: <SyncOutlined spin />,
  },
  failed: {
    text: '导入失败',
    className: 'bg-red-500/15 text-red-300',
    icon: <ExclamationCircleFilled />,
  },
  no_subtitle: {
    text: '无字幕',
    className: 'bg-amber-500/15 text-amber-300',
    icon: <ExclamationCircleFilled />,
  },
  ready: {
    text: '就绪',
    className: 'bg-emerald-500/15 text-emerald-300',
    icon: <CheckCircleFilled />,
  },
}

const ResourceCard: React.FC<ResourceCardProps> = ({ resource, onDelete }) => {
  const navigate = useNavigate()
  const isDocument = resource.type === 'document'
  const fileMeta = FILE_TYPE_META[resource.file_type ?? ''] ?? { label: '文档', color: '#6366F1' }
  const badge = STATUS_BADGE[resource.status] ?? STATUS_BADGE.ready
  const cover = resource.cover_url

  const openDetail = () => {
    if (resource.status === 'pending' || resource.status === 'failed') return
    navigate(`/learning/${resource.id}`)
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={openDetail}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          openDetail()
        }
      }}
      className={`group relative flex flex-col overflow-hidden rounded-2xl border border-slate-200/70 bg-white shadow-sm transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:-translate-y-1 hover:border-indigo-300 hover:shadow-[0_18px_40px_-12px_rgba(99,102,241,0.35)] active:scale-[0.985] ${
        resource.status === 'pending' || resource.status === 'failed'
          ? 'cursor-not-allowed opacity-80'
          : 'cursor-pointer'
      }`}
    >
      {/* 封面 / 文档格式色块 */}
      <div className="relative aspect-video w-full overflow-hidden bg-[linear-gradient(135deg,#0F1117_0%,#1E1B4B_55%,#312E81_100%)]">
        {isDocument ? (
          <div className="flex h-full w-full items-center justify-center">
            <span
              className="rounded-xl px-4 py-2 text-lg font-semibold tracking-wide text-white shadow-lg"
              style={{ backgroundColor: fileMeta.color }}
            >
              {fileMeta.label}
            </span>
          </div>
        ) : cover ? (
          <img
            src={cover}
            alt={resource.title}
            referrerPolicy="no-referrer"
            loading="lazy"
            className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center">
            <PlayCircleFilled className="text-4xl text-white/40" />
          </div>
        )}

        {/* 视频时长角标 */}
        {!isDocument && resource.duration_seconds > 0 && (
          <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white">
            {formatVideoBadge(resource.duration_seconds)}
          </span>
        )}

        {/* 平台来源 */}
        {!isDocument && (
          <span className="absolute left-2 top-2 rounded-md bg-black/60 px-2 py-0.5 text-xs font-medium text-white/90">
            {SOURCE_LABEL[resource.source] ?? resource.source}
          </span>
        )}

        {/* 文档页数 */}
        {isDocument && resource.page_count > 0 && (
          <span className="absolute bottom-2 right-2 rounded-md bg-black/70 px-1.5 py-0.5 text-xs font-medium text-white">
            {resource.page_count} 页
          </span>
        )}

        {/* 状态徽标 */}
        {resource.status !== 'ready' && (
          <span
            className={`absolute right-2 top-2 flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${badge.className}`}
          >
            {badge.icon}
            {badge.text}
          </span>
        )}

        {/* 播放态遮罩 */}
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-0 transition-opacity duration-200 group-hover:opacity-100">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
            {isDocument ? (
              <FileTextOutlined className="text-xl text-white" />
            ) : (
              <PlayCircleFilled className="text-2xl text-white" />
            )}
          </span>
        </div>
      </div>

      {/* 卡片主体 */}
      <div className="flex flex-1 flex-col gap-2 p-3">
        <h3 className="line-clamp-2 min-h-[40px] text-sm font-medium leading-5 text-slate-800">
          {resource.title}
        </h3>

        <div className="mt-auto space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <ClockCircleOutlined />
              {formatRelativeTime(resource.last_studied_at)}
            </span>
            <span className="flex items-center gap-1">
              <MessageOutlined />
              {resource.note_count}
            </span>
          </div>

          <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-[linear-gradient(90deg,#6366F1_0%,#8B5CF6_60%,#22D3EE_100%)] transition-[width] duration-500"
              style={{ width: `${Math.min(Math.max(resource.progress_percent, 0), 100)}%` }}
            />
          </div>
        </div>
      </div>

      {/* 删除按钮：命中区域 44px，避免触屏误触 */}
      <button
        type="button"
        aria-label="删除资源"
        onClick={(event) => {
          event.stopPropagation()
          onDelete(resource)
        }}
        className="absolute right-2 top-2 hidden h-11 w-11 items-center justify-center rounded-full bg-white/90 text-slate-500 shadow-md transition-colors hover:bg-red-50 hover:text-red-500 group-hover:flex"
      >
        <DeleteOutlined />
      </button>
    </div>
  )
}

export default ResourceCard
