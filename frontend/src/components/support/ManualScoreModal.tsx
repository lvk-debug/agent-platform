/**
 * ManualScoreModal - 人工标注打分弹窗
 *
 * 坐席/管理员对单条 AI 回答按四个维度（准确性/帮助性/安全性/流畅性）星级打分并写评语。
 * 星级 1~5 在提交时转换为 0~1 传给后端。
 */

import React, { useEffect, useState } from 'react'
import { Modal, Rate, Input, message as antdMessage, Tag } from 'antd'
import supportApi from '../../services/support'
import type { SupportMessage } from '../../types/support'

const DIMENSIONS: { key: 'accuracy' | 'helpfulness' | 'safety' | 'fluency'; label: string; color: string }[] = [
  { key: 'accuracy', label: '准确性', color: 'blue' },
  { key: 'helpfulness', label: '帮助性', color: 'green' },
  { key: 'safety', label: '安全性', color: 'red' },
  { key: 'fluency', label: '流畅性', color: 'purple' },
]

interface ManualScoreModalProps {
  open: boolean
  message: SupportMessage | null
  onCancel: () => void
  onSubmitted?: (messageId: number) => void
}

const ManualScoreModal: React.FC<ManualScoreModalProps> = ({ open, message, onCancel, onSubmitted }) => {
  const [scores, setScores] = useState<Record<string, number>>({ accuracy: 0, helpfulness: 0, safety: 0, fluency: 0 })
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (open && message) {
      setScores({ accuracy: 0, helpfulness: 0, safety: 0, fluency: 0 })
      setComment('')
    }
  }, [open, message])

  const handleSubmit = async () => {
    if (!message) return
    if (!scores.accuracy && !scores.helpfulness && !scores.safety && !scores.fluency) {
      antdMessage.warning('请至少对一个维度打分')
      return
    }
    setSubmitting(true)
    try {
      await supportApi.manualScore({
        message_id: message.id,
        accuracy: scores.accuracy / 5,
        helpfulness: scores.helpfulness / 5,
        safety: scores.safety / 5,
        fluency: scores.fluency / 5,
        comment: comment.trim() || undefined,
      })
      antdMessage.success('打分已提交')
      onSubmitted?.(message.id)
      onCancel()
    } catch (err) {
      console.error('人工打分提交失败:', err)
      antdMessage.error('提交失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      title="人工标注打分"
      open={open}
      onCancel={onCancel}
      onOk={handleSubmit}
      okText="提交打分"
      confirmLoading={submitting}
      destroyOnClose
      width={460}
    >
      {message && (
        <div className="space-y-4">
          <div className="text-xs text-slate-400 line-clamp-2 bg-slate-50 rounded p-2">
            {message.content || '（空）'}
          </div>
          {DIMENSIONS.map((dim) => (
            <div key={dim.key} className="flex items-center gap-3">
              <Tag color={dim.color} className="!w-14 !text-center !m-0">
                {dim.label}
              </Tag>
              <Rate value={scores[dim.key]} onChange={(v) => setScores((s) => ({ ...s, [dim.key]: v }))} />
              <span className="text-xs text-slate-400">{scores[dim.key] ? `${scores[dim.key]} 星` : '未评'}</span>
            </div>
          ))}
          <div>
            <div className="text-xs text-slate-500 mb-1">评语（可选）</div>
            <Input.TextArea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={3}
              maxLength={500}
              placeholder="补充人工评价，例如幻觉点、违规表述等"
            />
          </div>
        </div>
      )}
    </Modal>
  )
}

export default ManualScoreModal
