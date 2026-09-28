/**
 * 工作助理 - 聊天区域
 *
 * 消息列表 + 欢迎页 + 输入区 + 附件上传 + SSE 流式渲染
 * 使用 useChatStream（SSE）与 useAttachments（上传队列）两个 hook
 */
import React, { useState, useRef, useEffect, useCallback } from 'react'
import { App } from 'antd'
import MessageBubble from './MessageBubble'
import WelcomeView from './WelcomeView'
import ComposerInput from './ComposerInput'
import {
  HermesMessage,
  type HermesAttachment,
  type QuickPrompt,
  getQuickPrompts,
  getSessionAttachments,
} from '@/services/hermes'
import { useChatStream } from '@/hooks/useChatStream'
import { useAttachments } from '@/hooks/useAttachments'
import { useAuthStore } from '@/stores/auth'
import type { CapabilityConfig } from './CapabilityDrawer'

interface ChatAreaProps {
  sessionId: string | null
  messages: HermesMessage[]
  capability: CapabilityConfig
  onNewMessage: (msg: HermesMessage) => void
  onCreateSession: () => Promise<string | null>
  onSwitchSession: (sessionId: string) => void
}

const ChatArea: React.FC<ChatAreaProps> = ({
  sessionId,
  messages,
  capability,
  onNewMessage,
  onCreateSession,
  onSwitchSession,
}) => {
  const { message: antMessage } = App.useApp()
  const token = useAuthStore((state) => state.token)
  const [inputValue, setInputValue] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const { content, loading, error, toolsUsed, send, cancel, reset } = useChatStream()
  const attachments = useAttachments()

  // 稳定化 attachments 中需要在 effect 中引用的函数
  const clearAttachmentsRef = useRef(attachments.clear)
  clearAttachmentsRef.current = attachments.clear

  const [quickPrompts, setQuickPrompts] = useState<QuickPrompt[]>([])
  const [quickLoading, setQuickLoading] = useState(false)
  // 历史消息附件：message_id -> 附件列表
  const [attachmentsByMessage, setAttachmentsByMessage] = useState<
    Record<string, HermesAttachment[]>
  >({})

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])
  useEffect(() => {
    scrollToBottom()
  }, [messages, content, toolsUsed, scrollToBottom])

  // 流式内容结束时，添加助手消息到列表
  useEffect(() => {
    if (!loading && content && !error) {
      const assistantMsg: HermesMessage = {
        id: `stream-${Date.now()}`,
        role: 'assistant',
        content,
        tools_used: toolsUsed.map((t) => ({
          name: t.name,
          args: t.args,
          output: t.output,
        })),
        token_input: 0,
        token_output: 0,
        created_at: new Date().toISOString(),
      }
      onNewMessage(assistantMsg)
      reset()
    }
  }, [loading, content, error, toolsUsed, onNewMessage, reset])

  // 错误处理
  useEffect(() => {
    if (error) antMessage.error(error)
  }, [error, antMessage])

  // 加载快捷提示词（欢迎页推荐卡片）
  useEffect(() => {
    let mounted = true
    setQuickLoading(true)
    getQuickPrompts()
      .then((list) => {
        if (mounted) setQuickPrompts(list)
      })
      .catch(() => undefined)
      .finally(() => {
        if (mounted) setQuickLoading(false)
      })
    return () => {
      mounted = false
    }
  }, [])

  // 会话切换：清空待发送附件 + 重新加载历史附件缩略图
  useEffect(() => {
    clearAttachmentsRef.current()
    setAttachmentsByMessage({})
    if (!sessionId) return
    getSessionAttachments(sessionId)
      .then((list) => {
        const map: Record<string, HermesAttachment[]> = {}
        list.forEach((a) => {
          const mid = a.message_id
          if (!mid) return
          ;(map[mid] ||= []).push(a)
        })
        setAttachmentsByMessage(map)
      })
      .catch(() => undefined)
  }, [sessionId])

  // 发送消息
  const handleSend = useCallback(async () => {
    const text = inputValue.trim()
    if (!text || loading) return

    if (!token) {
      antMessage.error('请先登录')
      return
    }

    // 如果没有会话，先创建
    let activeSessionId = sessionId
    if (!activeSessionId) {
      activeSessionId = await onCreateSession()
      if (!activeSessionId) return
      onSwitchSession(activeSessionId)
    }

    // 收集当前已上传成功的附件
    const currentAttachments = attachments.items
      .filter((i) => i.status === 'success' && i.attachment)
      .map((i) => i.attachment!)
    const attachmentIds = attachments.attachmentIds

    // 清空输入与待发送附件
    setInputValue('')
    attachments.clear()

    // 创建临时用户消息（含附件）用于即时展示
    const tempUserMsg: HermesMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text,
      tools_used: [],
      token_input: 0,
      token_output: 0,
      created_at: new Date().toISOString(),
      attachments: currentAttachments,
    }
    onNewMessage(tempUserMsg)

    // 发送（携带技能 / 工具 / 模型 / 附件）
    send({
      sessionId: activeSessionId,
      message: text,
      token,
      options: {
        model: capability.model,
        skills: capability.skills,
        tools: capability.tools,
      },
      attachmentIds,
    })
  }, [
    inputValue,
    loading,
    sessionId,
    token,
    capability,
    antMessage,
    onNewMessage,
    onCreateSession,
    onSwitchSession,
    send,
    attachments,
  ])

  // 停止生成
  const handleStop = useCallback(() => {
    cancel()
  }, [cancel])

  const showWelcome = messages.length === 0 && !content && !loading

  return (
    <div className="flex flex-col h-full">
      {/* 消息列表 / 欢迎页 */}
      <div className="flex-1 overflow-y-auto p-4">
        {showWelcome ? (
          <WelcomeView
            prompts={quickPrompts}
            onSelectPrompt={(p) => setInputValue(p.content)}
          />
        ) : (
          <div className="max-w-4xl mx-auto space-y-4">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={{
                  ...msg,
                  attachments:
                    attachmentsByMessage[msg.id] || msg.attachments || [],
                }}
              />
            ))}

            {/* 流式输出中 */}
            {loading && (content || toolsUsed.length > 0) && (
              <MessageBubble
                message={{
                  id: 'streaming',
                  role: 'assistant',
                  content: content,
                  tools_used: [],
                  token_input: 0,
                  token_output: 0,
                  created_at: new Date().toISOString(),
                }}
                streaming
                streamingTools={toolsUsed}
              />
            )}

            {/* 加载指示器（无内容且无工具时） */}
            {loading && !content && toolsUsed.length === 0 && (
              <div className="flex items-center gap-2 text-gray-400">
                <div className="animate-pulse">●</div>
                <div className="animate-pulse delay-100">●</div>
                <div className="animate-pulse delay-200">●</div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* 输入区（常驻底部） */}
      <ComposerInput
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSend}
        onStop={handleStop}
        loading={loading}
        token={token}
        attachmentItems={attachments.items}
        onAddFiles={attachments.addFiles}
        onRemoveAttachment={attachments.removeItem}
        quickPrompts={quickPrompts}
        quickPromptsLoading={quickLoading}
        onSelectQuickPrompt={(p) => setInputValue(p.content)}
      />
    </div>
  )
}

export default ChatArea
