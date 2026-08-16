"""
聊天助手 API 端点
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.chatbot import (
    ChatRequest,
    ChatResponse,
    ChatbotConfig,
    ChatbotUpdate,
    ConversationResponse,
    MessageResponse,
)
from app.services.chatbot import get_chatbot_service
from app.utils.deps import get_current_user

router = APIRouter()


@router.get("/{app_id}/config", response_model=ChatbotConfig)
def get_chatbot_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """
    获取聊天助手配置
    """
    from app.models.app import App

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    service = get_chatbot_service(db)
    config = service.get_chatbot_config(app_id)
    if not config:
        # 返回默认配置
        return ChatbotConfig()
    return config


@router.put("/{app_id}/config", response_model=dict)
def update_chatbot_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    config: ChatbotConfig,
) -> Any:
    """
    更新聊天助手配置
    """
    from app.models.app import App

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    service = get_chatbot_service(db)
    success = service.save_chatbot_config(app_id, config)
    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")

    return {"message": "配置已保存"}


@router.post("/{app_id}/chat", response_model=ChatResponse)
async def chat(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    request: ChatRequest,
) -> Any:
    """
    发送聊天消息
    """
    from app.models.app import App

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    service = get_chatbot_service(db)
    try:
        response = await service.chat(app_id, request, current_user)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"聊天处理失败: {str(e)}")


@router.get("/{app_id}/conversations", response_model=List[ConversationResponse])
def list_conversations(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    page: int = 1,
    page_size: int = 20,
) -> Any:
    """
    获取会话列表
    """
    from app.models.app import App

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    service = get_chatbot_service(db)
    return service.list_conversations(app_id, current_user.id, page, page_size)


@router.get(
    "/{app_id}/conversations/{conversation_id}/messages",
    response_model=List[MessageResponse],
)
def get_conversation_messages(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    conversation_id: int,
    limit: int = 50,
) -> Any:
    """
    获取会话消息列表
    """
    from app.models.app import App
    from app.models.conversation import Conversation

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    # 验证会话存在且属于该应用
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.app_id == app_id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    service = get_chatbot_service(db)
    return service.get_conversation_messages(conversation_id, limit)


@router.delete("/{app_id}/conversations/{conversation_id}")
def delete_conversation(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    conversation_id: int,
) -> Any:
    """
    删除会话
    """
    from app.models.app import App

    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    service = get_chatbot_service(db)
    success = service.delete_conversation(conversation_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="会话不存在")

    return {"message": "会话已删除"}
