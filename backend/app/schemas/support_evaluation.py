"""
客服助手评测 Schema 模型

路由前缀 /api/v1/support
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.support import PageMeta


# ------------------------------------------------------------------
# 人工标注打分
# ------------------------------------------------------------------


class ManualScoreRequest(BaseModel):
    """人工标注打分（四个维度各 0~1，由前端星级 /5 转换后传入）"""

    message_id: int = Field(..., description="被标注的 AI 消息 ID")
    accuracy: float = Field(0.0, ge=0.0, le=1.0)
    helpfulness: float = Field(0.0, ge=0.0, le=1.0)
    safety: float = Field(0.0, ge=0.0, le=1.0)
    fluency: float = Field(0.0, ge=0.0, le=1.0)
    comment: Optional[str] = Field(None, max_length=2000)


class ManualScoreResponse(BaseModel):
    """打分结果确认"""

    ok: bool = True
    message_id: int
    status: str = ""
    manual_overall: Optional[float] = None


# ------------------------------------------------------------------
# 评测记录响应
# ------------------------------------------------------------------


class EvaluationResponse(BaseModel):
    """单条评测记录"""

    id: int
    message_id: int
    session_id: int
    query: Optional[str] = None
    intent: Optional[str] = None
    intent_label: str = ""
    # 自动分：为兼容前端保留 auto_* 字段名，值来自 DeepEval（见 deepeval_*）
    auto_scores: Optional[Dict[str, float]] = None
    auto_overall: Optional[float] = None
    # DeepEval 自动评测原始结果（answer_relevancy/faithfulness/contextual_relevancy/GEval×3）
    deepeval_scores: Optional[Dict[str, float]] = None
    deepeval_overall: Optional[float] = None
    deepeval_reasoning: Optional[str] = None
    manual_scores: Optional[Dict[str, float]] = None
    manual_overall: Optional[float] = None
    annotator_id: Optional[int] = None
    annotator_name: str = ""
    comment: Optional[str] = None
    status: str
    ai_content: str = ""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 待标注队列
# ------------------------------------------------------------------


class EvalQueueItem(BaseModel):
    """待标注队列项"""

    message_id: int
    session_id: int
    query: Optional[str] = None
    ai_preview: str = ""
    intent: Optional[str] = None
    intent_label: str = ""
    auto_overall: Optional[float] = None
    status: str
    created_at: datetime


class EvalQueueResponse(BaseModel):
    """待标注队列"""

    items: List[EvalQueueItem] = Field(default_factory=list)
    meta: PageMeta


# ------------------------------------------------------------------
# 质量看板
# ------------------------------------------------------------------


class QualityTrendPoint(BaseModel):
    """按日趋势"""

    date: str
    count: int = 0
    auto_avg: Optional[float] = None
    manual_avg: Optional[float] = None


class QualityIntentItem(BaseModel):
    """按意图分布"""

    intent: str
    label: str = ""
    count: int = 0
    auto_avg: Optional[float] = None
    manual_avg: Optional[float] = None


class QualityOverview(BaseModel):
    """看板概览指标"""

    total: int = 0
    auto_count: int = 0
    manual_count: int = 0
    pending_count: int = 0
    auto_avg: Optional[float] = None
    manual_avg: Optional[float] = None
    annotated_rate: float = 0.0


class QualitySummaryResponse(BaseModel):
    """质量看板汇总"""

    days: int = 7
    overview: QualityOverview = Field(default_factory=QualityOverview)
    trend: List[QualityTrendPoint] = Field(default_factory=list)
    by_intent: List[QualityIntentItem] = Field(default_factory=list)


# ------------------------------------------------------------------
# 生成知识库文档
# ------------------------------------------------------------------


class GenerateKbDocsResponse(BaseModel):
    """知识库文档生成结果"""

    ok: bool = True
    knowledge_base_id: int
    knowledge_base_name: str = ""
    documents: List[Dict[str, object]] = Field(default_factory=list)
    message: str = ""


# 解决前向引用
EvalQueueResponse.model_rebuild()
