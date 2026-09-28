/**
 * SupportChatWidget - 在线客服悬浮入口
 *
 * 固定在智能客服页右下角的渐变图标按钮，点击展开玻璃聊天面板。
 * 首次展开惰性创建一条 AI 模式会话（supportApi.createSession），
 * 之后复用 useSupportChat 驱动流式回答与 Agent 过程展示。
 * Agent 过程（思考链/工具调用/自动工单）由 MessageBubble 折叠呈现。
 */

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Input, message as antdMessage } from 'antd'
import { CloseOutlined, CustomerServiceOutlined, SendOutlined } from '@ant-design/icons'
import MessageBubble from './MessageBubble'
import useSupportChat from '../../hooks/useSupportChat'
import supportApi from '../../services/support'

const SupportChatWidget: React.FC = () => {
  const [open, setOpen] = useState(false)
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [creating, setCreating] = useState(false)
  const [input, setInput] = useState('')
  const scrollRef = useRef<HTMLDivElement>(null)

  const chat = useSupportChat(sessionId)

  // 首次展开时惰性创建一条 AI 会话，之后复用该会话
  const ensureSession = useCallback(async () => {
    if (sessionId != null || creating) return
    setCreating(true)
    try {
      const session = await supportApi.createSession({ mode: 'ai' })
      setSessionId(session.id)
    } catch (err) {
      console.error('创建在线客服会话失败:', err)
      antdMessage.error('暂时无法发起咨询，请稍后重试')
    } finally {
      setCreating(false)
    }
  }, [sessionId, creating])

  const toggle = useCallback(() => {
    const next = !open
    setOpen(next)
    if (next && sessionId == null) void ensureSession()
  }, [open, sessionId])

  // 新消息与流式内容都会撑高内容区，统一在变化时贴底
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [chat.messages, chat.draftContent, chat.loading])

  const handleSend = useCallback(() => {
    const text = input.trim()
    if (!text || !sessionId || chat.loading) return
    chat.send(text)
    setInput('')
  }, [input, sessionId, chat])

  // 流式中的那条 AI 消息：占位 id 为负，落库后变正
  const streamingId = chat.loading
    ? chat.messages.find((m) => m.role === 'ai' && m.id < 0)?.id
    : undefined

  return (
    <>
      {/* 折叠态：渐变客服图标 + 脉冲光圈微动效 */}
      {!open && (
        <button
          type="button"
          onClick={toggle}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-white shadow-lg shadow-indigo-500/30 flex items-center justify-center hover:scale-105 transition-transform"
          aria-label="在线客服"
        >
          <span className="absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-40 animate-ping" />
          <CustomerServiceOutlined style={{ fontSize: 26 }} />
        </button>
      )}

      {/* 展开态：玻璃聊天面板 */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[380px] max-w-[calc(100vw-2rem)] h-[540px] max-h-[calc(100vh-3rem)] flex flex-col rounded-2xl border border-white/40 bg-white/80 backdrop-blur-xl shadow-2xl overflow-hidden">
          {/* 头部 */}
          <div className="flex items-center gap-2 px-4 py-3 bg-gradient-to-r from-indigo-500 to-violet-500 text-white">
            <CustomerServiceOutlined style={{ fontSize: 18 }} />
            <span className="font-medium">在线客服</span>
            <Button
              type="text"
              size="small"
              icon={<CloseOutlined />}
              onClick={toggle}
              className="ml-auto !text-white hover:!bg-white/20"
            />
          </div>

          {/* 消息区 */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-3 space-y-3 bg-slate-50/40">
            {chat.messages.length === 0 && !chat.loading && (
              <div className="text-center text-xs text-slate-400 py-10">
                您好，我是 AI 客服助手，请问有什么可以帮您？
              </div>
            )}
            {chat.messages.map((item) => (
              <MessageBubble
                key={item.id}
                message={item}
                streaming={item.id === streamingId}
                draftContent={chat.draftContent}
                draftReferences={chat.draftReferences}
                draftMeta={chat.draftMeta}
                draftThoughts={chat.draftThoughts}
                draftToolCalls={chat.draftToolCalls}
                draftTicket={chat.draftTicket}
              />
            ))}
          </div>

          {/* 输入区 */}
          <div className="border-t border-slate-100 p-3 bg-white/60">
            {chat.error && <div className="mb-2 text-xs text-red-500">{chat.error}</div>}
            <div className="flex items-end gap-2">
              <Input.TextArea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={creating ? '正在接入客服…' : '请输入您的问题，Enter 发送'}
                autoSize={{ minRows: 1, maxRows: 4 }}
                disabled={!sessionId || creating}
                onPressEnter={(e) => {
                  if (!e.shiftKey) {
                    e.preventDefault()
                    handleSend()
                  }
                }}
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                loading={chat.loading}
                disabled={!input.trim() || !sessionId || creating}
              >
                发送
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default SupportChatWidget
