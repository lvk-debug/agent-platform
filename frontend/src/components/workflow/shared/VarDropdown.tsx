/**
 * 变量选择下拉 — 按节点类型分组展示上游节点变量
 * 用于 End、Knowledge、Condition 等节点的变量引用选择
 */
import React from 'react'
import { FunctionOutlined } from '@ant-design/icons'

export interface UpstreamNode {
  id: string
  data: { label?: string; config?: Record<string, any> }
  type?: string
}

interface VarDropdownProps {
  upstreamNodes: UpstreamNode[]
  onChange: (value: string) => void
  currentValue?: string
  emptyText?: string
}

const TYPE_LABELS: Record<string, string> = {
  llm: 'LLM',
  knowledge_retrieval: '知识检索',
  code: '代码执行',
  start: '用户输入',
  tool: '工具',
  http: 'HTTP 请求',
  end: '直接回复',
}

/** 构建分组变量列表 */
export function buildGroupedVars(upstreamNodes: UpstreamNode[]) {
  const groups: Record<string, Array<{ id: string; label: string; vars: Array<{ key: string; label: string; type: string }> }>> = {}

  for (const node of upstreamNodes) {
    const nodeType = node.type || 'unknown'
    if (!groups[nodeType]) groups[nodeType] = []

    const vars: Array<{ key: string; label: string; type: string }> = []
    if (nodeType === 'start') {
      const startVars = node.data?.config?.variables || []
      for (const sv of startVars) {
        vars.push({ key: sv.key || sv.name, label: sv.key || sv.name, type: sv.type || 'String' })
      }
    } else {
      const outputKey = node.data?.config?.output_key || 'output'
      vars.push({ key: outputKey, label: outputKey, type: 'String' })
      if (nodeType === 'llm') {
        vars.push({ key: 'reasoning_content', label: 'reasoning_content', type: 'String' })
      }
    }

    if (vars.length > 0) {
      groups[nodeType].push({ id: node.id, label: node.data?.label || node.id, vars })
    }
  }

  return groups
}

const VarDropdown: React.FC<VarDropdownProps> = ({ upstreamNodes, onChange, currentValue, emptyText = '暂无可用变量' }) => {
  const groupedNodes = buildGroupedVars(upstreamNodes)

  return (
    <div style={{ maxHeight: 320, overflow: 'auto' }}>
      {Object.entries(groupedNodes).map(([nodeType, nodeList]) => (
        <div key={nodeType}>
          <div style={{
            padding: '6px 12px', fontWeight: 600, fontSize: 12,
            color: '#8c8c8c', background: '#fafafa', borderBottom: '1px solid #f0f0f0',
          }}>
            {TYPE_LABELS[nodeType] || nodeType}
          </div>
          {nodeList.map((node) =>
            node.vars.map((v) => {
              const ref = `${node.id}.${v.key}`
              const isSelected = currentValue === ref
              return (
                <div
                  key={ref}
                  onClick={() => onChange(ref)}
                  style={{
                    padding: '7px 12px', cursor: 'pointer', display: 'flex',
                    justifyContent: 'space-between', alignItems: 'center',
                    background: isSelected ? '#e6f4ff' : undefined,
                  }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f5f5f5' }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = isSelected ? '#e6f4ff' : '' }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{
                      color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace',
                      background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                    }}>{'{x}'}</span>
                    <span style={{ fontSize: 13 }}>{node.label} . {v.label}</span>
                  </span>
                  <span style={{ fontSize: 12, color: '#bfbfbf' }}>{v.type}</span>
                </div>
              )
            })
          )}
        </div>
      ))}
      {Object.keys(groupedNodes).length === 0 && (
        <div style={{ padding: '16px 12px', textAlign: 'center', color: '#bfbfbf', fontSize: 13 }}>
          {emptyText}
        </div>
      )}
    </div>
  )
}

export default VarDropdown
