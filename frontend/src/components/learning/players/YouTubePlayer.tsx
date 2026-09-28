/**
 * YouTube 播放器适配器
 *
 * 通过 IFrame Player API 做 postMessage 双向通信：
 * - 读：定时轮询 getCurrentTime()（YouTube 没有 timeupdate 事件）
 * - 写：seekTo() / setPlaybackRate() / playVideo() / pauseVideo()
 */

import React, { useCallback, useEffect, useRef } from 'react'

interface YouTubePlayerProps {
  videoId: string
  playbackRate: number
  /** 回传真实播放进度（毫秒） */
  onTime: (ms: number) => void
  onPlayingChange: (playing: boolean) => void
  /** 把 seek 能力交给上层时钟 */
  registerSeeker: (seeker: (ms: number) => void) => void
}

/** IFrame API 只需加载一次，多个播放器实例共享 */
let apiPromise: Promise<void> | null = null

const loadIframeApi = (): Promise<void> => {
  if (apiPromise) return apiPromise
  apiPromise = new Promise<void>((resolve) => {
    if (window.YT?.Player) {
      resolve()
      return
    }
    const previous = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      previous?.()
      resolve()
    }
    if (!document.getElementById('youtube-iframe-api')) {
      const script = document.createElement('script')
      script.id = 'youtube-iframe-api'
      script.src = 'https://www.youtube.com/iframe_api'
      script.async = true
      document.body.appendChild(script)
    }
  })
  return apiPromise
}

const YouTubePlayer: React.FC<YouTubePlayerProps> = ({
  videoId,
  playbackRate,
  onTime,
  onPlayingChange,
  registerSeeker,
}) => {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const playerRef = useRef<any>(null)
  /** 标记是否为程序内 seek，避免把 seek 造成的跳变当成用户操作 */
  const rateRef = useRef(playbackRate)

  useEffect(() => {
    rateRef.current = playbackRate
  }, [playbackRate])

  // 创建播放器
  useEffect(() => {
    let disposed = false

    const create = async () => {
      await loadIframeApi()
      if (disposed || !containerRef.current) return

      playerRef.current = new window.YT!.Player(containerRef.current, {
        videoId,
        playerVars: {
          playsinline: 1,
          rel: 0,
          modestbranding: 1,
          origin: window.location.origin,
        },
        events: {
          onReady: () => {
            playerRef.current?.setPlaybackRate?.(rateRef.current)
          },
          onStateChange: (event: any) => {
            // 1=播放中 3=缓冲 其余视为暂停/结束
            onPlayingChange(event.data === 1 || event.data === 3)
          },
        },
      })
    }

    void create()
    return () => {
      disposed = true
      try {
        playerRef.current?.destroy?.()
      } catch (error) {
        console.error('销毁 YouTube 播放器失败', error)
      }
      playerRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId])

  // 轮询真实进度
  useEffect(() => {
    const timer = window.setInterval(() => {
      const player = playerRef.current
      if (!player?.getCurrentTime) return
      const seconds = player.getCurrentTime()
      if (typeof seconds === 'number') onTime(seconds * 1000)
    }, 250)
    return () => window.clearInterval(timer)
  }, [onTime])

  // 倍速切换
  useEffect(() => {
    playerRef.current?.setPlaybackRate?.(playbackRate)
  }, [playbackRate])

  const seek = useCallback(
    (ms: number) => {
      playerRef.current?.seekTo?.(ms / 1000, true)
      playerRef.current?.playVideo?.()
    },
    []
  )

  useEffect(() => {
    registerSeeker(seek)
  }, [registerSeeker, seek])

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-black">
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />
    </div>
  )
}

export default YouTubePlayer
