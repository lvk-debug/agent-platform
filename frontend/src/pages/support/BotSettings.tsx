/**
 * 机器人配置
 *
 * 系统提示词、回复模型、绑定的知识库与检索参数、转人工触发规则。
 * 知识库复用平台既有「知识库」模块，这里只做绑定，不另建 FAQ。
 */

import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Segmented,
  Select,
  Slider,
  Space,
  Spin,
  Switch,
  Tag,
  message as antdMessage,
} from 'antd'
import supportApi from '../../services/support'
import { modelsApi, type ModelData } from '../../services/models'
import { knowledgeApi, type KnowledgeBaseData } from '../../services/knowledge'
import type { OptionItem, SupportSettings } from '../../types/support'
import BusinessDataPanel from '../../components/support/BusinessDataPanel'

const NAV_ITEMS = [
  { label: '工作台', value: '/support' },
  { label: '工单中心', value: '/support/tickets' },
  { label: '数据看板', value: '/support/analytics' },
  { label: '机器人配置', value: '/support/settings' },
  { label: '客户管理', value: '/support/customers' },
]

const SEARCH_MODES = [
  { label: '混合检索（推荐）', value: 'rrf' },
  { label: '向量检索', value: 'vector' },
  { label: '关键词检索', value: 'bm25' },
]

