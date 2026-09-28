/**
 * 能力设置抽屉 - 技能 Tab
 *
 * 展示平台自建技能，支持搜索与多选；选中项在保存后随对话注入。
 */
import React, { useMemo, useState } from 'react'
import { Empty, Input, Spin, Tag } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { HermesSkill } from '@/services/hermes'

interface SkillTabProps {
  skills: HermesSkill[]
  loading: boolean
  selected: string[]
  onChange: (slugs: string[]) => void
}

const SkillTab: React.FC<SkillTabProps> = ({ skills, loading, selected, onChange }) => {
  const [keyword, setKeyword] = useState('')

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase()
    if (!kw) return skills
    return skills.filter(
      (s) =>
        s.name.toLowerCase().includes(kw) ||
        s.slug.toLowerCase().includes(kw) ||
        (s.description || '').toLowerCase().includes(kw)
    )
  }, [skills, keyword])

  const toggle = (slug: string) => {
    onChange(
      selected.includes(slug) ? selected.filter((s) => s !== slug) : [...selected, slug]
    )
  }

  return (
    <div>
      <Input.Search
        placeholder="搜索技能"
        allowClear
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        className="mb-3"
      />

      <div className="mb-3 flex items-center gap-2 text-xs text-gray-500">
        <ThunderboltOutlined />
        <span>已选 {selected.length} 个技能，保存后以系统指令形式注入本会话</span>
      </div>

      <Spin spinning={loading}>
        {filtered.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={loading ? '加载中…' : '暂无可用技能，请先到「技能管理」新建'}
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {filtered.map((skill) => {
              const active = selected.includes(skill.slug)
              return (
                <button
                  key={skill.id}
                  type="button"
                  onClick={() => toggle(skill.slug)}
                  className={`text-left p-3 rounded-lg border transition-all duration-150 ${
                    active
                      ? 'border-blue-500 bg-blue-50 shadow-sm'
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:bg-blue-50/40'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-base">{skill.icon || '🧩'}</span>
                    <span className="font-medium text-sm text-gray-800 truncate">
                      {skill.name}
                    </span>
                    {!skill.enabled && <Tag color="default">停用</Tag>}
                  </div>
                  <div className="text-xs text-gray-500 line-clamp-2 min-h-[32px]">
                    {skill.description || '暂无描述'}
                  </div>
                </button>
              )
            })}
          </div>
        )}
      </Spin>
    </div>
  )
}

export default SkillTab
