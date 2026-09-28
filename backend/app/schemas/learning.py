"""
学习助手 Schema 模型

路由前缀 /api/v1/learning
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# 资源
# ------------------------------------------------------------------


class SubtitleTrack(BaseModel):
    """字幕语言轨道"""

    lang: str = Field(..., description="语言代码，如 zh-Hans / en")
    name: str = Field("", description="展示名")
    source: str = Field("platform", description="platform / manual / llm")
    # 是否是视频原文语言的轨道：双语展示时它作为「原文」那一行
    is_original: bool = Field(False, description="是否为视频原文语言轨道")


class UrlImportRequest(BaseModel):
    """URL 导入请求"""

    url: str = Field(..., min_length=1, max_length=2000, description="YouTube / B站视频链接")
    languages: List[str] = Field(
        default_factory=lambda: ["en","zh-Hans", "zh-CN", "zh", "zh-TW"],
        description="字幕语言优先级，从高到低",
    )


class ResourceResponse(BaseModel):
    """资源响应"""

    id: int
    user_id: int
    type: str
    source: str
    title: str
    description: str = ""
    cover_url: Optional[str] = None
    source_url: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    page_count: int = 0
    duration_seconds: int = 0
    platform_id: Optional[str] = None
    subtitle_tracks: Optional[List[SubtitleTrack]] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # 关联统计（随列表一起返回，避免前端 N+1）
    progress_percent: float = 0.0
    total_seconds: int = 0
    note_count: int = 0
    last_studied_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResourceListResponse(BaseModel):
    """资源列表（游标分页）"""

    items: List[ResourceResponse]
    next_cursor: Optional[int] = None
    has_more: bool = False


class ResourceUpdateRequest(BaseModel):
    """资源更新"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None


# ------------------------------------------------------------------
# 字幕
# ------------------------------------------------------------------


class TranscriptCue(BaseModel):
    """字幕片段（VTT/SRT 与手动上传的统一结构）"""

    id: int = 0
    seq: int = Field(0, description="片段序号，从 0 开始")
    start_ms: int = 0
    end_ms: int = 0
    text: str = ""
    language: str = ""
    source: str = "platform"
    # 按时间对齐后的译文（双语展示的副行）。由后端对齐填充，前端直接渲染。
    translation: str = Field("", description="时间对齐的译文，空串表示无译文")


class TranscriptResponse(BaseModel):
    """字幕列表响应"""

    resource_id: int
    language: str = ""
    cues: List[TranscriptCue]
    tracks: List[SubtitleTrack] = Field(default_factory=list)


# ------------------------------------------------------------------
# 文档分页
# ------------------------------------------------------------------


class PageBlock(BaseModel):
    """文档页内的一个结构化区块（PPTX 还原用）"""

    kind: str = Field("text", description="text / image / table")
    text: str = ""
    src: Optional[str] = None
    # 归一化坐标与尺寸（相对页面宽高，0~1）
    x: float = 0.0
    y: float = 0.0
    w: float = 0.0
    h: float = 0.0
    style: Dict[str, Any] = Field(default_factory=dict)


class DocumentPageResponse(BaseModel):
    """文档分页内容"""

    resource_id: int
    file_type: str
    page_count: int
    page_index: int
    width: float = 1.0
    height: float = 1.0
    title: str = ""
    # Markdown / EPUB 给渲染源（md 原文 / 净化后 HTML）；PPTX 给结构化 blocks
    html: str = ""
    raw: str = ""
    blocks: List[PageBlock] = Field(default_factory=list)


class DocumentOutlineItem(BaseModel):
    """目录项"""

    title: str
    page_index: int


class DocumentMetaResponse(BaseModel):
    """文档元信息"""

    resource_id: int
    file_type: str
    page_count: int
    outline: List[DocumentOutlineItem] = Field(default_factory=list)


# ------------------------------------------------------------------
# 笔记（矢量标注 / 文本便签 / 导出图）
# ------------------------------------------------------------------


