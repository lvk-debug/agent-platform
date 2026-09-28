"""
学习助手数据模型

八张表（Integer 自增主键，时间戳统一 UTC）：
- learning_resources     学习资源（视频/文档）
- learning_transcripts   资源字幕片段（视频用）
- learning_notes         笔记（矢量标注 / 文本便签 / 画布导出图，三态合一）
- learning_progress      资源学习进度（每资源每用户一条，upsert）
- learning_sessions      学习会话明细（一次连续学习一段）
- learning_page_texts    文档每页纯文本（AI 索引与降级检索的数据源）
- learning_chat_sessions AI 问答会话（每资源每用户一条）
- learning_chat_messages AI 问答消息（含引用来源，可回溯）

设计要点：
1. **枚举用模块级字符串常量**：SQLite 的 Enum 以 VARCHAR + CHECK 实现，新增枚举值
   必须走 Alembic 迁移；这里沿用定时任务模块的做法，改用常量 + 服务层校验。
2. **三类笔记统一存 learning_notes**：靠 kind 区分，payload 承载各自结构化数据，
   避免为便签与导出图各建一张表；page_index / position_ms 二选一用于跳转定位。
3. **坐标一律归一化 0~1**：同一资源在不同屏幕尺寸与缩放下打开也不错位。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """
    读写两端都保证 UTC aware 的 DateTime

    SQLite 不保存时区：`DateTime(timezone=True)` 写入后读回会变成 **naive**
    （实测：写入 tzinfo=UTC，读回 tzinfo=None）。由此引发两类问题：

    1. 与 `datetime.now(UTC)` 相减直接抛
       `can't subtract offset-naive and offset-aware datetimes`；
    2. naive 值序列化成 ISO 后没有时区后缀，前端会把它当**本地时间**解析，
       显示时间偏差一个时区（东八区即 8 小时）。

    这里在驱动层统一补齐：读回的 naive 一律按 UTC 解释（库里本来就是 UTC 存的值）。
    PostgreSQL 原生保留时区，该处理对它也安全。
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN201
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def process_result_value(self, value, dialect):  # noqa: ANN201
        if value is None:
            return None
        return value if value.tzinfo else value.replace(tzinfo=UTC)


class ResourceType:
    """资源类型（仅视频与文档，不含音频）"""

    VIDEO = "video"
    DOCUMENT = "document"

    ALL = (VIDEO, DOCUMENT)


class ResourceSource:
    """资源来源"""

    YOUTUBE = "youtube"
    BILIBILI = "bilibili"
    UPLOAD = "upload"

    ALL = (YOUTUBE, BILIBILI, UPLOAD)


class ResourceStatus:
    """资源处理状态

    no_subtitle: 视频可用但平台无字幕，等待用户手动上传 SRT/VTT
    """

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"
    NO_SUBTITLE = "no_subtitle"

    ALL = (PENDING, READY, FAILED, NO_SUBTITLE)


class DocumentFileType:
    """文档文件格式"""

    PDF = "pdf"
    PPTX = "pptx"
    EPUB = "epub"
    MARKDOWN = "markdown"

    ALL = (PDF, PPTX, EPUB, MARKDOWN)

    EXT_MAP = {
        ".pdf": PDF,
        ".pptx": PPTX,
        ".epub": EPUB,
        ".md": MARKDOWN,
        ".markdown": MARKDOWN,
        ".mdown": MARKDOWN,
    }


class TranscriptSource:
    """字幕来源"""

    PLATFORM = "platform"  # yt-dlp 抓取的平台字幕
    MANUAL = "manual"  # 用户手动上传
    LLM = "llm"  # 平台无译文轨道时，由 LLM 翻译生成的译文轨道

    ALL = (PLATFORM, MANUAL, LLM)


class NoteKind:
    """笔记类型"""

    DRAW = "draw"  # 矢量标注（payload 存归一化坐标）
    TEXT = "text"  # 文本便签/评论批注（content 存正文）
    EXPORT = "export"  # 画布截图导出（file_url 存导出图）

    ALL = (DRAW, TEXT, EXPORT)


