import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Typography,
  Upload,
  App,
  Popconfirm,
  Descriptions,
  Statistic,
  Row,
  Col,
} from 'antd'
import {
  ArrowLeftOutlined,
  UploadOutlined,
  DeleteOutlined,
  EyeOutlined,
  ReloadOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  SyncOutlined,
  ClockCircleOutlined,
  DownOutlined,
} from '@ant-design/icons'
import {
  knowledgeApi,
  KnowledgeBaseData,
  DocumentData,
} from '../services/knowledge'
import SegmentDrawer from '../components/SegmentDrawer'
import SearchTestPanel from '../components/SearchTestPanel'

const { Title, Text } = Typography

const KnowledgeDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { message } = App.useApp()

  const kbId = Number(id)
  const [kb, setKb] = useState<KnowledgeBaseData | null>(null)
  const [documents, setDocuments] = useState<DocumentData[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<number | null>(null)

  // 分段抽屉
  const [segmentDrawerVisible, setSegmentDrawerVisible] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState<DocumentData | null>(null)

  useEffect(() => {
    if (kbId) {
      fetchKB()
      fetchDocuments(true)
    }
  }, [kbId])

  const fetchKB = async () => {
    try {
      const response = await knowledgeApi.getKnowledgeBase(kbId)
      setKb(response.data)
    } catch {
      message.error('获取知识库信息失败')
    }
  }

  const fetchDocuments = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? undefined : nextCursor ?? undefined
      const response = await knowledgeApi.getDocuments(kbId, {
        cursor,
        limit: 50,
      })
      const { items, next_cursor, has_more } = response.data
      if (reset) {
        setDocuments(items)
      } else {
        setDocuments((prev) => [...prev, ...items])
      }
      setNextCursor(next_cursor)
      setHasMore(has_more)
    } catch {
      message.error('获取文档列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      await knowledgeApi.uploadDocument(kbId, file)
      message.success('文档上传成功，正在后台处理...')
      // 重新加载文档列表
      setDocuments([])
      setNextCursor(null)
      fetchDocuments(true)
      fetchKB()
    } catch {
      message.error('文档上传失败')
    } finally {
      setUploading(false)
    }
    return false
  }

  const handleDeleteDocument = async (docId: number) => {
    try {
      await knowledgeApi.deleteDocument(kbId, docId)
      message.success('文档已删除')
      setDocuments((prev) => prev.filter((doc) => doc.id !== docId))
      fetchKB()
    } catch {
      message.error('删除文档失败')
    }
  }

  const handleRetryDocument = async (docId: number) => {
    try {
      await knowledgeApi.retryDocument(kbId, docId)
      message.success('文档已加入重新处理队列')
      // 重新加载
      setDocuments([])
      setNextCursor(null)
      fetchDocuments(true)
    } catch {
      message.error('重新处理失败')
    }
  }

  const handleViewSegments = (doc: DocumentData) => {
    setSelectedDoc(doc)
    setSegmentDrawerVisible(true)
  }

  // 状态标签
  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待处理' },
      processing: { color: 'processing', icon: <SyncOutlined spin />, text: '处理中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '处理失败' },
    }
    const c = config[status] || config.pending
    return <Tag color={c.color} icon={c.icon}>{c.text}</Tag>
  }

  // 文件大小格式化
  const formatFileSize = (bytes?: number) => {
    if (!bytes) return '-'
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  // 文档类型图标
  const getFileTypeTag = (type: string) => {
    const colors: Record<string, string> = {
      pdf: 'red',
      excel: 'green',
      markdown: 'blue',
      docx: 'cyan',
      html: 'orange',
      txt: 'default',
    }
    return <Tag color={colors[type] || 'default'}>{type.toUpperCase()}</Tag>
  }

  const columns = [
    {
      title: '文档名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: DocumentData) => (
        <Space>
          <FileTextOutlined />
          <Text>{text}</Text>
          {getFileTypeTag(record.file_type)}
        </Space>
      ),
    },
    {
      title: '大小',
      dataIndex: 'file_size',
      key: 'file_size',
      width: 100,
      render: (size: number) => formatFileSize(size),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '分段数',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 80,
      render: (count: number, record: DocumentData) =>
        record.status === 'completed' ? count : '-',
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      width: 200,
      render: (msg: string) =>
        msg ? <Text type="danger" ellipsis>{msg}</Text> : '-',
    },
    {
      title: '上传时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: DocumentData) => (
        <Space>
          {record.status === 'completed' && (
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => handleViewSegments(record)}
            >
              分段
            </Button>
          )}
          {record.status === 'failed' && (
            <Button
              type="link"
              icon={<ReloadOutlined />}
              onClick={() => handleRetryDocument(record.id)}
            >
              重试
            </Button>
          )}
          <Popconfirm
            title="确定要删除此文档吗？"
            description="删除后关联的分段数据也将被删除"
            onConfirm={() => handleDeleteDocument(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  if (!kb) {
    return <Card loading />
  }

  return (
    <div>
      {/* 顶部导航 */}
      <div style={{ marginBottom: 16 }}>
        <Button
          type="link"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/knowledge')}
          style={{ padding: 0 }}
        >
          返回知识库列表
        </Button>
      </div>

      {/* 知识库信息 */}
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={24}>
          <Col span={16}>
            <Title level={4} style={{ margin: 0 }}>
              <DatabaseOutlined style={{ marginRight: 8 }} />
              {kb.name}
              <Tag
                color={kb.status === 'active' ? 'success' : 'default'}
                style={{ marginLeft: 12 }}
              >
                {kb.status === 'active' ? '正常' : kb.status}
              </Tag>
            </Title>
            {kb.description && (
              <Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
                {kb.description}
              </Text>
            )}
          </Col>
          <Col span={8}>
            <Row gutter={16}>
              <Col span={12}>
                <Statistic title="文档数量" value={kb.document_count} prefix={<FileTextOutlined />} />
              </Col>
              <Col span={12}>
                <Statistic title="分段数量" value={kb.chunk_count} prefix={<DatabaseOutlined />} />
              </Col>
            </Row>
          </Col>
        </Row>
      </Card>

      {/* 文档列表 */}
      <Card
        title="文档管理"
        extra={
          <Upload
            beforeUpload={handleUpload}
            showUploadList={false}
            accept=".pdf,.xlsx,.xls,.md,.docx,.html,.txt"
            disabled={uploading}
          >
            <Button type="primary" icon={<UploadOutlined />} loading={uploading}>
              上传文档
            </Button>
          </Upload>
        }
      >
        <Table
          columns={columns}
          dataSource={documents}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
        {hasMore && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Button
              icon={<DownOutlined />}
              loading={loading}
              onClick={() => fetchDocuments(false)}
            >
              加载更多
            </Button>
          </div>
        )}
      </Card>

      {/* 检索测试 */}
      <SearchTestPanel kbId={kbId} />

      {/* 分段查看抽屉 */}
      {selectedDoc && (
        <SegmentDrawer
          visible={segmentDrawerVisible}
          onClose={() => {
            setSegmentDrawerVisible(false)
            setSelectedDoc(null)
          }}
          kbId={kbId}
          docId={selectedDoc.id}
          docName={selectedDoc.name}
        />
      )}
    </div>
  )
}

export default KnowledgeDetail
