/**
 * 工作助理 - 能力设置抽屉
 *
 * 会话栏顶部的「能力设置」入口打开本抽屉，内含：
 * 技能 / 工具 / 模型 / 任务 / 状态 五个分区。
 *
 * 数据只在抽屉打开时拉取，失败时分区内降级提示，不影响其它分区。
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Badge, Button, Drawer, Space, Tabs, App as AntApp } from 'antd'
import {
  ExperimentOutlined,
  ScheduleOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import SkillTab from './SkillTab'
import ToolTab from './ToolTab'
import ModelTab from './ModelTab'
import JobsTab from './JobsTab'
import StatusTab from './StatusTab'
import {
  HermesCapabilities,
  HermesHealthDetail,
  HermesModel,
  HermesSkill,
  HermesTool,
  getCapabilities,
  getHealthDetail,
  getModels,
  getSkills,
  getTools,
} from '@/services/hermes'

export interface CapabilityConfig {
  model: string
  skills: string[]
  tools: string[]
}

export const DEFAULT_CAPABILITY: CapabilityConfig = {
  model: '',
  skills: [],
  tools: [],
}

interface CapabilityDrawerProps {
  open: boolean
  onClose: () => void
  value: CapabilityConfig
  usedTools: string[]
  onSubmit: (config: CapabilityConfig) => Promise<void> | void
}

const CapabilityDrawer: React.FC<CapabilityDrawerProps> = ({
  open,
  onClose,
  value,
  usedTools,
  onSubmit,
}) => {
  const { message } = AntApp.useApp()
  const [draft, setDraft] = useState<CapabilityConfig>(value)
  const [saving, setSaving] = useState(false)

  const [skills, setSkills] = useState<HermesSkill[]>([])
  const [tools, setTools] = useState<HermesTool[]>([])
  const [models, setModels] = useState<HermesModel[]>([])
  const [defaultModel, setDefaultModel] = useState('')
  const [capabilities, setCapabilities] = useState<HermesCapabilities | undefined>()
  const [health, setHealth] = useState<HermesHealthDetail | undefined>()
  const [loading, setLoading] = useState(false)
  const [modelsError, setModelsError] = useState('')
  const [statusError, setStatusError] = useState('')
  const [loaded, setLoaded] = useState(false)

  // 打开时同步外部值并加载数据（仅首次）
  useEffect(() => {
    if (!open) return
    setDraft(value)
    if (loaded) return
    setLoaded(true)
    void loadAll()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, value])

  const loadAll = useCallback(async () => {
    setLoading(true)
    const results = await Promise.allSettled([
      getSkills({ enabled_only: true }),
      getTools(),
      getModels(),
      getCapabilities(),
      getHealthDetail(),
    ])

    const [skillsRes, toolsRes, modelsRes, capRes, healthRes] = results

    if (skillsRes.status === 'fulfilled') setSkills(skillsRes.value)
    if (toolsRes.status === 'fulfilled') setTools(toolsRes.value)
    if (modelsRes.status === 'fulfilled') {
      setModels(modelsRes.value.models || [])
      setDefaultModel(modelsRes.value.model || '')
      setModelsError('')
    } else {
      setModelsError('未能获取模型列表')
    }
    if (capRes.status === 'fulfilled') {
      setCapabilities(capRes.value)
      setStatusError('')
    } else {
      setStatusError('未能获取能力清单')
    }
    if (healthRes.status === 'fulfilled') {
      setHealth(healthRes.value)
    } else {
      setStatusError((prev) => prev || '未能获取详细状态')
    }

    setLoading(false)
  }, [])

  const handleRefreshStatus = useCallback(async () => {
    setLoading(true)
    const [capRes, healthRes] = await Promise.allSettled([
      getCapabilities(true),
      getHealthDetail(true),
    ])
    if (capRes.status === 'fulfilled') {
      setCapabilities(capRes.value)
      setStatusError('')
    } else {
      setStatusError('未能获取能力清单')
    }
    if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
    setLoading(false)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSubmit(draft)
      message.success('能力配置已应用')
      onClose()
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const healthStatus = health?.status
  const connected = healthStatus === 'ok' || healthStatus === 'healthy'

  const tabItems = [
    {
      key: 'skills',
      label: (
        <Space size={4}>
          <ThunderboltOutlined />
          技能
          {draft.skills.length > 0 && <Badge count={draft.skills.length} size="small" />}
        </Space>
      ),
      children: (
        <SkillTab
          skills={skills}
          loading={loading && skills.length === 0}
          selected={draft.skills}
          onChange={(skillsSelected) =>
            setDraft((prev) => ({ ...prev, skills: skillsSelected }))
          }
        />
      ),
    },
    {
      key: 'tools',
      label: (
        <Space size={4}>
          <ToolOutlined />
          工具
          {draft.tools.length > 0 && <Badge count={draft.tools.length} size="small" />}
        </Space>
      ),
      children: (
        <ToolTab
          tools={tools}
          loading={loading && tools.length === 0}
          selected={draft.tools}
          usedTools={usedTools}
          onChange={(toolsSelected) =>
            setDraft((prev) => ({ ...prev, tools: toolsSelected }))
          }
        />
      ),
    },
    {
      key: 'model',
      label: (
        <Space size={4}>
          <ExperimentOutlined />
          模型
        </Space>
      ),
      children: (
        <ModelTab
          models={models}
          defaultModel={defaultModel}
          loading={loading && models.length === 0}
          error={modelsError}
          value={draft.model}
          onChange={(model) => setDraft((prev) => ({ ...prev, model }))}
        />
      ),
    },
    {
      key: 'jobs',
      label: (
        <Space size={4}>
          <ScheduleOutlined />
          任务
        </Space>
      ),
      children: <JobsTab skills={skills} supported />,
    },
    {
      key: 'status',
      label: (
        <Space size={4}>
          <SettingOutlined />
          状态
        </Space>
      ),
      children: (
        <StatusTab
          capabilities={capabilities}
          health={health}
          loading={loading}
          error={statusError}
          onRefresh={handleRefreshStatus}
        />
      ),
    },
  ]

  return (
    <Drawer
      title={
        <Space>
          <span>能力设置</span>
          <Badge
            status={connected ? 'success' : healthStatus ? 'warning' : 'default'}
            text={
              <span className="text-xs text-gray-500">
                {healthStatus ? `${defaultModel || 'hermes-agent'} · ${healthStatus}` : '未连接'}
              </span>
            }
          />
        </Space>
      }
      placement="right"
      width={520}
      open={open}
      onClose={onClose}
      destroyOnClose={false}
      footer={
        <div className="flex justify-between">
          <Button onClick={() => setDraft(DEFAULT_CAPABILITY)}>重置</Button>
          <Space>
            <Button onClick={onClose}>取消</Button>
            <Button type="primary" loading={saving} onClick={handleSave}>
              保存并应用
            </Button>
          </Space>
        </div>
      }
    >
      <Tabs items={tabItems} size="small" />
    </Drawer>
  )
}

export default CapabilityDrawer
