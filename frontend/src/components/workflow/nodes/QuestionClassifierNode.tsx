/**
 * 问题分类器节点 — 使用 LLM 对输入进行分类
 * 输出: CLASS 1 / CLASS 2 / ...（动态，基于配置的分类）
 */
import React, { memo, useMemo } from 'react'
import BaseNode from './BaseNode'

interface HandleLabel {
  id: string
  label: string
  color?: string
}

// 分类颜色轮转
const CLASS_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2']

const QuestionClassifierNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  const config = props.data?.config || {}
  const categories = config.categories || []

  // 根据分类生成输出连接点
  const sourceHandles: HandleLabel[] = useMemo(() => {
    if (categories.length === 0) {
      return [
        { id: 'CLASS 1', label: 'CLASS 1', color: CLASS_COLORS[0] },
        { id: 'CLASS 2', label: 'CLASS 2', color: CLASS_COLORS[1] },
      ]
    }
    return categories.map((cat: any, i: number) => ({
      id: cat.name || `CLASS ${i + 1}`,
      label: cat.name || `CLASS ${i + 1}`,
      color: CLASS_COLORS[i % CLASS_COLORS.length],
    }))
  }, [categories])

  // 分类内容描述（显示在节点内）
  const categoryDescriptions = useMemo(() => {
    return categories.map((cat: any, i: number) => ({
      name: cat.name || `CLASS ${i + 1}`,
      description: cat.description || '在这里输入你的主题内容',
    }))
  }, [categories])

  return (
    <BaseNode
      {...props}
      sourceHandles={sourceHandles}
    >
      {/* 分类列表显示在节点内容区域 */}
      {categoryDescriptions.length > 0 && (
        <div className="space-y-1 mt-1">
          {categoryDescriptions.map((cat, i) => (
            <div
              key={i}
              className="text-xs px-2 py-1 rounded"
              style={{
                background: `${CLASS_COLORS[i % CLASS_COLORS.length]}08`,
                borderLeft: `2px solid ${CLASS_COLORS[i % CLASS_COLORS.length]}`,
                color: '#595959',
              }}
            >
              <span className="font-medium">{cat.name}</span>
              {cat.description && (
                <span className="ml-1 text-gray-400">— {cat.description}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </BaseNode>
  )
}

export default memo(QuestionClassifierNode)
