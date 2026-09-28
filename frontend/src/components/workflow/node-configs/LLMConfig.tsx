/**
 * LLM 节点配置 — 模型选择 / 提示词 / 用户消息 / 高级参数 / 输出变量
 */
import React from 'react'
import {
  Form, Input, Select, InputNumber, Button, Divider,
  Typography, Tooltip,
} from 'antd'
import { SettingOutlined, InfoCircleOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { ModelData } from '@/services/models'
import type { UpstreamNode } from '../shared/VarDropdown'
import PromptEditor from '../shared/PromptEditor'

const { Text } = Typography

interface LLMConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
  availableModels: ModelData[]
  modelsLoading: boolean
  /** 输出类型 (Form.useWatch 的结果) */
  watchedOutputType: string
}

const TYPE_OPTIONS = [
  { value: 'String', label: 'String' },
  { value: 'Number', label: 'Number' },
  { value: 'Boolean', label: 'Boolean' },
  { value: 'Array', label: 'Array' },
  { value: 'Object', label: 'Object' },
]

const LLMConfig: React.FC<LLMConfigProps> = ({
  form, upstreamNodes, availableModels, modelsLoading, watchedOutputType,
}) => {

  return (
    <>
      {/* 模型 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-red-500">*</span>
          <Text strong>模型</Text>
          <Tooltip title="选择用于此节点的大语言模型">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <div className="flex gap-2">
          <Form.Item name="model_id" noStyle>
            <Select
              placeholder={modelsLoading ? "加载中..." : "选择模型"}
              className="flex-1"
              allowClear
              showSearch
              optionFilterProp="label"
              loading={modelsLoading}
              notFoundContent={modelsLoading ? "加载中..." : "暂无可用模型"}
            >
              {availableModels.filter(m => m.is_active).map((model) => (
                <Select.Option key={model.id} value={model.id} label={model.name}>
                  <div className="flex items-center justify-between">
                    <span>{model.name}</span>
                    <span className="text-xs text-gray-400">{model.model_id}</span>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Tooltip title="模型设置">
            <Button icon={<SettingOutlined />} />
          </Tooltip>
        </div>
      </div>

      {/* 系统提示词 */}
      <PromptEditor
        form={form}
        upstreamNodes={upstreamNodes}
        fieldName="prompt"
        label="提示词"
        placeholder="你是一个专业的助手，请根据用户消息进行回答"
        minRows={4}
      />

      {/* 用户消息 */}
      <PromptEditor
        form={form}
        upstreamNodes={upstreamNodes}
        fieldName="user_message"
        label="用户消息"
        placeholder="请根据以下内容回答问题：\n\n{{node_id.output}}"
        minRows={4}
      />

      {/* 高级参数 */}
      <Divider className="my-3" />
      <div className="flex items-center gap-1 mb-3">
        <SettingOutlined className="text-gray-400" />
        <Text type="secondary">高级参数</Text>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div>
          <Text type="secondary" className="text-xs block mb-1">温度</Text>
          <Form.Item name="temperature" initialValue={0.7} noStyle>
            <InputNumber className="w-full" size="small" min={0} max={2} step={0.1} />
          </Form.Item>
        </div>
        <div>
          <Text type="secondary" className="text-xs block mb-1">最大 Token</Text>
          <Form.Item name="max_tokens" initialValue={2048} noStyle>
            <InputNumber className="w-full" size="small" min={1} max={8192} />
          </Form.Item>
        </div>
        <div>
          <Text type="secondary" className="text-xs block mb-1">Top P</Text>
          <Form.Item name="top_p" initialValue={1.0} noStyle>
            <InputNumber className="w-full" size="small" min={0} max={1} step={0.1} />
          </Form.Item>
        </div>
      </div>

      {/* 输出变量 */}
      <Divider className="my-3" />
      <div className="mb-4">
        <div className="flex items-center justify-between mb-3">
          <Text strong>输出变量</Text>
        </div>

        <div className="mb-3">
          <Form.Item name="output_type" initialValue="text" noStyle>
            <Select size="small">
              <Select.Option value="text">文本输出</Select.Option>
              <Select.Option value="structured">结构化输出</Select.Option>
            </Select>
          </Form.Item>
        </div>

        <div className="mb-3">
          <Text type="secondary" className="text-xs block mb-1">输出键名</Text>
          <Form.Item name="output_key" initialValue="output" noStyle>
            <Input size="small" placeholder="output" />
          </Form.Item>
        </div>

        {watchedOutputType === 'structured' && (
          <>
            <div className="mb-3">
              <div className="flex items-center gap-1 mb-1">
                <Text type="secondary" className="text-xs">JSON Schema</Text>
                <Tooltip title="定义 LLM 输出的 JSON 结构，模型将按照此 Schema 返回数据">
                  <InfoCircleOutlined className="text-gray-400 text-xs" />
                </Tooltip>
              </div>
              <Form.Item name="output_schema" noStyle>
                <Input.TextArea
                  rows={4}
                  placeholder={`{\n  "type": "object",\n  "properties": {\n    "answer": { "type": "string" },\n    "confidence": { "type": "number" }\n  },\n  "required": ["answer"]\n}`}
                  style={{ fontFamily: 'monospace', fontSize: 12 }}
                />
              </Form.Item>
            </div>

            <div className="mb-3">
              <div className="flex items-center gap-1 mb-2">
                <Text type="secondary" className="text-xs">输出字段</Text>
                <Tooltip title="从 JSON Schema 中提取的字段，将作为独立变量供下游节点引用">
                  <InfoCircleOutlined className="text-gray-400 text-xs" />
                </Tooltip>
              </div>
              <Form.List name="output_variables" initialValue={[]}>
                {(fields, { add, remove }) => (
                  <>
                    {fields.map(({ key, name, ...restField }) => (
                      <div key={key} className="flex items-center gap-2 mb-2">
                        <Form.Item {...restField} name={[name, 'name']} noStyle>
                          <Input size="small" placeholder="字段名" className="flex-1" />
                        </Form.Item>
                        <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="String">
                          <Select size="small" style={{ width: 90 }} options={TYPE_OPTIONS} />
                        </Form.Item>
                        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} size="small" />
                      </div>
                    ))}
                    <Button type="dashed" onClick={() => add({ name: '', type: 'String' })} block icon={<PlusOutlined />} size="small">
                      添加输出字段
                    </Button>
                  </>
                )}
              </Form.List>
            </div>
          </>
        )}
      </div>
    </>
  )
}

export default LLMConfig
