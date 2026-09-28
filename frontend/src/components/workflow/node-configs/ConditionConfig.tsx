/**
 * 条件分支节点配置 — IF / ELIF / ELSE 条件行 + 变量选择
 */
import React, { useMemo } from 'react'
import { Form, Input, Select, Button, Popover, Tag, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined, FunctionOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { UpstreamNode } from '../shared/VarDropdown'
import VarDropdown from '../shared/VarDropdown'

const { Text } = Typography

interface ConditionConfigProps {
  form: FormInstance
  upstreamNodes: UpstreamNode[]
}

const OPERATORS = [
  { value: 'contains', label: '包含' },
  { value: 'not_contains', label: '不包含' },
  { value: 'equals', label: '等于' },
  { value: 'not_equals', label: '不等于' },
  { value: 'gt', label: '大于' },
  { value: 'lt', label: '小于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lte', label: '小于等于' },
  { value: 'empty', label: '为空' },
  { value: 'not_empty', label: '不为空' },
]

interface ConditionRowProps {
  name: number
  restField: any
  label: string
  labelColor: string
  canDelete: boolean
  form: FormInstance
  upstreamNodes: UpstreamNode[]
  onRemove?: () => void
}

const ConditionRow: React.FC<ConditionRowProps> = ({
  name, restField, label, labelColor, canDelete, form, upstreamNodes, onRemove,
}) => (
  <div className="border border-gray-200 rounded-lg mb-3 overflow-hidden">
    <div className="flex items-center justify-between px-3 py-2" style={{ background: '#fafafa', borderBottom: '1px solid #f0f0f0' }}>
      <div className="flex items-center gap-2">
        <span style={{ color: labelColor, fontWeight: 700, fontSize: 13 }}>{label}</span>
        {canDelete && <Tag color="blue" style={{ marginLeft: 4, fontSize: 11 }}>CASE{name + 1}</Tag>}
      </div>
      {canDelete && onRemove && (
        <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={onRemove} />
      )}
    </div>
    <div className="p-3">
      <div className="flex items-center gap-2">
        <Form.Item {...restField} name={[name, 'variable']} noStyle>
          <Popover
            content={
              <VarDropdown
                upstreamNodes={upstreamNodes}
                onChange={(val) => {
                  const fieldsValues = form.getFieldsValue()
                  const branches = fieldsValues.branches || []
                  if (branches[name]) {
                    branches[name].variable = val
                    form.setFieldsValue({ branches })
                  }
                }}
                currentValue={form.getFieldValue(['branches', name, 'variable'])}
              />
            }
            trigger="click"
            placement="bottomLeft"
            overlayInnerStyle={{ padding: 0, width: 280 }}
          >
            <div style={{
              border: '1px solid #d9d9d9', borderRadius: 6, padding: '5px 10px',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
              minWidth: 130, fontSize: 13, background: '#fff',
            }}>
              <FunctionOutlined style={{ color: '#8c8c8c' }} />
              <span style={{ color: '#8c8c8c' }}>选择变量</span>
            </div>
          </Popover>
        </Form.Item>

        <Form.Item {...restField} name={[name, 'operator']} noStyle initialValue="contains">
          <Select size="middle" style={{ minWidth: 90 }} popupMatchSelectWidth={false}>
            {OPERATORS.map((op) => (
              <Select.Option key={op.value} value={op.value}>{op.label}</Select.Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item {...restField} name={[name, 'value']} noStyle>
          <Input placeholder="值" style={{ flex: 1 }} />
        </Form.Item>
      </div>
    </div>
  </div>
)

const ConditionConfig: React.FC<ConditionConfigProps> = ({ form, upstreamNodes }) => (
  <Form.List
    name="branches"
    initialValue={[
      { variable: '', operator: 'contains', value: '', branch: 'IF' },
      { variable: '', operator: 'default', value: '', branch: 'ELSE' },
    ]}
  >
    {(fields, { add, remove }) => {
      const ifField = fields[0]
      const elseField = fields[fields.length - 1]
      const elifFields = fields.slice(1, -1)

      return (
        <div>
          {ifField && (
            <ConditionRow
              name={ifField.name} restField={ifField} label="IF" labelColor="#1677ff"
              canDelete={false} form={form} upstreamNodes={upstreamNodes}
            />
          )}

          {elifFields.map((f) => (
            <ConditionRow
              key={f.key} name={f.name} restField={f} label="ELIF" labelColor="#722ed1"
              canDelete={true} form={form} upstreamNodes={upstreamNodes}
              onRemove={() => remove(f.name)}
            />
          ))}

          <div className="flex gap-2 mb-3">
            <Button
              type="dashed"
              size="small"
              icon={<PlusOutlined />}
              onClick={() => {
                const elseIdx = fields.length - 1
                add({ variable: '', operator: 'contains', value: '', branch: 'ELIF' }, elseIdx)
              }}
            >
              添加 ELIF
            </Button>
          </div>

          {elseField && (
            <ConditionRow
              name={elseField.name} restField={elseField} label="ELSE" labelColor="#52c41a"
              canDelete={false} form={form} upstreamNodes={upstreamNodes}
            />
          )}
        </div>
      )
    }}
  </Form.List>
)

export default ConditionConfig
