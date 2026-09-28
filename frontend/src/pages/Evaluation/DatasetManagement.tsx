/**
 * 数据集管理页面
 */

import React, { useEffect, useState } from 'react'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  Modal,
  Form,
  Input,
  Select,
  message,
  Typography,
  Popconfirm,
  Tooltip,
  Drawer,
  Descriptions,
  Spin,
  Empty,
  InputNumber,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  ImportOutlined,
  EyeOutlined,
  DatabaseOutlined,
} from '@ant-design/icons'
import {
  datasetsApi,
  EvaluationDataset,
  DatasetDetail,
  DatasetImportRequest,
} from '@/services/evaluation'

const { Title, Text } = Typography
const { Option } = Select
const { TextArea } = Input

const DatasetManagement: React.FC = () => {
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)
  const [selectedDataset, setSelectedDataset] = useState<DatasetDetail | null>(null)
  const [createForm] = Form.useForm()
  const [importForm] = Form.useForm()
  const [importing, setImporting] = useState(false)

  useEffect(() => {
    fetchDatasets()
  }, [])

  const fetchDatasets = async () => {
    setLoading(true)
    try {
      const response = await datasetsApi.getDatasets()
      setDatasets(response.data)
    } catch (error) {
      message.error('获取数据集列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await datasetsApi.createDataset(values)
      message.success('数据集创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchDatasets()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '创建失败'
      message.error(detail)
    }
  }

  const handleDelete = async (datasetId: number) => {
    try {
      await datasetsApi.deleteDataset(datasetId)
      message.success('数据集已删除')
      fetchDatasets()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '删除失败'
      message.error(detail)
    }
  }

  const handleViewDetail = async (datasetId: number) => {
    try {
      const response = await datasetsApi.getDataset(datasetId)
      setSelectedDataset(response.data)
      setDetailDrawerVisible(true)
    } catch (error) {
      message.error('获取数据集详情失败')
    }
  }

  const handleImport = async (values: any) => {
    if (!selectedDataset) return

    setImporting(true)
    try {
      const importData: DatasetImportRequest = {
        source: values.source,
        categories: values.categories,
        max_cases: values.max_cases,
      }

      const response = await datasetsApi.importTestCases(selectedDataset.id, importData)
      const result = response.data

      message.success(
        `导入完成：成功 ${result.imported_count} 个，跳过 ${result.skipped_count} 个，失败 ${result.error_count} 个`
      )

      setImportModalVisible(false)
      importForm.resetFields()
      fetchDatasets()

      // 刷新详情
      if (detailDrawerVisible) {
        handleViewDetail(selectedDataset.id)
      }
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '导入失败'
      message.error(detail)
    } finally {
      setImporting(false)
    }
  }

  const getDatasetTypeTag = (type: string) => {
    const typeMap: Record<string, { color: string; label: string }> = {
      bfcl: { color: 'blue', label: 'BFCL' },
      gaia: { color: 'green', label: 'GAIA' },
      custom: { color: 'orange', label: '自定义' },
    }
    const config = typeMap[type] || { color: 'default', label: type }
    return <Tag color={config.color}>{config.label}</Tag>
  }

  const columns = [
    {
      title: '数据集名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: EvaluationDataset) => (
        <a onClick={() => handleViewDetail(record.id)}>{text}</a>
      ),
    },
    {
      title: '类型',
      dataIndex: 'dataset_type',
      key: 'dataset_type',
      render: (type: string) => getDatasetTypeTag(type),
    },
    {
      title: '版本',
      dataIndex: 'version',
      key: 'version',
    },
    {
      title: '测试用例数',
      dataIndex: 'total_cases',
      key: 'total_cases',
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'green' : 'red'}>
          {isActive ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: EvaluationDataset) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => handleViewDetail(record.id)}
            />
          </Tooltip>
          <Tooltip title="导入测试用例">
            <Button
              type="link"
              icon={<ImportOutlined />}
              onClick={() => {
                setSelectedDataset(record as DatasetDetail)
                setImportModalVisible(true)
              }}
            />
          </Tooltip>
          <Popconfirm
            title="确定要删除此数据集吗？"
            description="删除后无法恢复，相关的测试用例也将被删除"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button type="link" danger icon={<DeleteOutlined />} />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={3} className="mb-0">
          <DatabaseOutlined className="mr-2" />
          数据集管理
        </Title>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
        >
          创建数据集
        </Button>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={datasets}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 创建数据集弹窗 */}
      <Modal
        title="创建数据集"
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
        >
          <Form.Item
            name="name"
            label="数据集名称"
            rules={[{ required: true, message: '请输入数据集名称' }]}
          >
            <Input placeholder="请输入数据集名称" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <TextArea rows={3} placeholder="请输入数据集描述" />
          </Form.Item>

          <Form.Item
            name="dataset_type"
            label="数据集类型"
            rules={[{ required: true, message: '请选择数据集类型' }]}
          >
            <Select placeholder="请选择数据集类型">
              <Option value="bfcl">BFCL - 工具调用能力评估</Option>
              <Option value="gaia">GAIA - 通用 AI 助手评估</Option>
              <Option value="custom">自定义数据集</Option>
            </Select>
          </Form.Item>

          <Form.Item name="version" label="版本" initialValue="1.0">
            <Input placeholder="请输入版本号" />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit">
                创建
              </Button>
              <Button onClick={() => setCreateModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 导入测试用例弹窗 */}
      <Modal
        title={`导入测试用例 - ${selectedDataset?.name || ''}`}
        open={importModalVisible}
        onCancel={() => {
          setImportModalVisible(false)
          importForm.resetFields()
        }}
        footer={null}
      >
        <Form
          form={importForm}
          layout="vertical"
          onFinish={handleImport}
          initialValues={{ source: 'builtin' }}
        >
          <Form.Item
            name="source"
            label="数据源"
            rules={[{ required: true, message: '请选择数据源' }]}
          >
            <Select placeholder="请选择数据源">
              <Option value="builtin">内置示例数据</Option>
              <Option value="huggingface">HuggingFace</Option>
            </Select>
          </Form.Item>

          <Form.Item name="categories" label="测试类别（可选）">
            <Select
              mode="multiple"
              placeholder="选择要导入的类别，留空表示全部"
            >
              <Option value="simple">简单函数调用</Option>
              <Option value="multiple">多函数调用</Option>
              <Option value="parallel">并行函数调用</Option>
              <Option value="parallel_multiple">并行多函数调用</Option>
              <Option value="relevance">相关性检测</Option>
            </Select>
          </Form.Item>

          <Form.Item name="max_cases" label="最大导入数量（可选）">
            <InputNumber
              min={1}
              placeholder="留空表示不限制"
              style={{ width: '100%' }}
            />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={importing}>
                开始导入
              </Button>
              <Button onClick={() => setImportModalVisible(false)}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* 数据集详情抽屉 */}
      <Drawer
        title="数据集详情"
        placement="right"
        width={600}
        open={detailDrawerVisible}
        onClose={() => {
          setDetailDrawerVisible(false)
          setSelectedDataset(null)
        }}
      >
        {selectedDataset ? (
          <div>
            <Descriptions column={1} bordered className="mb-4">
              <Descriptions.Item label="名称">{selectedDataset.name}</Descriptions.Item>
              <Descriptions.Item label="类型">
                {getDatasetTypeTag(selectedDataset.dataset_type)}
              </Descriptions.Item>
              <Descriptions.Item label="版本">{selectedDataset.version}</Descriptions.Item>
              <Descriptions.Item label="描述">
                {selectedDataset.description || '无'}
              </Descriptions.Item>
              <Descriptions.Item label="测试用例数">
                {selectedDataset.test_cases_count}
              </Descriptions.Item>
              <Descriptions.Item label="评估任务数">
                {selectedDataset.evaluations_count}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={selectedDataset.is_active ? 'green' : 'red'}>
                  {selectedDataset.is_active ? '启用' : '禁用'}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(selectedDataset.created_at).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>

            <div className="flex justify-end">
              <Button
                type="primary"
                icon={<ImportOutlined />}
                onClick={() => setImportModalVisible(true)}
              >
                导入测试用例
              </Button>
            </div>
          </div>
        ) : (
          <Spin className="flex justify-center" />
        )}
      </Drawer>
    </div>
  )
}

export default DatasetManagement
