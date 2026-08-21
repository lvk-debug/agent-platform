/**
 * 工具节点
 * Dify 风格：显示输入/输出变量列表，带类型标签
 */
import React, { memo } from 'react'
import { Handle, Position } from 'reactflow'
import { ToolOutlined } from '@ant-design/icons'

interface ToolInput {
  name: string
  type: string
  required?: boolean
  label?: string
}

interface ToolOutput {
  name: string
  type: string
}

interface ToolNodeData {
  label: string
  description?: string
  nodeType: string
  config?: {
    tool_name?: string
    tool_description?: string
    inputs?: ToolInput[]
    outputs?: ToolOutput[]
    [key: string]: any
  }
}

// 默认输入参数
const DEFAULT_INPUTS: ToolInput[] = [
  { name: 'city', type: 'String', required: false },
  { name: 'gps', type: 'String', required: false },
  { name: 'ip', type: 'String', required: false },
  { name: 'startDate', type: 'String', required: false },
  { name: 'endDate', type: 'String', required: false },
  { name: 'hour', type: 'String', required: false },
]

// 默认输出参数
const DEFAULT_OUTPUTS: ToolOutput[] = [
  { name: 'message', type: 'string' },
  { name: 'data', type: 'Array<Object>' },
  { name: 'code', type: 'integer' },
]

const ToolNode: React.FC<{ data: ToolNodeData; selected: boolean; id: string }> = ({ data, selected }) => {
  const config = data.config || {}
  const inputs = config.inputs && config.inputs.length > 0 ? config.inputs : DEFAULT_INPUTS
  const outputs = config.outputs && config.outputs.length > 0 ? config.outputs : DEFAULT_OUTPUTS

  return (
    <div
      className={`bg-white rounded-lg border shadow-sm transition-all ${
        selected ? 'shadow-md border-blue-400' : 'border-gray-200'
      }`}
      style={{ minWidth: 180, maxWidth: 280 }}
    >
      {/* 节点头部 */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-100">
        <div
          className="flex items-center justify-center w-6 h-6 rounded-md text-white text-xs flex-shrink-0"
          style={{ backgroundColor: '#595959' }}
        >
          <ToolOutlined />
        </div>
        <span className="text-sm font-medium text-gray-800 truncate flex-1">
          {data.label || '工具节点'}
        </span>
      </div>

      {/* 输入变量列表 */}
      <div className="px-3 py-2 border-b border-gray-50">
        <div className="text-[10px] text-gray-400 mb-1 font-medium">输入</div>
        <div className="flex flex-wrap gap-1">
          {inputs.slice(0, 6).map((input) => (
            <div key={input.name} className="flex items-center gap-1 text-xs">
              {input.required && <span className="text-red-500 text-[10px]">*</span>}
              <span className="text-gray-600">{input.name}</span>
              <span className="px-1 py-0.5 bg-gray-100 text-gray-500 rounded text-[10px]">
                {input.type}
              </span>
            </div>
          ))}
          {inputs.length > 6 && (
            <span className="text-[10px] text-gray-400">+{inputs.length - 6}</span>
          )}
        </div>
      </div>

      {/* 输出变量列表 */}
      <div className="px-3 py-2">
        <div className="text-[10px] text-gray-400 mb-1 font-medium">输出</div>
        <div className="flex flex-wrap gap-1">
          {outputs.map((output) => (
            <div key={output.name} className="flex items-center gap-1 text-xs">
              <span className="text-gray-600">{output.name}</span>
              <span className="px-1 py-0.5 bg-gray-100 text-gray-500 rounded text-[10px]">
                {output.type}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 左侧 target 连接点 */}
      <Handle
        type="target"
        position={Position.Left}
        style={{ background: '#595959', width: 8, height: 8 }}
      />

      {/* 右侧 source 连接点 */}
      <Handle
        type="source"
        position={Position.Right}
        style={{ background: '#595959', width: 8, height: 8 }}
      />
    </div>
  )
}

export default memo(ToolNode)
