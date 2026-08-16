import os
from typing import Any, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.knowledge import Document, DocumentSegment, KnowledgeBase
from app.models.user import User
from app.schemas.knowledge import (
    DocumentResponse,
    DocumentSegmentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)
from app.schemas.pagination import CursorResponse
from app.services.knowledge import get_knowledge_service
from app.services.vector_store import vector_store_service
from app.utils.deps import get_current_user
from app.utils.pagination import apply_cursor_pagination

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".md", ".docx", ".html", ".txt"}
FILE_TYPE_MAP = {
    ".pdf": "pdf",
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",
    ".docx": "docx",
    ".html": "html",
    ".txt": "txt",
}


def _process_document_task(db: Session, document_id: int):
    """后台任务：处理文档"""
    import asyncio

    service = get_knowledge_service(db)
    asyncio.run(service.process_document(document_id))


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
    vector_store_service.delete_collection(kb_id)
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

    # 后台异步处理文档
    background_tasks.add_task(_process_document_task, db, document.id)

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
    """重新处理失败的文档"""
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

    if document.status not in ("failed", "completed"):
        raise HTTPException(status_code=400, detail="只能重试失败或已完成的文档")

    # 清除旧的分段
    db.query(DocumentSegment).filter(DocumentSegment.document_id == doc_id).delete()
    document.status = "pending"
    document.error_message = None
    document.chunk_count = 0
    db.commit()

    # 后台重新处理
    background_tasks.add_task(_process_document_task, db, doc_id)

    return {"message": "文档已加入重新处理队列"}


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge_base(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    kb_id: int,
    search_in: SearchRequest,
) -> Any:
    """知识库检索（混合向量 + 关键词）"""
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
    )

    return SearchResponse(
        query=search_in.query,
        results=[SearchResultItem(**r) for r in results],
        total=len(results),
    )
