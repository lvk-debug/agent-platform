import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Tabs,
  Switch,
  Button,
  Tag,
  Space,
  Typography,
  Spin,
  Input,
  message,
  Divider,
  Steps,
} from 'antd'
import {
  ApiOutlined,
  CloudOutlined,
  CodeOutlined,
  WechatOutlined,
  MobileOutlined,
  CopyOutlined,
  ArrowLeftOutlined,
  CheckCircleFilled,
  LinkOutlined,
} from '@ant-design/icons'
import { appsApi, AppData } from '../services/apps'
import { publishApi, PublishConfig, PublishChannel } from '../services/publish'

const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs

// 渠道图标映射
const channelIcons: Record<PublishChannel, React.ReactNode> = {
  api: <ApiOutlined />,
  mcp: <CloudOutlined />,
  embed: <CodeOutlined />,
  wechat: <WechatOutlined />,
  h5: <MobileOutlined />,
}

// 渠道名称映射
const channelNames: Record<PublishChannel, string> = {
  api: 'API',
  mcp: 'MCP',
  embed: '平台嵌入',
  wechat: '微信公众号',
  h5: 'H5',
}

const PublishManagement: React.FC = () => {
  const { appId } = useParams<{ appId: string }>()
  const navigate = useNavigate()
  const [app, setApp] = useState<AppData | null>(null)
  const [configs, setConfigs] = useState<PublishConfig[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<PublishChannel>('api')
  const [toggling, setToggling] = useState<Record<string, boolean>>({})
  const { message: msg } = message

  // 加载应用信息
  const fetchApp = useCallback(async () => {
    if (!appId) return
    try {
      const response = await appsApi.getApp(Number(appId))
      setApp(response.data)
    } catch (error) {
      msg.error('获取应用信息失败')
    }
  }, [appId, msg])

  // 加载发布配置
  const fetchConfigs = useCallback(async () => {
    if (!appId) return
    setLoading(true)
    try {
      const response = await publishApi.getAll(Number(appId))
      setConfigs(response.data.configs)
    } catch (error) {
      msg.error('获取发布配置失败')
    } finally {
      setLoading(false)
    }
  }, [appId, msg])

  useEffect(() => {
    fetchApp()
    fetchConfigs()
  }, [fetchApp, fetchConfigs])

  // 获取当前渠道配置
  const getConfig = (channel: PublishChannel): PublishConfig | undefined => {
    return configs.find((c) => c.channel === channel)
  }

  // 切换渠道启用状态
  const handleToggle = async (channel: PublishChannel, enabled: boolean) => {
    setToggling((prev) => ({ ...prev, [channel]: true }))
    try {
      let response
      if (enabled) {
        response = await publishApi.enable(Number(appId), channel)
      } else {
        response = await publishApi.disable(Number(appId), channel)
      }
      setConfigs((prev) =>
        prev.map((c) => (c.channel === channel ? response.data : c))
      )
      msg.success(enabled ? '已启用' : '已禁用')
    } catch (error) {
      msg.error('操作失败')
    } finally {
      setToggling((prev) => ({ ...prev, [channel]: false }))
    }
  }

  // 复制文本到剪贴板
  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      msg.success('已复制到剪贴板')
    }).catch(() => {
      msg.error('复制失败')
    })
  }

  // 渲染 API 渠道配置
  const renderApiConfig = () => {
    const config = getConfig('api')
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text strong>启用 API 访问</Text>
            <Text type="secondary">通过 API Key 调用应用</Text>
          </Space>
          <Switch
            checked={config?.enabled || false}
            loading={toggling['api']}
            onChange={(checked) => handleToggle('api', checked)}
          />
        </div>

        {config?.enabled && (
          <Card type="inner" title="访问凭证">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">API Key</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input.Password
                    value={config.api_key || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.api_key || '')}>
                    复制
                  </Button>
                </div>
              </div>
              <div>
                <Text type="secondary">API Endpoint</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={config.api_endpoint || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.api_endpoint || '')}>
                    复制
                  </Button>
                </div>
              </div>
            </Space>

            <Divider />

            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>调用示例</Text>
            <Card style={{ background: '#1e1e1e', borderRadius: 8 }}>
              <pre style={{ color: '#d4d4d4', margin: 0, fontSize: 13 }}>
{`curl -X POST ${config.api_endpoint || 'https://api.example.com/v1/apps/1/chat'} \\
  -H "Authorization: Bearer ${config.api_key || '<your-api-key>'}" \\
  -H "Content-Type: application/json" \\
  -d '{"message": "你好"}'`}
              </pre>
            </Card>
          </Card>
        )}

        {!config?.enabled && (
          <Card type="inner" style={{ textAlign: 'center', padding: '40px 0' }}>
            <ApiOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">启用后将生成 API Key 和调用地址</Text>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // 渲染 MCP 渠道配置
  const renderMcpConfig = () => {
    const config = getConfig('mcp')
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text strong>启用 MCP 服务</Text>
            <Text type="secondary">通过 MCP 协议访问应用</Text>
          </Space>
          <Switch
            checked={config?.enabled || false}
            loading={toggling['mcp']}
            onChange={(checked) => handleToggle('mcp', checked)}
          />
        </div>

        {config?.enabled && (
          <Card type="inner" title="MCP 配置">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">启动命令</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={config.mcp_command || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.mcp_command || '')}>
                    复制
                  </Button>
                </div>
              </div>
            </Space>

            <Divider />

            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>MCP Server 配置</Text>
            <Card style={{ background: '#1e1e1e', borderRadius: 8 }}>
              <pre style={{ color: '#d4d4d4', margin: 0, fontSize: 13 }}>
                {JSON.stringify(config.mcp_config || {}, null, 2)}
              </pre>
            </Card>
          </Card>
        )}

        {!config?.enabled && (
          <Card type="inner" style={{ textAlign: 'center', padding: '40px 0' }}>
            <CloudOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">启用后将生成 MCP Server 配置</Text>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // 渲染平台嵌入配置
  const renderEmbedConfig = () => {
    const config = getConfig('embed')
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text strong>启用平台嵌入</Text>
            <Text type="secondary">通过 iframe 嵌入到其他页面</Text>
          </Space>
          <Switch
            checked={config?.enabled || false}
            loading={toggling['embed']}
            onChange={(checked) => handleToggle('embed', checked)}
          />
        </div>

        {config?.enabled && (
          <Card type="inner" title="嵌入代码">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">访问链接</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={config.embed_url || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.embed_url || '')}>
                    复制
                  </Button>
                </div>
              </div>
            </Space>

            <Divider />

            <Text type="secondary" style={{ display: 'block', marginBottom: 8 }}>iframe 嵌入代码</Text>
            <Card style={{ background: '#1e1e1e', borderRadius: 8 }}>
              <pre style={{ color: '#d4d4d4', margin: 0, fontSize: 13 }}>
                {config.embed_code || '未生成'}
              </pre>
            </Card>
            <Button
              type="primary"
              icon={<CopyOutlined />}
              style={{ marginTop: 12 }}
              onClick={() => handleCopy(config.embed_code || '')}
            >
              复制嵌入代码
            </Button>
          </Card>
        )}

        {!config?.enabled && (
          <Card type="inner" style={{ textAlign: 'center', padding: '40px 0' }}>
            <CodeOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">启用后将生成 iframe 嵌入代码</Text>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // 渲染微信公众号配置
  const renderWechatConfig = () => {
    const config = getConfig('wechat')
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text strong>启用微信公众号</Text>
            <Text type="secondary">对接微信公众号自动回复</Text>
          </Space>
          <Switch
            checked={config?.enabled || false}
            loading={toggling['wechat']}
            onChange={(checked) => handleToggle('wechat', checked)}
          />
        </div>

        {config?.enabled && (
          <Card type="inner" title="对接配置">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">Webhook URL</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={config.wechat_webhook_url || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.wechat_webhook_url || '')}>
                    复制
                  </Button>
                </div>
              </div>
            </Space>

            <Divider />

            <Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>配置步骤</Text>
            <Steps
              direction="vertical"
              size="small"
              current={-1}
              items={(config.wechat_guide || []).map((step) => ({
                title: step.title,
                description: step.description,
              }))}
            />
          </Card>
        )}

        {!config?.enabled && (
          <Card type="inner" style={{ textAlign: 'center', padding: '40px 0' }}>
            <WechatOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">启用后将生成微信公众号对接配置</Text>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // 渲染 H5 配置
  const renderH5Config = () => {
    const config = getConfig('h5')
    return (
      <div>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Text strong>启用 H5 页面</Text>
            <Text type="secondary">生成独立的移动端访问页面</Text>
          </Space>
          <Switch
            checked={config?.enabled || false}
            loading={toggling['h5']}
            onChange={(checked) => handleToggle('h5', checked)}
          />
        </div>

        {config?.enabled && (
          <Card type="inner" title="H5 访问信息">
            <Space direction="vertical" style={{ width: '100%' }}>
              <div>
                <Text type="secondary">访问链接</Text>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Input
                    value={config.h5_url || '未生成'}
                    readOnly
                    style={{ fontFamily: 'monospace' }}
                  />
                  <Button icon={<CopyOutlined />} onClick={() => handleCopy(config.h5_url || '')}>
                    复制
                  </Button>
                </div>
              </div>
            </Space>

            <Divider />

            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={{
                width: 200,
                height: 200,
                border: '1px solid #d9d9d9',
                borderRadius: 8,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto',
                background: '#fafafa',
              }}>
                <div style={{ textAlign: 'center' }}>
                  <MobileOutlined style={{ fontSize: 32, color: '#1677ff', marginBottom: 8 }} />
                  <div>
                    <Text type="secondary">二维码</Text>
                  </div>
                </div>
              </div>
              <Button
                type="primary"
                icon={<LinkOutlined />}
                style={{ marginTop: 16 }}
                onClick={() => window.open(config.h5_url, '_blank')}
              >
                预览 H5 页面
              </Button>
            </div>
          </Card>
        )}

        {!config?.enabled && (
          <Card type="inner" style={{ textAlign: 'center', padding: '40px 0' }}>
            <MobileOutlined style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 16 }} />
            <div>
              <Text type="secondary">启用后将生成 H5 访问链接</Text>
            </div>
          </Card>
        )}
      </div>
    )
  }

  // 根据渠道渲染配置内容
  const renderChannelContent = (channel: PublishChannel) => {
    switch (channel) {
      case 'api':
        return renderApiConfig()
      case 'mcp':
        return renderMcpConfig()
      case 'embed':
        return renderEmbedConfig()
      case 'wechat':
        return renderWechatConfig()
      case 'h5':
        return renderH5Config()
      default:
        return null
    }
  }

  // 渲染渠道状态标签
  const renderChannelStatus = (channel: PublishChannel) => {
    const config = getConfig(channel)
    if (config?.enabled) {
      return <Tag color="success" icon={<CheckCircleFilled />}>已启用</Tag>
    }
    return <Tag>未启用</Tag>
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      {/* 顶部导航 */}
      <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/apps')}
        />
        <div>
          <Title level={4} style={{ margin: 0 }}>
            {app?.name || '应用'} - 发布管理
          </Title>
          <Space style={{ marginTop: 4 }}>
            <Tag color={app?.status === 'published' ? 'success' : 'default'}>
              {app?.status === 'published' ? '已发布' : app?.status === 'draft' ? '草稿' : '已禁用'}
            </Tag>
            <Text type="secondary">版本 {app?.version}</Text>
          </Space>
        </div>
      </div>

      {/* 渠道配置 Tabs */}
      <Card>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as PublishChannel)}
          items={[
            {
              key: 'api',
              label: (
                <Space>
                  {channelIcons.api}
                  {channelNames.api}
                  {renderChannelStatus('api')}
                </Space>
              ),
              children: renderChannelContent('api'),
            },
            {
              key: 'mcp',
              label: (
                <Space>
                  {channelIcons.mcp}
                  {channelNames.mcp}
                  {renderChannelStatus('mcp')}
                </Space>
              ),
              children: renderChannelContent('mcp'),
            },
            {
              key: 'embed',
              label: (
                <Space>
                  {channelIcons.embed}
                  {channelNames.embed}
                  {renderChannelStatus('embed')}
                </Space>
              ),
              children: renderChannelContent('embed'),
            },
            {
              key: 'wechat',
              label: (
                <Space>
                  {channelIcons.wechat}
                  {channelNames.wechat}
                  {renderChannelStatus('wechat')}
                </Space>
              ),
              children: renderChannelContent('wechat'),
            },
            {
              key: 'h5',
              label: (
                <Space>
                  {channelIcons.h5}
                  {channelNames.h5}
                  {renderChannelStatus('h5')}
                </Space>
              ),
              children: renderChannelContent('h5'),
            },
          ]}
        />
      </Card>
    </div>
  )
}

export default PublishManagement
