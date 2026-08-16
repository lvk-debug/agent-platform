from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolBase(BaseModel):
    """
    工具基础Schema
    """
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    tool_type: str = Field(default="builtin", pattern="^(builtin|plugin|mcp)$")


class ToolCreate(ToolBase):
    """
    工具创建Schema
    """
    icon: Optional[str] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None
    endpoint: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None


class ToolUpdate(BaseModel):
    """
    工具更新Schema
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None
    endpoint: Optional[str] = None
    auth_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ToolResponse(ToolBase):
    """
    工具响应Schema
    """
    id: int
    icon: Optional[str] = None
    parameters_schema: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None
    endpoint: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
