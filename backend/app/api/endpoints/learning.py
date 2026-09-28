"""
学习助手端点

路由前缀 /api/v1/learning

分层约定：端点只做参数校验（Pydantic）、调用 Service、序列化返回；
业务逻辑全部在 app/services/learning.py 及其下游 media / subtitle / document_page。
"""

import os
from typing import AsyncGenerator, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.models.learning import (
    DocumentFileType,
    LearningChatMessage,
    LearningResource,
    LearningSession,
    ResourceType,
)
from app.models.user import User
from app.schemas.learning import (
    ChatAskRequest,
    ChatHistoryResponse,
    ChatMessageResponse,
    ClearHistoryResponse,
    DocumentMetaResponse,
    DocumentOutlineItem,
    DocumentPageResponse,
    DrawNoteBatchResponse,
    DrawNoteBatchSave,
    ExportNoteCreate,
    LearningReference,
    NoteResponse,
    PageOption,
    PageOptionListResponse,
    NoteTimelineItem,
    NoteTimelineResponse,
    PageBlock,
    ProgressReport,
    ProgressResponse,
    RecordResourceItem,
    RecordSessionItem,
    ResourceListResponse,
    ResourceResponse,
    ResourceUpdateRequest,
    StatsResponse,
    SuggestedQuestionsResponse,
    TextNoteCreate,
    TextNoteUpdate,
    TranscriptCue,
    TranscriptResponse,
    UrlImportRequest,
)
from app.services import document_page as document_page_module
from app.services.learning import LearningService, get_learning_service
from app.services.learning_chat import get_learning_chat_service
from app.services.learning_index import build_index_async
from app.utils.deps import get_current_user
from app.utils.logger import logger

router = APIRouter()

_SUBTITLE_UPLOAD_LIMIT_MB = 5


def _resource_payload(resource: LearningResource, stats: dict) -> ResourceResponse:
    """组装资源响应（ORM + 统计 → Pydantic）"""
    return ResourceResponse(
        id=resource.id,
        user_id=resource.user_id,
        type=resource.type,
        source=resource.source,
        title=resource.title,
        description=resource.description or "",
        cover_url=resource.cover_url,
        source_url=resource.source_url,
        file_type=resource.file_type,
        file_size=resource.file_size,
        page_count=resource.page_count,
        duration_seconds=resource.duration_seconds,
        platform_id=resource.platform_id,
        subtitle_tracks=resource.subtitle_tracks,
        status=resource.status,
        error_message=resource.error_message,
        created_at=resource.created_at,
        updated_at=resource.updated_at,
        progress_percent=stats["progress_percent"],
        total_seconds=stats["total_seconds"],
        note_count=stats["note_count"],
        last_studied_at=stats["last_studied_at"],
    )


# ==================================================================
# 资源
# ==================================================================


