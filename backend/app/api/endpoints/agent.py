"""
Agent API 端点 - 使用 LangGraph create_react_agent
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.utils.deps import get_current_user
from app.models.app import App
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConfig,
    AgentConfigResponse,
    AgentUpdate,
)
from app.services.agent import get_agent_service
from app.utils.logger import logger

router = APIRouter()


@router.get("/{app_id}/config", response_model=AgentConfigResponse)
async def get_agent_config(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取 Agent 配置
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    agent_service = get_agent_service(db)
    config = agent_service.get_agent_config(app_id)

    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    return AgentConfigResponse(
        app_id=app.id,
        app_name=app.name,
        config=config,
    )


@router.get("/{app_id}/debug/config")
async def debug_agent_config(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    调试：获取原始配置数据
    """
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    raw_config = app.config or {}
    logger.info(f"原始配置: {raw_config}")

    return {
        "app_id": app.id,
        "app_name": app.name,
        "raw_config": raw_config,
        "model_id": raw_config.get("model_id"),
        "config_keys": list(raw_config.keys()),
    }


@router.put("/{app_id}/config")
async def update_agent_config(
    app_id: int,
    config: AgentConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新 Agent 配置
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    agent_service = get_agent_service(db)
    success = agent_service.save_agent_config(app_id, config)

    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")

    return {"message": "配置已保存"}


@router.post("/{app_id}/chat", response_model=AgentChatResponse)
async def agent_chat(
    app_id: int,
    request: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Agent 聊天接口

    使用 LangGraph create_react_agent 执行工具调用循环
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    agent_service = get_agent_service(db)

    # 调试：打印原始配置
    raw_config = app.config or {}
    logger.info(f"聊天端点原始配置: app_id={app_id}, model_id={raw_config.get('model_id')}, config_keys={list(raw_config.keys())}")

    try:
        response = await agent_service.chat(
            app_id=app_id,
            request=request,
            user=current_user,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {str(e)}")


@router.post("/{app_id}/chat/stream")
async def agent_chat_stream(
    app_id: int,
    request: AgentChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Agent 流式聊天接口 (SSE)

    返回 Server-Sent Events 流:
    - event: message     - 最终回答文本片段
    - event: tool_start  - 工具调用开始
    - event: tool_end    - 工具调用完成
    - event: thinking    - Agent 推理过程
    - event: done        - 执行完成
    - event: error       - 错误
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    agent_service = get_agent_service(db)

    return StreamingResponse(
        agent_service.chat_stream(
            app_id=app_id,
            request=request,
            user=current_user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{app_id}/debug/model")
async def debug_agent_model(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    调试：测试模型加载
    """
    from app.models.model import Model

    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
        App.app_type == "agent",
    ).first()

    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    raw_config = app.config or {}
    model_id = raw_config.get("model_id")

    if not model_id:
        return {"error": "未配置 model_id", "config": raw_config}

    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        return {"error": f"模型不存在: model_id={model_id}"}

    return {
        "model_id": model.id,
        "model_name": model.name,
        "model_model_id": model.model_id,
        "provider_id": model.provider_id,
        "provider_type": model.provider.provider_type if model.provider else None,
        "is_active": model.is_active,
    }
