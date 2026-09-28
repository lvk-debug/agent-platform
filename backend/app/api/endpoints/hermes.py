"""
Hermes Agent API 端点

所有数据存储在本地数据库（PostgreSQL）。
FastAPI 只负责：用户认证 + 数据库读写 + SSE 中继。
所有 Agent 逻辑由远程 Hermes API Server 完成。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.hermes import HermesAttachment
from app.models.user import User
from app.services.attachment import AttachmentError, get_attachment_service
from app.services.hermes import get_hermes_service
from app.services.hermes_gateway import GatewayError, HermesGateway
from app.services.quick_prompt import BUILTIN_PROMPTS, get_quick_prompt_service
from app.services.hermes_skill import get_hermes_skill_service
from app.utils.deps import get_current_user
from app.utils.logger import logger

router = APIRouter()


# ==================== 工具函数 ====================


@asynccontextmanager
async def _gateway_session():
    """
    创建并安全关闭 HermesGateway

    httpx.AsyncClient 绑定事件循环，因此每个请求使用独立实例并在同一协程内关闭。
    """
    gateway = HermesGateway()
    try:
        yield gateway
    finally:
        try:
            await gateway.close()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"关闭 Hermes gateway 失败: {e}")


def _raise_gateway_error(e: GatewayError) -> None:
    """把上游错误转换为对前端友好的 HTTP 错误（不透出密钥与内部细节）"""
    status = 503 if e.unavailable else (502 if not e.status_code else e.status_code)
    if e.status_code in (404, 405):
        status = 404
    raise HTTPException(status_code=status, detail=e.message)


def _parse_default_tools() -> List[Dict[str, str]]:
    """解析配置中的内置工具清单（name:label:desc，逗号分隔）"""
    raw = getattr(settings, "HERMES_DEFAULT_TOOLS", "") or ""
    tools: List[Dict[str, str]] = []
    for item in raw.split(","):
        parts = [p.strip() for p in item.split(":")]
        if not parts or not parts[0]:
            continue
        tools.append(
            {
                "name": parts[0],
                "label": parts[1] if len(parts) > 1 and parts[1] else parts[0],
                "description": parts[2] if len(parts) > 2 else "",
            }
        )
    return tools


# ==================== Request / Response Schemas ====================


class CreateSessionRequest(BaseModel):
    title: str = "新会话"
    model: str = ""
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)


class UpdateSessionConfigRequest(BaseModel):
    """更新会话能力配置（未传入的字段保持不变）"""

    model: Optional[str] = None
    skills: Optional[List[str]] = None
    tools: Optional[List[str]] = None


class SessionResponse(BaseModel):
    id: str
    title: str
    model: str
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    tools_used: list
    token_input: int
    token_output: int
    created_at: str

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    """发送消息请求"""

    message: str = Field(..., min_length=1, max_length=10000)
    model: str = ""
    skills: List[str] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)
    # 已上传附件的 ID，随本条消息一起送入模型上下文
    attachment_ids: List[int] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    api_url: str
    error: Optional[str] = None


# ==================== 技能管理 ====================


class SkillCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100)
    description: str = ""
    instruction: str = ""
    icon: str = ""
    enabled: bool = True
    sort_order: int = 0


class SkillUpdateRequest(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    instruction: Optional[str] = None
    icon: Optional[str] = None
    enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class SkillResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    instruction: str
    icon: str
    enabled: bool
    sort_order: int
    created_at: str
    updated_at: str


# ==================== 任务管理 ====================


class JobCreateRequest(BaseModel):
    """创建后台计划任务（结构对齐 hermes cron）"""

    prompt: str = Field(..., min_length=1)
    schedule: str = Field(..., min_length=1, description="cron 表达式或计划描述")
    skills: List[str] = Field(default_factory=list)
    name: str = ""
    delivery: Optional[Dict[str, Any]] = None
    model: str = ""


class JobUpdateRequest(BaseModel):
    prompt: Optional[str] = None
    schedule: Optional[str] = None
    skills: Optional[List[str]] = None
    name: Optional[str] = None
    delivery: Optional[Dict[str, Any]] = None
    model: Optional[str] = None


# ==================== 会话管理 ====================


def _to_session_response(s) -> SessionResponse:
    """会话模型 -> 响应体"""
    return SessionResponse(
        id=s.id,
        title=s.title,
        model=s.model or "",
        skills=s.skills or [],
        tools=s.tools or [],
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


@router.get("/sessions", response_model=List[SessionResponse])
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取当前用户的所有会话"""
    service = get_hermes_service(db)
    sessions = service.list_sessions(current_user.id)
    return [_to_session_response(s) for s in sessions]


