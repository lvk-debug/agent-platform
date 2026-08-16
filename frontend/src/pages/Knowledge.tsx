import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Input,
  Modal,
  Form,
  Select,
  App,
  Popconfirm,
  Typography,
  Upload,
  Row,
  Col,
} from 'antd'
import {
  PlusOutlined,
  SearchOutlined,
  EditOutlined,
  DeleteOutlined,
  UploadOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  DownOutlined,
} from '@ant-design/icons'
import { knowledgeApi, KnowledgeBaseData, CreateKnowledgeBaseData } from '../services/knowledge'

const { Title, Text } = Typography
const { Option } = Select

const Knowledge: React.FC = () => {
  const navigate = useNavigate()
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBaseData[]>([])
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState<number | null>(null)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [createForm] = Form.useForm()
  const [selectedKB, setSelectedKB] = useState<KnowledgeBaseData | null>(null)
  const [uploadModalVisible, setUploadModalVisible] = useState(false)
  const { message } = App.useApp()

  useEffect(() => {
    fetchKnowledgeBases(true)
  }, [])

  const fetchKnowledgeBases = async (reset = false) => {
    setLoading(true)
    try {
      const cursor = reset ? undefined : nextCursor ?? undefined
      const response = await knowledgeApi.getKnowledgeBases({ cursor, limit: 20 })
      const { items, next_cursor, has_more } = response.data
      if (reset) {
        setKnowledgeBases(items)
      } else {
        setKnowledgeBases((prev) => [...prev, ...items])
      }
      setNextCursor(next_cursor)
      setHasMore(has_more)
    } catch (error) {
      message.error('获取知识库列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: CreateKnowledgeBaseData) => {
    try {
      await knowledgeApi.createKnowledgeBase(values)
      message.success('知识库创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      setKnowledgeBases([])
      setNextCursor(null)
      fetchKnowledgeBases(true)
    } catch (error) {
      message.error('创建知识库失败')
    }
  }

  const handleDelete = async (id: number) => {
    try {
      await knowledgeApi.deleteKnowledgeBase(id)
      message.success('知识库已删除')
      setKnowledgeBases((prev) => prev.filter((kb) => kb.id !== id))
    } catch (error) {
      message.error('删除知识库失败')
    }
  }

  const handleUpload = async (file: File) => {
    if (!selectedKB) return

    try {
      await knowledgeApi.uploadDocument(selectedKB.id, file)
      message.success('文档上传成功')
      setUploadModalVisible(false)
      setKnowledgeBases([])
      setNextCursor(null)
      fetchKnowledgeBases(true)
    } catch (error) {
      message.error('文档上传失败')
    }

    return false
  }

  // 知识库类型中文名
  const getKBTypeName = (type: string) => {
    const names: Record<string, string> = {
      local: '本地知识库',
      external: '外部知识库',
    }
    return names[type] || type
  }

  // 状态标签颜色
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      active: 'success',
      inactive: 'default',
      processing: 'processing',
    }
    return colors[status] || 'default'
  }

  // 状态中文名
  const getStatusName = (status: string) => {
    const names: Record<string, string> = {
      active: '正常',
      inactive: '停用',
      processing: '处理中',
    }
    return names[status] || status
  }

  // 表格列定义
  const columns = [
    {
      title: '知识库名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: KnowledgeBaseData) => (
        <Space>
          <DatabaseOutlined />
          <Text strong>{text}</Text>
          <Tag>{getKBTypeName(record.kb_type)}</Tag>
        </Space>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusName(status)}</Tag>
      ),
    },
    {
      title: '文档数量',
      dataIndex: 'document_count',
      key: 'document_count',
      width: 100,
    },
    {
      title: '分段数量',
      dataIndex: 'chunk_count',
      key: 'chunk_count',
      width: 100,
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 250,
      render: (_: any, record: KnowledgeBaseData) => (
        <Space>
          {record.kb_type === 'local' && (
            <Button
              type="link"
              icon={<UploadOutlined />}
              onClick={() => {
                setSelectedKB(record)
                setUploadModalVisible(true)
              }}
            >
              上传
            </Button>
          )}
          <Button
            type="link"
            icon={<FileTextOutlined />}
            onClick={() => navigate(`/knowledge/${record.id}`)}
          >
            文档
          </Button>
          <Popconfirm
            title="确定要删除此知识库吗？"
            description="删除后将无法恢复，关联的文档也将被删除"
            onConfirm={() => handleDelete(record.id)}
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

  return (
    <div>
      <div className="mb-4 flex justify-between">
        <Title level={4} className="m-0">
          知识库
        </Title>
        <Space>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            创建知识库
          </Button>
        </Space>
      </div>

      {/* 知识库列表 */}
      <Card>
        <Table
          columns={columns}
          dataSource={knowledgeBases}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
        {hasMore && (
          <div className="text-center mt-4">
            <Button
              icon={<DownOutlined />}
              loading={loading}
              onClick={() => fetchKnowledgeBases(false)}
            >
              加载更多
            </Button>
          </div>
        )}
      </Card>

      {/* 创建知识库弹窗 */}
      <Modal
        title="创建知识库"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        footer={null}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ kb_type: 'local' }}
        >
          <Form.Item
            name="name"
            label="知识库名称"
            rules={[{ required: true, message: '请输入知识库名称' }]}
          >
            <Input placeholder="请输入知识库名称" />
          </Form.Item>

          <Form.Item
            name="kb_type"
            label="知识库类型"
            rules={[{ required: true, message: '请选择知识库类型' }]}
          >
            <Select>
              <Option value="local">本地知识库</Option>
              <Option value="external">外部知识库</Option>
            </Select>
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={4} placeholder="请输入知识库描述" />
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.kb_type !== currentValues.kb_type
            }
          >
            {({ getFieldValue }) =>
              getFieldValue('kb_type') === 'external' && (
                <>
                  <Form.Item
                    name="api_endpoint"
                    label="API地址"
                    rules={[{ required: true, message: '请输入API地址' }]}
                  >
                    <Input placeholder="请输入知识库API地址" />
                  </Form.Item>

                  <Form.Item
                    name="api_key"
                    label="API Key"
                  >
                    <Input.Password placeholder="请输入API Key（可选）" />
                  </Form.Item>
                </>
              )
            }
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button
                onClick={() => {
                  setCreateModalVisible(false)
                  createForm.resetFields()
                }}
              >
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 上传文档弹窗 */}
      <Modal
        title={`上传文档到 ${selectedKB?.name}`}
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
      >
        <Upload.Dragger
          name="file"
          multiple={false}
          accept=".pdf,.xlsx,.xls,.md,.docx,.html,.txt"
          beforeUpload={handleUpload}
          showUploadList={false}
        >
          <p className="ant-upload-drag-icon">
            <UploadOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">
            支持 PDF、Excel、Markdown、Word、HTML、TXT 格式
          </p>
        </Upload.Dragger>
      </Modal>
    </div>
  )
}

export default Knowledge
