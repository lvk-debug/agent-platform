/**
 * 提示词编辑器 — 支持 { 触发变量选择下拉，插入 {{node_id.key}} 引用
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Form, Input, Typography, Tooltip } from 'antd'
import { InfoCircleOutlined, FunctionOutlined } from '@ant-design/icons'
import type { FormInstance } from 'antd'
import type { UpstreamNode } from './VarDropdown'

const { Text } = Typography

interface PromptEditorProps {
  form: FormInstance
  /** 上游节点列表（当未提供 inputVariables 时，从上游节点提取变量） */
  upstreamNodes?: UpstreamNode[]
  /** 输入变量列表（优先使用，变量名为 key，如 'user_query'） */
  inputVariables?: Array<{ name: string; type: string }>
  /** Form.Item 的 name，默认 'prompt' */
  fieldName?: string
  /** 标签文本，默认 '提示词' */
  label?: string
  /** 提示词输入框的 placeholder */
  placeholder?: string
  /** 输入框最小行数 */
  minRows?: number
}

/** 从输入变量列表构建变量组（用于 PromptEditor） */
export function buildInputVarGroups(
  inputVariables: Array<{ name: string; type: string }>,
): Array<{ label: string; vars: Array<{ ref: string; label: string; type: string }> }> {
  const groups: Array<{ label: string; vars: Array<{ ref: string; label: string; type: string }> }> = []
  const vars: Array<{ ref: string; label: string; type: string }> = []
  for (const v of inputVariables) {
    if (v.name) {
      vars.push({ ref: `{{${v.name}}}`, label: v.name, type: v.type || 'String' })
    }
  }
  if (vars.length > 0) {
    groups.push({ label: '输入变量', vars })
  }
  // 系统变量
  groups.push({
    label: 'SYSTEM',
    vars: [
      { ref: '{{sys.dialogue_count}}', label: 'sys.dialogue_count', type: 'Number' },
      { ref: '{{sys.conversation_id}}', label: 'sys.conversation_id', type: 'String' },
      { ref: '{{sys.user_id}}', label: 'sys.user_id', type: 'String' },
      { ref: '{{sys.app_id}}', label: 'sys.app_id', type: 'String' },
      { ref: '{{sys.workflow_id}}', label: 'sys.workflow_id', type: 'String' },
      { ref: '{{sys.workflow_run_id}}', label: 'sys.workflow_run_id', type: 'String' },
    ],
  })
  return groups
}

/** 构建变量列表（上游节点 + 系统变量） */
export function buildPromptVarGroups(upstreamNodes: UpstreamNode[]) {
  const groups: Array<{ label: string; vars: Array<{ ref: string; label: string; type: string }> }> = []

  const typeLabels: Record<string, string> = {
    llm: 'LLM', knowledge_retrieval: '知识检索', code: '代码执行',
    start: '用户输入', tool: '工具', http: 'HTTP 请求', end: '直接回复',
  }

  for (const n of upstreamNodes) {
    const nodeType = n.type || 'unknown'
    const vars: Array<{ ref: string; label: string; type: string }> = []

    if (nodeType === 'start') {
      const startVars = n.data?.config?.variables || []
      for (const sv of startVars) {
        const key = sv.key || sv.name
        vars.push({ ref: `{{${n.id}.${key}}}`, label: key, type: sv.type || 'String' })
      }
    } else if (nodeType === 'llm') {
      const cfg = n.data?.config || {}
      if (cfg.output_type === 'structured' && cfg.output_variables?.length > 0) {
        // 结构化输出：暴露每个输出字段
        for (const ov of cfg.output_variables) {
          if (ov.name) {
            vars.push({ ref: `{{${n.id}.${ov.name}}}`, label: ov.name, type: ov.type || 'String' })
          }
        }
      } else {
        // 文本输出：默认 output
        const outputKey = cfg.output_key || 'output'
        vars.push({ ref: `{{${n.id}.${outputKey}}}`, label: outputKey, type: 'String' })
      }
    } else {
      const outputKey = n.data?.config?.output_key || 'output'
      vars.push({ ref: `{{${n.id}.${outputKey}}}`, label: outputKey, type: 'String' })
    }

    if (vars.length > 0) {
      groups.push({ label: typeLabels[nodeType] || nodeType, vars })
    }
  }

  // 系统变量
  groups.push({
    label: 'SYSTEM',
    vars: [
      { ref: '{{sys.dialogue_count}}', label: 'sys.dialogue_count', type: 'Number' },
      { ref: '{{sys.conversation_id}}', label: 'sys.conversation_id', type: 'String' },
      { ref: '{{sys.user_id}}', label: 'sys.user_id', type: 'String' },
      { ref: '{{sys.app_id}}', label: 'sys.app_id', type: 'String' },
      { ref: '{{sys.workflow_id}}', label: 'sys.workflow_id', type: 'String' },
      { ref: '{{sys.workflow_run_id}}', label: 'sys.workflow_run_id', type: 'String' },
    ],
  })

  return groups
}

