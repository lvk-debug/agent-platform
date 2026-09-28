"""
工作助理 - OpenClaw 会话与消息模型
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class OpenClawSession(Base):
    """
    工作助理会话
    """
    __tablename__ = "openclaw_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String(100), default="main")
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联 - 级联删除
    messages = relationship(
        "OpenClawMessage",
        back_populates="session",
        order_by="OpenClawMessage.created_at",
        cascade="all, delete-orphan",
    )
    runs = relationship(
        "OpenClawRun",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<OpenClawSession(id={self.id}, user_id={self.user_id}, agent_id={self.agent_id})>"


class OpenClawMessage(Base):
    """
    工作助理消息

    content 使用 JSON 类型，存储 OpenClaw 原始 content 数组格式：
    [{"type": "output_text", "text": "xxx"}, {"type": "image", "image_url": "xxx"}]
    """
    __tablename__ = "openclaw_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("openclaw_sessions.id"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user / assistant / tool（String 兼容 SQLite/PG）
    content = Column(JSON, nullable=False)     # OpenClaw content 数组格式
    run_id = Column(String(100), nullable=True)
    tool_calls = Column(JSON, nullable=True)       # assistant: [{"id","name","arguments"}]
    tool_call_id = Column(String(100), nullable=True)  # tool: 关联的 tool_call id
    tool_name = Column(String(100), nullable=True)     # tool: 工具名
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    session = relationship("OpenClawSession", back_populates="messages")

    def __repr__(self):
        return f"<OpenClawMessage(id={self.id}, role={self.role}, session_id={self.session_id})>"


class OpenClawRun(Base):
    """
    OpenClaw 任务记录

    runId 由 OpenClaw 远端返回（SSE event:response.created），不是本地生成。
    user_id 冗余存储，权限校验无需 join session 表。
    """
    __tablename__ = "openclaw_runs"

    id = Column(String(100), primary_key=True)  # openclaw runId
    session_id = Column(Integer, ForeignKey("openclaw_sessions.id"), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    status = Column(String(50), default="pending")  # pending / in_progress / completed / cancelled / failed
    error = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关联
    session = relationship("OpenClawSession", back_populates="runs")

    def __repr__(self):
        return f"<OpenClawRun(id={self.id}, status={self.status})>"
