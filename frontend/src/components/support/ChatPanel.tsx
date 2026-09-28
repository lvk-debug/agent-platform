/**
 * ChatPanel - 对话区（坐席工作台中栏）
 *
 * 两个模式共用一套输入：
 * - AI 模式：坐席录入客户诉求 → 机器人检索知识库流式回答
 * - 人工模式：坐席直接回复客户，AI 退到「建议回复」
 *
 * 顶部常驻模式开关与转人工/建单/结单入口，保证坐席不用来回切页面。
 */

import React, { useEffect, useRef, useState } from 'react'
import {
  Button,
  Drawer,
  Dropdown,
  Empty,
  Input,
  message as antdMessage,
  Modal,
  Rate,
  Segmented,
  Space,
  Tag,
  Tooltip,
} from 'antd'
import {
  BulbOutlined,
  FileTextOutlined,
  MessageOutlined,
  PauseCircleOutlined,
  SendOutlined,
  StopOutlined,
  ThunderboltOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons'
import MessageBubble from './MessageBubble'
import ManualScoreModal from './ManualScoreModal'
import AgentTrace from './AgentTrace'
import ToolCallCard from './ToolCallCard'
import EscalationTicketCard from './EscalationTicketCard'
import supportApi from '../../services/support'
import SuggestionCard from './SuggestionCard'
import TransferHumanModal from './TransferHumanModal'
import type {
  AgentTicketInfo,
  AgentToolCall,
  AgentTraceStep,
  QuickReply,
  SupportEvaluation,
  SupportMessage,
  SupportReference,
  SupportSession,
} from '../../types/support'

const EVAL_DIMS: { key: 'accuracy' | 'helpfulness' | 'safety' | 'fluency'; label: string }[] = [
  { key: 'accuracy', label: '准确性' },
  { key: 'helpfulness', label: '帮助性' },
  { key: 'safety', label: '安全性' },
  { key: 'fluency', label: '流畅性' },
]

// 自动评测指标：后端已由四维度 LLM 裁判改为 DeepEval 指标
const DEEPEVAL_DIMS: { key: string; label: string }[] = [
  { key: 'answer_relevancy', label: '答案相关性' },
  { key: 'faithfulness', label: '忠实度' },
  { key: 'contextual_relevancy', label: '上下文相关性' },
  { key: 'safety_geval', label: '安全性' },
  { key: 'helpfulness_geval', label: '帮助性' },
  { key: 'accuracy_geval', label: '准确性' },
]

interface ChatPanelProps {
  session: SupportSession | null
  messages: SupportMessage[]
  loading: boolean
  streaming: boolean
  draftContent: string
  draftReferences: SupportReference[]
  draftMeta: { intentLabel: string; confidence: number; suggestHuman: boolean }
  draftThoughts?: AgentTraceStep[]
  draftToolCalls?: AgentToolCall[]
  draftTicket?: AgentTicketInfo | null
  suggestHuman: boolean
  quickReplies: QuickReply[]
  suggestion: { content: string; references: SupportReference[]; error: string | null }
  suggesting: boolean
  onSend: (query: string) => void
  onSendAgent: (content: string) => void
  onCancelStream: () => void
  onSwitchMode: (mode: 'ai' | 'human') => void
  onTakeOver: (reason: string) => Promise<void>
  onSuggest: () => void
  onDiscardSuggestion: () => void
  onOpenTicket: () => void
  onClose: (payload: { status: 'resolved' | 'closed'; satisfaction?: number; satisfaction_comment?: string }) => Promise<void>
}

const ChatPanel: React.FC<ChatPanelProps> = ({
  session,
  messages,
  loading,
  streaming,
  draftContent,
  draftReferences,
  draftMeta,
  draftThoughts,
  draftToolCalls,
  draftTicket,
  suggestHuman,
  quickReplies,
  suggestion,
  suggesting,
  onSend,
  onSendAgent,
  onCancelStream,
  onSwitchMode,
  onTakeOver,
  onSuggest,
  onDiscardSuggestion,
  onOpenTicket,
  onClose,
}) => {
  const [input, setInput] = useState('')
  const [transferOpen, setTransferOpen] = useState(false)
  const [closeOpen, setCloseOpen] = useState(false)
  const [satisfaction, setSatisfaction] = useState<number>(5)
  const [closeComment, setCloseComment] = useState('')
  const [closeStatus, setCloseStatus] = useState<'resolved' | 'closed'>('resolved')
  const scrollRef = useRef<HTMLDivElement>(null)

  // 新消息与流式内容都会撑高内容区，统一在变化时贴底
  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, draftContent, streaming])

  useEffect(() => {
    setInput('')
  }, [session?.id])

  const isHuman = session?.mode === 'human'
  const finished = session?.status === 'resolved' || session?.status === 'closed'

  const handleSend = () => {
    const text = input.trim()
    if (!text || !session) return
    if (isHuman) {
      void onSendAgent(text)
    } else {
      onSend(text)
    }
    setInput('')
  }

  const handleTakeOver = async (reason: string) => {
    await onTakeOver(reason)
    setTransferOpen(false)
  }

  const handleClose = async () => {
    await onClose({
      status: closeStatus,
      satisfaction,
      satisfaction_comment: closeComment || undefined,
    })
    setCloseOpen(false)
  }

  // ---------------- 评测：处理过程检视 + 人工打分 ----------------
  const [evalMsg, setEvalMsg] = useState<SupportMessage | null>(null)
  const [evalData, setEvalData] = useState<SupportEvaluation | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalOpen, setEvalOpen] = useState(false)
  const [scoreOpen, setScoreOpen] = useState(false)
  const [scoreMsg, setScoreMsg] = useState<SupportMessage | null>(null)
  const [evaluating, setEvaluating] = useState(false)

  const handleEvaluate = async (msg: SupportMessage) => {
    setEvalMsg(msg)
    setEvalOpen(true)
    setEvalLoading(true)
    setEvalData(null)
    try {
      setEvalData(await supportApi.getEvaluation(msg.id))
    } catch {
      setEvalData(null)
    } finally {
      setEvalLoading(false)
    }
  }

  const handleScoreOpen = (msg: SupportMessage) => {
    setScoreMsg(msg)
    setScoreOpen(true)
  }

  const handleScored = (messageId: number) => {
    // 打分后刷新抽屉里的评测数据（若存在）
    if (evalMsg && evalMsg.id === messageId) void handleEvaluate(evalMsg)
  }

  const handleEvaluateSession = async () => {
    if (!session) return
    setEvaluating(true)
    try {
      const res = await supportApi.evaluateSession(session.id)
      antdMessage.success(`已自动评测 ${res.done} 条 AI 回答`)
    } catch (err) {
      console.error('自动评测会话失败:', err)
      antdMessage.error('自动评测失败，请重试')
    } finally {
      setEvaluating(false)
    }
  }

  if (!session) {
    return (
      <div className="h-full flex items-center justify-center bg-white rounded-xl border border-slate-200">
        <Empty description="从左侧选择一个会话开始处理" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* 顶部信息栏 */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3 flex-wrap">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-slate-800 truncate">
              {session.title || (session.customer_name ? `${session.customer_name} 的咨询` : '未命名会话')}
            </span>
            <Tag color={session.status === 'pending_human' ? 'orange' : session.status === 'open' ? 'green' : 'default'}>
              {session.status_label}
            </Tag>
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            {session.customer_name ? `客户：${session.customer_name} · ` : ''}
            {session.intent_label ? `意图：${session.intent_label} · ` : ''}
            {session.assignee_name ? `负责人：${session.assignee_name}` : '未接管'}
          </div>
        </div>

        <div className="ml-auto flex items-center gap-2">
          <Segmented
            size="small"
            value={session.mode}
            onChange={(value) => onSwitchMode(value as 'ai' | 'human')}
            options={[
              { label: 'AI 模式', value: 'ai' },
              { label: '人工模式', value: 'human' },
            ]}
          />
          <Tooltip title="转人工">
            <Button
              size="small"
              icon={<UserSwitchOutlined />}
              onClick={() => setTransferOpen(true)}
              disabled={finished}
            >
              转人工
            </Button>
          </Tooltip>
          <Tooltip title="创建工单">
            <Button size="small" icon={<FileTextOutlined />} onClick={onOpenTicket}>
              建单
            </Button>
          </Tooltip>
          <Button
            size="small"
            icon={<PauseCircleOutlined />}
            onClick={() => setCloseOpen(true)}
            disabled={finished}
          >
            结束
          </Button>
          <Tooltip title="对本会话全部未评的 AI 回答自动打分">
            <Button
              size="small"
              icon={<ThunderboltOutlined />}
              loading={evaluating}
              onClick={handleEvaluateSession}
              disabled={finished}
            >
              自动评测
            </Button>
          </Tooltip>
        </div>
      </div>

      {/* 消息区 */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-slate-50/40">
        {messages.length === 0 && !streaming && (
          <div className="text-center text-xs text-slate-400 py-10">
            还没有消息，录入客户诉求后由 AI 先答一版
          </div>
        )}
        {messages.map((item) => (
          <MessageBubble
            key={item.id}
            message={item}
            onEvaluate={item.role === 'ai' ? handleEvaluate : undefined}
            onScore={item.role === 'ai' ? handleScoreOpen : undefined}
          />
        ))}
        {streaming && (
          <MessageBubble
            message={{
              id: -1,
              session_id: session.id,
              role: 'ai',
              content: '',
              references: [],
              created_at: new Date().toISOString(),
            }}
            streaming
            draftContent={draftContent}
            draftReferences={draftReferences}
            draftMeta={draftMeta}
            draftThoughts={draftThoughts}
            draftToolCalls={draftToolCalls}
            draftTicket={draftTicket}
          />
        )}
      </div>

      {/* 输入区 */}
      <div className="border-t border-slate-100 p-3">
        {(suggestion.content || suggestion.error || suggesting) && (
          <SuggestionCard
            content={suggestion.content}
            references={suggestion.references}
            loading={suggesting}
            error={suggestion.error}
            onAdopt={(content) => setInput(content)}
            onDiscard={onDiscardSuggestion}
          />
        )}

        {suggestHuman && !streaming && (
          <div className="mb-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-200 text-xs text-amber-700 flex items-center gap-2">
            <ThunderboltOutlined />
            AI 建议转人工处理，避免给出不准确的承诺
            <Button size="small" type="link" onClick={() => setTransferOpen(true)}>
              立即转人工
            </Button>
          </div>
        )}

        <div className="flex items-end gap-2">
          <Dropdown
            menu={{
              items: quickReplies.map((item, index) => ({
                key: index,
                label: item.title,
                onClick: () => setInput((prev) => (prev ? `${prev}\n${item.content}` : item.content)),
              })),
            }}
            disabled={quickReplies.length === 0}
          >
            <Button icon={<MessageOutlined />} />
          </Dropdown>
          {isHuman && (
            <Tooltip title="让 AI 起草一版回复">
              <Button icon={<BulbOutlined />} onClick={onSuggest} loading={suggesting} />
            </Tooltip>
          )}

          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              isHuman ? '直接回复客户，Enter 发送 / Shift+Enter 换行' : '录入客户诉求，Enter 交给 AI 回答'
            }
            autoSize={{ minRows: 1, maxRows: 5 }}
            disabled={finished}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />

          {streaming ? (
            <Button danger icon={<StopOutlined />} onClick={onCancelStream}>
              停止
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              loading={loading}
              disabled={!input.trim() || finished}
            >
              发送
            </Button>
          )}
        </div>
      </div>

      <TransferHumanModal
        open={transferOpen}
        onCancel={() => setTransferOpen(false)}
        onOk={handleTakeOver}
      />

      <Modal
        title="结束会话"
        open={closeOpen}
        onCancel={() => setCloseOpen(false)}
        onOk={handleClose}
        okText="确认结束"
        cancelText="取消"
      >
        <Space direction="vertical" className="w-full" size="middle">
          <div>
            <div className="text-sm text-slate-600 mb-1">结束方式</div>
            <Segmented
              value={closeStatus}
              onChange={(value) => setCloseStatus(value as 'resolved' | 'closed')}
              options={[
                { label: '标记为已解决', value: 'resolved' },
                { label: '直接关闭归档', value: 'closed' },
              ]}
            />
          </div>
          <div>
            <div className="text-sm text-slate-600 mb-1">客户满意度</div>
            <Rate value={satisfaction} onChange={setSatisfaction} />
          </div>
          <Input.TextArea
            rows={2}
            placeholder="备注（可选）"
            value={closeComment}
            onChange={(e) => setCloseComment(e.target.value)}
            maxLength={500}
          />
        </Space>
      </Modal>

      {/* 评测 / 处理过程检视抽屉 */}
      <Drawer
        title="评测 / 处理过程"
        open={evalOpen}
        onClose={() => setEvalOpen(false)}
        width={440}
      >
        {evalMsg && (
          <div className="space-y-4">
            <div>
              <div className="text-xs text-slate-400 mb-1">{evalMsg.intent_label || 'AI 回答'}</div>
              <div className="text-sm text-slate-700 bg-slate-50 rounded p-3 whitespace-pre-wrap max-h-48 overflow-auto">
                {evalMsg.content || '（内容为空）'}
              </div>
            </div>

            {(evalMsg.trace?.steps?.length || evalMsg.trace?.tool_calls?.length || evalMsg.trace?.ticket) && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">处理过程（Trace）</div>
                <div className="space-y-2">
                  <AgentTrace steps={evalMsg.trace?.steps || []} />
                  {(evalMsg.trace?.tool_calls || []).map((call, i) => (
                    <ToolCallCard key={i} call={call} />
                  ))}
                  {evalMsg.trace?.ticket && <EscalationTicketCard ticket={evalMsg.trace.ticket} />}
                </div>
              </div>
            )}

            <div>
              <div className="text-sm font-medium text-slate-700 mb-2">自动评测（DeepEval）</div>
              {evalLoading ? (
                <span className="text-xs text-slate-400">加载中…</span>
              ) : evalData?.deepeval_scores || evalData?.auto_scores ? (
                <div className="space-y-2">
                  {DEEPEVAL_DIMS.map((d) => {
                    const score =
                      evalData?.deepeval_scores?.[d.key] ?? evalData?.auto_scores?.[d.key] ?? 0
                    return (
                      <div key={d.key} className="flex items-center gap-2">
                        <span className="w-16 text-xs text-slate-500">{d.label}</span>
                        <Rate disabled value={Math.round(score * 5)} />
                        <span className="text-xs text-slate-400">{Math.round(score * 100)}</span>
                      </div>
                    )
                  })}
                  <div className="text-xs text-slate-500">
                    综合：
                    {(evalData?.deepeval_overall ?? evalData?.auto_overall) != null
                      ? Math.round(
                          (evalData?.deepeval_overall ?? evalData?.auto_overall ?? 0) * 100
                        )
                      : '—'}
                    {evalData?.status ? `（${evalData.status}）` : ''}
                  </div>
                  {evalData?.deepeval_reasoning && (
                    <div className="text-xs text-slate-400 mt-1 whitespace-pre-wrap">
                      {evalData.deepeval_reasoning}
                    </div>
                  )}
                </div>
              ) : (
                <span className="text-xs text-slate-400">
                  尚未自动评测（可在对话区点「自动评测」或在质量看板触发）
                </span>
              )}
            </div>

            {evalData?.manual_scores && (
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">人工打分</div>
                <div className="space-y-2">
                  {EVAL_DIMS.map((d) => (
                    <div key={d.key} className="flex items-center gap-2">
                      <span className="w-12 text-xs text-slate-500">{d.label}</span>
                      <Rate disabled value={Math.round((evalData.manual_scores?.[d.key] || 0) * 5)} />
                    </div>
                  ))}
                  {evalData.annotator_name && (
                    <div className="text-xs text-slate-400">标注人：{evalData.annotator_name}</div>
                  )}
                  {evalData.comment && <div className="text-xs text-slate-400 mt-1">{evalData.comment}</div>}
                </div>
              </div>
            )}

            <Button type="primary" onClick={() => evalMsg && handleScoreOpen(evalMsg)}>
              人工打分
            </Button>
          </div>
        )}
      </Drawer>

      {/* 人工打分弹窗 */}
      <ManualScoreModal
        open={scoreOpen}
        message={scoreMsg}
        onCancel={() => setScoreOpen(false)}
        onSubmitted={handleScored}
      />
    </div>
  )
}

export default ChatPanel
