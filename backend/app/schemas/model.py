from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ModelProviderBase(BaseModel):
    """
    模型供应商基础Schema
    """
    name: str = Field(..., min_length=1, max_length=100)
    provider_type: str = Field(..., pattern="^(openai|anthropic|local|custom)$")


class ModelProviderCreate(ModelProviderBase):
    """
    模型供应商创建Schema
    """
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_config: Optional[Dict[str, Any]] = None


class ModelProviderUpdate(BaseModel):
    """
    模型供应商更新Schema
    """
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    api_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ModelProviderResponse(ModelProviderBase):
    """
    模型供应商响应Schema
    """
    id: int
    api_endpoint: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelBase(BaseModel):
    """
    模型基础Schema
    """
    name: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class ModelResponse(ModelBase):
    """
    模型响应Schema
    """
    id: int
    provider_id: int
    max_tokens: Optional[int] = None
    supports_streaming: bool
    supports_function_calling: bool
    default_temperature: int
    default_max_tokens: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
