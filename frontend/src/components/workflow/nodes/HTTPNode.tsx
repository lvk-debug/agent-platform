/**
 * HTTP 请求节点
 */
import React, { memo } from 'react'
import BaseNode from './BaseNode'

const HTTPNode: React.FC<{ data: any; selected: boolean; id: string }> = (props) => {
  return <BaseNode {...props} />
}

export default memo(HTTPNode)
