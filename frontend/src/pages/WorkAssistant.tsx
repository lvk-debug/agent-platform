/**
 * 工作助理页面
 *
 * 左侧：Agent 会话列表
 * 右侧：聊天区域
 */
import React, { useState, useCallback, useEffect, useMemo } from 'react'
import { App } from 'antd'
import AgentSidebar from '@/components/workassistant/AgentSidebar'
import ChatArea from '@/components/workassistant/ChatArea'
import CapabilityDrawer, {
  CapabilityConfig,
  DEFAULT_CAPABILITY,
} from '@/components/workassistant/CapabilityDrawer'
import {
  HermesSession,
  HermesMessage,
  getSessions,
  createSession,
  deleteSession,
  getMessages,
  updateSessionConfig,
} from '@/services/hermes'

const WorkAssistant: React.FC = () => {
  const { message: antMessage } = App.useApp()
  const [sessions, setSessions] = useState<HermesSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<HermesMessage[]>([])
  const [capability, setCapability] = useState<CapabilityConfig>(DEFAULT_CAPABILITY)
  const [drawerOpen, setDrawerOpen] = useState(false)

  // 本次会话已经命中的工具（用于工具面板的统计回显）
  const usedTools = useMemo(() => {
    const names = new Set<string>()
    messages.forEach((msg) => {
      ;(msg.tools_used || []).forEach((tool) => {
        if (tool?.name) names.add(tool.name)
      })
    })
    return Array.from(names)
  }, [messages])

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    try {
      const data = await getSessions()
      setSessions(data)
    } catch (error) {
      console.error('加载会话列表失败:', error)
    }
  }, [])

  // 加载消息列表
  const loadMessages = useCallback(async (sessionId: string) => {
    try {
      const data = await getMessages(sessionId)
      setMessages(data)
    } catch (error) {
      console.error('加载消息列表失败:', error)
    }
  }, [])

  // 切换会话（同步该会话的能力配置）
  const handleSwitchSession = useCallback(
    (sessionId: string) => {
      setCurrentSessionId(sessionId)
      setMessages([])
      const session = sessions.find((s) => s.id === sessionId)
      setCapability({
        model: session?.model || '',
        skills: session?.skills || [],
        tools: session?.tools || [],
      })
      loadMessages(sessionId)
    },
    [loadMessages, sessions]
  )

  // 创建会话（沿用当前能力配置）
  const handleCreateSession = useCallback(async (): Promise<string | null> => {
    try {
      const session = await createSession(
        '新会话',
        capability.model,
        capability.skills,
        capability.tools
      )
      await loadSessions()
      setCurrentSessionId(session.id)
      setMessages([])
      return session.id
    } catch (error) {
      antMessage.error('创建会话失败')
      return null
    }
  }, [antMessage, loadSessions, capability])

  // 保存能力配置到会话
  const handleSaveCapability = useCallback(
    async (config: CapabilityConfig) => {
      setCapability(config)
      if (!currentSessionId) return
      try {
        await updateSessionConfig(currentSessionId, config)
        await loadSessions()
      } catch (error) {
        antMessage.error('能力配置保存失败，本次会话仍会生效')
      }
    },
    [currentSessionId, loadSessions, antMessage]
  )

  // 删除会话
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      try {
        await deleteSession(sessionId)
        antMessage.success('已删除')
        await loadSessions()
        if (currentSessionId === sessionId) {
          setCurrentSessionId(null)
          setMessages([])
        }
      } catch (error) {
        antMessage.error('删除失败')
      }
    },
    [antMessage, currentSessionId, loadSessions]
  )

  // 添加新消息到列表
  const handleNewMessage = useCallback((msg: HermesMessage) => {
    setMessages((prev) => [...prev, msg])
  }, [])

  // 加载会话列表
  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  return (
    <div className="flex h-full">
      {/* 左侧栏 */}
      <AgentSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        capability={capability}
        onOpenCapability={() => setDrawerOpen(true)}
        onSwitchSession={handleSwitchSession}
        onCreateSession={handleCreateSession}
        onDeleteSession={handleDeleteSession}
        onRefreshSessions={loadSessions}
      />

      {/* 右侧聊天区 */}
      <div className="flex-1">
        <ChatArea
          sessionId={currentSessionId}
          messages={messages}
          capability={capability}
          onNewMessage={handleNewMessage}
          onCreateSession={handleCreateSession}
          onSwitchSession={handleSwitchSession}
        />
      </div>

      {/* 能力设置抽屉 */}
      <CapabilityDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        value={capability}
        usedTools={usedTools}
        onSubmit={handleSaveCapability}
      />
    </div>
  )
}

export default WorkAssistant
