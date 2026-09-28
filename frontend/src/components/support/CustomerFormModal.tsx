/**
 * CustomerFormModal - 客户关联 / 编辑
 *
 * 两种用途共用一个弹窗：
 * - link：把会话关联到某个客户（可现场新建）
 * - edit：修改客户资料
 */

import React, { useEffect, useState } from 'react'
import { AutoComplete, Form, Input, Modal, Segmented, Select, message as antdMessage } from 'antd'
import supportApi from '../../services/support'
import type { OptionItem, SupportCustomer } from '../../types/support'

interface CustomerFormModalProps {
  /** link: 关联到会话；edit: 编辑资料；create: 仅新建客户 */
  open: boolean
  mode: 'link' | 'edit' | 'create'
  sessionId: number | null
  customerId: number | null
  sourceOptions: OptionItem[]
  onCancel: () => void
  onDone: () => void
}

const CustomerFormModal: React.FC<CustomerFormModalProps> = ({
  open,
  mode,
  sessionId,
  customerId,
  sourceOptions,
  onCancel,
  onDone,
}) => {
  const [form] = Form.useForm()
  const [tab, setTab] = useState<'select' | 'create'>('select')
  const [submitting, setSubmitting] = useState(false)
  const [options, setOptions] = useState<{ value: number; label: string }[]>([])
  const [keyword, setKeyword] = useState('')

  useEffect(() => {
    if (!open) return
    setKeyword('')
    if (mode === 'edit' && customerId) {
      setTab('create')
      supportApi
        .getCustomer(customerId)
        .then((detail) => {
          form.setFieldsValue({
            name: detail.name,
            phone: detail.phone || '',
            wechat: detail.wechat || '',
            email: detail.email || '',
            source: detail.source,
            remark: detail.remark || '',
          })
        })
        .catch(() => antdMessage.error('客户信息加载失败'))
    } else {
      setTab(mode === 'create' ? 'create' : 'select')
      form.resetFields()
      form.setFieldsValue({ source: 'other' })
    }
  }, [open, mode, customerId, form])

  useEffect(() => {
    if (!open || tab !== 'select' || !keyword.trim()) return
    const timer = setTimeout(() => {
      supportApi
        .listCustomers({ keyword, page_size: 20 })
        .then((res) =>
          setOptions(
            (res.items || []).map((item) => ({
              value: item.id,
              label: item.phone ? `${item.name}（${item.phone}）` : item.name,
            }))
          )
        )
        .catch(() => undefined)
    }, 300)
    return () => clearTimeout(timer)
  }, [keyword, open, tab])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      let targetId: number | null = null
      if (mode === 'edit' && customerId) {
        await supportApi.updateCustomer(customerId, {
          name: values.name,
          phone: values.phone,
          wechat: values.wechat,
          email: values.email,
          source: values.source,
          remark: values.remark,
        })
        antdMessage.success('客户资料已更新')
      } else if (tab === 'select') {
        targetId = values.customer_id ?? null
        if (!targetId) {
          antdMessage.warning('请选择一个客户')
          return
        }
        if (sessionId) {
          await supportApi.updateSession(sessionId, { customer_id: targetId })
          antdMessage.success('已关联客户')
        }
      } else {
        const created: SupportCustomer = await supportApi.createCustomer({
          name: values.name,
          phone: values.phone,
          wechat: values.wechat,
          email: values.email,
          source: values.source || 'other',
          remark: values.remark,
        })
        targetId = created.id
        if (sessionId) {
          await supportApi.updateSession(sessionId, { customer_id: targetId })
          antdMessage.success('已新建并关联客户')
        }
      }
      onDone()
    } catch (err) {
      console.error('客户操作失败:', err)
      antdMessage.error('操作失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title={mode === 'edit' ? '编辑客户资料' : '关联客户'}
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      confirmLoading={submitting}
      okText="保存"
      cancelText="取消"
      destroyOnClose
    >
      {mode === 'link' && (
        <div className="mb-4">
          <Segmented
            block
            value={tab}
            onChange={(value) => setTab(value as 'select' | 'create')}
            options={[
              { label: '选择已有客户', value: 'select' },
              { label: '新建客户', value: 'create' },
            ]}
          />
        </div>
      )}

      <Form form={form} layout="vertical">
        {mode === 'link' && tab === 'select' ? (
          <Form.Item
            name="customer_id"
            label="客户"
            rules={[{ required: true, message: '请选择客户' }]}
          >
            <AutoComplete
              options={options}
              onSearch={setKeyword}
              placeholder="输入姓名或手机号搜索"
              allowClear
            />
          </Form.Item>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
                <Input placeholder="如：王女士" maxLength={50} />
              </Form.Item>
              <Form.Item name="phone" label="手机号">
                <Input placeholder="选填" maxLength={30} />
              </Form.Item>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="wechat" label="微信">
                <Input placeholder="选填" maxLength={50} />
              </Form.Item>
              <Form.Item name="source" label="来源渠道">
                <Select options={sourceOptions} />
              </Form.Item>
            </div>
            <Form.Item name="email" label="邮箱">
              <Input placeholder="选填" maxLength={100} />
            </Form.Item>
            <Form.Item name="remark" label="备注">
              <Input.TextArea rows={2} maxLength={500} placeholder="如：孩子 8 岁，已报科学课" />
            </Form.Item>
          </>
        )}
      </Form>
    </Modal>
  )
}

export default CustomerFormModal
