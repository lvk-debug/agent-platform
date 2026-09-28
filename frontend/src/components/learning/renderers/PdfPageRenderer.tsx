/**
 * PDF 页面渲染器
 *
 * 用 pdfjs 直接把 PDF 流渲染到 canvas：
 * - 省掉后端逐页出图的 CPU 与磁盘开销
 * - 按 devicePixelRatio 提升采样，缩放到 200% 仍然清晰
 *
 * canvas 上的文字是**像素**，天生选不中、复制不了。因此在 canvas 之上再叠一层
 * 透明的 pdfjs TextLayer：视觉上仍是 canvas，但文字变成真实 DOM，可以选词与复制。
 * 该层不设 z-index，自然位于 canvas 之上、标注画布（Konva）之下——
 * 于是预览态能选词，标注态又不会被它挡住笔迹。
 */

import React, { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
// worker 以 URL 形式导入，Vite 通过 ?url 后缀返回最终打包地址
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import { Alert } from 'antd'

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

/**
 * TextLayer 需要的最小样式（取自 pdfjs 官方 text_layer.css 的必需品）。
 * 不整包引入 pdf_viewer.css：它带有大量全局规则，会污染本站样式。
 */
const TEXT_LAYER_CSS = `
.learning-pdf-text-layer {
  /* 兜底值：JS 会按当前缩放覆盖它，避免变量缺失导致 calc() 失效 */
  --scale-factor: 1;
  position: absolute;
  left: 0;
  top: 0;
  right: 0;
  bottom: 0;
  overflow: hidden;
  line-height: 1;
  text-size-adjust: none;
  forced-color-adjust: none;
  transform-origin: 0 0;
}
.learning-pdf-text-layer span,
.learning-pdf-text-layer br {
  color: transparent;
  position: absolute;
  white-space: pre;
  cursor: text;
  transform-origin: 0% 0%;
}
.learning-pdf-text-layer span.markedContent {
  top: 0;
  height: 0;
}
.learning-pdf-text-layer ::selection {
  background: rgba(99, 102, 241, 0.3);
}
`

interface PdfPageRendererProps {
  /** PDF 文件的 blob URL */
  fileUrl: string
  pageIndex: number
  /** 目标显示宽度（CSS 像素） */
  width: number
  onLoaded?: (pageCount: number) => void
}

const PdfPageRenderer: React.FC<PdfPageRendererProps> = ({
  fileUrl,
  pageIndex,
  width,
  onLoaded,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const textLayerRef = useRef<HTMLDivElement | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    let textLayer: pdfjs.TextLayer | null = null

    const render = async () => {
      try {
        const document = await pdfjs.getDocument(fileUrl).promise
        if (cancelled) return
        onLoaded?.(document.numPages)

        const page = await document.getPage(pageIndex + 1)
        if (cancelled) return

        const canvas = canvasRef.current
        if (!canvas) return

        const ratio = Math.min(window.devicePixelRatio || 1, 2)
        const baseViewport = page.getViewport({ scale: 1 })
        // CSS 尺寸用的缩放（文本层按它排版），canvas 位图再乘 devicePixelRatio
        const cssScale = width / baseViewport.width
        const viewport = page.getViewport({ scale: cssScale * ratio })

        canvas.width = Math.floor(viewport.width)
        canvas.height = Math.floor(viewport.height)
        canvas.style.width = `${Math.floor(viewport.width / ratio)}px`
        canvas.style.height = `${Math.floor(viewport.height / ratio)}px`

        const context = canvas.getContext('2d')
        if (!context) {
          setError('当前浏览器不支持 Canvas 渲染')
          return
        }

        await page.render({ canvasContext: context, viewport }).promise

        const container = textLayerRef.current
        if (!container || cancelled) return
        container.innerHTML = ''

        // 必须传 CSS 像素的 viewport，否则文本层与画面错位
        const textViewport = page.getViewport({ scale: cssScale })
        // 关键：pdfjs 只**读取** CSS 变量 --scale-factor（span 的 left/top/font-size
        // 全是 calc(var(--scale-factor) * Npx)），自己从不设置它。缺了这一步，
        // calc() 整体失效、文本层塌成一团，表现就是「明明加了文本层却选不中」。
        container.style.setProperty('--scale-factor', String(textViewport.scale))

        textLayer = new pdfjs.TextLayer({
          textContentSource: page.streamTextContent(),
          container,
          viewport: textViewport,
        })
        await textLayer.render()
      } catch (renderError) {
        console.error('PDF 渲染失败', renderError)
        if (!cancelled) setError('PDF 渲染失败，请确认文件未损坏')
      }
    }

    void render()
    return () => {
      cancelled = true
      textLayer?.cancel()
      // 翻页时清掉上一页的文本节点，避免新旧文本叠在一起
      if (textLayerRef.current) textLayerRef.current.innerHTML = ''
    }
  }, [fileUrl, pageIndex, width, onLoaded])

  if (error) {
    return <Alert type="error" showIcon message={error} className="m-4" />
  }

  return (
    <div className="flex justify-center bg-white">
      <style>{TEXT_LAYER_CSS}</style>
      {/* inline-block 让容器尺寸由 canvas 决定，文本层再 absolute 铺满它 */}
      <div className="relative inline-block">
        <canvas ref={canvasRef} className="block" />
        <div ref={textLayerRef} className="learning-pdf-text-layer" />
      </div>
    </div>
  )
}

export default PdfPageRenderer
