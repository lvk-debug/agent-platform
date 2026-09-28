/**
 * 推荐问题卡
 *
 * 由后端基于资源内容生成并缓存；生成中显示骨架，失败时后端已回退模板，
 * 因此这里只处理「加载中 / 有数据」两种状态。
 */

import React from 'react'
import { Sparkles } from 'lucide-react'

interface SuggestedQuestionsProps {
  questions: string[]
  loading: boolean
  disabled: boolean
  onPick: (question: string) => void
}

const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  questions,
  loading,
  disabled,
  onPick,
}) => {
  if (loading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((key) => (
          <div
            key={key}
            className="h-11 animate-pulse rounded-xl bg-slate-100"
            aria-hidden="true"
          />
        ))}
      </div>
    )
  }

  if (!questions.length) return null

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-slate-400">
        <Sparkles size={14} />
        推荐问题
      </div>
      {questions.map((question) => (
        <button
          key={question}
          type="button"
          disabled={disabled}
          onClick={() => onPick(question)}
          className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-left text-sm text-slate-600 transition-all duration-150 hover:-translate-y-0.5 hover:border-indigo-300 hover:bg-indigo-50/60 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {question}
        </button>
      ))}
    </div>
  )
}

export default SuggestedQuestions
