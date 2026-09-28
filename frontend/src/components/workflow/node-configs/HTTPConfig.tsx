/**
 * HTTP 节点配置 — 方法 / URL / 请求头 / 请求体 / 超时
 */
import React from 'react'
import { Form, Input, Select, InputNumber } from 'antd'

const { TextArea } = Input

const HTTPConfig: React.FC = () => (
  <>
    <Form.Item name="method" label="请求方法" initialValue="GET">
      <Select>
        <Select.Option value="GET">GET</Select.Option>
        <Select.Option value="POST">POST</Select.Option>
        <Select.Option value="PUT">PUT</Select.Option>
        <Select.Option value="DELETE">DELETE</Select.Option>
      </Select>
    </Form.Item>
    <Form.Item name="url" label="URL">
      <Input placeholder="https://api.example.com/endpoint" />
    </Form.Item>
    <Form.Item name="headers" label="请求头（JSON）">
      <TextArea rows={2} placeholder='{"Content-Type": "application/json"}' />
    </Form.Item>
    <Form.Item name="body" label="请求体（JSON）">
      <TextArea rows={3} placeholder='{"key": "value"}' />
    </Form.Item>
    <Form.Item name="timeout" label="超时（秒）" initialValue={30}>
      <InputNumber className="w-full" min={1} max={300} />
    </Form.Item>
    <Form.Item name="output_key" label="输出键名" initialValue="response">
      <Input />
    </Form.Item>
  </>
)

export default HTTPConfig
