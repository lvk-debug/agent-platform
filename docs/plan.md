# 智能体平台开发计划

## 项目概述

构建一个企业级智能体平台，支持创建聊天助手、工作流和Agent应用，集成知识库和多种外部工具。

## 技术架构

### 前端技术栈
- **框架**: React 18 + TypeScript
- **UI库**: Ant Design 5.x
- **状态管理**: Zustand
- **路由**: React Router 6
- **构建工具**: Vite
- **图表**: ReactFlow (工作流可视化)
- **代码编辑器**: Monaco Editor

### 后端技术栈
- **框架**: FastAPI (Python 3.11+)
- **数据库**: 生产: PostgreSQL 15 + pgvector (向量数据库) 本地:SQLite 3.40.0 + SQLiteVector
- **缓存**: Redis
- **ORM**: SQLAlchemy 2.0 + Alembic (数据库迁移)
- **任务队列**: Celery + Redis
- **文件存储**: MinIO / 本地存储
- **LLM集成**: LangChain

### 部署架构
- **本地开发**: SQLite + SQLiteVector + 内存缓存
- **生产环境**: Docker + PostgreSQL + pgvector + Redis
- **反向代理**: Nginx
- **监控**: Prometheus + Grafana (可选)

## 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      前端 (React)                           │
├─────────────────────────────────────────────────────────────┤
│                      API Gateway (Nginx)                    │
├─────────────────────────────────────────────────────────────┤
│                    后端服务 (FastAPI)                        │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│ 应用服务  │ 知识库服务│ 模型服务  │ 工具服务  │  工作流引擎    │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│    数据层 (本地: SQLite + SQLiteVector / 生产: PostgreSQL + pgvector)  │
└─────────────────────────────────────────────────────────────┘
```

## 数据库设计

### 数据库策略
- **本地开发**: SQLite 3.40.0 + SQLiteVector (轻量级，无需额外服务)
- **生产环境**: PostgreSQL 15 + pgvector (高性能，支持并发)
- **ORM**: SQLAlchemy 2.0 统一抽象，支持两种数据库
- **迁移**: Alembic 自动处理数据库差异

### 核心表结构

#### 1. 用户与权限
- `users` - 用户表
- `teams` - 团队表
- `team_members` - 团队成员关联表
- `permissions` - 权限表

#### 2. 应用管理
- `apps` - 应用表 (聊天助手/工作流/Agent)
- `app_configs` - 应用配置表
- `app_versions` - 应用版本表
- `conversations` - 对话表
- `messages` - 消息表

#### 3. 知识库
- `knowledge_bases` - 知识库表
- `documents` - 文档表
- `document_segments` - 文档分段表
- `document_chunks` - 向量分块表 (SQLiteVector/pgvector)

#### 4. 模型与工具
- `model_providers` - 模型供应商表
- `models` - 模型表
- `tools` - 工具表
- `tool_configs` - 工具配置表

#### 5. 工作流
- `workflows` - 工作流表
- `workflow_nodes` - 工作流节点表
- `workflow_edges` - 工作流边表
- `workflow_runs` - 工作流运行记录表

### 向量数据库抽象层
```python
# 统一向量存储接口
class VectorStore(ABC):
    @abstractmethod
    async def add_vectors(self, vectors, metadata):
        pass
    
    @abstractmethod
    async def search_vectors(self, query_vector, top_k):
        pass

# SQLiteVector 实现 (本地开发)
class SQLiteVectorStore(VectorStore):
    # 使用 SQLiteVector 扩展
    pass

# pgvector 实现 (生产环境)
class PGVectorStore(VectorStore):
    # 使用 pgvector 扩展
    pass
