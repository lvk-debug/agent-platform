/**
 * 学习时长心跳
 *
 * 上报策略：
 * - 每 HEARTBEAT_INTERVAL 秒上报一次，携带位置与增量时长
 * - client_seq 单调递增，后端据此去重，重复/乱序上报不会导致时长翻倍
 * - 页面隐藏或卸载时立即结算：先补最后一次增量，再显式结束会话
 *
 * 计时为什么不让后端做：播放器可能暂停、标签页可能后台，
 * 只有前端知道「用户是否真的在看」。前端算增量、后端负责幂等累加。
 */

import { useCallback, useEffect, useRef } from 'react'
import learningApi from '../services/learning'

const HEARTBEAT_INTERVAL_MS = 15_000

export interface HeartbeatOptions {
  resourceId: number
  /** 获取当前位置：视频为秒，文档为页码 */
  getPosition: () => number
  enabled?: boolean
  onReported?: (totalSeconds: number, percent: number) => void
}

export const useStudyHeartbeat = ({
  resourceId,
  getPosition,
  enabled = true,
  onReported,
}: HeartbeatOptions) => {
  const seqRef = useRef(0)
  const lastTickRef = useRef<number>(Date.now())
  const resourceRef = useRef(resourceId)

  useEffect(() => {
    resourceRef.current = resourceId
    seqRef.current = 0
    lastTickRef.current = Date.now()
  }, [resourceId])

  const flush = useCallback(
    async (isFinished = false) => {
      if (!enabled) return
      const now = Date.now()
      const delta = Math.max(Math.round((now - lastTickRef.current) / 1000), 0)
      if (delta === 0 && !isFinished) return

      seqRef.current += 1
      try {
        const result = await learningApi.reportProgress(resourceRef.current, {
          position: getPosition(),
          delta_seconds: delta,
          client_seq: seqRef.current,
          is_finished: isFinished,
        })
        lastTickRef.current = now
        onReported?.(result.total_seconds, result.percent)
      } catch (error) {
        console.error('学习时长上报失败', error)
        // 上报失败不推进 seq，下轮重试时仍用同一序号，避免重复计时
        seqRef.current -= 1
      }
    },
    [enabled, getPosition, onReported]
  )

  useEffect(() => {
    if (!enabled) return
    const timer = window.setInterval(() => {
      void flush()
    }, HEARTBEAT_INTERVAL_MS)

    // 页面隐藏：浏览器会节流定时器，先把已消耗的时间结算掉
    const handleVisibility = () => {
      if (document.hidden) void flush()
      else lastTickRef.current = Date.now()
    }
    const handleLeave = () => {
      void flush()
      void learningApi.closeSession(resourceRef.current)
    }

    document.addEventListener('visibilitychange', handleVisibility)
    window.addEventListener('pagehide', handleLeave)

    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', handleVisibility)
      window.removeEventListener('pagehide', handleLeave)
      void flush()
      void learningApi.closeSession(resourceRef.current)
    }
  }, [enabled, flush])

  return { flush }
}

export default useStudyHeartbeat
