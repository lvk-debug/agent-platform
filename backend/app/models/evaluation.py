"""
评估系统数据模型 (v2)

参考 LangSmith 评估框架，支持：
- Dataset: 测试用例集合
- Evaluator: 评估器（启发式/LLM裁判/自定义）
- Evaluation: 一次评估运行（Experiment）
- EvaluationResult: 单个测试用例的评估结果
- Trace: 执行轨迹记录
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


# ============================================================
# 数据集
# ============================================================


class EvaluationDataset(Base):
    """
    评估数据集

    支持三种类型：
    - bfcl: Berkeley Function Calling Leaderboard
    - gaia: General AI Assistants
    - custom: 自定义数据集
    """

    __tablename__ = "evaluation_datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    dataset_type = Column(
        Enum("bfcl", "gaia", "custom", name="dataset_type_enum"),
        nullable=False,
        default="custom",
    )
    version = Column(String(20), default="1.0")
    total_cases = Column(Integer, default=0)

    # 数据集配置
    metadata_ = Column("metadata", JSON, nullable=True)

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    test_cases = relationship(
        "TestCase", back_populates="dataset", cascade="all, delete-orphan"
    )
    evaluations = relationship("Evaluation", back_populates="dataset")

    def __repr__(self):
        return f"<EvaluationDataset(id={self.id}, name={self.name}, type={self.dataset_type})>"


class TestCase(Base):
    """
    测试用例

    每个测试用例包含：
    - input: 输入（query + context + tools）
    - expected: 期望输出（answer + trajectory）
    - metadata: 标签、难度等元数据
    """

    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(
        Integer, ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False
    )
    case_id = Column(String(100), nullable=False)  # 外部 ID，如 bfcl_simple_001
    category = Column(String(50), nullable=True)  # 测试类别
    difficulty = Column(
        Enum("easy", "medium", "hard", name="difficulty_enum"),
        nullable=True,
        default="medium",
    )

    # 输入
    input_query = Column(Text, nullable=False)
    input_context = Column(JSON, nullable=True)  # 上下文信息
    input_tools = Column(JSON, nullable=True)  # 可用工具定义

    # 期望输出
    expected_answer = Column(Text, nullable=True)  # 期望的最终答案
    expected_trajectory = Column(JSON, nullable=True)  # 期望执行轨迹
    expected_tools = Column(JSON, nullable=True)  # 期望调用的工具列表

    # 元数据
    tags = Column(JSON, nullable=True)  # 标签列表
    metadata_ = Column("metadata", JSON, nullable=True)  # 扩展元数据

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    dataset = relationship("EvaluationDataset", back_populates="test_cases")
    results = relationship("EvaluationResult", back_populates="test_case")

    def __repr__(self):
        return f"<TestCase(id={self.id}, case_id={self.case_id}, category={self.category})>"


# ============================================================
# 评估器
# ============================================================


class Evaluator(Base):
    """
    评估器

    支持四种类型：
    - heuristic: 启发式规则（exact_match, contains, regex, json_match, tool_accuracy）
    - llm_judge: LLM 裁判（使用 LLM 评估回答质量）
    - trajectory: 轨迹评估（评估执行路径）
    - custom: 自定义评估器（用户上传脚本）
    """

    __tablename__ = "evaluators"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    evaluator_type = Column(
        Enum("heuristic", "llm_judge", "trajectory", "custom", name="evaluator_type_enum"),
        nullable=False,
    )

    # 配置
    config = Column(JSON, nullable=True)  # 评估器配置

    # LLM 裁判配置
    judge_model = Column(String(50), nullable=True)  # 裁判模型
    judge_prompt = Column(Text, nullable=True)  # 评分提示词

    # 启发式评估器配置
    metric_type = Column(
        Enum(
            "exact_match",
            "contains",
            "regex",
            "json_match",
            "tool_accuracy",
            "trajectory_match",
            "numeric_match",
            name="metric_type_enum",
        ),
        nullable=True,
    )

    # 自定义评估器
    script_content = Column(Text, nullable=True)  # 用户上传的脚本

    # 状态
    is_builtin = Column(Boolean, default=False)  # 是否内置
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    results = relationship("EvaluationResult", back_populates="evaluator")

    def __repr__(self):
        return f"<Evaluator(id={self.id}, name={self.name}, type={self.evaluator_type})>"


# ============================================================
# 评估任务
# ============================================================


class Evaluation(Base):
    """
    评估任务（Experiment）

    一次评估运行，关联一个应用、一个数据集、多个评估器
    """

    __tablename__ = "evaluations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)

    # 关联
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    dataset_id = Column(Integer, ForeignKey("evaluation_datasets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 配置
    evaluator_ids = Column(JSON, nullable=True)  # 使用的评估器 ID 列表
    config = Column(JSON, nullable=True)  # 评估配置（并发数、超时等）

    # 状态
    status = Column(
        Enum("pending", "running", "completed", "failed", name="eval_status_enum"),
        default="pending",
    )
    progress = Column(Integer, default=0)  # 进度百分比

    # 结果摘要
    total_cases = Column(Integer, default=0)
    completed_cases = Column(Integer, default=0)
    success_cases = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)  # 总体得分

    # 时间
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    app = relationship("App")
    dataset = relationship("EvaluationDataset", back_populates="evaluations")
    user = relationship("User")
    results = relationship(
        "EvaluationResult", back_populates="evaluation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Evaluation(id={self.id}, name={self.name}, status={self.status})>"


# ============================================================
# 评估结果
# ============================================================


class EvaluationResult(Base):
    """
    评估结果

    记录每个测试用例的执行结果，支持多评估器评分
    """

    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(
        Integer, ForeignKey("evaluations.id", ondelete="CASCADE"), nullable=False
    )
    test_case_id = Column(Integer, ForeignKey("test_cases.id"), nullable=False)
    evaluator_id = Column(Integer, ForeignKey("evaluators.id"), nullable=True)

    # 执行结果
    actual_answer = Column(Text, nullable=True)  # 实际答案
    actual_output = Column(JSON, nullable=True)  # 完整输出（含中间步骤）
    actual_trajectory = Column(JSON, nullable=True)  # 实际执行轨迹

    # 评分
    score = Column(Float, nullable=True)  # 得分 (0-1)
    score_details = Column(JSON, nullable=True)  # 各维度得分详情
    passed = Column(Boolean, default=False)  # 是否通过

    # 诊断信息
    execution_time = Column(Integer, nullable=True)  # 执行时间(ms)
    error_message = Column(Text, nullable=True)  # 错误信息
    diagnostics = Column(JSON, nullable=True)  # 详细诊断

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    evaluation = relationship("Evaluation", back_populates="results")
    test_case = relationship("TestCase", back_populates="results")
    evaluator = relationship("Evaluator", back_populates="results")

    def __repr__(self):
        return f"<EvaluationResult(id={self.id}, score={self.score}, passed={self.passed})>"


# ============================================================
# 执行轨迹
# ============================================================


class Trace(Base):
    """
    执行轨迹

    记录应用执行的完整过程，支持：
    - LLM 调用轨迹
    - 工具调用轨迹
    - 工作流节点执行轨迹
    """

    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_result_id = Column(
        Integer, ForeignKey("evaluation_results.id", ondelete="CASCADE"), nullable=True
    )
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    conversation_id = Column(Integer, nullable=True)  # 关联的对话 ID

    # 轨迹信息
    trace_type = Column(
        Enum("agent", "workflow", "chatbot", name="trace_type_enum"),
        nullable=False,
    )
    status = Column(
        Enum("running", "completed", "failed", name="trace_status_enum"),
        default="running",
    )

    # 执行步骤（JSON 数组）
    steps = Column(JSON, nullable=True, default=list)

    # 总结信息
    total_steps = Column(Integer, default=0)
    total_llm_calls = Column(Integer, default=0)
    total_tool_calls = Column(Integer, default=0)
    total_time_ms = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # 输入/输出
    input_query = Column(Text, nullable=True)
    output_answer = Column(Text, nullable=True)

    # 错误信息
    error_message = Column(Text, nullable=True)

    # 时间戳
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Trace(id={self.id}, type={self.trace_type}, status={self.status})>"
