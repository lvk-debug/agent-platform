"""
智能客服助手数据模型

七张表（Integer 自增主键，时间戳统一 UTC）：
- support_customers     客户档案（学员/家长）
- support_sessions      咨询会话（AI 模式 / 人工模式）
- support_messages      会话消息（含引用来源、意图、置信度）
- support_tickets       售后工单（退费 / 调课 / 报修 / 投诉）
- support_ticket_logs   工单处理流水（状态流转与处理记录）
- support_settings      机器人配置（全局单例，id 恒为 1）
- support_quick_replies 坐席快捷话术

设计要点：
1. **不复用 Conversation / Message**。客服会话需要客户维度、AI/人工模式切换、
   意图分类、满意度、工单关联等语义，硬套 App 会话体系会退化成字段外挂。
   底层 RAG / LLM / SSE / 鉴权仍全部复用平台既有能力。
2. **枚举用模块级字符串常量**。SQLite 的 Enum 是 VARCHAR + CHECK，新增取值
   必须走 Alembic 迁移；改用常量 + 服务层校验可随时扩展（同学习助手模块做法）。
3. **会话是共享池**：所有坐席可见，接管时写 assignee_id，不按人隔离数据。
4. **模式与状态分离**：mode 回答「现在谁在说话」，status 回答「进展如何」，
   两者正交，避免用一个字段表达两件事导致状态爆炸。
"""

from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)

from app.core.database import UTCDateTime, Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------
# 常量
# ------------------------------------------------------------------


class SessionMode:
    """会话模式：决定消息由 AI 还是坐席产生"""

    AI = "ai"
    HUMAN = "human"

    ALL = (AI, HUMAN)


class SessionStatus:
    """会话状态"""

    OPEN = "open"  # 进行中
    PENDING_HUMAN = "pending_human"  # 待人工：进入待接管队列
    RESOLVED = "resolved"  # 已解决
    CLOSED = "closed"  # 已关闭（归档）

    ALL = (OPEN, PENDING_HUMAN, RESOLVED, CLOSED)

    LABELS = {
        OPEN: "进行中",
        PENDING_HUMAN: "待人工",
        RESOLVED: "已解决",
        CLOSED: "已关闭",
    }


class MessageRole:
    """消息角色

    customer: 客户说的话；agent: 坐席人工回复；ai: AI 自动回复；system: 系统提示
    """

    CUSTOMER = "customer"
    AGENT = "agent"
    AI = "ai"
    SYSTEM = "system"

    ALL = (CUSTOMER, AGENT, AI, SYSTEM)


class TicketType:
    """工单类型"""

    REFUND = "refund"
    RESCHEDULE = "reschedule"
    REPAIR = "repair"
    COMPLAINT = "complaint"
    CONSULT = "consult"
    OTHER = "other"

    ALL = (REFUND, RESCHEDULE, REPAIR, COMPLAINT, CONSULT, OTHER)

    LABELS = {
        REFUND: "退费",
        RESCHEDULE: "调课",
        REPAIR: "报修",
        COMPLAINT: "投诉",
        CONSULT: "咨询",
        OTHER: "其他",
    }


class TicketStatus:
    """工单状态

    合法流转集中在 ALLOWED_TRANSITIONS 声明，服务层据此校验，
    避免出现「已关闭又回到处理中」这类脏状态。
    """

    PENDING = "pending"
    PROCESSING = "processing"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    CLOSED = "closed"

    ALL = (PENDING, PROCESSING, RESOLVED, REJECTED, CLOSED)

    LABELS = {
        PENDING: "待处理",
        PROCESSING: "处理中",
        RESOLVED: "已解决",
        REJECTED: "已驳回",
        CLOSED: "已关闭",
    }

    ALLOWED_TRANSITIONS = {
        PENDING: (PROCESSING, REJECTED, CLOSED),
        PROCESSING: (RESOLVED, REJECTED, CLOSED),
        RESOLVED: (PROCESSING, CLOSED),
        REJECTED: (PROCESSING, CLOSED),
        CLOSED: (),
    }


