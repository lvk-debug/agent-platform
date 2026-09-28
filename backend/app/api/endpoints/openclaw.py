"""
工作助理 - OpenClaw API 端点
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.openclaw import get_openclaw_service
from app.utils.deps import get_current_user
from app.utils.logger import logger

router = APIRouter()


# ==================== 请求/响应模型 ====================

class SessionCreateRequest(BaseModel):
    agent_id: str = "main"
    title: Optional[str] = None


class SessionResponse(BaseModel):
    id: int
    agent_id: str
    title: Optional[str]
    created_at: Any
    updated_at: Any

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: Any
    run_id: Optional[str]
    created_at: Any

    class Config:
        from_attributes = True


class ChatStreamRequest(BaseModel):
    session_id: int
    input: str
    agent_id: str = "main"


class RunCancelRequest(BaseModel):
    pass


# ==================== 会话管理 ====================

@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """获取当前用户的会话列表"""
    service = get_openclaw_service(db)
    sessions = service.list_sessions(current_user.id)
    return sessions


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: SessionCreateRequest,
) -> Any:
    """创建新会话"""
    service = get_openclaw_service(db)
    session = service.create_session(
        user_id=current_user.id,
        agent_id=request.agent_id,
        title=request.title,
    )
    return session


@router.delete("/sessions/{session_id}")
def delete_session(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_id: int,
) -> Any:
    """删除会话（级联删除 messages + runs）"""
    service = get_openclaw_service(db)
    if not service.delete_session(session_id, current_user.id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"message": "删除成功"}


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    session_id: int,
) -> Any:
    """获取会话消息历史"""
    service = get_openclaw_service(db)
    messages = service.get_messages(session_id, current_user.id)
    if not messages:
        # 检查会话是否存在
        session = service.get_session(session_id, current_user.id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
    return messages


# ==================== 聊天 ====================

@router.post("/chat/stream")
async def chat_stream(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    request: ChatStreamRequest,
) -> Any:
    """
    聊天流式代理（SSE）

    返回 Server-Sent Events 流:
    - event: message  - 文本片段
    - event: done     - 完成
    - event: error    - 错误
    """
    service = get_openclaw_service(db)

    return StreamingResponse(
        service.chat_stream(
            session_id=request.session_id,
            user_input=request.input,
            current_user_id=current_user.id,
            agent_id=request.agent_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== 任务管理 ====================

@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    run_id: str,
) -> Any:
    """取消任务（幂等）"""
    service = get_openclaw_service(db)
    success = await service.cancel_remote_run(run_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"message": "取消成功"}


# ==================== 健康检查 ====================

@router.get("/health")
async def health_check() -> Any:
    """OpenClaw 服务健康检查"""
    from app.core.config import settings
    if not settings.OPENCLAW_API_URL:
        return {"status": "not_configured", "message": "OPENCLAW_API_URL 未配置"}

    service = get_openclaw_service(None)
    return await service.check_health()
