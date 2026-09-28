"""
会话附件服务（工作助理）

职责：
1. 白名单校验与安全落盘（UUID 命名，杜绝路径穿越）
2. 文档解析为文本（复用 utils/file_parser，与知识库同一份实现）
3. 归属校验下的读取 / 删除 / 绑定
4. 把附件转换成 OpenAI content fragment，供 Hermes 消息构造使用

设计原则：
- **解析失败不阻塞**：仅标记 parse_status=failed 并把文件名作为上下文，
  保证用户仍然可以发送这条消息
- **图片内联为 data URI**：Hermes 部署在远端，访问不到本地 uploads，
  只能把字节嵌入请求体
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.hermes import HermesAttachment
from app.utils.file_parser import convert_to_markdown_sync
from app.utils.logger import logger


class AttachmentError(Exception):
    """附件业务校验失败（调用方应转成 400）"""


# 允许的图片扩展名
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# 允许的文档扩展名 -> 内部 file_type（与知识库 FILE_TYPE_MAP 保持一致）
DOCUMENT_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "excel",
    ".xls": "excel",
    ".md": "markdown",
    ".txt": "txt",
    ".html": "html",
    ".htm": "html",
    ".epub": "epub",
}


def classify(filename: str) -> Tuple[str, str]:
    """
    根据扩展名判定附件种类。

    Returns:
        (kind, file_type)；图片 file_type 为空字符串

    Raises:
        AttachmentError: 扩展名不在白名单内
    """
    ext = Path(filename or "").suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return "image", ""
    if ext in DOCUMENT_EXTENSIONS:
        return "document", DOCUMENT_EXTENSIONS[ext]
    raise AttachmentError(
        f"不支持的文件类型 {ext or '(无扩展名)'}，"
        f"图片支持 {'/'.join(sorted(IMAGE_EXTENSIONS))}，"
        f"文档支持 {'/'.join(sorted(DOCUMENT_EXTENSIONS))}"
    )


class AttachmentService:
    """会话附件服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 存储根目录
    # ------------------------------------------------------------------

    @staticmethod
    def _base_dir() -> Path:
        return Path(settings.UPLOAD_DIR)

    @staticmethod
    def _user_dir(user_id: int) -> Path:
        return (
            Path(settings.UPLOAD_DIR) / settings.ATTACHMENT_SUBDIR / str(user_id)
        )

    @staticmethod
    def _abs_path(attachment: HermesAttachment) -> Path:
        """file_path 存的是相对 UPLOAD_DIR 的路径"""
        return Path(settings.UPLOAD_DIR) / attachment.file_path

    # ------------------------------------------------------------------
    # 创建
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        user_id: int,
        filename: str,
        data: bytes,
        mime_type: Optional[str] = None,
    ) -> HermesAttachment:
        """
        落盘 + 建记录 +（文档）解析。

        Raises:
            AttachmentError: 类型不允许或体积超限
        """
        kind, file_type = classify(filename)
        size = len(data)

        limit_mb = (
            settings.ATTACHMENT_MAX_IMAGE_MB
            if kind == "image"
            else settings.ATTACHMENT_MAX_DOC_MB
        )
        if size > limit_mb * 1024 * 1024:
            raise AttachmentError(
                f"文件过大（{size / 1024 / 1024:.1f}MB），上限 {limit_mb}MB"
            )
        if size == 0:
            raise AttachmentError("文件内容为空")

        # 安全落盘：目录按 user_id 隔离，文件名用 UUID，杜绝路径穿越与覆盖
        user_dir = self._user_dir(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower()
        stored_name = f"{uuid.uuid4().hex}{ext}"
        abs_path = user_dir / stored_name

        with open(abs_path, "wb") as f:
            f.write(data)

        rel_path = f"{settings.ATTACHMENT_SUBDIR}/{user_id}/{stored_name}"
        attachment = HermesAttachment(
            user_id=user_id,
            kind=kind,
            filename=filename[:255],
            stored_name=stored_name,
            file_path=rel_path,
            mime_type=mime_type or mimetypes.guess_type(filename)[0],
            file_size=size,
            parse_status="skipped" if kind == "image" else "pending",
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)

        # 文档同步解析（阻塞 IO 放线程池），失败仅标记状态
        if kind == "document":
            await self._parse(attachment, file_type)

        return attachment

    async def _parse(self, attachment: HermesAttachment, file_type: str) -> None:
        """解析文档正文，结果截断后入库；异常只记录不抛出。"""
        abs_path = self._abs_path(attachment)
        try:
            text = await asyncio.to_thread(
                convert_to_markdown_sync, str(abs_path), file_type
            )
            text = (text or "").strip()
            limit = settings.ATTACHMENT_TEXT_LIMIT
            if len(text) > limit:
                text = text[:limit] + f"\n\n[内容过长，已截断至 {limit} 字符]"
            attachment.parsed_text = text
            attachment.parse_status = "parsed" if text else "failed"
            if not text:
                attachment.parse_error = "解析结果为空"
        except Exception as e:  # noqa: BLE001
            logger.warning(f"附件解析失败 id={attachment.id}: {e}")
            attachment.parse_status = "failed"
            attachment.parse_error = str(e)[:500]
        finally:
            self.db.commit()
            self.db.refresh(attachment)

    # ------------------------------------------------------------------
    # 查询 / 删除 / 绑定
    # ------------------------------------------------------------------

    def get_owned(
        self, attachment_id: int, user_id: int
    ) -> Optional[HermesAttachment]:
        """带归属校验地取附件（非本人返回 None）"""
        return (
            self.db.query(HermesAttachment)
            .filter(
                HermesAttachment.id == attachment_id,
                HermesAttachment.user_id == user_id,
            )
            .first()
        )

    def delete(self, attachment_id: int, user_id: int) -> bool:
        """删除附件（未发送的或已发送但会话被删的均允许本人删除）"""
        attachment = self.get_owned(attachment_id, user_id)
        if not attachment:
            return False

        try:
            abs_path = self._abs_path(attachment)
            if abs_path.exists():
                abs_path.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning(f"删除附件文件失败 id={attachment_id}: {e}")

        self.db.delete(attachment)
        self.db.commit()
        return True

    def bind(
        self,
        attachment_ids: List[int],
        *,
        user_id: int,
        session_id: str,
        message_id: Optional[str] = None,
    ) -> List[HermesAttachment]:
        """把已上传的附件绑定到会话（及消息）"""
        if not attachment_ids:
            return []
        rows = (
            self.db.query(HermesAttachment)
            .filter(
                HermesAttachment.id.in_(attachment_ids),
                HermesAttachment.user_id == user_id,
            )
            .all()
        )
        for row in rows:
            row.session_id = session_id
            if message_id:
                row.message_id = message_id
        if rows:
            self.db.commit()
        return rows

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def read_bytes(self, attachment: HermesAttachment) -> bytes:
        with open(self._abs_path(attachment), "rb") as f:
            return f.read()

    def data_uri(self, attachment: HermesAttachment) -> str:
        """图片转 base64 data URI（远端 Hermes 无法访问本地文件）"""
        raw = self.read_bytes(attachment)
        mime = attachment.mime_type or mimetypes.guess_type(attachment.filename)[0] or "image/png"
        return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"

    # ------------------------------------------------------------------
    # 消息构造
    # ------------------------------------------------------------------

    def to_content_fragment(
        self, attachment: HermesAttachment, *, as_image: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        附件 → OpenAI content fragment。

        - 图片：as_image=True 时产出 image_url(data URI)，否则降级为文本占位
        - 文档：产出「文件名 + 正文」的 text fragment
        - 解析失败：降级为仅文件名的 text fragment，保证上下文不丢失
        """
        if attachment.kind == "image":
            if not as_image:
                return {
                    "type": "text",
                    "text": f"[用户上传了图片：{attachment.filename}]",
                }
            try:
                return {
                    "type": "image_url",
                    "image_url": {"url": self.data_uri(attachment)},
                }
            except Exception as e:  # noqa: BLE001
                logger.warning(f"读取图片失败 id={attachment.id}: {e}")
                return {
                    "type": "text",
                    "text": f"[用户上传了图片：{attachment.filename}（读取失败）]",
                }

        # 文档
        text = (attachment.parsed_text or "").strip()
        if not text:
            return {
                "type": "text",
                "text": f"[用户上传了文件：{attachment.filename}"
                + ("（解析失败，仅文件名可见）" if attachment.parse_status == "failed" else "）"),
            }
        return {
            "type": "text",
            "text": f"[用户上传了文件：{attachment.filename}]\n{text}",
        }


def get_attachment_service(db: Session) -> AttachmentService:
    """获取附件服务实例"""
    return AttachmentService(db)
