/**
 * MessageBubble - 会话消息气泡
 *
 * 四种角色四种形态：客户左侧浅灰、坐席右侧实色、AI 左侧渐变（带引用与意图）、
 * 系统消息居中弱化为提示条。AI 回答走 Markdown 渲染，保留分点与加粗。
 *
 * 多 Agent 改造：AI 气泡上方可折叠展示「处理过程」——思考链步骤条
 * （AgentTrace）、工具调用卡片（ToolCallCard）、自动升级工单卡片
 * （EscalationTicketCard）。历史消息读 message.trace，流式过程读 draft 字段。
 */

import React, { useState } from 'react'
import { Avatar, Popover, Tag, Tooltip } from 'antd'
import { RobotOutlined, UserOutlined, CustomerServiceOutlined } from '@ant-design/icons'
import ReactMarkdown from 'react-markdown'
import type { SupportMessage, SupportMessageTrace } from '../../types/support'
import AgentTrace from './AgentTrace'
import ToolCallCard from './ToolCallCard'
import EscalationTicketCard from './EscalationTicketCard'

const ROLE_META: Record<string, { name: string; bubble: string; text: string; align: string }> = {
  customer: {
    name: '客户',
    bubble: 'bg-white border border-slate-200 rounded-2xl rounded-tl-sm',
    text: 'text-slate-700',
    align: 'justify-start',
  },
  agent: {
    name: '坐席',
    bubble: 'bg-gradient-to-br from-blue-500 to-blue-600 rounded-2xl rounded-tr-sm',
    text: 'text-white',
    align: 'justify-end',
  },
  ai: {
    name: 'AI 助手',
    bubble: 'bg-gradient-to-br from-indigo-50 to-violet-50 border border-indigo-100 rounded-2xl rounded-tl-sm',
    text: 'text-slate-800',
    align: 'justify-start',
  },
}

