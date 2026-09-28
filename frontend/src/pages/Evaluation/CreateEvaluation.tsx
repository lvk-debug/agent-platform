/**
 * 创建评估任务页面
 *
 * 步骤：
 * 1. 选择应用和数据集
 * 2. 选择评估器
 * 3. 配置参数
 */

import React, { useState, useEffect } from 'react'
import {
  Card,
  Steps,
  Form,
  Input,
  Select,
  Button,
  message,
  Space,
  Table,
  Tag,
  Checkbox,
  Row,
  Col,
  Statistic,
  Descriptions,
} from 'antd'
import {
  RocketOutlined,
  ExperimentOutlined,
  SettingOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { evaluationsApi, evaluatorsApi, datasetsApi, type Evaluator, type EvaluationDataset } from '@/services'
import { appsApi } from '@/services'

const { Step } = Steps
const { Option } = Select
const { TextArea } = Input

interface App {
  id: number
  name: string
  app_type: string
}

const CreateEvaluation: React.FC = () => {
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [currentStep, setCurrentStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [apps, setApps] = useState<App[]>([])
  const [datasets, setDatasets] = useState<EvaluationDataset[]>([])
  const [evaluators, setEvaluators] = useState<Evaluator[]>([])
  const [selectedEvaluators, setSelectedEvaluators] = useState<number[]>([])

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [appsRes, datasetsRes, evaluatorsRes] = await Promise.all([
        appsApi.getApps(),
        datasetsApi.getDatasets({ is_active: true }),
        evaluatorsApi.getEvaluators({ is_active: true }),
      ])
      setApps(appsRes.data || [])
      setDatasets(datasetsRes.data || [])
      setEvaluators(evaluatorsRes.data?.items || [])
    } catch (error) {
      console.error('Failed to load data:', error)
    }
  }

  const handleNext = async () => {
    try {
      if (currentStep === 0) {
        await form.validateFields(['name', 'app_id', 'dataset_id'])
      } else if (currentStep === 1) {
        if (selectedEvaluators.length === 0) {
          message.warning('请至少选择一个评估器')
          return
        }
      }
      setCurrentStep(currentStep + 1)
    } catch (error) {
      console.error('Validation failed:', error)
    }
  }

  const handlePrev = () => {
    setCurrentStep(currentStep - 1)
  }

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)

      const response = await evaluationsApi.createEvaluation({
        name: values.name,
        description: values.description,
        app_id: Number(values.app_id),
        dataset_id: Number(values.dataset_id),
        evaluator_ids: selectedEvaluators,
        config: {
          max_concurrency: values.max_concurrency || 3,
          timeout: values.timeout || 120,
        },
      })

      message.success('评估任务创建成功')
      navigate(`/evaluation/tasks/${response.data.id}`)
    } catch (error: any) {
      if (error.response?.data?.detail) {
        message.error(error.response.data.detail)
      } else if (error.message) {
        message.error(error.message)
      }
    } finally {
      setLoading(false)
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

  const evaluatorColumns = [
    {
      title: '评估器名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Evaluator) => (
        <Space>
          <span style={{ fontWeight: 500 }}>{text}</span>
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
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
  ]

  const steps = [
    {
      title: '基本信息',
      icon: <ExperimentOutlined />,
    },
    {
      title: '选择评估器',
      icon: <SettingOutlined />,
    },
    {
      title: '确认创建',
      icon: <CheckCircleOutlined />,
    },
  ]

  const selectedDataset = datasets.find(d => d.id === form.getFieldValue('dataset_id'))
  const selectedApp = apps.find(a => a.id === form.getFieldValue('app_id'))
  const selectedEvaluatorDetails = evaluators.filter(e => selectedEvaluators.includes(e.id))

  return (
    <div style={{ padding: 24 }}>
      <Card title="创建评估任务">
        <Steps current={currentStep} items={steps} style={{ marginBottom: 32 }} />

        <Form form={form} layout="vertical">
          {/* Step 1: 基本信息 */}
          <div style={{ display: currentStep === 0 ? 'block' : 'none' }}>
            <Form.Item
              name="name"
              label="评估任务名称"
              rules={[{ required: true, message: '请输入评估任务名称' }]}
            >
              <Input placeholder="请输入评估任务名称" />
            </Form.Item>

            <Form.Item name="description" label="描述">
              <TextArea rows={3} placeholder="请输入评估任务描述" />
            </Form.Item>

            <Form.Item
              name="app_id"
              label="选择应用"
              rules={[{ required: true, message: '请选择要评估的应用' }]}
            >
              <Select placeholder="请选择要评估的应用">
                {apps.map(app => (
                  <Option key={app.id} value={app.id}>
                    {app.name} ({app.app_type})
                  </Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="dataset_id"
              label="选择数据集"
              rules={[{ required: true, message: '请选择数据集' }]}
            >
              <Select placeholder="请选择数据集">
                {datasets.map(dataset => (
                  <Option key={dataset.id} value={dataset.id}>
                    {dataset.name} ({dataset.total_cases} 个测试用例)
                  </Option>
                ))}
              </Select>
            </Form.Item>
          </div>

          {/* Step 2: 选择评估器 */}
          <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
            <div style={{ marginBottom: 16 }}>
              <Space>
                <Button
                  size="small"
                  onClick={() => setSelectedEvaluators(evaluators.map(e => e.id))}
                >
                  全选
                </Button>
                <Button size="small" onClick={() => setSelectedEvaluators([])}>
                  清空
                </Button>
                <span style={{ color: '#999' }}>
                  已选择 {selectedEvaluators.length} 个评估器
                </span>
              </Space>
            </div>

            <Table
              dataSource={evaluators}
              columns={evaluatorColumns}
              rowKey="id"
              pagination={false}
              size="small"
              rowSelection={{
                selectedRowKeys: selectedEvaluators,
                onChange: (keys) => setSelectedEvaluators(keys as number[]),
              }}
            />
          </div>

          {/* Step 3: 确认创建 */}
          <div style={{ display: currentStep === 2 ? 'block' : 'none' }}>
            <Descriptions title="评估任务配置" bordered column={2}>
              <Descriptions.Item label="任务名称">{form.getFieldValue('name')}</Descriptions.Item>
              <Descriptions.Item label="描述">{form.getFieldValue('description') || '-'}</Descriptions.Item>
              <Descriptions.Item label="应用">{selectedApp?.name || '-'}</Descriptions.Item>
              <Descriptions.Item label="数据集">{selectedDataset?.name || '-'}</Descriptions.Item>
              <Descriptions.Item label="测试用例数">{selectedDataset?.total_cases || 0}</Descriptions.Item>
              <Descriptions.Item label="评估器数">{selectedEvaluators.length}</Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <h4>已选评估器：</h4>
              <Space wrap>
                {selectedEvaluatorDetails.map(e => (
                  <Tag key={e.id} color={getEvaluatorTypeColor(e.evaluator_type)}>
                    {e.name}
                  </Tag>
                ))}
              </Space>
            </div>

            <Row gutter={16} style={{ marginTop: 24 }}>
              <Col span={12}>
                <Form.Item name="max_concurrency" label="最大并发数" initialValue={3}>
                  <Select>
                    <Option value={1}>1</Option>
                    <Option value={3}>3</Option>
                    <Option value={5}>5</Option>
                    <Option value={10}>10</Option>
                  </Select>
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item name="timeout" label="超时时间(秒)" initialValue={120}>
                  <Select>
                    <Option value={30}>30秒</Option>
                    <Option value={60}>60秒</Option>
                    <Option value={120}>120秒</Option>
                    <Option value={300}>300秒</Option>
                  </Select>
                </Form.Item>
              </Col>
            </Row>
          </div>
        </Form>

        <div style={{ marginTop: 24, textAlign: 'right' }}>
          <Space>
            {currentStep > 0 && (
              <Button onClick={handlePrev}>上一步</Button>
            )}
            {currentStep < 2 && (
              <Button type="primary" onClick={handleNext}>
                下一步
              </Button>
            )}
            {currentStep === 2 && (
              <Button type="primary" loading={loading} onClick={handleSubmit} icon={<RocketOutlined />}>
                创建并启动评估
              </Button>
            )}
            <Button onClick={() => navigate('/evaluation')}>取消</Button>
          </Space>
        </div>
      </Card>
    </div>
  )
}

export default CreateEvaluation
