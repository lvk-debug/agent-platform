"""
智能客服助手 Schema 模型

路由前缀 /api/v1/support

分页统一用页码（page + page_size）：客服后台需要跳页与显示总数，
游标分页在这种场景下反而不好用。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# 通用
# ------------------------------------------------------------------


class PageMeta(BaseModel):
    """分页元信息"""

    total: int = 0
    page: int = 1
    page_size: int = 20


class SupportReference(BaseModel):
    """回答引用到的知识库片段"""

    kb_id: Optional[int] = None
    kb_name: str = ""
    document_id: Optional[int] = None
    document_name: str = ""
    segment_id: Optional[int] = None
    content: str = ""
    score: float = 0.0


# ------------------------------------------------------------------
# 客户
# ------------------------------------------------------------------


class CustomerCreate(BaseModel):
    """客户创建"""

    name: str = Field(..., min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    wechat: Optional[str] = Field(None, max_length=100)
    source: str = Field("other", max_length=20)
    remark: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CustomerUpdate(BaseModel):
    """客户更新"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=200)
    wechat: Optional[str] = Field(None, max_length=100)
    source: Optional[str] = Field(None, max_length=20)
    remark: Optional[str] = None
    tags: Optional[List[str]] = None


class CustomerResponse(BaseModel):
    """客户响应"""

    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    wechat: Optional[str] = None
    source: str
    source_label: str = ""
    remark: Optional[str] = None
    tags: Optional[List[str]] = None
    session_count: int = 0
    ticket_count: int = 0
    last_session_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """客户列表"""

    items: List[CustomerResponse] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


# ------------------------------------------------------------------
# 会话
# ------------------------------------------------------------------


class SessionCreate(BaseModel):
    """会话创建"""

    customer_id: Optional[int] = Field(None, description="不传则创建匿名会话")
    title: Optional[str] = Field(None, max_length=500)
    mode: str = Field("ai", description="ai / human")


class SessionUpdate(BaseModel):
    """会话更新（标题、意图等轻量字段）"""

    title: Optional[str] = Field(None, max_length=500)
    customer_id: Optional[int] = None
    intent: Optional[str] = Field(None, max_length=30)


class SessionTakeoverRequest(BaseModel):
    """坐席接管会话"""

    reason: Optional[str] = Field(None, max_length=500, description="转人工原因")


class SessionTransferRequest(BaseModel):
    """会话转交给其他坐席"""

    assignee_id: Optional[int] = Field(None, description="为空表示退回公共池")


class SessionCloseRequest(BaseModel):
    """结束会话"""

    status: str = Field("resolved", description="resolved / closed")
    satisfaction: Optional[int] = Field(None, ge=1, le=5)
    satisfaction_comment: Optional[str] = Field(None, max_length=1000)


class SessionResponse(BaseModel):
    """会话响应"""

    id: int
    customer_id: Optional[int] = None
    customer_name: str = ""
    title: str = ""
    mode: str
    status: str
    status_label: str = ""
    intent: Optional[str] = None
    intent_label: str = ""
    intent_confidence: float = 0.0
    assignee_id: Optional[int] = None
    assignee_name: str = ""
    message_count: int = 0
    last_message_at: Optional[datetime] = None
    last_message_preview: str = ""
    low_confidence_streak: int = 0
    satisfaction: Optional[int] = None
    satisfaction_comment: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    # 最新一条 AI 消息的处理轨迹（节点步骤 + 工具调用 + 工单 + 引用），供会话列表查看运行日志
    last_ai_trace: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """会话列表"""

    items: List[SessionResponse] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


# ------------------------------------------------------------------
# 消息
# ------------------------------------------------------------------


class MessageSendRequest(BaseModel):
    """发送消息

    AI 模式下由机器人回答；人工模式下坐席点发送即作为人工回复。
    """

    content: str = Field(..., min_length=1, max_length=4000)
    role: str = Field(
        "customer", description="customer（代客录入）/ agent（坐席回复）"
    )
    model_id: Optional[int] = Field(None, description="AI 回答使用的模型")


class MessageResponse(BaseModel):
    """消息响应"""

    id: int
    session_id: int
    role: str
    content: str
    references: List[SupportReference] = Field(default_factory=list)
    intent: Optional[str] = None
    intent_label: str = ""
    confidence: Optional[float] = None
    model: Optional[str] = None
    tokens_used: Optional[int] = None
    latency_ms: Optional[int] = None
    error: Optional[str] = None
    operator_id: Optional[int] = None
    operator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    """消息列表"""

    session_id: int
    items: List[MessageResponse] = Field(default_factory=list)