function ReferenceList({ references }: { references: SupportMessage['references'] }) {
  if (!references?.length) return null
  return (
    <div className="mt-3 space-y-2">
      {references.map((item, index) => (
        <div
          key={index}
          className="rounded-lg bg-white/70 border border-indigo-100 p-2 text-xs text-slate-600"
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center justify-center w-4 h-4 rounded bg-indigo-100 text-indigo-600 text-[10px] font-semibold">
              {index + 1}
            </span>
            <span className="font-medium text-slate-700 truncate">
              {item.document_name || item.kb_name || '知识库资料'}
            </span>
            {typeof item.score === 'number' && (
              <span className="ml-auto text-[10px] text-slate-400">
                相关度 {(item.score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <p className="line-clamp-3 whitespace-pre-wrap leading-relaxed">{item.content}</p>
        </div>
      ))}
    </div>
  )
}

/** AI 处理过程：思考链 + 工具调用 + 自动工单，可折叠 */
function AgentProcess({ trace }: { trace: SupportMessageTrace }) {
  const hasContent =
    (trace.steps?.length || 0) + (trace.tool_calls?.length || 0) + (trace.ticket ? 1 : 0) > 0
  const [open, setOpen] = useState(true)
  if (!hasContent) return null
  return (
    <div className="mb-1">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="text-[11px] text-indigo-500 hover:text-indigo-600 flex items-center gap-1 mb-1"
      >
        <span>🧠</span>
        {open ? '收起' : '展开'} AI 思考过程（{trace.steps?.length || 0} 步）
      </button>
      {open && (
        <div className="space-y-1.5">
          <AgentTrace steps={trace.steps || []} />
          {(trace.tool_calls || []).map((call, i) => (
            <ToolCallCard key={i} call={call} />
          ))}
          {trace.ticket && <EscalationTicketCard ticket={trace.ticket} />}
        </div>
      )}
    </div>
  )
}

interface MessageBubbleProps {
  message: SupportMessage
  /** 流式中的临时气泡：内容来自 draft，还没落库 */
  streaming?: boolean
  draftContent?: string
  draftReferences?: SupportMessage['references']
  draftMeta?: { intentLabel: string; confidence: number }
  /** 流式中的 Agent 处理过程（thought / tool_call / ticket） */
  draftThoughts?: SupportMessageTrace['steps']
  draftToolCalls?: SupportMessageTrace['tool_calls']
  draftTicket?: SupportMessageTrace['ticket']
  /** 打开评测/处理过程检视抽屉 */
  onEvaluate?: (message: SupportMessage) => void
  /** 打开人工打分弹窗 */
  onScore?: (message: SupportMessage) => void
}

const MessageBubble: React.FC<MessageBubbleProps> = ({
  message,
  streaming,
  draftContent,
  draftReferences,
  draftMeta,
  draftThoughts,
  draftToolCalls,
  draftTicket,
  onEvaluate,
  onScore,
}) => {
  if (message.role === 'system') {
    return (
      <div className="flex justify-center my-3">
        <span className="px-3 py-1 rounded-full bg-amber-50 text-amber-700 text-xs border border-amber-100">
          {message.content}
        </span>
      </div>
    )
  }

  const meta = ROLE_META[message.role] || ROLE_META.customer
  const content = streaming ? draftContent || '' : message.content
  const references = streaming ? draftReferences : message.references
  const isAgent = message.role === 'agent'
  const isAI = message.role === 'ai'

  // 流式过程优先用 draft，落库后用 message.trace
  const trace: SupportMessageTrace | undefined = isAI
    ? streaming
      ? { steps: draftThoughts || [], tool_calls: draftToolCalls || [], ticket: draftTicket || null }
      : message.trace || undefined
    : undefined

  const avatar = isAgent ? (
    <Avatar size={32} className="bg-blue-500" icon={<CustomerServiceOutlined />} />
  ) : isAI ? (
    <Avatar size={32} className="bg-gradient-to-br from-indigo-500 to-violet-500" icon={<RobotOutlined />} />
  ) : (
    <Avatar size={32} className="bg-slate-300" icon={<UserOutlined />} />
  )

  return (
    <div className={`flex gap-2 ${meta.align} ${isAgent ? 'flex-row-reverse' : ''}`}>
      <div className="flex-shrink-0 mt-1">{avatar}</div>
      <div className={`max-w-[78%] ${isAgent ? 'items-end' : 'items-start'} flex flex-col`}>
        <div className="flex items-center gap-2 mb-1 px-1">
          <span className="text-xs text-slate-400">{meta.name}</span>
          {isAI && !streaming && message.model && (
            <span className="text-[10px] text-slate-300">{message.model}</span>
          )}
          {isAI && (streaming ? draftMeta?.intentLabel : message.intent_label) && (
            <Tag color="indigo" className="!m-0 !text-[10px] !leading-4">
              {streaming ? draftMeta?.intentLabel : message.intent_label}
            </Tag>
          )}
          {isAI && !streaming && typeof message.latency_ms === 'number' && (
            <span className="text-[10px] text-slate-300">{message.latency_ms}ms</span>
          )}
        </div>

        {isAI && trace && <AgentProcess trace={trace} />}

        <div className={`px-4 py-2.5 shadow-sm ${meta.bubble} ${meta.text}`}>
          {message.error ? (
            <span className="text-red-500 text-sm">{message.error}</span>
          ) : isAI ? (
            <div className="text-sm leading-relaxed prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1">
              <ReactMarkdown>{content || ' '}</ReactMarkdown>
              {streaming && (
                <span className="inline-block w-1.5 h-4 ml-0.5 bg-indigo-400 animate-pulse align-middle" />
              )}
            </div>
          ) : (
            <div className="text-sm leading-relaxed whitespace-pre-wrap">
              {content}
              {streaming && (
                <span className="inline-block w-1.5 h-4 ml-0.5 bg-current animate-pulse align-middle" />
              )}
            </div>
          )}

          {references && references.length > 0 && (
            <div className={isAgent ? 'text-slate-100' : ''}>
              {isAgent ? (
                <Popover
                  content={
                    <div className="w-72 text-slate-600">
                      <ReferenceList references={references} />
                    </div>
                  }
                  title="引用来源"
                >
                  <span className="text-xs opacity-80 cursor-pointer underline decoration-dotted">
                    {references.length} 条引用
                  </span>
                </Popover>
              ) : (
                <ReferenceList references={references} />
              )}
            </div>
          )}
        </div>

        {isAI && !streaming && typeof message.confidence === 'number' && message.confidence > 0 && (
          <Tooltip title="AI 对本次意图判断的置信度">
            <span className="mt-1 px-1 text-[10px] text-slate-300">
              置信度 {(message.confidence * 100).toFixed(0)}%
            </span>
          </Tooltip>
        )}

        {isAI && !streaming && (onEvaluate || onScore) && (
          <div className="mt-1 flex items-center gap-2 px-1">
            {onEvaluate && (
              <button
                type="button"
                onClick={() => onEvaluate(message)}
                className="text-[11px] text-indigo-500 hover:text-indigo-600 border border-indigo-100 rounded px-2 py-0.5 hover:bg-indigo-50 transition-colors"
              >
                查看评测 / 过程
              </button>
            )}
            {onScore && (
              <button
                type="button"
                onClick={() => onScore(message)}
                className="text-[11px] text-violet-500 hover:text-violet-600 border border-violet-100 rounded px-2 py-0.5 hover:bg-violet-50 transition-colors"
              >
                人工打分
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default MessageBubble
