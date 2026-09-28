/**
 * 指针绘制状态机
 *
 * 平板同时存在手指、手写笔、鼠标三种输入源，统一收敛到 PointerEvent：
 * - `pointerType === 'pen'` 时按 `pressure` 映射线宽，还原真实书写笔锋
 * - 鼠标/手指无压感，使用固定线宽
 *
 * 本 hook 只维护「正在绘制的那一个图形」的点序列，不涉及任何 DOM。
 * draft 同时存在 ref 与 state 中：ref 用于抬笔时同步取值（setState 是异步的），
 * state 用于驱动实时渲染。
 */

import { useCallback, useRef, useState } from 'react'
import type { AnnotationPoint, AnnotationShape, AnnotationTool } from '../types/learning'

export interface DrawConfig {
  tool: AnnotationTool
  color: string
  /** 归一化线宽（相对页面宽度） */
  strokeWidth: number
  opacity: number
}

const uuid = (): string =>
  typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`

/** 鼠标与触摸的名义压力值 */
const DEFAULT_PRESSURE = 0.5

/** 采样阈值：位移过小不记录，压缩点数以降低存储与渲染开销 */
const MIN_STEP = 0.0015

export const usePointerDraw = () => {
  const draftRef = useRef<AnnotationShape | null>(null)
  const [draft, setDraft] = useState<AnnotationShape | null>(null)

  const begin = useCallback(
    (point: AnnotationPoint, config: DrawConfig, pressure = DEFAULT_PRESSURE) => {
      // 压感映射：0.6~1.4 倍基准线宽，避免压力抖动导致笔迹忽粗忽细
      const width =
        config.tool === 'highlighter'
          ? config.strokeWidth
          : config.strokeWidth * (0.6 + pressure * 0.8)

      // 两点类图形（矩形/箭头/椭圆）落笔即补一个与起点重合的末点：
      // 否则首帧只有起点，末点被当成原点 (0,0)，会先甩出一个贯穿整页的巨大图形
      const isPathTool = config.tool === 'pen' || config.tool === 'highlighter'

      const shape: AnnotationShape = {
        id: uuid(),
        tool: config.tool,
        color: config.color,
        strokeWidth: width,
        opacity: config.opacity,
        points: isPathTool ? [point] : [point, { ...point }],
        createdAt: new Date().toISOString(),
      }
      draftRef.current = shape
      setDraft(shape)
    },
    []
  )

  const extend = useCallback((point: AnnotationPoint) => {
    const current = draftRef.current
    if (!current) return

    const last = current.points[current.points.length - 1]
    if (last && Math.hypot(point.x - last.x, point.y - last.y) < MIN_STEP) return

    // 两点类图形只维护首点与末点：末点跟随指针，而不是不断追加
    const isPathTool = current.tool === 'pen' || current.tool === 'highlighter'
    const updated: AnnotationShape = {
      ...current,
      points: isPathTool ? [...current.points, point] : [current.points[0], point],
    }
    draftRef.current = updated
    setDraft(updated)
  }, [])

  const cancel = useCallback(() => {
    draftRef.current = null
    setDraft(null)
  }, [])

  /** 抬笔：同步返回成形图形并清空草稿 */
  const commit = useCallback((): AnnotationShape | null => {
    const result = draftRef.current
    draftRef.current = null
    setDraft(null)
    return result
  }, [])

  return { draft, begin, extend, cancel, commit }
}

/**
 * 把原始图形收敛成最终形态
 *
 * - pen / highlighter 保留路径点（少于 2 点视为无效点击）
 * - arrow / rect / ellipse 只取首点与末点
 */
export const normalizeShape = (shape: AnnotationShape): AnnotationShape | null => {
  const { points, tool } = shape
  if (points.length === 0) return null

  if (tool === 'pen' || tool === 'highlighter') {
    return points.length < 2 ? null : shape
  }

  const first = points[0]
  const last = points[points.length - 1]
  if (Math.hypot(last.x - first.x, last.y - first.y) < 0.005) return null
  return { ...shape, points: [first, last] }
}

export default usePointerDraw
