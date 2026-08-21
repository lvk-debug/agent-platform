/**
 * 条件分支节点 — 根据配置的 branches 动态生成 IF/ELIF/ELSE 输出
 */
import React, { memo, useMemo } from 'react'
import BaseNode from './BaseNode'

interface HandleLabel {
  id: string
  label: string
  color?: string
}

const ConditionNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  const sourceHandles: HandleLabel[] = useMemo(() => {
    const config = props.data?.config || {}
    const branchList = config.branches || []

    if (branchList.length === 0) {
      return [
        { id: 'IF', label: 'IF', color: '#52c41a' },
        { id: 'ELSE', label: 'ELSE', color: '#fa8c16' },
      ]
    }

    const handles: HandleLabel[] = []
    const total = branchList.length

    branchList.forEach((branch: any, i: number) => {
      const branchName = branch.branch || ''
      let label: string
      let color: string

      if (i === 0) {
        // 第一个是 IF
        label = branchName || 'IF'
        color = '#52c41a'
      } else if (i === total - 1) {
        // 最后一个是 ELSE
        label = branchName || 'ELSE'
        color = '#fa8c16'
      } else {
        // 中间的是 ELIF
        label = branchName || `ELIF${i}`
        color = '#722ed1'
      }

      handles.push({ id: label, label, color })
    })

    return handles
  }, [props.data?.config])

  return (
    <BaseNode
      {...props}
      sourceHandles={sourceHandles}
    />
  )
}

export default memo(ConditionNode)
