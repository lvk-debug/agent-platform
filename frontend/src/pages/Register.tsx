import React from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Form, Input, Button, Card, Typography, Space, App } from 'antd'
import { UserOutlined, LockOutlined, MailOutlined } from '@ant-design/icons'
import { useAuthStore } from '../stores/auth'

const { Title, Text } = Typography

interface RegisterForm {
  email: string
  username: string
  password: string
  confirmPassword: string
  fullName?: string
}

const Register: React.FC = () => {
  const navigate = useNavigate()
  const { register, isLoading, error, clearError } = useAuthStore()
  const { message } = App.useApp()

  const onFinish = async (values: RegisterForm) => {
    try {
      await register(values.email, values.username, values.password, values.fullName)
      message.success('注册成功，请登录')
      navigate('/login')
    } catch (error) {
      // 错误已在store中处理
    }
  }

  return (
    <div className="min-h-screen flex justify-center items-center bg-gradient-primary">
      <Card className="w-[450px] rounded-card shadow-card">
        <div className="text-center mb-8">
          <Title level={2} className="mb-2">
            智能体平台
          </Title>
          <Text type="secondary">创建新账号</Text>
        </div>

        <Form
          name="register"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input
              prefix={<MailOutlined />}
              placeholder="邮箱"
            />
          </Form.Item>

          <Form.Item
            name="username"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, message: '用户名至少3个字符' },
              { max: 100, message: '用户名最多100个字符' },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="用户名"
            />
          </Form.Item>

          <Form.Item name="fullName">
            <Input
              prefix={<UserOutlined />}
              placeholder="姓名（可选）"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 6, message: '密码至少6个字符' },
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>

          <Form.Item
            name="confirmPassword"
            dependencies={['password']}
            rules={[
              { required: true, message: '请确认密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('password') === value) {
                    return Promise.resolve()
                  }
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="确认密码"
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
              注册
            </Button>
          </Form.Item>

          <Form.Item className="text-center mb-0">
            <Space>
              <Text type="secondary">已有账号？</Text>
              <Link to="/login">立即登录</Link>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default Register
