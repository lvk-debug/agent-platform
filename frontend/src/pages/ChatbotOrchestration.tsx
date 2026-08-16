import React, { useState, useEffect } from 'react'
import { Card, Button, message, Spin, Row, Col, Space, Breadcrumb } from 'antd'
import { SaveOutlined, SettingOutlined, CommentOutlined } from '@ant-design/icons'
import { useParams, useNavigate, Link } from 'react-router-dom'
import PromptEditor from '../components/PromptEditor'
import VariableSettings from '../components/VariableSettings'
import KnowledgeBaseSelector from '../components/KnowledgeBaseSelector'
import ModelSelector from '../components/ModelSelector'
import ModelParametersModal from '../components/ModelParameters'
import { chatbotApi, ChatbotConfig, ModelParameters as ModelParametersType } from '../services/chatbot'

const defaultParameters: ModelParametersType = {
  temperature: 0.7,
  top_p: 1,
  top_k: 1,
  presence_penalty: 0,
  frequency_penalty: 0,
  max_tokens: 512,
  skip_content_review: false
}

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

        <Card title="变量设置" className="mb-4">
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
