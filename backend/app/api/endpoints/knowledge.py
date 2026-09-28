import os
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.knowledge import Document, DocumentSegment, KnowledgeBase
from app.models.user import User
from app.schemas.knowledge import (
    CrawlRequest,
    CrawlResponse,
    DocumentResponse,
    DocumentSegmentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    ChunkPreviewRequest,
    ChunkPreviewResponse,
    DocumentProcessRequest,
)
from app.schemas.pagination import CursorResponse
from app.services.knowledge import get_knowledge_service
from app.services.vector_store import get_vector_store_service
from app.utils.deps import get_current_user
from app.utils.pagination import apply_cursor_pagination

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".md", ".docx", ".html", ".txt", ".epub"}
FILE_TYPE_MAP = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",
    ".docx": "docx",
    ".html": "html",
    ".txt": "txt",
    ".epub": "epub",
}


async def _parse_document_task(document_id: int):
    """后台任务：解析文档为 Markdown（创建独立的 db session）"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = get_knowledge_service(db)
        await service.parse_document(document_id)
    finally:
        db.close()


async def _process_document_task(
    document_id: int,
    chunk_strategy: str = "sliding_window",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: Optional[List[str]] = None,
):
    """后台任务：处理文档分片和向量化（创建独立的 db session）"""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = get_knowledge_service(db)
        await service.process_document(
            document_id,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )
    finally:
        db.close()


@router.get("/", response_model=CursorResponse[KnowledgeBaseResponse])
def read_knowledge_bases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cursor: Optional[int] = Query(None, description="上一页最后一条记录的 ID"),
    limit: int = Query(default=20, ge=1, le=100),
) -> Any:
    """获取知识库列表（游标分页）"""
    query = db.query(KnowledgeBase).filter(KnowledgeBase.owner_id == current_user.id)

    items, next_cursor, has_more = apply_cursor_pagination(
        query, KnowledgeBase, cursor=cursor, limit=limit
    )

    return CursorResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/", response_model=KnowledgeBaseResponse)
def create_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_in: KnowledgeBaseCreate,
) -> Any:
    """创建知识库"""
    knowledge_base = KnowledgeBase(
        name=kb_in.name,
        description=kb_in.description,
        kb_type=kb_in.kb_type,
        api_endpoint=kb_in.api_endpoint,
        api_key=kb_in.api_key,
        api_config=kb_in.api_config,
        owner_id=current_user.id,
    )
    db.add(knowledge_base)
    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
def read_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
) -> Any:
    """获取知识库详情"""
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")
    return knowledge_base


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    kb_in: KnowledgeBaseUpdate,
) -> Any:
    """更新知识库"""
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    if kb_in.name is not None:
        knowledge_base.name = kb_in.name
    if kb_in.description is not None:
        knowledge_base.description = kb_in.description
    if kb_in.api_endpoint is not None:
        knowledge_base.api_endpoint = kb_in.api_endpoint
    if kb_in.api_key is not None:
        knowledge_base.api_key = kb_in.api_key
    if kb_in.api_config is not None:
        knowledge_base.api_config = kb_in.api_config

    db.commit()
    db.refresh(knowledge_base)
    return knowledge_base


@router.delete("/{kb_id}")
def delete_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
) -> Any:
    """删除知识库"""
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 删除关联文档的分段和文件
    documents = db.query(Document).filter(Document.knowledge_base_id == kb_id).all()
    for doc in documents:
        db.query(DocumentSegment).filter(DocumentSegment.document_id == doc.id).delete()
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass

    # 删除文档
    db.query(Document).filter(Document.knowledge_base_id == kb_id).delete()

    # 删除知识库
    db.delete(knowledge_base)

    # 清理向量数据
    get_vector_store_service().delete_collection(kb_id)
    db.commit()
    return {"message": "知识库已删除"}


@router.post("/{kb_id}/documents", response_model=DocumentResponse)
async def upload_document(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks,
) -> Any:
    """上传文档到知识库，并自动触发后台处理"""
    # 检查知识库是否存在
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 检查文件类型
    file_ext = "." + file.filename.split(".")[-1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {file_ext}，支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 保存文件
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(kb_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)

    content = await file.read()

    # 检查文件大小
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小超过限制: {settings.MAX_FILE_SIZE_MB}MB",
        )

    with open(file_path, "wb") as buffer:
        buffer.write(content)

    # 创建文档记录
    document = Document(
        knowledge_base_id=kb_id,
        name=file.filename,
        file_path=file_path,
        file_type=FILE_TYPE_MAP.get(file_ext, "txt"),
        file_size=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # 后台异步解析文档为 Markdown
    background_tasks.add_task(_parse_document_task, document.id)

    return document


@router.get("/{kb_id}/documents", response_model=CursorResponse[DocumentResponse])
def read_documents(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    cursor: Optional[int] = Query(None, description="上一页最后一条记录的 ID"),
    limit: int = Query(default=50, ge=1, le=100),
) -> Any:
    """获取知识库文档列表（游标分页）"""
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    query = db.query(Document).filter(Document.knowledge_base_id == kb_id)

    items, next_cursor, has_more = apply_cursor_pagination(
        query, Document, cursor=cursor, limit=limit
    )

    return CursorResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.delete("/{kb_id}/documents/{doc_id}")
def delete_document(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
) -> Any:
    """删除文档及其分段"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    service = get_knowledge_service(db)
    service.delete_document(doc_id)
    return {"message": "文档已删除"}


