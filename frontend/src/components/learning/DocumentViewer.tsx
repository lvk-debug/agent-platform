/**
 * 文档学习视图
 *
 * 组合了：分页导航 + 四种渲染器 + 双指缩放平移 + 透明标注画布 + 便签层 + 工具条。
 * 所有笔记按页独立存储，翻页自动切换。
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Alert, message, Spin } from 'antd'
import AnnotationCanvas from './AnnotationCanvas'
import AnnotationToolbar, { type CanvasMode } from './AnnotationToolbar'
import PdfPageRenderer from './renderers/PdfPageRenderer'
import PptxPageRenderer from './renderers/PptxPageRenderer'
import EpubChapterRenderer from './renderers/EpubChapterRenderer'
import MarkdownPageRenderer from './renderers/MarkdownPageRenderer'
import usePointerDraw, { normalizeShape } from '../../hooks/usePointerDraw'
import learningApi from '../../services/learning'
import type {
  AnnotationShape,
  AnnotationTool,
  DocumentPage,
  LearningResource,
} from '../../types/learning'
import { composePageSnapshot } from '../../utils/snapshot'
import type Konva from 'konva'

/** Konva 画布高度上限，避免超长 EPUB 章节生成巨型画布 */
const MAX_CANVAS_HEIGHT = 8000

/**
 * 自动保存的空闲阈值：停止操作画布满 2 分钟才落库。
 * 期间若翻页或离开详情页，会走 flushSave 立即保存，因此不会丢数据。
 */
const AUTOSAVE_IDLE_MS = 120_000

/** 页面最大渲染宽度，超宽屏下不让文档被拉得过散 */
const MAX_PAGE_WIDTH = 1000

/** 视口内边距（p-4）左右合计 */
const VIEWPORT_PADDING = 32

export interface DocumentViewerHandle {
  /** 供导出弹窗合成当前页 */
  captureCurrentPage: () => Promise<{ dataURL: string; width: number; height: number }>
  /** 逐页合成（全部页导出） */
  captureAllPages: (onProgress: (done: number, total: number) => void) => Promise<void>
}

/** 待落库的标注上下文：定位「哪个资源的哪一页」 */
interface PendingSave {
  resourceId: number
  pageIndex: number
  shapes: AnnotationShape[]
}

interface DocumentViewerProps {
  resource: LearningResource
  pageIndex: number
  onPageChange: (pageIndex: number) => void
  onViewerReady: (handle: DocumentViewerHandle) => void
  /** 画布工具条的挂载容器；由页面 header 提供（页码右侧），为空则不渲染工具条 */
  toolbarSlot?: HTMLElement | null
}

