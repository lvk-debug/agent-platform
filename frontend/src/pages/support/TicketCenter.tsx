/**
 * 工单中心
 *
 * 列表筛选 + 详情抽屉。状态流转走后端状态机，
 * 非法流转由后端返回 400，前端直接把原因提示给坐席。
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Button,
  DatePicker,
  Drawer,
  Form,
  Input,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  message as antdMessage,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import TicketTimeline from '../../components/support/TicketTimeline'
import supportApi from '../../services/support'
import type { OptionItem, SupportTicket, TicketDetailResponse } from '../../types/support'

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  processing: 'blue',
  resolved: 'green',
  rejected: 'red',
  closed: 'default',
}

const TicketCenter: React.FC = () => {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [tickets, setTickets] = useState<SupportTicket[]>([])
  const [loading, setLoading] = useState(false)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const [status, setStatus] = useState<string>('all')
  const [type, setType] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [onlyOverdue, setOnlyOverdue] = useState(false)

  // 客户管理页「查看某客户工单」跳转进来时带 ?customer=ID，自动锁定筛选
  const [searchParams] = useSearchParams()
  const [customerId, setCustomerId] = useState<number | undefined>()

  const [options, setOptions] = useState<{
    ticket_types: OptionItem[]
    ticket_status: OptionItem[]
  }>({ ticket_types: [], ticket_status: [] })

  const [detail, setDetail] = useState<TicketDetailResponse | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [comment, setComment] = useState('')
  const [transitionTo, setTransitionTo] = useState<string>('')
  const [transitionNote, setTransitionNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    supportApi
      .options()
      .then((res) => setOptions({ ticket_types: res.ticket_types, ticket_status: res.ticket_status }))
      .catch(() => undefined)
  }, [])

  const loadTickets = useCallback(async () => {
    setLoading(true)
    try {
      const res = await supportApi.listTickets({
        status: status === 'all' ? undefined : status,
        type,
        customer_id: customerId,
        keyword: keyword || undefined,
        only_overdue: onlyOverdue || undefined,
        page,
        page_size: pageSize,
      })
      setTickets(res.items || [])
      setTotal(res.meta?.total || 0)
    } catch (err) {
      console.error('加载工单列表失败:', err)
    } finally {
      setLoading(false)
    }
  }, [status, type, customerId, keyword, onlyOverdue, page])

  useEffect(() => {
    const param = searchParams.get('customer')
    if (param) setCustomerId(Number(param))
  }, [searchParams])

  useEffect(() => {
    void loadTickets()
  }, [loadTickets])

  const openDetail = useCallback(async (ticket: SupportTicket) => {
    try {
      const res = await supportApi.getTicket(ticket.id)
      setDetail(res)
      setTransitionTo('')
      setTransitionNote('')
      setComment('')
      setDrawerOpen(true)
    } catch (err) {
      console.error('加载工单详情失败:', err)
      antdMessage.error('工单详情加载失败')
    }
  }, [])

  const handleTransition = useCallback(async () => {
    if (!detail || !transitionTo) return
    setSubmitting(true)
    try {
      const res = await supportApi.transitionTicket(
        detail.ticket.id,
        transitionTo,
        transitionNote || undefined
      )
      setDetail(res)
      setTransitionTo('')
      setTransitionNote('')
      antdMessage.success('状态已更新')
      void loadTickets()
    } catch (err: any) {
      const detailMsg = err?.response?.data?.detail || '状态流转失败'
      antdMessage.error(detailMsg)
    } finally {
      setSubmitting(false)
    }
  }, [detail, transitionTo, transitionNote, loadTickets])

  const handleComment = useCallback(async () => {
    if (!detail || !comment.trim()) return
    setSubmitting(true)
    try {
      const res = await supportApi.commentTicket(detail.ticket.id, comment.trim())
      setDetail(res)
      setComment('')
      antdMessage.success('已留言')
    } catch (err) {
      console.error('留言失败:', err)
      antdMessage.error('留言失败')
    } finally {
      setSubmitting(false)
    }
  }, [detail, comment])

  const handleUpdate = useCallback(async () => {
    if (!detail) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const updated = await supportApi.updateTicket(detail.ticket.id, {
        due_at: values.due_at ? values.due_at.toISOString() : null,
        priority: values.priority,
        type: values.type,
        description: values.description,
      })
      setDetail({ ...detail, ticket: updated })
      antdMessage.success('已保存')
      void loadTickets()
    } catch (err) {
      console.error('更新工单失败:', err)
      antdMessage.error('保存失败')
    } finally {
      setSubmitting(false)
    }
  }, [detail, form, loadTickets])

  const columns = useMemo<ColumnsType<SupportTicket>>(
    () => [
      {
        title: '工单',
        dataIndex: 'title',
        render: (_, row) => (
          <div className="min-w-0">
            <div className="font-medium text-slate-800 truncate">{row.title}</div>
            <div className="text-xs text-slate-400">
              {row.ticket_no} · {row.customer_name || '无客户'}
            </div>
          </div>
        ),
      },
      {
        title: '类型',
        dataIndex: 'type_label',
        width: 90,
        render: (value: string) => <Tag className="!m-0">{value}</Tag>,
      },
      {
        title: '状态',
        dataIndex: 'status',
        width: 100,
        render: (value: string, row) => (
          <Tag color={STATUS_COLOR[value]} className="!m-0">
            {row.status_label}
          </Tag>
        ),
      },
      {
        title: '优先级',
        dataIndex: 'priority',
        width: 90,
        render: (value: string, row) => (
          <span
            className={
              value === 'urgent'
                ? 'text-red-600'
                : value === 'high'
                  ? 'text-orange-600'
                  : 'text-slate-500'
            }
          >
            {row.priority_label}
          </span>
        ),
      },
      {
        title: '负责人',
        dataIndex: 'assignee_name',
        width: 100,
        render: (value: string) => value || <span className="text-slate-300">未指派</span>,
      },
      {
        title: '截止时间',
        dataIndex: 'due_at',
        width: 130,
        render: (value: string, row) =>
          value ? (
            <span className={row.is_overdue ? 'text-red-600' : ''}>
              {dayjs(value).format('MM-DD HH:mm')}
              {row.is_overdue && ' 已超时'}
            </span>
          ) : (
            <span className="text-slate-300">—</span>
          ),
      },
      {
        title: '操作',
        width: 90,
        render: (_, row) => (
          <Button type="link" size="small" onClick={() => openDetail(row)}>
            查看
          </Button>
        ),
      },
    ],
    [openDetail]
  )

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <Segmented
          value="/support/tickets"
          options={NAV_ITEMS}
          onChange={(value) => navigate(value as string)}
        />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented
            value={status}
            onChange={(value) => {
              setStatus(value as string)
              setPage(1)
            }}
            options={[
              { label: '全部', value: 'all' },
              ...options.ticket_status.map((item) => ({
                label: item.label,
                value: item.value,
              })),
            ]}
          />
          <Select
            allowClear
            placeholder="工单类型"
            className="w-36"
            value={type}
            onChange={(value) => {
              setType(value)
              setPage(1)
            }}
            options={options.ticket_types}
          />
          <Input.Search
            allowClear
            placeholder="单号 / 标题"
            className="w-56"
            onSearch={(value) => {
              setKeyword(value)
              setPage(1)
            }}
          />
          <label className="flex items-center gap-1 text-sm text-slate-600 cursor-pointer">
            <input
              type="checkbox"
              checked={onlyOverdue}
              onChange={(e) => {
                setOnlyOverdue(e.target.checked)
                setPage(1)
              }}
            />
            只看超时
          </label>
          {customerId !== undefined && (
            <Tag closable color="blue" onClose={() => setCustomerId(undefined)}>
              客户 #{customerId} 的工单
            </Tag>
          )}
        </div>

        <Table
          rowKey="id"
          loading={loading}
          columns={columns}
          dataSource={tickets}
          pagination={{
            current: page,
            pageSize,
            total,
            onChange: setPage,
            showTotal: (count) => `共 ${count} 条`,
          }}
        />
      </div>

      <Drawer
        title={detail ? `${detail.ticket.ticket_no} ${detail.ticket.title}` : '工单详情'}
        width={520}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      >
        {detail && (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2">
              <Tag color={STATUS_COLOR[detail.ticket.status]}>{detail.ticket.status_label}</Tag>
              <Tag>{detail.ticket.type_label}</Tag>
              <Tag>{detail.ticket.priority_label}</Tag>
              {detail.ticket.is_overdue && <Tag color="red">已超时</Tag>}
            </div>

            <Form form={form} layout="vertical" initialValues={{
              type: detail.ticket.type,
              priority: detail.ticket.priority,
              description: detail.ticket.description || '',
              due_at: detail.ticket.due_at ? dayjs(detail.ticket.due_at) : null,
            }}>
              <div className="grid grid-cols-2 gap-3">
                <Form.Item name="type" label="类型">
                  <Select options={options.ticket_types} />
                </Form.Item>
                <Form.Item name="priority" label="优先级">
                  <Select
                    options={[
                      { label: '低', value: 'low' },
                      { label: '普通', value: 'normal' },
                      { label: '高', value: 'high' },
                      { label: '紧急', value: 'urgent' },
                    ]}
                  />
                </Form.Item>
              </div>
              <Form.Item name="due_at" label="期望完成时间">
                <DatePicker showTime className="w-full" />
              </Form.Item>
              <Form.Item name="description" label="问题描述">
                <Input.TextArea rows={3} maxLength={2000} />
              </Form.Item>
              <Button type="primary" loading={submitting} onClick={handleUpdate}>
                保存修改
              </Button>
            </Form>

            <div className="border-t pt-4">
              <div className="text-sm font-medium text-slate-700 mb-2">处理记录</div>
              <TicketTimeline logs={detail.logs || []} />
            </div>

            <div className="border-t pt-4 space-y-3">
              <div className="text-sm font-medium text-slate-700">添加留言</div>
              <Input.TextArea
                rows={2}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="记录处理进展"
                maxLength={1000}
              />
              <Button onClick={handleComment} disabled={!comment.trim()} loading={submitting}>
                提交留言
              </Button>
            </div>

            <div className="border-t pt-4 space-y-3">
              <div className="text-sm font-medium text-slate-700">状态流转</div>
              <Space.Compact className="w-full">
                <Select
                  className="flex-1"
                  placeholder="选择目标状态"
                  value={transitionTo || undefined}
                  onChange={setTransitionTo}
                  options={options.ticket_status.filter(
                    (item) => item.value !== detail.ticket.status
                  )}
                />
                <Button
                  type="primary"
                  onClick={handleTransition}
                  disabled={!transitionTo}
                  loading={submitting}
                >
                  流转
                </Button>
              </Space.Compact>
              <Input.TextArea
                rows={2}
                value={transitionNote}
                onChange={(e) => setTransitionNote(e.target.value)}
                placeholder="流转说明（可选）"
                maxLength={500}
              />
            </div>
          </div>
        )}
      </Drawer>
    </div>
  )
}

export default TicketCenter
