/**
 * 学习资源库 /learning
 *
 * 资源导入入口（URL / 拖拽文档）+ 筛选搜索 + 响应式卡片网格。
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Empty, Modal, Select, Spin } from 'antd'
import {
  BarChartOutlined,
  LinkOutlined,
  PlusOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import ResourceCard from '../../components/learning/ResourceCard'
import ResourceDropzone from '../../components/learning/ResourceDropzone'
import UrlImportModal from '../../components/learning/UrlImportModal'
import { useLearningStore } from '../../stores/learningStore'
import learningApi from '../../services/learning'
import useBreakpoint from '../../hooks/useBreakpoint'
import type { LearningResource, ResourceType } from '../../types/learning'

const TYPE_TABS: Array<{ key: ResourceType | 'all'; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'video', label: '视频' },
  { key: 'document', label: '文档' },
]

const SORT_OPTIONS = [
  { value: 'recent_studied', label: '最近学习' },
  { value: 'recent_created', label: '最近添加' },
  { value: 'progress', label: '学习进度' },
]

const ResourceLibrary: React.FC = () => {
  const navigate = useNavigate()
  const { layout, isTouch } = useBreakpoint()
  const [urlModalOpen, setUrlModalOpen] = useState(false)
  const [uploadVisible, setUploadVisible] = useState(false)
  const [keyword, setKeyword] = useState('')

  const {
    resources,
    hasMore,
    loading,
    filters,
    loadResources,
    loadMore,
    setFilters,
    appendResource,
    replaceResource,
    removeResource,
  } = useLearningStore()

  const sentinelRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    void loadResources(true)
  }, [loadResources])

  // 触底加载更多：用 IntersectionObserver 替代 scroll 监听，滚动更稳
  useEffect(() => {
    const node = sentinelRef.current
    if (!node) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) void loadMore()
      },
      { rootMargin: '120px' }
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [loadMore, resources.length])

  const handleDelete = useCallback(
    async (resource: LearningResource) => {
      Modal.confirm({
        title: `删除「${resource.title}」？`,
        content: '该资源的字幕、笔记与学习记录将一并删除，且无法恢复。',
        okText: '确认删除',
        okButtonProps: { danger: true },
        cancelText: '取消',
        onOk: async () => {
          await learningApi.deleteResource(resource.id)
          removeResource(resource.id)
        },
      })
    },
    [removeResource]
  )

  const gridColumns = useMemo(() => {
    if (layout === 'desktop') return 'grid-cols-4'
    if (layout === 'tablet-landscape') return 'grid-cols-3'
    if (layout === 'tablet-portrait') return 'grid-cols-2'
    return 'grid-cols-1'
  }, [layout])

  return (
    <div className="mx-auto w-full max-w-[1560px] px-1 py-2">
      {/* 顶部操作栏 */}
      <header className="mb-5 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_60%,#22D3EE_100%)] bg-clip-text text-2xl font-semibold text-transparent">
            学习助手
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            导入长视频与文档，在沉浸式工作台里学习、标注、沉淀笔记
            <span className="ml-2 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
              {resources.length} 个资源
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button
            icon={<BarChartOutlined />}
            onClick={() => navigate('/learning/records')}
            className="!h-11 !rounded-xl !px-4"
          >
            学习记录
          </Button>
          <Button
            icon={<LinkOutlined />}
            onClick={() => setUrlModalOpen(true)}
            className="!h-11 !rounded-xl !px-4"
          >
            导入 URL
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setUploadVisible((prev) => !prev)}
            className="!h-11 !rounded-xl !border-0 !px-4 !bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] !shadow-[0_8px_20px_-6px_rgba(99,102,241,0.6)] hover:!opacity-95 active:!scale-[0.97]"
          >
            上传文档
          </Button>
        </div>
      </header>

      {uploadVisible && (
        <section className="mb-5 animate-[fadeSlideUp_0.2s_cubic-bezier(0.4,0,0.2,1)]">
          <ResourceDropzone
            onUploaded={(resource) => {
              appendResource(resource)
              replaceResource(resource)
            }}
          />
        </section>
      )}

      {/* 筛选与搜索 */}
      <section
        className={`mb-5 flex flex-wrap items-center justify-between gap-3 ${
          isTouch ? '' : ''
        }`}
      >
        <div
          className="flex items-center gap-1 overflow-x-auto rounded-full bg-white p-1 shadow-sm ring-1 ring-slate-200/70"
          style={{ scrollbarWidth: 'none' }}
        >
          {TYPE_TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => void setFilters({ type: tab.key })}
              className={`h-11 shrink-0 rounded-full px-4 text-sm font-medium transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] ${
                filters.type === tab.key
                  ? 'bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white shadow-[0_6px_16px_-6px_rgba(99,102,241,0.7)]'
                  : 'text-slate-500 hover:text-indigo-600'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <input
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter') void setFilters({ keyword })
            }}
            placeholder="搜索资源标题"
            className="h-11 w-52 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100"
          />
          <Select
            value={filters.sort}
            onChange={(value) => void setFilters({ sort: value })}
            options={SORT_OPTIONS}
            className="w-32"
            size="large"
          />
        </div>
      </section>

      {/* 资源网格 */}
      {loading && resources.length === 0 ? (
        <div className="flex h-64 items-center justify-center">
          <Spin size="large" />
        </div>
      ) : resources.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/70 py-16">
          <Empty
            description={
              <span className="text-slate-500">
                还没有学习资源，导入一个视频链接或上传文档开始学习
              </span>
            }
          >
            <div className="flex justify-center gap-2">
              <Button icon={<LinkOutlined />} onClick={() => setUrlModalOpen(true)}>
                导入 URL
              </Button>
              <Button
                type="primary"
                icon={<UploadOutlined />}
                onClick={() => setUploadVisible(true)}
                className="!border-0 !bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)]"
              >
                上传文档
              </Button>
            </div>
          </Empty>
        </div>
      ) : (
        <>
          <div className={`grid gap-4 ${gridColumns}`}>
            {resources.map((resource) => (
              <ResourceCard key={resource.id} resource={resource} onDelete={handleDelete} />
            ))}
          </div>

          <div ref={sentinelRef} className="h-10" />
          {loading && (
            <div className="flex justify-center py-4">
              <Spin />
            </div>
          )}
          {!hasMore && resources.length > 0 && (
            <p className="py-4 text-center text-xs text-slate-400">已经到底啦</p>
          )}
        </>
      )}

      <UrlImportModal
        open={urlModalOpen}
        onClose={() => setUrlModalOpen(false)}
        onImported={(resource) => {
          appendResource(resource)
          replaceResource(resource)
        }}
      />
    </div>
  )
}

export default ResourceLibrary
