/**
 * SupportQuality - 客服质量看板
 *
 * 自动分 + 人工分结合的质量总览：概览指标卡、按日趋势、按意图分布、待标注队列。
 * 待标注队列的「去打分」直接打开人工打分弹窗。
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Segmented,
  Select,
  Table,
  Tag,
  message as antdMessage,
} from 'antd'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RTooltip,
  ResponsiveContainer,
} from 'recharts'
import supportApi from '../../services/support'
import ManualScoreModal from '../../components/support/ManualScoreModal'
import type {
  EvalQueueItem,
  QualitySummaryResponse,
  SupportMessage,
} from '../../types/support'

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '质量看板', value: '/support/quality' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const pct = (v?: number | null) => (v == null ? '—' : `${(v * 100).toFixed(0)}%`)

const SupportQuality: React.FC = () => {
  const navigate = useNavigate()
  const [days, setDays] = useState(7)
  const [summary, setSummary] = useState<QualitySummaryResponse | null>(null)
  const [queue, setQueue] = useState<EvalQueueItem[]>([])
  const [queueTotal, setQueueTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  const [scoreOpen, setScoreOpen] = useState(false)
  const [scoreMsg, setScoreMsg] = useState<SupportMessage | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [s, q] = await Promise.all([
        supportApi.qualitySummary(days),
        supportApi.evaluationQueue({ page: 1, page_size: 200 }),
      ])
      setSummary(s)
      setQueue(q.items)
      setQueueTotal(q.meta.total)
    } catch (err) {
      console.error('加载质量看板失败:', err)
      antdMessage.error('加载质量看板失败')
    } finally {
      setLoading(false)
    }
  }, [days])

  useEffect(() => {
    void load()
  }, [load])

  const openScore = (item: EvalQueueItem) => {
    setScoreMsg({
      id: item.message_id,
      session_id: item.session_id,
      role: 'ai',
      content: item.query || '',
      references: [],
      created_at: item.created_at,
    })
    setScoreOpen(true)
  }

  const metrics = useMemo(() => {
    const o = summary?.overview
    return [
      { label: '自动均分', value: pct(o?.auto_avg), color: '#6366F1' },
      { label: '人工均分', value: pct(o?.manual_avg), color: '#8B5CF6' },
      { label: '已标注率', value: o ? `${(o.annotated_rate * 100).toFixed(0)}%` : '—', color: '#10B981' },
      { label: '待标注数', value: `${o?.pending_count ?? 0}`, color: '#F59E0B' },
    ]
  }, [summary])

  const trendData = useMemo(
    () =>
      (summary?.trend || []).map((t) => ({
        date: t.date.slice(5),
        auto: t.auto_avg != null ? Math.round(t.auto_avg * 100) : null,
        manual: t.manual_avg != null ? Math.round(t.manual_avg * 100) : null,
        count: t.count,
      })),
    [summary],
  )

  const intentData = useMemo(
    () =>
      (summary?.by_intent || []).map((i) => ({
        intent: i.label,
        auto: i.auto_avg != null ? Math.round(i.auto_avg * 100) : 0,
        manual: i.manual_avg != null ? Math.round(i.manual_avg * 100) : 0,
        count: i.count,
      })),
    [summary],
  )

  const columns = [
    { title: '会话', dataIndex: 'session_id', width: 80, render: (v: number) => `#${v}` },
    { title: '客户问题', dataIndex: 'query', ellipsis: true, render: (v?: string) => v || '—' },
    {
      title: '意图',
      dataIndex: 'intent_label',
      width: 110,
      render: (v: string) => <Tag color="indigo">{v || '其他'}</Tag>,
    },
    {
      title: '自动分',
      dataIndex: 'auto_overall',
      width: 90,
      render: (v: number) => pct(v),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => (
        <Tag color={v === 'done' ? 'green' : v === 'auto' ? 'blue' : 'default'}>
          {v === 'done' ? '已标注' : v === 'auto' ? '已自动评' : '待评'}
        </Tag>
      ),
    },
    {
      title: '操作',
      width: 90,
      render: (_: unknown, row: EvalQueueItem) => (
        <a onClick={() => openScore(row)}>去打分</a>
      ),
    },
  ]

  return (
    <div className="h-full flex flex-col gap-3 py-3">
      <div className="flex justify-center">
        <Segmented value="/support/quality" options={NAV_ITEMS} onChange={(v) => navigate(v as string)} />
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto px-1">
        {/* 指标卡 */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {metrics.map((m) => (
            <Card key={m.label} size="small" className="rounded-xl border-slate-200">
              <div className="text-xs text-slate-400">{m.label}</div>
              <div className="text-3xl font-semibold mt-1" style={{ color: m.color }}>
                {m.value}
              </div>
            </Card>
          ))}
        </div>

        {/* 趋势 + 意图分布 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mt-3">
          <Card
            size="small"
            title="质量趋势（按日，百分比）"
            extra={
              <Select
                size="small"
                value={days}
                style={{ width: 96 }}
                onChange={setDays}
                options={[
                  { value: 7, label: '近 7 天' },
                  { value: 14, label: '近 14 天' },
                  { value: 30, label: '近 30 天' },
                ]}
              />
            }
            className="rounded-xl border-slate-200"
          >
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEF2FF" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} />
                  <RTooltip />
                  <Line type="monotone" dataKey="auto" name="自动分" stroke="#6366F1" strokeWidth={2} connectNulls />
                  <Line type="monotone" dataKey="manual" name="人工分" stroke="#8B5CF6" strokeWidth={2} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card size="small" title="按意图分布（自动分，百分比）" className="rounded-xl border-slate-200">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={intentData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#EEF2FF" />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="intent" width={80} tick={{ fontSize: 11 }} />
                  <RTooltip />
                  <Bar dataKey="auto" name="自动分" fill="#6366F1" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="manual" name="人工分" fill="#8B5CF6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        {/* 待标注队列 */}
        <Card
          size="small"
          title={`待标注队列（${queueTotal}）`}
          className="rounded-xl border-slate-200 mt-3"
          loading={loading}
        >
          <Table
            rowKey="message_id"
            size="small"
            columns={columns}
            dataSource={queue}
            pagination={false}
          />
        </Card>
      </div>

      <ManualScoreModal
        open={scoreOpen}
        message={scoreMsg}
        onCancel={() => setScoreOpen(false)}
        onSubmitted={() => {
          setScoreOpen(false)
          void load()
        }}
      />
    </div>
  )
}

export default SupportQuality
