/**
 * 画布截图导出工具
 *
 * 导出需要把「文档层」与「标注层」压成一张图。两类文档层的抓取方式不同：
 * - canvas 型（PDF）：pdfjs 已渲染出 <canvas>，直接 drawImage，零失真
 * - DOM 型（PPTX/EPUB/Markdown）：走 html2canvas-pro 快照
 *
 * 合成规则：以文档层为底，标注层按比例拉伸覆盖其上（两者逻辑尺寸一致即可）。
 */

import type Konva from 'konva'

export interface SnapshotResult {
  dataURL: string
  width: number
  height: number
}

/**
 * 抓取 canvas 型文档层（PDF）
 */
export function pickPdfCanvas(container: HTMLElement | null): HTMLCanvasElement | null {
  if (!container) return null
  const canvas = container.querySelector('canvas')
  return canvas instanceof HTMLCanvasElement ? canvas : null
}

/**
 * 抓取 DOM 型文档层（PPTX / EPUB / Markdown）
 */
export async function captureDomLayer(container: HTMLElement): Promise<HTMLCanvasElement> {
  const { default: html2canvas } = await import('html2canvas-pro')
  return html2canvas(container, {
    backgroundColor: '#ffffff',
    scale: Math.min(window.devicePixelRatio || 1, 2),
    useCORS: true,
    logging: false,
  })
}

/**
 * 导出 Konva 标注层为独立 canvas
 */
export function captureKonvaStage(stage: Konva.Stage): HTMLCanvasElement {
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2)
  return stage.toCanvas({ pixelRatio })
}

/**
 * 把标注层合成到文档底图之上
 */
export function composeLayers(
  base: HTMLCanvasElement,
  overlay: HTMLCanvasElement | null
): SnapshotResult {
  const canvas = document.createElement('canvas')
  canvas.width = base.width
  canvas.height = base.height

  const ctx = canvas.getContext('2d')
  if (!ctx) {
    throw new Error('当前浏览器不支持 Canvas 2D，无法导出图片')
  }

  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(base, 0, 0, canvas.width, canvas.height)

  if (overlay && overlay.width > 0 && overlay.height > 0) {
    ctx.drawImage(overlay, 0, 0, canvas.width, canvas.height)
  }

  return {
    dataURL: canvas.toDataURL('image/png'),
    width: canvas.width,
    height: canvas.height,
  }
}

/**
 * 按容器形态自动选择抓取方式并合成导出图
 */
export async function composePageSnapshot(
  container: HTMLElement | null,
  stage: Konva.Stage | null
): Promise<SnapshotResult> {
  if (!container) {
    throw new Error('文档尚未渲染完成，无法导出')
  }

  const pdfCanvas = pickPdfCanvas(container)
  const base = pdfCanvas ?? (await captureDomLayer(container))
  const overlay = stage ? captureKonvaStage(stage) : null
  return composeLayers(base, overlay)
}

/**
 * 组装导出文件名：<资源标题>-第N页-<时间戳>.png
 */
export function buildExportFileName(title: string, pageIndex: number): string {
  const safeTitle = title.replace(/[\\/:*?"<>|]/g, '').slice(0, 40) || '学习笔记'
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
  return `${safeTitle}-第${pageIndex + 1}页-${stamp}.png`
}
