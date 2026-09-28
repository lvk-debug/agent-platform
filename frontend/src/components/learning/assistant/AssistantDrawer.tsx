/**
 * AI 学习助手抽屉
 *
 * 文档与视频共用：上下文由后端按 resource_id + 当前位置自动组装，
 * 这里只负责交互与展示。平板竖屏时抽屉近全屏，输入区放大便于手指输入。
 */

import React, { useCallback, useEffect, useState } from 'react'
import { Drawer, Popconfirm, Select } from 'antd'
import { Bot, Send, Square, Trash2, X } from 'lucide-react'
import type {
  ContextRef,
  LearningResource,
  TranscriptCue,
} from '../../../types/learning'
import type { ModelData } from '../../../services/models'
import { modelsApi } from '../../../services/models'
import learningApi from '../../../services/learning'
import useBreakpoint from '../../../hooks/useBreakpoint'
import useLearningChat from '../../../hooks/useLearningChat'
import AssistantMessageList from './AssistantMessageList'
import SuggestedQuestions from './SuggestedQuestions'
import ContextBar, { refKey } from './ContextBar'
import ContextPicker from './ContextPicker'

interface AssistantDrawerProps {
  open: boolean
  resource: LearningResource
  /** 当前位置：文档为页码，视频为秒 */
  position: number
  /** 视频模式的字幕列表，供 @ 选择器复用（避免重复请求） */
  cues?: TranscriptCue[]
  onClose: () => void
}

/** 助手默认使用的模型（按 name / model_id 模糊匹配，找不到则交给后端挑第一个可用的） */
const DEFAULT_MODEL_KEYWORD = 'mimo-v2.5'

/** 打开助手时默认的上下文：就是用户此刻正在看的位置 */
const buildDefaultRef = (resource: LearningResource, position: number): ContextRef => {
  if (resource.type === 'document') {
    return {
      type: 'page',
      page_index: Math.max(Math.floor(position), 0),
      start_ms: null,
      end_ms: null,
    }
  }
  const startMs = Math.max(Math.floor(position * 1000), 0)
  return {
    type: 'transcript',
    page_index: null,
    start_ms: startMs,
    end_ms: startMs + 30_000,
  }
}

