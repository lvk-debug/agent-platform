import React, { useState, useEffect } from 'react'
import { Modal, Table, Button, Space, Tag, Input, message, Typography } from 'antd'
import { SearchOutlined, ToolOutlined, CheckOutlined } from '@ant-design/icons'
import { toolsApi, ToolData } from '@/services/tools'
import { ToolConfig } from '@/services/agent'

const { Text } = Typography

interface ToolSelectorProps {
  open: boolean
  selected: ToolConfig[]
  onOk: (tools: ToolConfig[]) => void
  onCancel: () => void
}

const ToolSelector: React.FC<ToolSelectorProps> = ({
  open,
  selected,
  onOk,
  onCancel,
}) => {
  const [tools, setTools] = useState<ToolData[]>([])
  const [loading, setLoading] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [localSelected, setLocalSelected] = useState<ToolConfig[]>(selected)

  useEffect(() => {
    if (open) {
      fetchTools()
      setLocalSelected(selected)
    }
  }, [open, selected])

  const fetchTools = async () => {
    setLoading(true)
    try {
      const response = await toolsApi.getTools()
      setTools(response.data)
    } catch (error) {
      message.error('获取工具列表失败')
    } finally {
      setLoading(false)
    }
  }

  const isSelected = (toolId: number) => {
    return localSelected.some(t => t.tool_id === toolId)
  }

  const handleToggle = (tool: ToolData) => {
    if (isSelected(tool.id)) {
      setLocalSelected(localSelected.filter(t => t.tool_id !== tool.id))
    } else {
      setLocalSelected([
        ...localSelected,
        {
          tool_id: tool.id,
          name: tool.name,
          enabled: true,
        }
      ])
    }
  }

  const handleOk = () => {
    onOk(localSelected)
    onCancel()
  }

  const filteredTools = tools.filter(
    tool =>
      tool.name.toLowerCase().includes(searchText.toLowerCase()) ||
      tool.description?.toLowerCase().includes(searchText.toLowerCase())
  )

  const getToolTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      builtin: 'blue',
      plugin: 'green',
      mcp: 'purple',
    }
    return colors[type] || 'default'
  }

  const getToolTypeName = (type: string) => {
    const names: Record<string, string> = {
      builtin: '内置',
      plugin: '插件',
      mcp: 'MCP',
    }
    return names[type] || type
  }

  const columns = [
    {
      title: '工具名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: ToolData) => (
        <Space>
          <ToolOutlined style={{ color: '#1890ff' }} />
          <Text strong>{text}</Text>
          <Tag color={getToolTypeColor(record.tool_type)}>
            {getToolTypeName(record.tool_type)}
          </Tag>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 300,
      render: (text: string) => text || '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: any, record: ToolData) => (
        <Button
          type={isSelected(record.id) ? 'primary' : 'default'}
          icon={isSelected(record.id) ? <CheckOutlined /> : undefined}
          onClick={() => handleToggle(record)}
        >
          {isSelected(record.id) ? '已选择' : '选择'}
        </Button>
      ),
    },
  ]

  return (
    <Modal
      title={
        <Space>
          <ToolOutlined />
          <span>选择工具</span>
          {localSelected.length > 0 && (
            <Tag color="blue">{localSelected.length} 个已选</Tag>
          )}
        </Space>
      }
      open={open}
      onOk={handleOk}
      onCancel={onCancel}
      width={800}
      okText="确定"
      cancelText="取消"
    >
      <div style={{ marginBottom: 16 }}>
        <Input
          placeholder="搜索工具名称或描述"
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
        />
      </div>
      <Table
        columns={columns}
        dataSource={filteredTools}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 8 }}
        size="small"
      />
    </Modal>
  )
}

export default ToolSelector
