/**
 * 分析仪表盘
 */

import React, { useEffect, useState } from 'react'
import {
  Card,
  Row,
  Col,
  Statistic,
  Typography,
  Spin,
  message,
} from 'antd'
import {
  ExperimentOutlined,
  DatabaseOutlined,
  TrophyOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons'
import { analyticsApi, AnalyticsOverview } from '@/services/evaluation'

const { Title } = Typography

const AnalyticsDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true)
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null)

  useEffect(() => {
    fetchOverview()
  }, [])

  const fetchOverview = async () => {
    setLoading(true)
    try {
      const response = await analyticsApi.getOverview()
      setOverview(response.data)
    } catch (error) {
      message.error('获取分析概览失败')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div>
      <Title level={3} className="mb-6">
        评估分析仪表盘
      </Title>

      {/* 统计卡片 */}
      <Row gutter={16} className="mb-6">
        <Col span={6}>
          <Card>
            <Statistic
              title="总评估数"
              value={overview?.total_evaluations || 0}
              prefix={<ExperimentOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="数据集数量"
              value={overview?.total_datasets || 0}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="平均得分"
              value={overview?.avg_score || 0}
              suffix="%"
              precision={2}
              prefix={<TrophyOutlined />}
              valueStyle={{ color: '#3f8600' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="工具调用准确率"
              value={overview?.tool_accuracy || 0}
              suffix="%"
              precision={2}
              prefix={<ThunderboltOutlined />}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 完成率卡片 */}
      <Row gutter={16} className="mb-6">
        <Col span={24}>
          <Card>
            <Row gutter={16}>
              <Col span={8}>
                <Statistic
                  title="评估完成率"
                  value={overview?.completion_rate || 0}
                  suffix="%"
                  precision={2}
                  prefix={<CheckCircleOutlined />}
                />
              </Col>
              <Col span={16}>
                <div className="text-gray-500">
                  <Title level={5}>快速开始</Title>
                  <ul className="list-disc pl-4">
                    <li>创建评估数据集（支持 BFCL、GAIA 或自定义）</li>
                    <li>导入测试用例</li>
                    <li>创建评估任务并关联应用</li>
                    <li>启动评估并查看报告</li>
                  </ul>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      </Row>

      {/* 说明卡片 */}
      <Row gutter={16}>
        <Col span={12}>
          <Card title="BFCL 评估维度">
            <ul className="list-disc pl-4">
              <li><strong>简单函数调用</strong>：单函数调用能力</li>
              <li><strong>多函数调用</strong>：多函数组合调用</li>
              <li><strong>并行函数调用</strong>：独立并行调用</li>
              <li><strong>并行多函数调用</strong>：复杂并行场景</li>
              <li><strong>相关性检测</strong>：判断何时调用函数</li>
            </ul>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="GAIA 评估维度">
            <ul className="list-disc pl-4">
              <li><strong>任务完成率</strong>：任务是否成功完成</li>
              <li><strong>推理准确性</strong>：推理过程是否正确</li>
              <li><strong>工具使用正确性</strong>：工具选择和使用是否正确</li>
              <li><strong>响应质量</strong>：回答的质量和完整性</li>
            </ul>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default AnalyticsDashboard