@router.post("/sessions", response_model=SessionResponse)
def create_session(
    req: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """创建新会话（可携带技能与工具偏好）"""
    service = get_hermes_service(db)
    session = service.create_session(
        user_id=current_user.id,
        title=req.title,
        model=req.model,
        skills=req.skills,
        tools=req.tools,
    )
    return _to_session_response(session)


@router.patch("/sessions/{session_id}/config", response_model=SessionResponse)
def update_session_config(
    session_id: str,
    req: UpdateSessionConfigRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新会话的能力配置（模型 / 技能 / 工具）"""
    service = get_hermes_service(db)
    session = service.update_session_config(
        session_id=session_id,
        user_id=current_user.id,
        model=req.model,
        skills=req.skills,
        tools=req.tools,
    )
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return _to_session_response(session)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除指定会话"""
    service = get_hermes_service(db)
    if not service.delete_session(session_id, current_user.id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


# ==================== 消息管理 ====================


@router.get("/sessions/{session_id}/messages", response_model=List[MessageResponse])
def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取会话的消息列表"""
    service = get_hermes_service(db)
    session = service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    messages = service.get_messages(session_id)
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            tools_used=m.tools_used or [],
            token_input=m.token_input or 0,
            token_output=m.token_output or 0,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]


# ==================== SSE 流式对话 ====================


@router.post("/sessions/{session_id}/chat")
def chat_trigger(
    session_id: str,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    发送消息（触发对话）

    返回 run_id，前端通过 GET /stream/{run_id} 获取 SSE 事件流。
    """
    service = get_hermes_service(db)
    session = service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 创建 run 记录
    run = service.create_run(session_id)

    return {"run_id": run.id, "session_id": session_id}


@router.post("/sessions/{session_id}/stream")
def chat_stream(
    session_id: str,
    req: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    流式 SSE 接口

    调用 Hermes API Server，实时转发 content_delta / tool_start / tool_result 事件给前端。
    使用 fetch + ReadableStream 消费。
    """
    service = get_hermes_service(db)
    session = service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 同步会话级能力配置，使刷新后抽屉回显与本次请求保持一致
    if req.model or req.skills is not None or req.tools is not None:
        service.update_session_config(
            session_id=session_id,
            user_id=current_user.id,
            model=req.model or None,
            skills=req.skills if req.skills is not None else None,
            tools=req.tools if req.tools is not None else None,
        )

    def event_generator():
        """同步生成器，yield SSE 事件"""
        try:
            yield from service.chat_stream(
                session_id=session_id,
                user_message=req.message,
                model=req.model,
                skills=req.skills,
                tools=req.tools,
                attachment_ids=req.attachment_ids,
            )
        except Exception as e:
            logger.error(f"SSE 流异常: {e}", exc_info=True)
            yield f'event: error\ndata: {{"message": "{str(e)}"}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== 健康检查 ====================


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """检查 Hermes API Server 连通性"""
    import httpx

    api_url = f"{settings.HERMES_API_URL}/models" if settings.HERMES_API_URL else ""

    if not api_url:
        return HealthResponse(
            status="not_configured", api_url="", error="HERMES_API_URL 未配置"
        )

    try:
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            resp = await client.get(
                api_url,
                headers={"Authorization": f"Bearer {settings.HERMES_API_KEY}"},
            )
            if resp.status_code == 200:
                return HealthResponse(status="ok", api_url=api_url)
            return HealthResponse(
                status="error",
                api_url=api_url,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
    except httpx.ConnectError:
        return HealthResponse(status="unreachable", api_url=api_url, error="无法连接")
    except Exception as e:
        return HealthResponse(status="error", api_url=api_url, error=str(e))


# ==================== 能力发现 / 模型 / 工具 / 详细状态 ====================


@router.get("/capabilities")
async def get_capabilities(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    GET /v1/capabilities 代理

    返回 Hermes API Server 支持的稳定能力（chat_completions、run_stop 等），
    结果在后端缓存，上游故障时返回上一次成功结果。
    """
    try:
        async with _gateway_session() as gateway:
            data = await gateway.get_capabilities(force_refresh=refresh)
    except GatewayError as e:
        _raise_gateway_error(e)
    return data


@router.get("/models")
async def get_models(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
):
    """GET /v1/models 代理：返回可用模型列表"""
    try:
        async with _gateway_session() as gateway:
            data = await gateway.get_models(force_refresh=refresh)
    except GatewayError as e:
        _raise_gateway_error(e)
    return data


@router.get("/tools")
async def get_tools(current_user: User = Depends(get_current_user)):
    """
    内置工具清单（来自配置，用于工作助理工具面板展示与偏好勾选）

    注意：Hermes 服务端工具是全量启用的，这里的勾选仅作为本轮偏好注入，
    不构成硬性白名单。
    """
    return {"tools": _parse_default_tools()}


@router.get("/health/detailed")
async def get_health_detailed(
    refresh: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    GET /health/detailed 代理：只读的就绪状态摘要

    只返回状态与计数，不透出路径、凭据、配置值与原始错误。
    """
    try:
        async with _gateway_session() as gateway:
            data = await gateway.get_health_detailed(force_refresh=refresh)
    except GatewayError as e:
        _raise_gateway_error(e)
    return data


# ==================== 技能管理 ====================


def _to_skill_response(s) -> SkillResponse:
    return SkillResponse(
        id=s.id,
        name=s.name,
        slug=s.slug,
        description=s.description or "",
        instruction=s.instruction or "",
        icon=s.icon or "",
        enabled=bool(s.enabled),
        sort_order=s.sort_order or 0,
        created_at=s.created_at.isoformat() if s.created_at else "",
        updated_at=s.updated_at.isoformat() if s.updated_at else "",
    )


@router.get("/skills", response_model=List[SkillResponse])
def list_skills(
    keyword: str = "",
    enabled_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出技能（默认全部，可用于工作助理技能面板）"""
    service = get_hermes_skill_service(db)
    skills = service.list_skills(keyword=keyword, enabled_only=enabled_only)
    return [_to_skill_response(s) for s in skills]


@router.post("/skills", response_model=SkillResponse)
def create_skill(
    req: SkillCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建技能"""
    service = get_hermes_skill_service(db)
    if service.get_by_slug(req.slug):
        raise HTTPException(status_code=400, detail=f"技能标识已存在: {req.slug}")
    skill = service.create_skill(
        name=req.name,
        slug=req.slug,
        description=req.description,
        instruction=req.instruction,
        icon=req.icon,
        enabled=req.enabled,
        sort_order=req.sort_order,
        created_by=current_user.id,
    )
    return _to_skill_response(skill)


@router.put("/skills/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: str,
    req: SkillUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新技能"""
    service = get_hermes_skill_service(db)
    if req.slug:
        exist = service.get_by_slug(req.slug)
        if exist and exist.id != skill_id:
            raise HTTPException(status_code=400, detail=f"技能标识已存在: {req.slug}")
    skill = service.update_skill(skill_id, **req.dict(exclude_unset=True))
    if not skill:
        raise HTTPException(status_code=404, detail="技能不存在")
    return _to_skill_response(skill)


@router.delete("/skills/{skill_id}")
def delete_skill(
    skill_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除技能"""
    service = get_hermes_skill_service(db)
    if not service.delete_skill(skill_id):
        raise HTTPException(status_code=404, detail="技能不存在")
    return {"ok": True}


# ==================== Runs（运行状态与停止） ====================


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """查询 run 状态（本地记录 + 上游状态，若存在上游 run）"""
    service = get_hermes_service(db)
    run = service.get_run(run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    result: Dict[str, Any] = {
        "run_id": run.id,
        "session_id": run.session_id,
        "status": run.status,
        "external_run_id": run.external_run_id or "",
        "token_input": run.token_input or 0,
        "token_output": run.token_output or 0,
        "latency_ms": run.latency_ms or 0.0,
    }

    if run.external_run_id:
        try:
            async with _gateway_session() as gateway:
                upstream = await gateway.get_run(run.external_run_id)
            result["upstream"] = upstream
            if isinstance(upstream, dict) and upstream.get("status"):
                result["status"] = str(upstream["status"])
        except GatewayError as e:
            logger.warning(f"查询上游 run 失败: {e.message}")
            result["upstream_error"] = e.message

    return result


@router.post("/runs/{run_id}/stop")
async def stop_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    停止正在进行的生成

    - 存在上游 run_id：调用 POST /v1/runs/{id}/stop 真正中断 agent
    - 否则：仅标记本地 stopping，返回 external=false，前端降级为中止 SSE
    """
    service = get_hermes_service(db)
    run = service.get_run(run_id, current_user.id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")

    if not run.external_run_id:
        service.mark_run_stopping(run_id)
        return {"status": "stopping", "external": False, "run_id": run_id}

    try:
        async with _gateway_session() as gateway:
            result = await gateway.stop_run(run.external_run_id)
        service.mark_run_stopping(run_id)
        return {
            "status": result.get("status", "stopping"),
            "external": True,
            "run_id": run_id,
        }
    except GatewayError as e:
        logger.warning(f"停止上游 run 失败: {e.message}")
        service.mark_run_stopping(run_id)
        return {
            "status": "stopping",
            "external": False,
            "run_id": run_id,
            "message": e.message,
        }


@router.post("/runs")
async def submit_run(
    payload: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    通过 Runs API 提交一次 run（可后续用 /runs/{id}/stop 真正停止）

    body: {"session_id": "...", "input": "...", "instructions": "..."}
    """
    session_id = str(payload.get("session_id", ""))
    user_input = str(payload.get("input", ""))
    if not session_id or not user_input:
        raise HTTPException(status_code=400, detail="session_id 与 input 不能为空")

    service = get_hermes_service(db)
    session = service.get_session(session_id, current_user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        async with _gateway_session() as gateway:
            upstream = await gateway.create_run(
                user_input=user_input,
                session_id=session_id,
                instructions=str(payload.get("instructions", "")),
            )
    except GatewayError as e:
        _raise_gateway_error(e)

    run = service.create_run_with_external(
        session_id=session_id, external_run_id=upstream.get("run_id", "")
    )
    return {
        "run_id": run.id,
        "external_run_id": run.external_run_id,
        "status": upstream.get("status", "started"),
    }


# ==================== Jobs（后台计划任务） ====================


def _assert_jobs_enabled() -> None:
    if not getattr(settings, "HERMES_JOBS_ENABLED", True):
        raise HTTPException(status_code=404, detail="未启用后台任务能力")


@router.get("/jobs")
async def list_jobs(current_user: User = Depends(get_current_user)):
    """列出后台计划任务"""
    _assert_jobs_enabled()
    try:
        async with _gateway_session() as gateway:
            return await gateway.list_jobs()
    except GatewayError as e:
        _raise_gateway_error(e)


@router.post("/jobs")
async def create_job(
    req: JobCreateRequest,
    current_user: User = Depends(get_current_user),
):
    """创建后台计划任务"""
    _assert_jobs_enabled()
    payload: Dict[str, Any] = {
        "prompt": req.prompt,
        "schedule": req.schedule,
        "name": req.name or req.prompt[:20],
    }
    if req.skills:
        payload["skills"] = req.skills
    if req.delivery:
        payload["delivery"] = req.delivery
    if req.model:
        payload["model"] = req.model

    try:
        async with _gateway_session() as gateway:
            return await gateway.create_job(payload)
    except GatewayError as e:
        _raise_gateway_error(e)


@router.patch("/jobs/{job_id}")
async def update_job(
    job_id: str,
    req: JobUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """更新后台计划任务（部分字段合并）"""
    _assert_jobs_enabled()
    payload = {
        k: v for k, v in req.dict(exclude_unset=True).items() if v is not None
    }
    if not payload:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    try:
        async with _gateway_session() as gateway:
            return await gateway.update_job(job_id, payload)
    except GatewayError as e:
        _raise_gateway_error(e)


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    """删除后台计划任务（同时取消进行中的 run）"""
    _assert_jobs_enabled()
    try:
        async with _gateway_session() as gateway:
            return await gateway.delete_job(job_id)
    except GatewayError as e:
        _raise_gateway_error(e)


@router.post("/jobs/{job_id}/{action}")
async def control_job(
    job_id: str,
    action: str,
    current_user: User = Depends(get_current_user),
):
    """任务操作：pause（暂停）/ resume（恢复）/ run（立即执行）"""
    _assert_jobs_enabled()
    try:
        async with _gateway_session() as gateway:
            return await gateway.control_job(job_id, action)
    except GatewayError as e:
        _raise_gateway_error(e)


# ==================== 附件管理 ====================


class AttachmentResponse(BaseModel):
    id: int
    kind: str  # image / document
    filename: str
    mime_type: Optional[str] = None
    file_size: int
    parse_status: str  # pending / parsed / failed / skipped
    parse_error: Optional[str] = None
    message_id: Optional[str] = None
    preview_url: str
    created_at: str


def _to_attachment_response(a) -> AttachmentResponse:
    return AttachmentResponse(
        id=a.id,
        kind=a.kind,
        filename=a.filename,
        mime_type=a.mime_type,
        file_size=a.file_size or 0,
        parse_status=a.parse_status or "pending",
        parse_error=a.parse_error,
        message_id=a.message_id,
        preview_url=f"/api/v1/hermes/attachments/{a.id}/preview",
        created_at=a.created_at.isoformat() if a.created_at else "",
    )


@router.post("/attachments", response_model=AttachmentResponse)
async def upload_attachment(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    上传会话附件

    先落盘再返回 id，客户端在 /stream 请求体里带 attachment_ids 引用。
    采用两步式是因为 SSE 端点为 POST + JSON，无法携带 multipart。

    图片与文档走不同链路：图片转 base64 送视觉模型，文档解析为文本注入。
    """
    data = await file.read()
    service = get_attachment_service(db)
    try:
        attachment = await service.create(
            user_id=current_user.id,
            filename=file.filename or "unnamed",
            data=data,
            mime_type=file.content_type,
        )
    except AttachmentError as e:
        # 业务校验失败（类型不允许 / 体积超限）统一返回 400
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"附件上传失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="附件上传失败")

    return _to_attachment_response(attachment)


@router.get("/attachments/{attachment_id}/preview")
def preview_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """预览/下载附件（校验归属，非本人返回 404）"""
    service = get_attachment_service(db)
    attachment = service.get_owned(attachment_id, current_user.id)
    if not attachment:
        raise HTTPException(status_code=404, detail="附件不存在")

    try:
        content = service.read_bytes(attachment)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="附件文件已丢失")

    return Response(
        content=content,
        media_type=attachment.mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/attachments/{attachment_id}")
def delete_attachment(
    attachment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除本人上传的附件"""
    service = get_attachment_service(db)
    if not service.delete(attachment_id, current_user.id):
        raise HTTPException(status_code=404, detail="附件不存在")
    return {"ok": True}


@router.get("/attachments", response_model=List[AttachmentResponse])
def list_attachments(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    列出某会话下的全部附件（含 message_id，供前端按消息关联展示）

    仅返回归属当前用户、或关联本会话的附件（attachment.user_id == current_user.id）
    """
    rows = (
        db.query(HermesAttachment)
        .filter(
            HermesAttachment.session_id == session_id,
            HermesAttachment.user_id == current_user.id,
        )
        .order_by(HermesAttachment.created_at)
        .all()
    )
    return [_to_attachment_response(a) for a in rows]


# ==================== 快捷提示词（日常任务） ====================


class QuickPromptCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    description: str = ""
    icon: str = ""
    category: str = "general"
    sort_order: int = 0


class QuickPromptUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


class QuickPromptResponse(BaseModel):
    id: int
    title: str
    description: str
    content: str
    icon: str
    category: str
    sort_order: int
    is_builtin: bool
    is_active: bool
    created_at: str
    updated_at: str


def _to_quick_prompt_response(p) -> QuickPromptResponse:
    return QuickPromptResponse(
        id=p.id,
        title=p.title,
        description=p.description or "",
        content=p.content,
        icon=p.icon or "",
        category=p.category or "general",
        sort_order=p.sort_order or 0,
        is_builtin=bool(p.is_builtin),
        is_active=bool(p.is_active),
        created_at=p.created_at.isoformat() if p.created_at else "",
        updated_at=p.updated_at.isoformat() if p.updated_at else "",
    )


@router.get("/quick-prompts", response_model=List[QuickPromptResponse])
def list_quick_prompts(
    category: str = "",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """列出可用提示词（内置 + 本人自建）"""
    service = get_quick_prompt_service(db)
    prompts = service.list_available(current_user.id, category or None)
    return [_to_quick_prompt_response(p) for p in prompts]


@router.post("/quick-prompts", response_model=QuickPromptResponse)
def create_quick_prompt(
    req: QuickPromptCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """新建个人提示词"""
    service = get_quick_prompt_service(db)
    prompt = service.create(
        user_id=current_user.id,
        title=req.title,
        content=req.content,
        description=req.description,
        icon=req.icon,
        category=req.category,
        sort_order=req.sort_order,
    )
    return _to_quick_prompt_response(prompt)


@router.put("/quick-prompts/{prompt_id}", response_model=QuickPromptResponse)
def update_quick_prompt(
    prompt_id: int,
    req: QuickPromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新本人提示词（内置提示词不允许修改）"""
    service = get_quick_prompt_service(db)
    prompt = service.get(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    if prompt.is_builtin:
        raise HTTPException(status_code=400, detail="内置提示词不可修改")
    if prompt.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权修改该提示词")

    updated = service.update(prompt_id, **req.dict(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="提示词不存在")
    return _to_quick_prompt_response(updated)


@router.delete("/quick-prompts/{prompt_id}")
def delete_quick_prompt(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除本人提示词（内置提示词不可删除）"""
    service = get_quick_prompt_service(db)
    prompt = service.get(prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="提示词不存在")
    if prompt.is_builtin:
        raise HTTPException(status_code=400, detail="内置提示词不可删除")

    if not service.delete(prompt_id, current_user.id):
        raise HTTPException(status_code=403, detail="无权删除该提示词")
    return {"ok": True}


@router.post("/quick-prompts/init-builtin")
def init_builtin_quick_prompts(db: Session = Depends(get_db)):
    """初始化内置默认提示词集（按标题去重，可重复调用）"""
    service = get_quick_prompt_service(db)
    added = service.init_builtin()
    return {"added": added, "total_builtin": len(BUILTIN_PROMPTS)}