const DocumentViewer: React.FC<DocumentViewerProps> = ({
  resource,
  pageIndex,
  onPageChange,
  onViewerReady,
  toolbarSlot,
}) => {
  const [page, setPage] = useState<DocumentPage | null>(null)
  const [loadingPage, setLoadingPage] = useState(false)
  /** 加载失败时给出明确提示，而不是让用户对着转圈干等 */
  const [pageError, setPageError] = useState<string | null>(null)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)

  /** 画布总开关：默认关闭，文档以纯阅读态呈现，避免滚轮/拖拽被标注层拦截 */
  const [canvasEnabled, setCanvasEnabled] = useState(false)
  const [mode, setMode] = useState<CanvasMode>('browse')
  const [tool, setTool] = useState<AnnotationTool>('pen')
  const [color, setColor] = useState('#EF4444')
  const [strokeWidth, setStrokeWidth] = useState(0.004)
  const [allowFingerDraw, setAllowFingerDraw] = useState(false)

  const [shapes, setShapes] = useState<AnnotationShape[]>([])
  const [history, setHistory] = useState<AnnotationShape[][]>([[]])
  const [historyIndex, setHistoryIndex] = useState(0)

  const { draft, begin, extend, commit } = usePointerDraw()
  const stageRef = useRef<Konva.Stage | null>(null)

  const viewportRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [contentSize, setContentSize] = useState({ width: 800, height: 1000 })
  const saveTimer = useRef<number | null>(null)
  /**
   * 待落库的标注上下文。
   * 翻页或组件卸载时，state 可能已经指向新页（异步加载），
   * 因此必须单独记录「改动发生在哪个资源的哪一页」，才能正确保存。
   */
  const pendingRef = useRef<PendingSave | null>(null)
  /**
   * 加载请求令牌：快速翻页时旧请求可能后返回，
   * 用它丢弃过期响应，避免第 N 页的数据被第 N-1 页覆盖。
   *
   * ⚠️ 两个加载流程必须各用各的 ref：共用一个时，同一次渲染里两个 effect
   * 会各自把令牌 +1，导致先运行的那个响应永远被判定为「过期」而被丢弃，
   * 结果是文档页一直停在 loading。
   */
  const pageLoadTokenRef = useRef(0)
  const noteLoadTokenRef = useRef(0)

  const fileType = resource.file_type ?? 'pdf'

  // PDF 需要原始字节流
  useEffect(() => {
    if (fileType !== 'pdf') return
    let revoked = false
    learningApi
      .fetchDocumentBlob(resource.id)
      .then((url) => {
        if (!revoked) setPdfUrl(url)
      })
      .catch((error) => {
        console.error('加载 PDF 文件失败', error)
        // 取不到文件流时后面的分页请求会被跳过，若不提示就会一直转圈
        if (!revoked) setPageError('PDF 文件加载失败，请确认文件未损坏或重新上传')
      })
    return () => {
      revoked = true
    }
  }, [fileType, resource.id])

  // 加载当前页
  useEffect(() => {
    if (fileType === 'pdf' && !pdfUrl) return
    setLoadingPage(true)
    setPageError(null)

    const token = pageLoadTokenRef.current + 1
    pageLoadTokenRef.current = token

    learningApi
      .getDocumentPage(resource.id, pageIndex)
      .then((data) => {
        if (token !== pageLoadTokenRef.current) return
        setPage(data)
      })
      .catch((error) => {
        if (token === pageLoadTokenRef.current) setPageError('文档页加载失败，请重试')
        console.error('加载文档页失败', error)
      })
      .finally(() => {
        if (token === pageLoadTokenRef.current) setLoadingPage(false)
      })
  }, [resource.id, pageIndex, fileType, pdfUrl])

  /** 立即落库：取消待执行的 debounce，翻页与卸载时调用 */
  const flushSave = useCallback((pending: PendingSave) => {
    if (saveTimer.current !== null) {
      window.clearTimeout(saveTimer.current)
      saveTimer.current = null
    }
    pendingRef.current = null
    return learningApi
      .saveDrawPage(pending.resourceId, pending.pageIndex, pending.shapes)
      .then(() => message.success('标注已保存'))
      .catch((error) => console.error('保存标注失败', error))
  }, [])

  /** 自动落库：每次改动都重置计时器，停手满 2 分钟后保存 */
  const scheduleSave = useCallback(
    (pending: PendingSave) => {
      if (saveTimer.current !== null) window.clearTimeout(saveTimer.current)
      saveTimer.current = window.setTimeout(() => {
        saveTimer.current = null
        void flushSave(pending)
      }, AUTOSAVE_IDLE_MS)
    },
    [flushSave]
  )

  // 加载本页标注与便签：每页一个独立画布，进入新页前先把上一页落库
  useEffect(() => {
    const pending = pendingRef.current
    if (
      pending &&
      (pending.resourceId !== resource.id || pending.pageIndex !== pageIndex)
    ) {
      void flushSave(pending)
    }

    const token = noteLoadTokenRef.current + 1
    noteLoadTokenRef.current = token

    learningApi
      .getDrawPage(resource.id, pageIndex)
      .then((draw) => {
        if (token !== noteLoadTokenRef.current) return
        setShapes(draw.shapes ?? [])
        setHistory([draw.shapes ?? []])
        setHistoryIndex(0)
      })
      .catch((error) => console.error('加载标注失败', error))
  }, [resource.id, pageIndex, flushSave])

  // 收起画布即视为"停止操作"，立即落库，不必等满 2 分钟
  useEffect(() => {
    if (canvasEnabled) return
    const pending = pendingRef.current
    if (pending) void flushSave(pending)
  }, [canvasEnabled, flushSave])

  // 离开详情页时立即落库：自动保存可能还没触发，否则最后一次标注会丢
  useEffect(
    () => () => {
      const pending = pendingRef.current
      if (pending) void flushSave(pending)
    },
    [flushSave]
  )

  // 测量文档内容尺寸，画布必须与之等大，否则标注会错位
  // 宽度取视口可用宽度（自适应，不做缩放）；高度由内容实际渲染结果决定
  useEffect(() => {
    const viewport = viewportRef.current
    const node = contentRef.current
    if (!viewport || !node) return

    const measure = () => {
      const available = Math.max((viewport.clientWidth || 800) - VIEWPORT_PADDING, 320)
      const width = Math.min(available, MAX_PAGE_WIDTH)
      const height = Math.min(node.scrollHeight || 1000, MAX_CANVAS_HEIGHT)
      // 值没变就返回原对象，避免 ResizeObserver → setState → 再触发的死循环
      setContentSize((prev) =>
        prev.width === width && prev.height === height ? prev : { width, height }
      )
    }

    measure()
    const viewportObserver = new ResizeObserver(measure)
    viewportObserver.observe(viewport)
    const contentObserver = new ResizeObserver(measure)
    contentObserver.observe(node)
    return () => {
      viewportObserver.disconnect()
      contentObserver.disconnect()
    }
  }, [page])

  const applyShapes = useCallback(
    (next: AnnotationShape[], persist = true) => {
      setShapes(next)
      setHistory((prev) => [...prev.slice(0, historyIndex + 1), next])
      setHistoryIndex((prev) => prev + 1)

      const pending: PendingSave = { resourceId: resource.id, pageIndex, shapes: next }
      pendingRef.current = pending
      if (persist) scheduleSave(pending)
    },
    [historyIndex, pageIndex, resource.id, scheduleSave]
  )

  const handleDrawEnd = useCallback(() => {
    const shape = commit()
    if (!shape) return
    const normalized = normalizeShape(shape)
    if (!normalized) return
    applyShapes([...shapes, normalized])
  }, [commit, shapes, applyShapes])

  const undo = useCallback(() => {
    if (historyIndex <= 0) return
    const prev = history[historyIndex - 1]
    setHistoryIndex(historyIndex - 1)
    setShapes(prev)
    const pending: PendingSave = { resourceId: resource.id, pageIndex, shapes: prev }
    pendingRef.current = pending
    scheduleSave(pending)
  }, [history, historyIndex, pageIndex, resource.id, scheduleSave])

  const redo = useCallback(() => {
    if (historyIndex >= history.length - 1) return
    const next = history[historyIndex + 1]
    setHistoryIndex(historyIndex + 1)
    setShapes(next)
    const pending: PendingSave = { resourceId: resource.id, pageIndex, shapes: next }
    pendingRef.current = pending
    scheduleSave(pending)
  }, [history, historyIndex, pageIndex, resource.id, scheduleSave])

  const clearPage = useCallback(() => {
    applyShapes([])
  }, [applyShapes])

  /** 文本贴纸拖动结束：写回归一化锚点并落库（不进撤销栈，避免拖一下就多一步历史） */
  const handleShapeMove = useCallback(
    (id: string, x: number, y: number) => {
      const next = shapes.map((shape) =>
        shape.id === id ? { ...shape, points: [{ x, y }] } : shape
      )
      setShapes(next)
      const pending: PendingSave = { resourceId: resource.id, pageIndex, shapes: next }
      pendingRef.current = pending
      scheduleSave(pending)
    },
    [shapes, pageIndex, resource.id, scheduleSave]
  )

  /** 贴纸旋转/缩放结束：写回归一化锚点、角度与缩放 */
  const handleShapeTransform = useCallback(
    (
      id: string,
      transform: { x: number; y: number; rotation: number; scaleX: number; scaleY: number }
    ) => {
      const next = shapes.map((shape) =>
        shape.id === id
          ? {
              ...shape,
              points: [{ x: transform.x, y: transform.y }],
              rotation: transform.rotation,
              scaleX: transform.scaleX,
              scaleY: transform.scaleY,
            }
          : shape
      )
      setShapes(next)
      const pending: PendingSave = { resourceId: resource.id, pageIndex, shapes: next }
      pendingRef.current = pending
      scheduleSave(pending)
    },
    [shapes, pageIndex, resource.id, scheduleSave]
  )

  // ---------------- 导出 ----------------

  useEffect(() => {
    const handle: DocumentViewerHandle = {
      captureCurrentPage: async () => {
        if (!contentRef.current) throw new Error('文档尚未渲染完成')
        return composePageSnapshot(contentRef.current, stageRef.current)
      },
      captureAllPages: async (onProgress) => {
        for (let index = 0; index < resource.page_count; index += 1) {
          if (index !== pageIndex) {
            onPageChange(index)
            // 等待切页渲染完成（渲染器为异步），给两帧 + 缓冲时间
            await new Promise((resolve) => window.setTimeout(resolve, 600))
          }
          const snapshot = await composePageSnapshot(contentRef.current, stageRef.current)
          await learningApi.createExportNote({
            resource_id: resource.id,
            page_index: index,
            image_base64: snapshot.dataURL,
            width: snapshot.width,
            height: snapshot.height,
          })
          onProgress(index + 1, resource.page_count)
        }
        onPageChange(pageIndex)
      },
    }
    onViewerReady(handle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resource.id, resource.page_count, pageIndex, onPageChange, onViewerReady])

  // ---------------- 渲染 ----------------

  const aspectRatio = useMemo(
    () => (page && page.width > 0 && page.height > 0 ? page.width / page.height : 16 / 9),
    [page]
  )

  const renderContent = () => {
    // 优先暴露失败原因，避免"一直转圈但不知道为什么"
    if (pageError) {
      return <Alert type="error" showIcon message={pageError} className="m-4" />
    }
    if (loadingPage || !page) {
      return (
        <div className="flex h-64 items-center justify-center">
          <Spin />
        </div>
      )
    }
    if (fileType === 'pdf') {
      return pdfUrl ? (
        <PdfPageRenderer fileUrl={pdfUrl} pageIndex={page.page_index} width={contentSize.width} />
      ) : (
        <div className="flex h-64 items-center justify-center">
          <Spin tip="加载 PDF…" />
        </div>
      )
    }
    if (fileType === 'pptx') {
      return (
        <PptxPageRenderer blocks={page.blocks} width={contentSize.width} aspectRatio={aspectRatio} />
      )
    }
    if (fileType === 'epub') {
      return <EpubChapterRenderer html={page.html} width={contentSize.width} />
    }
    return <MarkdownPageRenderer content={page.raw} width={contentSize.width} />
  }

  // 工具条渲染到页面 header 的插槽（页码右侧）。状态仍留在本组件内，
  // 用 portal 只搬运 DOM 位置，避免把画布状态整体提升到页面层。
  const toolbarNode = (
    <AnnotationToolbar
      canvasEnabled={canvasEnabled}
      mode={mode}
      tool={tool}
      color={color}
      strokeWidth={strokeWidth}
      allowFingerDraw={allowFingerDraw}
      canUndo={historyIndex > 0}
      canRedo={historyIndex < history.length - 1}
      vertical={false}
      onToggleCanvas={() => {
        const next = !canvasEnabled
        setCanvasEnabled(next)
        // 打开画布直接进入标注态，关闭则退回浏览态
        setMode(next ? 'draw' : 'browse')
      }}
      onModeChange={setMode}
      onToolChange={setTool}
      onColorChange={setColor}
      onStrokeWidthChange={setStrokeWidth}
      onToggleFingerDraw={() => setAllowFingerDraw((prev) => !prev)}
      onUndo={undo}
      onRedo={redo}
      onClear={clearPage}
      onExport={() => window.dispatchEvent(new CustomEvent('learning:open-export'))}
    />
  )

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      {toolbarSlot ? createPortal(toolbarNode, toolbarSlot) : null}

      {/* 页面视口：不提供缩放，页面按视口宽度 1:1 渲染，滚动交给浏览器原生滚动 */}
        <div
          ref={viewportRef}
          className="relative min-h-0 flex-1 overflow-auto rounded-2xl bg-[radial-gradient(circle_at_1px_1px,#e2e8f0_1px,transparent_0)] bg-[size:16px_16px] p-4"
          // 只有真正进入标注态才拦触摸手势；
          // 预览模式（画布开着但只阅读）要放开，否则触屏无法滑动，也无法长按选词
          style={{
            touchAction: canvasEnabled && mode !== 'browse' ? 'none' : undefined,
          }}
        >
          <div
            className="mx-auto shadow-[0_18px_50px_-20px_rgba(15,17,23,0.35)]"
            style={{ width: contentSize.width }}
          >
            <div ref={contentRef} className="relative w-full">
              {renderContent()}

              {/* 标注画布与便签层：仅在画布开启时挂载 */}
              {canvasEnabled && (
                <>
                  <AnnotationCanvas
                    width={contentSize.width}
                    height={contentSize.height}
                    shapes={shapes}
                    draft={draft}
                    // 预览模式完全不接管指针；画笔与文本贴纸模式才可交互
                    active={mode !== 'browse'}
                    mode={mode}
                    tool={tool}
                    color={color}
                    strokeWidth={strokeWidth}
                    allowFingerDraw={allowFingerDraw}
                    onDrawStart={(x, y, pressure) =>
                      begin({ x, y }, { tool, color, strokeWidth, opacity: 1 }, pressure)
                    }
                    onDrawMove={(x, y) => extend({ x, y })}
                    onDrawEnd={handleDrawEnd}
                    onTextCommit={(shape) => applyShapes([...shapes, shape])}
                    onShapeMove={handleShapeMove}
                    onShapeTransform={handleShapeTransform}
                    onStageReady={(stage) => {
                      stageRef.current = stage
                    }}
                  />
                </>
              )}
            </div>
          </div>
        </div>
    </div>
  )
}

export default DocumentViewer
