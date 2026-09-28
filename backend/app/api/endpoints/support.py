"""
智能客服助手端点

路由前缀 /api/v1/support

分层约定：端点只做参数校验、调用 Service、序列化返回；业务逻辑全在
services/support.py、support_chat.py、support_ticket.py。

SSE 说明：流式端点用**独立的 SessionLocal** 而不是 Depends(get_db) 的会话。
流式期间要边写库边推流，请求级会话的生命周期由 FastAPI 管理，
在生成器结束前就可能被关闭，导致落库失败（学习助手模块已踩过）。
"""

from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.models.support import (
    CustomerSource,
    IntentCategory,
    MessageRole,
    SessionMode,
    SessionStatus,
    SupportSession,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from app.models.user import User
from app.schemas.support import (
    AnalyticsResponse,
    ChatAskRequest,
    CustomerCreate,
    ReturnConfirmRequest,
    CustomerListResponse,
    CustomerResponse,
    CustomerUpdate,
    MessageListResponse,
    MessageResponse,
    MessageSendRequest,
    MessageSendResponse,
    PageMeta,
    QuickReplyCreate,
    QuickReplyListResponse,
    QuickReplyResponse,
    QuickReplyUpdate,
    SessionCloseRequest,
    SessionCreate,
    SessionListResponse,
    SessionModeRequest,
    SessionResponse,
    SessionTakeoverRequest,
    SessionTransferRequest,
    SessionUpdate,
    SettingsResponse,
    SettingsUpdate,
    SuggestReplyResponse,
    SuggestRequest,
    TicketCommentRequest,
    TicketCreate,
    TicketDetailResponse,
    TicketListResponse,
    TicketResponse,
    TicketTransitionRequest,
    TicketUpdate,
    BusinessDataResponse,
)
from app.schemas.support_evaluation import (
    EvaluationResponse,
    EvalQueueItem,
    EvalQueueResponse,
    GenerateKbDocsResponse,
    ManualScoreRequest,
    ManualScoreResponse,
    QualityOverview,
    QualitySummaryResponse,
    QualityTrendPoint,
    QualityIntentItem,
)
from app.services.support import SupportService, get_support_service
from app.services.support_chat import get_support_chat_service
from app.services.support_ticket import get_support_ticket_service
from app.services.support_evaluation import get_support_evaluation_service
from app.services.support_kb_docs import get_support_kb_doc_service
from app.utils.deps import get_current_user

router = APIRouter()


def _page_meta(total: int, page: int, page_size: int) -> PageMeta:
    return PageMeta(total=total, page=page, page_size=page_size)


def _get_session_or_404(service: SupportService, session_id: int) -> SupportSession:
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return session


# ==================================================================
# 会话
# ==================================================================


@router.get("/sessions", response_model=SessionListResponse, summary="会话列表")
def list_sessions(
    status: Optional[str] = Query(None, description="open / pending_human / resolved / closed"),
    mode: Optional[str] = Query(None, description="ai / human"),
    intent: Optional[str] = Query(None, description="意图分类"),
    assignee_id: Optional[int] = Query(None, description="坐席 ID；-1 表示未接管"),
    customer_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    items, total = service.list_sessions(
        status=status,
        mode=mode,
        intent=intent,
        assignee_id=assignee_id,
        customer_id=customer_id,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return SessionListResponse(
        items=[SessionResponse(**item) for item in items],
        meta=_page_meta(total, page, page_size),
    )


@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建会话",
)
def create_session(
    data: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = service.create_session(current_user.id, data)
    return SessionResponse(**service.session_payload(session))


@router.get("/sessions/{session_id}", response_model=SessionResponse, summary="会话详情")
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = _get_session_or_404(service, session_id)
    return SessionResponse(**service.session_payload(session))


@router.patch("/sessions/{session_id}", response_model=SessionResponse, summary="更新会话")
def update_session(
    session_id: int,
    data: SessionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = service.update_session(session_id, data)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return SessionResponse(**service.session_payload(session))


@router.delete(
    "/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除会话"
)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    if not service.delete_session(session_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessageListResponse,
    summary="会话消息",
)
def list_messages(
    session_id: int,
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    _get_session_or_404(service, session_id)
    items = service.list_messages(session_id, limit=limit)
    return MessageListResponse(
        session_id=session_id, items=[MessageResponse(**item) for item in items]
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageSendResponse,
    status_code=status.HTTP_201_CREATED,
    summary="发送消息（坐席回复 / 代客录入）",
)
def send_message(
    session_id: int,
    data: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """非流式发送

    role=agent 表示坐席亲自回复：此时会话自动切为人工模式并记在该坐席名下，
    因为「坐席亲自开口」本身就是一种接管动作。
    """
    service = get_support_service(db)
    session = _get_session_or_404(service, session_id)
    if session.status == SessionStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="会话已关闭，无法继续发送"
        )

    # 只允许坐席录入客户诉求或亲自回复，AI/系统消息由后端产生
    role = (
        data.role
        if data.role in (MessageRole.CUSTOMER, MessageRole.AGENT)
        else MessageRole.CUSTOMER
    )
    operator_id = current_user.id if role == MessageRole.AGENT else None
    if role == MessageRole.AGENT:
        session.mode = SessionMode.HUMAN
        session.assignee_id = session.assignee_id or current_user.id
        if session.status == SessionStatus.PENDING_HUMAN:
            session.status = SessionStatus.OPEN

    message = service.append_message(
        session_id=session_id,
        role=role,
        content=data.content,
        operator_id=operator_id,
    )
    db.refresh(session)
    return MessageSendResponse(
        message=MessageResponse(**service.message_payload(message)),
        session=SessionResponse(**service.session_payload(session)),
    )


@router.post(
    "/sessions/{session_id}/chat/stream", summary="AI 问答（SSE 流式）"
)
async def chat_stream(
    session_id: int,
    data: ChatAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """流式问答：references → delta… → done | error

    流式期间用独立 Session：生成器结束前请求级会话可能已被回收。
    """
    service = get_support_service(db)
    _get_session_or_404(service, session_id)

    stream_db = SessionLocal()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            chat = get_support_chat_service(stream_db)
            session = (
                stream_db.query(SupportSession)
                .filter(SupportSession.id == session_id)
                .first()
            )
            if not session:
                yield chat.sse_event("error", {"detail": "会话不存在"})
                return
            async for chunk in chat.chat_stream(
                session=session,
                query=data.query,
                user_id=current_user.id,
                model_id=data.model_id,
            ):
                yield chunk
        finally:
            stream_db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/confirm", summary="退货/退款人工确认后续跑（SSE 流式）"
)
async def confirm_return(
    session_id: int,
    data: ReturnConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """human-in-the-loop 续跑：坐席确认后恢复被挂起的客服图，流式输出最终回复。

    仅当上一轮 /chat/stream 返回 pending_confirm=true（并收到 human_confirm 事件）时调用。
    decision=approved 由 AI 继续按政策协助；rejected 转人工，不自动执行退款。
    """
    service = get_support_service(db)
    _get_session_or_404(service, session_id)

    stream_db = SessionLocal()

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            chat = get_support_chat_service(stream_db)
            session = (
                stream_db.query(SupportSession)
                .filter(SupportSession.id == session_id)
                .first()
            )
            if not session:
                yield chat.sse_event("error", {"detail": "会话不存在"})
                return
            async for chunk in chat.confirm_stream(
                session=session,
                decision=data.model_dump(),
                user_id=current_user.id,
            ):
                yield chunk
        finally:
            stream_db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post(
    "/sessions/{session_id}/suggest",
    response_model=SuggestReplyResponse,
    summary="AI 建议回复",
)
async def suggest_reply(
    session_id: int,
    data: SuggestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """人工模式下给坐席起草一版回复（不落库，采用后由坐席发送）"""
    service = get_support_service(db)
    session = _get_session_or_404(service, session_id)
    chat = get_support_chat_service(db)
    content, references, error = await chat.suggest_reply(session, data.model_id)
    return SuggestReplyResponse(content=content, references=references, error=error)


@router.post(
    "/sessions/{session_id}/takeover", response_model=SessionResponse, summary="接管会话"
)
def take_over(
    session_id: int,
    data: SessionTakeoverRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = service.take_over(session_id, current_user.id, data.reason)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="会话不存在或已关闭"
        )
    return SessionResponse(**service.session_payload(session))


@router.post(
    "/sessions/{session_id}/transfer", response_model=SessionResponse, summary="转交坐席"
)
def transfer_session(
    session_id: int,
    data: SessionTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = service.transfer(session_id, data.assignee_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return SessionResponse(**service.session_payload(session))


@router.post(
    "/sessions/{session_id}/mode", response_model=SessionResponse, summary="切换会话模式"
)
def switch_mode(
    session_id: int,
    data: SessionModeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.mode not in SessionMode.ALL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知模式")
    service = get_support_service(db)
    session = service.switch_mode(session_id, data.mode)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return SessionResponse(**service.session_payload(session))


@router.post(
    "/sessions/{session_id}/close", response_model=SessionResponse, summary="结束会话"
)
def close_session(
    session_id: int,
    data: SessionCloseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    session = service.close_session(session_id, current_user.id, data)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return SessionResponse(**service.session_payload(session))


# ==================================================================
# 客户
# ==================================================================


@router.get("/customers", response_model=CustomerListResponse, summary="客户列表")
def list_customers(
    keyword: Optional[str] = Query(None, max_length=100),
    source: Optional[str] = Query(None, max_length=20),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    items, total = service.list_customers(
        keyword=keyword, source=source, page=page, page_size=page_size
    )
    return CustomerListResponse(
        items=[CustomerResponse(**item) for item in items],
        meta=_page_meta(total, page, page_size),
    )


@router.post(
    "/customers",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建客户",
)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.create_customer(current_user.id, data)
    return CustomerResponse(**service.customer_payload(row))


@router.get(
    "/customers/{customer_id}", response_model=CustomerResponse, summary="客户详情"
)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.get_customer(customer_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return CustomerResponse(**service.customer_payload(row))


@router.patch(
    "/customers/{customer_id}", response_model=CustomerResponse, summary="更新客户"
)
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.update_customer(customer_id, data)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")
    return CustomerResponse(**service.customer_payload(row))


@router.delete(
    "/customers/{customer_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除客户"
)
def delete_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    if not service.delete_customer(customer_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="客户不存在")


# ==================================================================
# 工单
# ==================================================================


@router.get("/tickets", response_model=TicketListResponse, summary="工单列表")
def list_tickets(
    status: Optional[str] = Query(None, description="pending / processing / resolved / rejected / closed"),
    type: Optional[str] = Query(None, description="refund / reschedule / repair / complaint / consult / other"),
    priority: Optional[str] = Query(None, description="low / normal / high / urgent"),
    assignee_id: Optional[int] = Query(None, description="-1 表示未指派"),
    customer_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None, max_length=100),
    only_overdue: bool = Query(False, description="只看已超时"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    items, total = service.list_tickets(
        status=status,
        type=type,
        priority=priority,
        assignee_id=assignee_id,
        customer_id=customer_id,
        keyword=keyword,
        only_overdue=only_overdue,
        page=page,
        page_size=page_size,
    )
    return TicketListResponse(
        items=[TicketResponse(**item) for item in items],
        meta=_page_meta(total, page, page_size),
    )


@router.post(
    "/tickets",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建工单",
)
def create_ticket(
    data: TicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    row = service.create_ticket(current_user.id, data)
    return TicketResponse(**service.ticket_payload(row))


@router.get(
    "/tickets/{ticket_id}", response_model=TicketDetailResponse, summary="工单详情"
)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    row = service.get_ticket(ticket_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return TicketDetailResponse(
        ticket=TicketResponse(**service.ticket_payload(row)),
        logs=service.list_logs(ticket_id),
    )


@router.patch("/tickets/{ticket_id}", response_model=TicketResponse, summary="更新工单")
def update_ticket(
    ticket_id: int,
    data: TicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    row = service.update_ticket(ticket_id, data)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")
    return TicketResponse(**service.ticket_payload(row))


@router.post(
    "/tickets/{ticket_id}/transition",
    response_model=TicketDetailResponse,
    summary="工单状态流转",
)
def transition_ticket(
    ticket_id: int,
    data: TicketTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    try:
        row = service.transition(ticket_id, current_user.id, data)
    except ValueError as exc:
        # 状态机校验失败是业务错误，给 400 让前端直接提示原因
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return TicketDetailResponse(
        ticket=TicketResponse(**service.ticket_payload(row)),
        logs=service.list_logs(ticket_id),
    )


@router.post(
    "/tickets/{ticket_id}/comments",
    response_model=TicketDetailResponse,
    summary="工单留言",
)
def comment_ticket(
    ticket_id: int,
    data: TicketCommentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    try:
        service.add_comment(ticket_id, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    row = service.get_ticket(ticket_id)
    return TicketDetailResponse(
        ticket=TicketResponse(**service.ticket_payload(row)),
        logs=service.list_logs(ticket_id),
    )


@router.delete(
    "/tickets/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除工单"
)
def delete_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_ticket_service(db)
    if not service.delete_ticket(ticket_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工单不存在")


# ==================================================================
# 机器人配置
# ==================================================================


@router.get("/settings", response_model=SettingsResponse, summary="机器人配置")
def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    return SettingsResponse(**service.settings_payload(service.get_settings()))


@router.put("/settings", response_model=SettingsResponse, summary="更新机器人配置")
def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.update_settings(current_user.id, data)
    return SettingsResponse(**service.settings_payload(row))


# ==================================================================
# 快捷话术
# ==================================================================


@router.get(
    "/quick-replies", response_model=QuickReplyListResponse, summary="快捷话术列表"
)
def list_quick_replies(
    category: Optional[str] = Query(None, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    items = service.list_quick_replies(category=category)
    return QuickReplyListResponse(
        items=[QuickReplyResponse(**item) for item in items]
    )


@router.post(
    "/quick-replies",
    response_model=QuickReplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建快捷话术",
)
def create_quick_reply(
    data: QuickReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.create_quick_reply(current_user.id, data)
    return QuickReplyResponse(**service.quick_reply_payload(row))


@router.patch(
    "/quick-replies/{reply_id}", response_model=QuickReplyResponse, summary="更新快捷话术"
)
def update_quick_reply(
    reply_id: int,
    data: QuickReplyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    row = service.update_quick_reply(reply_id, data)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="话术不存在")
    return QuickReplyResponse(**service.quick_reply_payload(row))


@router.delete(
    "/quick-replies/{reply_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除快捷话术",
)
def delete_quick_reply(
    reply_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    if not service.delete_quick_reply(reply_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="话术不存在")


# ==================================================================
# 统计
# ==================================================================


@router.get("/analytics", response_model=AnalyticsResponse, summary="运营看板数据")
def analytics(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_service(db)
    return AnalyticsResponse(**service.analytics(days=days))


# ==================================================================
# 选项（供前端下拉）
# ==================================================================


# ==================================================================
# 业务数据（Demo 示例，供后台维护）
# ==================================================================


@router.get(
    "/business-data", response_model=BusinessDataResponse, summary="业务数据快照"
)
def business_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """订单/物流/商品/退换货政策示例数据，供机器人配置「业务数据」Tab 展示"""
    service = get_support_service(db)
    return BusinessDataResponse(**service.get_business_data())


@router.post("/business-data/reset", summary="恢复示例业务数据")
def reset_business_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空并重新写入示例数据（演示用，便于重置）"""
    get_support_service(db).reset_business_data()
    return {"ok": True}


@router.get("/options", summary="枚举选项")
def options(current_user: User = Depends(get_current_user)):
    """前端下拉与标签渲染用的常量，避免前后端各维护一份映射"""
    return {
        "session_status": [
            {"value": value, "label": SessionStatus.LABELS.get(value, value)}
            for value in SessionStatus.ALL
        ],
        "intents": [
            {"value": value, "label": IntentCategory.LABELS.get(value, value)}
            for value in IntentCategory.ALL
        ],
        "ticket_types": [
            {"value": value, "label": TicketType.LABELS.get(value, value)}
            for value in TicketType.ALL
        ],
        "ticket_status": [
            {"value": value, "label": TicketStatus.LABELS.get(value, value)}
            for value in TicketStatus.ALL
        ],
        "ticket_priorities": [
            {"value": value, "label": TicketPriority.LABELS.get(value, value)}
            for value in TicketPriority.ALL
        ],
        "customer_sources": [
            {"value": value, "label": CustomerSource.LABELS.get(value, value)}
            for value in CustomerSource.ALL
        ],
    }


# ==================================================================
# 评测（自动 + 人工）与质量看板
# ==================================================================


def _eval_response(evaluation, db: Session) -> EvaluationResponse:
    """把 SupportEvaluation 拼成响应（带 AI 内容摘要与标注人姓名）"""
    from app.models.support import IntentCategory, SupportMessage

    message = (
        db.query(SupportMessage)
        .filter(SupportMessage.id == evaluation.message_id)
        .first()
    )
    annotator_name = ""
    if evaluation.annotator_id:
        user = db.query(User).filter(User.id == evaluation.annotator_id).first()
        annotator_name = user.username if user else ""
    return EvaluationResponse(
        id=evaluation.id,
        message_id=evaluation.message_id,
        session_id=evaluation.session_id,
        query=evaluation.query,
        intent=evaluation.intent,
        intent_label=IntentCategory.LABELS.get(evaluation.intent, evaluation.intent or ""),
        auto_scores=evaluation.deepeval_scores,
        auto_overall=evaluation.deepeval_overall,
        deepeval_scores=evaluation.deepeval_scores,
        deepeval_overall=evaluation.deepeval_overall,
        deepeval_reasoning=evaluation.deepeval_reasoning,
        manual_scores=evaluation.manual_scores,
        manual_overall=evaluation.manual_overall,
        annotator_id=evaluation.annotator_id,
        annotator_name=annotator_name,
        comment=evaluation.comment,
        status=evaluation.status,
        ai_content=(message.content or "") if message else "",
        created_at=evaluation.created_at,
        updated_at=evaluation.updated_at,
    )


@router.post(
    "/sessions/{session_id}/messages/{message_id}/evaluate",
    response_model=EvaluationResponse,
    summary="触发单条 AI 回答的自动评测",
)
async def evaluate_message(
    session_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对一条 AI 消息跑自动评测（LLM 裁判 + 启发式），返回评测记录。"""
    service = get_support_evaluation_service(db)
    evaluation = await service.auto_evaluate(message_id, current_user.id)
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在或不是可评测的 AI 回答",
        )
    return _eval_response(evaluation, db)


@router.post(
    "/sessions/{session_id}/messages/evaluate-all",
    summary="自动评测本会话全部 AI 消息",
)
async def evaluate_session_all(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """对本会话尚未自动评测的 AI 回答批量回填分数（串行，控制 LLM 配额）"""
    _get_session_or_404(get_support_service(db), session_id)
    service = get_support_evaluation_service(db)
    done = await service.evaluate_session_messages(session_id)
    return {"ok": True, "done": done}


@router.post(
    "/evaluations/manual",
    response_model=ManualScoreResponse,
    summary="人工标注打分",
)
def manual_score(
    data: ManualScoreRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """坐席/管理员对 AI 回答按维度打分并写评语，status 置 done。"""
    service = get_support_evaluation_service(db)
    evaluation = service.manual_score(data.message_id, data, current_user.id)
    if not evaluation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="消息不存在或不是可评测的 AI 回答",
        )
    return ManualScoreResponse(
        message_id=evaluation.message_id,
        status=evaluation.status,
        manual_overall=evaluation.manual_overall,
    )


@router.get(
    "/evaluations/queue",
    response_model=EvalQueueResponse,
    summary="待标注队列",
)
def evaluation_queue(
    status_filter: Optional[str] = Query(None, description="auto / pending；不传为未标注全部"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """未人工标注的评测列表，供看板「去打分」。"""
    service = get_support_evaluation_service(db)
    items, total = service.list_queue(
        status=status_filter, page=page, page_size=page_size
    )
    queue_items = [
        EvalQueueItem(
            message_id=e.message_id,
            session_id=e.session_id,
            query=e.query,
            ai_preview=(e.query or ""),
            intent=e.intent,
            intent_label=IntentCategory.LABELS.get(e.intent, e.intent or ""),
            auto_overall=e.deepeval_overall,
            status=e.status,
            created_at=e.created_at,
        )
        for e in items
    ]
    return EvalQueueResponse(
        items=queue_items, meta=PageMeta(total=total, page=page, page_size=page_size)
    )


@router.get(
    "/evaluations/quality",
    response_model=QualitySummaryResponse,
    summary="质量看板",
)
def evaluation_quality(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """自动分 + 人工分结合的质量总览（趋势、按意图、待标注数）。"""
    service = get_support_evaluation_service(db)
    summary = service.quality_summary(days=days)
    return QualitySummaryResponse(
        days=days,
        overview=QualityOverview(**summary["overview"]),
        trend=[QualityTrendPoint(**t) for t in summary["trend"]],
        by_intent=[QualityIntentItem(**i) for i in summary["by_intent"]],
    )


@router.get(
    "/evaluations/{message_id}",
    response_model=EvaluationResponse,
    summary="单条评测记录",
)
def get_evaluation(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_support_evaluation_service(db)
    evaluation = service.get_by_message(message_id)
    if not evaluation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无评测记录")
    return _eval_response(evaluation, db)


@router.post(
    "/generate-kb-docs",
    response_model=GenerateKbDocsResponse,
    summary="从客服业务数据生成知识库文档",
)
async def generate_kb_docs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """读取订单/商品/物流/退换货政策示例数据，生成退换货政策、下单指引、
    商品说明书并向量化入库到「客服知识库（自动生成）」。幂等按文档名覆盖。"""
    service = get_support_kb_doc_service(db)
    result = await service.generate(current_user.id)
    return GenerateKbDocsResponse(**result)
