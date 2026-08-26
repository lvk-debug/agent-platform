"""
应用公开 API 端点 - 通过 API Key 认证访问
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Any, Optional

from app.core.database import get_db
from app.models.app import App
from app.models.publish_config import PublishConfig
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.utils.logger import logger

router = APIRouter()


def get_current_app_by_api_key(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> App:
    """
    通过 API Key 认证获取应用
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="缺少 Authorization 头")

    # 提取 Bearer token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Authorization 格式错误，应为 Bearer <api_key>")

    api_key = parts[1]

    # 查找 API Key 对应的发布配置
    config = (
        db.query(PublishConfig)
        .filter(
            PublishConfig.channel == "api",
            PublishConfig.enabled == True,
        )
        .all()
    )

    for pc in config:
        import json
        channel_config = json.loads(pc.config) if pc.config else {}
        if channel_config.get("api_key") == api_key:
            # 找到匹配的应用
            app = db.query(App).filter(App.id == pc.app_id).first()
            if app:
                return app

    raise HTTPException(status_code=401, detail="无效的 API Key")


@router.post("/{app_id}/api/chat", response_model=ChatResponse)
async def app_chat(
    app_id: int,
    request: ChatRequest,
    db: Session = Depends(get_db),
    app: App = Depends(get_current_app_by_api_key),
) -> Any:
    """
    应用聊天接口（通过 API Key 认证）

    支持聊天助手类型应用的对话功能
    """
    # 验证应用 ID 匹配
    if app.id != app_id:
        raise HTTPException(status_code=403, detail="无权访问此应用")

    # 验证应用类型
    if app.app_type not in ["chatbot", "workflow"]:
        raise HTTPException(status_code=400, detail="此应用类型不支持 API 聊天")

    # 使用内部用户（应用所有者）执行
    from app.models.user import User
    owner = db.query(User).filter(User.id == app.owner_id).first()
    if not owner:
        raise HTTPException(status_code=500, detail="应用所有者不存在")

    from app.services.chatbot import get_chatbot_service
    service = get_chatbot_service(db)

    try:
        response = await service.chat(app_id, request, owner)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API 聊天失败: {e}")
        raise HTTPException(status_code=500, detail=f"聊天处理失败: {str(e)}")


@router.post("/{app_id}/api/agent/chat", response_model=AgentChatResponse)
async def app_agent_chat(
    app_id: int,
    request: AgentChatRequest,
    db: Session = Depends(get_db),
    app: App = Depends(get_current_app_by_api_key),
) -> Any:
    """
    Agent 应用聊天接口（通过 API Key 认证）

    支持 Agent 类型应用的对话功能
    """
    # 验证应用 ID 匹配
    if app.id != app_id:
        raise HTTPException(status_code=403, detail="无权访问此应用")

    # 验证应用类型
    if app.app_type != "agent":
        raise HTTPException(status_code=400, detail="此应用不是 Agent 类型")

    # 使用内部用户（应用所有者）执行
    from app.models.user import User
    owner = db.query(User).filter(User.id == app.owner_id).first()
    if not owner:
        raise HTTPException(status_code=500, detail="应用所有者不存在")

    from app.services.agent import get_agent_service
    agent_service = get_agent_service(db)

    try:
        response = await agent_service.chat(
            app_id=app_id,
            request=request,
            user=owner,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"API Agent 聊天失败: {e}")
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {str(e)}")
