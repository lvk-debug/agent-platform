import React, { useState, useEffect, useMemo } from 'react'
import {
  Drawer,
  Steps,
  Button,
  Space,
  Typography,
  Radio,
  InputNumber,
  Card,
  Tag,
  Spin,
  App,
  Descriptions,
  Empty,
  Collapse,
  Pagination,
  Select,
} from 'antd'
import {
  FileTextOutlined,
  SettingOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons'
import {
  knowledgeApi,
  DocumentData,
  ChunkPreviewItem,
} from '@/services/knowledge'

const { Text, Paragraph } = Typography

interface ChunkSettingDrawerProps {
  visible: boolean
  onClose: () => void
  kbId: number
  document: DocumentData
  onSuccess: () => void
}

const ChunkSettingDrawer: React.FC<ChunkSettingDrawerProps> = ({
  visible,
  onClose,
  kbId,
  document,
  onSuccess,
}) => {
  const { message } = App.useApp()
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [processing, setProcessing] = useState(false)

  // 文档内容
  const [docContent, setDocContent] = useState<string>('')

  // 分片设置
  const [chunkStrategy, setChunkStrategy] = useState<'sliding_window' | 'paragraph'>('sliding_window')
  const [chunkSize, setChunkSize] = useState(500)
  const [chunkOverlap, setChunkOverlap] = useState(50)

  // 默认句子边界分隔符
  const DEFAULT_SEPARATORS = ['。', '\n', '！', '？', '.', '!', '?', '；', ';']
  const [separators, setSeparators] = useState<string[]>(DEFAULT_SEPARATORS)

  // 可选的分隔符列表
  const SEPARATOR_OPTIONS = [
    { label: '。 (中文句号)', value: '。' },
    { label: '. (英文句号)', value: '.' },
    { label: '\\n (换行)', value: '\n' },
    { label: '！ (中文感叹号)', value: '！' },
    { label: '! (英文感叹号)', value: '!' },
    { label: '？ (中文问号)', value: '？' },
    { label: '? (英文问号)', value: '?' },
    { label: '； (中文分号)', value: '；' },
    { label: '; (英文分号)', value: ';' },
    { label: '—— (破折号)', value: '——' },
    { label: '… (省略号)', value: '…' },
  ]

  // 分片预览
  const [previewChunks, setPreviewChunks] = useState<ChunkPreviewItem[]>([])
  const [totalChunks, setTotalChunks] = useState(0)

  useEffect(() => {
    if (visible && document) {
      setCurrentStep(0)
      setContentPage(1)
      setChunkPage(1)
      setPreviewChunks([])
      setTotalChunks(0)
      fetchDocumentContent()
    }
  }, [visible, document])

  const fetchDocumentContent = async () => {
    setLoading(true)
    try {
      const response = await knowledgeApi.getDocumentContent(kbId, document.id)
      setDocContent(response.data.content || '')
    } catch {
      message.error('获取文档内容失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePreviewChunks = async () => {
    setLoading(true)
    try {
      const response = await knowledgeApi.previewChunks(kbId, document.id, {
        chunk_strategy: chunkStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators,
      })
      setPreviewChunks(response.data.chunks)
      setTotalChunks(response.data.total_chunks)
      setCurrentStep(2)
    } catch {
      message.error('预览分片失败')
    } finally {
      setLoading(false)
    }
  }

  const handleProcess = async () => {
    setProcessing(true)
    try {
      await knowledgeApi.processDocument(kbId, document.id, {
        chunk_strategy: chunkStrategy,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        separators,
      })
      message.success('文档已加入处理队列')
      onClose()
      onSuccess()
    } catch {
      message.error('处理文档失败')
    } finally {
      setProcessing(false)
    }
  }

  const steps = [
    {
      title: '预览内容',
      icon: <FileTextOutlined />,
    },
    {
      title: '分片设置',
      icon: <SettingOutlined />,
    },
    {
      title: '确认处理',
      icon: <CheckCircleOutlined />,
    },
  ]

  // 内容分页
  const PAGE_SIZE = 3000
  const [contentPage, setContentPage] = useState(1)

  // 分片预览分页
  const CHUNK_PAGE_SIZE = 20
  const [chunkPage, setChunkPage] = useState(1)

  const contentPages = useMemo(() => {
    if (!docContent) return []
    const pages: string[] = []
    for (let i = 0; i < docContent.length; i += PAGE_SIZE) {
      pages.push(docContent.slice(i, i + PAGE_SIZE))
    }
    return pages
  }, [docContent])

  const renderStep0 = () => (
    <div>
      <Descriptions column={1} bordered size="small" className="mb-4">
        <Descriptions.Item label="文档名称">{document.name}</Descriptions.Item>
        <Descriptions.Item label="文件类型">
          <Tag color="blue">{document.file_type.toUpperCase()}</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="内容长度">
          {docContent ? `${docContent.length} 字符` : '-'}
        </Descriptions.Item>
      </Descriptions>

      <div className="mb-2">
        <Text strong>Markdown 内容预览：</Text>
      </div>
      <Card
        size="small"
        style={{
          maxHeight: 400,
          overflow: 'auto',
          backgroundColor: '#fafafa',
        }}
      >
        {loading ? (
          <div className="text-center py-8">
            <Spin />
          </div>
        ) : docContent ? (
          <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, margin: 0 }}>
            {contentPages[contentPage - 1] || ''}
          </pre>
        ) : (
          <Empty description="暂无内容" />
        )}
      </Card>

      {docContent && contentPages.length > 1 && (
        <div className="mt-2 text-center">
          <Pagination
            size="small"
            current={contentPage}
            total={contentPages.length}
            pageSize={1}
            onChange={setContentPage}
            showTotal={(p) => `第 ${p} / ${contentPages.length} 页`}
            simple
          />
        </div>
      )}

      <div className="mt-4 text-right">
        <Button
          type="primary"
          onClick={() => setCurrentStep(1)}
          disabled={!docContent}
        >
          下一步：设置分片策略
        </Button>
      </div>
    </div>
  )

  const renderStep1 = () => (
    <div>
      <div className="mb-4">
        <Text strong>分片策略：</Text>
        <Radio.Group
          value={chunkStrategy}
          onChange={(e) => setChunkStrategy(e.target.value)}
          className="ml-4"
        >
          <Radio.Button value="sliding_window">滑动窗口</Radio.Button>
          <Radio.Button value="paragraph">按段落</Radio.Button>
        </Radio.Group>
      </div>

      <Card size="small" className="mb-4">
        <div className="mb-2">
          <Text type="secondary">
            {chunkStrategy === 'sliding_window'
              ? '滑动窗口：按固定字符数切分，在句子边界处断开，适合长段落文本'
              : '按段落：先按双换行切分段落，超长段落再用滑动窗口细分，保留自然段落结构'}
          </Text>
        </div>
      </Card>

      <div className="flex gap-4 mb-4">
        <div>
          <Text>分片大小：</Text>
          <InputNumber
            value={chunkSize}
            onChange={(v) => setChunkSize(v || 500)}
            min={100}
            max={2000}
            step={100}
            className="ml-2"
            style={{ width: 100 }}
          />
          <Text type="secondary" className="ml-1">字符</Text>
        </div>
        <div>
          <Text>重叠大小：</Text>
          <InputNumber
            value={chunkOverlap}
            onChange={(v) => setChunkOverlap(v || 50)}
            min={0}
            max={500}
            step={10}
            className="ml-2"
            style={{ width: 100 }}
          />
          <Text type="secondary" className="ml-1">字符</Text>
        </div>
      </div>

      <div className="mb-4">
        <div className="mb-2">
          <Text>句子边界分隔符：</Text>
          <Text type="secondary" className="ml-2">按优先级排序，靠前的优先匹配</Text>
        </div>
        <Select
          mode="tags"
          value={separators}
          onChange={(vals) => setSeparators(vals)}
          options={SEPARATOR_OPTIONS}
          style={{ width: '100%' }}
          tokenSeparators={[',']}
          placeholder="输入或选择分隔符"
          maxTagCount="responsive"
        />
      </div>

      <div className="flex justify-between">
        <Button onClick={() => setCurrentStep(0)}>
          上一步
        </Button>
        <Button type="primary" onClick={handlePreviewChunks} loading={loading}>
          预览分片效果
        </Button>
      </div>
    </div>
  )

  const renderStep2 = () => (
    <div>
      <Descriptions column={2} bordered size="small" className="mb-4">
        <Descriptions.Item label="分片策略">
          <Tag color="blue">
            {chunkStrategy === 'sliding_window' ? '滑动窗口' : '按段落'}
          </Tag>
        </Descriptions.Item>
        <Descriptions.Item label="分片大小">{chunkSize} 字符</Descriptions.Item>
        <Descriptions.Item label="重叠大小">{chunkOverlap} 字符</Descriptions.Item>
        <Descriptions.Item label="总分片数">
          <Tag color="green">{totalChunks} 个</Tag>
        </Descriptions.Item>
        <Descriptions.Item label="句子边界" span={2}>
          <Space size={[4, 4]} wrap>
            {separators.map((sep, i) => (
              <Tag key={i}>{sep === '\n' ? '\\n' : sep}</Tag>
            ))}
          </Space>
        </Descriptions.Item>
      </Descriptions>

      <div className="mb-2">
        <Text strong>分片预览：</Text>
      </div>
      <Card
        size="small"
        style={{ maxHeight: 400, overflow: 'auto' }}
      >
        {previewChunks.length > 0 ? (
          <Collapse
            size="small"
            items={previewChunks
              .slice((chunkPage - 1) * CHUNK_PAGE_SIZE, chunkPage * CHUNK_PAGE_SIZE)
              .map((chunk, i) => {
                const index = (chunkPage - 1) * CHUNK_PAGE_SIZE + i
                return {
                  key: index,
                  label: (
                    <Space>
                      <Tag>#{index + 1}</Tag>
                      <Text type="secondary">{chunk.content.substring(0, 50)}...</Text>
                      <Text type="secondary">({chunk.content.length} 字符)</Text>
                    </Space>
                  ),
                  children: (
                    <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace', fontSize: 12, margin: 0 }}>
                      {chunk.content}
                    </pre>
                  ),
                }
              })}
          />
        ) : (
          <Empty description="暂无预览" />
        )}
      </Card>

      {previewChunks.length > CHUNK_PAGE_SIZE && (
        <div className="mt-2 text-center">
          <Pagination
            size="small"
            current={chunkPage}
            total={previewChunks.length}
            pageSize={CHUNK_PAGE_SIZE}
            onChange={setChunkPage}
            showTotal={(p, range) => `${range[0]}-${range[1]} / 共 ${previewChunks.length} 个分片`}
          />
        </div>
      )}

      <div className="mt-4 flex justify-between">
        <Button onClick={() => setCurrentStep(1)}>
          上一步
        </Button>
        <Button
          type="primary"
          onClick={handleProcess}
          loading={processing}
          icon={<CheckCircleOutlined />}
        >
          确认处理
        </Button>
      </div>
    </div>
  )

  return (
    <Drawer
      title="文档分片设置"
      placement="right"
      width={720}
      open={visible}
      onClose={onClose}
      extra={
        <Button onClick={onClose}>关闭</Button>
      }
    >
      <Steps
        current={currentStep}
        items={steps}
        className="mb-6"
      />

      {currentStep === 0 && renderStep0()}
      {currentStep === 1 && renderStep1()}
      {currentStep === 2 && renderStep2()}
    </Drawer>
  )
}

export default ChunkSettingDrawer
