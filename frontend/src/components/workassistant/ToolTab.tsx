/**
 * 能力设置抽屉 - 工具 Tab
 *
 * 展示 Hermes 内置工具集与本次会话命中情况。
 * 说明：Hermes 服务端工具是全量启用的，此处勾选仅作为本轮偏好注入，
 * 不构成硬性白名单。
 */
import React from 'react'
import { Alert, Empty, Spin, Switch, Tag } from 'antd'
import { ToolOutlined } from '@ant-design/icons'
import { HermesTool } from '@/services/hermes'

interface ToolTabProps {
  tools: HermesTool[]
  loading: boolean
  selected: string[]
  usedTools: string[]
  onChange: (tools: string[]) => void
}

const ToolTab: React.FC<ToolTabProps> = ({
  tools,
  loading,
  selected,
  usedTools,
  onChange,
}) => {
  const toggle = (name: string) => {
    onChange(
      selected.includes(name) ? selected.filter((t) => t !== name) : [...selected, name]
    )
  }

  return (
    <div>
      <Alert
        type="info"
        showIcon
        className="mb-3"
        message="工具偏好"
        description="Hermes 服务端默认启用全部工具，这里的勾选会作为本轮偏好写入系统指令，用于引导工具选择，不会限制其它工具的使用。"
      />

      <div className="mb-3 flex items-center gap-2 text-xs text-gray-500">
        <ToolOutlined />
        <span>已选 {selected.length} 个工具偏好</span>
      </div>

      <Spin spinning={loading}>
        {tools.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={loading ? '加载中…' : '未配置内置工具清单'}
          />
        ) : (
          <div className="space-y-2">
            {tools.map((tool) => (
              <div
                key={tool.name}
                className="flex items-center justify-between p-3 rounded-lg border border-gray-200 bg-white hover:border-blue-300 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm text-gray-800">{tool.label}</span>
                    <Tag color="blue">{tool.name}</Tag>
                    {usedTools.includes(tool.name) && (
                      <Tag color="green">本会话已使用</Tag>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {tool.description || '暂无说明'}
                  </div>
                </div>
                <Switch
                  size="small"
                  checked={selected.includes(tool.name)}
                  onChange={() => toggle(tool.name)}
                />
              </div>
            ))}
          </div>
        )}
      </Spin>
    </div>
  )
}

export default ToolTab
