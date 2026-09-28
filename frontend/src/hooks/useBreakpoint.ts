/**
 * 响应式断点判定
 *
 * 学习场景要兼顾平板：竖屏时视频页改为上下布局、工具栏移到底部，
 * 横屏与桌面保持左右分栏。这里给出统一的断点语义。
 */

import { useEffect, useState } from 'react'

export type LearningLayout = 'desktop' | 'tablet-landscape' | 'tablet-portrait' | 'mobile'

export interface BreakpointState {
  layout: LearningLayout
  width: number
  /** 平板及以上（含横竖屏） */
  isTablet: boolean
  /** 触屏为主的设备：命中区域与手势需按触屏规则放大 */
  isTouch: boolean
  /** 是否应当把左右分栏折叠为上下布局 */
  stackVertically: boolean
}

const resolveLayout = (width: number): LearningLayout => {
  if (width >= 1367) return 'desktop'
  if (width >= 1024) return 'tablet-landscape'
  if (width >= 768) return 'tablet-portrait'
  return 'mobile'
}

const detectTouch = (): boolean => {
  if (typeof window === 'undefined') return false
  const coarse = window.matchMedia?.('(pointer: coarse)').matches ?? false
  return coarse || navigator.maxTouchPoints > 0
}

export const useBreakpoint = (): BreakpointState => {
  const [width, setWidth] = useState<number>(() =>
    typeof window === 'undefined' ? 1440 : window.innerWidth
  )

  useEffect(() => {
    const handleResize = () => setWidth(window.innerWidth)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const layout = resolveLayout(width)
  return {
    layout,
    width,
    isTablet: layout === 'tablet-landscape' || layout === 'tablet-portrait',
    isTouch: detectTouch(),
    stackVertically: layout === 'tablet-portrait' || layout === 'mobile',
  }
}

export default useBreakpoint
