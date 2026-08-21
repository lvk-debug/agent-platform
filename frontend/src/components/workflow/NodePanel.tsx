/**
 * 节点面板 — 左侧可拖拽的节点类型列表
 */
import React from 'react'
import { Card, Typography } from 'antd'
import {
  PlayCircleOutlined,
  StopOutlined,
  RobotOutlined,
  BookOutlined,
  BranchesOutlined,
  CodeOutlined,
  GlobalOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import { NODE_TYPES, NodeType } from '../../services/workflow'

const { Text } = Typography

const iconMap: Record<string, React.ReactNode> = {
  PlayCircleOutlined: <PlayCircleOutlined />,
  StopOutlined: <StopOutlined />,
  RobotOutlined: <RobotOutlined />,
  BookOutlined: <BookOutlined />,
  BranchesOutlined: <BranchesOutlined />,
  CodeOutlined: <CodeOutlined />,
  GlobalOutlined: <GlobalOutlined />,
  ToolOutlined: <ToolOutlined />,
}

const NodePanel: React.FC = () => {
  const onDragStart = (event: React.DragEvent, nodeType: NodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div className="w-52 border-r border-border bg-white h-full overflow-y-auto p-3">
      <Text strong className="block mb-3 text-sm">
        节点
      </Text>
      <div className="flex flex-col gap-2">
        {NODE_TYPES.map((meta) => (
          <div
            key={meta.type}
            className="flex items-center gap-2 px-3 py-2 rounded-md border border-border cursor-grab bg-white hover:border-primary hover:text-primary transition-colors select-none"
            draggable
            onDragStart={(e) => onDragStart(e, meta.type)}
            title={meta.description}
          >
            <span
              className="text-base"
              style={{ color: meta.color }}
            >
              {iconMap[meta.icon]}
            </span>
            <Text className="text-sm">{meta.label}</Text>
          </div>
        ))}
      </div>
    </div>
  )
}

export default NodePanel