class TicketPriority:
    """工单优先级"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    ALL = (LOW, NORMAL, HIGH, URGENT)

    LABELS = {LOW: "低", NORMAL: "普通", HIGH: "高", URGENT: "紧急"}


class IntentCategory:
    """意图分类（面向终端用户的自主客服语义）

    与 `docs/智能客服.md` 对齐的 4 类 + `other` 兜底：
    - product_inquiry  商品咨询（功能/价格/质保）→ Knowledge Agent
    - order_query      订单/物流查询               → Tool Agent
    - complaint        投诉/复杂问题               → Escalation Agent（自动建工单）
    - general          问候/闲聊/其他              → Knowledge Agent
    - other            未能归类的兜底

    LABELS 供前端直接渲染中文标签；SENSITIVE 命中即建议转人工
    （涉及投诉情绪的，AI 自行承诺风险高）。
    ROUTE 是 Router 输出意图 → 下游 Agent 的路由映射，供 LangGraph 条件边使用。
    """

    PRODUCT_INQUIRY = "product_inquiry"
    ORDER_QUERY = "order_query"
    COMPLAINT = "complaint"
    GENERAL = "general"
    OTHER = "other"

    ALL = (PRODUCT_INQUIRY, ORDER_QUERY, COMPLAINT, GENERAL, OTHER)

    LABELS = {
        PRODUCT_INQUIRY: "商品咨询",
        ORDER_QUERY: "订单/物流",
        COMPLAINT: "投诉/升级",
        GENERAL: "通用/闲聊",
        OTHER: "其他",
    }

    # Router 意图 → 下游 Agent 路由
    ROUTE = {
        PRODUCT_INQUIRY: "knowledge",
        GENERAL: "knowledge",
        ORDER_QUERY: "tool",
        COMPLAINT: "escalation",
    }

    SENSITIVE = (COMPLAINT,)


class CustomerSource:
    """客户来源渠道"""

    WECHAT = "wechat"
    PHONE = "phone"
    WEB = "web"
    STORE = "store"
    REFERRAL = "referral"
    OTHER = "other"

    ALL = (WECHAT, PHONE, WEB, STORE, REFERRAL, OTHER)

    LABELS = {
        WECHAT: "微信",
        PHONE: "电话",
        WEB: "官网",
        STORE: "门店",
        REFERRAL: "转介绍",
        OTHER: "其他",
    }


class TicketLogAction:
    """工单流水动作"""

    CREATE = "create"
    TRANSITION = "transition"
    ASSIGN = "assign"
    COMMENT = "comment"

    ALL = (CREATE, TRANSITION, ASSIGN, COMMENT)


# 机器人配置的单例 ID：全局只有一条配置行
SUPPORT_SETTINGS_ID = 1


# ------------------------------------------------------------------
# ORM
# ------------------------------------------------------------------


class SupportCustomer(Base):
    """客户档案（学员/家长）

    session_count / ticket_count 为冗余计数，供列表页直接展示，
    由服务层在会话与工单创建时维护。
    """

    __tablename__ = "support_customers"
    __table_args__ = (Index("ix_support_customers_created", "created_at"),)

    id = Column(Integer, primary_key=True, autoincrement=True)

    name = Column(String(100), nullable=False, default="未命名客户")
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(200), nullable=True)
    wechat = Column(String(100), nullable=True)
    source = Column(String(20), nullable=False, default=CustomerSource.OTHER)

    remark = Column(Text, nullable=True)
    tags = Column(JSON, nullable=True)

    session_count = Column(Integer, nullable=False, default=0)
    ticket_count = Column(Integer, nullable=False, default=0)
    last_session_at = Column(UTCDateTime(timezone=True), nullable=True)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportCustomer(id={self.id}, name={self.name!r})>"


class SupportSession(Base):
    """咨询会话

    mode 与 status 正交：mode=ai 时消息由 AI 产生，坐席可随时切 human 接管；
    mode=human 时 AI 退居「建议回复」辅助。
    """

    __tablename__ = "support_sessions"
    __table_args__ = (
        Index("ix_support_sessions_status", "status"),
        Index("ix_support_sessions_intent", "intent"),
        Index("ix_support_sessions_assignee", "assignee_id"),
        Index("ix_support_sessions_customer", "customer_id"),
        Index("ix_support_sessions_updated", "updated_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(
        Integer,
        ForeignKey("support_customers.id", ondelete="SET NULL"),
        nullable=True,
    )

    title = Column(String(500), nullable=False, default="")
    mode = Column(String(20), nullable=False, default=SessionMode.AI)
    status = Column(String(20), nullable=False, default=SessionStatus.OPEN)

    intent = Column(String(30), nullable=True)
    intent_confidence = Column(Float, nullable=False, default=0.0)

    # 接管坐席；会话是共享池，未接管时为空
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    message_count = Column(Integer, nullable=False, default=0)
    last_message_at = Column(UTCDateTime(timezone=True), nullable=True)
    last_message_preview = Column(String(300), nullable=False, default="")

    # 连续低置信次数：达到阈值自动转人工，出现有把握的回答时清零
    low_confidence_streak = Column(Integer, nullable=False, default=0)

    # 满意度：1~5 分，未评价为空
    satisfaction = Column(Integer, nullable=True)
    satisfaction_comment = Column(Text, nullable=True)

    resolved_at = Column(UTCDateTime(timezone=True), nullable=True)
    closed_at = Column(UTCDateTime(timezone=True), nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportSession(id={self.id}, mode={self.mode}, status={self.status})>"


class SupportMessage(Base):
    """会话消息

    AI 消息自包含本次回答的引用来源、意图与置信度，
    回看历史时无需再查向量库即可还原「为什么这么答」。
    """

    __tablename__ = "support_messages"
    __table_args__ = (Index("ix_support_messages_session", "session_id", "id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("support_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role = Column(String(20), nullable=False, default=MessageRole.CUSTOMER)
    content = Column(Text, nullable=False, default="")
    # [{kb_id, kb_name, document_id, document_name, segment_id, content, score}]
    references = Column(JSON, nullable=True)
    # Agent 处理过程留痕（思考链 steps、工具调用 tool_calls），历史消息无需重跑即可还原
    trace = Column(JSON, nullable=True)

    intent = Column(String(30), nullable=True)
    confidence = Column(Float, nullable=True)

    model = Column(String(200), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    # 生成失败时记录原因，消息本身仍保留（前端显示为错误气泡，不丢用户输入）
    error = Column(Text, nullable=True)

    # 发言坐席；AI 消息为空
    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<SupportMessage(id={self.id}, session={self.session_id}, "
            f"role={self.role})>"
        )


class SupportTicket(Base):
    """售后工单"""

    __tablename__ = "support_tickets"
    __table_args__ = (
        Index("ix_support_tickets_status", "status"),
        Index("ix_support_tickets_type", "type"),
        Index("ix_support_tickets_assignee", "assignee_id"),
        Index("ix_support_tickets_customer", "customer_id"),
        Index("ix_support_tickets_created", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_no = Column(String(32), nullable=False, unique=True)

    customer_id = Column(
        Integer,
        ForeignKey("support_customers.id", ondelete="SET NULL"),
        nullable=True,
    )
    # 来源会话：从会话一键建单时回链，便于追溯上下文
    session_id = Column(
        Integer, ForeignKey("support_sessions.id", ondelete="SET NULL"), nullable=True
    )

    type = Column(String(20), nullable=False, default=TicketType.OTHER)
    title = Column(String(500), nullable=False, default="")
    description = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default=TicketStatus.PENDING)
    priority = Column(String(20), nullable=False, default=TicketPriority.NORMAL)

    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    due_at = Column(UTCDateTime(timezone=True), nullable=True)
    resolved_at = Column(UTCDateTime(timezone=True), nullable=True)
    closed_at = Column(UTCDateTime(timezone=True), nullable=True)

    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportTicket(id={self.id}, no={self.ticket_no}, status={self.status})>"


class SupportTicketLog(Base):
    """工单处理流水

    每次状态流转、指派、留言都落一条，天然形成审计记录；
    时间线展示直接按 id 正序读取即可。
    """

    __tablename__ = "support_ticket_logs"
    __table_args__ = (Index("ix_support_ticket_logs_ticket", "ticket_id", "id"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
    )

    action = Column(String(20), nullable=False, default=TicketLogAction.COMMENT)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=True)
    content = Column(Text, nullable=True)

    operator_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)

    def __repr__(self) -> str:
        return (
            f"<SupportTicketLog(id={self.id}, ticket={self.ticket_id}, "
            f"action={self.action})>"
        )


class SupportSettings(Base):
    """机器人配置（全局单例，id 恒为 SUPPORT_SETTINGS_ID）

    知识库复用平台「知识库」模块：这里只存绑定的 kb_id 列表，
    检索走 KnowledgeService.search，不另建 FAQ 表。
    """

    __tablename__ = "support_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    bot_name = Column(String(100), nullable=False, default="智能客服助手")
    system_prompt = Column(Text, nullable=True)
    model_id = Column(Integer, nullable=True)

    knowledge_base_ids = Column(JSON, nullable=True)
    search_mode = Column(String(10), nullable=False, default="rrf")
    top_k = Column(Integer, nullable=False, default=5)
    score_threshold = Column(Float, nullable=False, default=0.0)
    enable_rerank = Column(Boolean, nullable=False, default=False)

    temperature = Column(Float, nullable=False, default=0.4)
    max_tokens = Column(Integer, nullable=False, default=1500)
    history_turns = Column(Integer, nullable=False, default=6)

    # ---- 转人工触发规则（配置化，避免硬编码）----
    # 命中这些意图直接建议转人工
    human_intents = Column(JSON, nullable=True)
    # 客户消息包含这些关键词直接转人工
    human_keywords = Column(JSON, nullable=True)
    # 检索最高分低于该阈值视为「没把握」
    low_confidence_threshold = Column(Float, nullable=False, default=0.35)
    # 连续多少次没把握后自动置为待人工
    low_confidence_streak = Column(Integer, nullable=False, default=2)
    # 没把握时先说的兜底话术，再引导转人工或建工单
    fallback_answer = Column(Text, nullable=True)

    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportSettings(id={self.id}, bot_name={self.bot_name!r})>"


class SupportQuickReply(Base):
    """坐席快捷话术

    工作台输入框旁直接插入，避免高频问题（报名流程、退费口径）反复手打。
    """

    __tablename__ = "support_quick_replies"

    id = Column(Integer, primary_key=True, autoincrement=True)

    title = Column(String(100), nullable=False, default="")
    content = Column(Text, nullable=False, default="")
    category = Column(String(30), nullable=False, default="general")
    sort_order = Column(Integer, nullable=False, default=0)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(UTCDateTime(timezone=True), default=_utcnow)
    updated_at = Column(UTCDateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<SupportQuickReply(id={self.id}, title={self.title!r})>"
