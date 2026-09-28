/**
 * SessionList - 会话列表（坐席工作台左栏）
 *
 * 待人工的会话置顶高亮：它是唯一需要坐席立刻动手的队列。
 */

import React from 'react'
import { Badge, Button, Empty, Input, Pagination, Segmented, Spin } from 'antd'
import { PlusOutlined, SearchOutlined, UserSwitchOutlined } from '@ant-design/icons'
import type { OptionItem, SupportSession } from '../../types/support'

const STATUS_COLOR: Record<string, string> = {
  open: 'bg-emerald-500',
  pending_human: 'bg-amber-500',
  resolved: 'bg-blue-500',
  closed: 'bg-slate-300',
}

interface SessionListProps {
  sessions: SupportSession[]
  loading: boolean
  activeId: number | null
  total: number
  page: number
  pageSize: number
  statusFilter: string
  keyword: string
  statusOptions: OptionItem[]
  onStatusChange: (value: string) => void
  onKeywordChange: (value: string) => void
  onPageChange: (page: number) => void
  onSelect: (session: SupportSession) => void
  onShowTrace: (session: SupportSession) => void
  onCreate: () => void
}

const SessionList: React.FC<SessionListProps> = ({
  sessions,
  loading,
  activeId,
  total,
  page,
  pageSize,
  statusFilter,
  keyword,
  statusOptions,
  onStatusChange,
  onKeywordChange,
  onPageChange,
  onSelect,
  onShowTrace,
  onCreate,
}) => {
  const segmentedOptions = [
    { label: '全部', value: 'all' },
    ...statusOptions.map((item) => ({ label: item.label, value: item.value })),
  ]

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="p-3 border-b border-slate-100 space-y-2">
        <div className="flex items-center gap-2">
          <Input
            allowClear
            prefix={<SearchOutlined className="text-slate-400" />}
            placeholder="搜索会话内容 / 标题"
            value={keyword}
            onChange={(e) => onKeywordChange(e.target.value)}
          />
          <Button type="primary" icon={<PlusOutlined />} onClick={onCreate} />
        </div>
        <Segmented
          block
          size="small"
          value={statusFilter}
          options={segmentedOptions}
          onChange={(value) => onStatusChange(value as string)}
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && sessions.length === 0 ? (
          <div className="flex justify-center py-10">
            <Spin />
          </div>
        ) : sessions.length === 0 ? (
          <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无会话" className="mt-10" />
        ) : (
          <ul className="divide-y divide-slate-100">
            {sessions.map((item) => {
              const active = item.id === activeId
              const pending = item.status === 'pending_human'
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => onSelect(item)}
                    className={`w-full text-left px-3 py-3 transition-colors ${
                      active
                        ? 'bg-indigo-50/70 border-l-2 border-indigo-500'
                        : 'hover:bg-slate-50 border-l-2 border-transparent'
                    } ${pending ? 'bg-amber-50/40' : ''}`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          STATUS_COLOR[item.status] || 'bg-slate-300'
                        }`}
                      />
                      <span className="text-sm font-medium text-slate-800 truncate flex-1">
                        {item.title || (item.customer_name ? `${item.customer_name} 的咨询` : '未命名会话')}
                      </span>
                      {item.mode === 'human' && (
                        <span
                          title="人工模式"
                          className="text-[10px] px-1.5 py-0.5 rounded bg-blue-50 text-blue-600"
                        >
                          人工
                        </span>
                      )}
                      {pending && (
                        <Badge
                          count={<UserSwitchOutlined style={{ color: '#d97706' }} />}
                        />
                      )}
                    </div>

                    <p className="mt-1 text-xs text-slate-500 line-clamp-2 pl-4">
                      {item.last_message_preview || '暂无消息'}
                    </p>

                    <div className="mt-1.5 pl-4 flex items-center gap-2 flex-wrap">
                      {item.customer_name && (
                        <span className="text-[10px] text-slate-400">
                          {item.customer_name}
                        </span>
                      )}
                      {item.intent_label && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                          {item.intent_label}
                        </span>
                      )}
                      {item.assignee_name && (
                        <span className="text-[10px] text-slate-400">
                          · {item.assignee_name}
                        </span>
                      )}
                      {item.message_count > 0 && (
                        <span className="text-[10px] text-slate-300">
                          {item.message_count} 条
                        </span>
                      )}
                      {item.last_ai_trace?.steps?.length ? (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onShowTrace(item)
                          }}
                          className="ml-auto text-[10px] text-indigo-500 hover:underline"
                        >
                          运行日志 {item.last_ai_trace.steps.length} 步
                        </button>
                      ) : null}
                    </div>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {total > pageSize && (
        <div className="border-t border-slate-100 py-2 flex justify-center">
          <Pagination
            size="small"
            current={page}
            pageSize={pageSize}
            total={total}
            onChange={onPageChange}
            showSizeChanger={false}
          />
        </div>
      )}
    </div>
  )
}

export default SessionList
