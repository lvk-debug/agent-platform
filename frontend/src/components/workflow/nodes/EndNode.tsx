/**
 * 结束节点 — 工作流出口
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const EndNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} showSource={false} />
}

export default memo(EndNode)
