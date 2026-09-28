/**
 * 哔哩哔哩播放器适配器
 *
 * B站 iframe（player.bilibili.com）跨域不提供进度 API，因此：
 * - 进度由父页时钟推算（usePlayerClock 的父页驱动模式）
 * - seek 只能靠重建 iframe 并带上起播时间（B站无运行时 seek 接口）
 *
 * ⚠️ 关键约束：父页时钟由 rAF **每帧推进**，当前播放位置持续变化。
 * 绝不能把 iframe 的 key / src 绑定到它，否则播放器会被每秒卸载重建一次，
 * 表现为「视频永远加载不出来」。故这里用独立的 `seekVersion` 表示
 * 「用户真的跳转了」，只有它变化才重建 iframe。
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { PlayCircleOutlined } from '@ant-design/icons'

interface BilibiliPlayerProps {
  bvid: string
  onPlayingChange: (playing: boolean) => void
  registerSeeker: (seeker: (ms: number) => void) => void
}

const BilibiliPlayer: React.FC<BilibiliPlayerProps> = ({
  bvid,
  onPlayingChange,
  registerSeeker,
}) => {
  const [started, setStarted] = useState(false)
  /** 仅在用户主动跳转时自增，作为 iframe 的重建信号 */
  const [seekVersion, setSeekVersion] = useState(0)
  const seekSecondsRef = useRef(0)

  const handleSeeker = useCallback((ms: number) => {
    seekSecondsRef.current = Math.max(Math.floor(ms / 1000), 0)
    setSeekVersion((version) => version + 1)
    setStarted(true)
  }, [])

  useEffect(() => {
    registerSeeker(handleSeeker)
  }, [registerSeeker, handleSeeker])

  const start = () => {
    setStarted(true)
    onPlayingChange(true)
  }

  const src = `https://player.bilibili.com/player.html?bvid=${encodeURIComponent(
    bvid
  )}&autoplay=1&high_quality=1&danmaku=0&t=${seekSecondsRef.current}`

  return (
    <div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-black">
      {started ? (
        <iframe
          key={`${bvid}-${seekVersion}`}
          src={src}
          title="哔哩哔哩播放器"
          allowFullScreen
          scrolling="no"
          frameBorder="0"
          className="absolute inset-0 h-full w-full"
        />
      ) : (
        <button
          type="button"
          onClick={start}
          className="absolute inset-0 flex h-full w-full flex-col items-center justify-center gap-3 bg-[radial-gradient(circle_at_center,#1E1B4B_0%,#0F1117_70%)] text-white transition-colors hover:bg-[radial-gradient(circle_at_center,#312E81_0%,#0F1117_70%)]"
        >
          <span className="flex h-16 w-16 items-center justify-center rounded-full bg-white/15 text-4xl backdrop-blur-sm">
            <PlayCircleOutlined />
          </span>
          <span className="text-sm text-white/70">点击开始播放</span>
          <span className="max-w-[320px] px-6 text-xs leading-5 text-white/40">
            B站播放器受跨域限制，无法读取播放进度；开始后由本页为你计时。点字幕会尝试跳转，
            若该视频不支持指定起播时间，请手动拖动播放器进度条。
          </span>
        </button>
      )}
    </div>
  )
}

export default BilibiliPlayer
