"""
学习资源 AI 索引服务

为「AI 学习助手问答」提供检索能力。核心设计：

1. **虚拟 kb_id**
   学习资源不建 knowledge_bases 记录（否则会污染用户的知识库列表），而是把
   resource_id 映射到一个高位 kb_id 后直接操作向量库。之所以不能直接复用
   resource_id，是因为真实知识库的 id 也从 1 自增，两者会撞车。

2. **三态索引 + 优雅降级**
   pending → 首次提问时后台构建 → ready / unavailable。
   embedding 依赖本地模型（fastembed，`local_files_only=True`），模型缺失时
   构建必然失败。此时置 unavailable，检索退化为「数据库关键词召回」，
   问答依然可用（只是召回质量下降），绝不因此让问答接口报错。

3. **统一引用契约**
   文档与视频都产出同一种 Reference 结构，靠 type 区分定位方式，
   供问答服务拼上下文、供前端渲染可跳转的引用胶囊。
"""

import asyncio
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.learning import (
    IndexStatus,
    LearningPageText,
    LearningResource,
    LearningTranscript,
    ResourceType,
    TranscriptSource,
)
from app.services.document_page import get_document_page_service
from app.services.vector_store import get_vector_store_service
from app.utils.logger import logger

# 引用片段展示长度：够说明问题，又不至于把上下文撑爆
SNIPPET_CHARS = 400

# 切分时优先在此类标点处断句，避免把句子拦腰截断
_SENTENCE_ENDS = ("\n", "。", "！", "？", "；", ". ", "! ", "? ")


