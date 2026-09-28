/**
 * AgentTraceDrawer - 智能客服运行日志抽屉
 *
 * 从会话列表点「运行日志」打开，按时间线展示本次 AI 应答经过的图节点
 * （意图路由 / 知识检索 / 工具调用 / 投诉升级 / 汇总回复 / 退货确认）的
 * 详细指标：耗时、模型、token 用量、节点输入/输出，以及工具调用、升级工单与知识引用。
 */

import React from 'react'
import { Drawer, Tag, Empty } from 'antd'
import type {
  AgentTraceStep,
  AgentToolCall,
  AgentTicketInfo,
  SupportMessageTrace,
  SupportReference,
} from '../../types/support'
import ToolCallCard from './ToolCallCard'
import EscalationTicketCard from './EscalationTicketCard'

const NODE_META: Record<string, { label: string; color: string }> = {
  router: { label: '意图路由', color: 'text-indigo-500' },
  knowledge: { label: '知识检索', color: 'text-blue-500' },
  tool: { label: '工具调用', color: 'text-emerald-500' },
  escalation: { label: '投诉升级', color: 'text-orange-500' },
  summary: { label: '汇总回复', color: 'text-violet-500' },
  confirm_return: { label: '退货确认', color: 'text-rose-500' },
}

function formatTokens(tokens?: number | Record<string, number> | null): string {
  if (!tokens) return '—'
  if (typeof tokens === 'number') return String(tokens)
  const p = tokens.prompt_tokens || 0
  const c = tokens.completion_tokens || 0
  const total = tokens.total_tokens || p + c
  return `${total}（in ${p} / out ${c}）`
}

function formatDuration(ms?: number): string {
  if (ms == null) return '—'
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}s`
}

function formatJson(value: unknown): string {
  try {
    const s = JSON.stringify(value)
    return s.length > 400 ? `${s.slice(0, 400)}…` : s
  } catch {
    return String(value)
  }
}

const AgentTraceDrawer: React.FC<{
  open: boolean
  trace: SupportMessageTrace | null | undefined
  onClose: () => void
}> = ({ open, trace, onClose }) => {
  const steps: AgentTraceStep[] = trace?.steps ?? []
  const toolCalls: AgentToolCall[] = trace?.tool_calls ?? []
  const references: SupportReference[] = trace?.references?.references ?? []
  const ticket = trace?.ticket
  const hasContent = steps.length > 0 || toolCalls.length > 0 || !!ticket

  return (
    <Drawer
      title="运行日志（AI 处理过程）"
      open={open}
      onClose={onClose}
      width={460}
      destroyOnClose
    >
      {!hasContent ? (
        <Empty description="暂无运行日志" />
      ) : (
        <div className="space-y-4">
          {steps.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-slate-400">节点执行</div>
              <ol className="space-y-3">
                {steps.map((step: AgentTraceStep, i: number) => {
                  const meta = NODE_META[step.node] || { label: step.node, color: 'text-slate-500' }
                  return (
                    <li key={i} className="rounded-lg border border-slate-100 p-3">
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-semibold ${meta.color}`}>{meta.label}</span>
                        <span className="text-[11px] text-slate-500">{step.summary}</span>
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
                        <Tag>{formatDuration(step.duration_ms)}</Tag>
                        {step.model && <Tag color="purple">{step.model}</Tag>}
                        <Tag color="cyan">tokens {formatTokens(step.tokens)}</Tag>
                      </div>
                      {(step.input != null || step.output != null) && (
                        <div className="mt-2 grid grid-cols-1 gap-1 text-[11px]">
                          {step.input != null && (
                            <div className="flex gap-1">
                              <span className="w-10 flex-shrink-0 text-slate-400">输入</span>
                              <code className="break-all whitespace-pre-wrap text-slate-600">
                                {formatJson(step.input)}
                              </code>
                            </div>
                          )}
                          {step.output != null && (
                            <div className="flex gap-1">
                              <span className="w-10 flex-shrink-0 text-slate-400">输出</span>
                              <code className="break-all whitespace-pre-wrap text-slate-600">
                                {formatJson(step.output)}
                              </code>
                            </div>
                          )}
                        </div>
                      )}
                    </li>
                  )
                })}
              </ol>
            </div>
          )}

          {toolCalls.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-slate-400">工具调用（{toolCalls.length}）</div>
              <div className="space-y-2">
                {toolCalls.map((call: AgentToolCall, i: number) => (
                  <ToolCallCard key={i} call={call} />
                ))}
              </div>
            </div>
          )}

          {ticket && (
            <div>
              <div className="mb-2 text-xs font-medium text-slate-400">升级工单</div>
              <EscalationTicketCard ticket={ticket as AgentTicketInfo} />
            </div>
          )}

          {references.length > 0 && (
            <div>
              <div className="mb-2 text-xs font-medium text-slate-400">知识引用（{references.length}）</div>
              <ul className="space-y-1 text-[11px] text-slate-600">
                {references.map((ref: SupportReference, i: number) => (
                  <li key={i} className="rounded border border-slate-100 p-2">
                    <div className="text-slate-400">
                      {ref.kb_name || ref.document_name || '参考资料'}
                      {typeof ref.score === 'number' ? ` · 分数 ${ref.score.toFixed(2)}` : ''}
                    </div>
                    {ref.content && <div className="mt-0.5 whitespace-pre-wrap">{ref.content}</div>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Drawer>
  )
}

export default AgentTraceDrawer
