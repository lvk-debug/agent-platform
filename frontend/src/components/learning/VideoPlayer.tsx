/**
 * 播放器容器
 *
 * 按来源平台分派适配器，并统一暴露倍速、字幕语言、上下句等快捷控制。
 */

import React, { useState } from 'react'
import { Select } from 'antd'
import {
  BackwardOutlined,
  ForwardOutlined,
} from '@ant-design/icons'
import YouTubePlayer from './players/YouTubePlayer'
import BilibiliPlayer from './players/BilibiliPlayer'
import type { LearningResource } from '../../types/learning'

const RATE_OPTIONS = [0.75, 1, 1.25, 1.5, 2].map((rate) => ({
  value: rate,
  label: `${rate}x`,
}))

interface VideoPlayerProps {
  resource: LearningResource
  onTime: (ms: number) => void
  onPlayingChange: (playing: boolean) => void
  registerSeeker: (seeker: (ms: number) => void) => void
  onPrevCue: () => void
  onNextCue: () => void
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({
  resource,
  onTime,
  onPlayingChange,
  registerSeeker,
  onPrevCue,
  onNextCue,
}) => {
  const [playbackRate, setPlaybackRate] = useState(1)
  const platformId = resource.platform_id ?? ''
  const isBilibili = resource.source === 'bilibili'

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-black shadow-[0_18px_40px_-16px_rgba(15,17,23,0.3)]">
        {isBilibili ? (
          <BilibiliPlayer
            bvid={platformId}
            onPlayingChange={onPlayingChange}
            registerSeeker={registerSeeker}
          />
        ) : (
          <YouTubePlayer
            videoId={platformId}
            playbackRate={playbackRate}
            onTime={onTime}
            onPlayingChange={onPlayingChange}
            registerSeeker={registerSeeker}
          />
        )}
      </div>

      {/* 快捷控制条：按钮命中区域 44px */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={onPrevCue}
          className="flex h-11 items-center gap-1.5 rounded-xl bg-white px-4 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200 transition-colors hover:text-indigo-600 active:scale-[0.97]"
        >
          <BackwardOutlined />
          上一句
        </button>
        <button
          type="button"
          onClick={onNextCue}
          className="flex h-11 items-center gap-1.5 rounded-xl bg-white px-4 text-sm text-slate-600 shadow-sm ring-1 ring-slate-200 transition-colors hover:text-indigo-600 active:scale-[0.97]"
        >
          下一句
          <ForwardOutlined />
        </button>

        {!isBilibili && (
          <Select
            value={playbackRate}
            onChange={setPlaybackRate}
            options={RATE_OPTIONS}
            className="w-24"
            size="large"
          />
        )}

        {/* 字幕固定为原文 + 中文双语展示，不提供语言切换 */}
      </div>
    </div>
  )
}

export default VideoPlayer
