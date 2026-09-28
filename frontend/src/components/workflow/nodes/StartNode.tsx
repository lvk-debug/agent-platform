/**
 * 用户输入节点 — 工作流入口
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const StartNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} showTarget={false} description="用于节点开始" />
}

export default memo(StartNode)