@router.get(
    "/{kb_id}/documents/{doc_id}/segments",
    response_model=CursorResponse[DocumentSegmentResponse],
)
def read_document_segments(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
    cursor: Optional[int] = Query(None, description="上一页最后一条记录的 ID"),
    limit: int = Query(default=50, ge=1, le=100),
) -> Any:
    """获取文档分段列表（游标分页）"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    query = db.query(DocumentSegment).filter(DocumentSegment.document_id == doc_id)

    items, next_cursor, has_more = apply_cursor_pagination(
        query, DocumentSegment, cursor=cursor, limit=limit
    )

    return CursorResponse(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("/{kb_id}/documents/{doc_id}/retry")
async def retry_document(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
    background_tasks: BackgroundTasks,
) -> Any:
    """重新解析失败的文档"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.status not in ("failed", "completed", "parsed"):
        raise HTTPException(status_code=400, detail="只能重试失败、已完成或已解析的文档")

    # 清除旧的分段
    db.query(DocumentSegment).filter(DocumentSegment.document_id == doc_id).delete()

    if not document.file_path and document.content:
        # 纯内容型文档（无源文件，content 即正文，如客服知识库自动生成文档）：
        # 直接重新分片 + 向量化，切勿清空 content，否则 parse_document 会因
        # 「既无 file_path 又无 content」而报「缺少文件路径且文档内容为空」。
        document.status = "pending"
        document.error_message = None
        document.chunk_count = 0
        db.commit()
        background_tasks.add_task(
            _process_document_task, doc_id, "sliding_window", 500, 50, None
        )
        return {"message": "文档已加入重新处理队列"}

    document.status = "pending"
    document.error_message = None
    document.chunk_count = 0
    document.content = None
    db.commit()

    # 后台重新解析（有源文件的文档从文件重新读取）
    background_tasks.add_task(_parse_document_task, doc_id)

    return {"message": "文档已加入重新解析队列"}


