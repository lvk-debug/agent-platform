from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorParams(BaseModel):
    """游标分页请求参数"""

    cursor: Optional[int] = Field(None, description="上一页最后一条记录的 ID")
    limit: int = Field(default=20, ge=1, le=100, description="每页数量")


class CursorResponse(BaseModel, Generic[T]):
    """游标分页响应"""

    items: List[T]
    next_cursor: Optional[int] = Field(None, description="下一页游标，null 表示没有更多")
    has_more: bool
