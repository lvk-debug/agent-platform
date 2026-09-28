/**
 * 悬浮小人助手入口
 *
 * 固定在右下角，56px 圆形满足触屏命中要求；平板横竖屏均保持距边 24px，
 * 避开系统手势区。
 */

import React from 'react'
import { Bot } from 'lucide-react'

interface AssistantFabProps {
  onClick: () => void
  /** 尚未提问过时显示小红点，提示「这里可以问」 */
  showDot?: boolean
}

const AssistantFab: React.FC<AssistantFabProps> = ({ onClick, showDot }) => (
  <button
    type="button"
    aria-label="打开 AI 学习助手"
    onClick={onClick}
    className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white shadow-lg shadow-indigo-500/30 transition-transform duration-200 hover:scale-105 active:scale-95"
  >
    <Bot size={26} />
    {showDot ? (
      <span className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-[#EF4444]" />
    ) : null}
  </button>
)

export default AssistantFab
