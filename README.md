# 智能体平台 (Agent Platform)

一个功能完整的智能体平台，支持创建聊天助手、工作流和Agent应用，集成知识库、多种外部工具，并支持多渠道发布。

## 项目概述

本平台旨在提供一个低代码、可视化的智能体开发环境，让用户能够快速构建、部署和管理AI应用。

### 核心功能

#### 🤖 工作室
- **聊天助手**: 简单配置即可构建基于LLM的对话机器人，支持变量系统、记忆窗口、知识库检索
- **工作流**: 面向单轮自动化任务的可视化编排，支持10种节点类型（开始、结束、LLM、知识检索、条件判断、代码执行、HTTP请求、工具调用、人工介入、问题分类器）
- **Agent**: 具备推理与自主工具调用的智能助手

#### 📚 知识库
- **通用知识库**: 支持PDF、Excel、Markdown、Word、HTML格式文本解析
- **外部知识库**: 配置知识库API接入外部数据源
- **向量检索**: 基于语义相似度的智能检索，支持HyDE假设性文档嵌入和查询扩展

#### 🔌 工具集成
- **内置工具**: 预置10+常用工具模板（搜索、天气、网页抓取、文件处理、数据库、代码执行）
- **MCP工具**: 支持从MCP Server URL自动导入工具
- **工具插件**: 自定义工具接入

#### 🚀 应用发布
支持将应用发布到5个渠道：
| 渠道 | 说明 |
|------|------|
| **API** | 生成API密钥和调用示例 |
| **MCP** | 生成MCP Server配置 |
| **平台嵌入** | 生成iframe嵌入代码 |
| **微信公众号** | Webhook对接指南 |
| **H5** | 生成移动端访问链接 |

#### ⚙️ 模型供应商
支持OpenAI、Anthropic、DeepSeek、本地模型等多种供应商，统一管理API密钥和参数配置。

## 技术架构

### 前端
- React 18 + TypeScript
- Ant Design 5
- Zustand (状态管理)
- ReactFlow (工作流可视化)
- Vite 5 (构建工具)

### 后端
- FastAPI (Python 3.11+)
- SQLAlchemy 2.0 + Pydantic v2
- Alembic (数据库迁移)
- SQLite (本地开发) / PostgreSQL + pgvector (生产环境)

### 部署
- Docker + Docker Compose
- Nginx (反向代理)

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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --reload-exclude "test/"
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
cd docker

# 启动所有服务
docker-compose up -d

# 访问应用
open http://localhost
```

## 项目结构

```
agent-platform/
├── frontend/                    # 前端项目
│   ├── src/
│   │   ├── components/          # 组件
│   │   │   ├── Layout/          # 布局组件
│   │   │   ├── workflow/        # 工作流节点组件
│   │   │   ├── PromptEditor     # 提示词编辑器
│   │   │   ├── VariableSettings # 变量配置
│   │   │   └── ModelSelector    # 模型选择器
│   │   ├── pages/               # 页面
│   │   │   ├── Apps.tsx         # 应用管理
│   │   │   ├── ChatbotOrchestration.tsx  # 聊天助手编排
│   │   │   ├── WorkflowOrchestration.tsx # 工作流编排
│   │   │   ├── PublishManagement.tsx     # 发布管理
│   │   │   ├── Knowledge.tsx    # 知识库管理
│   │   │   ├── Tools.tsx        # 工具管理（含探索工具市场）
│   │   │   └── Models.tsx       # 模型管理
│   │   ├── services/            # API服务
│   │   └── stores/              # 状态管理
│   └── package.json
│
├── backend/                     # 后端项目
│   ├── app/
│   │   ├── api/                 # API路由
│   │   │   └── endpoints/       # 端点实现
│   │   ├── models/              # 数据模型
│   │   ├── schemas/             # Pydantic模型
│   │   ├── services/            # 业务逻辑
│   │   │   ├── llm.py           # LLM调用封装
│   │   │   ├── knowledge.py     # 知识库服务
│   │   │   ├── workflow.py      # 工作流引擎
│   │   │   ├── publish.py       # 发布服务
│   │   │   ├── tool_templates.py # 工具模板
│   │   │   └── mcp_import.py    # MCP导入服务
│   │   └── main.py              # 应用入口
│   └── pyproject.toml
│
├── docker/                      # Docker配置
├── docs/                        # 文档
└── README.md
```

## 功能详解

### 聊天助手编排
- **模型配置**: 选择模型供应商和模型，调整温度、Top-P等参数
- **提示词设置**: 系统提示词编辑，支持变量引用
- **变量系统**: 支持文本、段落、下拉选项、数字、复选框、API变量6种类型
- **知识库集成**: 选择知识库，配置检索参数（Top-K、相似度阈值）
- **检索增强**: HyDE假设性文档嵌入、查询扩展
- **记忆窗口**: 配置对话记忆长度

### 工作流编排
支持10种节点类型的可视化编排：

| 节点类型 | 说明 |
|---------|------|
| 开始节点 | 定义用户输入变量 |
| 结束节点 | 定义输出变量 |
| LLM节点 | 调用大语言模型，支持提示词模板、上下文引用 |
| 知识检索 | 从知识库检索相关文档 |
| 条件判断 | IF/ELIF/ELSE条件分支 |
| 代码执行 | Python代码执行 |
| HTTP请求 | 调用外部API |
| 工具调用 | 调用已安装的工具 |
| 人工介入 | 暂停流程等待人工审批 |
| 问题分类器 | 基于LLM的问题分类 |

### 工具管理
- **工具库**: 查看和管理已安装的工具
- **探索工具市场**: 浏览预置工具模板，一键安装
- **MCP导入**: 输入MCP Server URL自动导入工具

### 应用发布
每个渠道支持独立配置和启停：
- 启用渠道时自动生成所需配置（API密钥、MCP配置、嵌入代码等）
- 支持随时禁用渠道，配置保留

## 环境变量

### 后端 (.env.local 或 .env)

```env
# 数据库
DATABASE_URL=sqlite:///./agent_platform.db

# 安全
SECRET_KEY=your-secret-key

# 日志
LOG_LEVEL=INFO

# LLM API Keys (按需配置)
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
```

### 前端

```env
VITE_API_BASE_URL=/api/v1
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

- 后端: black + ruff
- 前端: ESLint + Prettier

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

## 许可证

MIT License - 详见 [LICENSE](LICENSE)
