/**
 * ToolCallCard - 工具调用卡片
 *
 * 展示 Tool Agent 调用的四个业务工具（订单 / 物流 / 退换货政策 / 商品）的
 * 入参与返回结果，成功绿边、失败红边，默认折叠详情避免信息过载。
 */

import React, { useState } from 'react'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import type { AgentToolCall } from '../../types/support'

const TOOL_LABELS: Record<string, string> = {
  query_order: '查询订单',
  track_shipment: '查询物流',
  check_return_policy: '退换货政策',
  get_product_info: '查询商品',
}

const ToolCallCard: React.FC<{ call: AgentToolCall }> = ({ call }) => {
  const [open, setOpen] = useState(false)
  const ok = call.success
  return (
    <div
      className={`rounded-xl border p-2.5 ${
        ok ? 'bg-emerald-50/60 border-emerald-100' : 'bg-red-50/60 border-red-100'
      }`}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 text-left"
      >
        {ok ? (
          <CheckCircleOutlined className="text-emerald-500" />
        ) : (
          <CloseCircleOutlined className="text-red-500" />
        )}
        <span className="text-xs font-medium text-slate-700">
          {TOOL_LABELS[call.name] || call.name}
        </span>
        <span className="text-[10px] text-slate-400 ml-auto">{open ? '收起' : '详情'}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1 text-[11px] leading-relaxed">
          <div className="flex gap-1">
            <span className="text-slate-400 flex-shrink-0">参数</span>
            <code className="text-slate-600 break-all">{JSON.stringify(call.arguments)}</code>
          </div>
          <div className="flex gap-1">
            <span className="text-slate-400 flex-shrink-0">结果</span>
            <span className="text-slate-600 whitespace-pre-wrap">{call.result}</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default ToolCallCard
