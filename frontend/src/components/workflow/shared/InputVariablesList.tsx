/**
 * 输入变量 Form.List — 支持变量名/类型/必填/默认值（可引用上游变量）
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Form, Input, Select, Switch, Button, Typography, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'

const { Text } = Typography

export interface VarGroup {
  label: string
  vars: Array<{ ref: string; label: string; type: string }>
}

interface InputVariablesListProps {
  form: FormInstance
  /** 可引用的变量分组列表 */
  varGroups: VarGroup[]
}

const TYPE_OPTIONS = [
  { value: 'String', label: 'String' },
  { value: 'Number', label: 'Number' },
  { value: 'Boolean', label: 'Boolean' },
  { value: 'Array', label: 'Array' },
  { value: 'Object', label: 'Object' },
]

const InputVariablesList: React.FC<InputVariablesListProps> = ({ form, varGroups }) => {
  const valueInputRefs = useRef<Record<number, HTMLInputElement | null>>({})
  const containerRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const [dropdownIdx, setDropdownIdx] = useState<number | null>(null)

  // 点击外部关闭下拉
  useEffect(() => {
    if (dropdownIdx === null) return
    const container = containerRefs.current[dropdownIdx]
    const onDocDown = (e: MouseEvent) => {
      if (!container || !container.contains(e.target as Node)) {
        setDropdownIdx(null)
      }
    }
    document.addEventListener('mousedown', onDocDown)
    return () => document.removeEventListener('mousedown', onDocDown)
  }, [dropdownIdx])

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>, index: number) => {
    if (e.key === '/') {
      e.preventDefault()
      setDropdownIdx(index)
    } else if (e.key === 'Escape') {
      setDropdownIdx(null)
    }
  }, [])

  const insertVarRef = useCallback((ref: string, index: number) => {
    const el = valueInputRefs.current[index]
    if (!el) return
    const input = (el as any)?.input ?? el
    const cursorPos = input.selectionStart ?? 0
    const text = input.value

    let slashIdx = cursorPos - 1
    while (slashIdx >= 0 && text[slashIdx] !== '/') slashIdx--
    const insertAt = slashIdx >= 0 ? slashIdx : cursorPos
    const before = text.substring(0, insertAt)
    const after = text.substring(cursorPos)
    const next = before + ref + after

    input.value = next
    const inputs = form.getFieldValue('inputs') || []
    inputs[index] = { ...inputs[index], value: next }
    form.setFieldsValue({ inputs })
    setDropdownIdx(null)

    requestAnimationFrame(() => {
      input.focus()
      const newPos = insertAt + ref.length
      input.setSelectionRange(newPos, newPos)
    })
  }, [form])

  return (
    <div className="mb-5">
      <div className="flex items-center justify-between mb-2">
        <Text strong>输入变量</Text>
        <Text type="secondary" className="text-xs">定义节点接受的输入参数</Text>
      </div>
      <Form.List name="inputs" initialValue={[]}>
        {(fields, { add, remove }) => (
          <>
            {fields.map(({ key, name, ...restField }, index) => (
              <div
                key={key}
                className="mb-2 p-2 bg-gray-50 rounded-md"
                ref={(el) => { containerRefs.current[index] = el }}
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <Form.Item {...restField} name={[name, 'name']} noStyle rules={[{ required: true, message: '请输入变量名' }]}>
                    <Input placeholder="变量名" className="flex-1" size="small" />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'type']} noStyle initialValue="String">
                    <Select size="small" style={{ width: 90 }} options={TYPE_OPTIONS} />
                  </Form.Item>
                  <Form.Item {...restField} name={[name, 'required']} noStyle valuePropName="checked" initialValue={true}>
                    <Switch size="small" checkedChildren="*" unCheckedChildren="" />
                  </Form.Item>
                  <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} size="small" />
                </div>
                {/* 默认值/引用 */}
                <div className="relative flex items-center gap-1">
                  <Form.Item {...restField} name={[name, 'value']} noStyle>
                    <Input
                      ref={(el) => { valueInputRefs.current[index] = el?.input || null }}
                      placeholder="默认值，按 / 插入变量引用"
                      size="small"
                      style={{ fontSize: 12, fontFamily: 'monospace' }}
                      onKeyDown={(e) => handleKeyDown(e, index)}
                    />
                  </Form.Item>
                  <Tooltip title="插入变量引用">
                    <Button
                      size="small"
                      type="text"
                      style={{ padding: '0 4px', fontSize: 11, fontFamily: 'monospace', color: '#8c8c8c' }}
                      onClick={() => setDropdownIdx(dropdownIdx === index ? null : index)}
                    >
                      {'{{x}}'}
                    </Button>
                  </Tooltip>
                  {dropdownIdx === index && (
                    <div style={{
                      position: 'absolute', left: 0, right: 0, top: '100%',
                      zIndex: 1050, background: '#fff', borderRadius: 8,
                      boxShadow: '0 6px 16px rgba(0,0,0,.12)', border: '1px solid #f0f0f0',
                      maxHeight: 260, overflow: 'auto', marginTop: 4,
                    }}>
                      {varGroups.length === 0 && (
                        <div style={{ padding: '12px', textAlign: 'center', color: '#bfbfbf', fontSize: 12 }}>无可引用变量</div>
                      )}
                      {varGroups.map((g) => (
                        <div key={g.label}>
                          <div style={{
                            padding: '5px 12px', fontWeight: 600, fontSize: 11,
                            color: '#8c8c8c', background: '#fafafa', borderBottom: '1px solid #f0f0f0',
                            position: 'sticky', top: 0,
                          }}>
                            {g.label}
                          </div>
                          {g.vars.map((v) => (
                            <div
                              key={v.ref}
                              onMouseDown={(e) => { e.preventDefault(); insertVarRef(v.ref, index) }}
                              style={{
                                padding: '6px 12px', cursor: 'pointer', display: 'flex',
                                justifyContent: 'space-between', alignItems: 'center',
                              }}
                              onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f5f5f5' }}
                              onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = '' }}
                            >
                              <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{
                                  color: '#8c8c8c', fontSize: 10, fontFamily: 'monospace',
                                  background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                                }}>{'{x}'}</span>
                                <span style={{ fontSize: 12 }}>{v.label}</span>
                              </span>
                              <span style={{ fontSize: 11, color: '#bfbfbf' }}>{v.type}</span>
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            <Button type="dashed" onClick={() => add({ name: '', type: 'String', required: true })} block icon={<PlusOutlined />} size="small">
              添加输入变量
            </Button>
          </>
        )}
      </Form.List>
    </div>
  )
}

export default InputVariablesList