class ChatAskRequest(BaseModel):
    """AI 流式问答请求"""

    query: str = Field(..., min_length=1, max_length=4000)
    model_id: Optional[int] = Field(None, description="不传则用配置或第一个可用模型")


class ReturnConfirmRequest(BaseModel):
    """human-in-the-loop：坐席对退货/退款诉求的确认决策"""

    decision: str = Field(..., description="approved=确认由 AI 继续处理 / rejected=拒绝并转人工")
    comment: Optional[str] = Field(None, description="坐席备注（可选）")


class SuggestRequest(BaseModel):
    """AI 建议回复请求"""

    model_id: Optional[int] = None


class SuggestReplyResponse(BaseModel):
    """AI 建议回复（人工模式下辅助坐席）"""

    content: str = ""
    references: List[SupportReference] = Field(default_factory=list)
    error: Optional[str] = None


class MessageSendResponse(BaseModel):
    """发送消息结果

    带上最新会话状态：坐席手动回复会自动切为人工模式，
    前端要据此刷新模式按钮与负责人。
    """

    message: MessageResponse
    session: SessionResponse


class SessionModeRequest(BaseModel):
    """切换会话模式"""

    mode: str = Field(..., description="ai / human")


# ------------------------------------------------------------------
# 工单
# ------------------------------------------------------------------


class TicketCreate(BaseModel):
    """工单创建

    customer_id 与 customer_new 二选一：会话已绑定客户时前端直接传前者，
    匿名会话建单时可现场录入客户资料。
    """

    customer_id: Optional[int] = None
    customer_new: Optional[CustomerCreate] = None
    session_id: Optional[int] = Field(None, description="来源会话，用于回链上下文")
    type: str = Field("other", max_length=20)
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = Field("normal", max_length=20)
    assignee_id: Optional[int] = None
    due_at: Optional[datetime] = None


