# 智能体平台后端

基于 FastAPI + SQLAlchemy 构建的智能体平台后端服务。

## 功能特性

- 用户认证与授权 (JWT)
- 应用管理 (聊天助手、工作流、Agent)
- 知识库管理 (本地/外部知识库)
- 模型供应商管理
- 工具管理 (内置工具、插件、MCP)
- 工作流执行引擎

## 技术栈

- **框架**: FastAPI
- **数据库**: SQLite (本地开发) / PostgreSQL (生产环境)
- **ORM**: SQLAlchemy 2.0
- **迁移**: Alembic
- **认证**: JWT (python-jose)
- **文档解析**: PyPDF2, python-docx, openpyxl

## 快速开始

### 安装依赖

```bash
# 安装基础依赖
pip install -e ".[dev,sqlite]"

# 或者使用PostgreSQL
pip install -e ".[dev,postgres]"
```

### 启动服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 访问API文档
open http://localhost:8000/docs
```

### 数据库迁移

```bash
# 创建迁移
alembic revision --autogenerate -m "initial"

# 执行迁移
alembic upgrade head
```

## 项目结构

```
backend/
├── app/
│   ├── api/
│   │   ├── endpoints/    # API端点
│   │   └── api.py        # 路由配置
│   ├── core/
│   │   ├── config.py     # 配置文件
│   │   ├── database.py   # 数据库配置
│   │   └── security.py   # 安全配置
│   ├── models/           # 数据模型
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # 业务逻辑
│   ├── utils/            # 工具函数
│   └── main.py           # 应用入口
├── alembic/              # 数据库迁移
├── pyproject.toml        # 项目配置
└── README.md
```

## 环境变量

创建 `.env` 文件:

```env
# 数据库
DATABASE_URL=sqlite:///./agent_platform.db
# DATABASE_URL=postgresql://user:pass@localhost/agent_platform

# 向量存储
VECTOR_STORE=sqlite_vector
# VECTOR_STORE=pgvector

# 安全
SECRET_KEY=your-secret-key-here

# Redis (可选)
REDIS_URL=redis://localhost:6379/0

# 日志
LOG_LEVEL=INFO
```

## API文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
