import os
from typing import List, Union
from pathlib import Path
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # 项目配置
    PROJECT_NAME: str = "智能体平台"
    PROJECT_VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    # 环境配置
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # 安全配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    ALGORITHM: str = "HS256"
    ADMIN_PASSWORD: str = "admin123"  # 默认管理员密码，生产环境请修改

    # 数据库配置
    DATABASE_URL: str = "sqlite:///./agent_platform.db"
    VECTOR_STORE: str = "sqlite_vector"  # sqlite_vector 或 pgvector
    VECTOR_DB_DIR: str = "./data/vectors"  # SQLiteVec 向量数据库目录

    # Qdrant配置
    QDRANT_URL: str = ""
    QDRANT_COLLECTION: str = "agent_platform"  # 统一 collection 名称
    RAG_SCORE_THRESHOLD: float = 0.5  # minimum cosine similarity to keep
    
    # Redis配置 (可选)
    REDIS_URL: str = "redis://localhost:6379/0"

    # CORS配置
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    @validator("BACKEND_CORS_ORIGINS", pre=True)
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # 文件存储配置
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # LLM配置
    OPENAI_API_KEY: str = ""
    OPENAI_API_BASE: str = "https://api.openai.com/v1"
    ANTHROPIC_API_KEY: str = ""
    LOCAL_LLM_BASE_URL: str = "http://localhost:11434"
    TAVILY_API_KEY: str = ""

    # 外部知识库配置 (可选)
    EXTERNAL_KB_API_KEY: str = ""
    EXTERNAL_KB_API_URL: str = ""

    # 向量数据库配置
    VECTOR_DB_NAME: str = "agent_platform"
    EMBEDDING_MODEL: str = ""
    EMBEDDING_SPARSE_MODEL: str = "Qdrant/bm25"  # fastembed 稀疏模型，用于 Qdrant 混合检索
    EMBEDDING_MODEL_PATH: str = ""
    EMBEDDING_DIMENSION: int = 0  # 0 表示自动检测

    # 日志配置
    LOG_LEVEL: str = "INFO"

    model_config = {
        "case_sensitive": True,
        "env_file": (".env.local", ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
