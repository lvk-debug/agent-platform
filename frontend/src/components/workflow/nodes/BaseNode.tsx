/**
 * 通用节点基础组件 — 所有自定义节点共用的外壳
 * Dify 风格：白色卡片 + 左侧彩色图标 + 右侧带标签的连接点
 */
import React, { memo } from 'react'
import { Handle, Position } from 'reactflow'
import {
  PlayCircleOutlined,
  StopOutlined,
  RobotOutlined,
  BookOutlined,
  BranchesOutlined,
  AuditOutlined,
  CodeOutlined,
  GlobalOutlined,
  ToolOutlined,
  UserOutlined,
} from '@ant-design/icons'

const iconMap: Record<string, React.ReactNode> = {
  start: <PlayCircleOutlined />,
  end: <StopOutlined />,
  llm: <RobotOutlined />,
  knowledge_retrieval: <BookOutlined />,
  condition: <BranchesOutlined />,
  question_classifier: <AuditOutlined />,
  code: <CodeOutlined />,
  http: <GlobalOutlined />,
  tool: <ToolOutlined />,
  human_intervention: <UserOutlined />,
}

const colorMap: Record<string, string> = {
  start: '#52c41a',
  end: '#ff4d4f',
  llm: '#1677ff',
  knowledge_retrieval: '#722ed1',
  condition: '#1677ff',
  question_classifier: '#13c2c2',
  code: '#13c2c2',
  http: '#eb2f96',
  tool: '#595959',
  human_intervention: '#1677ff',
}

interface BaseNodeData {
  label: string
  description?: string
  nodeType: string
  config?: Record<string, any>
}

interface HandleLabel {
  id: string
  label: string
  color?: string
}

interface BaseNodeProps {
  data: BaseNodeData
  selected: boolean
  id: string
  sourceHandles?: HandleLabel[] | string[]
  targetHandles?: string[]
  showSource?: boolean
  showTarget?: boolean
}

// 需要更多高度的节点类型
const TALL_TYPES = new Set(['condition', 'human_intervention', 'question_classifier'])
const TALL_MIN_HEIGHT = 100

const BaseNode: React.FC<BaseNodeProps> = ({
  data,
  selected,
  sourceHandles,
  targetHandles,
  showSource = true,
  showTarget = true,
}) => {
  const color = colorMap[data.nodeType] || '#595959'
  const icon = iconMap[data.nodeType] || <ToolOutlined />
  const needsTall = TALL_TYPES.has(data.nodeType)

  // 标准化 sourceHandles
  const normalizedHandles: HandleLabel[] = (sourceHandles || []).map((h) => {
    if (typeof h === 'string') {
      return { id: h, label: h }
    }
    return h
  })

  return (
    <div
      className={`bg-white rounded-lg border shadow-sm min-w-[160px] max-w-[240px] transition-all ${selected ? 'shadow-md border-blue-400' : 'border-gray-200'
        }`}
      style={needsTall ? { minHeight: TALL_MIN_HEIGHT } : undefined}
    >
      {/* 内容区域 — 图标 + 标签 */}
      <div className="flex items-center gap-2 px-3 py-2.5">
        {/* 左侧彩色图标 */}
        <div
          className="flex items-center justify-center w-7 h-7 rounded-md text-white text-sm flex-shrink-0"
          style={{ backgroundColor: color }}
        >
          {icon}
        </div>
        {/* 节点名称 */}
        <span className="text-sm font-medium text-gray-800 truncate">
          {data.label || data.nodeType}
        </span>
      </div>

      {/* 连接点 — 左侧 target */}
      {showTarget && (
        <>
          {targetHandles && targetHandles.length > 0 ? (
            targetHandles.map((h) => (
              <Handle
                key={`target-${h}`}
                type="target"
                position={Position.Left}
                id={h}
                style={{ background: color, width: 8, height: 8 }}
              />
            ))
          ) : (
            <Handle
              type="target"
              position={Position.Left}
              style={{ background: color, width: 8, height: 8 }}
            />
          )}
        </>
      )}

      {/* 连接点 — 右侧 source（带标签） */}
      {showSource && (
        <>
          {normalizedHandles.length > 0 ? (
            normalizedHandles.map((h, i) => {
              const total = normalizedHandles.length
              const topPercent = total === 1 ? 50 : (i / (total - 1)) * 20 + 50
              const handleColor = h.color || color
              return (
                <div
                  key={`source-${h.id}`}
                  className="absolute flex items-center"
                  style={{
                    right: 0,
                    top: `${topPercent}%`,
                    transform: 'translateY(-50%)',
                  }}
                >
                  {/* 标签（在节点内侧） */}
                  <span
                    className="text-xs font-medium whitespace-nowrap"
                    style={{
                      color: handleColor,
                      marginRight: 8,
                      background: 'rgba(255,255,255,0.9)',
                      padding: '0 4px',
                      borderRadius: 2,
                      position: 'relative',
                      zIndex: 1,
                    }}
                  >
                    {h.label}
                  </span>
                  {/* 连接点 */}
                  <Handle
                    type="source"
                    position={Position.Right}
                    id={h.id}
                    style={{ background: handleColor, width: 8, height: 8 }}
                  />
                </div>
              )
            })
          ) : (
            <Handle
              type="source"
              position={Position.Right}
              style={{ background: color, width: 8, height: 8 }}
            />
          )}
        </>
      )}
    </div>
  )
}

export default memo(BaseNode)
