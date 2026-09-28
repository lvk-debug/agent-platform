"""
智能客服助手主服务

职责：机器人配置、客户档案、咨询会话、消息落库、运营统计、快捷话术。

设计要点：
1. **会话是共享池**：不按坐席隔离数据，接管时写 assignee_id。
2. **响应组装在 Service 层**：关联名（客户名/坐席名）与中文标签一并拼好，
   endpoint 只做校验与序列化，避免 ORM 对象泄漏到接口层，也避免 N+1 查询。
3. **统计走 SQL 聚合**：GROUP BY + COUNT，不全表载入 Python 再遍历。
4. **问答永不因配置缺失而中断**：模型/知识库没配好时降级为提示文案，不抛异常。
"""

from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.knowledge import KnowledgeBase
from app.models.model import Model
from app.models.support import (
    SUPPORT_SETTINGS_ID,
    CustomerSource,
    IntentCategory,
    MessageRole,
    SessionMode,
    SessionStatus,
    SupportCustomer,
    SupportMessage,
    SupportQuickReply,
    SupportSession,
    SupportSettings,
    SupportTicket,
    TicketStatus,
)
from app.models.support_business import (
    ReturnCategory,
    SupportOrder,
    SupportProduct,
    SupportReturnPolicy,
    SupportShipment,
)
from app.models.user import User

from app.schemas.support import (
    CustomerCreate,
    CustomerUpdate,
    QuickReplyCreate,
    QuickReplyUpdate,
    SessionCreate,
    SessionCloseRequest,
    SessionUpdate,
    SettingsUpdate,
    SupportReference,
)
from app.utils.logger import logger

DEFAULT_SYSTEM_PROMPT = """你是「{bot_name}」，一家素质教育机构（兴趣课、科学课等）的智能客服。

工作方式：
1. 只依据【知识库资料】回答；资料里没有的信息，明确说明「这块我需要帮您确认」，不要编造价格、课时、政策。
2. 语气温和专业，先回应诉求再给结论，必要时分点说明，避免长篇大论。
3. 涉及退费、调课、投诉、报修等敏感事项，不要替机构做承诺，
   说清需要登记核实，并主动引导转人工或留下联系方式。
4. 用中文回答。"""

# 命中这些意图 / 关键词直接建议转人工：涉及钱或情绪，AI 自行承诺风险高
DEFAULT_HUMAN_INTENTS: List[str] = list(IntentCategory.SENSITIVE)
DEFAULT_HUMAN_KEYWORDS: List[str] = [
    "转人工",
    "人工客服",
    "找人工",
    "投诉",
    "退费",
    "退款",
    "举报",
]
DEFAULT_FALLBACK_ANSWER = (
    "抱歉，这个问题我没在资料里找到可靠答案，为避免给您错误信息，"
    "我帮您转接人工客服确认一下，可以吗？"
)

# 列表页单页条数上限
MAX_PAGE_SIZE = 100


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _display_name(user: Optional[User]) -> str:
    """坐席展示名：优先姓名，回退用户名"""
    if not user:
        return ""
    return user.full_name or user.username or ""


def _preview(text: str, limit: int = 100) -> str:
    """会话列表的消息预览：压成单行并截断"""
    flat = " ".join((text or "").split())
    return flat[:limit]


