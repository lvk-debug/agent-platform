from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AppBase(BaseModel):
    """
    应用基础Schema
    """
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    app_type: str = Field(..., pattern="^(chatbot|workflow|agent)$")
    icon: Optional[str] = None


class AppCreate(AppBase):
    """
    应用创建Schema
    """
    config: Optional[Dict[str, Any]] = None


class AppUpdate(BaseModel):
    """
    应用更新Schema
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = Field(None, pattern="^(draft|published|disabled)$")


class AppResponse(AppBase):
    """
    应用响应Schema
    """
    id: int
    owner_id: int
    status: str
    config: Optional[Dict[str, Any]] = None
    version: int
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AppListResponse(BaseModel):
    """
    应用列表响应Schema
    """
    items: List[AppResponse]
    total: int
    page: int
    page_size: int
