/**
 * EscalationTicketCard - 自动工单卡片
 *
 * Escalation Agent 由 LLM 生成结构化工单后，前端以醒目卡片呈现工单号、类型、
 * 优先级与摘要，并提示已升级人工处理。
 */

import React from 'react'
import { SolutionOutlined } from '@ant-design/icons'
import type { AgentTicketInfo } from '../../types/support'

const PRIORITY_COLOR: Record<string, string> = {
  high: 'bg-red-100 text-red-600',
  urgent: 'bg-red-100 text-red-600',
  normal: 'bg-blue-100 text-blue-600',
  low: 'bg-slate-100 text-slate-500',
}

const EscalationTicketCard: React.FC<{ ticket: AgentTicketInfo }> = ({ ticket }) => (
  <div className="mt-2 rounded-xl border border-orange-200 bg-orange-50/70 p-3">
    <div className="flex items-center gap-2 mb-1">
      <SolutionOutlined className="text-orange-500" />
      <span className="text-xs font-semibold text-orange-700">已为您升级工单</span>
      <span className="ml-auto text-xs font-mono font-medium text-orange-600">
        {ticket.ticket_no}
      </span>
    </div>
    <div className="text-sm text-slate-700 mb-1.5">{ticket.title}</div>
    <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
      {ticket.type_label && (
        <span className="px-1.5 py-0.5 rounded bg-white border border-orange-200 text-orange-600">
          {ticket.type_label}
        </span>
      )}
      {ticket.priority_label && (
        <span
          className={`px-1.5 py-0.5 rounded ${
            PRIORITY_COLOR[ticket.priority] || 'bg-slate-100 text-slate-500'
          }`}
        >
          {ticket.priority_label}
        </span>
      )}
      {ticket.status_label && (
        <span className="px-1.5 py-0.5 rounded bg-white border border-slate-200 text-slate-500">
          {ticket.status_label}
        </span>
      )}
    </div>
    {ticket.description && (
      <p className="mt-1.5 text-[11px] text-slate-500 whitespace-pre-wrap leading-relaxed">
        {ticket.description}
      </p>
    )}
  </div>
)

export default EscalationTicketCard
