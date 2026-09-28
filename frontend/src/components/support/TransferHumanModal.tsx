/**
 * TransferHumanModal - 转人工确认
 *
 * 常见原因做成一键选择，同时允许手输：坐席转人工往往有明确理由
 * （涉及退费、客户情绪激动），把原因留下来才能复盘「为什么 AI 没接住」。
 */

import React, { useState } from 'react'
import { Input, Modal, Radio, message as antdMessage } from 'antd'

const REASONS = [
  '涉及退费/退款，需人工核实',
  '客户情绪激动，需人工安抚',
  'AI 回答不准确',
  '客户明确要求人工',
  '需要调课/排课操作',
]

interface TransferHumanModalProps {
  open: boolean
  onCancel: () => void
  onOk: (reason: string) => Promise<void> | void
}

const TransferHumanModal: React.FC<TransferHumanModalProps> = ({
  open,
  onCancel,
  onOk,
}) => {
  const [reason, setReason] = useState(REASONS[0])
  const [custom, setCustom] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const finalReason = custom.trim() || reason

  const handleOk = async () => {
    setSubmitting(true)
    try {
      await onOk(finalReason)
      setCustom('')
    } catch (err) {
      console.error('转人工失败:', err)
      antdMessage.error('转人工失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="转人工处理"
      open={open}
      onCancel={onCancel}
      onOk={handleOk}
      confirmLoading={submitting}
      okText="确认转人工"
      cancelText="取消"
      destroyOnClose
    >
      <p className="text-sm text-slate-600 mb-3">
        转人工后会话进入「待接管」状态，由你继续回复客户，AI 转为建议回复模式。
      </p>
      <Radio.Group
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        className="w-full"
      >
        <div className="flex flex-col gap-2">
          {REASONS.map((item) => (
            <Radio key={item} value={item}>
              {item}
            </Radio>
          ))}
        </div>
      </Radio.Group>
      <Input.TextArea
        rows={2}
        className="mt-3"
        placeholder="补充说明（可选）"
        value={custom}
        onChange={(e) => setCustom(e.target.value)}
        maxLength={200}
      />
    </Modal>
  )
}

export default TransferHumanModal
