/**
 * 上下文选择器（@ 面板）
 *
 * 只负责分发：文档走页码列表，视频走字幕列表，两者交互一致。
 * 选中即加入并关闭，符合「快速追加一个上下文」的心智。
 */

import React from 'react'
import { Modal } from 'antd'
import type { ContextRef, LearningResource, TranscriptCue } from '../../../types/learning'
import useBreakpoint from '../../../hooks/useBreakpoint'
import ContextPickerDocument from './ContextPickerDocument'
import ContextPickerVideo from './ContextPickerVideo'

interface ContextPickerProps {
  open: boolean
  resource: LearningResource
  /** 视频模式的字幕来源（复用页面已加载的数据） */
  cues: TranscriptCue[]
  selected: ContextRef[]
  onClose: () => void
  onConfirm: (ref: ContextRef) => void
}

const ContextPicker: React.FC<ContextPickerProps> = ({
  open,
  resource,
  cues,
  selected,
  onClose,
  onConfirm,
}) => {
  const { stackVertically } = useBreakpoint()
  const isDocument = resource.type === 'document'

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      title={isDocument ? '添加文档页到上下文' : '添加视频片段到上下文'}
      width={stackVertically ? '92vw' : 480}
      styles={{ body: { height: '60vh', padding: 0 } }}
    >
      {isDocument ? (
        <ContextPickerDocument
          resource={resource}
          selected={selected}
          onConfirm={(ref) => {
            onConfirm(ref)
            onClose()
          }}
        />
      ) : (
        <ContextPickerVideo
          cues={cues}
          selected={selected}
          onConfirm={(ref) => {
            onConfirm(ref)
            onClose()
          }}
        />
      )}
    </Modal>
  )
}

export default ContextPicker
