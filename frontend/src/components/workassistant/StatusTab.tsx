/**
 * 能力设置抽屉 - 状态 Tab
 *
 * 展示 Hermes API Server 的连通性、稳定能力清单与只读健康摘要。
 */
import React from 'react'
import { Alert, Badge, Button, Empty, Space, Spin, Tag, Typography } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import { HermesCapabilities, HermesHealthDetail } from '@/services/hermes'

const { Text } = Typography

const FEATURE_LABELS: Record<string, string> = {
  chat_completions: '对话补全',
  responses_api: 'Responses API',
  run_submission: '任务提交',
  run_status: '运行状态',
  run_events_sse: '事件流 (SSE)',
  run_stop: '停止运行',
}

interface StatusTabProps {
  capabilities?: HermesCapabilities
  health?: HermesHealthDetail
  loading: boolean
  error?: string
  onRefresh: () => void
}

const StatusTab: React.FC<StatusTabProps> = ({
  capabilities,
  health,
  loading,
  error,
  onRefresh,
}) => {
  const features = Object.entries(capabilities?.features || {})

  const statusColor = (status?: string) => {
    if (!status) return 'default'
    if (status === 'ok' || status === 'healthy' || status === 'ready') return 'success'
    if (status === 'unreachable' || status === 'error') return 'error'
    return 'warning'
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <Space>
          <Badge status={statusColor(health?.status) as any} />
          <Text className="text-sm">
            {health?.status ? `服务状态：${health.status}` : '未获取到服务状态'}
          </Text>
          {health?.ready !== undefined && (
            <Tag color={health.ready ? 'green' : 'orange'}>
              {health.ready ? '就绪' : '未就绪'}
            </Tag>
          )}
        </Space>
        <Button size="small" icon={<ReloadOutlined />} loading={loading} onClick={onRefresh}>
          刷新
        </Button>
      </div>

      {error && <Alert type="warning" showIcon message={error} className="mb-3" />}

      <div className="mb-2 text-sm text-gray-700">稳定能力</div>
      <Spin spinning={loading}>
        {features.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description={loading ? '检测中…' : '未获取到能力清单'}
          />
        ) : (
          <div className="grid grid-cols-2 gap-2">
            {features.map(([key, value]) => (
              <div
                key={key}
                className="flex items-center justify-between p-2 rounded border border-gray-200 bg-white"
              >
                <span className="text-xs text-gray-700">
                  {FEATURE_LABELS[key] || key}
                </span>
                <Tag color={value ? 'green' : 'default'}>{value ? '支持' : '不支持'}</Tag>
              </div>
            ))}
          </div>
        )}
      </Spin>

      {health?.checks && health.checks.length > 0 && (
        <>
          <div className="mt-4 mb-2 text-sm text-gray-700">就绪检查</div>
          <div className="grid grid-cols-2 gap-2">
            {health.checks.map((check) => (
              <div
                key={check.name}
                className="flex items-center justify-between p-2 rounded border border-gray-200 bg-white"
              >
                <span className="text-xs text-gray-700 truncate">{check.name}</span>
                <Tag color={statusColor(check.status) === 'success' ? 'green' : 'orange'}>
                  {check.status}
                </Tag>
              </div>
            ))}
          </div>
        </>
      )}

      {health?.counts && Object.keys(health.counts).length > 0 && (
        <>
          <div className="mt-4 mb-2 text-sm text-gray-700">运行计数</div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(health.counts).map(([key, value]) => (
              <Tag key={key} color="blue">
                {key}: {value}
              </Tag>
            ))}
          </div>
        </>
      )}

      <div className="mt-4">
        <Text type="secondary" className="text-xs">
          状态信息仅包含聚合状态与计数，不含路径、凭据与原始错误。
        </Text>
      </div>
    </div>
  )
}

export default StatusTab