const PromptEditor: React.FC<PromptEditorProps> = ({
  form,
  upstreamNodes,
  inputVariables,
  fieldName = 'prompt',
  label = '提示词',
  placeholder = '分析用户的问题并基于上下文内容回答\n\n输入 { 插入变量，如 {{变量名}}',
  minRows = 6,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const cursorPosRef = useRef<number>(0)
  const [dropdownVisible, setDropdownVisible] = useState(false)

  // 优先使用 inputVariables，否则从 upstreamNodes 提取
  const varGroups = useMemo(
    () => inputVariables
      ? buildInputVarGroups(inputVariables)
      : buildPromptVarGroups(upstreamNodes || []),
    [inputVariables, upstreamNodes],
  )

  // 获取实际的 textarea DOM 元素
  const getTextarea = useCallback((): HTMLTextAreaElement | null => {
    const el = textareaRef.current as any
    if (!el) return null
    return el?.resizableTextArea?.textArea ?? el
  }, [])

  // 按键处理：{ 触发下拉
  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    const ta = e.currentTarget
    const cursorPos = ta.selectionStart
    // const textBefore = ta.value.substring(0, cursorPos)
    if (['{', '{'].includes(e.key)) {
      cursorPosRef.current = cursorPos + 1
      setDropdownVisible(true)
    } else {
      setDropdownVisible(false)
    }
  }, [])

  // 点击外部关闭下拉
  useEffect(() => {
    if (!dropdownVisible) return
    const handleOutsideClick = (e: MouseEvent) => {
      const container = containerRef.current
      if (container && !container.contains(e.target as Node)) {
        setDropdownVisible(false)
      }
    }
    document.addEventListener('mousedown', handleOutsideClick)
    return () => document.removeEventListener('mousedown', handleOutsideClick)
  }, [dropdownVisible])

  // 插入变量
  const insertVar = useCallback((ref: string) => {
    const textarea = getTextarea()
    if (!textarea) return
    const text = textarea.value
    const cursorPos = cursorPosRef.current

    // 从保存的光标位置往前找 {
    let braceIdx = cursorPos - 1
    while (braceIdx >= 0 && text[braceIdx] !== '{') braceIdx--
    const insertAt = braceIdx >= 0 ? braceIdx : cursorPos
    const before = text.substring(0, insertAt)
    const after = text.substring(cursorPos)
    const newText = before + ref + after

    textarea.value = newText
    form.setFieldsValue({ [fieldName]: newText })
    setDropdownVisible(false)

    requestAnimationFrame(() => {
      textarea.focus()
      const newPos = insertAt + ref.length
      textarea.setSelectionRange(newPos, newPos)
    })
  }, [form, fieldName, getTextarea])

  return (
    <div className="mb-5 relative">
      <div className="flex items-center gap-1 mb-2">
        <Text strong>{label}</Text>
        <Tooltip title="输入 { 可快速插入变量，支持 Jinja 模板语法">
          <InfoCircleOutlined className="text-gray-400 text-xs" />
        </Tooltip>
      </div>
      <div className="flex items-center gap-2 mb-2 text-xs text-gray-400">
        <span className="border border-gray-200 rounded px-1.5 py-0.5 text-[10px]">Jinja</span>
        <span>{'{{ }}'} 语法</span>
        <span className="ml-auto flex items-center gap-1">
          <FunctionOutlined /> {'{x}'} 变量
        </span>
      </div>
      <div ref={containerRef} className="relative">
        <Form.Item name={fieldName} noStyle>
          <Input.TextArea
            ref={textareaRef as any}
            autoSize={{ minRows, maxRows: 20 }}
            placeholder={placeholder}
            onKeyDown={handleKeyDown}
            style={{ fontFamily: 'monospace', fontSize: 13 }}
          />
        </Form.Item>
        {dropdownVisible && (
          <div style={{
            position: 'absolute', left: 0, right: 0, top: '100%',
            zIndex: 1050, background: '#fff', borderRadius: 8,
            boxShadow: '0 6px 16px rgba(0,0,0,.12)', border: '1px solid #f0f0f0',
            maxHeight: 320, overflow: 'auto', marginTop: 4,
          }}>
            {varGroups.length === 0 && (
              <div style={{ padding: '12px', textAlign: 'center', color: '#bfbfbf', fontSize: 13 }}>无匹配变量</div>
            )}
            {varGroups.map((g) => (
              <div key={g.label}>
                <div style={{
                  padding: '6px 12px', fontWeight: 600, fontSize: 12,
                  color: '#8c8c8c', background: '#fafafa', borderBottom: '1px solid #f0f0f0',
                  position: 'sticky', top: 0,
                }}>
                  {g.label}
                </div>
                {g.vars.map((v) => (
                  <div
                    key={v.ref}
                    onMouseDown={(e) => { e.preventDefault(); insertVar(v.ref) }}
                    style={{
                      padding: '7px 12px', cursor: 'pointer', display: 'flex',
                      justifyContent: 'space-between', alignItems: 'center',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.background = '#f5f5f5' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.background = '' }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{
                        color: '#8c8c8c', fontSize: 11, fontFamily: 'monospace',
                        background: '#f5f5f5', padding: '1px 4px', borderRadius: 3,
                      }}>{'{x}'}</span>
                      <span style={{ fontSize: 13 }}>{v.label}</span>
                    </span>
                    <span style={{ fontSize: 12, color: '#bfbfbf' }}>{v.type}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default PromptEditor