```

## 功能模块详细设计

### 一、工作室模块

#### 1.1 聊天助手
- **创建流程**:
  1. 选择基础模型
  2. 配置系统提示词
  3. 设置对话参数 (温度、最大token等)
  4. 关联知识库 (可选)
  5. 配置工具 (可选)
  6. 发布应用

- **技术实现**:
  - 前端: 对话界面 + 配置面板
  - 后端: LLM调用链 + 流式响应
  - 存储: 对话历史 + 应用配置

#### 1.2 工作流
- **节点类型**:
  - 开始节点
  - LLM节点
  - 知识库检索节点
  - 条件判断节点
  - 代码执行节点
  - HTTP请求节点
  - 工具调用节点
  - 结束节点

- **技术实现**:
  - 前端: ReactFlow可视化编辑器
  - 后端: DAG执行引擎
  - 存储: 工作流定义 + 执行日志

#### 1.3 Agent
- **核心能力**:
  - 推理规划
  - 自主工具调用
  - 多轮对话
  - 任务分解

- **技术实现**:
  - 前端: Agent配置界面 + 调试工具
  - 后端: ReAct/Plan-and-Execute框架
  - 存储: Agent配置 + 执行轨迹

### 二、知识库模块

#### 2.1 通用知识库
- **数据源支持**:
  - PDF文档
  - Excel表格
  - Markdown文件
  - Word文档
  - HTML页面
  - 网页爬虫

- **处理流程**:
  1. 文件上传/导入
  2. 文本提取 (保留结构)
  3. 智能分段
  4. 向量化 embedding
  5. 存储到向量数据库

- **技术实现**:
  - 向量化: OpenAI Embedding / 本地模型(本地使用from langchain_community.embeddings import FastEmbedEmbeddings导入本地模型实现向量化)
  - 存储: pgvector

  **解析方案**:
  - 原始文件(PDF/DOCX/HTML)
        ↓
    统一转换为 Markdown
            ↓
    Markdown预处理：清理页眉页脚、重复内容、特殊符号
            ↓
    语义分片（按标题切分优于固定字符滑动窗口）
            ↓
    给每个chunk带上metadata：来源文件名、页码、文档类型
            ↓
    embedding入库向量库

    **上传文档**
    知识库上传文档需要增加功能:
    1、第一步:上传后先转为Markdown格式,存入数据库,然后可以在线预览
    2、第二步:基于第一步markdown文件，选择分片策略，然后预览分片效果
    3、第三步:用户确认分片策略后，将文件切片上传到知识库
    分片策略：
    目前默认的是会先转化为结构json格式,然后按结构json的字符滑动窗口切分
    1、按标题切分
    2、按段落切分
    3、按字符切分（固定字符滑动窗口）
  - 
#### 2.2 外部知识库
- **API配置**:
  - 知识库API地址
  - 认证方式 (API Key/OAuth)
  - 请求/响应格式映射

- **技术实现**:
  - 统一知识库接口
  - API网关代理
  - 缓存策略

### 三、应用集成模块

#### 3.1 模型供应商
- **支持供应商**:
  - OpenAI
  - Anthropic (Claude)
  - 本地模型 (Ollama)
  - 阿里云通义千问
  - 百度文心一言
  - 讯飞星火
  - 自定义API

- **配置项**:
  - API Key
  - 模型列表
  - 参数配置
  - 限流策略

#### 3.2 工具
- **工具类型**:
  - 内置工具 (搜索、计算、代码执行)
  - 工具插件 (自定义函数)
  - MCP工具 (Model Context Protocol)

- **技术实现**:
  - 工具注册机制
  - 权限控制
  - 沙箱执行环境

#### 3.3 数据源
- **数据源类型**:
  - 文件存储
  - 数据库连接
  - API接口
  - 消息队列

## 开发阶段规划

### 阶段一: 基础架构 (2-3周)
- [x] 项目初始化
- [ ] 前端项目搭建 (React + Vite + TypeScript)
- [ ] 后端项目搭建 (FastAPI + SQLAlchemy)
- [ ] 数据库设计与迁移
- [ ] 用户认证系统 (JWT)
- [ ] 基础API框架
- [ ] Docker开发环境

### 阶段二: 核心功能 (4-6周)
- [ ] 聊天助手功能
  - 应用创建/编辑/删除
  - 对话界面
  - LLM集成
  - 流式响应
- [ ] 知识库基础功能
  - 文件上传
  - 文档解析
  - 向量化存储
  - 知识库检索
- [ ] 模型供应商管理
  - 供应商配置
  - 模型列表

### 阶段三: 高级功能 (4-6周)
- [ ] 工作流编辑器
  - 可视化编辑
  - 节点配置
  - 执行引擎
- [ ] Agent功能
  - 推理框架
  - 工具调用
  - 任务规划
- [ ] 工具系统
  - 内置工具
  - 插件机制
  - MCP集成

### 阶段四: 完善与优化 (2-4周)
- [ ] 外部知识库集成
- [ ] 高级工作流节点
- [ ] 性能优化
- [ ] 监控与日志
- [ ] 文档编写
- [ ] 部署脚本

## 项目结构

```
agent-platform/
├── frontend/                    # 前端项目
│   ├── src/
│   │   ├── components/         # 通用组件
│   │   ├── pages/             # 页面组件
│   │   ├── services/          # API服务
│   │   ├── stores/            # 状态管理
│   │   ├── utils/             # 工具函数
│   │   └── styles/            # 样式文件
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                     # 后端项目
│   ├── app/
│   │   ├── api/               # API路由
│   │   ├── core/              # 核心配置
│   │   ├── models/            # 数据模型
│   │   ├── services/          # 业务逻辑
│   │   ├── utils/             # 工具函数
│   │   └── main.py            # 应用入口
│   ├── pyproject.toml         # 项目配置与依赖
│   └── alembic/               # 数据库迁移
│
├── docker/                      # Docker配置
│   ├── docker-compose.yml
│   ├── Dockerfile.frontend
│   └── Dockerfile.backend
│
├── docs/                        # 项目文档
├── scripts/                     # 脚本工具
└── README.md
```

### pyproject.toml 配置示例

```toml
[project]
name = "agent-platform-backend"
version = "0.1.0"
description = "智能体平台后端服务"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.25",
    "alembic>=1.13.1",
    "pydantic>=2.5.3",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.6",
    "httpx>=0.26.0",
    "langchain>=0.1.0",
    "langchain-community>=0.0.10",
    "langchain-core>=0.1.10",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.4",
    "pytest-asyncio>=0.23.3",
    "black>=23.12.1",
    "ruff>=0.1.9",
    "mypy>=1.8.0",
]
sqlite = [
    "sqlite-vec>=0.1.0",
    "aiosqlite>=0.19.0",
]
postgres = [
    "psycopg2-binary>=2.9.9",
    "pgvector>=0.2.4",
    "asyncpg>=0.29.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["app"]

[tool.black]
line-length = 88
target-version = ["py311"]

[tool.ruff]
line-length = 88
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP"]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

## 关键技术点

### 1. LLM调用封装
```python
# 后端LLM服务抽象
class LLMService:
    async def chat(self, messages, model, **kwargs):
        # 统一调用接口
        pass
    
    async def stream_chat(self, messages, model, **kwargs):
        # 流式响应
        pass
```

### 2. 工作流执行引擎
```python
# DAG执行引擎
class WorkflowEngine:
    async def execute(self, workflow_id, inputs):
        # 拓扑排序
        # 节点执行
        # 结果传递
        pass
```

### 3. 向量检索
```python
# 知识库检索服务
class KnowledgeService:
    async def search(self, query, knowledge_base_id, top_k=5):
        # 向量相似度检索
        # 混合检索 (向量 + 关键词)
        pass
```

### 4. 工具调用框架
```python
# 工具注册与调用
class ToolRegistry:
    def register(self, tool_name, tool_func):
        pass
    
    async def call(self, tool_name, **kwargs):
        pass
```

## 部署方案

### 本地开发环境 (SQLite)
```bash
# 启动后端
cd backend
pip install -e ".[dev]"  # 使用 pyproject.toml 安装依赖
uvicorn app.main:app --reload

# 启动前端
cd frontend
npm install
npm run dev
```

### 生产环境 (PostgreSQL)
```bash
# 使用Docker Compose部署
docker-compose -f docker/docker-compose.prod.yml up -d

# 或者手动部署
# 1. 配置PostgreSQL数据库
# 2. 配置Redis缓存
# 3. 配置Nginx反向代理
# 4. 启动FastAPI服务
```

### 环境变量配置
```bash
# .env 文件
DATABASE_URL=sqlite:///./agent_platform.db  # 本地开发
# DATABASE_URL=postgresql://user:pass@localhost/agent_platform  # 生产环境

VECTOR_STORE=sqlite_vector  # 本地开发
# VECTOR_STORE=pgvector  # 生产环境

REDIS_URL=redis://localhost:6379/0  # 可选
```

## 下一步行动

1. **立即开始**: 项目初始化与基础架构搭建
2. **第一周**: 完成前后端项目搭建和数据库设计
3. **第二周**: 实现用户认证和基础API
4. **第三周**: 开始聊天助手功能开发

## 风险与挑战

1. **LLM API稳定性**: 需要实现重试机制和降级策略
2. **向量数据库性能**: 大规模知识库的检索优化
3. **工作流复杂性**: DAG执行引擎的可靠性
4. **安全性**: 工具执行的沙箱隔离
5. **成本控制**: LLM调用的成本监控

## 参考资源

- [Dify](https://github.com/langgenius/dify) - 开源LLM应用平台
- [FastGPT](https://github.com/labring/FastGPT) - 知识库问答平台
- [LangChain](https://github.com/langchain-ai/langchain) - LLM应用框架
- [ReactFlow](https://reactflow.dev/) - 工作流可视化库
- [pgvector](https://github.com/pgvector/pgvector) - PostgreSQL向量扩展
- [SQLiteVector](https://github.com/asg017/sqlite-vector) - SQLite向量扩展
- [SQLite](https://www.sqlite.org/) - 轻量级数据库