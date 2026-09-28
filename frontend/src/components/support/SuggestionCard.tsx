/**
 * SuggestionCard - AI 建议回复卡片
 *
 * 人工模式下 AI 退居辅助：给坐席一版草稿，采用后落入输入框继续编辑，
 * 不直接发送——最终对客户说的话必须由坐席确认。
 */

import React from 'react'
import { Button, Popover, Spin } from 'antd'
import { BulbOutlined, CheckOutlined, CloseOutlined } from '@ant-design/icons'
import type { SupportReference } from '../../types/support'

interface SuggestionCardProps {
  content: string
  references: SupportReference[]
  loading: boolean
  error?: string | null
  onAdopt: (content: string) => void
  onDiscard: () => void
}

const SuggestionCard: React.FC<SuggestionCardProps> = ({
  content,
  references,
  loading,
  error,
  onAdopt,
  onDiscard,
}) => {
  if (loading) {
    return (
      <div className="mb-2 flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-50 border border-amber-100 text-xs text-amber-700">
        <Spin size="small" />
        AI 正在起草回复…
      </div>
    )
  }

  if (error) {
    return (
      <div className="mb-2 flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-red-50 border border-red-100 text-xs text-red-600">
        <span>{error}</span>
        <Button type="text" size="small" icon={<CloseOutlined />} onClick={onDiscard} />
      </div>
    )
  }

  if (!content) return null

  return (
    <div className="mb-2 rounded-lg bg-gradient-to-br from-amber-50 to-orange-50 border border-amber-200 p-3">
      <div className="flex items-center gap-2 mb-1.5">
        <BulbOutlined className="text-amber-500" />
        <span className="text-xs font-medium text-amber-700">AI 建议回复</span>
        {references.length > 0 && (
          <Popover
            title="引用来源"
            content={
              <div className="w-72 space-y-2">
                {references.map((item, index) => (
                  <div key={index} className="text-xs text-slate-600">
                    <div className="font-medium text-slate-700">
                      {item.document_name || item.kb_name || '资料'}
                    </div>
                    <p className="line-clamp-3 whitespace-pre-wrap">{item.content}</p>
                  </div>
                ))}
              </div>
            }
          >
            <span className="text-[10px] text-amber-600 cursor-pointer underline decoration-dotted">
              {references.length} 条引用
            </span>
          </Popover>
        )}
        <Button
          type="text"
          size="small"
          className="ml-auto"
          icon={<CloseOutlined />}
          onClick={onDiscard}
        />
      </div>
      <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
        {content}
      </p>
      <div className="mt-2 flex justify-end">
        <Button
          size="small"
          type="primary"
          icon={<CheckOutlined />}
          onClick={() => onAdopt(content)}
        >
          采用并编辑
        </Button>
      </div>
    </div>
  )
}

export default SuggestionCard