class IndexStatus:
    """AI 问答索引状态（三态）

    pending    : 尚未建索引，首次提问时后台异步构建
    ready      : 向量索引可用，走向量 + BM25 检索
    unavailable: embedding 不可用（模型缺失等），问答降级为「当前位置窗口 + 关键词召回」

    设计要点：索引只是**加速与扩召回**手段，不是问答的前置条件。
    任何状态下问答都必须可用，unavailable 时功能降级但绝不报错。
    """

    PENDING = "pending"
    READY = "ready"
    UNAVAILABLE = "unavailable"

    ALL = (PENDING, READY, UNAVAILABLE)


class ChatRole:
    """问答消息角色"""

    USER = "user"
    ASSISTANT = "assistant"

    ALL = (USER, ASSISTANT)


class LearningResource(Base):
    """学习资源"""

    __tablename__ = "learning_resources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    type = Column(String(20), nullable=False, default=ResourceType.VIDEO)
    source = Column(String(20), nullable=False, default=ResourceSource.YOUTUBE)

    title = Column(String(500), nullable=False, default="未命名资源")
    description = Column(Text, nullable=False, default="")
    cover_url = Column(String(2000), nullable=True)
    source_url = Column(String(2000), nullable=True)

    # 文档资源专用
    file_path = Column(String(1000), nullable=True)
    file_type = Column(String(20), nullable=True)
    file_size = Column(Integer, nullable=True, default=0)
    page_count = Column(Integer, nullable=False, default=0)

    # 视频资源专用
    duration_seconds = Column(Integer, nullable=False, default=0)
    # 平台视频 ID（YouTube videoId / B站 BV 号），用于拼装 iframe 播放地址
    platform_id = Column(String(100), nullable=True)
    # 可用字幕语言轨道，JSON 数组，如 [{"lang":"zh-Hans","name":"中文（自动生成）"}]
    subtitle_tracks = Column(JSON, nullable=True)

    status = Column(String(20), nullable=False, default=ResourceStatus.PENDING)
    error_message = Column(Text, nullable=True)

    # ---- AI 问答相关（索引 / 摘要 / 推荐问题）----
    # 内容摘要：由前若干页文本或前若干条字幕截取，用于生成推荐问题与作为 Prompt 背景。
    # 单独存一份是为了避免每次问答都重新解析整份文档。
    summary = Column(Text, nullable=True)
    # 索引状态三态：pending / ready / unavailable，见 IndexStatus
    index_status = Column(String(20), nullable=False, default=IndexStatus.PENDING)
    index_error = Column(Text, nullable=True)
    index_chunk_count = Column(Integer, nullable=False, default=0)
    # AI 生成的推荐问题缓存，JSON 数组，如 ["这份文档的背景是什么？", ...]
    suggested_questions = Column(JSON, nullable=True)
    suggested_questions_at = Column(UTCDateTime(timezone=True), nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningResource(id={self.id}, type={self.type}, "
            f"title={self.title!r}, status={self.status})>"
        )


class LearningTranscript(Base):
    """字幕片段

    按 resource_id + start_ms 建联合索引，支撑时间轴顺序拉取与二分定位。
    """

    __tablename__ = "learning_transcripts"
    __table_args__ = (Index("ix_learning_transcripts_resource_start", "resource_id", "start_ms"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    seq = Column(Integer, nullable=False, default=0)
    start_ms = Column(Integer, nullable=False, default=0)
    end_ms = Column(Integer, nullable=False, default=0)
    text = Column(Text, nullable=False, default="")
    language = Column(String(20), nullable=False, default="")
    source = Column(String(20), nullable=False, default=TranscriptSource.PLATFORM)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningTranscript(id={self.id}, resource={self.resource_id}, "
            f"start={self.start_ms})>"
        )


class LearningNote(Base):
    """笔记

    kind 决定语义：
    - draw  : payload 存单个矢量图形坐标；page_index 标识所属页
    - text  : content 存正文，payload 存锚点 {x, y, pageIndex, positionMs, color}
    - export: file_url 存导出图 URL，payload 存 {pageIndex, range, width, height}
    """

    __tablename__ = "learning_notes"
    __table_args__ = (Index("ix_learning_notes_resource_page", "resource_id", "page_index"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    kind = Column(String(20), nullable=False, default=NoteKind.DRAW)

    page_index = Column(Integer, nullable=True)  # 文档页码
    position_ms = Column(Integer, nullable=True)  # 视频时间点

    content = Column(Text, nullable=True)  # 便签正文 / 导出备注
    payload = Column(JSON, nullable=True)  # 结构化载荷
    file_url = Column(String(2000), nullable=True)  # 导出图访问地址

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<LearningNote(id={self.id}, kind={self.kind}, resource={self.resource_id})>"


class LearningProgress(Base):
    """学习进度（每资源一条，upsert）"""

    __tablename__ = "learning_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # 视频为秒，文档为页码（可为小数）
    position = Column(Float, nullable=False, default=0.0)
    total_seconds = Column(Integer, nullable=False, default=0)

    # 心跳幂等：前端单调递增序号，重复上报不重复计时
    last_seq = Column(Integer, nullable=False, default=0)
    last_heartbeat_at = Column(UTCDateTime(timezone=True), nullable=True)
    is_finished = Column(Boolean, nullable=False, default=False)

    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningProgress(resource={self.resource_id}, pos={self.position}, "
            f"total={self.total_seconds})>"
        )


class LearningSession(Base):
    """学习会话

    心跳间隔超过 LEARNING_HEARTBEAT_IDLE_SECONDS 判定会话断开，自动结束并开新会话。
    """

    __tablename__ = "learning_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    started_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    ended_at = Column(UTCDateTime(timezone=True), nullable=True)
    seconds = Column(Integer, nullable=False, default=0)

    start_position = Column(Float, nullable=False, default=0.0)
    end_position = Column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return (
            f"<LearningSession(id={self.id}, resource={self.resource_id}, "
            f"seconds={self.seconds})>"
        )


class LearningPageText(Base):
    """文档每页纯文本

    文档（PDF/PPTX/EPUB/MD）的分页解析是**按需实时**的：翻到第 N 页才解析第 N 页。
    而全文索引需要遍历所有页，重复解析代价过高，因此解析一次后把纯文本落库，供：
    1) 索引服务切片并写入向量库；
    2) embedding 不可用时作为**关键词降级召回**的数据源（此时问答仍可用）。
    """

    __tablename__ = "learning_page_texts"
    __table_args__ = (
        UniqueConstraint("resource_id", "page_index", name="uq_learning_page_texts_page"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
    )
    page_index = Column(Integer, nullable=False, default=0)
    title = Column(String(500), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    char_count = Column(Integer, nullable=False, default=0)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningPageText(resource={self.resource_id}, "
            f"page={self.page_index}, chars={self.char_count})>"
        )


class LearningChatSession(Base):
    """AI 问答会话（每资源每用户一条）

    一个资源只保留一条会话：学习场景的问答是围绕该资源的连续追问，
    拆成多条会话反而增加选择成本。清空历史时只删消息、保留会话。
    """

    __tablename__ = "learning_chat_sessions"
    __table_args__ = (
        UniqueConstraint("resource_id", "user_id", name="uq_learning_chat_session"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(500), nullable=False, default="")
    # 最近一次使用的模型（平台 models 表的 model_id 字符串），下次打开沿用
    model_name = Column(String(200), nullable=False, default="")
    message_count = Column(Integer, nullable=False, default=0)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningChatSession(id={self.id}, resource={self.resource_id}, "
            f"messages={self.message_count})>"
        )


class LearningChatMessage(Base):
    """AI 问答消息

    references 保存本次回答引用到的来源（文档页码 / 视频时间戳），
    前端据此渲染「引用胶囊」，点击即可跳回原文，形成问答闭环。
    """

    __tablename__ = "learning_chat_messages"
    __table_args__ = (Index("ix_learning_chat_messages_session", "session_id", "id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("learning_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id = Column(
        Integer,
        ForeignKey("learning_resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    role = Column(String(20), nullable=False, default=ChatRole.USER)
    content = Column(Text, nullable=False, default="")
    # 引用来源：[{type: "page"|"transcript", page_index|start_ms, end_ms, title, snippet}]
    references = Column(JSON, nullable=True)

    model = Column(String(200), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    # 生成失败时记录原因，消息本身仍保留（前端显示为错误气泡，不丢用户输入）
    error = Column(Text, nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<LearningChatMessage(id={self.id}, session={self.session_id}, "
            f"role={self.role})>"
        )
