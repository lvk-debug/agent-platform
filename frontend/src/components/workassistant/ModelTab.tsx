/**
 * 能力设置抽屉 - 模型 Tab
 *
 * 从 Hermes /v1/models 拉取可用模型，选择后作为会话级默认模型。
 */
import React from 'react'
import { Alert, Empty, Select, Spin } from 'antd'
import { HermesModel } from '@/services/hermes'

interface ModelTabProps {
  models: HermesModel[]
  defaultModel: string
  loading: boolean
  error?: string
  value: string
  onChange: (model: string) => void
}

const ModelTab: React.FC<ModelTabProps> = ({
  models,
  defaultModel,
  loading,
  error,
  value,
  onChange,
}) => {
  const options = models.map((m) => ({
    value: m.id,
    label: m.name === m.id ? m.id : `${m.name}（${m.id}）`,
  }))
  if (value && !models.some((m) => m.id === value)) {
    options.unshift({ value, label: value })
  }

  return (
    <div>
      <div className="mb-3">
        <div className="text-sm text-gray-700 mb-2">当前会话模型</div>
        <Select
          className="w-full"
          placeholder={defaultModel || '使用 Hermes 默认模型'}
          loading={loading}
          value={value || undefined}
          allowClear
          onChange={(val) => onChange(val || '')}
          options={options}
          notFoundContent={loading ? <Spin size="small" /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未获取到模型" />}
        />
      </div>

      <Alert
        type="info"
        showIcon
        message="模型说明"
        description={
          error
            ? `未能获取模型列表：${error}`
            : `Hermes 广播的默认模型为 ${defaultModel || 'hermes-agent'}；留空则沿用服务端配置。请求中的模型字段仅用于路由展示，真实模型由 Hermes 服务端决定。`
        }
      />
    </div>
  )
}

export default ModelTab
