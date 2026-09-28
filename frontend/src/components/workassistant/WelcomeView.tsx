/**
 * 欢迎视图 - 无消息时居中展示
 *
 * 机器人标识 + 问候语 + 推荐任务卡片网格 + 「换一批」入口。
 * 点击卡片 → 把提示词内容填入输入框（聚焦，不自动发送）。
 */
import { useState } from 'react'
import { Avatar, Card, Button, Typography } from 'antd'
import { RobotOutlined, ReloadOutlined } from '@ant-design/icons'
import type { QuickPrompt } from '@/services/hermes'
import { PromptIcon } from './QuickPromptPanel'

const { Text } = Typography

export interface WelcomeViewProps {
  prompts: QuickPrompt[]
  onSelectPrompt: (p: QuickPrompt) => void
}

export default function WelcomeView({
  prompts,
  onSelectPrompt,
}: WelcomeViewProps) {
  const [shuffled, setShuffled] = useState(false)
  // 仅展示前 4 张；点「换一批」翻到后 4 张（如有）
  const base = shuffled ? prompts.slice(4) : prompts.slice(0, 4)
  const shown = base.length ? base : prompts.slice(0, 4)

  return (
    <div className="flex flex-col items-center justify-center h-full px-4 text-center">
      {/* 机器人标识 */}
      <div className="w-20 h-20 rounded-full bg-gradient-to-br from-blue-50 to-gray-100 flex items-center justify-center shadow-sm">
        <Avatar size={56} icon={<RobotOutlined />} className="bg-blue-500" />
      </div>

      <h1 className="mt-6 text-2xl font-semibold text-gray-800">
        有什么我能帮你的吗?
      </h1>
      <Text type="secondary" className="mt-1">
        添加文件或图片作为上下文，或选择一个常用任务开始
      </Text>

      {/* 推荐任务卡片 */}
      {shown.length > 0 && (
        <div className="mt-8 w-full max-w-2xl">
          <div className="flex items-center justify-between mb-3">
            <Text className="text-sm text-gray-500">推荐任务</Text>
            {prompts.length > 4 && (
              <Button
                type="text"
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => setShuffled((s) => !s)}
              >
                换一批
              </Button>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {shown.map((p) => (
              <Card
                key={p.id}
                hoverable
                onClick={() => onSelectPrompt(p)}
                className="text-left transition-all duration-150 hover:-translate-y-0.5 hover:border-blue-400"
                styles={{ body: { padding: '14px 16px' } }}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xl text-blue-500">
                    <PromptIcon name={p.icon} />
                  </span>
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-800">
                      {p.title}
                    </div>
                    <div className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                      {p.description || p.content}
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
