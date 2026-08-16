import React, { useEffect, useState } from 'react'
import { Select, Space, Typography, Spin } from 'antd'
import { modelsApi, ModelData } from '../services/models'

const { Text } = Typography

interface ModelSelectorProps {
  value?: number
  onChange?: (modelId: number | undefined) => void
}

const ModelSelector: React.FC<ModelSelectorProps> = ({ value, onChange }) => {
  const [models, setModels] = useState<ModelData[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchModels()
  }, [])

  const fetchModels = async () => {
    setLoading(true)
    try {
      const response = await modelsApi.getAllModels()
      setModels(response.data.filter(m => m.is_active))
    } catch (error) {
      console.error('Failed to fetch models:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (val: number | undefined) => {
    onChange?.(val)
  }

  return (
    <Select
      className="w-full"
      placeholder="选择模型"
      value={value}
      onChange={handleChange}
      loading={loading}
      allowClear
      notFoundContent={loading ? <Spin size="small" /> : '暂无可用模型'}
      options={models.map(model => ({
        value: model.id,
        label: (
          <Space>
            <Text>{model.name}</Text>
            <Text type="secondary" className="text-xs">
              ({model.model_id})
            </Text>
          </Space>
        ),
      }))}
    />
  )
}

export default ModelSelector
