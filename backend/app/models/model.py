from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class ModelProvider(Base):
    """
    模型供应商表
    """
    __tablename__ = "model_providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider_type = Column(
        Enum("openai", "anthropic", "local", "custom", name="provider_type_enum"),
        nullable=False
    )
    api_endpoint = Column(String(500), nullable=True)
    api_key = Column(String(500), nullable=True)
    api_config = Column(JSON, nullable=True)  # 额外配置

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    models = relationship("Model", back_populates="provider")

    def __repr__(self):
        return f"<ModelProvider(id={self.id}, name={self.name}, type={self.provider_type})>"


class Model(Base):
    """
    模型表
    """
    __tablename__ = "models"

    id = Column(Integer, primary_key=True, index=True)
    provider_id = Column(Integer, ForeignKey("model_providers.id"), nullable=False)
    name = Column(String(100), nullable=False)
    model_id = Column(String(100), nullable=False)  # 如 gpt-4, claude-3-opus
    description = Column(Text, nullable=True)

    # 模型能力
    max_tokens = Column(Integer, nullable=True)
    supports_streaming = Column(Boolean, default=True)
    supports_function_calling = Column(Boolean, default=False)

    # 模型参数默认值
    default_temperature = Column(Integer, default=70)  # 0-100, 实际值除以100
    default_max_tokens = Column(Integer, default=4096)

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    provider = relationship("ModelProvider", back_populates="models")

    def __repr__(self):
        return f"<Model(id={self.id}, name={self.name}, model_id={self.model_id})>"
