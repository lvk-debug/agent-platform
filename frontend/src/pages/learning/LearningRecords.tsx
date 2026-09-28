/**
 * 学习记录 /learning/records
 *
 * 概览统计卡 + 热力图 + 星期时长分布 + 资源进度列表。
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spin, Empty } from 'antd'
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  ArrowLeftOutlined,
  CheckCircleFilled,
  FireFilled,
  MessageFilled,
  ClockCircleFilled,
} from '@ant-design/icons'
import { MessageSquare } from 'lucide-react'
import StudyHeatmap from '../../components/learning/StudyHeatmap'
import learningApi from '../../services/learning'
import type { RecordResourceItem, StatsResponse } from '../../types/learning'
import { formatDuration, formatRelativeTime } from '../../utils/format'

const WEEKDAY_NAMES = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const BAR_COLORS = ['#6366F1', '#8B5CF6', '#A78BFA', '#22D3EE', '#34D399', '#FBBF24', '#FB7185']

interface OverviewCard {
  key: string
  title: string
  value: string
  hint: string
  icon: React.ReactNode
  gradient: string
}

const LearningRecords: React.FC = () => {
  const navigate = useNavigate()
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [records, setRecords] = useState<RecordResourceItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([learningApi.getStats(182), learningApi.listRecords(50)])
      .then(([statsData, recordList]) => {
        setStats(statsData)
        setRecords(recordList)
      })
      .catch((error) => console.error('加载学习记录失败', error))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Spin size="large" />
      </div>
    )
  }

  if (!stats) {
    return (
      <div className="py-20 text-center">
        <Empty description="加载学习记录失败，请稍后重试" />
      </div>
    )
  }

  const { overview } = stats
  const cards: OverviewCard[] = [
    {
      key: 'week',
      title: '本周学习',
      value: formatDuration(overview.week_seconds),
      hint:
        overview.week_delta_percent === 0
          ? '与上周持平'
          : `${overview.week_delta_percent > 0 ? '↑' : '↓'} ${Math.abs(overview.week_delta_percent)}% 环比`,
      icon: <ClockCircleFilled />,
      gradient: 'from-indigo-500 to-violet-500',
    },
    {
      key: 'streak',
      title: '连续学习',
      value: `${overview.streak_days} 天`,
      hint: overview.streak_days > 0 ? '保持住这个节奏' : '今天开始新的连续记录',
      icon: <FireFilled />,
      gradient: 'from-amber-400 to-orange-500',
    },
    {
      key: 'finished',
      title: '完成资源',
      value: `${overview.finished_count} 个`,
      hint: `累计学习 ${formatDuration(overview.total_seconds)}`,
      icon: <CheckCircleFilled />,
      gradient: 'from-emerald-400 to-teal-500',
    },
    {
      key: 'notes',
      title: '笔记总数',
      value: `${overview.note_count} 条`,
      hint: '标注、便签与导出截图',
      icon: <MessageFilled />,
      gradient: 'from-cyan-400 to-sky-500',
    },
  ]

  const weekdayData = (stats.weekday_distribution ?? []).map((item) => ({
    name: WEEKDAY_NAMES[item.weekday] ?? '',
    seconds: item.seconds,
    hours: Number((item.seconds / 3600).toFixed(2)),
  }))

  return (
    <div className="mx-auto w-full max-w-[1400px] px-1 py-2">
      <header className="mb-5 flex items-center gap-3">
        <button
          type="button"
          aria-label="返回"
          onClick={() => navigate('/learning')}
          className="flex h-11 w-11 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-indigo-600"
        >
          <ArrowLeftOutlined />
        </button>
        <div>
          <h1 className="bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_60%,#22D3EE_100%)] bg-clip-text text-2xl font-semibold text-transparent">
            学习记录
          </h1>
          <p className="mt-0.5 text-sm text-slate-500">回看投入的时间、进度与沉淀的笔记</p>
        </div>
      </header>

      {/* 概览卡片 */}
      <section className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.key}
            className="group relative overflow-hidden rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200/70 transition-all duration-200 hover:-translate-y-1 hover:shadow-[0_18px_40px_-16px_rgba(99,102,241,0.45)]"
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-xs text-slate-400">{card.title}</p>
                <p className="mt-1 text-xl font-semibold text-slate-800">{card.value}</p>
                <p className="mt-1 text-xs text-slate-400">{card.hint}</p>
              </div>
              <span
                className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${card.gradient} text-white shadow-md transition-transform duration-200 group-hover:scale-110`}
              >
                {card.icon}
              </span>
            </div>
            <span className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-indigo-50 opacity-60 blur-xl" />
          </div>
        ))}
      </section>

      {/* 热力图 */}
      <section className="mb-5 rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
        <h2 className="mb-4 text-base font-semibold text-slate-800">学习热力图</h2>
        <StudyHeatmap heatmap={stats.heatmap} streakDays={overview.streak_days} />
      </section>

      <div className="mb-5 grid gap-4 lg:grid-cols-2">
        {/* 星期分布 */}
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
          <h2 className="mb-4 text-base font-semibold text-slate-800">每日时长分布</h2>
          {weekdayData.every((item) => item.seconds === 0) ? (
            <p className="py-10 text-center text-sm text-slate-400">暂无数据</p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weekdayData} layout="vertical" margin={{ left: 8, right: 16 }}>
                  <XAxis type="number" tickFormatter={(value) => `${value}h`} fontSize={12} />
                  <YAxis type="category" dataKey="name" width={44} fontSize={12} />
                  <Tooltip
                    formatter={(value: number) => [formatDuration(value * 3600), '学习时长']}
                    cursor={{ fill: 'rgba(99,102,241,0.08)' }}
                  />
                  <Bar dataKey="hours" radius={[0, 6, 6, 0]} animationDuration={700}>
                    {weekdayData.map((item, index) => (
                      <Cell key={item.name} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </section>

        {/* 资源进度 */}
        <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70">
          <h2 className="mb-4 text-base font-semibold text-slate-800">资源进度</h2>
          {records.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">还没有开始学习任何资源</p>
          ) : (
            <ul className="max-h-64 space-y-2 overflow-y-auto pr-1">
              {records.map((record) => (
                <li key={record.resource_id}>
                  <button
                    type="button"
                    onClick={() => navigate(`/learning/${record.resource_id}`)}
                    className="w-full rounded-xl px-2 py-2 text-left transition-colors hover:bg-slate-50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="min-w-0 flex-1 truncate text-sm text-slate-700">
                        {record.title}
                      </span>
                      <span className="shrink-0 text-xs text-slate-400">
                        {formatDuration(record.total_seconds)}
                      </span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-[linear-gradient(90deg,#6366F1_0%,#8B5CF6_60%,#22D3EE_100%)]"
                          style={{ width: `${Math.min(record.percent, 100)}%` }}
                        />
                      </div>
                      <span className="w-10 shrink-0 text-right text-xs text-slate-400">
                        {Math.round(record.percent)}%
                      </span>
                      <span className="w-16 shrink-0 text-right text-xs text-slate-400">
                        {formatRelativeTime(record.last_studied_at)}
                      </span>
                    </div>
                    {record.qa_count > 0 ? (
                      <p className="mt-1.5 flex items-center gap-1.5 text-xs text-slate-400">
                        <MessageSquare size={12} className="shrink-0 text-indigo-400" />
                        <span className="min-w-0 flex-1 truncate">
                          问了 {record.qa_count} 个问题
                          {record.last_question ? ` · ${record.last_question}` : ''}
                        </span>
                      </p>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  )
}

export default LearningRecords
