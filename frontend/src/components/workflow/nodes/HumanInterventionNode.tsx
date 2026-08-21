/**
 * 人工介入节点 — 等待人工审批或输入
 * 输出: TIMEOUT（超时）/ APPROVED（通过）/ REJECTED（拒绝）
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const HumanInterventionNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  const sourceHandles = [
    { id: 'TIMEOUT', label: 'TIMEOUT', color: '#fa8c16' }
  ]

  return (
    <BaseNode
      {...props}
      sourceHandles={sourceHandles}
    />
  )
}

export default memo(HumanInterventionNode)