const AssistantDrawer: React.FC<AssistantDrawerProps> = ({
  open,
  resource,
  position,
  cues = [],
  onClose,
}) => {
  const { stackVertically } = useBreakpoint()
  const {
    messages,
    loading,
    loadingHistory,
    draftContent,
    loadHistory,
    send,
    cancel,
    clear,
  } = useLearningChat(resource.id)

  const [models, setModels] = useState<ModelData[]>([])
  const [modelId, setModelId] = useState<number | null>(null)
  const [questions, setQuestions] = useState<string[]>([])
  const [loadingSuggest, setLoadingSuggest] = useState(false)
  const [input, setInput] = useState('')
  /** 本次问答携带的上下文：打开时默认当前位置，可增删 */
  const [refs, setRefs] = useState<ContextRef[]>([])
  const [pickerOpen, setPickerOpen] = useState(false)

  // 打开时才拉数据：助手是按需使用的，没必要在页面加载时就打这些请求
  useEffect(() => {
    if (!open) return
    void loadHistory()
  }, [open, loadHistory])

  // 打开时把「当前位置」作为默认上下文。
  // position 故意不进依赖：播放/翻页时不该把用户调整过的上下文重置掉。
  useEffect(() => {
    if (!open) return
    setRefs([buildDefaultRef(resource, position)])
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resource.id])

  useEffect(() => {
    if (!open || models.length) return
    // 注意：modelsApi 各方法直接返回 axios Promise，数据在 res.data 上
    modelsApi
      .getAllModels()
      .then((res) => {
        const list = (res.data || []).filter((item) => item.is_active)
        setModels(list)
        const preferred = list.find(
          (item) =>
            item.name.toLowerCase().includes(DEFAULT_MODEL_KEYWORD) ||
            item.model_id.toLowerCase().includes(DEFAULT_MODEL_KEYWORD)
        )
        // 用 updater 形式：只填空，不覆盖用户已经手动切换过的选择
        if (preferred) setModelId((current) => current ?? preferred.id)
      })
      .catch((err) => console.error('加载模型列表失败:', err))
  }, [open, models.length])

  useEffect(() => {
    if (!open) return
    setLoadingSuggest(true)
    learningApi
      .getSuggestedQuestions(resource.id)
      .then((res) => setQuestions(res.questions || []))
      .catch((err) => console.error('加载推荐问题失败:', err))
      .finally(() => setLoadingSuggest(false))
  }, [open, resource.id])

  const submit = useCallback(
    (question: string) => {
      if (!question.trim() || loading) return
      send(question, position, modelId, refs)
      setInput('')
    },
    [loading, send, position, modelId, refs]
  )

  const addRef = useCallback((ref: ContextRef) => {
    setRefs((prev) => [...prev, ref])
  }, [])

  const removeRef = useCallback((ref: ContextRef) => {
    setRefs((prev) => prev.filter((item) => refKey(item) !== refKey(ref)))
  }, [])

  return (
    <Drawer
      open={open}
      onClose={onClose}
      placement="right"
      width={stackVertically ? '92vw' : 420}
      closable={false}
      // 不加遮罩：助手是「陪读」而不是模态弹窗，
      // 打开时仍要能翻页、选词、看字幕，否则等于把学习区锁死
      mask={false}
      styles={{ body: { padding: 0, display: 'flex', flexDirection: 'column' } }}
    >
      {/* 顶部标题栏 */}
      <div className="flex shrink-0 items-center gap-2 border-b border-slate-100 px-4 py-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white">
          <Bot size={16} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-slate-800">AI 学习助手</div>
          <div className="truncate text-xs text-slate-400">{resource.title}</div>
        </div>

        <Select
          size="small"
          value={modelId ?? undefined}
          placeholder="默认模型"
          allowClear
          onChange={(value) => setModelId(value ?? null)}
          options={models.map((item) => ({ value: item.id, label: item.name }))}
          className="w-28"
        />

        <Popconfirm
          title="清空问答历史？"
          description="该资源的问答记录会被删除，且无法恢复。"
          okText="清空"
          cancelText="取消"
          onConfirm={() => {
            void clear()
          }}
        >
          <button
            type="button"
            aria-label="清空问答历史"
            className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-rose-500"
          >
            <Trash2 size={16} />
          </button>
        </Popconfirm>

        <button
          type="button"
          aria-label="关闭助手"
          onClick={onClose}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
        >
          <X size={18} />
        </button>
      </div>

      {/* 消息区 */}
      <AssistantMessageList
        messages={messages}
        draftContent={draftContent}
        loading={loading}
        loadingHistory={loadingHistory}
        emptyExtra={
          <SuggestedQuestions
            questions={questions}
            loading={loadingSuggest}
            disabled={loading}
            onPick={submit}
          />
        }
      />

      {/* 输入区 */}
      <div className="shrink-0 border-t border-slate-100 p-3">
        <div className="mb-2">
          <ContextBar
            resource={resource}
            refs={refs}
            onRemove={removeRef}
            onAdd={() => setPickerOpen(true)}
          />
        </div>
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              // Enter 发送、Shift+Enter 换行，符合聊天输入习惯
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                submit(input)
              }
            }}
            rows={2}
            placeholder="就这份资料提问，Enter 发送 / Shift+Enter 换行"
            className="min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 outline-none transition-colors focus:border-indigo-400"
          />
          <button
            type="button"
            aria-label={loading ? '停止生成' : '发送'}
            onClick={() => (loading ? cancel() : submit(input))}
            disabled={!loading && !input.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[linear-gradient(135deg,#6366F1_0%,#8B5CF6_100%)] text-white transition-transform active:scale-95 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? <Square size={16} /> : <Send size={16} />}
          </button>
        </div>
      </div>

      <ContextPicker
        open={pickerOpen}
        resource={resource}
        cues={cues}
        selected={refs}
        onClose={() => setPickerOpen(false)}
        onConfirm={addRef}
      />
    </Drawer>
  )
}

export default AssistantDrawer
