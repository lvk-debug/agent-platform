/**
 * CustomerPanel - 客户信息侧栏
 *
 * 展示客户资料 + 历史会话 + 关联工单：坐席接手一个会话时，
 * 最需要的是「这个人之前发生过什么」，而不是再点进另一个页面查。
 */

import React, { useEffect, useState } from 'react'
import { Avatar, Button, Descriptions, Empty, Spin, Tag, message as antdMessage } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import supportApi from '../../services/support'
import type { SupportCustomer, SupportTicket } from '../../types/support'

interface CustomerPanelProps {
  sessionId: number | null
  customerId: number | null
  onChangeCustomer: () => void
  onEditCustomer: () => void
}

const CustomerPanel: React.FC<CustomerPanelProps> = ({
  sessionId,
  customerId,
  onChangeCustomer,
  onEditCustomer,
}) => {
  const [customer, setCustomer] = useState<SupportCustomer | null>(null)
  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!customerId) {
      setCustomer(null)
      setTickets([])
      return
    }
    let cancelled = false
    const load = async () => {
      setLoading(true)
      try {
        const [detail, ticketRes] = await Promise.all([
          supportApi.getCustomer(customerId),
          supportApi.listTickets({ customer_id: customerId, page_size: 10 }),
        ])
        if (cancelled) return
        setCustomer(detail)
        setTickets(ticketRes.items || [])
      } catch (err) {
        console.error('加载客户信息失败:', err)
        if (!cancelled) antdMessage.error('客户信息加载失败')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [customerId])

  if (!customerId) {
    return (
      <div className="p-4 text-center">
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description="该会话未关联客户"
        />
        <Button type="link" onClick={onChangeCustomer} disabled={!sessionId}>
          关联客户
        </Button>
      </div>
    )
  }

  if (loading || !customer) {
    return (
      <div className="flex justify-center py-10">
        <Spin />
      </div>
    )
  }

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-3">
        <Avatar size={44} className="bg-gradient-to-br from-indigo-400 to-violet-500" icon={<UserOutlined />} />
        <div className="min-w-0">
          <div className="font-medium text-slate-800 truncate">{customer.name}</div>
          <div className="text-xs text-slate-400">
            {customer.source_label || '未知来源'} · 咨询 {customer.session_count} 次
          </div>
        </div>
        <Button size="small" type="link" className="ml-auto" onClick={onEditCustomer}>
          编辑
        </Button>
      </div>

      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="手机号">
          {customer.phone || '—'}
        </Descriptions.Item>
        <Descriptions.Item label="微信">{customer.wechat || '—'}</Descriptions.Item>
        <Descriptions.Item label="邮箱" >
          <span className="break-all">{customer.email || '—'}</span>
        </Descriptions.Item>
        <Descriptions.Item label="最近咨询">
          {customer.last_session_at
            ? dayjs(customer.last_session_at).format('YYYY-MM-DD HH:mm')
            : '—'}
        </Descriptions.Item>
      </Descriptions>

      {customer.tags && customer.tags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {customer.tags.map((tag) => (
            <Tag key={tag} color="indigo">
              {tag}
            </Tag>
          ))}
        </div>
      )}

      {customer.remark && (
        <div className="rounded-lg bg-slate-50 p-2 text-xs text-slate-600 whitespace-pre-wrap">
          {customer.remark}
        </div>
      )}

      <div>
        <div className="text-xs font-medium text-slate-500 mb-2">
          关联工单（{customer.ticket_count}）
        </div>
        {tickets.length === 0 ? (
          <div className="text-xs text-slate-400">暂无工单</div>
        ) : (
          <ul className="space-y-1.5">
            {tickets.map((ticket) => (
              <li
                key={ticket.id}
                className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs"
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-700 truncate flex-1">
                    {ticket.title}
                  </span>
                  <Tag
                    color={
                      ticket.status === 'resolved'
                        ? 'green'
                        : ticket.is_overdue
                          ? 'red'
                          : 'orange'
                    }
                    className="!m-0"
                  >
                    {ticket.status_label}
                  </Tag>
                </div>
                <div className="text-[10px] text-slate-400 mt-0.5">
                  {ticket.ticket_no} · {ticket.type_label}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <Button block size="small" onClick={onChangeCustomer}>
        更换关联客户
      </Button>
    </div>
  )
}

export default CustomerPanel
