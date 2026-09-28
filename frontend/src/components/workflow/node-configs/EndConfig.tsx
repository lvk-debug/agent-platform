/**
 * 直接回复节点配置 — 回复内容 + 变量引用
 */
import React from 'react'
import { Form, Input, Button, Popover, Typography, Tooltip } from 'antd'
import { FunctionOutlined, InfoCircleOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { UpstreamNode } from '../shared/VarDropdown'
import VarDropdown from '../shared/VarDropdown'

const { TextArea } = Input
const { Text } = Typography

interface EndConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
}

const EndConfig: React.FC<EndConfigProps> = ({ form, upstreamNodes }) => (
  <>
    <div className="mb-3">
      <div className="flex items-center gap-1 mb-2">
        <Text strong>回复</Text>
        <Tooltip title="设置直接回复的内容，可引用上游节点的变量">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <div className="flex items-center gap-2 mb-3">
        <Form.Item name="output_key" noStyle initialValue="output">
          <Input size="small" placeholder="输出键名" style={{ width: 120 }} />
        </Form.Item>
        <Text type="secondary" className="text-xs">回复变量数: 1</Text>
      </div>
      <div className="border border-gray-200 rounded-lg p-3 relative">
        <Form.Item name="reply_content" noStyle>
          <TextArea
            rows={4}
            placeholder="输入回复内容，使用 / 或点击 {x} 插入变量"
            style={{ border: 'none', padding: 0, resize: 'none' }}
          />
        </Form.Item>
        <div className="absolute top-2 right-2">
          <Popover
            content={
              <VarDropdown
                upstreamNodes={upstreamNodes}
                onChange={(val) => {
                  const current = form.getFieldValue('reply_content') || ''
                  form.setFieldsValue({ reply_content: current + `{{${val}}}` })
                }}
              />
            }
            trigger="click"
            placement="bottomRight"
            overlayInnerStyle={{ padding: 0, width: 280 }}
          >
            <Tooltip title="插入变量">
              <Button type="text" size="small" icon={<FunctionOutlined />} className="text-gray-400" />
            </Tooltip>
          </Popover>
        </div>
      </div>
    </div>
  </>
)

export default EndConfig