class SupportService:
    """智能客服主服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 机器人配置
    # ------------------------------------------------------------------

    def get_settings(self) -> SupportSettings:
        """取全局配置；不存在则按默认落一条（懒初始化，免去启动迁移）"""
        row = (
            self.db.query(SupportSettings)
            .filter(SupportSettings.id == SUPPORT_SETTINGS_ID)
            .first()
        )
        if row:
            return row

        row = SupportSettings(
            id=SUPPORT_SETTINGS_ID,
            bot_name="智能客服助手",
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            human_intents=list(DEFAULT_HUMAN_INTENTS),
            human_keywords=list(DEFAULT_HUMAN_KEYWORDS),
            fallback_answer=DEFAULT_FALLBACK_ANSWER,
            top_k=settings.SUPPORT_CHAT_TOP_K,
            temperature=settings.SUPPORT_CHAT_TEMPERATURE,
            max_tokens=settings.SUPPORT_CHAT_MAX_TOKENS,
            history_turns=settings.SUPPORT_CHAT_HISTORY_TURNS,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_settings(self, user_id: int, data: SettingsUpdate) -> SupportSettings:
        """局部更新：只覆盖显式传入的字段（None 表示不改动）"""
        row = self.get_settings()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        row.updated_by = user_id
        row.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def settings_payload(self, row: SupportSettings) -> Dict[str, Any]:
        """配置响应：补上模型名与知识库名，前端无需再查"""
        kb_ids = [int(item) for item in (row.knowledge_base_ids or []) if item]
        knowledge_bases: List[Dict[str, Any]] = []
        if kb_ids:
            rows = (
                self.db.query(KnowledgeBase)
                .filter(KnowledgeBase.id.in_(kb_ids))
                .all()
            )
            knowledge_bases = [{"id": item.id, "name": item.name} for item in rows]

        model_name = ""
        if row.model_id:
            model = self.db.query(Model).filter(Model.id == row.model_id).first()
            model_name = f"{model.name}（{model.model_id}）" if model else ""

        return {
            "id": row.id,
            "bot_name": row.bot_name,
            "system_prompt": row.system_prompt,
            "model_id": row.model_id,
            "model_name": model_name,
            "knowledge_base_ids": kb_ids,
            "knowledge_bases": knowledge_bases,
            "search_mode": row.search_mode,
            "top_k": row.top_k,
            "score_threshold": row.score_threshold,
            "enable_rerank": row.enable_rerank,
            "temperature": row.temperature,
            "max_tokens": row.max_tokens,
            "history_turns": row.history_turns,
            "human_intents": list(row.human_intents or []),
            "human_keywords": list(row.human_keywords or []),
            "low_confidence_threshold": row.low_confidence_threshold,
            "low_confidence_streak": row.low_confidence_streak,
            "fallback_answer": row.fallback_answer,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------
    # 客户
    # ------------------------------------------------------------------

    def list_customers(
        self,
        keyword: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self.db.query(SupportCustomer)
        if keyword:
            # 手机号允许部分匹配：坐席常只记得后四位
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    SupportCustomer.name.like(like),
                    SupportCustomer.phone.like(like),
                    SupportCustomer.wechat.like(like),
                    SupportCustomer.email.like(like),
                )
            )
        if source:
            query = query.filter(SupportCustomer.source == source)

        total = query.count()
        rows = (
            query.order_by(SupportCustomer.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return [self.customer_payload(row) for row in rows], total

    def create_customer(self, user_id: int, data: CustomerCreate) -> SupportCustomer:
        row = SupportCustomer(
            name=data.name,
            phone=data.phone,
            email=data.email,
            wechat=data.wechat,
            source=data.source or CustomerSource.OTHER,
            remark=data.remark,
            tags=list(data.tags or []),
            created_by=user_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_customer(self, customer_id: int) -> Optional[SupportCustomer]:
        return (
            self.db.query(SupportCustomer)
            .filter(SupportCustomer.id == customer_id)
            .first()
        )

    def update_customer(
        self, customer_id: int, data: CustomerUpdate
    ) -> Optional[SupportCustomer]:
        row = self.get_customer(customer_id)
        if not row:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_customer(self, customer_id: int) -> bool:
        row = self.get_customer(customer_id)
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    def customer_payload(self, row: SupportCustomer) -> Dict[str, Any]:
        return {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "email": row.email,
            "wechat": row.wechat,
            "source": row.source,
            "source_label": CustomerSource.LABELS.get(row.source, row.source),
            "remark": row.remark,
            "tags": list(row.tags or []),
            "session_count": row.session_count or 0,
            "ticket_count": row.ticket_count or 0,
            "last_session_at": row.last_session_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------
    # 会话
    # ------------------------------------------------------------------

    def list_sessions(
        self,
        status: Optional[str] = None,
        mode: Optional[str] = None,
        intent: Optional[str] = None,
        assignee_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self.db.query(SupportSession)
        if status:
            query = query.filter(SupportSession.status == status)
        if mode:
            query = query.filter(SupportSession.mode == mode)
        if intent:
            query = query.filter(SupportSession.intent == intent)
        if assignee_id is not None:
            # -1 表示「未接管」，是列表页的常用筛选
            query = query.filter(
                SupportSession.assignee_id == (None if assignee_id == -1 else assignee_id)
            )
        if customer_id:
            query = query.filter(SupportSession.customer_id == customer_id)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    SupportSession.title.like(like),
                    SupportSession.last_message_preview.like(like),
                )
            )

        total = query.count()
        rows = (
            query.order_by(SupportSession.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return self.session_payloads(rows), total

    def create_session(self, user_id: int, data: SessionCreate) -> SupportSession:
        mode = data.mode if data.mode in SessionMode.ALL else SessionMode.AI
        row = SupportSession(
            customer_id=data.customer_id,
            title=data.title or "",
            mode=mode,
            status=SessionStatus.OPEN,
            created_by=user_id,
            # 人工模式建会话即视为已接管：坐席开这个会话就是为了自己回
            assignee_id=user_id if mode == SessionMode.HUMAN else None,
        )
        self.db.add(row)
        if data.customer_id:
            customer = self.get_customer(data.customer_id)
            if customer:
                customer.session_count = (customer.session_count or 0) + 1
                customer.last_session_at = _utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_session(self, session_id: int) -> Optional[SupportSession]:
        return (
            self.db.query(SupportSession)
            .filter(SupportSession.id == session_id)
            .first()
        )

    def update_session(
        self, session_id: int, data: SessionUpdate
    ) -> Optional[SupportSession]:
        row = self.get_session(session_id)
        if not row:
            return None
        if data.title is not None:
            row.title = data.title
        if data.customer_id is not None:
            row.customer_id = data.customer_id
        if data.intent is not None:
            row.intent = data.intent
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_session(self, session_id: int) -> bool:
        row = self.get_session(session_id)
        if not row:
            return False
        self.db.delete(row)  # 消息靠外键 CASCADE 一并删除
        self.db.commit()
        return True

    def take_over(
        self, session_id: int, user_id: int, reason: Optional[str] = None
    ) -> Optional[SupportSession]:
        """坐席接管：切人工模式、记录负责人、待人工状态回到进行中"""
        row = self.get_session(session_id)
        if not row:
            return None
        if row.status == SessionStatus.CLOSED:
            return None

        row.mode = SessionMode.HUMAN
        row.assignee_id = user_id
        if row.status == SessionStatus.PENDING_HUMAN:
            row.status = SessionStatus.OPEN
        if reason:
            self.append_message(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"已转人工：{reason}",
                operator_id=user_id,
            )
        self.db.commit()
        self.db.refresh(row)
        return row

    def transfer(
        self, session_id: int, assignee_id: Optional[int]
    ) -> Optional[SupportSession]:
        """转交其他坐席；assignee_id 为空表示退回公共池（同时切回 AI 模式）"""
        row = self.get_session(session_id)
        if not row:
            return None
        row.assignee_id = assignee_id
        if assignee_id is None:
            row.mode = SessionMode.AI
        self.db.commit()
        self.db.refresh(row)
        return row

    def switch_mode(self, session_id: int, mode: str) -> Optional[SupportSession]:
        row = self.get_session(session_id)
        if not row:
            return None
        row.mode = mode
        self.db.commit()
        self.db.refresh(row)
        return row

    def close_session(
        self, session_id: int, user_id: int, data: SessionCloseRequest
    ) -> Optional[SupportSession]:
        row = self.get_session(session_id)
        if not row:
            return None
        status = (
            data.status if data.status in (SessionStatus.RESOLVED, SessionStatus.CLOSED)
            else SessionStatus.RESOLVED
        )
        now = _utcnow()
        row.status = status
        row.assignee_id = row.assignee_id or user_id
        if data.satisfaction is not None:
            row.satisfaction = data.satisfaction
        if data.satisfaction_comment:
            row.satisfaction_comment = data.satisfaction_comment
        if status == SessionStatus.RESOLVED and not row.resolved_at:
            row.resolved_at = now
        if status == SessionStatus.CLOSED and not row.closed_at:
            row.closed_at = now
        self.db.commit()
        self.db.refresh(row)
        return row

    def session_payload(self, row: SupportSession) -> Dict[str, Any]:
        """单条会话响应（写操作后回调用，可接受一次额外查询）"""
        return self.session_payloads([row])[0]

    def session_payloads(self, rows: List[SupportSession]) -> List[Dict[str, Any]]:
        """批量组装会话响应

        列表接口一次查齐客户与坐席再拼装：逐条查会退化成 2N+1 次查询，
        20 条一页就是 41 次，列表刷新频繁时很明显。
        """
        customer_ids = {row.customer_id for row in rows if row.customer_id}
        assignee_ids = {row.assignee_id for row in rows if row.assignee_id}

        customers: Dict[int, SupportCustomer] = {}
        if customer_ids:
            customers = {
                item.id: item
                for item in self.db.query(SupportCustomer)
                .filter(SupportCustomer.id.in_(customer_ids))
                .all()
            }
        users: Dict[int, User] = {}
        if assignee_ids:
            users = {
                item.id: item
                for item in self.db.query(User).filter(User.id.in_(assignee_ids)).all()
            }

        # 批量取每个会话「最新一条 AI 消息」的处理轨迹，供列表查看运行日志（避免 N+1）
        trace_map = self._latest_ai_traces([row.id for row in rows])

        return [
            self._session_dict(
                row,
                customers.get(row.customer_id) if row.customer_id else None,
                users.get(row.assignee_id) if row.assignee_id else None,
                trace_map,
            )
            for row in rows
        ]

    def _session_dict(
        self,
        row: SupportSession,
        customer: Optional[SupportCustomer],
        assignee: Optional[User],
        trace_map: Optional[Dict[int, Any]] = None,
    ) -> Dict[str, Any]:
        """会话响应：补齐客户名、坐席名与中文标签"""
        return {
            "id": row.id,
            "customer_id": row.customer_id,
            "customer_name": customer.name if customer else "",
            "title": row.title,
            "mode": row.mode,
            "status": row.status,
            "status_label": SessionStatus.LABELS.get(row.status, row.status),
            "intent": row.intent,
            "intent_label": IntentCategory.LABELS.get(row.intent, "") if row.intent else "",
            "intent_confidence": row.intent_confidence or 0.0,
            "assignee_id": row.assignee_id,
            "assignee_name": _display_name(assignee),
            "message_count": row.message_count or 0,
            "last_message_at": row.last_message_at,
            "last_message_preview": row.last_message_preview or "",
            "low_confidence_streak": row.low_confidence_streak or 0,
            "satisfaction": row.satisfaction,
            "satisfaction_comment": row.satisfaction_comment,
            "resolved_at": row.resolved_at,
            "closed_at": row.closed_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            # 最新一条 AI 消息的处理轨迹（节点步骤 + 工具调用 + 工单 + 引用），供列表查看运行日志
            "last_ai_trace": (trace_map or {}).get(row.id),
        }

    def _latest_ai_traces(self, session_ids: List[int]) -> Dict[int, Any]:
        """取每个会话最新一条带轨迹的 AI 消息的 trace（JSON），按 session_id 索引"""
        if not session_ids:
            return {}
        subq = (
            self.db.query(
                SupportMessage.session_id,
                func.max(SupportMessage.id).label("mid"),
            )
            .filter(
                SupportMessage.session_id.in_(session_ids),
                SupportMessage.role == MessageRole.AI,
                SupportMessage.trace.isnot(None),
            )
            .group_by(SupportMessage.session_id)
            .subquery()
        )
        rows = (
            self.db.query(SupportMessage.session_id, SupportMessage.trace)
            .join(subq, SupportMessage.id == subq.c.mid)
            .all()
        )
        return {row.session_id: row.trace for row in rows}

    # ------------------------------------------------------------------
    # 消息
    # ------------------------------------------------------------------

    def list_messages(self, session_id: int, limit: int = 200) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(SupportMessage)
            .filter(SupportMessage.session_id == session_id)
            .order_by(SupportMessage.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return self.message_payloads(rows)

    def append_message(
        self,
        session_id: int,
        role: str,
        content: str,
        references: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        model: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
        operator_id: Optional[int] = None,
        refresh_session: bool = True,
    ) -> SupportMessage:
        """写入一条消息并同步会话的计数与预览"""
        row = SupportMessage(
            session_id=session_id,
            role=role,
            content=content or "",
            references=references,
            intent=intent,
            confidence=confidence,
            model=model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            error=error,
            operator_id=operator_id,
        )
        self.db.add(row)
        if refresh_session:
            self._touch_session(session_id, content or "", increment=True)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _touch_session(
        self, session_id: int, preview: str, increment: bool = True
    ) -> None:
        """刷新会话的最后消息与条数

        用 UPDATE 语句而不是先查后改：会话更新与消息写入在同一事务里，
        直接 UPDATE 可避免长事务下的读改写竞争。
        """
        session = self.get_session(session_id)
        if not session:
            return
        if increment:
            session.message_count = (session.message_count or 0) + 1
        if preview and session.id:
            session.last_message_preview = _preview(preview)
        session.last_message_at = _utcnow()
        session.updated_at = _utcnow()

    def message_payload(self, row: SupportMessage) -> Dict[str, Any]:
        """单条消息响应（发送后回调用）"""
        return self.message_payloads([row])[0]

    def message_payloads(self, rows: List[SupportMessage]) -> List[Dict[str, Any]]:
        """批量组装消息响应：坐席名一次查齐，避免历史消息 200 条查 200 次"""
        user_ids = {row.operator_id for row in rows if row.operator_id}
        users: Dict[int, User] = {}
        if user_ids:
            users = {
                item.id: item
                for item in self.db.query(User).filter(User.id.in_(user_ids)).all()
            }
        return [
            self._message_dict(
                row, users.get(row.operator_id) if row.operator_id else None
            )
            for row in rows
        ]

    def _message_dict(
        self, row: SupportMessage, operator: Optional[User]
    ) -> Dict[str, Any]:
        refs = [
            SupportReference(**item).model_dump()
            for item in (row.references or [])
            if isinstance(item, dict)
        ]
        return {
            "id": row.id,
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "references": refs,
            "intent": row.intent,
            "intent_label": IntentCategory.LABELS.get(row.intent, "") if row.intent else "",
            "confidence": row.confidence,
            "model": row.model,
            "tokens_used": row.tokens_used,
            "latency_ms": row.latency_ms,
            "error": row.error,
            "operator_id": row.operator_id,
            "operator_name": _display_name(operator),
            "trace": row.trace,
            "created_at": row.created_at,
        }



    # ------------------------------------------------------------------
    # 快捷话术
    # ------------------------------------------------------------------

    def list_quick_replies(
        self, category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = self.db.query(SupportQuickReply)
        if category:
            query = query.filter(SupportQuickReply.category == category)
        rows = query.order_by(
            SupportQuickReply.sort_order.asc(), SupportQuickReply.id.asc()
        ).all()
        return [self.quick_reply_payload(row) for row in rows]

    def create_quick_reply(
        self, user_id: int, data: QuickReplyCreate
    ) -> SupportQuickReply:
        row = SupportQuickReply(
            title=data.title,
            content=data.content,
            category=data.category or "general",
            sort_order=data.sort_order or 0,
            created_by=user_id,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_quick_reply(
        self, reply_id: int, data: QuickReplyUpdate
    ) -> Optional[SupportQuickReply]:
        row = (
            self.db.query(SupportQuickReply)
            .filter(SupportQuickReply.id == reply_id)
            .first()
        )
        if not row:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(row, field, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_quick_reply(self, reply_id: int) -> bool:
        row = (
            self.db.query(SupportQuickReply)
            .filter(SupportQuickReply.id == reply_id)
            .first()
        )
        if not row:
            return False
        self.db.delete(row)
        self.db.commit()
        return True

    @staticmethod
    def quick_reply_payload(row: SupportQuickReply) -> Dict[str, Any]:
        return {
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "category": row.category,
            "sort_order": row.sort_order,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    # ------------------------------------------------------------------
    # 运营统计
    # ------------------------------------------------------------------

    def analytics(self, days: int = 7) -> Dict[str, Any]:
        """看板数据

        全部走 SQL 聚合：会话/消息/工单三张表各按天分组一次，
        不做全表载入，避免数据量上来后接口变慢。
        """
        days = max(1, min(days, 90))
        today = _utcnow().date()
        start_date = today - timedelta(days=days - 1)
        start_dt = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)

        total = self.db.query(func.count(SupportSession.id)).scalar() or 0
        status_counts = dict(
            self.db.query(SupportSession.status, func.count(SupportSession.id))
            .group_by(SupportSession.status)
            .all()
        )
        # AI 独立解决率：已结束（已解决/已关闭）且仍是 AI 模式的会话占比
        finished_q = self.db.query(func.count(SupportSession.id)).filter(
            SupportSession.status.in_([SessionStatus.RESOLVED, SessionStatus.CLOSED])
        )
        finished = finished_q.scalar() or 0
        ai_finished = (
            finished_q.filter(SupportSession.mode == SessionMode.AI).scalar() or 0
        )
        avg_satisfaction = (
            self.db.query(func.avg(SupportSession.satisfaction))
            .filter(SupportSession.satisfaction.isnot(None))
            .scalar()
            or 0.0
        )
        message_total = self.db.query(func.count(SupportMessage.id)).scalar() or 0

        open_ticket_statuses = [TicketStatus.PENDING, TicketStatus.PROCESSING]
        ticket_total = self.db.query(func.count(SupportTicket.id)).scalar() or 0
        ticket_pending = (
            self.db.query(func.count(SupportTicket.id))
            .filter(SupportTicket.status.in_(open_ticket_statuses))
            .scalar()
            or 0
        )
        ticket_overdue = (
            self.db.query(func.count(SupportTicket.id))
            .filter(
                SupportTicket.due_at.isnot(None),
                SupportTicket.due_at < _utcnow(),
                SupportTicket.status.in_(open_ticket_statuses),
            )
            .scalar()
            or 0
        )

        overview = {
            "session_total": total,
            "session_open": status_counts.get(SessionStatus.OPEN, 0),
            "session_pending_human": status_counts.get(SessionStatus.PENDING_HUMAN, 0),
            "session_resolved": status_counts.get(SessionStatus.RESOLVED, 0),
            "ai_resolve_rate": round(ai_finished / finished * 100, 1) if finished else 0.0,
            "unresolved_rate": (
                round(
                    status_counts.get(SessionStatus.PENDING_HUMAN, 0) / total * 100, 1
                )
                if total
                else 0.0
            ),
            "avg_satisfaction": round(float(avg_satisfaction), 2),
            "ticket_total": ticket_total,
            "ticket_pending": ticket_pending,
            "ticket_overdue": ticket_overdue,
            "message_total": message_total,
        }

        # 按天分组；缺的日期补 0，前端折线图才不会出现断点
        session_trend = self._count_by_day(SupportSession.created_at, start_dt)
        message_trend = self._count_by_day(SupportMessage.created_at, start_dt)
        ticket_trend = self._count_by_day(SupportTicket.created_at, start_dt)
        trend = []
        for offset in range(days):
            day = start_date + timedelta(days=offset)
            key = day.isoformat()
            trend.append(
                {
                    "date": key,
                    "session_count": session_trend.get(key, 0),
                    "message_count": message_trend.get(key, 0),
                    "ticket_count": ticket_trend.get(key, 0),
                }
            )

        intent_rows = (
            self.db.query(SupportSession.intent, func.count(SupportSession.id))
            .filter(SupportSession.intent.isnot(None))
            .group_by(SupportSession.intent)
            .all()
        )
        intent_total = sum(count for _, count in intent_rows) or 1
        intents = [
            {
                "intent": intent,
                "label": IntentCategory.LABELS.get(intent, intent),
                "count": count,
                "percent": round(count / intent_total * 100, 1),
            }
            for intent, count in sorted(intent_rows, key=lambda item: -item[1])
        ]

        satisfaction_rows = (
            self.db.query(SupportSession.satisfaction, func.count(SupportSession.id))
            .filter(SupportSession.satisfaction.isnot(None))
            .group_by(SupportSession.satisfaction)
            .all()
        )
        satisfaction = [
            {"score": score, "count": count} for score, count in satisfaction_rows
        ]

        ticket_rows = (
            self.db.query(SupportTicket.status, func.count(SupportTicket.id))
            .group_by(SupportTicket.status)
            .all()
        )
        tickets = [
            {
                "status": status,
                "label": TicketStatus.LABELS.get(status, status),
                "count": count,
            }
            for status, count in ticket_rows
        ]

        return {
            "days": days,
            "overview": overview,
            "trend": trend,
            "intents": intents,
            "satisfaction": satisfaction,
            "tickets": tickets,
        }

    def _count_by_day(self, column, start_dt: datetime) -> Dict[str, int]:
        """按 UTC 日期分组计数，返回 {YYYY-MM-DD: count}"""
        rows = (
            self.db.query(func.date(column).label("day"), func.count())
            .filter(column >= start_dt)
            .group_by("day")
            .all()
        )
        result: Dict[str, int] = {}
        for day, count in rows:
            if not day:
                continue
            # SQLite 返回字符串，PostgreSQL 返回 date 对象，统一成字符串
            result[day.isoformat() if hasattr(day, "isoformat") else str(day)] = count
        return result

    # ------------------------------------------------------------------
    # 业务数据（Demo 示例：订单 / 物流 / 商品 / 退换货政策）
    # ------------------------------------------------------------------

    def get_business_data(self) -> Dict[str, Any]:
        """一次性拉取业务数据快照，供机器人配置「业务数据」Tab 展示"""
        orders = self.db.query(SupportOrder).order_by(SupportOrder.order_no).all()
        products = self.db.query(SupportProduct).order_by(SupportProduct.product_no).all()
        shipments = (
            self.db.query(SupportShipment).order_by(SupportShipment.order_no).all()
        )
        policies = (
            self.db.query(SupportReturnPolicy)
            .order_by(SupportReturnPolicy.category)
            .all()
        )
        return {
            "orders": [self._order_dict(o) for o in orders],
            "products": [self._product_dict(p) for p in products],
            "shipments": [self._shipment_dict(s) for s in shipments],
            "return_policies": [self._policy_dict(p) for p in policies],
        }

    @staticmethod
    def _order_dict(row: SupportOrder) -> Dict[str, Any]:
        return {
            "id": row.id,
            "order_no": row.order_no,
            "customer_name": row.customer_name,
            "product": row.product,
            "amount": row.amount,
            "status": row.status,
            "ordered_at": row.ordered_at,
        }

    @staticmethod
    def _product_dict(row: SupportProduct) -> Dict[str, Any]:
        return {
            "id": row.id,
            "product_no": row.product_no,
            "name": row.name,
            "price": row.price,
            "warranty": row.warranty,
            "category": row.category,
            "category_label": ReturnCategory.LABELS.get(row.category, row.category or ""),
            "description": row.description,
            "features": list(row.features or []),
        }

    @staticmethod
    def _shipment_dict(row: SupportShipment) -> Dict[str, Any]:
        return {
            "id": row.id,
            "order_no": row.order_no,
            "carrier": row.carrier,
            "tracking_no": row.tracking_no,
            "current_location": row.current_location,
            "estimated_text": row.estimated_text,
            "status": row.status,
        }

    @staticmethod
    def _policy_dict(row: SupportReturnPolicy) -> Dict[str, Any]:
        return {
            "id": row.id,
            "category": row.category,
            "category_label": row.category_label
            or ReturnCategory.LABELS.get(row.category, row.category),
            "policy_content": row.policy_content,
        }

    def reset_business_data(self) -> None:
        """清空并重新写入示例数据（运营在后台「恢复示例」用）"""
        from app.core.seed import seed_support_business

        for model in (SupportOrder, SupportShipment, SupportProduct, SupportReturnPolicy):
            self.db.query(model).delete()
        self.db.commit()
        seed_support_business(self.db)


def get_support_service(db: Session) -> SupportService:
    """客服主服务工厂"""
    return SupportService(db)
