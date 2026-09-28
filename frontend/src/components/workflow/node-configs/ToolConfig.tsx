/**
 * 工具节点配置 — 工具选择 / 输入 / 输出 / 异常处理
 */
import React from 'react'
import {
  Form, Input, Select, InputNumber, Switch, Button, Typography, Tooltip, Tag,
} from 'antd'
import {
  PlusOutlined, DeleteOutlined, InfoCircleOutlined,
  HolderOutlined, CaretDownOutlined, CaretRightOutlined,
} from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { ToolData } from '@/services/tools'
import type { UpstreamNode } from '../shared/VarDropdown'

const { Text } = Typography

interface ToolConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
  availableTools: ToolData[]
  toolsLoading: boolean
  selectedToolId?: number
  expandedSections: Record<string, boolean>
  onToggleSection: (section: string) => void
}

const TYPE_COLORS: Record<string, string> = {
  builtin: 'green',
  plugin: 'blue',
  mcp: 'purple',
}

const ToolConfig: React.FC<ToolConfigProps> = ({
  form, upstreamNodes, availableTools, toolsLoading, selectedToolId,
  expandedSections, onToggleSection,
}) => {
  const selectedTool = availableTools.find(t => t.id === selectedToolId)
  const schemaProps = selectedTool?.parameters_schema?.properties || {}
  const schemaRequired = selectedTool?.parameters_schema?.required || []

  const defaultInputs = Object.entries(schemaProps).map(([name, prop]: [string, any]) => ({
    name,
    type: (prop.type === 'integer' || prop.type === 'number') ? 'Number' : 'String',
    required: schemaRequired.includes(name),
  }))

  const defaultOutputs = [{ name: 'result', type: 'object' }]

  return (
    <>
      {/* 工具选择 */}
      <div className="mb-5">
        <div className="flex items-center gap-1 mb-2">
          <span className="text-red-500">*</span>
          <Text strong>工具</Text>
          <Tooltip title="选择要使用的工具">
            <InfoCircleOutlined className="text-gray-400 text-xs" />
          </Tooltip>
        </div>
        <Form.Item name="tool_id" noStyle>
          <Select
            placeholder={toolsLoading ? "加载中..." : "选择工具"}
            className="w-full"
            showSearch
            optionFilterProp="label"
            loading={toolsLoading}
            notFoundContent={toolsLoading ? "加载中..." : "暂无可用工具，请先在工具管理中安装"}
          >
            {availableTools.map((tool) => (
              <Select.Option key={tool.id} value={tool.id} label={tool.name}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span>{tool.icon || '🔧'}</span>
                    <span>{tool.name}</span>
                  </div>
                  <Tag color={TYPE_COLORS[tool.tool_type] || 'default'} style={{ marginRight: 0 }}>
                    {tool.tool_type}
                  </Tag>
                </div>
              </Select.Option>
            ))}
          </Select>
        </Form.Item>
        {selectedTool?.description && (
          <Text type="secondary" className="text-xs mt-1 block">{selectedTool.description}</Text>
        )}
      </div>

      {/* 输入 Section */}
      <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
        <div
          className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
          onClick={() => onToggleSection('input')}
        >
          <div className="flex items-center gap-2">
            {expandedSections.input ? <CaretDownOutlined /> : <CaretRightOutlined />}
            <Text strong>输入</Text>
          </div>
        </div>
        {expandedSections.input && (
          <div className="p-3 space-y-3">
            <Form.List name="inputs" initialValue={defaultInputs}>
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <div key={key} className="flex items-center gap-2">
                      <HolderOutlined className="text-gray-300 cursor-move" />
                      <Form.Item {...restField} name={[name, 'name']} noStyle>
                        <Input size="small" placeholder="参数名" style={{ width: 90 }} />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'required']} noStyle valuePropName="checked">
                        <Switch size="small" checkedChildren="*" unCheckedChildren="" />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="String">
                        <Select size="small" style={{ width: 90 }} popupMatchSelectWidth={false}>
                          <Select.Option value="String">String</Select.Option>
                          <Select.Option value="Number">Number</Select.Option>
                          <Select.Option value="Boolean">Boolean</Select.Option>
                          <Select.Option value="Array">Array</Select.Option>
                          <Select.Option value="Object">Object</Select.Option>
                        </Select>
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'inputMode']} noStyle initialValue="reference">
                        <Select size="small" style={{ width: 70 }} popupMatchSelectWidth={false}>
                          <Select.Option value="reference">引用</Select.Option>
                          <Select.Option value="direct">直接</Select.Option>
                        </Select>
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'value']} noStyle>
                        <Select
                          size="small"
                          placeholder="请选择"
                          className="flex-1"
                          allowClear
                          showSearch
                          optionFilterProp="label"
                        >
                          {upstreamNodes.map((n) => (
                            <Select.Option key={n.id} value={`${n.id}.output`} label={n.data?.label || n.id}>
                              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{
                                  color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace',
                                  background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                                }}>{'{x}'}</span>
                                {n.data?.label || n.id} . output
                              </span>
                            </Select.Option>
                          ))}
                        </Select>
                      </Form.Item>
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(name)} />
                    </div>
                  ))}
                  <Button type="dashed" onClick={() => add({ name: '', type: 'String', required: false, inputMode: 'reference' })} icon={<PlusOutlined />} block size="small">
                    添加输入
                  </Button>
                </>
              )}
            </Form.List>
          </div>
        )}
      </div>

      {/* 输出 Section */}
      <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
        <div
          className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
          onClick={() => onToggleSection('output')}
        >
          <div className="flex items-center gap-2">
            {expandedSections.output ? <CaretDownOutlined /> : <CaretRightOutlined />}
            <Text strong>输出</Text>
          </div>
        </div>
        {expandedSections.output && (
          <div className="p-3">
            <Form.List name="outputs" initialValue={defaultOutputs}>
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name, ...restField }) => (
                    <div key={key} className="flex items-center gap-2 mb-2">
                      <HolderOutlined className="text-gray-300 cursor-move" />
                      <Form.Item {...restField} name={[name, 'name']} noStyle>
                        <Input size="small" placeholder="变量名" style={{ width: 100 }} />
                      </Form.Item>
                      <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="string">
                        <Input size="small" placeholder="类型" style={{ width: 100 }} disabled />
                      </Form.Item>
                      <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => remove(name)} />
                    </div>
                  ))}
                  <Button type="dashed" onClick={() => add({ name: '', type: 'string' })} icon={<PlusOutlined />} block size="small">
                    添加输出
                  </Button>
                </>
              )}
            </Form.List>
          </div>
        )}
      </div>

      {/* 异常处理 Section */}
      <div className="mb-4 border border-gray-200 rounded-lg overflow-hidden">
        <div
          className="flex items-center justify-between px-3 py-2 cursor-pointer bg-gray-50 hover:bg-gray-100"
          onClick={() => onToggleSection('errorHandling')}
        >
          <div className="flex items-center gap-2">
            {expandedSections.errorHandling ? <CaretDownOutlined /> : <CaretRightOutlined />}
            <Text strong>异常处理</Text>
          </div>
          <div onClick={(e: React.MouseEvent) => e.stopPropagation()}>
            <Form.Item name="error_handling_enabled" valuePropName="checked" noStyle>
              <Switch size="small" />
            </Form.Item>
          </div>
        </div>
        {expandedSections.errorHandling && (
          <div className="p-3">
            <div className="mb-3">
              <Text type="secondary" className="text-xs block mb-1">失败时</Text>
              <Form.Item name="error_action" noStyle initialValue="retry">
                <Select size="small" className="w-full">
                  <Select.Option value="retry">重试</Select.Option>
                  <Select.Option value="skip">跳过</Select.Option>
                  <Select.Option value="fallback">使用默认值</Select.Option>
                  <Select.Option value="stop">终止流程</Select.Option>
                </Select>
              </Form.Item>
            </div>
            <div className="mb-3">
              <Text type="secondary" className="text-xs block mb-1">重试次数</Text>
              <Form.Item name="retry_count" noStyle initialValue={3}>
                <InputNumber size="small" className="w-full" min={1} max={10} />
              </Form.Item>
            </div>
            <div>
              <Text type="secondary" className="text-xs block mb-1">超时时间（秒）</Text>
              <Form.Item name="timeout" noStyle initialValue={30}>
                <InputNumber size="small" className="w-full" min={1} max={300} />
              </Form.Item>
            </div>
          </div>
        )}
      </div>
    </>
  )
}

export default ToolConfig