@router.get("/resources", response_model=ResourceListResponse, summary="学习资源列表")
def list_resources(
    type: Optional[str] = Query(None, description="video / document"),
    keyword: Optional[str] = Query(None, max_length=100),
    sort: str = Query("recent_studied", description="recent_studied / recent_created / progress"),
    cursor: Optional[int] = Query(None, ge=0),
    limit: int = Query(24, ge=1, le=60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resources, next_cursor, has_more, stats = service.list_resources(
        current_user.id,
        type_filter=type,
        keyword=keyword,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )
    items = [_resource_payload(item, stats[item.id]) for item in resources]
    return ResourceListResponse(items=items, next_cursor=next_cursor, has_more=has_more)


@router.post("/resources/url", response_model=ResourceResponse, summary="通过 URL 导入视频")
def create_resource_from_url(
    data: UrlImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resource = service.create_from_url(current_user.id, data)
    # 抓取耗时可达数十秒，丢到后台任务；前端轮询 resource.status 等待就绪
    background_tasks.add_task(service.hydrate_from_url, resource.id, data.languages)
    resource, stats = service.get_resource_with_stats(resource.id, current_user.id)
    return _resource_payload(resource, stats)


@router.post("/resources/document", response_model=ResourceResponse, summary="上传文档")
def create_resource_from_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resource = service.create_from_upload(current_user.id, file)
    _, stats = service.get_resource_with_stats(resource.id, current_user.id)
    return _resource_payload(resource, stats)


@router.get("/resources/{resource_id}", response_model=ResourceResponse, summary="资源详情")
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resource, stats = service.get_resource_with_stats(resource_id, current_user.id)
    return _resource_payload(resource, stats)


@router.patch("/resources/{resource_id}", response_model=ResourceResponse, summary="更新资源信息")
def update_resource(
    resource_id: int,
    data: ResourceUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resource = service.update_resource(
        resource_id, current_user.id, data.title, data.description
    )
    _, stats = service.get_resource_with_stats(resource_id, current_user.id)
    return _resource_payload(resource, stats)


@router.delete("/resources/{resource_id}", status_code=204, summary="删除资源")
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_learning_service(db).delete_resource(resource_id, current_user.id)


# ==================================================================
# 字幕
# ==================================================================


@router.get(
    "/resources/{resource_id}/transcripts",
    response_model=TranscriptResponse,
    summary="资源字幕",
)
def list_transcripts(
    resource_id: int,
    language: Optional[str] = Query(None, max_length=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    cues, tracks, translations = service.list_transcripts(
        resource_id, current_user.id, language
    )
    return TranscriptResponse(
        resource_id=resource_id,
        language=language
        or (cues[0].language if cues else (tracks[0].lang if tracks else "")),
        cues=[
            TranscriptCue(
                id=cue.id,
                seq=cue.seq,
                start_ms=cue.start_ms,
                end_ms=cue.end_ms,
                text=cue.text,
                language=cue.language,
                source=cue.source,
                # 时间对齐后的译文，双语展示的副行
                translation=translations.get(cue.id, ""),
            )
            for cue in cues
        ],
        tracks=tracks,
    )


@router.post(
    "/resources/{resource_id}/transcripts/upload", summary="手动上传 SRT/VTT 字幕"
)
def upload_subtitle(
    resource_id: int,
    file: UploadFile = File(...),
    language: str = Form("manual", max_length=20),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    raw = file.file.read()
    limit = _SUBTITLE_UPLOAD_LIMIT_MB * 1024 * 1024
    if len(raw) > limit:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"字幕文件超过 {_SUBTITLE_UPLOAD_LIMIT_MB}MB 上限",
        )

    text = raw.decode("utf-8", errors="ignore")
    service = get_learning_service(db)
    count = service.upload_manual_subtitle(resource_id, current_user.id, text, language)
    logger.info(f"手动上传字幕 resource={resource_id} count={count}")
    return {"resource_id": resource_id, "count": count, "language": language}


# ==================================================================
# 文档分页
# ==================================================================


@router.get("/resources/{resource_id}/file", summary="文档原文件")
def get_document_file(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    返回文档原文件（PDF 由前端 pdfjs 直接渲染，故必须能取到原始字节）

    与 /assets 同理走鉴权端点，不静态挂载 uploads 目录。
    """
    service = get_learning_service(db)
    resource = service.get_resource(resource_id, current_user.id)
    if resource.type != ResourceType.DOCUMENT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该资源不是文档")
    if not resource.file_path or not os.path.isfile(resource.file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档文件不存在")

    return FileResponse(resource.file_path, filename=f"{resource.title}{_file_suffix(resource)}")


def _file_suffix(resource: LearningResource) -> str:
    return {
        DocumentFileType.PDF: ".pdf",
        DocumentFileType.PPTX: ".pptx",
        DocumentFileType.EPUB: ".epub",
        DocumentFileType.MARKDOWN: ".md",
    }.get(resource.file_type or "", "")


@router.get(
    "/resources/{resource_id}/meta",
    response_model=DocumentMetaResponse,
    summary="文档页数与大纲",
)
def get_document_meta(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    page_count, outline = service.get_document_meta(resource_id, current_user.id)
    resource = service.get_resource(resource_id, current_user.id)
    return DocumentMetaResponse(
        resource_id=resource_id,
        file_type=resource.file_type or DocumentFileType.PDF,
        page_count=page_count,
        outline=[DocumentOutlineItem(**item) for item in outline],
    )


@router.get(
    "/resources/{resource_id}/pages/{page_index}",
    response_model=DocumentPageResponse,
    summary="文档单页内容",
)
def get_document_page(
    resource_id: int,
    page_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    page = service.get_document_page(resource_id, current_user.id, page_index)
    blocks = [PageBlock(**block) for block in page.get("blocks", [])]
    raw = page.get("raw", "")
    html = page.get("html", "")
    if len(html) > settings.LEARNING_MAX_PAGE_CHARS:
        html = html[: settings.LEARNING_MAX_PAGE_CHARS]
    if len(raw) > settings.LEARNING_MAX_PAGE_CHARS:
        raw = raw[: settings.LEARNING_MAX_PAGE_CHARS]

    return DocumentPageResponse(
        resource_id=resource_id,
        file_type=page["file_type"],
        page_count=page["page_count"],
        page_index=page["page_index"],
        width=page.get("width", 1.0),
        height=page.get("height", 1.0),
        title=page.get("title", ""),
        html=html,
        raw=raw,
        blocks=blocks,
    )


# ==================================================================
# 笔记
# ==================================================================


@router.get(
    "/resources/{resource_id}/notes",
    response_model=List[NoteResponse],
    summary="资源笔记列表",
)
def list_notes(
    resource_id: int,
    kind: Optional[str] = Query(None, description="draw / text / export"),
    page_index: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    return service.list_resource_notes(resource_id, current_user.id, kind, page_index)


@router.get(
    "/resources/{resource_id}/notes/draw",
    response_model=DrawNoteBatchResponse,
    summary="整页矢量标注",
)
def list_draw_notes(
    resource_id: int,
    page_index: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    shapes = service.list_draw_page(resource_id, current_user.id, page_index)
    return DrawNoteBatchResponse(resource_id=resource_id, page_index=page_index, shapes=shapes)


@router.post(
    "/resources/{resource_id}/notes/draw",
    response_model=DrawNoteBatchResponse,
    summary="整页矢量标注全量保存",
)
def save_draw_notes(
    resource_id: int,
    data: DrawNoteBatchSave,
    page_index: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    shapes = service.save_draw_page(resource_id, current_user.id, page_index, data)
    return DrawNoteBatchResponse(resource_id=resource_id, page_index=page_index, shapes=shapes)


@router.post(
    "/resources/{resource_id}/notes/text", response_model=NoteResponse, summary="创建文本便签"
)
def create_text_note(
    resource_id: int,
    data: TextNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    data.resource_id = resource_id
    return service.create_text_note(current_user.id, data)


@router.post(
    "/resources/{resource_id}/notes/export", response_model=NoteResponse, summary="画布截图导出"
)
def create_export_note(
    resource_id: int,
    data: ExportNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    data.resource_id = resource_id
    return service.create_export_note(current_user.id, data)


@router.patch("/notes/{note_id}", response_model=NoteResponse, summary="更新笔记")
def update_note(
    note_id: int,
    data: TextNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    return service.update_text_note(note_id, current_user.id, data)


@router.delete("/notes/{note_id}", status_code=204, summary="删除笔记")
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_learning_service(db).delete_note(note_id, current_user.id)


# ==================================================================
# 静态资产（文档内联图片 / 导出图）
# ==================================================================


@router.get("/assets/{resource_id}/{name}", summary="资源附属文件")
def get_asset(
    resource_id: int,
    name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    读取资源目录下的图片

    走带鉴权的端点而非静态挂载：避免暴露 uploads 下其他模块的私有文件。
    """
    # 路径穿越防护：只允许单层文件名
    if "/" in name or "\\" in name or ".." in name or name.startswith("."):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法的文件名")

    get_learning_service(db).get_resource(resource_id, current_user.id)

    base = document_page_module.resource_dir(resource_id)
    candidates = [os.path.join(base, "assets", name), os.path.join(base, "exports", name)]
    path = next((item for item in candidates if os.path.isfile(item)), None)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")

    media_type = "image/jpeg"
    if name.lower().endswith(".png"):
        media_type = "image/png"
    elif name.lower().endswith(".webp"):
        media_type = "image/webp"
    elif name.lower().endswith(".gif"):
        media_type = "image/gif"
    return FileResponse(path, media_type=media_type)


# ==================================================================
# 学习进度与会话
# ==================================================================


@router.post(
    "/resources/{resource_id}/progress",
    response_model=ProgressResponse,
    summary="进度心跳上报",
)
def report_progress(
    resource_id: int,
    data: ProgressReport,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    resource, progress = service.report_progress(resource_id, current_user.id, data)
    return ProgressResponse(
        resource_id=resource_id,
        position=progress.position,
        total_seconds=progress.total_seconds,
        is_finished=progress.is_finished,
        percent=service.compute_percent(resource, progress.position),
        updated_at=progress.updated_at,
    )


@router.post("/resources/{resource_id}/progress/close", summary="结束学习会话")
def close_session(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_learning_service(db).close_idle_session(resource_id, current_user.id)
    return {"resource_id": resource_id, "closed": True}


@router.get(
    "/resources/{resource_id}/sessions",
    response_model=List[RecordSessionItem],
    summary="资源学习会话明细",
)
def list_sessions(
    resource_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_learning_service(db)
    sessions: List[LearningSession] = service.list_resource_sessions(
        resource_id, current_user.id, limit
    )
    return [
        RecordSessionItem(
            id=item.id,
            started_at=item.started_at,
            ended_at=item.ended_at,
            seconds=item.seconds,
            start_position=item.start_position,
            end_position=item.end_position,
        )
        for item in sessions
    ]


# ==================================================================
# 学习记录与统计
# ==================================================================


@router.get("/records", response_model=List[RecordResourceItem], summary="学习记录列表")
def list_records(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = get_learning_service(db).list_records(current_user.id, limit)
    return [RecordResourceItem(**item) for item in records]


@router.get("/stats", response_model=StatsResponse, summary="学习统计")
def get_stats(
    heatmap_days: int = Query(182, ge=30, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_learning_service(db).get_stats(current_user.id, heatmap_days)


@router.get(
    "/notes/timeline", response_model=NoteTimelineResponse, summary="跨资源笔记时间线"
)
def list_note_timeline(
    kind: Optional[str] = Query(None, description="draw / text / export"),
    cursor: Optional[int] = Query(None, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service: LearningService = get_learning_service(db)
    items: List[NoteTimelineItem]
    items, next_cursor, has_more = service.list_note_timeline(
        current_user.id, kind, cursor, limit
    )
    return NoteTimelineResponse(items=items, next_cursor=next_cursor, has_more=has_more)


# ==================================================================
# AI 问答
# ==================================================================


def _message_payload(row: LearningChatMessage) -> ChatMessageResponse:
    """ORM 消息 → 响应模型（references 是 JSON 列，需显式转换）"""
    return ChatMessageResponse(
        id=row.id,
        role=row.role,
        content=row.content,
        references=[LearningReference(**item) for item in (row.references or [])],
        model=row.model,
        error=row.error,
        created_at=row.created_at,
    )


@router.post("/resources/{resource_id}/chat/stream", summary="AI 问答（SSE 流式）")
async def chat_stream(
    resource_id: int,
    data: ChatAskRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    围绕当前资源问答，返回 SSE 流

    事件顺序：
    - references: 引用来源（先于答案发出，用户可提前点击跳转）
    - delta     : 答案增量文本
    - done      : 完成，含 message_id 与耗时
    - error     : 出错（模型不可用、调用失败等）
    """
    resource = get_learning_service(db).get_resource(resource_id, current_user.id)

    # 首次提问时后台构建向量索引；本次先用关键词降级，不阻塞用户拿到答案
    if get_learning_chat_service(db).index_service.needs_build(resource):
        background_tasks.add_task(build_index_async, resource.id)

    # 流式期间用独立 Session：Depends(get_db) 的会话可能在响应返回后就被回收，
    # 而 SSE 生成器还要持续写库（保存提问与回答）。
    stream_db = SessionLocal()
    service = get_learning_chat_service(stream_db)
    # ORM 实例绑定在各自的 Session 上，流式会话不能复用请求 Session 查出来的对象
    stream_resource = get_learning_service(stream_db).get_resource(
        resource_id, current_user.id
    )

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for chunk in service.chat_stream(
                resource=stream_resource,
                user_id=current_user.id,
                query=data.query,
                position=data.position,
                model_id=data.model_id,
                context_refs=data.context_refs,
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


@router.get(
    "/resources/{resource_id}/chat/messages",
    response_model=ChatHistoryResponse,
    summary="问答历史",
)
def list_chat_messages(
    resource_id: int,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_learning_service(db).get_resource(resource_id, current_user.id)
    rows = get_learning_chat_service(db).list_messages(
        resource_id, current_user.id, limit
    )
    return ChatHistoryResponse(
        resource_id=resource_id, messages=[_message_payload(row) for row in rows]
    )


@router.delete(
    "/resources/{resource_id}/chat/messages",
    response_model=ClearHistoryResponse,
    summary="清空问答历史",
)
def clear_chat_messages(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_learning_service(db).get_resource(resource_id, current_user.id)
    deleted = get_learning_chat_service(db).clear_messages(resource_id, current_user.id)
    return ClearHistoryResponse(deleted=deleted)


@router.post(
    "/resources/{resource_id}/transcripts/translate",
    summary="生成中文字幕（AI 翻译）",
)
async def translate_transcripts(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    用平台已配模型把原文字幕翻译成中文，供双语对照

    幂等：已有译文则直接跳过。导入时会自动跑一次，
    这里供「当时没配模型、后来配好了」的场景手动补。
    """
    resource = get_learning_service(db).get_resource(resource_id, current_user.id)
    if resource.type != ResourceType.VIDEO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该资源不是视频"
        )
    count = await get_learning_chat_service(db).translate_transcripts(resource)
    return {"resource_id": resource_id, "count": count}


@router.get(
    "/resources/{resource_id}/pages",
    response_model=PageOptionListResponse,
    summary="文档分页列表（供 AI 上下文选择）",
)
def list_page_options(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """列出文档各页，供助手的 @ 选择器挑选要加入上下文的页"""
    resource = get_learning_service(db).get_resource(resource_id, current_user.id)
    if resource.type != ResourceType.DOCUMENT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="该资源不是文档"
        )
    items = get_learning_chat_service(db).list_page_options(resource)
    return PageOptionListResponse(
        resource_id=resource_id,
        items=[PageOption(**item) for item in items],
    )


@router.get(
    "/resources/{resource_id}/chat/suggestions",
    response_model=SuggestedQuestionsResponse,
    summary="推荐问题",
)
async def get_suggested_questions(
    resource_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取该资源推荐的 3 个问题

    由 LLM 基于标题与内容摘要生成并缓存；模型不可用或超时时回退固定模板，
    保证「打开助手」永远有内容可点。
    """
    resource = get_learning_service(db).get_resource(resource_id, current_user.id)
    questions = await get_learning_chat_service(db).suggest_questions(resource)
    return SuggestedQuestionsResponse(resource_id=resource_id, questions=questions)
