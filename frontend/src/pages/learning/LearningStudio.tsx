/**
 * 学习详情 /learning/:id
 *
 * 按资源类型分发两种沉浸式布局：
 * - 视频：左侧播放器 + 右侧时间轴字幕
 * - 文档：分页预览 + 标注画布 + 便签（浅色纸感）
 *
 * 两种模式共用一套学习时长心跳。
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Button, Drawer, Spin, Upload, message } from 'antd'
import {
  AimOutlined,
  ArrowLeftOutlined,
  BarChartOutlined,
  FileTextOutlined,
  MessageOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import VideoPlayer from '../../components/learning/VideoPlayer'
import TranscriptTimeline, {
  type TranscriptTimelineHandle,
} from '../../components/learning/TranscriptTimeline'
import DocumentViewer, { type DocumentViewerHandle } from '../../components/learning/DocumentViewer'
import PageNavigator from '../../components/learning/PageNavigator'
import AssistantFab from '../../components/learning/assistant/AssistantFab'
import AssistantDrawer from '../../components/learning/assistant/AssistantDrawer'
import ExportSnapshotDialog, { type ExportRange } from '../../components/learning/ExportSnapshotDialog'
import NoteTimeline from '../../components/learning/NoteTimeline'
import usePlayerClock from '../../hooks/usePlayerClock'
import useStudyHeartbeat from '../../hooks/useStudyHeartbeat'
import useBreakpoint from '../../hooks/useBreakpoint'
import learningApi from '../../services/learning'
import type {
  LearningResource,
  TranscriptCue,
} from '../../types/learning'
import { buildExportFileName } from '../../utils/snapshot'
import { formatClock, formatDuration } from '../../utils/format'

const LearningStudio: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { stackVertically } = useBreakpoint()
  const resourceId = Number(id)

  const [resource, setResource] = useState<LearningResource | null>(null)
  const [cues, setCues] = useState<TranscriptCue[]>([])
  const [language, setLanguage] = useState('')
  const [pageIndex, setPageIndex] = useState(0)
  /** header 中的工具条挂载点。用 state 而非 ref 存节点，容器一挂载就能触发 portal 渲染 */
  const [toolbarSlot, setToolbarSlot] = useState<HTMLDivElement | null>(null)
  const [exportOpen, setExportOpen] = useState(false)
  const [noteDrawerOpen, setNoteDrawerOpen] = useState(false)
  const [bottomTab, setBottomTab] = useState<'transcript' | 'notes'>('transcript')
  const [assistantOpen, setAssistantOpen] = useState(false)

  const viewerRef = useRef<DocumentViewerHandle | null>(null)
  const positionRef = useRef(0)
  // 字幕时间轴的定位句柄（「回到当前句」用）。
  // 必须和其余 hook 一起放在顶部：放在条件返回之后会导致两次渲染的 hook 数量不一致。
  const timelineRef = useRef<TranscriptTimelineHandle | null>(null)

  const isDocument = resource?.type === 'document'
  const clock = usePlayerClock(resource?.source ?? 'youtube', (resource?.duration_seconds ?? 0) * 1000)

  // 加载资源
  useEffect(() => {
    if (!resourceId) return
    learningApi
      .getResource(resourceId)
      .then(setResource)
      .catch((error) => console.error('加载资源失败', error))
  }, [resourceId])

  // 加载字幕
  const loadTranscripts = useCallback(
    (lang?: string) => {
      if (!resourceId || isDocument) return
      learningApi
        .getTranscripts(resourceId, lang)
        .then((data) => {
          setCues(data.cues)
          if (!lang && data.language) setLanguage(data.language)
        })
        .catch((error) => console.error('加载字幕失败', error))
    },
    [resourceId, isDocument]
  )

  // 首次进入拉取字幕
  useEffect(() => {
    loadTranscripts()
  }, [loadTranscripts])

  // 资源刚导入时可能仍在后台抓取，轮询等待就绪
  // 依赖里带上 resource.status，否则首帧 resource 还是 null 会导致轮询永不启动
  useEffect(() => {
    if (!resource || resource.status !== 'pending' || isDocument) return
    const timer = window.setInterval(() => {
      learningApi
        .getResource(resourceId)
        .then((latest) => {
          setResource(latest)
          if (latest.status !== 'pending') {
            window.clearInterval(timer)
            loadTranscripts()
          }
        })
        .catch((error) => console.error('轮询资源状态失败', error))
    }, 3000)
    return () => window.clearInterval(timer)
  }, [resource, isDocument, resourceId, loadTranscripts])

  // 位置同步：视频用播放时钟，文档用页码
  useEffect(() => {
    positionRef.current = isDocument ? pageIndex : clock.currentMs / 1000
  }, [clock.currentMs, pageIndex, isDocument])

  const getPosition = useCallback(() => positionRef.current, [])



  useStudyHeartbeat({ resourceId, getPosition, enabled: Boolean(resource) })

  // ---------------- 视频交互 ----------------

  const seekTo = useCallback(
    (ms: number) => {
      clock.seekTo(ms)
    },
    [clock]
  )

  const stepCue = useCallback(
    (direction: 1 | -1) => {
      if (cues.length === 0) return
      const current = clock.currentMs
      if (direction === 1) {
        const next = cues.find((cue) => cue.start_ms > current + 200)
        if (next) clock.seekTo(next.start_ms)
        return
      }
      const previous = [...cues].reverse().find((cue) => cue.start_ms < current - 200)
      if (previous) clock.seekTo(previous.start_ms)
    },
    [cues, clock]
  )

  // ---------------- 导出 ----------------

  useEffect(() => {
    const openExport = () => setExportOpen(true)
    window.addEventListener('learning:open-export', openExport)
    return () => window.removeEventListener('learning:open-export', openExport)
  }, [])

  const handleExport = async (range: ExportRange, note: string) => {
    if (!resource || !viewerRef.current) return

    if (range === 'current') {
      const snapshot = await viewerRef.current.captureCurrentPage()
      await learningApi.createExportNote({
        resource_id: resource.id,
        page_index: pageIndex,
        image_base64: snapshot.dataURL,
        note,
        width: snapshot.width,
        height: snapshot.height,
      })
      const link = document.createElement('a')
      link.href = snapshot.dataURL
      link.download = buildExportFileName(resource.title, pageIndex)
      link.click()
      message.success('已导出当前页并留档')
      return
    }

    await viewerRef.current.captureAllPages((done, total) => {
      message.loading({ content: `正在导出 ${done}/${total} 页…`, key: 'exportAll' })
    })
    message.success({ content: `已导出全部 ${resource.page_count} 页`, key: 'exportAll' })
  }

  const handleUploadSubtitle = async (file: File) => {
    try {
      await learningApi.uploadSubtitle(resourceId, file, language || 'manual')
      message.success('字幕上传成功')
      loadTranscripts(language || undefined)
    } catch (error) {
      console.error('上传字幕失败', error)
      message.error('字幕上传失败，请确认是 SRT/VTT 文件')
    }
    return false
  }

  if (!resource) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#F7F8FA]">
        <Spin size="large" />
      </div>
    )
  }

  if (resource.status === 'failed') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-[#F7F8FA] px-6 text-center">
        <p className="text-base font-medium text-slate-800">资源导入失败</p>
        <p className="max-w-md text-sm text-slate-500">{resource.error_message ?? '未知错误'}</p>
        <Button onClick={() => navigate('/learning')}>返回资源库</Button>
      </div>
    )
  }

  if (resource.status === 'pending') {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-[#F7F8FA] text-center">
        <Spin size="large" />
        <p className="text-sm text-slate-500">正在抓取视频信息与字幕，请稍候…</p>
      </div>
    )
  }

  // ---------------- 文档模式 ----------------
  if (isDocument) {
    return (
      <div className="flex h-screen flex-col bg-[#F7F8FA]">
        <header className="flex min-h-[64px] shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-slate-200 bg-white px-4 py-2">
          <div className="flex min-w-0 flex-1 items-center gap-3">
            <button
              type="button"
              aria-label="返回"
              onClick={() => navigate('/learning')}
              className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-indigo-600"
            >
              <ArrowLeftOutlined />
            </button>
            <FileTextOutlined className="text-indigo-500" />
            <h1 className="min-w-0 truncate text-base font-semibold text-slate-800">
              {resource.title}
            </h1>
            {/* 页码紧随标题，支持手动输入跳转 */}
            <PageNavigator
              pageIndex={pageIndex}
              pageCount={resource.page_count || 1}
              onChange={setPageIndex}
            />
            {/* 画布工具条插槽：由 DocumentViewer 通过 portal 填充，位于页码右侧 */}
            <div ref={setToolbarSlot} className="flex min-w-0 flex-1" />
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <span className="text-xs text-slate-500">
              已学 {formatDuration(resource.total_seconds)}
            </span>
            <Button
              icon={<MessageOutlined />}
              onClick={() => setNoteDrawerOpen(true)}
              className="!h-11"
            >
              笔记
            </Button>
          </div>
        </header>

        <div className="min-h-0 flex-1 p-4">
          <DocumentViewer
            resource={resource}
            pageIndex={pageIndex}
            onPageChange={setPageIndex}
            onViewerReady={(handle) => {
              viewerRef.current = handle
            }}
            toolbarSlot={toolbarSlot}
          />
        </div>

        <ExportSnapshotDialog
          open={exportOpen}
          pageIndex={pageIndex}
          pageCount={resource.page_count || 1}
          onClose={() => setExportOpen(false)}
          onPreview={async () => {
            const snapshot = await viewerRef.current!.captureCurrentPage()
            return snapshot.dataURL
          }}
          onExport={handleExport}
        />

        <Drawer
          title="本资源笔记"
          placement="right"
          width={420}
          open={noteDrawerOpen}
          onClose={() => setNoteDrawerOpen(false)}
        >
          <NoteTimeline resourceId={resource.id} onJump={(page) => {
            setPageIndex(page)
            setNoteDrawerOpen(false)
          }} />
        </Drawer>

        {/* AI 助手：文档模式把当前页码作为「正在看哪」传给问答上下文 */}
        <AssistantFab onClick={() => setAssistantOpen(true)} />
        <AssistantDrawer
          open={assistantOpen}
          resource={resource}
          position={pageIndex}
          onClose={() => setAssistantOpen(false)}
        />
      </div>
    )
  }

  // ---------------- 视频模式（深色沉浸） ----------------
  /**
   * 桌面/横屏的标题栏自带「回到当前句」按钮（放在「字幕」二字右侧），
   * 组件内就不重复渲染；平板竖屏没有标题栏，仍由组件内显示。
   */
  const renderTranscript = (showActiveButton: boolean) => (
    <TranscriptTimeline
      ref={timelineRef}
      cues={cues}
      currentMs={clock.currentMs}
      onSeek={seekTo}
      showActiveButton={showActiveButton}
    />
  )

  return (
    <div className="flex h-screen flex-col bg-[#F7F8FA] text-slate-800">
      {/* 顶部资源条 */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            aria-label="返回"
            onClick={() => navigate('/learning')}
            className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-indigo-600"
          >
            <ArrowLeftOutlined />
          </button>
          <h1 className="truncate text-base font-semibold text-slate-800">{resource.title}</h1>
          <span className="shrink-0 rounded-md bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-600">
            {resource.source === 'bilibili' ? '哔哩哔哩' : 'YouTube'}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-3 text-xs text-slate-500">
          <span>{formatClock(clock.currentMs)} / {formatClock(resource.duration_seconds * 1000)}</span>
          <span className="font-medium text-indigo-600">{Math.min(resource.progress_percent, 100)}%</span>
          <span className="hidden sm:inline">已学 {formatDuration(resource.total_seconds)}</span>
        </div>
      </header>

      <div
        className={`min-h-0 flex-1 gap-4 p-4 ${
          stackVertically ? 'flex flex-col overflow-y-auto' : 'flex'
        }`}
      >
        <section className={stackVertically ? 'w-full' : 'min-w-0 flex-[3]'}>
          <VideoPlayer
            resource={resource}
            onTime={clock.syncExternal}
            onPlayingChange={clock.setPlaying}
            registerSeeker={clock.registerSeeker}
            onPrevCue={() => stepCue(-1)}
            onNextCue={() => stepCue(1)}
          />

          {/* 无字幕时引导手动上传 */}
          {(resource.status === 'no_subtitle' || cues.length === 0) && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
              <p className="text-sm text-amber-800">
                该视频没有可用字幕，上传 SRT/VTT 后即可对照原文学习。
              </p>
              <Upload
                accept=".srt,.vtt"
                showUploadList={false}
                beforeUpload={(file) => handleUploadSubtitle(file as unknown as File)}
              >
                <Button icon={<UploadOutlined />} className="!h-11 !rounded-xl">
                  上传字幕
                </Button>
              </Upload>
            </div>
          )}
        </section>

        {stackVertically ? (
          <section className="flex w-full min-h-[420px] flex-col">
            <div className="mb-2 flex gap-1 rounded-full bg-slate-100 p-1">
              {(['transcript', 'notes'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setBottomTab(tab)}
                  className={`h-11 flex-1 rounded-full text-sm transition-colors ${
                    bottomTab === tab
                      ? 'bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white shadow-sm'
                      : 'text-slate-500'
                  }`}
                >
                  {tab === 'transcript' ? '字幕' : '笔记'}
                </button>
              ))}
            </div>
            <div className="min-h-0 flex-1 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
              {bottomTab === 'transcript' ? (
                renderTranscript(true)
              ) : (
                <NoteTimeline
                  resourceId={resource.id}
                  onJumpToTime={(ms) => {
                    clock.seekTo(ms)
                    setBottomTab('transcript')
                  }}
                />
              )}
            </div>
          </section>
        ) : (
          <section className="flex min-h-0 min-w-0 flex-[2] flex-col">
            <div className="mb-2 flex items-center justify-between gap-2">
              <h2 className="text-sm font-medium text-slate-600">字幕</h2>
              <div className="flex items-center">
                {/* 与「笔记」同为浅色文字按钮，放在「字幕」标题右侧 */}
                <Button
                  type="text"
                  icon={<AimOutlined />}
                  onClick={() => timelineRef.current?.scrollToActive()}
                  className="!h-11 !text-slate-500"
                >
                  回到当前句
                </Button>
                <Button
                  type="text"
                  icon={<BarChartOutlined />}
                  onClick={() => setNoteDrawerOpen(true)}
                  className="!h-11 !text-slate-500"
                >
                  笔记
                </Button>
              </div>
            </div>
            <div className="min-h-0 flex-1 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
              {renderTranscript(false)}
            </div>
          </section>
        )}
      </div>

      <Drawer
        title="本资源笔记"
        placement="right"
        width={420}
        open={noteDrawerOpen}
        onClose={() => setNoteDrawerOpen(false)}
      >
        <NoteTimeline
          resourceId={resource.id}
          onJumpToTime={(ms) => {
            clock.seekTo(ms)
            setNoteDrawerOpen(false)
          }}
        />
      </Drawer>

      {/* AI 助手：视频模式把当前播放秒数作为「正在看哪」传给问答上下文 */}
      <AssistantFab onClick={() => setAssistantOpen(true)} />
      <AssistantDrawer
        open={assistantOpen}
        resource={resource}
        position={clock.currentMs / 1000}
        cues={cues}
        onClose={() => setAssistantOpen(false)}
      />
    </div>
  )
}

export default LearningStudio
