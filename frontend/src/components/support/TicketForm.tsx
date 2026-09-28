/**
 * TicketForm - 工单创建表单
 *
 * 客户来源二选一：选已有客户，或现场录入一份资料。
 * 从会话一键建单时默认带出该会话的客户，减少重复操作。
 */

import React, { useEffect, useState } from 'react'
import {
  AutoComplete,
  DatePicker,
  Form,
  Input,
  Modal,
  Select,
  Switch,
  message as antdMessage,
} from 'antd'
import dayjs from 'dayjs'
import supportApi from '../../services/support'
import { useAuthStore } from '../../stores/auth'
import type { OptionItem, SupportCustomer, SupportTicket } from '../../types/support'

interface TicketFormProps {
  open: boolean
  sessionId: number | null
  defaultCustomerId: number | null
  defaultTitle?: string
  typeOptions: OptionItem[]
  priorityOptions: OptionItem[]
  onCancel: () => void
  onCreated: (ticket: SupportTicket) => void
}

const TicketForm: React.FC<TicketFormProps> = ({
  open,
  sessionId,
  defaultCustomerId,
  defaultTitle,
  typeOptions,
  priorityOptions,
  onCancel,
  onCreated,
}) => {
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)
  const [createNew, setCreateNew] = useState(false)
  const [customerOptions, setCustomerOptions] = useState<
    { value: number; label: string }[]
  >([])
  const [keyword, setKeyword] = useState('')
  const { user } = useAuthStore()

  useEffect(() => {
    if (!open) return
    form.resetFields()
    setCreateNew(!defaultCustomerId)
    form.setFieldsValue({
      type: 'other',
      priority: 'normal',
      title: defaultTitle || '',
      customer_id: defaultCustomerId ?? undefined,
      assign_to_me: true,
    })
  }, [open, defaultCustomerId, defaultTitle, form])

  useEffect(() => {
    if (!open || keyword.trim().length === 0) return
    let cancelled = false
    const timer = setTimeout(async () => {
      try {
        const res = await supportApi.listCustomers({ keyword, page_size: 20 })
        if (cancelled) return
        setCustomerOptions(
          (res.items || []).map((item: SupportCustomer) => ({
            value: item.id,
            label: item.phone ? `${item.name}（${item.phone}）` : item.name,
          }))
        )
      } catch (err) {
        console.error('搜索客户失败:', err)
      }
    }, 300)
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [keyword, open])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      const payload = {
        session_id: sessionId ?? null,
        type: values.type,
        title: values.title,
        description: values.description,
        priority: values.priority,
        due_at: values.due_at ? values.due_at.toISOString() : null,
        assignee_id: values.assign_to_me ? user?.id ?? null : null,
        customer_id: createNew ? null : values.customer_id ?? null,
        customer_new: createNew
          ? {
              name: values.customer_name,
              phone: values.customer_phone,
              source: 'other',
            }
          : null,
      }
      const ticket = await supportApi.createTicket(payload)
      antdMessage.success(`工单 ${ticket.ticket_no} 已创建`)
      onCreated(ticket)
    } catch (err) {
      console.error('创建工单失败:', err)
      antdMessage.error('创建工单失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="创建售后工单"
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={submitting}
      okText="创建"
      cancelText="取消"
      width={560}
      destroyOnClose
    >
      <Form form={form} layout="vertical" className="mt-4">
        <Form.Item label="关联客户" required>
          <div className="flex items-center gap-2 mb-2">
            <Switch
              size="small"
              checked={createNew}
              onChange={(checked) => setCreateNew(checked)}
            />
            <span className="text-xs text-slate-500">
              {createNew ? '新建客户' : '选择已有客户'}
            </span>
          </div>
          {createNew ? (
            <div className="grid grid-cols-2 gap-2">
              <Form.Item
                name="customer_name"
                noStyle
                rules={[{ required: true, message: '请输入客户姓名' }]}
              >
                <Input placeholder="客户姓名" />
              </Form.Item>
              <Form.Item name="customer_phone" noStyle>
                <Input placeholder="手机号（选填）" />
              </Form.Item>
            </div>
          ) : (
            <Form.Item
              name="customer_id"
              noStyle
              rules={[{ required: true, message: '请选择客户' }]}
            >
              <AutoComplete
                options={customerOptions}
                onSearch={setKeyword}
                placeholder="输入姓名或手机号搜索"
                allowClear
              />
            </Form.Item>
          )}
        </Form.Item>

        <Form.Item name="title" label="工单标题" rules={[{ required: true, message: '请输入标题' }]}>
          <Input placeholder="如：申请退剩余 12 课时费用" maxLength={200} />
        </Form.Item>

        <div className="grid grid-cols-2 gap-3">
          <Form.Item name="type" label="工单类型">
            <Select options={typeOptions} />
          </Form.Item>
          <Form.Item name="priority" label="优先级">
            <Select options={priorityOptions} />
          </Form.Item>
        </div>

        <Form.Item name="description" label="问题描述">
          <Input.TextArea rows={3} placeholder="补充客户诉求、订单信息等" maxLength={2000} />
        </Form.Item>

        <div className="grid grid-cols-2 gap-3">
          <Form.Item name="due_at" label="期望完成时间">
            <DatePicker
              showTime
              className="w-full"
              disabledDate={(current) => current && current < dayjs().startOf('day')}
            />
          </Form.Item>
          <Form.Item name="assign_to_me" label="指派给自己" valuePropName="checked">
            <Switch />
          </Form.Item>
        </div>
      </Form>
    </Modal>
  )
}

export default TicketForm
