from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Conversation(Base):
    """
    对话模型
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=True)

    # 对话状态
    status = Column(
        Enum("active", "archived", "deleted", name="conversation_status_enum"),
        default="active"
    )

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    app = relationship("App", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")

    def __repr__(self):
        return f"<Conversation(id={self.id}, app_id={self.app_id})>"


class Message(Base):
    """
    消息模型
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(
        Enum("user", "assistant", "system", name="message_role_enum"),
        nullable=False
    )
    content = Column(Text, nullable=False)

    # 消息元数据
    metadata_ = Column("metadata", JSON, nullable=True)

    # LLM相关
    model = Column(String(100), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    latency = Column(Integer, nullable=True)  # 毫秒

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, conversation_id={self.conversation_id})>"
