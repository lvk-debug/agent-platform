import React, { useState, useEffect } from 'react'
import { Card, Button, message, Spin, Row, Col, Space, Breadcrumb, Switch, Input, InputNumber, Collapse, Typography } from 'antd'
import { SaveOutlined, SettingOutlined, CommentOutlined } from '@ant-design/icons'
import { useParams, useNavigate, Link } from 'react-router-dom'
import PromptEditor from '@/components/PromptEditor'
import VariableSettings from '@/components/VariableSettings'
import KnowledgeBaseSelector from '@/components/KnowledgeBaseSelector'
import ModelSelector from '@/components/ModelSelector'
import ModelParametersModal from '@/components/ModelParameters'
import { chatbotApi, ChatbotConfig, ModelParameters as ModelParametersType } from '@/services/chatbot'

const defaultParameters: ModelParametersType = {
  temperature: 0.7,
  top_p: 1,
  top_k: 1,
  presence_penalty: 0,
  frequency_penalty: 0,
  max_tokens: 512,
  skip_content_review: false
}

const DEFAULT_HYDE_PROMPT = `你是一个假设性文档生成器。请根据用户的问题，生成一段假想的文档内容（200-400字），这段内容应该：
1. 假设是知识库中真实存在的一篇文章
2. 直接回答或解释用户的问题
3. 使用陈述语气，不要用疑问句
4. 包含具体的细节和信息

用户问题：{query}

假想文档：`

const DEFAULT_EXPANSION_PROMPT = `你是一个查询扩展助手。请将用户的问题扩展为更适合全文检索的形式。

规则：
1. 保留原始问题的核心语义
2. 补充相关的同义词、近义词、神学术语
3. 输出 1-3 个扩展后的检索查询，每行一个
4. 不要输出解释，只输出查询

用户问题：{query}`