const BotSettings: React.FC = () => {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [settings, setSettings] = useState<SupportSettings | null>(null)
  const [models, setModels] = useState<{ id: number; name: string; provider: string }[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseData[]>([])
  const [intentOptions, setIntentOptions] = useState<OptionItem[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [settingsRes, kbRes, optionsRes] = await Promise.all([
        supportApi.getSettings(),
        knowledgeApi.getKnowledgeBases({ limit: 100 }),
        supportApi.options(),
      ])
      setSettings(settingsRes)
      // 平台 service 直接返回 AxiosResponse，实际数据在 .data 上
      setKnowledgeBases(kbRes?.data?.items || [])
      setIntentOptions(optionsRes.intents || [])

      // 模型按供应商分组：先取供应商，再逐个取名下模型
      try {
        const providerRes = await modelsApi.getProviders()
        const providers = (providerRes?.data || []) as { id: number; name: string }[]
        const nested = await Promise.all(
          providers.map(async (provider) => {
            const res = await modelsApi.getModels(provider.id).catch(() => null)
            const list: ModelData[] = res?.data || []
            return list.map((item) => ({
              id: item.id,
              name: `${item.name}（${item.model_id}）`,
              provider: provider.name,
            }))
          })
        )
        setModels(nested.flat())
      } catch (err) {
        console.error('加载模型列表失败:', err)
      }

      form.setFieldsValue({
        bot_name: settingsRes.bot_name,
        system_prompt: settingsRes.system_prompt || '',
        model_id: settingsRes.model_id ?? undefined,
        knowledge_base_ids: settingsRes.knowledge_base_ids || [],
        search_mode: settingsRes.search_mode,
        top_k: settingsRes.top_k,
        score_threshold: settingsRes.score_threshold,
        enable_rerank: settingsRes.enable_rerank,
        temperature: settingsRes.temperature,
        max_tokens: settingsRes.max_tokens,
        history_turns: settingsRes.history_turns,
        human_intents: settingsRes.human_intents || [],
        human_keywords: settingsRes.human_keywords || [],
        low_confidence_threshold: settingsRes.low_confidence_threshold,
        low_confidence_streak: settingsRes.low_confidence_streak,
        fallback_answer: settingsRes.fallback_answer || '',
      })
    } catch (err) {
      console.error('加载机器人配置失败:', err)
      antdMessage.error('配置加载失败')
    } finally {
      setLoading(false)
    }
  }, [form])

  useEffect(() => {
    void load()
  }, [load])

  const modelOptions = useMemo(() => {
    const groups = new Map<string, { label: string; value: number }[]>()
    for (const item of models) {
      const list = groups.get(item.provider) || []
      list.push({ label: item.name, value: item.id })
      groups.set(item.provider, list)
    }
    return Array.from(groups.entries()).map(([provider, children]) => ({
      label: provider,
      options: children,
    }))
  }, [models])

  const handleSave = useCallback(async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const updated = await supportApi.updateSettings(values)
      setSettings(updated)
      antdMessage.success('配置已保存')
    } catch (err) {
      console.error('保存配置失败:', err)
      antdMessage.error('保存失败，请重试')
    } finally {
      setSaving(false)
    }
  }, [form])

  return (
    <div className="space-y-4">
      <div className="flex justify-center">
        <Segmented
          value="/support/settings"
          options={NAV_ITEMS}
          onChange={(value) => navigate(value as string)}
        />
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Spin size="large" />
        </div>
      ) : (
        <Form form={form} layout="vertical">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="基础配置">
              <Form.Item name="bot_name" label="助手名称" rules={[{ required: true, message: '请输入名称' }]}>
                <Input maxLength={50} />
              </Form.Item>

              <Form.Item
                name="system_prompt"
                label="系统提示词"
                extra="可用 {bot_name} 占位符，保存后自动替换为助手名称"
              >
                <Input.TextArea rows={8} />
              </Form.Item>

              <Form.Item name="model_id" label="回复模型" extra="留空则自动选择第一个可用模型">
                <Select
                  allowClear
                  placeholder="选择模型"
                  options={modelOptions}
                  notFoundContent="请先在「模型管理」配置供应商与模型"
                />
              </Form.Item>

              <Form.Item
                name="knowledge_base_ids"
                label="绑定知识库"
                extra="在「知识库」模块维护课程 FAQ 与售后话术，这里只做绑定"
              >
                <Select
                  mode="multiple"
                  allowClear
                  placeholder="选择知识库"
                  options={knowledgeBases.map((item) => ({
                    label: item.name,
                    value: item.id,
                  }))}
                />
              </Form.Item>
            </Card>

            <Card title="检索与生成">
              <Form.Item name="search_mode" label="检索模式">
                <Select options={SEARCH_MODES} />
              </Form.Item>

              <div className="grid grid-cols-2 gap-3">
                <Form.Item name="top_k" label="每段引用条数">
                  <InputNumber min={1} max={20} className="w-full" />
                </Form.Item>
                <Form.Item name="score_threshold" label="分数阈值">
                  <InputNumber min={0} max={1} step={0.05} className="w-full" />
                </Form.Item>
              </div>

              <Form.Item name="enable_rerank" label="启用重排序" valuePropName="checked">
                <Switch />
              </Form.Item>

              <Form.Item name="temperature" label="生成温度">
                <Slider min={0} max={1} step={0.1} marks={{ 0: '严谨', 1: '灵活' }} />
              </Form.Item>

              <div className="grid grid-cols-2 gap-3">
                <Form.Item name="max_tokens" label="最大输出长度">
                  <InputNumber min={128} max={8000} step={128} className="w-full" />
                </Form.Item>
                <Form.Item name="history_turns" label="携带历史轮数">
                  <InputNumber min={0} max={20} className="w-full" />
                </Form.Item>
              </div>
            </Card>

            <Card title="转人工规则">
              <Form.Item
                name="human_intents"
                label="命中这些意图直接转人工"
                extra="涉及钱或情绪，AI 自行承诺风险高"
              >
                <Select
                  mode="multiple"
                  allowClear
                  placeholder="选择意图"
                  options={intentOptions}
                />
              </Form.Item>

              <Form.Item
                name="human_keywords"
                label="触发关键词"
                extra="回车可自定义；客户消息包含任一词即转人工"
              >
                <Select mode="tags" placeholder="如：转人工、投诉" tokenSeparators={[',', '，']} />
              </Form.Item>

              <div className="grid grid-cols-2 gap-3">
                <Form.Item name="low_confidence_threshold" label="有把握的分数下限">
                  <InputNumber min={0} max={1} step={0.05} className="w-full" />
                </Form.Item>
                <Form.Item name="low_confidence_streak" label="连续没把握几次转人工">
                  <InputNumber min={1} max={10} className="w-full" />
                </Form.Item>
              </div>

              <Form.Item name="fallback_answer" label="兜底话术">
                <Input.TextArea rows={3} maxLength={500} />
              </Form.Item>
            </Card>

            <Card title="当前状态">
              <Space direction="vertical" className="w-full">
                <div>
                  <div className="text-xs text-slate-500 mb-1">已绑定知识库</div>
                  {settings?.knowledge_bases?.length ? (
                    <div className="flex flex-wrap gap-1">
                      {settings.knowledge_bases.map((item) => (
                        <Tag key={item.id} color="indigo">
                          {item.name}
                        </Tag>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">未绑定（AI 将仅凭提示词作答）</span>
                  )}
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-1">当前模型</div>
                  <span className="text-sm text-slate-700">
                    {settings?.model_name || '自动选择可用模型'}
                  </span>
                </div>
                <div>
                  <div className="text-xs text-slate-500 mb-1">最近更新</div>
                  <span className="text-xs text-slate-400">
                    {settings?.updated_at
                      ? new Date(settings.updated_at).toLocaleString('zh-CN')
                      : '—'}
                  </span>
                </div>
              </Space>
            </Card>

            <div className="lg:col-span-2">
              <BusinessDataPanel />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Space>
              <Button onClick={() => void load()}>重置</Button>
              <Button type="primary" loading={saving} onClick={handleSave}>
                保存配置
              </Button>
            </Space>
          </div>
        </Form>
      )}
    </div>
  )
}

export default BotSettings
