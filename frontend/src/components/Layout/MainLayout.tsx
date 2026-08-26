import React, { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import {
  Layout,
  Menu,
  Button,
  Avatar,
  Dropdown,
  Typography,
} from 'antd'
import {
  DashboardOutlined,
  AppstoreOutlined,
  BookOutlined,
  SettingOutlined,
  ToolOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
} from '@ant-design/icons'
import { useAuthStore } from '../../stores/auth'

const { Sider, Content } = Layout
const { Text } = Typography

// 路由配置：hasPadding 控制 Content 是否有上下间距
const routeConfig: Record<string, { hasPadding?: boolean }> = {
  '/dashboard': { hasPadding: true },
  '/apps': { hasPadding: true },
  '/knowledge': { hasPadding: true },
  '/models': { hasPadding: true },
  '/tools': { hasPadding: true },
  // 编排/调试/发布等页面无间距
  '/apps/:appId/chatbot': { hasPadding: false },
  '/apps/:appId/chatbot/debug': { hasPadding: false },
  '/apps/:appId/workflow': { hasPadding: false },
  '/apps/:appId/agent': { hasPadding: false },
  '/apps/:appId/agent/debug': { hasPadding: false },
  '/apps/:appId/publish': { hasPadding: false },
  '/apps/:appId/run': { hasPadding: false },
  '/knowledge/:id': { hasPadding: true },
  '/models/:providerId': { hasPadding: true },
}

// 检查当前路由是否匹配配置（支持动态参数）
const matchRouteConfig = (pathname: string) => {
  // 精确匹配
  if (routeConfig[pathname]) return routeConfig[pathname]
  // 匹配动态路由（如 /apps/123/chatbot -> /apps/:appId/chatbot）
  for (const [pattern, config] of Object.entries(routeConfig)) {
    if (pattern.includes(':')) {
      const regex = new RegExp('^' + pattern.replace(/:[^/]+/g, '[^/]+') + '$')
      if (regex.test(pathname)) return config
    }
  }
  return { hasPadding: true } // 默认有间距
}

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { user, logout } = useAuthStore()

  // 当前路由的配置
  const currentRouteConfig = matchRouteConfig(location.pathname)
  const hasPadding = currentRouteConfig.hasPadding ?? true

  // 侧边栏菜单项
  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/apps',
      icon: <AppstoreOutlined />,
      label: '工作室',
    },
    {
      key: '/knowledge',
      icon: <BookOutlined />,
      label: '知识库',
    },
    {
      key: '/models',
      icon: <SettingOutlined />,
      label: '模型管理',
    },
    {
      key: '/tools',
      icon: <ToolOutlined />,
      label: '工具管理',
    },
  ]

  // 用户下拉菜单
  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人信息',
      onClick: () => navigate('/profile'),
    },
    {
      type: 'divider' as const,
    },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      onClick: () => {
        logout()
        navigate('/login')
      },
    },
  ]

  // 获取当前匹配的顶级菜单路径
  const selectedKey = '/' + location.pathname.split('/').filter(Boolean)[0]

  // 处理菜单点击
  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  return (
    <Layout className="min-h-screen">
      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        className="overflow-hidden h-screen fixed left-0 top-0 bottom-0 bg-white shadow-sider"
      >
        <div className="flex flex-col h-full">
          {/* 顶部 Logo */}
          <div className="h-header flex items-center justify-center border-b border-border flex-shrink-0">
            <Text strong className="text-lg">
              {collapsed ? 'AP' : '智能体平台'}
            </Text>
          </div>

          {/* 中间菜单 */}
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            items={menuItems}
            onClick={handleMenuClick}
            className="border-r-0 flex-1 overflow-auto"
          />

          {/* 底部用户区域 */}
          <div className="border-t border-border flex-shrink-0">
            <Dropdown menu={{ items: userMenuItems }} placement="topRight" trigger={['click']}>
              <div className="flex items-center justify-center gap-2 py-3 cursor-pointer hover:bg-gray-50 transition-colors">
                <Avatar icon={<UserOutlined />} size={collapsed ? 'small' : 'default'} />
                {!collapsed && <Text className="text-sm">{user?.username || '用户'}</Text>}
              </div>
            </Dropdown>
            <div className="flex justify-center pb-2">
              <Button
                type="text"
                icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                onClick={() => setCollapsed(!collapsed)}
                className="w-full h-8"
              />
            </div>
          </div>
        </div>
      </Sider>

      <Layout className={`transition-all duration-200 ${collapsed ? 'ml-20' : 'ml-sider'}`}>
        <Content className={`${hasPadding ? 'py-3 overflow-y-auto' : ''} px-4 bg-page rounded-lg h-screen`}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}

export default MainLayout
