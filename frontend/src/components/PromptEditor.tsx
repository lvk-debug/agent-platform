import React from 'react'
import { Input, Space } from 'antd'

const { TextArea } = Input

interface PromptEditorProps {
  systemPrompt?: string
  onChange?: (systemPrompt: string) => void
}

const PromptEditor: React.FC<PromptEditorProps> = ({
  systemPrompt = '',
  onChange
}) => {
  return (
    <Space direction="vertical" className="w-full" size={16}>
      <div>
        <div className="mb-2 font-medium">系统提示词</div>
        <TextArea
          rows={6}
          placeholder="输入系统提示词，指导模型如何回答用户问题..."
          value={systemPrompt}
          onChange={(e) => onChange?.(e.target.value)}
          className="resize-y"
        />
      </div>
    </Space>
  )
}

export default PromptEditor