def _split_text(text: str, max_chars: int) -> List[str]:
    """按最大字符数切分长文本，尽量在换行或句末处断开"""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    pieces: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            # 只在后半段找断点，避免切出大量碎片段
            cut = -1
            cut_end = -1
            for marker in _SENTENCE_ENDS:
                found = text.rfind(marker, start + max_chars // 2, end)
                if found > cut:
                    cut = found
                    cut_end = found + len(marker)
            if cut > start:
                # 断点连同标点一起吃掉；越界则退化为断在标点前
                end = cut_end if cut_end <= end else cut + 1
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        start = end
    return pieces


def _extract_terms(query: str, limit: int = 5) -> List[str]:
    """
    从问题里抽检索词，供关键词降级召回使用

    中文没有空格分词，长句直接 LIKE 几乎必然落空，故把长片段再切成 6 字滑窗；
    英文/数字按空白与标点切分即可。
    """
    parts = re.split(r"[\s，。？！、；：,.?!;:()（）\"'「」【】《》]+", query or "")
    terms = [part for part in parts if len(part) >= 2]
    if not terms:
        return [query[:12]] if query else []

    expanded: List[str] = []
    for term in terms:
        if len(term) <= 8:
            expanded.append(term)
        else:
            expanded.extend(term[i : i + 6] for i in range(0, len(term) - 5, 4))

    seen = set()
    result: List[str] = []
    for term in expanded:
        if term not in seen:
            seen.add(term)
            result.append(term)
    return result[:limit]


def _keyword_score(text: str, terms: List[str]) -> int:
    """命中了几个检索词（用于降级排序）"""
    return sum(1 for term in terms if term and term in text)


class LearningIndexService:
    """学习资源索引服务（依赖 DB Session）"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def kb_id(resource_id: int) -> int:
        """资源 → 虚拟 kb_id，避开真实知识库的自增 id 区间"""
        return settings.LEARNING_KB_ID_BASE + int(resource_id)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    def needs_build(self, resource: LearningResource) -> bool:
        """是否还没建过索引（首次提问时触发后台构建）"""
        return resource.index_status == IndexStatus.PENDING

    def ensure_page_texts(self, resource: LearningResource) -> int:
        """
        确保文档页面文本已落库（解析一次复用），返回页数

        推荐问题与关键词降级都依赖它：文档解析不便宜，能少解析一次是一次。
        """
        count = (
            self.db.query(func.count(LearningPageText.id))
            .filter(LearningPageText.resource_id == resource.id)
            .scalar()
            or 0
        )
        if count:
            return int(count)
        return len(self._extract_and_store_page_texts(resource))

    def build_index(self, resource: LearningResource) -> str:
        """
        构建（重建）索引，返回最终状态

        全流程吞异常：索引是加速手段，构建失败只应降级，不能影响问答主流程。
        """
        try:
            if resource.type == ResourceType.DOCUMENT:
                chunks = self._chunks_from_pages(resource)
            else:
                chunks = self._chunks_from_transcripts(resource)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"索引内容抽取失败 resource={resource.id}: {exc}")
            return self._mark_unavailable(resource, f"内容抽取失败：{exc}")

        if not chunks:
            return self._mark_unavailable(resource, "未抽取到任何文本内容")

        if len(chunks) > settings.LEARNING_INDEX_MAX_CHUNKS:
            logger.warning(
                f"索引片段超限，截断 resource={resource.id} "
                f"{len(chunks)}→{settings.LEARNING_INDEX_MAX_CHUNKS}"
            )
            chunks = chunks[: settings.LEARNING_INDEX_MAX_CHUNKS]

        kb_id = self.kb_id(resource.id)
        store = get_vector_store_service()
        try:
            # 全量重建：先清旧集合，避免内容更新后残留过期片段
            store.delete_collection(kb_id)
            store.add_texts(
                kb_id=kb_id,
                texts=[chunk["text"] for chunk in chunks],
                metadatas=[chunk["metadata"] for chunk in chunks],
                ids=[f"{resource.id}-{index}" for index in range(len(chunks))],
            )
        except Exception as exc:  # noqa: BLE001 - embedding 模型缺失等
            logger.warning(f"向量索引构建失败，降级为关键词召回 resource={resource.id}: {exc}")
            return self._mark_unavailable(resource, str(exc)[:500])

        resource.index_status = IndexStatus.READY
        resource.index_error = None
        resource.index_chunk_count = len(chunks)
        self.db.commit()
        logger.info(f"索引构建完成 resource={resource.id} chunks={len(chunks)}")
        return IndexStatus.READY

    def _mark_unavailable(self, resource: LearningResource, reason: str) -> str:
        resource.index_status = IndexStatus.UNAVAILABLE
        resource.index_error = reason[:1000]
        resource.index_chunk_count = 0
        self.db.commit()
        return IndexStatus.UNAVAILABLE

    # ------------------------------------------------------------------
    # 切片
    # ------------------------------------------------------------------

    def _chunks_from_pages(self, resource: LearningResource) -> List[Dict[str, Any]]:
        """文档：页面纯文本 → 切片

        页面文本优先取自 learning_page_texts（解析一次复用）；
        为空说明尚未抽取过，此时才真正解析文档并落库。
        """
        rows = (
            self.db.query(LearningPageText)
            .filter(LearningPageText.resource_id == resource.id)
            .order_by(LearningPageText.page_index.asc())
            .all()
        )
        if not rows:
            rows = self._extract_and_store_page_texts(resource)

        max_chars = settings.LEARNING_INDEX_CHUNK_CHARS
        chunks: List[Dict[str, Any]] = []
        for row in rows:
            for piece in _split_text(row.content, max_chars):
                chunks.append(
                    {
                        "text": piece,
                        "metadata": {
                            "type": "page",
                            "page_index": row.page_index,
                            "title": row.title,
                            "resource_id": resource.id,
                        },
                    }
                )
        return chunks

    def _extract_and_store_page_texts(
        self, resource: LearningResource
    ) -> List[LearningPageText]:
        """解析文档全文并落库（供索引与降级检索复用，避免重复解析）"""
        texts = get_document_page_service().extract_page_texts(resource)

        # 先清后写：页数可能因重新上传而变化，残留旧页会污染检索
        self.db.query(LearningPageText).filter(
            LearningPageText.resource_id == resource.id
        ).delete(synchronize_session=False)

        objects = [
            LearningPageText(
                resource_id=resource.id,
                page_index=item["page_index"],
                title=(item.get("title") or "")[:500],
                content=item.get("content") or "",
                char_count=len(item.get("content") or ""),
            )
            for item in texts
        ]
        for start in range(0, len(objects), 200):
            self.db.bulk_save_objects(objects[start : start + 200])
        self.db.commit()
        return objects

    def _chunks_from_transcripts(self, resource: LearningResource) -> List[Dict[str, Any]]:
        """视频：字幕按时间窗聚合 → 切片

        逐条字幕太碎（一句话一片段），按 30s 窗口聚合后语义更完整，
        且引用时能给出有意义的时间区间。
        """
        rows = (
            self.db.query(LearningTranscript)
            .filter(LearningTranscript.resource_id == resource.id)
            .order_by(LearningTranscript.start_ms.asc())
            .all()
        )
        if not rows:
            return []

        # 只索引原文轨道：AI 译文与原文时间轴完全重合，
        # 混进来会让每个片段中英夹杂、检索结果成倍重复。
        cues = [row for row in rows if row.source != TranscriptSource.LLM]
        if cues:
            original_lang = cues[0].language
            cues = [row for row in cues if row.language == original_lang]
        if not cues:
            return []

        window_ms = settings.LEARNING_INDEX_WINDOW_MS
        groups: List[List[LearningTranscript]] = []
        current: List[LearningTranscript] = []
        window_start: Optional[int] = None

        for cue in cues:
            if window_start is None:
                window_start = cue.start_ms
            if current and cue.start_ms - window_start > window_ms:
                groups.append(current)
                current = []
                window_start = cue.start_ms
            current.append(cue)
        if current:
            groups.append(current)

        max_chars = settings.LEARNING_INDEX_CHUNK_CHARS
        chunks: List[Dict[str, Any]] = []
        for group in groups:
            text = "\n".join(cue.text for cue in group if cue.text)
            if not text.strip():
                continue
            start_ms = group[0].start_ms
            end_ms = group[-1].end_ms
            for piece in _split_text(text, max_chars):
                chunks.append(
                    {
                        "text": piece,
                        "metadata": {
                            "type": "transcript",
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "title": "",
                            "resource_id": resource.id,
                        },
                    }
                )
        return chunks

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    async def search(
        self, resource: LearningResource, query: str, top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """统一检索入口：优先向量，不可用时自动降级为关键词召回"""
        top_k = top_k or settings.LEARNING_CHAT_TOP_K
        # 先把需要的标量取出：ORM 对象跨线程再访问属性可能触发惰性加载而报错
        resource_id = resource.id
        resource_type = resource.type
        status = resource.index_status

        if status == IndexStatus.READY:
            items = await asyncio.to_thread(
                self._vector_search, resource_id, query, top_k
            )
            if items:
                return items
            # 有索引却没召回（如问题里全是停用词），退回关键词而非直接返回空

        return self._keyword_search(resource_id, resource_type, query, top_k)

    def _vector_search(
        self, resource_id: int, query: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """向量检索（在线程中执行：embedding 推理是 CPU 密集）"""
        try:
            store = get_vector_store_service()
            raw = store.similarity_search(
                kb_id=self.kb_id(resource_id), query=query, k=top_k
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"向量检索失败，降级关键词召回 resource={resource_id}: {exc}")
            return []
        return [self._to_reference(item) for item in raw]

    @staticmethod
    def _to_reference(item: Dict[str, Any]) -> Dict[str, Any]:
        metadata = item.get("metadata") or {}
        content = item.get("content") or ""
        return {
            "type": metadata.get("type", "page"),
            "page_index": metadata.get("page_index"),
            "start_ms": metadata.get("start_ms"),
            "end_ms": metadata.get("end_ms"),
            "title": metadata.get("title") or "",
            "snippet": content[:SNIPPET_CHARS],
            "score": float(item.get("score") or 0.0),
        }

    def _keyword_search(
        self, resource_id: int, resource_type: str, query: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """关键词降级召回：直接查库，不依赖 embedding"""
        terms = _extract_terms(query)
        if not terms:
            return []

        if resource_type == ResourceType.DOCUMENT:
            conditions = [LearningPageText.content.like(f"%{term}%") for term in terms]
            rows = (
                self.db.query(LearningPageText)
                .filter(
                    LearningPageText.resource_id == resource_id,
                    or_(*conditions),
                )
                .limit(50)
                .all()
            )
            candidates = [
                {
                    "type": "page",
                    "page_index": row.page_index,
                    "start_ms": None,
                    "end_ms": None,
                    "title": row.title,
                    "text": row.content,
                }
                for row in rows
            ]
        else:
            conditions = [LearningTranscript.text.like(f"%{term}%") for term in terms]
            rows = (
                self.db.query(LearningTranscript)
                .filter(
                    LearningTranscript.resource_id == resource_id,
                    or_(*conditions),
                )
                .order_by(LearningTranscript.start_ms.asc())
                .limit(100)
                .all()
            )
            candidates = [
                {
                    "type": "transcript",
                    "page_index": None,
                    "start_ms": row.start_ms,
                    "end_ms": row.end_ms,
                    "title": "",
                    "text": row.text,
                }
                for row in rows
            ]

        scored = [
            (candidate, _keyword_score(candidate["text"] or "", terms))
            for candidate in candidates
        ]
        scored = [item for item in scored if item[1] > 0]
        scored.sort(key=lambda item: item[1], reverse=True)

        return [
            {
                "type": candidate["type"],
                "page_index": candidate["page_index"],
                "start_ms": candidate["start_ms"],
                "end_ms": candidate["end_ms"],
                "title": candidate["title"],
                "snippet": _snippet_around(candidate["text"] or "", terms),
                "score": float(score),
            }
            for candidate, score in scored[:top_k]
        ]

    # ------------------------------------------------------------------
    # 当前位置窗口
    # ------------------------------------------------------------------

    def get_window(
        self, resource: LearningResource, position: float
    ) -> List[Dict[str, Any]]:
        """
        当前位置附近的内容，保证回答「懂你正在看哪」

        position 语义与学习进度一致：文档为页码，视频为秒。
        """
        if resource.type == ResourceType.DOCUMENT:
            page_index = int(position or 0)
            span = settings.LEARNING_CHAT_PAGE_WINDOW
            rows = (
                self.db.query(LearningPageText)
                .filter(
                    LearningPageText.resource_id == resource.id,
                    LearningPageText.page_index >= max(page_index - span, 0),
                    LearningPageText.page_index <= page_index + span,
                )
                .order_by(LearningPageText.page_index.asc())
                .all()
            )
            return [
                {
                    "type": "page",
                    "page_index": row.page_index,
                    "start_ms": None,
                    "end_ms": None,
                    "title": row.title,
                    "snippet": (row.content or "")[: settings.LEARNING_INDEX_CHUNK_CHARS],
                    "score": 0.0,
                    "is_current": row.page_index == page_index,
                }
                for row in rows
            ]

        pos_ms = int((position or 0) * 1000)
        span_ms = settings.LEARNING_CHAT_TRANSCRIPT_WINDOW_MS
        cues = (
            self.db.query(LearningTranscript)
            .filter(
                LearningTranscript.resource_id == resource.id,
                LearningTranscript.end_ms >= max(pos_ms - span_ms, 0),
                LearningTranscript.start_ms <= pos_ms + span_ms,
            )
            .order_by(LearningTranscript.start_ms.asc())
            .all()
        )
        if not cues:
            return []
        return [
            {
                "type": "transcript",
                "page_index": None,
                "start_ms": cues[0].start_ms,
                "end_ms": cues[-1].end_ms,
                "title": "",
                "snippet": "\n".join(cue.text for cue in cues if cue.text)[
                    : settings.LEARNING_INDEX_CHUNK_CHARS
                ],
                "score": 0.0,
                "is_current": True,
            }
        ]

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------

    def delete_index(self, resource_id: int) -> None:
        """删除资源时清理向量集合，不留孤儿文件"""
        try:
            get_vector_store_service().delete_collection(self.kb_id(resource_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"清理索引失败 resource={resource_id}: {exc}")


def _snippet_around(text: str, terms: List[str], radius: int = 200) -> str:
    """截取命中位置附近的文本，避免把整页内容塞进上下文"""
    position = -1
    for term in terms:
        position = text.find(term)
        if position >= 0:
            break
    if position < 0:
        return text[: radius * 2]
    start = max(position - radius, 0)
    end = min(position + radius, len(text))
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


def get_learning_index_service(db: Session) -> LearningIndexService:
    """索引服务工厂"""
    return LearningIndexService(db)


def ensure_page_texts(resource_id: int) -> int:
    """
    线程安全版：确保文档页面文本已落库

    自带 Session：Session 不是线程安全的，而本函数要在 asyncio.to_thread 里跑，
    复用请求级 Session 会与其所在的事件循环形成竞态。
    """
    db = SessionLocal()
    try:
        resource = (
            db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        )
        if not resource:
            return 0
        return LearningIndexService(db).ensure_page_texts(resource)
    finally:
        db.close()


def _build_in_thread(resource_id: int) -> None:
    """在独立线程里建索引（自带 Session，Session 非线程安全）"""
    db = SessionLocal()
    try:
        resource = (
            db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        )
        if not resource:
            return
        LearningIndexService(db).build_index(resource)
    except Exception as exc:  # noqa: BLE001
        logger.error(f"后台索引构建异常 resource={resource_id}: {exc}")
    finally:
        db.close()


async def build_index_async(resource_id: int) -> None:
    """后台任务入口：不阻塞请求，供 BackgroundTasks 使用"""
    await asyncio.to_thread(_build_in_thread, resource_id)
