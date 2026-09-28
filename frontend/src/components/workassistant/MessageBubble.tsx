/**
 * 工作助理 - 消息气泡组件
 *
 * 支持纯字符串 content 渲染 + 工具调用展示 + 用户附件展示
 * 用户消息右对齐 / 助手消息左对齐
 */
import React, { useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Typography, Tag } from 'antd'
import {
  UserOutlined,
  RobotOutlined,
  ToolOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { HermesMessage, type HermesAttachment } from '@/services/hermes'
import { ToolCall } from '@/hooks/useChatStream'
import { AttachmentImage } from './AttachmentChips'
import { getFileIcon } from '@/utils/fileIcons'
import { useAuthStore } from '@/stores/auth'

const { Text } = Typography

interface MessageBubbleProps {
  message: HermesMessage
  streaming?: boolean
  /** 流式输出时的实时工具调用列表 */
  streamingTools?: ToolCall[]
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  streaming,
  streamingTools,
}) => {
  const isUser = message.role === 'user'
  const token = useAuthStore((state) => state.token)
  const attachments: HermesAttachment[] = message.attachments || []
  const [expandedTools, setExpandedTools] = useState<Record<number, boolean>>({})

  // 工具调用列表（流式用 streamingTools，完成后用 message.tools_used）
  const tools = streaming ? streamingTools || [] : message.tools_used || []
  const hasTools = tools.length > 0

  const toggleTool = (index: number) => {
    setExpandedTools((prev) => ({ ...prev, [index]: !prev[index] }))
  }

  // 渲染工具调用列表
  const renderTools = () => {
    if (!hasTools) return null

    return (
      <div className="mt-2 space-y-1">
        {tools.map((tool, index) => {
          const isRunning =
            'status' in tool && (tool as ToolCall).status === 'running'
          const isDone =
            !('status' in tool) || (tool as ToolCall).status === 'done'
          const isExpanded = expandedTools[index]

          return (
            <div
              key={index}
              className="bg-gray-50 rounded-md border border-gray-200 text-xs"
            >
              {/* 工具头部 */}
              <div
                className="flex items-center gap-2 px-2 py-1.5 cursor-pointer hover:bg-gray-100 transition-colors"
                onClick={() => toggleTool(index)}
              >
                {isRunning ? (
                  <LoadingOutlined className="text-blue-500" spin />
                ) : (
                  <CheckCircleOutlined className="text-green-500" />
                )}
                <ToolOutlined className="text-gray-500" />
                <Text className="text-xs font-medium text-gray-700 flex-1">
                  {tool.name}
                </Text>
                {isRunning && (
                  <Tag color="processing" className="text-xs">
                    执行中
                  </Tag>
                )}
                {isDone && (
                  <Tag color="success" className="text-xs">
                    完成
                  </Tag>
                )}
                <DownOutlined
                  className={`text-gray-400 transition-transform text-xs ${
                    isExpanded ? 'rotate-180' : ''
                  }`}
                />
              </div>

              {/* 工具详情（展开时显示） */}
              {isExpanded && (
                <div className="px-2 pb-2 border-t border-gray-100">
                  {tool.args && (
                    <div className="mt-1">
                      <Text className="text-xs text-gray-500">参数：</Text>
                      <pre className="text-xs bg-gray-100 rounded p-1 mt-0.5 overflow-x-auto max-h-24 overflow-y-auto">
                        {tool.args}
                      </pre>
                    </div>
                  )}
                  {tool.output && (
                    <div className="mt-1">
                      <Text className="text-xs text-gray-500">结果：</Text>
                      <pre className="text-xs bg-gray-100 rounded p-1 mt-0.5 overflow-x-auto max-h-32 overflow-y-auto">
                        {tool.output}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  // 渲染用户附件（图片缩略图 + 文件名）
  const renderAttachments = () => {
    if (!isUser || attachments.length === 0) return null
    return (
      <div className="mb-2 space-y-1.5">
        {attachments.map((att) => (
          <div key={att.id} className="flex items-center gap-2">
            {att.kind === 'image' ? (
              <AttachmentImage id={att.id} token={token} />
            ) : (
              <span className="text-lg text-blue-200">
                {getFileIcon(att.filename)}
              </span>
            )}
            <span className="text-xs text-white/90 max-w-[200px] truncate">
              {att.filename}
            </span>
            {att.parse_status === 'failed' && (
              <Tag color="warning" className="text-xs">
                解析失败
              </Tag>
            )}
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* 头像 */}
      <div
        className={`
          flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${isUser ? 'bg-blue-500' : 'bg-gray-200'}
        `}
      >
        {isUser ? (
          <UserOutlined className="text-white text-sm" />
        ) : (
          <RobotOutlined className="text-gray-600 text-sm" />
        )}
      </div>

      {/* 消息内容 */}
      <div
        className={`
          max-w-[70%] rounded-lg px-4 py-2
          ${isUser ? 'bg-blue-500 text-white' : 'bg-gray-100 text-gray-800'}
        `}
      >
        {/* 工具调用区域（助手消息显示在内容上方） */}
        {!isUser && renderTools()}

        {/* 用户附件（显示在文本上方） */}
        {renderAttachments()}

        {/* 消息文本：助手消息用 Markdown 渲染，用户消息纯文本 */}
        {isUser ? (
          <Text className="whitespace-pre-wrap text-white">
            {message.content}
          </Text>
        ) : (
          <div className="prose prose-sm max-w-none break-words
            prose-pre:bg-gray-800 prose-pre:text-gray-100 prose-pre:rounded-md prose-pre:p-3 prose-pre:overflow-x-auto
            prose-code:before:content-none prose-code:after:content-none
            prose-code:bg-gray-200 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-xs
            prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1
            prose-th:border prose-td:border prose-th:bg-gray-50
            prose-ul:list-disc prose-ol:list-decimal prose-li:my-0.5
            prose-p:my-1 prose-headings:my-2
            prose-a:text-blue-600 prose-a:underline
            prose-blockquote:border-l-4 prose-blockquote:border-gray-300 prose-blockquote:pl-3 prose-blockquote:italic prose-blockquote:text-gray-600">
            <Markdown remarkPlugins={[remarkGfm]}>
              {message.content || ''}
            </Markdown>
          </div>
        )}
        {streaming && <span className="animate-pulse ml-1">▍</span>}

        {/* 流式加载指示器（无内容且无工具时） */}
        {streaming && !message.content && !hasTools && (
          <div className="flex items-center gap-1 text-gray-400">
            <LoadingOutlined spin />
            <Text className="text-xs text-gray-400">思考中...</Text>
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
