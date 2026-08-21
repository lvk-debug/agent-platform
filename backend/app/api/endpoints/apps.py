from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.app import App
from app.models.conversation import Conversation, Message
from app.schemas.app import AppCreate, AppUpdate, AppResponse
from app.schemas.pagination import CursorResponse
from app.utils.deps import get_current_user
from app.utils.pagination import apply_cursor_pagination

router = APIRouter()


@router.get("/", response_model=CursorResponse[AppResponse])
def read_apps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cursor: Optional[int] = Query(None, description="上一页最后一条记录的 ID"),
    limit: int = Query(default=20, ge=1, le=100),
    app_type: Optional[str] = None,
    status: Optional[str] = None,
) -> Any:
    """
    获取应用列表（游标分页）
    """
    query = db.query(App).filter(App.owner_id == current_user.id)

    # 按类型过滤
    if app_type:
        query = query.filter(App.app_type == app_type)

    # 按状态过滤
    if status:
        query = query.filter(App.status == status)

    # 游标分页
    items, next_cursor, has_more = apply_cursor_pagination(
        query, App, cursor=cursor, limit=limit
    )

    return CursorResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/", response_model=AppResponse)
def create_app(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_in: AppCreate,
) -> Any:
    """
    创建应用
    """
    app = App(
        name=app_in.name,
        description=app_in.description,
        app_type=app_in.app_type,
        icon=app_in.icon,
        config=app_in.config,
        owner_id=current_user.id,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}", response_model=AppResponse)
def read_app(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """
    获取应用详情
    """
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(
            status_code=404,
            detail="应用不存在",
        )
    return app


@router.put("/{app_id}", response_model=AppResponse)
def update_app(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    app_in: AppUpdate,
) -> Any:
    """
    更新应用
    """
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(
            status_code=404,
            detail="应用不存在",
        )

    # 更新应用信息
    if app_in.name is not None:
        app.name = app_in.name
    if app_in.description is not None:
        app.description = app_in.description
    if app_in.icon is not None:
        app.icon = app_in.icon
    if app_in.config is not None:
        app.config = app_in.config
    if app_in.status is not None:
        app.status = app_in.status

    db.commit()
    db.refresh(app)
    return app


@router.delete("/{app_id}")
def delete_app(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """
    删除应用
    """
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(
            status_code=404,
            detail="应用不存在",
        )

    db.delete(app)
    db.commit()
    return {"message": "应用已删除"}


@router.post("/{app_id}/publish", response_model=AppResponse)
def publish_app(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """
    发布应用
    """
    from datetime import datetime

    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(
            status_code=404,
            detail="应用不存在",
        )

    app.status = "published"
    app.published_at = datetime.utcnow()
    app.version += 1

    db.commit()
    db.refresh(app)
    return app


@router.get("/{app_id}/conversations", response_model=CursorResponse)
def get_app_conversations(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    cursor: Optional[int] = Query(None, description="上一页最后一条记录的 ID"),
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    """
    获取应用的会话列表
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    # 查询会话列表
    query = db.query(Conversation).filter(
        Conversation.app_id == app_id,
        Conversation.status != "deleted"
    ).order_by(Conversation.created_at.desc())

    # 游标分页
    if cursor:
        query = query.filter(Conversation.id < cursor)

    items = query.limit(limit + 1).all()
    has_more = len(items) > limit
    items = items[:limit]
    next_cursor = items[-1].id if has_more and items else None

    # 添加消息数量
    result = []
    for conv in items:
        msg_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        result.append({
            "id": conv.id,
            "name": conv.title or f"会话 {conv.id}",
            "app_id": conv.app_id,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
            "message_count": msg_count,
        })

    return {
        "items": result,
        "next_cursor": next_cursor,
        "has_more": has_more,
    }


@router.get("/{app_id}/conversations/{conversation_id}/messages")
def get_conversation_messages(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    conversation_id: int,
) -> Any:
    """
    获取会话的消息列表
    """
    # 验证应用存在且属于当前用户
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == current_user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")

    # 验证会话存在且属于该应用
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.app_id == app_id,
    ).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 查询消息列表
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    result = []
    for msg in messages:
        # 解析 metadata 中的 tool_calls
        tool_calls = []
        if msg.metadata_ and isinstance(msg.metadata_, dict):
            tool_calls = msg.metadata_.get("tool_calls", [])

        result.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "role": msg.role,
            "content": msg.content,
            "tool_calls": tool_calls,
            "metadata": msg.metadata_,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        })

    return {"items": result}
