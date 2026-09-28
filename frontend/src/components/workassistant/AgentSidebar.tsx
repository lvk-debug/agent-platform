/**
 * 工作助理 - 左侧栏
 *
 * Agents 列表 + 会话历史 + 新建对话
 */
import React, { useEffect } from 'react'
import { Button, Typography, Popconfirm, Space, Tag } from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  RobotOutlined,
  MessageOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { HermesSession } from '@/services/hermes'
import type { CapabilityConfig } from './CapabilityDrawer'

const { Text } = Typography

interface AgentSidebarProps {
  sessions: HermesSession[]
  currentSessionId: string | null
  capability: CapabilityConfig
  onOpenCapability: () => void
  onSwitchSession: (sessionId: string) => void
  onCreateSession: () => void
  onDeleteSession: (sessionId: string) => void
  onRefreshSessions: () => void
}

const AgentSidebar: React.FC<AgentSidebarProps> = ({
  sessions,
  currentSessionId,
  capability,
  onOpenCapability,
  onSwitchSession,
  onCreateSession,
  onDeleteSession,
  onRefreshSessions,
}) => {
  useEffect(() => {
    onRefreshSessions()
  }, [onRefreshSessions])

  return (
    <div className="w-64 border-r border-gray-200 flex flex-col bg-gray-50">
      {/* 顶部标题 */}
      <div className="p-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <Text strong className="text-base">
            工作助理
          </Text>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            size="small"
            onClick={onCreateSession}
          >
            新建
          </Button>
        </div>
      </div>

      {/* 能力设置入口 */}
      <button
        type="button"
        onClick={onOpenCapability}
        className="mx-2 mt-2 flex items-center justify-between px-3 py-2 rounded-lg border border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50 transition-all duration-150"
      >
        <span className="flex items-center gap-2 text-sm text-gray-700">
          <SettingOutlined className="text-blue-600" />
          能力设置
        </span>
        <span className="flex items-center gap-1">
          {capability.skills.length > 0 && (
            <Tag color="blue" className="!mr-0">
              技能 {capability.skills.length}
            </Tag>
          )}
          {capability.tools.length > 0 && (
            <Tag color="cyan" className="!mr-0">
              工具 {capability.tools.length}
            </Tag>
          )}
          {capability.model && (
            <Tag className="!mr-0 max-w-[72px] truncate">{capability.model}</Tag>
          )}
        </span>
      </button>

      {/* 会话列表 */}
      <div className="flex-1 overflow-y-auto p-2">
        {sessions.length === 0 ? (
          <div className="text-center text-gray-400 mt-8">
            <MessageOutlined className="text-3xl mb-2" />
            <div>暂无会话</div>
          </div>
        ) : (
          <Space direction="vertical" className="w-full" size={4}>
            {sessions.map((session) => (
              <div
                key={session.id}
                className={`
                  group flex items-center justify-between p-3 rounded-lg cursor-pointer
                  transition-colors duration-150
                  ${
                    currentSessionId === session.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-100 border border-transparent'
                  }
                `}
                onClick={() => onSwitchSession(session.id)}
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <RobotOutlined className="text-gray-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium truncate">
                      {session.title || `会话 ${session.id.slice(0, 8)}`}
                    </div>
                    <div className="text-xs text-gray-400 truncate">
                      {session.model || '默认模型'}
                    </div>
                  </div>
                </div>
                <Popconfirm
                  title="确定删除此会话？"
                  onConfirm={(e) => {
                    e?.stopPropagation()
                    onDeleteSession(session.id)
                  }}
                  onCancel={(e) => e?.stopPropagation()}
                  okText="删除"
                  cancelText="取消"
                >
                  <DeleteOutlined
                    className="text-gray-400 opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity"
                    onClick={(e) => e.stopPropagation()}
                  />
                </Popconfirm>
              </div>
            ))}
          </Space>
        )}
      </div>

      {/* 底部信息 */}
      <div className="p-3 border-t border-gray-200 text-center">
        <Text type="secondary" className="text-xs">
          共 {sessions.length} 个会话
        </Text>
      </div>
    </div>
  )
}

export default AgentSidebar
