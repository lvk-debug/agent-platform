/**
 * DSL 导入弹窗
 */
import React, { useState } from 'react'
import { Modal, Input, Upload, Button, message, Tabs } from 'antd'
import { UploadOutlined, FileTextOutlined } from '@ant-design/icons'
import { DSLData } from '@/services/workflow'

const { TextArea } = Input

interface DSLImportModalProps {
  open: boolean
  onClose: () => void
  onImport: (dsl: DSLData) => void
}

const DSLImportModal: React.FC<DSLImportModalProps> = ({ open, onClose, onImport }) => {
  const [dslText, setDslText] = useState('')

  const handleImportText = () => {
    if (!dslText.trim()) {
      message.warning('请输入 DSL JSON')
      return
    }
    try {
      const dsl = JSON.parse(dslText) as DSLData
      if (!dsl.nodes || !Array.isArray(dsl.nodes)) {
        message.error('DSL 格式错误：缺少 nodes 数组')
        return
      }
      onImport(dsl)
      setDslText('')
      onClose()
    } catch {
      message.error('JSON 解析失败，请检查格式')
    }
  }

  const handleImportFile = (file: File) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const dsl = JSON.parse(content) as DSLData
        if (!dsl.nodes || !Array.isArray(dsl.nodes)) {
          message.error('DSL 格式错误：缺少 nodes 数组')
          return
        }
        onImport(dsl)
        onClose()
      } catch {
        message.error('文件解析失败，请检查 JSON 格式')
      }
    }
    reader.readAsText(file)
    return false // 阻止自动上传
  }

  return (
    <Modal
      title="导入 DSL"
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
    >
      <Tabs
        items={[
          {
            key: 'text',
            label: (
              <span>
                <FileTextOutlined /> 粘贴 JSON
              </span>
            ),
            children: (
              <div>
                <TextArea
                  value={dslText}
                  onChange={(e) => setDslText(e.target.value)}
                  rows={12}
                  placeholder="粘贴 DSL JSON..."
                  style={{ fontFamily: 'monospace' }}
                />
                <div className="mt-3 text-right">
                  <Button type="primary" onClick={handleImportText}>
                    导入
                  </Button>
                </div>
              </div>
            ),
          },
          {
            key: 'file',
            label: (
              <span>
                <UploadOutlined /> 上传文件
              </span>
            ),
            children: (
              <Upload.Dragger
                accept=".json"
                beforeUpload={handleImportFile}
                showUploadList={false}
              >
                <p className="text-4xl text-text-secondary">
                  <UploadOutlined />
                </p>
                <p>点击或拖拽 JSON 文件到此区域</p>
              </Upload.Dragger>
            ),
          },
        ]}
      />
    </Modal>
  )
}

export default DSLImportModal