@router.get("/{kb_id}/documents/{doc_id}/content")
def get_document_content(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
) -> Any:
    """获取文档解析后的内容（Markdown）"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    return {
        "id": document.id,
        "name": document.name,
        "content": document.content or "",
        "status": document.status,
    }


@router.post("/{kb_id}/documents/{doc_id}/chunks/preview")
def preview_document_chunks(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
    preview_in: ChunkPreviewRequest,
) -> Any:
    """预览文档分片效果"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.status not in ("parsed", "completed", "failed"):
        raise HTTPException(status_code=400, detail="文档未解析，请先上传或重试")

    service = get_knowledge_service(db)
    try:
        chunks = service.preview_chunks(
            document_id=doc_id,
            chunk_strategy=preview_in.chunk_strategy,
            chunk_size=preview_in.chunk_size,
            chunk_overlap=preview_in.chunk_overlap,
            separators=preview_in.separators,
        )
        return ChunkPreviewResponse(
            total_chunks=len(chunks),
            chunks=chunks,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{kb_id}/documents/{doc_id}/process")
async def process_document_chunks(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    doc_id: int,
    process_in: DocumentProcessRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """确认分片策略，开始处理文档（分片 + 向量化）"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    document = (
        db.query(Document)
        .filter(Document.id == doc_id, Document.knowledge_base_id == kb_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    if document.status not in ("parsed", "failed", "completed"):
        raise HTTPException(status_code=400, detail="文档状态不正确，需要先解析文档")

    # 清除旧的分段（如果有的话）
    db.query(DocumentSegment).filter(DocumentSegment.document_id == doc_id).delete()
    db.commit()

    # 后台处理文档
    background_tasks.add_task(
        _process_document_task,
        doc_id,
        process_in.chunk_strategy,
        process_in.chunk_size,
        process_in.chunk_overlap,
        process_in.separators,
    )

    return {"message": "文档已加入处理队列"}


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    search_in: SearchRequest,
) -> Any:
    """知识库检索（支持 vector / bm25 / rrf 三种模式）"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    service = get_knowledge_service(db)
    results = await service.search(
        kb_id=kb_id,
        query=search_in.query,
        top_k=search_in.top_k,
        score_threshold=search_in.score_threshold,
        search_mode=search_in.search_mode,
        enable_rerank=search_in.enable_rerank,
    )

    return SearchResponse(
        query=search_in.query,
        results=[SearchResultItem(**r) for r in results],
        total=len(results),
        search_mode=search_in.search_mode,
        enable_rerank=search_in.enable_rerank,
    )


# ------------------------------------------------------------------
# URL 爬取
# ------------------------------------------------------------------

async def _crawl_and_process_task(kb_id: int, crawl_request: CrawlRequest):
    """后台任务：爬取 URL → 创建文档 → 处理分段（创建独立的 db session）"""
    from app.core.database import SessionLocal
    from app.services.crawler import WebCrawler
    from app.services.knowledge import KnowledgeService

    crawler = WebCrawler()
    crawl_result = await crawler.crawl(
        start_url=crawl_request.url,
        max_depth=crawl_request.max_depth,
        max_pages=crawl_request.max_pages,
    )

    db = SessionLocal()
    try:
        service = KnowledgeService(db)
        doc_ids = []

        for page in crawl_result.pages:
            document = Document(
                knowledge_base_id=kb_id,
                name=page.title[:200] if page.title else page.url[:200],
                file_type="txt",
                source_type="url",
                url=page.url,
                file_size=len(page.content.encode("utf-8")),
                status="pending",
                content=page.content,
            )
            db.add(document)
            db.flush()

            try:
                # 爬取的内容已经直接设置到 content 字段，直接处理分片
                await service.process_document(document.id)
                doc_ids.append(document.id)
            except Exception as e:
                document.status = "failed"
                document.error_message = str(e)[:500]
                db.commit()

        db.commit()
    finally:
        db.close()


@router.post("/{kb_id}/crawl", response_model=CrawlResponse)
async def crawl_url(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    crawl_in: CrawlRequest,
    background_tasks: BackgroundTasks,
) -> Any:
    """爬取网站内容并导入知识库"""
    # 验证知识库归属
    knowledge_base = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.id == kb_id, KnowledgeBase.owner_id == current_user.id)
        .first()
    )
    if not knowledge_base:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 验证 URL 格式
    from urllib.parse import urlparse
    parsed = urlparse(crawl_in.url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise HTTPException(status_code=400, detail="无效的 URL")

    background_tasks.add_task(_crawl_and_process_task, kb_id, crawl_in)

    return CrawlResponse(
        message=f"已开始爬取 {crawl_in.url}，最大深度 {crawl_in.max_depth}，最多 {crawl_in.max_pages} 页",
        total_pages=0,
        document_ids=[],
    )
