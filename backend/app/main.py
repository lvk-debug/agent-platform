from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import engine, Base, SessionLocal
from app.core.seed import seed_data
from app.api.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期：启动时初始化数据库和种子数据
    """
    # 启动时创建表
    Base.metadata.create_all(bind=engine)

    # 初始化默认数据
    db = SessionLocal()
    try:
        seed_data(db)
    finally:
        db.close()

    yield


# 创建FastAPI应用
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    redirect_slashes=False,
)

# 配置CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 包含API路由
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """
    根路径
    """
    return {
        "message": "欢迎使用智能体平台API",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    健康检查
    """
    return {"status": "healthy"}