const ChatbotOrchestration: React.FC = () => {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const [config, setConfig] = useState<ChatbotConfig>({
    prompt: {},
    variables: [],
    knowledge_bases: [],
    model_parameters: defaultParameters,
    memory_enabled: false,
    memory_window: 50,
    metadata_filter_enabled: false,
    hyde_enabled: false,
    hyde_prompt: undefined,
    query_expansion_enabled: false,
    query_expansion_prompt: undefined,
    rerank_enabled: false,
    rerank_top_k: 3,
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [paramsOpen, setParamsOpen] = useState(false)

  useEffect(() => {
    fetchConfig()
  }, [appId])

  const fetchConfig = async () => {
    if (!appId) return
    setLoading(true)
    try {
      const data = await chatbotApi.getConfig(Number(appId))
      setConfig({
        ...data,
        model_parameters: data.model_parameters || defaultParameters,
        prompt: data.prompt || { system_prompt: '' }
      })
    } catch (error) {
      console.error('Failed to fetch config:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    if (!appId) return
    setSaving(true)
    try {
      await chatbotApi.updateConfig(Number(appId), config)
      message.success('保存成功')
    } catch (error) {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  const handleParamsOk = (params: ModelParametersType) => {
    setConfig({ ...config, model_parameters: params })
    setParamsOpen(false)
  }

  if (loading) {
    return (
      <div className="text-center py-25">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="h-screen pb-3 flex flex-col">
      <div className="pb-3 border-b border-border">
        <Row justify="space-between" align="middle">
          <Col>
            <Breadcrumb
              items={[
                { title: <Link to="/apps">应用</Link> },
                { title: '聊天助手编排' },
              ]}
            />
          </Col>
          <Col>
            <Space>
              <Button
                icon={<CommentOutlined />}
                onClick={() => navigate(`/apps/${appId}/chatbot/debug`)}
              >
                调试
              </Button>
              <Button
                type="primary"
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
              >
                保存
              </Button>
            </Space>
          </Col>
        </Row>
      </div>

      <div className="flex-1 bg-page">
        <Card
          title="模型配置"
          className="mb-4"
          extra={
            <Button
              type="link"
              icon={<SettingOutlined />}
              onClick={() => setParamsOpen(true)}
              disabled={!config.model_id}
            >
              参数设置
            </Button>
          }
        >
          <div className="mb-2">选择模型</div>
          <ModelSelector
            value={config.model_id}
            onChange={(modelId) => setConfig({ ...config, model_id: modelId })}
          />
        </Card>

        <Card title="提示词设置" className="mb-4">
          <PromptEditor
            systemPrompt={config.prompt?.system_prompt || ''}
            onChange={(systemPrompt) => setConfig({
              ...config,
              prompt: { ...config.prompt, system_prompt: systemPrompt }
            })}
          />
        </Card>

        <Card className="mb-4">
          <VariableSettings
            variables={config.variables}
            onChange={(variables) => setConfig({ ...config, variables })}
          />
        </Card>

        <Card title="知识库设置">
          <KnowledgeBaseSelector
            selected={config.knowledge_bases || []}
            onChange={(knowledge_bases) => setConfig({ ...config, knowledge_bases })}
          />
        </Card>

        <Card title="检索增强" className="mb-4">
          <Collapse
            ghost
            items={[
              {
                key: 'hyde',
                label: (
                  <Space>
                    <Switch
                      size="small"
                      checked={config.hyde_enabled}
                      onChange={(checked) => setConfig({
                        ...config,
                        hyde_enabled: checked,
                        hyde_prompt: config.hyde_prompt || DEFAULT_HYDE_PROMPT,
                      })}
                    />
                    <span>假设性文档嵌入 (HyDE)</span>
                  </Space>
                ),
                children: (
                  <div>
                    <Typography.Text type="secondary" className="block mb-2">
                      让 LLM 先根据问题生成一段假想的回答，再用这段文本去检索，提高语义匹配度
                    </Typography.Text>
                    <Input.TextArea
                      value={config.hyde_prompt || DEFAULT_HYDE_PROMPT}
                      onChange={(e) => setConfig({ ...config, hyde_prompt: e.target.value })}
                      rows={6}
                      placeholder="使用 {query} 作为用户问题占位符"
                      disabled={!config.hyde_enabled}
                    />
                    <Button
                      size="small"
                      className="mt-2"
                      onClick={() => setConfig({ ...config, hyde_prompt: DEFAULT_HYDE_PROMPT })}
                      disabled={!config.hyde_enabled}
                    >
                      恢复默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'expansion',
                label: (
                  <Space>
                    <Switch
                      size="small"
                      checked={config.query_expansion_enabled}
                      onChange={(checked) => setConfig({
                        ...config,
                        query_expansion_enabled: checked,
                        query_expansion_prompt: config.query_expansion_prompt || DEFAULT_EXPANSION_PROMPT,
                      })}
                    />
                    <span>查询扩展 (Query Expansion)</span>
                  </Space>
                ),
                children: (
                  <div>
                    <Typography.Text type="secondary" className="block mb-2">
                      用 LLM 将用户问题扩展为多个相关表述，补充同义词和神学术语，提高召回率
                    </Typography.Text>
                    <Input.TextArea
                      value={config.query_expansion_prompt || DEFAULT_EXPANSION_PROMPT}
                      onChange={(e) => setConfig({ ...config, query_expansion_prompt: e.target.value })}
                      rows={6}
                      placeholder="使用 {query} 作为用户问题占位符"
                      disabled={!config.query_expansion_enabled}
                    />
                    <Button
                      size="small"
                      className="mt-2"
                      onClick={() => setConfig({ ...config, query_expansion_prompt: DEFAULT_EXPANSION_PROMPT })}
                      disabled={!config.query_expansion_enabled}
                    >
                      恢复默认
                    </Button>
                  </div>
                ),
              },
              {
                key: 'rerank',
                label: (
                  <Space>
                    <Switch
                      size="small"
                      checked={config.rerank_enabled}
                      onChange={(checked) => setConfig({
                        ...config,
                        rerank_enabled: checked,
                      })}
                    />
                    <span>重排序 (Rerank)</span>
                  </Space>
                ),
                children: (
                  <div>
                    <Typography.Text type="secondary" className="block mb-2">
                      使用 Cross-Encoder 模型对检索结果进行二次排序，提升检索精度。基于 BAAI/bge-reranker-base 模型。
                    </Typography.Text>
                    <Space align="center">
                      <span>保留 Top-K 结果：</span>
                      <InputNumber
                        min={1}
                        max={20}
                        value={config.rerank_top_k || 3}
                        onChange={(value) => setConfig({ ...config, rerank_top_k: value || 3 })}
                        disabled={!config.rerank_enabled}
                        style={{ width: 80 }}
                      />
                    </Space>
                  </div>
                ),
              },
            ]}
          />
        </Card>
      </div>

      <ModelParametersModal
        open={paramsOpen}
        parameters={config.model_parameters || defaultParameters}
        onOk={handleParamsOk}
        onCancel={() => setParamsOpen(false)}
      />
    </div>
  )
}

export default ChatbotOrchestration
