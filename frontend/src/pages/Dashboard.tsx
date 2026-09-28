import React, { useEffect, useState } from 'react'
import { Row, Col, Card, Statistic, Typography, Space, Button, List, Tag } from 'antd'
import {
  AppstoreOutlined,
  BookOutlined,
  SettingOutlined,
  ToolOutlined,
  PlusOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { appsApi, AppData } from '@/services/apps'
import { knowledgeApi, KnowledgeBaseData } from '@/services/knowledge'

const { Title, Text } = Typography

const Dashboard: React.FC = () => {
  const navigate = useNavigate()
  const [apps, setApps] = useState<AppData[]>([])
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseData[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [appsRes, kbRes] = await Promise.all([
        appsApi.getApps({ limit: 5 }),
        knowledgeApi.getKnowledgeBases({ limit: 5 }),
      ])
      setApps(appsRes.data.items)
      setKnowledgeBases(kbRes.data.items)
    } catch (error) {
      console.error('获取数据失败:', error)
    } finally {
      setLoading(false)
    }
  }

  // 应用类型标签颜色
  const getAppTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      chatbot: 'blue',
      workflow: 'green',
      agent: 'purple',
    }
    return colors[type] || 'default'
  }

  // 应用类型中文名
  const getAppTypeName = (type: string) => {
    const names: Record<string, string> = {
      chatbot: '聊天助手',
      workflow: '工作流',
      agent: 'Agent',
    }
    return names[type] || type
  }

  return (
    <div>
      <Title level={4} className="mb-6">
        仪表盘
      </Title>

      {/* 统计卡片 */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/apps')}>
            <Statistic
              title="应用数量"
              value={apps.length}
              prefix={<AppstoreOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/knowledge')}>
            <Statistic
              title="知识库数量"
              value={knowledgeBases.length}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/models')}>
            <Statistic
              title="模型供应商"
              value={0}
              prefix={<SettingOutlined />}
            />
          </Card>
        </Col>
        <Col xs={24} sm={12} lg={6}>
          <Card hoverable onClick={() => navigate('/tools')}>
            <Statistic
              title="工具数量"
              value={0}
              prefix={<ToolOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 快速操作 */}
      <Row gutter={[16, 16]} className="mb-6">
        <Col xs={24} lg={12}>
          <Card
            title="快速创建"
            extra={
              <Button type="link" onClick={() => navigate('/apps')}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
          >
            <Space direction="vertical" className="w-full">
              <Button
                type="dashed"
                block
                icon={<PlusOutlined />}
                onClick={() => navigate('/apps?create=chatbot')}
              >
                创建聊天助手
              </Button>
              <Button
                type="dashed"
                block
                icon={<PlusOutlined />}
                onClick={() => navigate('/apps?create=workflow')}
              >
                创建工作流
              </Button>
              <Button
                type="dashed"
                block
                icon={<PlusOutlined />}
                onClick={() => navigate('/apps?create=agent')}
              >
                创建Agent
              </Button>
            </Space>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title="快速开始"
            extra={
              <Button type="link">
                查看文档 <ArrowRightOutlined />
              </Button>
            }
          >
            <List
              dataSource={[
                { title: '1. 配置模型供应商', desc: '添加OpenAI、Anthropic等模型供应商' },
                { title: '2. 创建知识库', desc: '上传文档，构建知识库' },
                { title: '3. 创建应用', desc: '选择类型，配置应用' },
                { title: '4. 测试发布', desc: '测试应用并发布上线' },
              ]}
              renderItem={(item) => (
                <List.Item>
                  <List.Item.Meta
                    title={item.title}
                    description={item.desc}
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>

      {/* 最近应用 */}
      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card
            title="最近应用"
            extra={
              <Button type="link" onClick={() => navigate('/apps')}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
          >
            <List
              loading={loading}
              dataSource={apps}
              renderItem={(app) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      onClick={() => navigate(`/apps/${app.id}`)}
                    >
                      编辑
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={app.name}
                    description={
                      <Space>
                        <Tag color={getAppTypeColor(app.app_type)}>
                          {getAppTypeName(app.app_type)}
                        </Tag>
                        <Text type="secondary">
                          {new Date(app.updated_at).toLocaleDateString()}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            title="最近知识库"
            extra={
              <Button type="link" onClick={() => navigate('/knowledge')}>
                查看全部 <ArrowRightOutlined />
              </Button>
            }
          >
            <List
              loading={loading}
              dataSource={knowledgeBases}
              renderItem={(kb) => (
                <List.Item
                  actions={[
                    <Button
                      type="link"
                      onClick={() => navigate(`/knowledge/${kb.id}`)}
                    >
                      查看
                    </Button>,
                  ]}
                >
                  <List.Item.Meta
                    title={kb.name}
                    description={
                      <Space>
                        <Text type="secondary">{kb.document_count} 个文档</Text>
                        <Text type="secondary">{kb.chunk_count} 个分段</Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
