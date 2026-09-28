/**
 * YouTube IFrame Player API 的全局声明
 *
 * 只声明本项目实际用到的成员，播放器实例本身类型松散（官方无类型包），故用 any 承载。
 */

export interface YouTubePlayerInstance {
  getCurrentTime?: () => number
  seekTo?: (seconds: number, allowSeekAhead: boolean) => void
  playVideo?: () => void
  pauseVideo?: () => void
  setPlaybackRate?: (rate: number) => void
  destroy?: () => void
}

declare global {
  interface Window {
    YT?: {
      Player: new (
        element: HTMLElement | string,
        options: {
          videoId: string
          playerVars?: Record<string, string | number>
          events?: {
            onReady?: (event: { target: YouTubePlayerInstance }) => void
            onStateChange?: (event: { data: number; target: YouTubePlayerInstance }) => void
          }
        }
      ) => YouTubePlayerInstance
    }
    onYouTubeIframeAPIReady?: () => void
  }
}

export {}
