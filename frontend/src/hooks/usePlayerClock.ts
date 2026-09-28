/**
 * 统一播放时钟
 *
 * 两种平台的进度获取能力不同，这里向上层屏蔽差异：
 *
 * | 平台    | 时钟来源                                   |
 * |---------|--------------------------------------------|
 * | YouTube | IFrame Player API，postMessage 回传真实进度 |
 * | 哔哩哔哩 | iframe 跨域不可读退化为「父页驱动时钟」      |
 *
 * B站父页驱动：用户点播放时记 wall clock 基准，随后靠 rAF 推进；
 * 手动 seek / 暂停 / 页面隐藏时校正基准，把累计漂移压到可接受范围。
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import type { ResourceSource } from '../types/learning'

export interface PlayerClock {
  currentMs: number
  isPlaying: boolean
  /** 请求播放器跳转（真正的 seek 由播放器适配器执行） */
  seekTo: (ms: number) => void
  /** 播放器回传真实进度（YouTube 用） */
  syncExternal: (ms: number) => void
  setPlaying: (playing: boolean) => void
  /** 注册真正执行 seek 的回调 */
  registerSeeker: (seeker: (ms: number) => void) => void
}

/**
 * @param source    资源平台
 * @param durationMs 视频总时长（毫秒），用于夹逼
 */
export const usePlayerClock = (source: ResourceSource, durationMs: number): PlayerClock => {
  const [currentMs, setCurrentMs] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)

  const baseMsRef = useRef(0)
  const startedAtRef = useRef<number | null>(null)
  const seekerRef = useRef<((ms: number) => void) | null>(null)
  const frameRef = useRef<number | null>(null)

  const clamp = useCallback(
    (ms: number) => {
      const upper = durationMs > 0 ? durationMs : Number.MAX_SAFE_INTEGER
      return Math.min(Math.max(ms, 0), upper)
    },
    [durationMs]
  )

  const registerSeeker = useCallback((seeker: (ms: number) => void) => {
    seekerRef.current = seeker
  }, [])

  const seekTo = useCallback(
    (ms: number) => {
      const target = clamp(ms)
      setCurrentMs(target)
      baseMsRef.current = target
      startedAtRef.current = performance.now()
      seekerRef.current?.(target)
    },
    [clamp]
  )

  const syncExternal = useCallback(
    (ms: number) => {
      const target = clamp(ms)
      setCurrentMs(target)
      baseMsRef.current = target
      startedAtRef.current = performance.now()
    },
    [clamp]
  )

  const setPlaying = useCallback((playing: boolean) => {
    setIsPlaying(playing)
    if (playing) {
      startedAtRef.current = performance.now()
    } else {
      baseMsRef.current = clamp(baseMsRef.current + elapsed())
      startedAtRef.current = null
      setCurrentMs(baseMsRef.current)
    }
  }, [clamp])

  const elapsed = (): number =>
    startedAtRef.current === null ? 0 : performance.now() - startedAtRef.current

  // B站（父页驱动）：启动后靠 rAF 推进时钟
  useEffect(() => {
    // YouTube 有真实进度回传，无需自行推算
    if (source !== 'bilibili' || !isPlaying) {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
      return
    }

    const tick = () => {
      if (startedAtRef.current !== null) {
        const next = clamp(baseMsRef.current + elapsed())
        setCurrentMs(next)
      }
      frameRef.current = requestAnimationFrame(tick)
    }
    frameRef.current = requestAnimationFrame(tick)

    return () => {
      if (frameRef.current !== null) {
        cancelAnimationFrame(frameRef.current)
        frameRef.current = null
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [source, isPlaying, clamp])

  // 页面隐藏时暂停计时，回来后重新对齐基准，避免后台标签页里时间飞涨
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden && isPlaying) {
        baseMsRef.current = clamp(baseMsRef.current + elapsed())
        startedAtRef.current = performance.now()
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, clamp])

  return { currentMs, isPlaying, seekTo, syncExternal, setPlaying, registerSeeker }
}

export default usePlayerClock
