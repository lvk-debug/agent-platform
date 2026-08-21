/**
 * 代码执行节点
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const CodeNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} />
}

export default memo(CodeNode)
