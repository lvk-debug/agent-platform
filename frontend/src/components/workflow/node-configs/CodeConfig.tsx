/**
 * 代码节点配置 — 语言 / 代码 / 输出键名
 */
import React from 'react'
import { Form, Input, Select } from 'antd'

const { TextArea } = Input

const CodeConfig: React.FC = () => (
  <>
    <Form.Item name="language" label="语言" initialValue="python">
      <Select>
        <Select.Option value="python">Python</Select.Option>
      </Select>
    </Form.Item>
    <Form.Item name="code" label="代码">
      <TextArea
        rows={8}
        placeholder={'# 可用变量: inputs, node_outputs, merged\n# 设置 result 作为输出\nresult = merged.get("query", "").upper()'}
        style={{ fontFamily: 'monospace' }}
      />
    </Form.Item>
    <Form.Item name="output_key" label="输出键名" initialValue="output">
      <Input />
    </Form.Item>
  </>
)

export default CodeConfig
