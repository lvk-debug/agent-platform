/**
 * 开始节点配置 — 定义输入字段
 */
import React from 'react'
import { Form, Input, Select, Button, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'

const { Text } = Typography

const StartConfig: React.FC = () => (
  <div>
    <div className="flex items-center justify-between mb-3">
      <div>
        <Text strong>输入字段</Text>
        <div className="text-xs text-gray-400 mt-0.5">设置的输入可在工作流中使用</div>
      </div>
    </div>
    <Form.List name="variables" initialValue={[{ key: 'query', type: 'string', required: true, label: '输入问题' }]}>
      {(fields, { add, remove }) => (
        <>
          {fields.map(({ key, name, ...restField }) => (
            <div key={key} className="flex items-center gap-2 mb-2 p-2 bg-gray-50 rounded-md">
              <Form.Item {...restField} name={[name, 'key']} noStyle rules={[{ required: true, message: '请输入变量名' }]}>
                <Input placeholder="变量名" className="flex-1" />
              </Form.Item>
              <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="string">
                <Select className="w-28" options={[
                  { value: 'string', label: 'String' },
                  { value: 'number', label: 'Number' },
                  { value: 'array', label: 'Array' },
                  { value: 'object', label: 'Object' },
                  { value: 'file', label: 'File' },
                  { value: 'array[file]', label: 'Array[File]' },
                ]} />
              </Form.Item>
              <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} size="small" />
            </div>
          ))}
          <Button type="dashed" onClick={() => add({ id: Date.now().toString(), key: '', type: 'string', required: true })} block icon={<PlusOutlined />}>
            添加
          </Button>
        </>
      )}
    </Form.List>
  </div>
)

export default StartConfig
