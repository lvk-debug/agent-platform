import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, Space, App } from 'antd'
import { UserOutlined, LockOutlined } from '@ant-design/icons'
import { useAuthStore } from '../stores/auth'

const { Title, Text } = Typography

interface LoginForm {
  username: string
  password: string
}

const Login: React.FC = () => {
  const navigate = useNavigate()
  const { login, isLoading, error, clearError } = useAuthStore()
  const { message } = App.useApp()

  const onFinish = async (values: LoginForm) => {
    try {
      await login(values.username, values.password)
      message.success('登录成功')
      navigate('/dashboard')
    } catch (error) {
      // 错误已在store中处理
    }
  }

  return (
    <div className="min-h-screen flex justify-center items-center bg-gradient-primary">
      <Card className="w-[400px] rounded-card shadow-card">
        <div className="text-center mb-8">
          <Title level={2} className="mb-2">
            智能体平台
          </Title>
          <Text type="secondary">登录您的账号</Text>
        </div>

        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
          initialValues={{ username: '', password: '' }}
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名或邮箱' }]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名或邮箱"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          {error && (
            <Form.Item>
              <Text type="danger">{error}</Text>
            </Form.Item>
          )}

          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
              className="h-12 rounded-button text-base"
            >
              登录
            </Button>
          </Form.Item>

          <Form.Item className="text-center mb-0">
            <Space>
              <Text type="secondary">还没有账号？</Text>
              <Link to="/register">立即注册</Link>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Login
