# Ant Design 5 使用规范

本项目使用 Ant Design 5 (antd ^5.12.8)，请遵循以下规范。

## 关键变更和弃用提示

### 1. message/notification/modal 使用方式

**❌ 已弃用（静态方法）：**
```tsx
import { message } from 'antd'

message.success('操作成功')
message.error('操作失败')
```

**✅ 推荐方式（Hooks）：**
```tsx
import { App } from 'antd'

const MyComponent = () => {
  const { message, notification, modal } = App.useApp()

  const handleClick = () => {
    message.success('操作成功')
  }

  return <Button onClick={handleClick}>点击</Button>
}
```

### 2. App 组件包裹

必须使用 `App` 组件包裹应用根组件，才能使用 hooks 方式：

```tsx
import { App, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

const Root = () => (
  <ConfigProvider locale={zhCN}>
    <App>
      <YourApp />
    </App>
  </ConfigProvider>
)
```

### 3. 可见性属性变更

**❌ 已弃用：**
```tsx
<Modal visible={true} />
<Dropdown visible={true} />
<Tooltip visible={true} />
```

**✅ 推荐方式：**
```tsx
<Modal open={true} />
<Dropdown open={true} />
<Tooltip open={true} />
```

### 4. Icon 引入方式

**✅ 正确方式：**
```tsx
import { UserOutlined, LockOutlined } from '@ant-design/icons'
```

### 5. 主题配置

使用 `ConfigProvider` 的 `theme` 属性：

```tsx
import { ConfigProvider } from 'antd'

<ConfigProvider
  theme={{
    token: {
      colorPrimary: '#1677ff',
      borderRadius: 8,
    },
  }}
>
  <App>...</App>
</ConfigProvider>
```

### 6. 表单使用

```tsx
import { Form, Input, Button } from 'antd'

const MyForm = () => {
  const [form] = Form.useForm()

  const onFinish = (values: any) => {
    console.log(values)
  }

  return (
    <Form form={form} onFinish={onFinish}>
      <Form.Item name="username" rules={[{ required: true }]}>
        <Input />
      </Form.Item>
      <Button htmlType="submit">提交</Button>
    </Form>
  )
}
```

## 常用组件导入

```tsx
// 基础组件
import { Button, Input, Select, Form, Table, Modal, Drawer } from 'antd'

// 布局组件
import { Layout, Space, Divider, Grid } from 'antd'

// 数据展示
import { Tag, Badge, Avatar, List, Card, Descriptions } from 'antd'

// 反馈组件
import { App, message, notification, Spin, Alert } from 'antd'

// 图标
import { UserOutlined, SettingOutlined } from '@ant-design/icons'
```

## 注意事项

1. **不要使用** `message.success()` 等静态方法，使用 `App.useApp()` hooks
2. **不要使用** `visible` 属性，使用 `open`
3. **确保** 使用 `App` 组件包裹应用根组件
4. **使用** TypeScript 严格模式，利用 antd 的类型定义
