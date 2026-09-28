"""
学习助手主服务

职责编排：资源 CRUD（含 URL 导入与文档上传）、字幕存取、笔记（标注/便签/导出）CRUD、
学习进度心跳与会话切分、学习记录与统计聚合。

分层关系：
    endpoints/learning.py → services/learning.py → services/{media,subtitle,document_page}.py

所有 DB 操作集中在此，OCR/抓取/解析等无状态能力下沉到各自的 service。
"""

import base64
import io
import os
import uuid
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.learning import (
    ChatRole,
    LearningChatMessage,
    LearningChatSession,
    LearningNote,
    LearningPageText,
    LearningProgress,
    LearningResource,
    LearningSession,
    LearningTranscript,
    NoteKind,
    ResourceSource,
    ResourceStatus,
    ResourceType,
    TranscriptSource,
)
from app.schemas.learning import (
    AnnotationShape,
    DrawNoteBatchSave,
    ExportNoteCreate,
    HeatmapPoint,
    NoteTimelineItem,
    ProgressReport,
    StatsOverview,
    StatsResponse,
    SubtitleTrack,
    TextNoteCreate,
    TextNoteUpdate,
    UrlImportRequest,
    WeekdayDistribution,
)
from app.services import document_page as document_page_module
from app.services.media import (
    MediaUnavailableError,
    detect_platform,
    get_media_service,
)
from app.services.learning_index import get_learning_index_service
from app.services.subtitle import validate_manual_subtitle
from app.utils.logger import logger
from app.utils.pagination import apply_desc_cursor_pagination

try:  # 时区在城市作息统计里很关键，缺失时退化到 Asia/Shanghai 固定偏移
    from zoneinfo import ZoneInfo

    STUDY_TZ = ZoneInfo(settings.SCHEDULER_TIMEZONE)
except Exception:  # noqa: BLE001
    STUDY_TZ = timezone(timedelta(hours=8))


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _as_utc(moment: Optional[datetime]) -> Optional[datetime]:
    """
    把数据库读回的时间统一成 UTC aware

    SQLite 不保存时区：`DateTime(timezone=True)` 写入后读回会变成 **naive**，
    直接与 `datetime.now(UTC)` 相减会抛
    `can't subtract offset-naive and offset-aware datetimes`。
    （PostgreSQL 会保留时区，故该处理对两种库都安全。）

    与定时任务模块 `scheduled_task_service.py` 保持同一约定：naive 一律按 UTC 解释。
    """
    if moment is None:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _local_date(moment: datetime) -> datetime:
    """把 UTC 时间戳换算为用户所在时区的日期零点，用于按天聚合"""
    aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    local = aware.astimezone(STUDY_TZ)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def _is_chinese_lang(lang: str) -> bool:
    """判断是否为中文轨道（yt-dlp 的语言代码形如 zh-Hans / zh-CN）"""
    return (lang or "").lower().startswith("zh")


def _align_translations(
    primary: List[LearningTranscript], secondary: List[LearningTranscript]
) -> Dict[int, str]:
    """
    按时间重叠把译文挂到原文字幕上

    两条轨道的切分边界几乎不可能对齐（一句原文可能对应半句或多句译文），
    故取「与原文区间有重叠」的全部译文拼起来。双指针推进，整体 O(n+m)。

    Returns:
        {原文字幕 id: 译文文本}
    """
    result: Dict[int, str] = {}
    if not secondary:
        return result

    ordered = sorted(secondary, key=lambda cue: cue.start_ms)
    index = 0
    for cue in primary:
        # 跳开已经完全早于当前原句的译文
        while index < len(ordered) and ordered[index].end_ms <= cue.start_ms:
            index += 1

        texts: List[str] = []
        cursor = index
        while cursor < len(ordered) and ordered[cursor].start_ms < cue.end_ms:
            if ordered[cursor].text:
                texts.append(ordered[cursor].text)
            cursor += 1

        if texts:
            result[cue.id] = " ".join(texts)
    return result


