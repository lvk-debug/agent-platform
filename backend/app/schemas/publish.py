from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PublishChannel(str, Enum):
    """发布渠道"""

    API = "api"
    MCP = "mcp"
    EMBED = "embed"
    WECHAT = "wechat"
    H5 = "h5"


class PublishConfigResponse(BaseModel):
    """发布配置响应"""

    channel: PublishChannel
    enabled: bool
    config: Optional[Dict[str, Any]] = None
    # 渠道产出物
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    mcp_config: Optional[Dict[str, Any]] = None
    mcp_command: Optional[str] = None
    embed_code: Optional[str] = None
    embed_url: Optional[str] = None
    wechat_webhook_url: Optional[str] = None
    wechat_guide: Optional[List[Dict[str, str]]] = None
    h5_url: Optional[str] = None
    h5_qr_code: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PublishConfigUpdate(BaseModel):
    """发布配置更新请求"""

    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None


class PublishConfigListResponse(BaseModel):
    """所有渠道配置列表响应"""

    app_id: int
    app_name: str
    configs: List[PublishConfigResponse]