class TicketUpdate(BaseModel):
    """工单更新（不含状态，状态走 transition）"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    type: Optional[str] = Field(None, max_length=20)
    priority: Optional[str] = Field(None, max_length=20)
    assignee_id: Optional[int] = None
    due_at: Optional[datetime] = None


class TicketTransitionRequest(BaseModel):
    """工单状态流转"""

    to_status: str = Field(..., description="目标状态")
    content: Optional[str] = Field(None, max_length=2000, description="处理说明")


class TicketCommentRequest(BaseModel):
    """工单留言"""

    content: str = Field(..., min_length=1, max_length=2000)


class TicketResponse(BaseModel):
    """工单响应"""

    id: int
    ticket_no: str
    customer_id: Optional[int] = None
    customer_name: str = ""
    session_id: Optional[int] = None
    type: str
    type_label: str = ""
    title: str
    description: Optional[str] = None
    status: str
    status_label: str = ""
    priority: str
    priority_label: str = ""
    assignee_id: Optional[int] = None
    assignee_name: str = ""
    due_at: Optional[datetime] = None
    is_overdue: bool = False
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TicketListResponse(BaseModel):
    """工单列表"""

    items: List[TicketResponse] = Field(default_factory=list)
    meta: PageMeta = Field(default_factory=PageMeta)


class TicketLogResponse(BaseModel):
    """工单处理流水"""

    id: int
    ticket_id: int
    action: str
    from_status: Optional[str] = None
    from_status_label: str = ""
    to_status: Optional[str] = None
    to_status_label: str = ""
    content: Optional[str] = None
    operator_id: Optional[int] = None
    operator_name: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class TicketDetailResponse(BaseModel):
    """工单详情（含处理流水）"""

    ticket: TicketResponse
    logs: List[TicketLogResponse] = Field(default_factory=list)


# ------------------------------------------------------------------
# 机器人配置
# ------------------------------------------------------------------


class SettingsUpdate(BaseModel):
    """机器人配置更新（全量覆盖，未传字段保留原值）"""

    bot_name: Optional[str] = Field(None, max_length=100)
    system_prompt: Optional[str] = None
    model_id: Optional[int] = None
    knowledge_base_ids: Optional[List[int]] = None
    search_mode: Optional[str] = Field(None, max_length=10)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    score_threshold: Optional[float] = Field(None, ge=0.0)
    enable_rerank: Optional[bool] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=32000)
    history_turns: Optional[int] = Field(None, ge=0, le=50)
    human_intents: Optional[List[str]] = None
    human_keywords: Optional[List[str]] = None
    low_confidence_threshold: Optional[float] = Field(None, ge=0.0)
    low_confidence_streak: Optional[int] = Field(None, ge=1, le=10)
    fallback_answer: Optional[str] = None


class SettingsResponse(BaseModel):
    """机器人配置响应"""

    id: int
    bot_name: str
    system_prompt: Optional[str] = None
    model_id: Optional[int] = None
    model_name: str = ""
    knowledge_base_ids: List[int] = Field(default_factory=list)
    knowledge_bases: List[Dict[str, Any]] = Field(default_factory=list)
    search_mode: str = "rrf"
    top_k: int = 5
    score_threshold: float = 0.0
    enable_rerank: bool = False
    temperature: float = 0.4
    max_tokens: int = 1500
    history_turns: int = 6
    human_intents: List[str] = Field(default_factory=list)
    human_keywords: List[str] = Field(default_factory=list)
    low_confidence_threshold: float = 0.35
    low_confidence_streak: int = 2
    fallback_answer: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ------------------------------------------------------------------
# 快捷话术
# ------------------------------------------------------------------


class QuickReplyCreate(BaseModel):
    """快捷话术创建"""

    title: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1, max_length=4000)
    category: str = Field("general", max_length=30)
    sort_order: int = 0


class QuickReplyUpdate(BaseModel):
    """快捷话术更新"""

    title: Optional[str] = Field(None, min_length=1, max_length=100)
    content: Optional[str] = Field(None, min_length=1, max_length=4000)
    category: Optional[str] = Field(None, max_length=30)
    sort_order: Optional[int] = None


class QuickReplyResponse(BaseModel):
    """快捷话术响应"""

    id: int
    title: str
    content: str
    category: str = "general"
    sort_order: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class QuickReplyListResponse(BaseModel):
    """快捷话术列表"""

    items: List[QuickReplyResponse] = Field(default_factory=list)


# ------------------------------------------------------------------
# 统计
# ------------------------------------------------------------------


class AnalyticsOverview(BaseModel):
    """看板概览指标"""

    session_total: int = 0
    session_open: int = 0
    session_pending_human: int = 0
    session_resolved: int = 0
    # AI 独立解决率 = 已解决且全程未转人工 / 已结束会话
    ai_resolve_rate: float = 0.0
    unresolved_rate: float = 0.0
    avg_satisfaction: float = 0.0
    ticket_total: int = 0
    ticket_pending: int = 0
    ticket_overdue: int = 0
    message_total: int = 0


class TrendPoint(BaseModel):
    """趋势单点"""

    date: str
    session_count: int = 0
    message_count: int = 0
    ticket_count: int = 0


class IntentStatItem(BaseModel):
    """意图分布项"""

    intent: str
    label: str = ""
    count: int = 0
    percent: float = 0.0


class SatisfactionStatItem(BaseModel):
    """满意度分布项"""

    score: int
    count: int = 0


class TicketStatItem(BaseModel):
    """工单状态分布项"""

    status: str
    label: str = ""
    count: int = 0


class AnalyticsResponse(BaseModel):
    """看板数据"""

    days: int = 7
    overview: AnalyticsOverview = Field(default_factory=AnalyticsOverview)
    trend: List[TrendPoint] = Field(default_factory=list)
    intents: List[IntentStatItem] = Field(default_factory=list)
    satisfaction: List[SatisfactionStatItem] = Field(default_factory=list)
    tickets: List[TicketStatItem] = Field(default_factory=list)


# ------------------------------------------------------------------
# 业务数据（订单 / 物流 / 商品 / 退换货政策，Demo 示例，供后台维护）
# ------------------------------------------------------------------


class BusinessOrderResponse(BaseModel):
    """订单（只读展示，运营在后台维护）"""

    id: int
    order_no: str
    customer_name: str
    product: str
    amount: float
    status: str
    ordered_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BusinessProductResponse(BaseModel):
    """商品"""

    id: int
    product_no: str
    name: str
    price: float
    warranty: Optional[str] = None
    category: Optional[str] = None
    category_label: str = ""
    description: Optional[str] = None
    features: List[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BusinessShipmentResponse(BaseModel):
    """物流"""

    id: int
    order_no: str
    carrier: Optional[str] = None
    tracking_no: Optional[str] = None
    current_location: Optional[str] = None
    estimated_text: Optional[str] = None
    status: Optional[str] = None

    class Config:
        from_attributes = True


class BusinessReturnPolicyResponse(BaseModel):
    """退换货政策"""

    id: int
    category: str
    category_label: str = ""
    policy_content: str

    class Config:
        from_attributes = True


class BusinessDataResponse(BaseModel):
    """业务数据快照（机器人配置「业务数据」Tab 一次性拉取）"""

    orders: List[BusinessOrderResponse] = Field(default_factory=list)
    products: List[BusinessProductResponse] = Field(default_factory=list)
    shipments: List[BusinessShipmentResponse] = Field(default_factory=list)
    return_policies: List[BusinessReturnPolicyResponse] = Field(default_factory=list)