class LearningService:
    """学习助手服务"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ==================================================================
    # 资源
    # ==================================================================

    def _note_count_subquery(self):
        """每个资源的笔记数量子查询，避免列表页 N+1"""
        return (
            self.db.query(
                LearningNote.resource_id.label("rid"),
                func.count(LearningNote.id).label("cnt"),
            )
            .group_by(LearningNote.resource_id)
            .subquery()
        )

    def list_resources(
        self,
        user_id: int,
        type_filter: Optional[str] = None,
        keyword: Optional[str] = None,
        sort: str = "recent_studied",
        cursor: Optional[int] = None,
        limit: int = 24,
    ) -> Tuple[List[LearningResource], Optional[int], bool, Dict[int, Dict[str, Any]]]:
        """
        资源列表（降序游标分页）

        Returns:
            (resources, next_cursor, has_more, stats_map)
            stats_map 以 resource.id 为键，含 percent/total_seconds/note_count/last_studied_at
        """
        counts = self._note_count_subquery()
        query = (
            self.db.query(LearningResource, LearningProgress, counts.c.cnt)
            .outerjoin(LearningProgress, LearningProgress.resource_id == LearningResource.id)
            .outerjoin(counts, counts.c.rid == LearningResource.id)
            .filter(LearningResource.user_id == user_id)
        )

        if type_filter and type_filter in ResourceType.ALL:
            query = query.filter(LearningResource.type == type_filter)
        if keyword:
            pattern = f"%{keyword}%"
            query = query.filter(
                or_(LearningResource.title.like(pattern), LearningResource.description.like(pattern))
            )

        # 排序：为保证降序游标可用，主序统一收敛到 resource.id DESC，
        # 再用次序列表达语义（同 id 不可能并列，故语义仍然成立）
        if sort == "recent_created":
            query = query.order_by(LearningResource.created_at.desc(), LearningResource.id.desc())
        elif sort == "progress":
            query = query.order_by(LearningProgress.position.desc(), LearningResource.id.desc())
        else:  # recent_studied
            query = query.order_by(LearningResource.updated_at.desc(), LearningResource.id.desc())

        rows, next_cursor, has_more = apply_desc_cursor_pagination(
            query, LearningResource, cursor=cursor, limit=limit
        )

        resources: List[LearningResource] = []
        stats: Dict[int, Dict[str, Any]] = {}
        for resource, progress, note_count in rows:
            resources.append(resource)
            stats[resource.id] = self._build_stats(resource, progress, int(note_count or 0))
        return resources, next_cursor, has_more, stats

    @staticmethod
    def _build_stats(
        resource: LearningResource, progress: Optional[LearningProgress], note_count: int
    ) -> Dict[str, Any]:
        """组装资源卡片的展示统计"""
        total_seconds = progress.total_seconds if progress else 0
        position = progress.position if progress else 0.0
        return {
            "progress_percent": LearningService.compute_percent(resource, position),
            "total_seconds": total_seconds,
            "note_count": note_count,
            "last_studied_at": progress.updated_at if progress else None,
        }

    @staticmethod
    def compute_percent(resource: LearningResource, position: float) -> float:
        """完成百分比：视频按秒，文档按页码"""
        total = (
            resource.duration_seconds
            if resource.type == ResourceType.VIDEO
            else resource.page_count
        )
        if total and total > 0:
            return round(min(max(position / total, 0.0), 1.0) * 100, 1)
        return 0.0

    def get_resource(self, resource_id: int, user_id: int) -> LearningResource:
        """取资源并校验归属"""
        resource = (
            self.db.query(LearningResource)
            .filter(LearningResource.id == resource_id, LearningResource.user_id == user_id)
            .first()
        )
        if resource is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="学习资源不存在")
        return resource

    def get_resource_with_stats(self, resource_id: int, user_id: int) -> Tuple[LearningResource, Dict[str, Any]]:
        """资源详情 + 统计"""
        resource = self.get_resource(resource_id, user_id)
        progress = (
            self.db.query(LearningProgress)
            .filter(LearningProgress.resource_id == resource_id)
            .first()
        )
        note_count = (
            self.db.query(func.count(LearningNote.id))
            .filter(LearningNote.resource_id == resource_id)
            .scalar()
            or 0
        )
        return resource, self._build_stats(resource, progress, int(note_count))

    # ---------- URL 导入 ----------

    def create_from_url(self, user_id: int, data: UrlImportRequest) -> LearningResource:
        """
        创建视频资源占位记录（状态 pending），随后由后台任务补全

        先立记录再抓取：抓取耗时可能几十秒，同步等待会拖垮接口响应。
        """
        try:
            platform, platform_id = detect_platform(data.url)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        if not get_media_service().is_ytdlp_installed():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="服务端未安装 yt-dlp，无法导入视频链接。请执行：pip install -U yt-dlp",
            )

        resource = LearningResource(
            user_id=user_id,
            type=ResourceType.VIDEO,
            source=platform,
            title="正在解析…",
            source_url=data.url,
            platform_id=platform_id,
            status=ResourceStatus.PENDING,
        )
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        self._ensure_document_dir(resource)
        logger.info(f"创建 URL 资源占位 resource={resource.id} platform={platform}")
        return resource

    async def hydrate_from_url(self, resource_id: int, languages: List[str]) -> None:
        """
        后台补全视频元数据与字幕（独立 DB Session）

        原请求 Session 在响应返回后即关闭，故这里新开 Session以避免操作已释放连接。
        """
        service = get_media_service()
        db = SessionLocal()
        try:
            resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
            if resource is None:
                return

            payload = await service.fetch(resource.source_url or "", languages)
            self._apply_media_payload(resource, payload)
            self._persist_media_payload(db, resource, payload)
            db.commit()

            # 平台没给中文轨道时（B站、YouTube 无翻译），用 LLM 补一条译文做双语。
            # 就地导入避免与 learning_chat 形成顶层循环依赖。
            try:
                from app.services.learning_chat import get_learning_chat_service

                await get_learning_chat_service(db).translate_transcripts(resource)
            except Exception as exc:  # noqa: BLE001 - 翻译失败不影响视频本身可用
                logger.warning(f"字幕翻译失败 resource={resource_id}: {exc}")

            logger.info(
                f"URL 资源补全成功 resource={resource_id} cues={len(payload.get('cues') or [])}"
            )
        except MediaUnavailableError as exc:
            logger.error(f"URL 资源补全失败 resource={resource_id}: {exc}")
            self._mark_failed(db, resource_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - 后台任务异常不得冒泡
            logger.error(f"URL 资源补全异常 resource={resource_id}: {exc}", exc_info=True)
            self._mark_failed(db, resource_id, "解析视频链接失败，请确认链接有效且可公开访问")
        finally:
            db.close()

    def _persist_media_payload(
        self, db: Session, resource: LearningResource, payload: Dict[str, Any]
    ) -> None:
        """把字幕轨道与片段写库，并根据是否有字幕推进资源状态

        支持多轨道：`tracks` 里第一条是原文、第二条是中文译文（若有）。
        """
        availability = payload.get("availability") or {}
        target_lang = payload.get("target_lang") or ""
        tracks = payload.get("tracks") or []

        if tracks:
            resource.subtitle_tracks = [
                {
                    "lang": track.get("lang") or "",
                    "name": track.get("lang") or "",
                    "source": track.get("source") or TranscriptSource.PLATFORM,
                    "is_original": bool(track.get("is_original")),
                }
                for track in tracks
            ]
        else:
            # 兼容旧结构：只有单条 cues，没有轨道信息
            manual_langs = availability.get("manual") or []
            auto_langs = availability.get("auto") or []
            resource.subtitle_tracks = [
                {
                    "lang": lang,
                    "name": lang,
                    "source": TranscriptSource.PLATFORM,
                    "is_original": lang == (payload.get("original_lang") or target_lang),
                }
                for lang in dict.fromkeys(manual_langs + auto_langs)
            ]

        written = False
        if tracks:
            # 每条轨道按 (source, language) 独立替换，互不覆盖
            for track in tracks:
                cues = track.get("cues") or []
                if not cues:
                    continue
                self.replace_transcripts_on_session(
                    db,
                    resource.id,
                    resource.user_id,
                    cues,
                    track.get("source") or TranscriptSource.PLATFORM,
                    track.get("lang") or "",
                )
                written = True
        else:
            cues = payload.get("cues") or []
            if cues:
                self.replace_transcripts_on_session(
                    db,
                    resource.id,
                    resource.user_id,
                    cues,
                    TranscriptSource.PLATFORM,
                    target_lang,
                )
                written = True

        if written:
            resource.status = ResourceStatus.READY
            resource.error_message = None
        else:
            resource.status = ResourceStatus.NO_SUBTITLE
            resource.error_message = self._build_no_subtitle_message(payload)

    @staticmethod
    def _build_no_subtitle_message(payload: Dict[str, Any]) -> str:
        """
        构造「无字幕」的诊断文案

        区分「视频根本没有字幕轨道」与「有轨道但抓取被限流」，
        否则用户无法判断该等重试还是直接上传字幕文件。
        """
        availability = payload.get("availability") or {}
        manual = availability.get("manual") or []
        auto = availability.get("auto") or []
        requested = payload.get("requested_langs") or []

        if not manual and not auto:
            return "该视频没有任何字幕轨道（作者未提供，且无自动生成字幕），请手动上传 SRT/VTT"

        available = ", ".join(dict.fromkeys(manual + auto))
        tried = ", ".join(requested) or "无"
        return (
            f"字幕抓取失败：已尝试 {tried}；平台报告可用轨道 {available}。"
            "翻译类自动字幕常被平台限流，可稍后重试或直接手动上传 SRT/VTT"
        )

    @staticmethod
    def _replace_transcripts_on_session_impl(
        db: Session, resource_id: int, user_id: int, cues: List[dict], source: str, language: str
    ) -> int:
        """（供后台 Session 复用的）字幕全量替换实现"""
        db.query(LearningTranscript).filter(
            LearningTranscript.resource_id == resource_id,
            LearningTranscript.source == source,
            LearningTranscript.language == language,
        ).delete(synchronize_session=False)
        db.flush()

        objects = [
            LearningTranscript(
                resource_id=resource_id,
                user_id=user_id,
                seq=cue["seq"],
                start_ms=cue["start_ms"],
                end_ms=cue["end_ms"],
                text=cue["text"],
                language=language,
                source=source,
            )
            for cue in cues
        ]
        for start in range(0, len(objects), 500):
            db.bulk_save_objects(objects[start : start + 500])
        return len(objects)

    def replace_transcripts_on_session(
        self, db: Session, resource_id: int, user_id: int, cues: List[dict], source: str, language: str
    ) -> int:
        """在指定 Session 上替换字幕（后台任务用）"""
        count = self._replace_transcripts_on_session_impl(
            db, resource_id, user_id, cues, source, language
        )
        logger.info(f"写入字幕 resource={resource_id} lang={language} count={count}")
        return count

    @staticmethod
    def _apply_media_payload(resource: LearningResource, payload: Dict[str, Any]) -> None:
        """把抓取结果写进资源字段"""
        resource.title = payload.get("title") or resource.title
        resource.description = payload.get("description") or ""
        resource.cover_url = payload.get("cover_url") or ""
        resource.duration_seconds = int(payload.get("duration_seconds") or 0)
        resource.platform_id = payload.get("platform_id") or resource.platform_id
        resource.source_url = payload.get("source_url") or resource.source_url

    @staticmethod
    def _mark_failed(db: Session, resource_id: int, message: str) -> None:
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        if resource is None:
            return
        resource.status = ResourceStatus.FAILED
        resource.error_message = message[:500]
        db.commit()

    # ---------- 文档上传 ----------

    def create_from_upload(self, user_id: int, file: UploadFile) -> LearningResource:
        """创建文档资源并落盘"""
        try:
            file_type = document_page_module.detect_file_type(file.filename or "")
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        content = file.file.read()
        max_bytes = settings.LEARNING_MAX_DOC_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"文件超过 {settings.LEARNING_MAX_DOC_MB}MB 上限",
            )

        resource = LearningResource(
            user_id=user_id,
            type=ResourceType.DOCUMENT,
            source=ResourceSource.UPLOAD,
            title=os.path.splitext(file.filename or "未命名文档")[0] or "未命名文档",
            file_type=file_type,
            file_size=len(content),
            status=ResourceStatus.PENDING,
        )
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)

        try:
            self._ensure_document_dir(resource)
            path = document_page_module.save_upload(
                resource.id, content, file.filename or "", file_type
            )
            resource.file_path = path
            page_count, _ = document_page_module.DocumentPageService().get_meta(resource)
            resource.page_count = page_count
            resource.status = ResourceStatus.READY
        except document_page_module.DocumentParseError as exc:
            logger.error(f"文档解析失败 resource={resource.id}: {exc}")
            resource.status = ResourceStatus.FAILED
            resource.error_message = str(exc)[:500]
        except Exception as exc:  # noqa: BLE001
            logger.error(f"文档落盘失败 resource={resource.id}: {exc}", exc_info=True)
            resource.status = ResourceStatus.FAILED
            resource.error_message = "文档解析失败，请确认文件未损坏"

        self.db.commit()
        self.db.refresh(resource)
        return resource

    @staticmethod
    def _ensure_document_dir(resource: LearningResource) -> None:
        os.makedirs(document_page_module.resource_dir(resource.id), exist_ok=True)

    def update_resource(
        self, resource_id: int, user_id: int, title: Optional[str], description: Optional[str]
    ) -> LearningResource:
        resource = self.get_resource(resource_id, user_id)
        if title is not None:
            resource.title = title
        if description is not None:
            resource.description = description
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def delete_resource(self, resource_id: int, user_id: int) -> None:
        """删除资源及其字幕、笔记、进度、会话、问答记录与落盘文件"""
        resource = self.get_resource(resource_id, user_id)

        # 向量索引独立于数据库（kb_*.db 文件），必须先显式清理。
        # 其余子表也不能指望外键级联：SQLite 的 PRAGMA foreign_keys 默认是关闭的。
        try:
            get_learning_index_service(self.db).delete_index(resource_id)
        except Exception as exc:  # noqa: BLE001 - 清理失败不该阻断删除
            logger.warning(f"清理问答索引失败 resource={resource_id}: {exc}")

        self.db.query(LearningTranscript).filter(
            LearningTranscript.resource_id == resource_id
        ).delete(synchronize_session=False)
        self.db.query(LearningNote).filter(LearningNote.resource_id == resource_id).delete(
            synchronize_session=False
        )
        self.db.query(LearningProgress).filter(LearningProgress.resource_id == resource_id).delete(
            synchronize_session=False
        )
        self.db.query(LearningSession).filter(LearningSession.resource_id == resource_id).delete(
            synchronize_session=False
        )
        self.db.query(LearningPageText).filter(
            LearningPageText.resource_id == resource_id
        ).delete(synchronize_session=False)
        self.db.query(LearningChatMessage).filter(
            LearningChatMessage.resource_id == resource_id
        ).delete(synchronize_session=False)
        self.db.query(LearningChatSession).filter(
            LearningChatSession.resource_id == resource_id
        ).delete(synchronize_session=False)
        self.db.delete(resource)
        self.db.commit()

        document_page_module.delete_resource_files(resource_id)
        logger.info(f"删除学习资源 resource={resource_id}")

    # ==================================================================
    # 字幕
    # ==================================================================

    def list_transcripts(
        self, resource_id: int, user_id: int, language: Optional[str] = None
    ) -> Tuple[List[LearningTranscript], List[SubtitleTrack], Dict[int, str]]:
        """
        取字幕（默认返回原文轨道）

        Returns:
            (原文字幕, 可用轨道, {原文字幕 id: 对齐后的译文})
        """
        self.get_resource(resource_id, user_id)

        query = self.db.query(LearningTranscript).filter(
            LearningTranscript.resource_id == resource_id
        )
        if language:
            query = query.filter(LearningTranscript.language == language)

        # 先取出全部语言的字幕：主/副轨道都要从这份里筛，
        # 否则把全集覆盖成主语言后，译文必然筛不出来。
        all_rows = query.order_by(LearningTranscript.start_ms.asc()).all()
        tracks = self.list_subtitle_tracks(resource_id)

        # 主语言（原文那一行）：显式指定 > 标记为原文 > 第一条
        primary_lang = language or ""
        if not primary_lang and tracks:
            original = next((track for track in tracks if track.is_original), None)
            primary_lang = (original or tracks[0]).lang
        if not primary_lang and all_rows:
            # 连轨道都没有：退化为按第一条出现的语言，避免混合多语言
            primary_lang = all_rows[0].language

        cues = [row for row in all_rows if row.language == primary_lang]

        # 译文轨道：与主语言不同的中文轨道（平台抓取或 AI 翻译都算）
        secondary_lang = ""
        if primary_lang:
            candidate = next(
                (
                    track
                    for track in tracks
                    if track.lang != primary_lang and _is_chinese_lang(track.lang)
                ),
                None,
            )
            secondary_lang = candidate.lang if candidate else ""
        secondary = (
            [row for row in all_rows if row.language == secondary_lang]
            if secondary_lang
            else []
        )

        return cues, tracks, _align_translations(cues, secondary)

    def list_subtitle_tracks(self, resource_id: int) -> List[SubtitleTrack]:
        """按语言聚合出可用字幕轨道（含是否原文标记）"""
        rows = (
            self.db.query(
                LearningTranscript.language,
                LearningTranscript.source,
                func.count(LearningTranscript.id).label("cnt"),
            )
            .filter(LearningTranscript.resource_id == resource_id)
            .group_by(LearningTranscript.language, LearningTranscript.source)
            .all()
        )
        # 轨道的 is_original 标记写在资源上（抓取时判定），这里取来合并
        resource = (
            self.db.query(LearningResource)
            .filter(LearningResource.id == resource_id)
            .first()
        )
        meta: Dict[str, Dict[str, Any]] = {}
        for item in (resource.subtitle_tracks if resource else None) or []:
            if isinstance(item, dict) and item.get("lang"):
                meta[str(item["lang"])] = item

        tracks: List[SubtitleTrack] = []
        for lang, source, count in rows:
            if not lang or count == 0:
                continue
            suffix = ""
            if source == TranscriptSource.MANUAL:
                suffix = "（手动上传）"
            elif source == TranscriptSource.LLM:
                suffix = "（AI 翻译）"
            tracks.append(
                SubtitleTrack(
                    lang=lang,
                    name=f"{lang}{suffix}",
                    source=source,
                    is_original=bool(meta.get(lang, {}).get("is_original")),
                )
            )

        # 兜底：只有一条轨道时它就是原文，否则双语无从谈起
        if len(tracks) == 1:
            tracks[0].is_original = True
        # 原文轨道排在最前：调用方用 tracks[0] 兜底选主语言时不会挑到译文
        tracks.sort(key=lambda track: (not track.is_original, track.lang))
        return tracks

    def replace_transcripts(
        self, resource_id: int, user_id: int, cues: List[dict], source: str, language: str
    ) -> int:
        """全量替换某语言轨道的字幕并批量入库"""
        self.get_resource(resource_id, user_id)
        count = self._replace_transcripts_on_session_impl(
            self.db, resource_id, user_id, cues, source, language
        )
        self.db.commit()
        logger.info(f"写入字幕 resource={resource_id} lang={language} count={count}")
        return count

    def upload_manual_subtitle(
        self, resource_id: int, user_id: int, content: str, language: str = "manual"
    ) -> int:
        """手动上传 SRT/VTT 字幕"""
        resource = self.get_resource(resource_id, user_id)
        try:
            cues = validate_manual_subtitle(content)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        count = self.replace_transcripts(
            resource_id, user_id, cues, TranscriptSource.MANUAL, language
        )

        # 登记轨道：手动上传也走同一套轨道元信息，
        # 否则 list_subtitle_tracks 拿不到 is_original，主语言可能选错。
        tracks = [
            item for item in (resource.subtitle_tracks or []) if isinstance(item, dict)
        ]
        if not any(item.get("lang") == language for item in tracks):
            tracks.append(
                {
                    "lang": language,
                    "name": language,
                    "source": TranscriptSource.MANUAL,
                    # 此前没有任何轨道时，这份就是原文
                    "is_original": len(tracks) == 0,
                }
            )
            resource.subtitle_tracks = tracks

        if resource.status == ResourceStatus.NO_SUBTITLE:
            resource.status = ResourceStatus.READY
            resource.error_message = None
        self.db.commit()
        return count

    # ==================================================================
    # 文档分页
    # ==================================================================

    def get_document_meta(self, resource_id: int, user_id: int) -> Tuple[int, List[Dict[str, Any]]]:
        resource = self.get_resource(resource_id, user_id)
        if resource.type != ResourceType.DOCUMENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该资源不是文档")
        page_count, outline = document_page_module.DocumentPageService().get_meta(resource)
        if resource.page_count != page_count:
            resource.page_count = page_count
            self.db.commit()
        return page_count, outline

    def get_document_page(self, resource_id: int, user_id: int, page_index: int) -> Dict[str, Any]:
        resource = self.get_resource(resource_id, user_id)
        if resource.type != ResourceType.DOCUMENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该资源不是文档")
        try:
            return document_page_module.DocumentPageService().get_page(resource, page_index)
        except document_page_module.DocumentParseError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # ==================================================================
    # 笔记
    # ==================================================================

    def save_draw_page(
        self, resource_id: int, user_id: int, page_index: int, payload: DrawNoteBatchSave
    ) -> List[AnnotationShape]:
        """
        整页矢量标注全量覆盖保存

        按前端 shape.id 做 upsert：已存在则更新，缺失则插入，多余则删除。
        前端抬笔后 debounce 调用本接口，故必须是幂等的。
        """
        self.get_resource(resource_id, user_id)

        existing = (
            self.db.query(LearningNote)
            .filter(
                LearningNote.resource_id == resource_id,
                LearningNote.user_id == user_id,
                LearningNote.kind == NoteKind.DRAW,
                LearningNote.page_index == page_index,
            )
            .all()
        )
        existing_map: Dict[str, LearningNote] = {}
        for note in existing:
            shape_id = (note.payload or {}).get("id")
            if isinstance(shape_id, str):
                existing_map[shape_id] = note

        incoming_ids = set()
        for shape in payload.shapes:
            incoming_ids.add(shape.id)
            data = shape.model_dump()
            note = existing_map.get(shape.id)
            if note is None:
                self.db.add(
                    LearningNote(
                        resource_id=resource_id,
                        user_id=user_id,
                        kind=NoteKind.DRAW,
                        page_index=page_index,
                        payload=data,
                    )
                )
            else:
                note.payload = data

        for shape_id, note in existing_map.items():
            if shape_id not in incoming_ids:
                self.db.delete(note)

        self.db.commit()
        return payload.shapes

    def list_draw_page(
        self, resource_id: int, user_id: int, page_index: int
    ) -> List[AnnotationShape]:
        """读取整页矢量标注"""
        notes = (
            self.db.query(LearningNote)
            .filter(
                LearningNote.resource_id == resource_id,
                LearningNote.kind == NoteKind.DRAW,
                LearningNote.page_index == page_index,
            )
            .order_by(LearningNote.id.asc())
            .all()
        )
        shapes: List[AnnotationShape] = []
        for note in notes:
            data = note.payload or {}
            if not isinstance(data, dict) or "tool" not in data:
                continue
            try:
                shapes.append(AnnotationShape(**data))
            except Exception:  # noqa: BLE001 - 单条脏数据不应拖垮整页
                logger.error(f"矢量标注数据损坏 note={note.id}")
        return shapes

    def create_text_note(self, user_id: int, data: TextNoteCreate) -> LearningNote:
        """创建文本便签/评论批注"""
        self.get_resource(data.resource_id, user_id)
        # 便签必须锚定到文档页或视频时间点，否则无法跳转回填
        if data.page_index is None and data.position_ms is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="便签缺少定位信息")

        note = LearningNote(
            resource_id=data.resource_id,
            user_id=user_id,
            kind=NoteKind.TEXT,
            content=data.content,
            page_index=data.page_index,
            position_ms=data.position_ms,
            payload={
                "x": data.x,
                "y": data.y,
                "color": data.color,
                "pageIndex": data.page_index,
                "positionMs": data.position_ms,
            },
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    def update_text_note(
        self, note_id: int, user_id: int, data: TextNoteUpdate
    ) -> LearningNote:
        note = self._get_note(note_id, user_id)
        if data.content is not None:
            note.content = data.content
        if data.color is not None or data.x is not None or data.y is not None:
            payload = dict(note.payload or {})
            if data.color is not None:
                payload["color"] = data.color
            if data.x is not None:
                payload["x"] = data.x
            if data.y is not None:
                payload["y"] = data.y
            note.payload = payload
        self.db.commit()
        self.db.refresh(note)
        return note

    def delete_note(self, note_id: int, user_id: int) -> None:
        note = self._get_note(note_id, user_id)
        if note.kind == NoteKind.EXPORT and note.file_url:
            self._remove_export_file(note)
        self.db.delete(note)
        self.db.commit()

    def _get_note(self, note_id: int, user_id: int) -> LearningNote:
        note = (
            self.db.query(LearningNote)
            .filter(LearningNote.id == note_id, LearningNote.user_id == user_id)
            .first()
        )
        if note is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="笔记不存在")
        return note

    def list_resource_notes(
        self, resource_id: int, user_id: int, kind: Optional[str] = None,
        page_index: Optional[int] = None,
    ) -> List[LearningNote]:
        """资源下的笔记列表"""
        self.get_resource(resource_id, user_id)
        query = self.db.query(LearningNote).filter(LearningNote.resource_id == resource_id)
        if kind:
            query = query.filter(LearningNote.kind == kind)
        if page_index is not None:
            query = query.filter(LearningNote.page_index == page_index)
        return query.order_by(LearningNote.created_at.asc()).all()

    # ---------- 画布截图导出 ----------

    @staticmethod
    def _export_dir(resource_id: int) -> str:
        return os.path.join(document_page_module.resource_dir(resource_id), "exports")

    @staticmethod
    def _remove_export_file(note: LearningNote) -> None:
        """删除导出图物理文件"""
        name = (note.file_url or "").rsplit("/", 1)[-1]
        if not name:
            return
        base = LearningService._export_dir(note.resource_id)
        path = os.path.join(base, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError as exc:  # noqa: BLE001
                logger.error(f"删除导出图失败 note={note.id}: {exc}")

    def create_export_note(self, user_id: int, data: ExportNoteCreate) -> LearningNote:
        """
        画布截图导出：解压 base64 → Pillow 压缩 → 落盘 → 记一条 export 笔记

        导出图需在「学习记录」中长期回看，故不能只做浏览器下载，必须后端留档。
        """
        self.get_resource(data.resource_id, user_id)

        try:
            raw = base64.b64decode(data.image_base64.split(",")[-1])
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片数据格式非法") from exc

        from PIL import Image  # noqa: PLC0415 - 延迟导入，缺失时给出明确提示

        try:
            image = Image.open(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="无法识别的图片内容") from exc

        # 长边收敛 + RGB 规范化，避免 RGBA/CMYK 直接存 JPEG 报错
        image = image.convert("RGB")
        max_edge = settings.LEARNING_EXPORT_MAX_EDGE
        if max(image.size) > max_edge:
            ratio = max_edge / max(image.size)
            image = image.resize(
                (max(int(image.width * ratio), 1), max(int(image.height * ratio), 1)),
                Image.LANCZOS,
            )

        directory = self._export_dir(data.resource_id)
        os.makedirs(directory, exist_ok=True)
        stored_name = f"{uuid.uuid4().hex}.jpg"
        path = os.path.join(directory, stored_name)

        max_bytes = settings.LEARNING_EXPORT_MAX_MB * 1024 * 1024
        quality = 92
        while quality >= 60:
            image.save(path, format="JPEG", quality=quality, optimize=True)
            if os.path.getsize(path) <= max_bytes:
                break
            quality -= 12
        logger.info(f"导出图落盘 resource={data.resource_id} size={os.path.getsize(path)} quality={quality}")

        note = LearningNote(
            resource_id=data.resource_id,
            user_id=user_id,
            kind=NoteKind.EXPORT,
            page_index=data.page_index,
            content=data.note,
            file_url=f"/api/v1/learning/assets/{data.resource_id}/{stored_name}",
            payload={
                "width": image.width,
                "height": image.height,
                "format": "jpeg",
                "pageIndex": data.page_index,
            },
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        return note

    # ==================================================================
    # 学习进度与会话
    # ==================================================================

    def report_progress(
        self, resource_id: int, user_id: int, data: ProgressReport
    ) -> Tuple[LearningResource, LearningProgress]:
        """
        进度心跳上报

        幂等与会话切分：
        - client_seq 未推进时判定重复上报，只刷新 position，不重复计时
        - 距上次心跳超过 LEARNING_HEARTBEAT_IDLE_SECONDS 判定会话断开，结算旧会话并开新会话
        """
        resource = self.get_resource(resource_id, user_id)
        now = _utcnow()

        progress = (
            self.db.query(LearningProgress)
            .filter(LearningProgress.resource_id == resource_id)
            .first()
        )
        if progress is None:
            progress = LearningProgress(
                resource_id=resource_id,
                user_id=user_id,
                position=data.position,
                total_seconds=data.delta_seconds,
                last_seq=data.client_seq,
                last_heartbeat_at=now,
            )
            self.db.add(progress)
            self.db.flush()
            self.db.add(
                LearningSession(
                    resource_id=resource_id,
                    user_id=user_id,
                    started_at=now,
                    start_position=data.position,
                    end_position=data.position,
                    seconds=data.delta_seconds,
                )
            )
            self.db.commit()
            self.db.refresh(progress)
            return resource, progress

        # 重复心跳：只更新位置，避免刷新导致时长翻倍
        if data.client_seq <= progress.last_seq:
            progress.position = data.position
            self.db.commit()
            return resource, progress

        session = self._current_session(resource_id, user_id)
        idle_limit = settings.LEARNING_HEARTBEAT_IDLE_SECONDS
        last_beat = _as_utc(progress.last_heartbeat_at)
        stale = last_beat is None or (now - last_beat).total_seconds() > idle_limit

        if stale:
            if session is not None:
                # 结算断开的旧会话：时长以最后一次心跳为准
                session.ended_at = last_beat or now
                started_at = _as_utc(session.started_at) or now
                session.seconds = max(int((session.ended_at - started_at).total_seconds()), 0)
                session.end_position = progress.position
            session = LearningSession(
                resource_id=resource_id,
                user_id=user_id,
                started_at=now,
                start_position=data.position,
            )
            self.db.add(session)
            self.db.flush()

        progress.total_seconds += data.delta_seconds
        progress.position = data.position
        progress.last_seq = data.client_seq
        progress.last_heartbeat_at = now
        if data.is_finished:
            progress.is_finished = True

        if session is not None:
            session.end_position = data.position
            started_at = _as_utc(session.started_at) or now
            session.seconds = max(int((now - started_at).total_seconds()), 0)

        self.db.commit()
        self.db.refresh(progress)
        return resource, progress

    def _current_session(self, resource_id: int, user_id: int) -> Optional[LearningSession]:
        """当前未结束的学习会话"""
        return (
            self.db.query(LearningSession)
            .filter(
                LearningSession.resource_id == resource_id,
                LearningSession.user_id == user_id,
                LearningSession.ended_at.is_(None),
            )
            .order_by(LearningSession.id.desc())
            .first()
        )

    def close_idle_session(self, resource_id: int, user_id: int) -> None:
        """页面离开时显式结束会话（防止意外关闭导致会话悬挂）"""
        session = self._current_session(resource_id, user_id)
        if session is None:
            return
        now = _utcnow()
        session.ended_at = now
        started_at = _as_utc(session.started_at) or now
        session.seconds = max(int((now - started_at).total_seconds()), 0)
        self.db.commit()

    # ==================================================================
    # 学习记录与统计
    # ==================================================================

    def list_records(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """记录页的资源进度列表（按最近学习时间倒序）"""
        counts = self._note_count_subquery()
        rows = (
            self.db.query(LearningResource, LearningProgress, counts.c.cnt)
            .join(LearningProgress, LearningProgress.resource_id == LearningResource.id)
            .outerjoin(counts, counts.c.rid == LearningResource.id)
            .filter(LearningResource.user_id == user_id)
            .order_by(LearningProgress.updated_at.desc())
            .limit(limit)
            .all()
        )

        # 问答统计一次性查完再映射，避免每条记录都打一次库（N+1）
        qa_count_map, last_question_map = self._collection_qa_stats(user_id)

        records: List[Dict[str, Any]] = []
        for resource, progress, note_count in rows:
            records.append(
                {
                    "resource_id": resource.id,
                    "title": resource.title,
                    "type": resource.type,
                    "source": resource.source,
                    "cover_url": resource.cover_url,
                    "percent": self.compute_percent(resource, progress.position),
                    "total_seconds": progress.total_seconds,
                    "note_count": int(note_count or 0),
                    "last_studied_at": progress.updated_at,
                    "is_finished": progress.is_finished,
                    "qa_count": qa_count_map.get(resource.id, 0),
                    "last_question": last_question_map.get(resource.id),
                }
            )
        return records

    def _collection_qa_stats(
        self, user_id: int
    ) -> Tuple[Dict[int, int], Dict[int, Optional[str]]]:
        """批量统计每个资源的提问条数与最近一条提问"""
        base = self.db.query(LearningChatMessage).filter(
            LearningChatMessage.user_id == user_id,
            LearningChatMessage.role == ChatRole.USER,
        )

        counted = (
            base.with_entities(
                LearningChatMessage.resource_id,
                func.count(LearningChatMessage.id).label("cnt"),
            )
            .group_by(LearningChatMessage.resource_id)
            .all()
        )
        count_map = {int(row[0]): int(row[1] or 0) for row in counted}
        if not count_map:
            return {}, {}

        # 每个资源最后一条提问：先取各资源最大 id，再一次性取内容
        latest_ids = [
            int(row[0])
            for row in base.with_entities(
                func.max(LearningChatMessage.id).label("mid")
            )
            .group_by(LearningChatMessage.resource_id)
            .all()
        ]
        latest_rows = (
            self.db.query(LearningChatMessage)
            .filter(LearningChatMessage.id.in_(latest_ids))
            .all()
            if latest_ids
            else []
        )
        question_map = {row.resource_id: row.content for row in latest_rows}
        return count_map, question_map

    def list_resource_sessions(self, resource_id: int, user_id: int, limit: int = 20) -> List[LearningSession]:
        """某资源的学习会话明细"""
        self.get_resource(resource_id, user_id)
        return (
            self.db.query(LearningSession)
            .filter(LearningSession.resource_id == resource_id)
            .order_by(LearningSession.id.desc())
            .limit(limit)
            .all()
        )

    def get_stats(self, user_id: int, heatmap_days: int = 182) -> StatsResponse:
        """
        概览 + 热力图 + 星期分布

        说明：会话与笔记在 Python 侧按「用户本地时区」归日聚合（SQL 的日期函数
        在 SQLite/PostgreSQL 间行为不一致，且时区由 SCHEDULER_TIMEZONE 决定）。
        个人学习场景的量级（千级会话）完全够用；若后续出现大规模数据，
        再改为按日预聚合表。
        """
        sessions = (
            self.db.query(LearningSession)
            .filter(LearningSession.user_id == user_id, LearningSession.seconds > 0)
            .all()
        )

        now_local = _local_date(_utcnow())
        week_start = now_local - timedelta(days=6)
        prev_week_start = week_start - timedelta(days=7)
        heat_start = now_local - timedelta(days=heatmap_days - 1)

        week_seconds = 0
        prev_week_seconds = 0
        weekday_totals: Dict[int, int] = {index: 0 for index in range(7)}
        daily_seconds: Dict[datetime, int] = {}
        daily_resources: Dict[datetime, set] = {}

        for session in sessions:
            day = _local_date(session.started_at)
            seconds = max(int(session.seconds or 0), 0)
            if day < heat_start:
                continue

            daily_seconds[day] = daily_seconds.get(day, 0) + seconds
            daily_resources.setdefault(day, set()).add(session.resource_id)
            weekday_totals[day.weekday()] += seconds

            if day >= week_start:
                week_seconds += seconds
            elif day >= prev_week_start:
                prev_week_seconds += seconds

        # 每日笔记数单独聚合，同样按本地时区归日
        notes = self.db.query(LearningNote).filter(LearningNote.user_id == user_id).all()
        daily_notes: Dict[datetime, int] = {}
        for note in notes:
            day = _local_date(note.created_at)
            if day < heat_start:
                continue
            daily_notes[day] = daily_notes.get(day, 0) + 1

        heatmap: List[HeatmapPoint] = []
        for offset in range(heatmap_days):
            day = heat_start + timedelta(days=offset)
            heatmap.append(
                HeatmapPoint(
                    date=day.strftime("%Y-%m-%d"),
                    seconds=daily_seconds.get(day, 0),
                    resource_count=len(daily_resources.get(day, set())),
                    note_count=daily_notes.get(day, 0),
                )
            )

        # 连续学习天数：从今天（或昨天，允许当天还没学）往前推
        streak = 0
        cursor_day = now_local
        if not daily_seconds.get(cursor_day):
            cursor_day = cursor_day - timedelta(days=1)
        while daily_seconds.get(cursor_day, 0) > 0:
            streak += 1
            cursor_day = cursor_day - timedelta(days=1)

        finished_count = (
            self.db.query(func.count(LearningProgress.id))
            .filter(LearningProgress.user_id == user_id, LearningProgress.is_finished.is_(True))
            .scalar()
            or 0
        )
        total_seconds = (
            self.db.query(func.coalesce(func.sum(LearningProgress.total_seconds), 0))
            .filter(LearningProgress.user_id == user_id)
            .scalar()
            or 0
        )

        delta_percent = 0.0
        if prev_week_seconds > 0:
            delta_percent = round((week_seconds - prev_week_seconds) / prev_week_seconds * 100, 1)

        return StatsResponse(
            overview=StatsOverview(
                week_seconds=week_seconds,
                week_delta_percent=delta_percent,
                streak_days=streak,
                finished_count=int(finished_count),
                note_count=len(notes),
                total_seconds=int(total_seconds),
            ),
            heatmap=heatmap,
            weekday_distribution=[
                WeekdayDistribution(weekday=day, seconds=seconds)
                for day, seconds in sorted(weekday_totals.items())
            ],
        )

    def list_note_timeline(
        self, user_id: int, kind: Optional[str] = None, cursor: Optional[int] = None, limit: int = 30
    ) -> Tuple[List[NoteTimelineItem], Optional[int], bool]:
        """跨资源的笔记时间线（倒序游标分页）"""
        query = (
            self.db.query(LearningNote, LearningResource)
            .join(LearningResource, LearningResource.id == LearningNote.resource_id)
            .filter(LearningNote.user_id == user_id)
        )
        if kind:
            query = query.filter(LearningNote.kind == kind)

        rows, next_cursor, has_more = apply_desc_cursor_pagination(
            query, LearningNote, cursor=cursor, limit=limit
        )

        items: List[NoteTimelineItem] = []
        for note, resource in rows:
            payload = note.payload or {}
            items.append(
                NoteTimelineItem(
                    id=note.id,
                    resource_id=note.resource_id,
                    resource_title=resource.title,
                    resource_type=resource.type,
                    kind=note.kind,
                    page_index=note.page_index,
                    position_ms=note.position_ms,
                    content=note.content,
                    file_url=note.file_url,
                    preview_color=str(payload.get("color", "") or payload.get("tool", "")),
                    created_at=note.created_at,
                )
            )
        return items, next_cursor, has_more


def get_learning_service(db: Session) -> LearningService:
    """学习服务工厂（与既有 get_xxx_service(db) 保持一致）"""
    return LearningService(db)
