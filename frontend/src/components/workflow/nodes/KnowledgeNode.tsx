/**
 * 知识库检索节点
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const KnowledgeNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} />
}

export default memo(KnowledgeNode)
