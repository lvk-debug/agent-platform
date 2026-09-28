"""
Paper Agent 运行记录

一次「主题检索 + 综述生成」的完整运行对应一条记录。
大文本产物（review.md / papers.bib / trace.jsonl 等）落在文件系统，
这里只存元数据与路径。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PaperAgentRun(Base):
    """Paper Agent 运行记录"""

    __tablename__ = "paper_agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    # 对外暴露的运行标识，对应 outputs 子目录名
    run_id = Column(String, default=_uuid, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    topic = Column(Text, nullable=False)
    # pending / running / completed / failed
    status = Column(String(20), nullable=False, default="pending")

    model_id = Column(Integer, nullable=True)
    model_name = Column(String(255), nullable=True)

    paper_count = Column(Integer, nullable=False, default=0)
    # JSON 字符串：论文数 / 耗时 / 步骤数等
    summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    output_dir = Column(String(500), nullable=True)
    review_path = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<PaperAgentRun(run_id={self.run_id}, status={self.status})>"


class PaperAgentEvalRun(Base):
    """Paper Agent 评测运行记录（里程碑4）"""

    __tablename__ = "paper_agent_eval_runs"

    id = Column(Integer, primary_key=True, index=True)
    eval_id = Column(String, default=_uuid, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    model_id = Column(Integer, nullable=True)
    model_name = Column(String(255), nullable=True)

    # pending / running / completed / failed
    status = Column(String(20), nullable=False, default="pending")
    case_count = Column(Integer, nullable=False, default=0)
    # JSON 字符串：各项指标与分类统计
    summary = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    output_dir = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<PaperAgentEvalRun(eval_id={self.eval_id}, status={self.status})>"
