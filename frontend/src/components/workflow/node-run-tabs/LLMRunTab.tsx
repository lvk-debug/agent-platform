/**
 * LLM 运行调试 Tab — 用户消息输入 / 运行按钮 / 结果展示
 */
import React from 'react'
import { Form, Input, Button, Typography } from 'antd'
import { CaretRightOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'

const { Text } = Typography

interface LLMRunTabProps {
  form: FormInstance
  llmRunUserMessage: string
  onUserMessageChange: (val: string) => void
  llmRunResult: any
  llmRunLoading: boolean
  onRun: () => void
}

const LLMRunTab: React.FC<LLMRunTabProps> = ({
  form, llmRunUserMessage, onUserMessageChange, llmRunResult, llmRunLoading, onRun,
}) => {
  const watchedOutputType = Form.useWatch('output_type', form) || 'text'
  const watchedOutputVariables = Form.useWatch('output_variables', form) || []

  return (
    <div className="mt-2">
      {/* 用户消息输入 */}
      <div className="mb-4">
        <Text strong className="block mb-2">用户消息</Text>
        <Input.TextArea
          value={llmRunUserMessage}
          onChange={(e) => onUserMessageChange(e.target.value)}
          placeholder="输入用户消息，点击运行后将作为 user 消息发送给 LLM"
          autoSize={{ minRows: 3, maxRows: 8 }}
        />
      </div>

      {/* 运行按钮 */}
      <div className="mb-4">
        <Button type="primary" icon={<CaretRightOutlined />} loading={llmRunLoading} onClick={onRun} block>
          运行
        </Button>
      </div>

      {/* 运行结果 */}
      {llmRunResult ? (
        <div>
          <div className="text-xs text-gray-500 mb-2 flex items-center gap-2">
            <span>模型: <code>{llmRunResult.model || '-'}</code></span>
            {llmRunResult.usage && <span>· tokens: {llmRunResult.usage.total_tokens || '-'}</span>}
          </div>

          {/* 结构化输出：按 output_variables 配置展示解析字段 */}
          {watchedOutputType === 'structured' && watchedOutputVariables.length > 0 && (
            <div className="border border-green-200 rounded-lg p-3 mb-2 bg-green-50">
              <Text strong className="text-xs block mb-2 text-green-700">结构化输出</Text>
              <div className="space-y-1.5">
                {watchedOutputVariables.map((v: { name: string; type: string }) => {
                  const parsed = llmRunResult.structured_output
                  const value = parsed && v.name in parsed ? parsed[v.name] : undefined
                  return (
                    <div key={v.name} className="flex items-start gap-2">
                      <code className="text-xs bg-green-100 px-1.5 py-0.5 rounded text-green-800 shrink-0">{v.name}</code>
                      <span className="text-xs text-gray-400 shrink-0">{v.type}</span>
                      <span className="text-xs text-gray-700 break-all flex-1">
                        {value !== undefined
                          ? (typeof value === 'object' ? JSON.stringify(value) : String(value))
                          : <span className="text-gray-300">未解析</span>}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {/* 原始回复内容 */}
          <div className="border border-gray-200 rounded-lg p-3">
            <Text strong className="text-xs block mb-2">
              {watchedOutputType === 'structured' ? '原始回复' : '回复内容'}
            </Text>
            <div className="text-sm whitespace-pre-wrap" style={{ fontFamily: 'inherit' }}>
              {llmRunResult.content}
            </div>
          </div>

          {llmRunResult.reasoning_content && (
            <div className="border border-gray-200 rounded-lg p-3 mt-2">
              <Text strong className="text-xs block mb-2">推理内容</Text>
              <div className="text-xs text-gray-500 whitespace-pre-wrap">
                {llmRunResult.reasoning_content}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-8 text-gray-400">
          {llmRunLoading ? '正在调用 LLM...' : '点击运行查看结果'}
        </div>
      )}
    </div>
  )
}

export default LLMRunTab
