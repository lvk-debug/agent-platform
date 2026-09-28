"""
评估系统 Pydantic Schema (v2)

参考 LangSmith 评估框架，支持：
- Dataset: 测试用例集合
- Evaluator: 评估器
- Evaluation: 评估任务（Experiment）
- Trace: 执行轨迹
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# 评估数据集 Schema
# ============================================================


class DatasetCreate(BaseModel):
    """创建数据集请求"""

    name: str = Field(..., min_length=1, max_length=100, description="数据集名称")
    description: Optional[str] = Field(None, description="数据集描述")
    dataset_type: str = Field(
        "custom",
        pattern="^(bfcl|gaia|custom)$",
        description="数据集类型: bfcl, gaia, custom",
    )
    version: str = Field("1.0", description="数据集版本")
    metadata: Optional[Dict[str, Any]] = Field(None, description="数据集元数据")


class DatasetUpdate(BaseModel):
    """更新数据集请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DatasetResponse(BaseModel):
    """数据集响应"""

    id: int
    name: str
    description: Optional[str]
    dataset_type: str
    version: str
    total_cases: int
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class DatasetDetailResponse(DatasetResponse):
    """数据集详情响应（包含测试用例统计）"""

    test_cases_count: int = 0
    evaluations_count: int = 0


# ============================================================
# 测试用例 Schema
# ============================================================


class TestCaseCreate(BaseModel):
    """创建测试用例请求"""

    case_id: str = Field(..., max_length=100, description="外部用例 ID")
    category: Optional[str] = Field(None, max_length=50, description="测试类别")
    difficulty: Optional[str] = Field(
        "medium", pattern="^(easy|medium|hard)$", description="难度级别"
    )
    input_query: str = Field(..., description="输入查询")
    input_context: Optional[Dict[str, Any]] = Field(None, description="上下文信息")
    input_tools: Optional[List[Dict[str, Any]]] = Field(None, description="可用工具定义")
    expected_answer: Optional[str] = Field(None, description="期望的最终答案")
    expected_trajectory: Optional[List[Dict[str, Any]]] = Field(
        None, description="期望执行轨迹"
    )
    expected_tools: Optional[List[str]] = Field(None, description="期望调用的工具")
    tags: Optional[List[str]] = Field(None, description="标签列表")
    metadata: Optional[Dict[str, Any]] = Field(None, description="扩展元数据")


