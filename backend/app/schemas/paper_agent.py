"""
Paper Agent Schema 模型
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PaperAgentRunRequest(BaseModel):
    """创建 Paper Agent 运行请求"""

    topic: str = Field(..., min_length=1, max_length=500, description="综述主题")
    model_id: str = Field(..., description="模型 ID（models 表）")
    max_papers: int = Field(10, ge=1, le=50, description="期望论文数量")
    year_from: int | None = Field(None, ge=1900, le=2100, description="起始年份")
    year_to: int | None = Field(None, ge=1900, le=2100, description="截止年份")
    source: str = Field(
        "arxiv",
        description="检索源：arxiv / semantic_scholar / openalex / all（多源融合）",
    )
    with_pdf: bool = Field(True, description="是否解析 PDF 抽取证据（关闭可提速）")


class PaperAgentRunResponse(BaseModel):
    """运行记录响应"""

    id: int
    run_id: str
    topic: str
    status: str
    model_id: int | None = None
    model_name: str | None = None
    paper_count: int = 0
    summary: dict[str, Any] | None = None
    error: str | None = None
    output_dir: str | None = None
    review_path: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("summary", mode="before")
    @classmethod
    def _parse_summary(cls, v: Any) -> Any:
        """数据库以 JSON 字符串存储，响应中还原为对象"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return None
        return v


class PaperAgentRunDetailResponse(PaperAgentRunResponse):
    """运行详情响应（附带综述正文）"""

    review: str | None = None


class PaperAgentRunListResponse(BaseModel):
    """运行记录列表响应"""

    items: list[PaperAgentRunResponse]
    total: int


# ------------------------------------------------------------------
# 评测（里程碑4）
# ------------------------------------------------------------------


class PaperAgentEvalRequest(BaseModel):
    """创建评测运行请求"""

    model_id: str = Field(..., description="模型 ID（models 表 model_id）")
    case_ids: list[str] | None = Field(None, description="指定用例，为空则按类别/全部")
    category: str | None = Field(
        None,
        description="用例类别：topic_search/single_paper/multi_compare/failure/safety",
    )
    with_pdf: bool = Field(False, description="是否解析 PDF（显著增加耗时）")
    eval_backend: str | None = Field(
        None,
        description="评测后端：builtin / deepeval / both，为空时按配置 auto",
    )


class PaperAgentEvalRunResponse(BaseModel):
    """评测运行响应"""

    id: int
    eval_id: str
    status: str
    model_id: int | None = None
    model_name: str | None = None
    case_count: int = 0
    summary: dict[str, Any] | None = None
    error: str | None = None
    output_dir: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator("summary", mode="before")
    @classmethod
    def _parse_summary(cls, v: Any) -> Any:
        """数据库以 JSON 字符串存储，响应中还原为对象"""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return None
        return v


class PaperAgentEvalCaseResponse(BaseModel):
    """评测用例响应"""

    case_id: str
    category: str
    topic: str
    notes: str = ""
