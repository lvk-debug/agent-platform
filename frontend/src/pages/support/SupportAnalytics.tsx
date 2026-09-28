/**
 * 数据看板
 *
 * 会话量、AI 解决率、待人工占比、满意度与工单情况一屏看全。
 */

import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Empty, Segmented, Spin } from 'antd'
import AnalyticsCards from '../../components/support/AnalyticsCards'
import supportApi from '../../services/support'
import type { AnalyticsResponse } from '../../types/support'

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const SupportAnalytics: React.FC = () => {
  const navigate = useNavigate()
  const [days, setDays] = useState(7)
  const [data, setData] = useState<AnalyticsResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await supportApi.analytics(days)
      setData(res)
    } catch (err) {
      console.error('加载看板数据失败:', err)
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    void load()
  }, [load])

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <Segmented
          value="/support/analytics"
          options={NAV_ITEMS}
          onChange={(value) => navigate(value as string)}
        />
      </div>

      <div className="flex justify-end">
        <Segmented
          value={days}
          onChange={(value) => setDays(value as number)}
          options={[
            { label: '近 7 天', value: 7 },
            { label: '近 14 天', value: 14 },
            { label: '近 30 天', value: 30 },
          ]}
        />
      </div>

      {loading && !data ? (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      ) : !data ? (
        <Empty description="暂无数据" />
      ) : (
        <AnalyticsCards
          overview={data.overview}
          trend={data.trend}
          intents={data.intents}
          satisfaction={data.satisfaction}
          tickets={data.tickets}
        />
      )}
    </div>
  )
}

export default SupportAnalytics