class TestCaseResponse(BaseModel):
    """测试用例响应"""

    id: int
    dataset_id: int
    case_id: str
    category: Optional[str]
    difficulty: Optional[str]
    input_query: str
    input_context: Optional[Dict[str, Any]]
    input_tools: Optional[List[Dict[str, Any]]]
    expected_answer: Optional[str]
    expected_trajectory: Optional[List[Dict[str, Any]]]
    expected_tools: Optional[List[str]]
    tags: Optional[List[str]]
    metadata: Optional[Dict[str, Any]] = Field(None, alias="metadata_")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class TestCaseListResponse(BaseModel):
    """测试用例列表响应"""

    items: List[TestCaseResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# 评估器 Schema
# ============================================================


class EvaluatorCreate(BaseModel):
    """创建评估器请求"""

    name: str = Field(..., min_length=1, max_length=100, description="评估器名称")
    description: Optional[str] = Field(None, description="评估器描述")
    evaluator_type: str = Field(
        ...,
        pattern="^(heuristic|llm_judge|trajectory|custom)$",
        description="评估器类型",
    )
    config: Optional[Dict[str, Any]] = Field(None, description="评估器配置")

    # LLM 裁判配置
    judge_model: Optional[str] = Field(None, description="裁判模型名称")
    judge_prompt: Optional[str] = Field(None, description="评分提示词")

    # 启发式评估器配置
    metric_type: Optional[str] = Field(
        None,
        pattern="^(exact_match|contains|regex|json_match|tool_accuracy|trajectory_match|numeric_match)$",
        description="指标类型",
    )

    # 自定义评估器
    script_content: Optional[str] = Field(None, description="自定义脚本内容")


class EvaluatorUpdate(BaseModel):
    """更新评估器请求"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    judge_model: Optional[str] = None
    judge_prompt: Optional[str] = None
    is_active: Optional[bool] = None


class EvaluatorResponse(BaseModel):
    """评估器响应"""

    id: int
    name: str
    description: Optional[str]
    evaluator_type: str
    config: Optional[Dict[str, Any]]
    judge_model: Optional[str]
    judge_prompt: Optional[str]
    metric_type: Optional[str]
    is_builtin: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluatorListResponse(BaseModel):
    """评估器列表响应"""

    items: List[EvaluatorResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# 评估任务 Schema
# ============================================================


class EvaluationCreate(BaseModel):
    """创建评估任务请求"""

    name: str = Field(..., min_length=1, max_length=100, description="评估任务名称")
    description: Optional[str] = Field(None, description="评估任务描述")
    app_id: int = Field(..., description="关联的应用 ID")
    dataset_id: int = Field(..., description="关联的数据集 ID")
    evaluator_ids: List[int] = Field(..., min_length=1, description="使用的评估器 ID 列表")
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="评估配置，如 max_concurrency, timeout 等",
    )


class EvaluationResponse(BaseModel):
    """评估任务响应"""

    id: int
    name: str
    description: Optional[str]
    app_id: int
    dataset_id: int
    user_id: int
    evaluator_ids: Optional[List[int]]
    config: Optional[Dict[str, Any]]
    status: str
    progress: int
    total_cases: int
    completed_cases: int
    success_cases: int
    overall_score: Optional[float]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationDetailResponse(EvaluationResponse):
    """评估任务详情响应"""

    dataset_name: Optional[str] = None
    app_name: Optional[str] = None
    evaluators: Optional[List[EvaluatorResponse]] = None
    results_summary: Optional[Dict[str, Any]] = None


class EvaluationListResponse(BaseModel):
    """评估任务列表响应"""

    items: List[EvaluationResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# 评估结果 Schema
# ============================================================


class EvaluationResultResponse(BaseModel):
    """评估结果响应"""

    id: int
    evaluation_id: int
    test_case_id: int
    evaluator_id: Optional[int]
    actual_answer: Optional[str]
    actual_output: Optional[Dict[str, Any]]
    actual_trajectory: Optional[List[Dict[str, Any]]]
    score: Optional[float]
    score_details: Optional[Dict[str, Any]]
    passed: bool
    execution_time: Optional[int]
    error_message: Optional[str]
    diagnostics: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class EvaluationResultDetailResponse(EvaluationResultResponse):
    """评估结果详情响应（包含测试用例和轨迹信息）"""

    test_case: Optional[TestCaseResponse] = None
    evaluator: Optional[EvaluatorResponse] = None


class EvaluationResultListResponse(BaseModel):
    """评估结果列表响应"""

    items: List[EvaluationResultResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# 执行轨迹 Schema
# ============================================================


class TraceStep(BaseModel):
    """轨迹步骤"""

    step_type: str = Field(..., description="步骤类型: llm_call, tool_call, workflow_node, condition")
    name: str = Field(..., description="步骤名称")
    input_data: Optional[Dict[str, Any]] = Field(None, description="输入数据")
    output_data: Optional[Dict[str, Any]] = Field(None, description="输出数据")
    duration_ms: Optional[int] = Field(None, description="执行时长(ms)")
    tokens: Optional[int] = Field(None, description="Token 使用量")
    status: str = Field("success", description="状态: success, error")
    error: Optional[str] = Field(None, description="错误信息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


class TraceCreate(BaseModel):
    """创建轨迹请求"""

    evaluation_result_id: Optional[int] = Field(None, description="关联的评估结果 ID")
    app_id: int = Field(..., description="关联的应用 ID")
    conversation_id: Optional[int] = Field(None, description="关联的对话 ID")
    trace_type: str = Field(
        ...,
        pattern="^(agent|workflow|chatbot)$",
        description="轨迹类型",
    )
    input_query: Optional[str] = Field(None, description="输入查询")


class TraceResponse(BaseModel):
    """轨迹响应"""

    id: int
    evaluation_result_id: Optional[int]
    app_id: int
    conversation_id: Optional[int]
    trace_type: str
    status: str
    steps: Optional[List[Dict[str, Any]]]
    total_steps: int
    total_llm_calls: int
    total_tool_calls: int
    total_time_ms: int
    total_tokens: int
    input_query: Optional[str]
    output_answer: Optional[str]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class TraceListResponse(BaseModel):
    """轨迹列表响应"""

    items: List[TraceResponse]
    total: int
    page: int
    page_size: int


# ============================================================
# 分析统计 Schema
# ============================================================


class AnalyticsOverview(BaseModel):
    """分析概览"""

    total_evaluations: int = 0
    total_datasets: int = 0
    total_evaluators: int = 0
    avg_score: float = 0.0
    tool_accuracy: float = 0.0
    completion_rate: float = 0.0


class DimensionScore(BaseModel):
    """维度得分"""

    dimension: str
    score: float
    count: int


class CategoryScore(BaseModel):
    """分类得分"""

    category: str
    score: float
    total: int
    passed: int


class EvaluationReport(BaseModel):
    """评估报告"""

    evaluation: EvaluationResponse
    dataset_name: str
    app_name: str
    total_cases: int
    completed_cases: int
    success_cases: int
    overall_score: float
    duration: Optional[str] = None
    evaluator_scores: List[Dict[str, Any]] = []
    dimension_scores: List[DimensionScore] = []
    category_scores: List[CategoryScore] = []
    error_analysis: Dict[str, Any] = {}


class ComparisonResult(BaseModel):
    """对比分析结果"""

    evaluations: List[EvaluationResponse]
    evaluator_comparison: List[Dict[str, Any]]
    dimension_comparison: List[Dict[str, Any]]
    category_comparison: List[Dict[str, Any]]
    summary: Dict[str, Any] = {}


# ============================================================
# 数据集导入 Schema
# ============================================================


class DatasetImportRequest(BaseModel):
    """数据集导入请求"""

    source: str = Field(
        "builtin",
        pattern="^(builtin|huggingface|custom)$",
        description="数据源: builtin, huggingface, custom",
    )
    categories: Optional[List[str]] = Field(None, description="要导入的类别")
    max_cases: Optional[int] = Field(None, ge=1, description="最大导入数量")


class DatasetImportResponse(BaseModel):
    """数据集导入响应"""

    dataset_id: int
    imported_count: int
    skipped_count: int
    error_count: int
    message: str
