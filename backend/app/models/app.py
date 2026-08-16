from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String, Text, JSON
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class App(Base):
    """
    应用模型 - 支持聊天助手、工作流、Agent三种类型
    """
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    app_type = Column(
        Enum("chatbot", "workflow", "agent", name="app_type_enum"),
        nullable=False,
        default="chatbot"
    )
    icon = Column(String(500), nullable=True)
    status = Column(
        Enum("draft", "published", "disabled", name="app_status_enum"),
        default="draft"
    )

    # 所有者
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 配置信息 (JSON格式存储)
    config = Column(JSON, nullable=True)

    # 版本信息
    version = Column(Integer, default=1)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)

    # 关系
    owner = relationship("User", back_populates="apps")
    conversations = relationship("Conversation", back_populates="app")
    app_knowledge_bases = relationship("AppKnowledgeBase", back_populates="app")

    def __repr__(self):
        return f"<App(id={self.id}, name={self.name}, type={self.app_type})>"


class AppKnowledgeBase(Base):
    """
    应用与知识库的关联表
    """
    __tablename__ = "app_knowledge_bases"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    app = relationship("App", back_populates="app_knowledge_bases")
    knowledge_base = relationship("KnowledgeBase", back_populates="app_knowledge_bases")

    def __repr__(self):
        return f"<AppKnowledgeBase(app_id={self.app_id}, kb_id={self.knowledge_base_id})>"