class AnnotationPoint(BaseModel):
    """归一化坐标点"""

    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)


class AnnotationShape(BaseModel):
    """单个矢量图形（归一化坐标）"""

    id: str = Field(..., description="前端生成的 uuid，用于幂等更新与撤销重做")
    # text 为文本标注：points 只取第一个点作为锚点，正文存 text 字段
    tool: Literal["pen", "highlighter", "arrow", "rect", "ellipse", "text"]
    color: str = "#EF4444"
    strokeWidth: float = Field(0.003, ge=0.0005, le=0.05, description="归一化线宽（相对页宽）")
    opacity: float = Field(1.0, ge=0.05, le=1.0)
    points: List[AnnotationPoint] = Field(default_factory=list)
    text: str = Field("", max_length=2000, description="文本标注的正文，支持多行")
    # 贴纸的旋转与缩放：由前端 Konva Transformer 产出，存下来才能复现摆放角度
    rotation: float = 0.0
    scaleX: float = Field(1.0, ge=0.1, le=10)
    scaleY: float = Field(1.0, ge=0.1, le=10)
    createdAt: str = ""


class DrawNoteCreate(BaseModel):
    """矢量标注创建"""

    resource_id: int
    page_index: int = Field(0, ge=0)
    shape: AnnotationShape


class DrawNoteBatchSave(BaseModel):
    """整页矢量标注全量覆盖保存（前端抬笔后 300ms debounce 调用）"""

    shapes: List[AnnotationShape] = Field(default_factory=list)


class TextNoteCreate(BaseModel):
    """文本便签创建"""

    resource_id: int
    content: str = Field("", max_length=5000)
    x: float = Field(0.0, ge=0.0, le=1.0)
    y: float = Field(0.0, ge=0.0, le=1.0)
    page_index: Optional[int] = None
    position_ms: Optional[int] = None
    color: str = "#F59E0B"


class TextNoteUpdate(BaseModel):
    """文本便签更新"""

    content: Optional[str] = Field(None, max_length=5000)
    x: Optional[float] = Field(None, ge=0.0, le=1.0)
    y: Optional[float] = Field(None, ge=0.0, le=1.0)
    color: Optional[str] = None


class ExportNoteCreate(BaseModel):
    """画布截图导出"""

    resource_id: int
    page_index: int = Field(0, ge=0)
    image_base64: str = Field(..., description="前端合成的 PNG dataURL（不含前缀）")
    note: str = Field("", max_length=2000, description="导出备注")
    width: int = 0
    height: int = 0


class NoteResponse(BaseModel):
    """笔记响应"""

    id: int
    resource_id: int
    kind: str
    page_index: Optional[int] = None
    position_ms: Optional[int] = None
    content: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    file_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DrawNoteBatchResponse(BaseModel):
    """整页矢量标注查询结果"""

    resource_id: int
    page_index: int
    shapes: List[AnnotationShape]


# ------------------------------------------------------------------
# 学习进度
# ------------------------------------------------------------------


class ProgressReport(BaseModel):
    """进度心跳上报"""

    position: float = Field(0.0, ge=0.0, description="视频为秒，文档为页码")
    delta_seconds: int = Field(0, ge=0, le=600, description="距上次心跳的增量时长")
    client_seq: int = Field(0, ge=0, description="单调递增序号，用于幂等去重")
    is_finished: bool = False


class ProgressResponse(BaseModel):
    """进度响应"""

    resource_id: int
    position: float
    total_seconds: int
    is_finished: bool
    percent: float
    updated_at: Optional[datetime] = None


# ------------------------------------------------------------------
# 学习记录与统计
# ------------------------------------------------------------------


class RecordSessionItem(BaseModel):
    """单次学习会话"""

    id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    seconds: int = 0
    start_position: float = 0.0
    end_position: float = 0.0


