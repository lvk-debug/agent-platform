from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, JSON, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class Workflow(Base):
    """
    工作流表
    """
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False, unique=True)

    # 工作流配置
    graph = Column(JSON, nullable=False)  # 存储整个图结构
    nodes_config = Column(JSON, nullable=True)  # 节点配置详情

    # 版本
    version = Column(Integer, default=1)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    app = relationship("App")
    runs = relationship("WorkflowRun", back_populates="workflow")

    def __repr__(self):
        return f"<Workflow(id={self.id}, app_id={self.app_id})>"


class WorkflowRun(Base):
    """
    工作流运行记录表
    """
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=True)

    # 运行状态
    status = Column(
        Enum("pending", "running", "completed", "failed", name="run_status_enum"),
        default="pending"
    )

    # 输入输出
    inputs = Column(JSON, nullable=True)
    outputs = Column(JSON, nullable=True)

    # 执行详情
    node_runs = Column(JSON, nullable=True)  # 每个节点的执行结果
    error_message = Column(Text, nullable=True)

    # 性能指标
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # 毫秒

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    workflow = relationship("Workflow", back_populates="runs")
    conversation = relationship("Conversation")

    def __repr__(self):
        return f"<WorkflowRun(id={self.id}, status={self.status})>"
