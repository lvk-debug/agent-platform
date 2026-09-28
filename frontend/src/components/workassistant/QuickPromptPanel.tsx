/**
 * 快捷指令面板（Modal）
 *
 * 支持按标题/描述/内容搜索，按分类展示。点击条目触发 onSelect。
 * 图标按后端返回的 icon 名（Ant Design 图标名）动态解析，缺省用 BulbOutlined。
 */
import { useMemo, useState } from 'react'
import { Modal, Input, Tag, Empty, Spin, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import * as AntdIcons from '@ant-design/icons'
import { BulbOutlined } from '@ant-design/icons'
import type { QuickPrompt } from '@/services/hermes'

const { Text } = Typography

/** 分类中文标签 */
export const CATEGORY_LABELS: Record<string, string> = {
  writing: '写作',
  dev: '开发',
  analysis: '分析',
  productivity: '效率',
  general: '通用',
}

/** 按图标名动态解析 Ant Design 图标组件 */
export function PromptIcon({ name }: { name?: string }) {
  const map = AntdIcons as unknown as Record<string, React.ComponentType>
  if (name && map[name]) {
    const Cmp = map[name]
    return <Cmp />
  }
  return <BulbOutlined />
}

export interface QuickPromptPanelProps {
  open: boolean
  prompts: QuickPrompt[]
  loading?: boolean
  onClose: () => void
  onSelect: (prompt: QuickPrompt) => void
}

export default function QuickPromptPanel({
  open,
  prompts,
  loading,
  onClose,
  onSelect,
}: QuickPromptPanelProps) {
  const [keyword, setKeyword] = useState('')

  const filtered = useMemo(() => {
    const k = keyword.trim().toLowerCase()
    if (!k) return prompts
    return prompts.filter(
      (p) =>
        p.title.toLowerCase().includes(k) ||
        (p.description || '').toLowerCase().includes(k) ||
        p.content.toLowerCase().includes(k)
    )
  }, [prompts, keyword])

  return (
    <Modal
      title="快捷指令"
      open={open}
      onCancel={onClose}
      footer={null}
      width={560}
      destroyOnClose
    >
      <Input
        allowClear
        prefix={<SearchOutlined />}
        placeholder="搜索提示词…"
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="mb-3"
      />
      {loading ? (
        <div className="flex justify-center py-8">
          <Spin />
        </div>
      ) : filtered.length === 0 ? (
        <Empty description="暂无提示词" />
      ) : (
        <div className="max-h-[50vh] overflow-y-auto pr-1">
          {filtered.map((p) => (
            <div
              key={p.id}
              onClick={() => onSelect(p)}
              className="flex items-start gap-3 p-3 rounded-lg cursor-pointer hover:bg-gray-50 border border-transparent hover:border-blue-200 transition-all"
            >
              <div className="mt-0.5 text-lg text-blue-500">
                <PromptIcon name={p.icon} />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Text strong className="text-sm">
                    {p.title}
                  </Text>
                  {p.category && (
                    <Tag className="text-xs">
                      {CATEGORY_LABELS[p.category] || p.category}
                    </Tag>
                  )}
                </div>
                <Text type="secondary" className="text-xs line-clamp-1">
                  {p.description || p.content}
                </Text>
              </div>
            </div>
          ))}
        </div>
      )}
    </Modal>
  )
}
