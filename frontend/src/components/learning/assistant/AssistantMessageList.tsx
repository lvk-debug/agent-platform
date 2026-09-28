/**
 * 助手消息列表
 *
 * 复用 react-markdown 渲染回答（与项目其他聊天页一致）；
 * 流式回复单独渲染一条「正在生成」的气泡，带闪烁光标。
 */

import React, { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Bot, User } from 'lucide-react'
import type { ChatMessage } from '../../../types/learning'

interface AssistantMessageListProps {
  messages: ChatMessage[]
  draftContent: string
  loading: boolean
  loadingHistory: boolean
  /** 空态时插入的内容（推荐问题） */
  emptyExtra?: React.ReactNode
}

const AssistantMessageList: React.FC<AssistantMessageListProps> = ({
  messages,
  draftContent,
  loading,
  loadingHistory,
  emptyExtra,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新消息与流式增量都要把视口带到底部，否则用户看不到正在生成的内容
  useEffect(() => {
    const node = scrollRef.current
    if (!node) return
    node.scrollTop = node.scrollHeight
  }, [messages, draftContent])

  if (loadingHistory) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-slate-400">
        加载中…
      </div>
    )
  }

  return (
    <div ref={scrollRef} className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-3">
      {!messages.length && !loading ? (
        <div className="space-y-3">
          <div className="flex items-start gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white">
              <Bot size={16} />
            </span>
            <div className="rounded-2xl rounded-tl-sm bg-white px-3 py-2 text-sm text-slate-600 shadow-sm">
              我已经读过这份资料了，随时可以问它相关的问题。
            </div>
          </div>
          {emptyExtra}
        </div>
      ) : null}

      {messages.map((message) =>
        message.role === 'user' ? (
          <div key={message.id} className="flex items-start justify-end gap-2">
            <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-tr-sm bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] px-3 py-2 text-sm text-white shadow-sm">
              {message.content}
            </div>
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-500">
              <User size={16} />
            </span>
          </div>
        ) : (
          <div key={message.id} className="flex items-start gap-2">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white">
              <Bot size={16} />
            </span>
            <div className="min-w-0 max-w-[85%]">
              {message.error ? (
                <div className="rounded-2xl rounded-tl-sm border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-600">
                  {message.error}
                </div>
              ) : (
                <div className="rounded-2xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
                  <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-pre:bg-slate-800 prose-pre:text-slate-50">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          </div>
        )
      )}

      {loading ? (
        <div className="flex items-start gap-2">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white">
            <Bot size={16} />
          </span>
          <div className="min-w-0 max-w-[85%]">
            <div className="rounded-2xl rounded-tl-sm bg-white px-3 py-2 shadow-sm">
              {draftContent ? (
                <div className="prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-pre:bg-slate-800 prose-pre:text-slate-50">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {draftContent}
                  </ReactMarkdown>
                </div>
              ) : (
                <span className="text-sm text-slate-400">正在阅读资料…</span>
              )}
              {/* 流式光标：告诉用户还在生成，而不是卡住了 */}
              <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-indigo-400 align-middle" />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

export default AssistantMessageList
