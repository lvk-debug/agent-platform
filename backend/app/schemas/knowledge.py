from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class KnowledgeBaseBase(BaseModel):
    """
    知识库基础Schema
    """
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    kb_type: str = Field(default="local", pattern="^(local|external)$")


class KnowledgeBaseCreate(KnowledgeBaseBase):
    """
    知识库创建Schema
    """
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_config: Optional[Dict[str, Any]] = None


class KnowledgeBaseUpdate(BaseModel):
    """
    知识库更新Schema
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_config: Optional[Dict[str, Any]] = None


class KnowledgeBaseResponse(KnowledgeBaseBase):
    """
    知识库响应Schema
    """
    id: int
    owner_id: int
    status: str
    document_count: int
    chunk_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentBase(BaseModel):
    """
    文档基础Schema
    """
    name: str


class DocumentResponse(DocumentBase):
    """
    文档响应Schema
    """
    id: int
    knowledge_base_id: int
    file_type: str
    file_size: Optional[int] = None
    status: str
    chunk_count: int
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentSegmentResponse(BaseModel):
    """
    文档分段响应Schema
    """
    id: int
    document_id: int
    content: str
    token_count: Optional[int] = None
    position: int
    metadata_: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """
    检索请求Schema
    """
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class SearchResultItem(BaseModel):
    """
    检索结果项Schema
    """
    segment_id: int
    document_id: int
    document_name: str
    content: str
    score: float
    metadata: Optional[Dict[str, Any]] = None


class SearchResponse(BaseModel):
    """
    检索响应Schema
    """
    query: str
    results: List[SearchResultItem]
    total: int
