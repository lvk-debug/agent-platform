/**
 * AnalyticsCards - 看板指标与图表
 *
 * 指标卡 + 趋势 + 意图分布 + 工单状态 + 满意度，一屏看完运营全貌。
 */

import React from 'react'
import { Card, Empty } from 'antd'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type {
  AnalyticsOverview,
  IntentStatItem,
  SatisfactionStatItem,
  TicketStatItem,
  TrendPoint,
} from '../../types/support'

const PIE_COLORS = [
  '#6366f1',
  '#8b5cf6',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#ef4444',
  '#3b82f6',
  '#ec4899',
  '#64748b',
]

const STATUS_COLORS: Record<string, string> = {
  pending: '#f59e0b',
  processing: '#3b82f6',
  resolved: '#10b981',
  rejected: '#ef4444',
  closed: '#94a3b8',
}

interface MetricCardProps {
  label: string
  value: string | number
  hint?: string
  tone?: 'indigo' | 'amber' | 'emerald' | 'rose'
}

const TONE_CLASS: Record<string, string> = {
  indigo: 'from-indigo-500 to-violet-500',
  amber: 'from-amber-400 to-orange-500',
  emerald: 'from-emerald-400 to-teal-500',
  rose: 'from-rose-400 to-pink-500',
}

export const MetricCard: React.FC<MetricCardProps> = ({ label, value, hint, tone = 'indigo' }) => (
  <div className="rounded-xl bg-white border border-slate-200 p-4 relative overflow-hidden">
    <div
      className={`absolute -right-6 -top-6 w-20 h-20 rounded-full bg-gradient-to-br ${TONE_CLASS[tone]} opacity-10`}
    />
    <div className="text-xs text-slate-500">{label}</div>
    <div className="mt-1 text-2xl font-semibold text-slate-800">{value}</div>
    {hint && <div className="mt-1 text-[11px] text-slate-400">{hint}</div>}
  </div>
)

interface AnalyticsCardsProps {
  overview: AnalyticsOverview
  trend: TrendPoint[]
  intents: IntentStatItem[]
  satisfaction: SatisfactionStatItem[]
  tickets: TicketStatItem[]
}

const AnalyticsCards: React.FC<AnalyticsCardsProps> = ({
  overview,
  trend,
  intents,
  satisfaction,
  tickets,
}) => {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="会话总量"
          value={overview.session_total}
          hint={`进行中 ${overview.session_open} · 待人工 ${overview.session_pending_human}`}
        />
        <MetricCard
          label="AI 独立解决率"
          value={`${overview.ai_resolve_rate}%`}
          hint="已结束会话中全程未转人工的占比"
          tone="emerald"
        />
        <MetricCard
          label="待人工占比"
          value={`${overview.unresolved_rate}%`}
          hint="AI 没能接住的比例"
          tone="amber"
        />
        <MetricCard
          label="平均满意度"
          value={overview.avg_satisfaction || '—'}
          hint={`工单待处理 ${overview.ticket_pending} · 超时 ${overview.ticket_overdue}`}
          tone="rose"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card title="会话趋势" className="lg:col-span-2" styles={{ body: { paddingTop: 8 } }}>
          {trend.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorSession" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.35} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorMessage" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} tickFormatter={(v: string) => v.slice(5)} />
                <YAxis tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="session_count" name="新增会话" stroke="#6366f1" fill="url(#colorSession)" />
                <Area type="monotone" dataKey="message_count" name="消息量" stroke="#06b6d4" fill="url(#colorMessage)" />
                <Area type="monotone" dataKey="ticket_count" name="新建工单" stroke="#f59e0b" fillOpacity={0} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="咨询意图分布">
          {intents.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无意图数据" />
          ) : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={intents}
                  dataKey="count"
                  nameKey="label"
                  innerRadius={50}
                  outerRadius={85}
                  paddingAngle={2}
                >
                  {intents.map((_, index) => (
                    <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(value: number, name: string) => [`${value} 次`, name]} />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="工单状态">
          {tickets.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={tickets} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" name="工单数" radius={[4, 4, 0, 0]}>
                  {tickets.map((item, index) => (
                    <Cell key={index} fill={STATUS_COLORS[item.status] || '#6366f1'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        <Card title="满意度分布">
          {satisfaction.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无评价" />
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={satisfaction} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="score" tick={{ fontSize: 12 }} tickFormatter={(v: number) => `${v} 星`} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" name="评价数" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>
    </div>
  )
}

export default AnalyticsCards
