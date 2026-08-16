# 智能体平台前端

基于 React + TypeScript + Ant Design 构建的智能体平台前端应用。

## 功能特性

- 用户登录/注册
- 仪表盘
- 应用管理 (聊天助手、工作流、Agent)
- 知识库管理
- 模型供应商管理
- 工具管理

## 技术栈

- **框架**: React 18
- **语言**: TypeScript
- **UI库**: Ant Design 5
- **状态管理**: Zustand
- **路由**: React Router 6
- **HTTP客户端**: Axios
- **构建工具**: Vite
- **样式**: Tailwind CSS

## 快速开始

### 安装依赖

```bash
pnpm install
```

### 启动开发服务器

```bash
pnpm dev
```

访问 http://localhost:3000

### 构建生产版本

```bash
pnpm build
```

## 项目结构

```
frontend/
├── src/
│   ├── components/       # 组件
│   │   └── Layout/       # 布局组件
│   ├── pages/            # 页面
│   │   ├── Login.tsx     # 登录页
│   │   ├── Register.tsx  # 注册页
│   │   ├── Dashboard.tsx # 仪表盘
│   │   ├── Apps.tsx      # 应用管理
│   │   ├── Knowledge.tsx # 知识库管理
│   │   ├── Models.tsx    # 模型管理
│   │   └── Tools.tsx     # 工具管理
│   ├── services/         # API服务
│   ├── stores/           # 状态管理
│   ├── utils/            # 工具函数
│   ├── styles/           # 样式
│   ├── App.tsx           # 应用入口
│   └── main.tsx          # 主入口
├── public/               # 静态资源
├── package.json          # 项目配置
├── vite.config.ts        # Vite配置
├── tsconfig.json         # TypeScript配置
└── README.md
```

## 环境变量

创建 `.env` 文件:

```env
# API地址
VITE_API_BASE_URL=/api/v1

# 其他配置
VITE_APP_TITLE=智能体平台
```

## 开发指南

### 添加新页面

1. 在 `src/pages/` 目录创建新页面组件
2. 在 `src/App.tsx` 中添加路由
3. 在 `src/components/Layout/MainLayout.tsx` 中添加菜单项

### 添加新API服务

1. 在 `src/services/` 目录创建新的API服务文件
2. 使用 `api` 实例发送请求
3. 定义TypeScript接口

### 状态管理

使用 Zustand 进行状态管理:

```typescript
import { create } from 'zustand'

interface MyState {
  data: any
  setData: (data: any) => void
}

const useMyStore = create<MyState>((set) => ({
  data: null,
  setData: (data) => set({ data }),
}))
```

## 代码规范

- 使用 ESLint 进行代码检查
- 使用 Prettier 进行代码格式化
- 遵循 TypeScript 严格模式

```bash
# 检查代码
pnpm lint

# 格式化代码
pnpm format
```
