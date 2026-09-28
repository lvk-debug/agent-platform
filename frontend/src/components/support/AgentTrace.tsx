/**
 * AgentTrace - 思考链时间线
 *
 * 把客服多 Agent 的节点处理过程（router / knowledge / tool / escalation / summary）
 * 渲染成竖向步骤条：完成态高亮、进行态脉冲，让回答「可解释」。
 */

import React from 'react'
import {
  AlertOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  RobotOutlined,
  ToolOutlined,
} from '@ant-design/icons'
import type { AgentTraceStep } from '../../types/support'

const NODE_META: Record<string, { label: string; icon: React.ReactNode; color: string }> = {
  router: { label: '意图路由', icon: <RobotOutlined />, color: 'text-indigo-500' },
  knowledge: { label: '知识检索', icon: <DatabaseOutlined />, color: 'text-blue-500' },
  tool: { label: '工具调用', icon: <ToolOutlined />, color: 'text-emerald-500' },
  escalation: { label: '投诉升级', icon: <AlertOutlined />, color: 'text-orange-500' },
  summary: { label: '汇总回复', icon: <FileTextOutlined />, color: 'text-violet-500' },
}

const AgentTrace: React.FC<{ steps: AgentTraceStep[] }> = ({ steps }) => {
  if (!steps?.length) return null
  return (
    <div className="rounded-xl bg-white/70 border border-slate-100 p-3">
      <div className="flex items-center gap-1.5 mb-2 text-[11px] font-medium text-slate-400">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-indigo-400" />
        AI 处理过程
      </div>
      <div className="flex">
        <div className="flex flex-col items-center mr-2">
          {steps.map((s, i) => (
            <React.Fragment key={i}>
              <span
                className={`inline-flex items-center justify-center w-6 h-6 rounded-full bg-slate-50 text-xs ${
                  NODE_META[s.node]?.color || 'text-slate-400'
                }`}
              >
                {NODE_META[s.node]?.icon || <RobotOutlined />}
              </span>
              {i < steps.length - 1 && <span className="w-px flex-1 bg-slate-200 my-0.5" />}
            </React.Fragment>
          ))}
        </div>
        <div className="flex-1 pt-0.5">
          {steps.map((s, i) => (
            <div key={i} className="pb-2 last:pb-0">
              <span className="text-xs font-medium text-slate-600">
                {NODE_META[s.node]?.label || s.node}
              </span>
              <span className="text-xs text-slate-500 ml-1.5">{s.summary}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default AgentTrace