class RecordResourceItem(BaseModel):
    """记录页的资源进度项"""

    resource_id: int
    title: str
    type: str
    source: str
    cover_url: Optional[str] = None
    percent: float = 0.0
    total_seconds: int = 0
    note_count: int = 0
    last_studied_at: Optional[datetime] = None
    is_finished: bool = False
    # AI 问答：提问条数与最近一条提问，用于在记录页回看学习过程
    qa_count: int = 0
    last_question: Optional[str] = None


class HeatmapPoint(BaseModel):
    """热力图单点"""

    date: str
    seconds: int = 0
    resource_count: int = 0
    note_count: int = 0


class WeekdayDistribution(BaseModel):
    """星期分布"""

    weekday: int = Field(0, description="0=周一 ... 6=周日")
    seconds: int = 0


class StatsOverview(BaseModel):
    """概览统计"""

    week_seconds: int = 0
    week_delta_percent: float = 0.0
    streak_days: int = 0
    finished_count: int = 0
    note_count: int = 0
    total_seconds: int = 0


class StatsResponse(BaseModel):
    """统计响应"""

    overview: StatsOverview
    heatmap: List[HeatmapPoint] = Field(default_factory=list)
    weekday_distribution: List[WeekdayDistribution] = Field(default_factory=list)

    class Config:
        from_attributes = True


class NoteTimelineItem(BaseModel):
    """笔记时间线条目"""

    id: int
    resource_id: int
    resource_title: str = ""
    resource_type: str = ""
    kind: str
    page_index: Optional[int] = None
    position_ms: Optional[int] = None
    content: Optional[str] = None
    file_url: Optional[str] = None
    preview_color: str = ""
    created_at: datetime


class NoteTimelineResponse(BaseModel):
    """笔记时间线（游标分页）"""

    items: List[NoteTimelineItem]
    next_cursor: Optional[int] = None
    has_more: bool = False


# ------------------------------------------------------------------
# AI 问答
# ------------------------------------------------------------------


class ContextRef(BaseModel):
    """手动指定的上下文引用（前端 @ 添加）

    文档用 page_index 定位，视频用 start_ms / end_ms 定位。
    与 LearningReference 的区别：那个是**回答产生的引用**（输出），
    这个是**用户圈定的输入范围**，方向相反。
    """

    type: str = Field("page", description="page / transcript")
    page_index: Optional[int] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None


class ChatAskRequest(BaseModel):
    """AI 问答请求"""

    query: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    position: float = Field(0.0, ge=0.0, description="当前位置：文档为页码，视频为秒")
    model_id: Optional[int] = Field(None, description="平台模型 ID；不传则用第一个可用模型")
    # 用户显式圈定的范围：强制进入上下文并排在最前，其余仍由窗口与检索补齐
    context_refs: List[ContextRef] = Field(default_factory=list)


class PageOption(BaseModel):
    """文档分页选项（供 @ 选择器列出可选页）"""

    page_index: int
    title: str = ""


class PageOptionListResponse(BaseModel):
    """文档分页列表"""

    resource_id: int
    items: List[PageOption] = Field(default_factory=list)


class LearningReference(BaseModel):
    """引用来源

    文档用 page_index 定位，视频用 start_ms / end_ms 定位，前端据此跳转。
    """

    type: str = Field("page", description="page / transcript")
    page_index: Optional[int] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    title: str = ""
    snippet: str = ""
    score: float = 0.0
    # 该片段是否是用户手动 @ 指定的（回看历史时可据此高亮）
    is_pinned: bool = False


class ChatMessageResponse(BaseModel):
    """问答消息"""

    id: int
    role: str
    content: str
    references: List[LearningReference] = Field(default_factory=list)
    model: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """问答历史"""

    resource_id: int
    messages: List[ChatMessageResponse] = Field(default_factory=list)


class SuggestedQuestionsResponse(BaseModel):
    """推荐问题"""

    resource_id: int
    questions: List[str] = Field(default_factory=list)


class ClearHistoryResponse(BaseModel):
    """清空历史结果"""

    deleted: int = 0
