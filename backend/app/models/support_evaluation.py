"""
客服助手评测数据模型

为客服助手的每条 AI 回答留存质量评测：
- 自动评测（auto_*）：复用平台 LLM 裁判思路，对单条 AI 回答按多维度打分。
- 人工标注（manual_*）：坐席/管理员按维度星级打分并写评语。
- 二者结合出质量看板。

与现有 evaluation 模块解耦：此处不把客服注册成 app、不跑「评估任务」，
而是直接对 support_messages 的 AI 回答打分，爆炸半径小、语义贴合客服链路。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    Float,
    Column,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from app.core.database import UTCDateTime, Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# 人工/自动打分维度（一致性用于前端渲染与均值计算）
EVAL_DIMENSIONS = ("accuracy", "helpfulness", "safety", "fluency")

EVAL_DIMENSION_LABELS = {
    "accuracy": "准确性",
    "helpfulness": "帮助性",
    "safety": "安全性",
    "fluency": "流畅性",
}

# 评测状态：pending（仅落库未评）/ auto（已自动评）/ done（人工已标注）
EVAL_STATUS = ("pending", "auto", "done")


class SupportEvaluation(Base):
    """客服 AI 回答评测（按 message_id 唯一）"""

    __tablename__ = "support_evaluations"
    __table_args__ = (
        Index("ix_support_evaluations_session", "session_id"),
        Index("ix_support_evaluations_status", "status"),
        Index("ix_support_evaluations_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联的 AI 消息；唯一：一条 AI 回答只评一次
    message_id = Column(
        Integer,
        ForeignKey("support_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    session_id = Column(Integer, nullable=False, index=True)

    # 提问快照：便于看板/队列直接展示，无需回查客户消息
    query = Column(Text, nullable=True)
    intent = Column(String(30), nullable=True)

    # 自动评测（自研四维度 LLM 裁判，已废弃保留兼容）：各维度 0~1
    auto_scores = Column(JSON, nullable=True)
    auto_overall = Column(Float, nullable=True)
    # 自动评测备注（LLM 裁判理由）
    auto_reasoning = Column(Text, nullable=True)

    # DeepEval 自动评测（当前线上唯一自动裁判）：各指标 0~1
    deepeval_scores = Column(JSON, nullable=True)
    deepeval_overall = Column(Float, nullable=True)
    # DeepEval 自动评测综合备注（各指标理由拼接）
    deepeval_reasoning = Column(Text, nullable=True)

    # 人工标注：各维度 0~1
    manual_scores = Column(JSON, nullable=True)
    manual_overall = Column(Float, nullable=True)
    annotator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    comment = Column(Text, nullable=True)

    status = Column(String(16), nullable=False, default="pending")

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<SupportEvaluation(id={self.id}, message={self.message_id}, "
            f"status={self.status})>"
        )
