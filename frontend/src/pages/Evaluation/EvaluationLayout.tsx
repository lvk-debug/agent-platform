/**
 * 评估模块布局
 */

import React from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography } from 'antd'
import {
  DashboardOutlined,
  DatabaseOutlined,
  PlayCircleOutlined,
  BarChartOutlined,
  SettingOutlined,
} from '@ant-design/icons'

const { Sider, Content } = Layout
const { Title } = Typography

const EvaluationLayout: React.FC = () => {
  const navigate = useNavigate()
  const location = useLocation()

  // 获取当前选中的菜单项
  const getSelectedKey = () => {
    const path = location.pathname
    if (path.includes('/evaluation/datasets')) return 'datasets'
    if (path.includes('/evaluation/evaluators')) return 'evaluators'
    if (path.includes('/evaluation/tasks')) return 'tasks'
    return 'dashboard'
  }

  // 菜单项配置
  const menuItems = [
    {
      key: 'dashboard',
      icon: <DashboardOutlined />,
      label: '分析仪表盘',
      onClick: () => navigate('/evaluation'),
    },
    {
      key: 'datasets',
      icon: <DatabaseOutlined />,
      label: '数据集管理',
      onClick: () => navigate('/evaluation/datasets'),
    },
    {
      key: 'evaluators',
      icon: <SettingOutlined />,
      label: '评估器管理',
      onClick: () => navigate('/evaluation/evaluators'),
    },
    {
      key: 'tasks',
      icon: <PlayCircleOutlined />,
      label: '评估任务',
      onClick: () => navigate('/evaluation/tasks'),
    },
  ]

  return (
    <Layout className="min-h-screen">
      <Sider width={200} className="bg-white shadow-sm">
        <div className="p-4">
          <Title level={4} className="mb-0">
            <BarChartOutlined className="mr-2" />
            评估中心
          </Title>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[getSelectedKey()]}
          items={menuItems}
          className="border-r-0"
        />
      </Sider>
      <Content className="p-6 bg-gray-50">
        <Outlet />
      </Content>
    </Layout>
  )
}

export default EvaluationLayout
