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
    source_type: str = "file"
    url: Optional[str] = None
    chunk_strategy: Optional[str] = None
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
    search_mode: str = Field(default="rrf", pattern="^(vector|bm25|rrf)$")


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
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None


class SearchResponse(BaseModel):
    """
    检索响应Schema
    """
    query: str
    results: List[SearchResultItem]
    total: int
    search_mode: str


# --- URL 爬取 ---

class CrawlRequest(BaseModel):
    """
    URL 爬取请求Schema
    """
    url: str = Field(..., description="起始 URL")
    max_depth: int = Field(default=3, ge=0, le=30, description="最大爬取深度")
    max_pages: int = Field(default=50, ge=1, le=500, description="最大爬取页面数")


class CrawlResponse(BaseModel):
    """
    URL 爬取响应Schema
    """
    message: str
    total_pages: int
    document_ids: List[int]


# --- 文档分片预览 ---

class ChunkPreviewRequest(BaseModel):
    """
    分片预览请求Schema
    """
    chunk_strategy: str = Field(
        default="sliding_window",
        pattern="^(sliding_window|paragraph)$",
        description="分片策略: sliding_window 或 paragraph"
    )
    chunk_size: int = Field(default=500, ge=100, le=2000, description="分片大小")
    chunk_overlap: int = Field(default=50, ge=0, le=500, description="分片重叠大小")
    separators: Optional[List[str]] = Field(
        default=None,
        description="句子边界分隔符列表，按优先级排序。None 时使用默认值"
    )


class ChunkPreviewItem(BaseModel):
    """
    分片预览项Schema
    """
    content: str
    metadata: Optional[Dict[str, Any]] = None


class ChunkPreviewResponse(BaseModel):
    """
    分片预览响应Schema
    """
    total_chunks: int
    chunks: List[ChunkPreviewItem]


class DocumentProcessRequest(BaseModel):
    """
    文档处理请求Schema
    """
    chunk_strategy: str = Field(
        default="sliding_window",
        pattern="^(sliding_window|paragraph)$",
        description="分片策略: sliding_window 或 paragraph"
    )
    chunk_size: int = Field(default=500, ge=100, le=2000, description="分片大小")
    chunk_overlap: int = Field(default=50, ge=0, le=500, description="分片重叠大小")
    separators: Optional[List[str]] = Field(
        default=None,
        description="句子边界分隔符列表，按优先级排序。None 时使用默认值"
    )
