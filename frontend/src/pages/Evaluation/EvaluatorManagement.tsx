/**
 * 评估器管理页面
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
  Descriptions,
  Drawer,
  Spin,
  Empty,
} from 'antd'
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  SettingOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { evaluatorsApi, Evaluator } from '@/services/evaluation'

const { Title, Text } = Typography
const { Option } = Select
const { TextArea } = Input

const EvaluatorManagement: React.FC = () => {
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])
  const [loading, setLoading] = useState(false)
  const [createModalVisible, setCreateModalVisible] = useState(false)
  const [detailDrawerVisible, setDetailDrawerVisible] = useState(false)
  const [selectedEvaluator, setSelectedEvaluator] = useState<Evaluator | null>(null)
  const [createForm] = Form.useForm()

  useEffect(() => {
    fetchEvaluators()
  }, [])

  const fetchEvaluators = async () => {
    setLoading(true)
    try {
      const response = await evaluatorsApi.getEvaluators()
      setEvaluators(response.data.items || [])
    } catch (error) {
      message.error('获取评估器列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (values: any) => {
    try {
      await evaluatorsApi.createEvaluator(values)
      message.success('评估器创建成功')
      setCreateModalVisible(false)
      createForm.resetFields()
      fetchEvaluators()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '创建失败'
      message.error(detail)
    }
  }

  const handleDelete = async (evaluatorId: number) => {
    try {
      await evaluatorsApi.deleteEvaluator(evaluatorId)
      message.success('评估器已删除')
      fetchEvaluators()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '删除失败'
      message.error(detail)
    }
  }

  const handleInitBuiltin = async () => {
    try {
      const response = await evaluatorsApi.initBuiltin()
      message.success(response.data.message)
      fetchEvaluators()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '初始化失败'
      message.error(detail)
    }
  }

  const getEvaluatorTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      heuristic: '启发式规则',
      llm_judge: 'LLM 裁判',
      trajectory: '轨迹评估',
      custom: '自定义',
    }
    return labels[type] || type
  }

  const getEvaluatorTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      heuristic: 'blue',
      llm_judge: 'purple',
      trajectory: 'orange',
      custom: 'green',
    }
    return colors[type] || 'default'
  }

  const getMetricTypeLabel = (metricType: string | null) => {
    if (!metricType) return '-'
    const labels: Record<string, string> = {
      exact_match: '精确匹配',
      contains: '包含匹配',
      regex: '正则匹配',
      json_match: 'JSON 匹配',
      tool_accuracy: '工具准确性',
      numeric_match: '数值匹配',
      trajectory_match: '轨迹匹配',
    }
    return labels[metricType] || metricType
  }

  const columns = [
    {
      title: '评估器名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Evaluator) => (
        <Space>
          <a onClick={() => {
            setSelectedEvaluator(record)
            setDetailDrawerVisible(true)
          }}>
            {text}
          </a>
          {record.is_builtin && <Tag color="blue">内置</Tag>}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'evaluator_type',
      key: 'evaluator_type',
      render: (type: string) => (
        <Tag color={getEvaluatorTypeColor(type)}>{getEvaluatorTypeLabel(type)}</Tag>
      ),
    },
    {
      title: '指标',
      dataIndex: 'metric_type',
      key: 'metric_type',
      render: (metricType: string | null) => getMetricTypeLabel(metricType),
    },
    {
      title: '裁判模型',
      dataIndex: 'judge_model',
      key: 'judge_model',
      render: (model: string | null) => model || '-',
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
      title: '操作',
      key: 'action',
      render: (_: any, record: Evaluator) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => {
                setSelectedEvaluator(record)
                setDetailDrawerVisible(true)
              }}
            />
          </Tooltip>
          {!record.is_builtin && (
            <Popconfirm
              title="确定要删除此评估器吗？"
              onConfirm={() => handleDelete(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Tooltip title="删除">
                <Button type="link" danger icon={<DeleteOutlined />} />
              </Tooltip>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <Title level={3} className="mb-0">
          <SettingOutlined className="mr-2" />
          评估器管理
        </Title>
        <Space>
          <Button
            icon={<ReloadOutlined />}
            onClick={handleInitBuiltin}
          >
            初始化内置评估器
          </Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setCreateModalVisible(true)}
          >
            创建评估器
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={evaluators}
          rowKey="id"
          loading={loading}
          pagination={{ pageSize: 10 }}
        />
      </Card>

      {/* 创建评估器弹窗 */}
      <Modal
        title="创建评估器"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false)
          createForm.resetFields()
        }}
        footer={null}
        width={600}
      >
        <Form
          form={createForm}
          layout="vertical"
          onFinish={handleCreate}
        >
          <Form.Item
            name="name"
            label="评估器名称"
            rules={[{ required: true, message: '请输入评估器名称' }]}
          >
            <Input placeholder="请输入评估器名称" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="请输入评估器描述" />
          </Form.Item>

          <Form.Item
            name="evaluator_type"
            label="评估器类型"
            rules={[{ required: true, message: '请选择评估器类型' }]}
          >
            <Select placeholder="请选择评估器类型">
              <Option value="heuristic">启发式规则</Option>
              <Option value="llm_judge">LLM 裁判</Option>
              <Option value="trajectory">轨迹评估</Option>
              <Option value="custom">自定义</Option>
            </Select>
          </Form.Item>

          <Form.Item
            noStyle
            shouldUpdate={(prevValues, currentValues) =>
              prevValues.evaluator_type !== currentValues.evaluator_type
            }
          >
            {({ getFieldValue }) => {
              const evaluatorType = getFieldValue('evaluator_type')
              if (evaluatorType === 'heuristic') {
                return (
                  <Form.Item
                    name="metric_type"
                    label="指标类型"
                    rules={[{ required: true, message: '请选择指标类型' }]}
                  >
                    <Select placeholder="请选择指标类型">
                      <Option value="exact_match">精确匹配</Option>
                      <Option value="contains">包含匹配</Option>
                      <Option value="regex">正则匹配</Option>
                      <Option value="json_match">JSON 匹配</Option>
                      <Option value="tool_accuracy">工具准确性</Option>
                      <Option value="numeric_match">数值匹配</Option>
                    </Select>
                  </Form.Item>
                )
              }
              if (evaluatorType === 'llm_judge') {
                return (
                  <>
                    <Form.Item
                      name="judge_model"
                      label="裁判模型"
                      initialValue="gpt-3.5-turbo"
                    >
                      <Select placeholder="请选择裁判模型">
                        <Option value="gpt-3.5-turbo">GPT-3.5 Turbo</Option>
                        <Option value="gpt-4">GPT-4</Option>
                        <Option value="gpt-4-turbo">GPT-4 Turbo</Option>
                      </Select>
                    </Form.Item>
                    <Form.Item name="judge_prompt" label="评分提示词">
                      <TextArea rows={4} placeholder="请输入评分提示词，使用 {query}, {expected_answer}, {actual_answer} 作为占位符" />
                    </Form.Item>
                  </>
                )
              }
              return null
            }}
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

      {/* 评估器详情抽屉 */}
      <Drawer
        title="评估器详情"
        placement="right"
        width={500}
        open={detailDrawerVisible}
        onClose={() => {
          setDetailDrawerVisible(false)
          setSelectedEvaluator(null)
        }}
      >
        {selectedEvaluator ? (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="名称">{selectedEvaluator.name}</Descriptions.Item>
            <Descriptions.Item label="类型">
              <Tag color={getEvaluatorTypeColor(selectedEvaluator.evaluator_type)}>
                {getEvaluatorTypeLabel(selectedEvaluator.evaluator_type)}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="描述">
              {selectedEvaluator.description || '无'}
            </Descriptions.Item>
            <Descriptions.Item label="指标类型">
              {getMetricTypeLabel(selectedEvaluator.metric_type)}
            </Descriptions.Item>
            <Descriptions.Item label="裁判模型">
              {selectedEvaluator.judge_model || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="内置评估器">
              {selectedEvaluator.is_builtin ? '是' : '否'}
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={selectedEvaluator.is_active ? 'green' : 'red'}>
                {selectedEvaluator.is_active ? '启用' : '禁用'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedEvaluator.created_at).toLocaleString()}
            </Descriptions.Item>
            {selectedEvaluator.judge_prompt && (
              <Descriptions.Item label="评分提示词">
                <Text code style={{ whiteSpace: 'pre-wrap' }}>
                  {selectedEvaluator.judge_prompt}
                </Text>
              </Descriptions.Item>
            )}
          </Descriptions>
        ) : (
          <Spin className="flex justify-center" />
        )}
      </Drawer>
    </div>
  )
}

export default EvaluatorManagement
