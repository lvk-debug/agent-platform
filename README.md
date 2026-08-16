# 智能体平台 (Agent Platform)

一个功能完整的智能体平台，支持创建聊天助手、工作流和Agent应用，集成知识库和多种外部工具。

## 项目概述

本平台旨在提供一个低代码、可视化的智能体开发环境，让用户能够快速构建、部署和管理AI应用。

### 核心功能

#### 🤖 工作室
- **聊天助手**: 简单配置即可构建基于LLM的对话机器人
- **工作流**: 面向单轮自动化任务的编排工作流
- **Agent**: 具备推理与自主工具调用的智能助手

#### 📚 知识库
- **通用知识库**: 支持PDF、Excel、Markdown、Word、HTML格式文本解析
- **外部知识库**: 配置知识库API接入外部数据源

#### 🔌 应用集成
- **模型供应商**: 支持OpenAI、Anthropic、本地模型等多种供应商
- **工具**: 内置工具、工具插件、MCP工具
- **数据源**: 文件存储、数据库连接、API接口等

## 技术架构

### 前端
- React 18 + TypeScript
- Ant Design 5
- Zustand (状态管理)
- ReactFlow (工作流可视化)
- Vite (构建工具)

### 后端
- FastAPI (Python 3.11+)
- SQLAlchemy 2.0 + Alembic
- SQLite + SQLiteVector (本地开发)
- PostgreSQL + pgvector (生产环境)

### 部署
- Docker + Docker Compose
- Nginx (反向代理)
- Redis (缓存，可选)

## 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- pnpm 9+

### 后端启动

```bash
cd backend

# 安装依赖
pip install -e ".[dev,sqlite]"

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API文档: http://localhost:8000/docs

### 前端启动

```bash
cd frontend

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev
```

访问应用: http://localhost:3000

### Docker部署

```bash
# 启动所有服务
docker-compose up -d

# 访问应用
open http://localhost
```

## 项目结构

```
agent-platform/
├── frontend/                # 前端项目
│   ├── src/
│   │   ├── components/     # 组件
│   │   ├── pages/          # 页面
│   │   ├── services/       # API服务
│   │   └── stores/         # 状态管理
│   └── package.json
│
├── backend/                 # 后端项目
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── models/         # 数据模型
│   │   ├── services/       # 业务逻辑
│   │   └── main.py         # 应用入口
│   └── pyproject.toml
│
├── docker/                  # Docker配置
├── docs/                    # 文档
└── README.md
```

## 开发指南

### 添加新功能

1. **后端**: 在 `app/api/endpoints/` 添加API端点
2. **前端**: 在 `src/pages/` 添加页面组件
3. **状态管理**: 在 `src/stores/` 添加状态管理
4. **API服务**: 在 `src/services/` 添加API调用

### 数据库迁移

```bash
cd backend

# 创建迁移
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head
```

### 代码规范

- 后端: 使用 black + ruff 进行代码格式化
- 前端: 使用 ESLint + Prettier 进行代码格式化

## 部署

### 开发环境

```bash
# 后端
cd backend
uvicorn app.main:app --reload

# 前端
cd frontend
pnpm dev
```

### 生产环境

```bash
# 使用Docker Compose
docker-compose -f docker/docker-compose.prod.yml up -d

# 或者手动部署
# 1. 构建前端
cd frontend && pnpm build

# 2. 启动后端
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 配置Nginx
# 参考 docker/nginx.conf
```

## 环境变量

### 后端 (.env)

```env
DATABASE_URL=sqlite:///./agent_platform.db
SECRET_KEY=your-secret-key
LOG_LEVEL=INFO
```

### 前端 (.env)

```env
VITE_API_BASE_URL=/api/v1
```

## 文档

- [API文档](http://localhost:8000/docs) - Swagger UI
- [后端文档](backend/README.md)
- [前端文档](frontend/README.md)

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE)

## 联系方式

- 项目链接: https://github.com/your-username/agent-platform
- 问题反馈: Issues
