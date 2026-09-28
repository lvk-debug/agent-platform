/**
 * TicketTimeline - 工单处理流水时间线
 *
 * 状态流转与留言混排展示：坐席关心的是「这件事怎么推进的」，
 * 而不是区分「这是系统流转还是人工留言」。
 */

import React from 'react'
import { Tag, Timeline } from 'antd'
import dayjs from 'dayjs'
import type { SupportTicketLog } from '../../types/support'

const ACTION_META: Record<string, { label: string; color: string }> = {
  create: { label: '创建', color: 'blue' },
  transition: { label: '状态变更', color: 'purple' },
  assign: { label: '指派', color: 'cyan' },
  comment: { label: '留言', color: 'green' },
}

interface TicketTimelineProps {
  logs: SupportTicketLog[]
}

const TicketTimeline: React.FC<TicketTimelineProps> = ({ logs }) => {
  if (!logs.length) {
    return <div className="text-xs text-slate-400 py-2">暂无处理记录</div>
  }

  return (
    <Timeline
      items={logs.map((log) => {
        const meta = ACTION_META[log.action] || { label: log.action, color: 'gray' }
        return {
          color: meta.color,
          children: (
            <div className="pb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <Tag color={meta.color} className="!m-0">
                  {meta.label}
                </Tag>
                {log.to_status_label && (
                  <span className="text-xs text-slate-600">
                    {log.from_status_label ? `${log.from_status_label} → ` : ''}
                    {log.to_status_label}
                  </span>
                )}
                <span className="text-[10px] text-slate-400 ml-auto">
                  {dayjs(log.created_at).format('MM-DD HH:mm')}
                </span>
              </div>
              {log.content && (
                <p className="mt-1 text-xs text-slate-600 whitespace-pre-wrap">
                  {log.content}
                </p>
              )}
              {log.operator_name && (
                <span className="text-[10px] text-slate-400">处理人：{log.operator_name}</span>
              )}
            </div>
          ),
        }
      })}
    />
  )
}

export default TicketTimeline
