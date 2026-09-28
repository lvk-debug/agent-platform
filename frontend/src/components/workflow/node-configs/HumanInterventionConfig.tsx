/**
 * 人工干预节点配置 — 提示消息 / 超时 / 输出
 */
import React from 'react'
import { Form, Input, InputNumber } from 'antd'

const { TextArea } = Input

const HumanInterventionConfig: React.FC = () => (
  <>
    <Form.Item name="message" label="提示消息">
      <TextArea rows={2} placeholder="请审批此操作" />
    </Form.Item>
    <Form.Item name="timeout" label="超时时间（秒）" initialValue={300}>
      <InputNumber className="w-full" min={1} max={3600} />
    </Form.Item>
    <Form.Item name="timeout_output" label="超时输出值" initialValue="timeout">
      <Input />
    </Form.Item>
    <Form.Item name="output_key" label="输出键名" initialValue="output">
      <Input />
    </Form.Item>
  </>
)

export default HumanInterventionConfig
