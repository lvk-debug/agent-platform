/**
 * 评估报告页面
 */

import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Card,
  Row,
  Col,
  Typography,
  Spin,
  message,
  Descriptions,
  Tag,
  Progress,
  Table,
  Button,
  Space,
  Statistic,
  Divider,
  Empty,
} from 'antd'
import {
  ArrowLeftOutlined,
  FileTextOutlined,
  TrophyOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons'
import {
  evaluationsApi,
  EvaluationReport as EvaluationReportType,
  CategoryScore,
} from '@/services/evaluation'

const { Title, Text } = Typography

const EvaluationReport: React.FC = () => {
  const { evalId } = useParams<{ evalId: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState<EvaluationReportType | null>(null)

  useEffect(() => {
    if (evalId) {
      fetchReport(parseInt(evalId))
    }
  }, [evalId])

  const fetchReport = async (id: number) => {
    setLoading(true)
    try {
      const response = await evaluationsApi.getReport(id)
      setReport(response.data)
    } catch (error) {
      message.error('获取评估报告失败')
    } finally {
      setLoading(false)
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

  const getScoreColor = (score: number) => {
    if (score >= 80) return '#3f8600'
    if (score >= 60) return '#d4b106'
    return '#cf1322'
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    )
  }

  if (!report) {
    return <Empty description="评估报告不存在" />
  }

  const evaluatorColumns = [
    {
      title: '评估器',
      dataIndex: 'evaluator_name',
      key: 'evaluator_name',
    },
    {
      title: '平均得分',
      dataIndex: 'avg_score',
      key: 'avg_score',
      render: (score: number) => (
        <span style={{ color: getScoreColor(score * 100) }}>
          {(score * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      title: '通过率',
      dataIndex: 'pass_rate',
      key: 'pass_rate',
      render: (rate: number) => (
        <Progress
          percent={Math.round(rate * 100)}
          size="small"
          status={rate >= 0.7 ? 'success' : rate >= 0.5 ? 'normal' : 'exception'}
        />
      ),
    },
    {
      title: '测试用例数',
      dataIndex: 'total',
      key: 'total',
    },
  ]

  const categoryColumns = [
    {
      title: '测试类别',
      dataIndex: 'category',
      key: 'category',
    },
    {
      title: '平均得分',
      dataIndex: 'score',
      key: 'score',
      render: (score: number) => (
        <span style={{ color: getScoreColor(score * 100) }}>
          {(score * 100).toFixed(2)}%
        </span>
      ),
    },
    {
      title: '通过/总数',
      key: 'accuracy',
      render: (_: any, record: CategoryScore) => (
        <span>
          {record.passed}/{record.total}
        </span>
      ),
    },
    {
      title: '通过率',
      key: 'accuracy_rate',
      render: (_: any, record: CategoryScore) => {
        const rate = record.total > 0 ? (record.passed / record.total) * 100 : 0
        return (
          <Progress
            percent={Math.round(rate)}
            size="small"
            status={rate >= 70 ? 'success' : rate >= 50 ? 'normal' : 'exception'}
          />
        )
      },
    },
  ]

  return (
    <div>
      <div className="flex items-center mb-4">
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/evaluation/tasks')}
          className="mr-2"
        />
        <Title level={3} className="mb-0">
          <FileTextOutlined className="mr-2" />
          评估报告
        </Title>
      </div>

      {/* 概览卡片 */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <Statistic
              title="总体得分"
              value={report.overall_score}
              suffix="%"
              precision={2}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: getScoreColor(report.overall_score) }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="成功率"
              value={
                report.total_cases > 0
                  ? (report.success_cases / report.total_cases) * 100
                  : 0
              }
              suffix="%"
              precision={2}
              prefix={<CheckCircleOutlined />}
              valueStyle={{
                color: getScoreColor(
                  report.total_cases > 0
                    ? (report.success_cases / report.total_cases) * 100
                    : 0
                ),
              }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="测试用例"
              value={report.completed_cases}
              suffix={`/ ${report.total_cases}`}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="耗时"
              value={report.duration || '-'}
              prefix={<ClockCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 基本信息 */}
      <Card className="mb-6">
        <Title level={5}>评估任务信息</Title>
        <Descriptions column={2} bordered>
          <Descriptions.Item label="任务名称">
            {report.evaluation.name}
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            {getStatusTag(report.evaluation.status)}
          </Descriptions.Item>
          <Descriptions.Item label="数据集">{report.dataset_name}</Descriptions.Item>
          <Descriptions.Item label="应用">{report.app_name}</Descriptions.Item>
          <Descriptions.Item label="开始时间">
            {report.evaluation.started_at
              ? new Date(report.evaluation.started_at).toLocaleString()
              : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="完成时间">
            {report.evaluation.completed_at
              ? new Date(report.evaluation.completed_at).toLocaleString()
              : '-'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 评估器得分 */}
      <Card className="mb-6">
        <Title level={5}>评估器得分分析</Title>
        {report.evaluator_scores && report.evaluator_scores.length > 0 ? (
          <Table
            columns={evaluatorColumns}
            dataSource={report.evaluator_scores}
            rowKey="evaluator_id"
            pagination={false}
          />
        ) : (
          <Empty description="暂无评估器得分数据" />
        )}
      </Card>

      {/* 分类得分 */}
      <Card className="mb-6">
        <Title level={5}>分类得分分析</Title>
        {report.category_scores.length > 0 ? (
          <Table
            columns={categoryColumns}
            dataSource={report.category_scores}
            rowKey="category"
            pagination={false}
          />
        ) : (
          <Empty description="暂无分类得分数据" />
        )}
      </Card>

      {/* 错误分析 */}
      <Card className="mb-6">
        <Title level={5}>错误分析</Title>
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="错误总数"
              value={report.error_analysis.total_errors || 0}
              prefix={<CloseCircleOutlined />}
              valueStyle={{ color: '#cf1322' }}
            />
          </Col>
          <Col span={16}>
            <Title level={5}>低分用例</Title>
            {report.error_analysis.low_score_cases?.length > 0 ? (
              <Text>
                共 {report.error_analysis.low_score_cases.length} 个用例得分低于 50%
              </Text>
            ) : (
              <Text type="success">没有低分用例</Text>
            )}
          </Col>
        </Row>

        {report.error_analysis.error_types &&
          Object.keys(report.error_analysis.error_types).length > 0 && (
            <>
              <Divider />
              <Title level={5}>错误类型分布</Title>
              {Object.entries(report.error_analysis.error_types).map(
                ([errorType, count]) => (
                  <div key={errorType} className="mb-2">
                    <Text code>{errorType}</Text>
                    <Text className="ml-2">: {count as number} 次</Text>
                  </div>
                )
              )}
            </>
          )}
      </Card>

      {/* 操作按钮 */}
      <div className="flex justify-end">
        <Space>
          <Button onClick={() => navigate('/evaluation/tasks')}>返回列表</Button>
          <Button
            type="primary"
            onClick={() => navigate(`/evaluation/tasks/${evalId}`)}
          >
            查看详情
          </Button>
        </Space>
      </div>
    </div>
  )
}

export default EvaluationReport
