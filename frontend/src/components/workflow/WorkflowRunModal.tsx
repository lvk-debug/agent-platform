/**
 * 工作流运行弹窗 — 根据起始节点变量动态生成输入表单，展示运行结果
 */
import React, { useEffect, useState } from 'react'
import { Modal, Form, Input, InputNumber, Button, Typography, Tag, Spin, Collapse } from 'antd'
import { CaretRightOutlined } from '@ant-design/icons'
import { workflowApi } from '@/services/workflow'

const { Text } = Typography
const { TextArea } = Input

interface StartVariable {
  key: string
  type?: string
  required?: boolean
  label?: string
}

interface WorkflowRunModalProps {
  open: boolean
  onClose: () => void
  appId: number
  /** 起始节点的变量配置 */
  variables: StartVariable[]
}

const WorkflowRunModal: React.FC<WorkflowRunModalProps> = ({ open, onClose, appId, variables }) => {
  const [form] = Form.useForm()
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  // 打开时重置状态
  useEffect(() => {
    if (open) {
      setResult(null)
      setError(null)
      // 设置默认值
      const defaults: Record<string, any> = {}
      for (const v of variables) {
        if (v.key) defaults[v.key] = ''
      }
      form.setFieldsValue(defaults)
    }
  }, [open, variables, form])

  const handleRun = async () => {
    try {
      await form.validateFields()
    } catch {
      return
    }

    const values = form.getFieldsValue()
    setRunning(true)
    setResult(null)
    setError(null)

    try {
      const res = await workflowApi.run(appId, { inputs: values })
      setResult(res)
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || '执行失败')
    } finally {
      setRunning(false)
    }
  }

  const renderInputField = (v: StartVariable) => {
    const name = v.key
    if (!name) return null

    const label = <span>{v.label || name} <code className="text-xs text-gray-400">{v.key}</code></span>
    const rules = v.required !== false ? [{ required: true, message: `请输入 ${name}` }] : []

    switch (v.type) {
      case 'number':
        return (
          <Form.Item key={name} name={name} label={label} rules={rules}>
            <InputNumber className="w-full" placeholder={`输入 ${name}`} />
          </Form.Item>
        )
      case 'array':
      case 'object':
        return (
          <Form.Item key={name} name={name} label={label} rules={rules}>
            <TextArea
              rows={3}
              placeholder={v.type === 'array' ? '["值1", "值2"]' : '{"key": "value"}'}
              style={{ fontFamily: 'monospace', fontSize: 12 }}
            />
          </Form.Item>
        )
      default: // string, file 等
        return (
          <Form.Item key={name} name={name} label={label} rules={rules}>
            <Input placeholder={`输入 ${name}`} />
          </Form.Item>
        )
    }
  }

  return (
    <Modal
      title="运行工作流"
      open={open}
      onCancel={onClose}
      width={600}
      footer={
        <div className="flex justify-between">
          <Button onClick={onClose}>关闭</Button>
          <Button type="primary" icon={<CaretRightOutlined />} loading={running} onClick={handleRun}>
            运行
          </Button>
        </div>
      }
    >
      {/* 输入表单 */}
      {variables.length > 0 ? (
        <Form form={form} layout="vertical" className="mb-4">
          <Text strong className="block mb-2">输入变量</Text>
          {variables.map(renderInputField)}
        </Form>
      ) : (
        <div className="mb-4 p-3 bg-gray-50 rounded text-sm text-gray-500">
          起始节点未配置输入变量，将使用空输入执行
        </div>
      )}

      {/* 运行结果 */}
      {running && (
        <div className="text-center py-6">
          <Spin tip="工作流执行中..." />
        </div>
      )}

      {error && (
        <div className="border border-red-200 rounded-lg p-3 bg-red-50">
          <Text strong className="text-xs text-red-600 block mb-1">执行失败</Text>
          <Text className="text-sm text-red-500">{error}</Text>
        </div>
      )}

      {result && (
        <div>
          {/* 状态栏 */}
          <div className="flex items-center gap-2 mb-3">
            <Tag color={result.status === 'completed' ? 'green' : 'red'}>
              {result.status === 'completed' ? '成功' : '失败'}
            </Tag>
            {result.run_id && <Text type="secondary" className="text-xs">ID: {result.run_id}</Text>}
          </div>

          {/* 最终输出 */}
          {result.outputs && Object.keys(result.outputs).length > 0 && (
            <div className="border border-green-200 rounded-lg p-3 mb-3 bg-green-50">
              <Text strong className="text-xs block mb-2 text-green-700">最终输出</Text>
              <div className="space-y-1">
                {Object.entries(result.outputs).map(([key, val]) => (
                  <div key={key} className="flex items-start gap-2">
                    <code className="text-xs bg-green-100 px-1.5 py-0.5 rounded text-green-800 shrink-0">{key}</code>
                    <span className="text-xs text-gray-700 break-all whitespace-pre-wrap">
                      {typeof val === 'object' ? JSON.stringify(val, null, 2) : String(val ?? '')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 各节点运行详情 */}
          {result.node_runs && Object.keys(result.node_runs).length > 0 && (
            <Collapse
              size="small"
              className="mb-3"
              items={Object.entries(result.node_runs).map(([nodeId, output]) => ({
                key: nodeId,
                label: <span className="text-xs font-mono">{nodeId}</span>,
                children: (
                  <pre className="text-xs bg-gray-50 p-2 rounded overflow-auto max-h-48 m-0">
                    {typeof output === 'object' ? JSON.stringify(output, null, 2) : String(output ?? '')}
                  </pre>
                ),
              }))}
            />
          )}
        </div>
      )}
    </Modal>
  )
}

export default WorkflowRunModal
