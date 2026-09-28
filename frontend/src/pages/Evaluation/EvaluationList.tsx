/**
 * 评估任务列表页面
 */

import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card,
  Button,
  Table,
  Tag,
  Space,
  message,
  Typography,
  Popconfirm,
  Tooltip,
  Progress,
  Select,
} from 'antd'
import {
  PlusOutlined,
  PlayCircleOutlined,
  StopOutlined,
  EyeOutlined,
  DeleteOutlined,
  FileTextOutlined,
} from '@ant-design/icons'
import { evaluationsApi, Evaluation } from '@/services/evaluation'

const { Title } = Typography
const { Option } = Select

const EvaluationList: React.FC = () => {
  const navigate = useNavigate()
  const [evaluations, setEvaluations] = useState<Evaluation[]>([])
  const [loading, setLoading] = useState(false)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0,
  })

  useEffect(() => {
    fetchEvaluations()
  }, [pagination.current, statusFilter])

  const fetchEvaluations = async () => {
    setLoading(true)
    try {
      const response = await evaluationsApi.getEvaluations({
        page: pagination.current,
        page_size: pagination.pageSize,
        status: statusFilter,
      })
      setEvaluations(response.data.items)
      setPagination({
        ...pagination,
        total: response.data.total,
      })
    } catch (error) {
      message.error('获取评估任务列表失败')
    } finally {
      setLoading(false)
    }
  }

  const handleStart = async (evalId: number) => {
    try {
      await evaluationsApi.startEvaluation(evalId)
      message.success('评估任务已启动')
      fetchEvaluations()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '启动失败'
      message.error(detail)
    }
  }

  const handleCancel = async (evalId: number) => {
    try {
      await evaluationsApi.cancelEvaluation(evalId)
      message.success('评估任务已取消')
      fetchEvaluations()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '取消失败'
      message.error(detail)
    }
  }

  const handleDelete = async (evalId: number) => {
    try {
      await evaluationsApi.deleteEvaluation(evalId)
      message.success('评估任务已删除')
      fetchEvaluations()
    } catch (error: any) {
      const detail = error?.response?.data?.detail || '删除失败'
      message.error(detail)
    }
  }

  const getStatusTag = (status: string) => {
    const statusMap: Record<string, { color: string; label: string }> = {
      pending: { color: 'default', label: '待执行' },
      running: { color: 'processing', label: '运行中' },
      completed: { color: 'success', label: '已完成' },
      failed: { color: 'error', label: '失败' },
    }
    const config = statusMap[status] || { color: 'default', label: status }
    return <Tag color={config.color}>{config.label}</Tag>
  }

  const columns = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Evaluation) => (
        <a onClick={() => navigate(`/evaluation/tasks/${record.id}`)}>{text}</a>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '进度',
      key: 'progress',
      render: (_: any, record: Evaluation) => (
        <Progress
          percent={record.progress}
          size="small"
          status={record.status === 'failed' ? 'exception' : undefined}
        />
      ),
    },
    {
      title: '测试用例',
      key: 'cases',
      render: (_: any, record: Evaluation) => (
        <span>
          {record.completed_cases}/{record.total_cases}
        </span>
      ),
    },
    {
      title: '成功率',
      key: 'success_rate',
      render: (_: any, record: Evaluation) => {
        if (record.completed_cases === 0) return '-'
        const rate = (record.success_cases / record.completed_cases) * 100
        return (
          <span style={{ color: rate >= 70 ? '#3f8600' : '#cf1322' }}>
            {rate.toFixed(1)}%
          </span>
        )
      },
    },
    {
      title: '总分',
      dataIndex: 'overall_score',
      key: 'overall_score',
      render: (score: number | null) => {
        if (score === null || score === undefined) return '-'
        return (
          <span style={{ color: score >= 70 ? '#3f8600' : '#cf1322' }}>
            {score.toFixed(2)}%
          </span>
        )
      },
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
      render: (_: any, record: Evaluation) => (
        <Space>
          <Tooltip title="查看详情">
            <Button
              type="link"
              icon={<EyeOutlined />}
              onClick={() => navigate(`/evaluation/tasks/${record.id}`)}
            />
          </Tooltip>

          {record.status === 'pending' && (
            <Tooltip title="启动评估">
              <Button
                type="link"
                icon={<PlayCircleOutlined />}
                onClick={() => handleStart(record.id)}
              />
            </Tooltip>
          )}

          {record.status === 'running' && (
            <Tooltip title="取消评估">
              <Button
                type="link"
                danger
                icon={<StopOutlined />}
                onClick={() => handleCancel(record.id)}
              />
            </Tooltip>
          )}

          {record.status === 'completed' && (
            <Tooltip title="查看报告">
              <Button
                type="link"
                icon={<FileTextOutlined />}
                onClick={() => navigate(`/evaluation/tasks/${record.id}/report`)}
              />
            </Tooltip>
          )}

          {record.status !== 'running' && (
            <Popconfirm
              title="确定要删除此评估任务吗？"
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
          <PlayCircleOutlined className="mr-2" />
          评估任务
        </Title>
        <Space>
          <Select
            placeholder="筛选状态"
            allowClear
            style={{ width: 150 }}
            onChange={(value) => setStatusFilter(value)}
          >
            <Option value="pending">待执行</Option>
            <Option value="running">运行中</Option>
            <Option value="completed">已完成</Option>
            <Option value="failed">失败</Option>
          </Select>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/evaluation/tasks/create')}
          >
            创建评估任务
          </Button>
        </Space>
      </div>

      <Card>
        <Table
          columns={columns}
          dataSource={evaluations}
          rowKey="id"
          loading={loading}
          pagination={{
            ...pagination,
            onChange: (page) => setPagination({ ...pagination, current: page }),
          }}
        />
      </Card>
    </div>
  )
}

export default EvaluationList
