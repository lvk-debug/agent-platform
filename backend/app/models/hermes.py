"""
Hermes Agent 数据库模型

六张表（前四张 UUID 主键，后两张自增主键；时间戳统一 UTC）：
- hermes_sessions     会话
- hermes_messages     消息
- hermes_runs         运行记录
- hermes_skills       技能（注入 system 指令）
- hermes_attachments  会话附件（图片走视觉通道 / 文档解析注入）
- hermes_quick_prompts 快捷提示词（内置 + 用户自建）
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class HermesSession(Base):
    """Hermes 会话表"""

    __tablename__ = "hermes_sessions"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), default="新会话")
    model = Column(String(100), default="")  # 会话级模型覆盖（空=全局默认）
    skills = Column(JSON, default=list)  # 会话级选中技能 slug 列表
    tools = Column(JSON, default=list)  # 会话级工具偏好列表
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # 关联
    messages = relationship(
        "HermesMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HermesMessage.created_at",
    )
    runs = relationship(
        "HermesRun",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HermesRun.created_at.desc()",
    )
    attachments = relationship(
        "HermesAttachment",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="HermesAttachment.created_at",
    )


class HermesMessage(Base):
    """Hermes 消息表（每个 SSE event 存一行）"""

    __tablename__ = "hermes_messages"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(
        String, ForeignKey("hermes_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False, default="")
    tools_used = Column(JSON, default=list)  # [{"name": "terminal", "command": "ls"}]
    token_input = Column(Integer, default=0)
    token_output = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    session = relationship("HermesSession", back_populates="messages")
    attachments = relationship(
        "HermesAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="HermesAttachment.created_at",
    )


class HermesRun(Base):
    """Hermes 运行记录表（每次请求产生一条）"""

    __tablename__ = "hermes_runs"

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(
        String, ForeignKey("hermes_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    status = Column(String(20), default="running")  # running / completed / error
    external_run_id = Column(String(100), default="")  # Hermes 上游 run_id，用于 /v1/runs/{id}/stop
    tools_used = Column(JSON, default=list)
    token_input = Column(Integer, default=0)
    token_output = Column(Integer, default=0)
    latency_ms = Column(Float, default=0.0)
    error_message = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    session = relationship("HermesSession", back_populates="runs")


class HermesSkill(Base):
    """Hermes 技能表（平台自建，可 CRUD，选中后作为 system 指令注入对话）"""

    __tablename__ = "hermes_skills"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String(100), nullable=False)  # 技能名称
    slug = Column(String(100), nullable=False, unique=True, index=True)  # 唯一标识
    description = Column(Text, default="")  # 技能描述
    instruction = Column(Text, default="")  # 注入到 system prompt 的指令
    icon = Column(String(20), default="")  # 展示图标（emoji 或 icon key）
    enabled = Column(Boolean, default=True)  # 是否启用
    sort_order = Column(Integer, default=0)  # 排序（升序）
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class HermesAttachment(Base):
    """
    Hermes 会话附件表

    两类用途：
    - image: 转 base64 data URI，按 OpenAI vision 内容格式送入模型
      （Hermes 部署在远端，访问不到本地 uploads，必须内联）
    - document: 解析为文本，以「文件名 + 正文」形式注入上下文

    session_id 非空表示该附件已随消息发送并绑定会话；
    仅上传未发送时 session_id 为空。
    """

    __tablename__ = "hermes_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    session_id = Column(
        String, ForeignKey("hermes_sessions.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    message_id = Column(
        String, ForeignKey("hermes_messages.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )

    # image / document
    kind = Column(String(20), nullable=False)
    filename = Column(String(255), nullable=False)    # 原始文件名（展示用）
    stored_name = Column(String(255), nullable=False)  # UUID 落盘名（防路径穿越）
    file_path = Column(String(500), nullable=False)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=False, default=0)

    # 文档解析：pending / parsed / failed / skipped
    parse_status = Column(String(20), default="pending")
    parsed_text = Column(Text, nullable=True)
    parse_error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)

    session = relationship("HermesSession", back_populates="attachments")
    message = relationship("HermesMessage", back_populates="attachments")

    def __repr__(self):
        return (
            f"<HermesAttachment(id={self.id}, kind={self.kind}, "
            f"filename={self.filename}, status={self.parse_status})>"
        )


class HermesQuickPrompt(Base):
    """
    Hermes 快捷提示词表（日常任务提示词）

    两条来源：
    - 内置（is_builtin=True, owner_id 为空）：平台预置，所有用户可见
    - 自建（owner_id = 用户 ID）：仅本人可见

    icon 存 Ant Design 图标名（如 BulbOutlined），前端按需映射。
    """

    __tablename__ = "hermes_quick_prompts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(100), nullable=False)        # 卡片标题
    description = Column(String(255), nullable=True)   # 卡片副标题
    content = Column(Text, nullable=False)             # 实际注入的提示词
    icon = Column(String(50), nullable=True)           # 图标名
    category = Column(String(50), default="general")   # 分组
    sort_order = Column(Integer, default=0)            # 升序

    is_builtin = Column(Boolean, default=False)        # 内置不可删除
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self):
        return f"<HermesQuickPrompt(id={self.id}, title={self.title})>"
