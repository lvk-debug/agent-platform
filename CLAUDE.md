# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

智能体平台 (Agent Platform) - 类似 Dify/Coze 的 AI Agent 开发平台，支持聊天助手、工作流、Agent 三种应用类型，集成知识库 RAG 和工具调用能力。

## Tech Stack

**Backend**: Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Pydantic v2 / Alembic
**Frontend**: React 18 / TypeScript / Vite 5 / Ant Design 5 / Zustand / ReactFlow
**Database**: SQLite (开发) / PostgreSQL + pgvector (生产)
**AI**: LangChain / httpx (LLM API 调用)

## Common Commands

### Backend
```bash
cd backend

# Install dependencies
pip install -e ".[dev,sqlite]"      # Development + SQLite support
pip install -e ".[dev,postgres]"    # Development + PostgreSQL support

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Code quality
black app/                          # Format code
ruff check app/                     # Lint
mypy app/                           # Type check
pytest                              # Run tests

# Database migrations
alembic revision --autogenerate -m "description"  # Create migration
alembic upgrade head                               # Apply migrations
```

### Frontend
```bash
cd frontend

# Install dependencies
pnpm install

# Development (auto-proxies /api to localhost:8000)
pnpm dev

# Production build
pnpm build

# Lint
pnpm lint
```

### Docker
```bash
cd docker
docker-compose up -d --build        # Start all services
docker-compose down                  # Stop all services
```

## Architecture

### Backend Structure
```
backend/app/
├── main.py              # FastAPI entry point
├── core/
│   ├── config.py        # Settings (pydantic-settings, loads .env.local > .env)
│   ├── database.py      # SQLAlchemy engine/session
│   └── security.py      # JWT + bcrypt
├── api/endpoints/       # REST API routes (users, apps, knowledge, models, tools)
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response models
├── services/            # Business logic (LLM, Knowledge, Workflow)
└── utils/               # Dependencies injection, logging
```

### Frontend Structure
```
frontend/src/
├── main.tsx             # React entry
├── App.tsx              # Routes with ProtectedRoute
├── pages/               # Page components (Dashboard, Apps, Knowledge, Models, Tools)
├── components/Layout/   # MainLayout (sidebar + header)
├── services/            # Axios API clients (one per domain)
└── stores/              # Zustand state (auth store persisted to localStorage)
```

### Key Design Patterns

1. **三层架构**: API (endpoints) → Services → Models/Schemas，依赖单向
2. **LLM 抽象层**: `services/llm.py` 统一 OpenAI/Anthropic 调用接口
3. **工作流引擎**: `services/workflow.py` 实现 DAG 拓扑排序执行，支持 7 种节点类型
4. **认证链**: OAuth2PasswordBearer → JWT → get_current_user 依赖注入
5. **数据库抽象**: 默认 SQLite 零配置，切换 PostgreSQL 只需改 DATABASE_URL

### Database Models
```
User 1──N App 1──1 Workflow
User 1──N KnowledgeBase 1──N Document 1──N DocumentSegment
App N──N KnowledgeBase (via AppKnowledgeBase)
App N──N Tool (via AppTool)
App 1──N Conversation 1──N Message
ModelProvider 1──N Model
```

## Environment Configuration

- `backend/.env.local` - Local development config (created, not committed)
- `backend/.env.example` - Production config template
- Copy `.env.example` to `.env` and fill in actual values for production

## Development Notes

- 后端启动时自动创建 SQLite 数据库表 (`Base.metadata.create_all()`)
- 前端开发服务器 (port 3000) 自动代理 `/api` 到后端 (port 8000)
- 配置优先级: 环境变量 > `.env.local` > `.env`
- API 统一前缀: `/api/v1`
