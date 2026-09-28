import React, { useState, useEffect } from 'react'
import { Spin, Row, Col, Breadcrumb } from 'antd'
import { useParams, useNavigate, Link } from 'react-router-dom'
import ChatPreview from '@/components/ChatPreview'
import { chatbotApi, ChatbotConfig } from '@/services/chatbot'

const ChatbotDebug: React.FC = () => {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const [config, setConfig] = useState<ChatbotConfig | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchConfig()
  }, [appId])

  const fetchConfig = async () => {
    if (!appId) return
    setLoading(true)
    try {
      const data = await chatbotApi.getConfig(Number(appId))
      setConfig(data)
    } catch (error) {
      console.error('Failed to fetch config:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '100px 0' }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div style={{ height: 'calc(100vh - 100px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '12px 0', borderBottom: '1px solid #f0f0f0' }}>
        <Row justify="space-between" align="middle">
          <Col>
            <Breadcrumb
              items={[
                { title: <Link to="/apps">应用</Link> },
                { title: <Link to={`/apps/${appId}/chatbot`}>聊天助手编排</Link> },
                { title: '调试与预览' },
              ]}
            />
          </Col>
        </Row>
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <ChatPreview
          appId={Number(appId)}
          config={{
            variables: config?.variables,
          }}
        />
      </div>
    </div>
  )
}

export default ChatbotDebug
