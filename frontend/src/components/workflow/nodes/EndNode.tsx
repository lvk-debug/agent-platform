/**
 * 直接回复节点 — 工作流出口
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const EndNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} showSource={false} description="设置回复内容，可引用上游变量" />
}

export default memo(EndNode)
