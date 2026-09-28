"""
智能客服工单服务

职责：工单 CRUD、状态机校验、处理流水、从会话一键建单。

设计要点：
1. **状态机集中校验**。合法流转只写在 TicketStatus.ALLOWED_TRANSITIONS 一处，
   服务层照它校验，非法流转直接抛 ValueError 由端点转 400。
2. **每次变动都落流水**。状态流转、指派、留言统一进 support_ticket_logs，
   天然形成审计记录，前端时间线直接按 id 正序渲染。
3. **建单即回链会话**。从会话一键建单时记下 session_id，
   工单详情可回看当时聊了什么，避免坐席在两个系统之间对不上号。
"""

import secrets
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.support import (
    SupportCustomer,
    SupportMessage,
    SupportSession,
    SupportTicket,
    SupportTicketLog,
    TicketLogAction,
    TicketPriority,
    TicketStatus,
    TicketType,
)
from app.models.user import User
from app.schemas.support import (
    TicketCommentRequest,
    TicketCreate,
    TicketTransitionRequest,
    TicketUpdate,
)
from app.services.support import SupportService

# 未闭环的状态：统计「待处理」与「是否超时」都以此为准
OPEN_STATUSES = (TicketStatus.PENDING, TicketStatus.PROCESSING)

MAX_PAGE_SIZE = 100


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _display_name(user: Optional[User]) -> str:
    if not user:
        return ""
    return user.full_name or user.username or ""


class SupportTicketService:
    """工单服务"""

    def __init__(self, db: Session):
        self.db = db
        self.support = SupportService(db)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def list_tickets(
        self,
        status: Optional[str] = None,
        type: Optional[str] = None,
        priority: Optional[str] = None,
        assignee_id: Optional[int] = None,
        customer_id: Optional[int] = None,
        keyword: Optional[str] = None,
        only_overdue: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self.db.query(SupportTicket)
        if status:
            query = query.filter(SupportTicket.status == status)
        if type:
            query = query.filter(SupportTicket.type == type)
        if priority:
            query = query.filter(SupportTicket.priority == priority)
        if assignee_id is not None:
            query = query.filter(
                SupportTicket.assignee_id == (None if assignee_id == -1 else assignee_id)
            )
        if customer_id:
            query = query.filter(SupportTicket.customer_id == customer_id)
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                or_(
                    SupportTicket.title.like(like),
                    SupportTicket.ticket_no.like(like),
                )
            )
        if only_overdue:
            query = query.filter(
                SupportTicket.due_at.isnot(None),
                SupportTicket.due_at < _utcnow(),
                SupportTicket.status.in_(OPEN_STATUSES),
            )

        total = query.count()
        rows = (
            query.order_by(SupportTicket.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return self.ticket_payloads(rows), total

    def get_ticket(self, ticket_id: int) -> Optional[SupportTicket]:
        return (
            self.db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        )

    def list_logs(self, ticket_id: int) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(SupportTicketLog)
            .filter(SupportTicketLog.ticket_id == ticket_id)
            .order_by(SupportTicketLog.id.asc())
            .all()
        )
        return self.ticket_log_payloads(rows)

    # ------------------------------------------------------------------
    # 创建与更新
    # ------------------------------------------------------------------

    def create_ticket(self, user_id: int, data: TicketCreate) -> SupportTicket:
        customer = self._resolve_customer(user_id, data)
        session = (
            self.db.query(SupportSession)
            .filter(SupportSession.id == data.session_id)
            .first()
            if data.session_id
            else None
        )

        row = SupportTicket(
            ticket_no=self._generate_no(),
            customer_id=customer.id if customer else None,
            session_id=session.id if session else None,
            type=data.type if data.type in TicketType.ALL else TicketType.OTHER,
            title=data.title,
            description=data.description,
            status=TicketStatus.PENDING,
            priority=data.priority or "normal",
            assignee_id=data.assignee_id,
            due_at=data.due_at,
            created_by=user_id,
        )
        self.db.add(row)
        self.db.flush()

        if customer:
            customer.ticket_count = (customer.ticket_count or 0) + 1

        self._add_log(
            row,
            action=TicketLogAction.CREATE,
            to_status=TicketStatus.PENDING,
            content="创建工单",
            operator_id=user_id,
        )
        if data.assignee_id:
            self._add_log(
                row,
                action=TicketLogAction.ASSIGN,
                content=f"指派给 {_display_name(self._user(data.assignee_id))}",
                operator_id=user_id,
            )

        # 在来源会话里留一条系统提示，坐席与后续接手的人都能看到建单动作
        if session:
            self.db.add(
                SupportMessage(
                    session_id=session.id,
                    role="system",
                    content=f"已创建工单 {row.ticket_no}：{row.title}",
                    operator_id=user_id,
                )
            )
            session.message_count = (session.message_count or 0) + 1
            session.updated_at = _utcnow()

        self.db.commit()
        self.db.refresh(row)
        return row

    def create_from_escalation(
        self, session, payload: Dict[str, Any], customer_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Escalation Agent 自动建单：把 LLM 生成的结构化工单映射到 TicketCreate 并落库

        字段映射：title←ticket_summary、type←issue_category、description←detail+建议处理、
        priority←urgency。返回工单响应字典（供 SSE ticket 事件透传前端）。
        """
        from app.schemas.support import TicketCreate

        category = payload.get("issue_category") or ""
        type_ = self._category_to_type(category)
        urgency = payload.get("urgency") or "normal"
        if urgency not in TicketPriority.ALL:
            urgency = "normal"

        description = payload.get("detail") or ""
        suggested = payload.get("suggested_action")
        if suggested:
            description = description + f"\n\n建议处理：{suggested}"

        data = TicketCreate(
            customer_id=customer_id or getattr(session, "customer_id", None),
            session_id=getattr(session, "id", None),
            type=type_,
            title=payload.get("ticket_summary") or "客户投诉升级",
            description=description,
            priority=urgency,
        )
        ticket = self.create_ticket(getattr(session, "created_by", None) or 1, data)
        return self.ticket_payload(ticket)

    @staticmethod
    def _category_to_type(category: str) -> str:
        """把 Escalation 的问题类别映射到平台工单类型"""
        c = category or ""
        if any(k in c for k in ["投诉", "态度", "服务", "欺骗", "维权"]):
            return TicketType.COMPLAINT
        if any(k in c for k in ["退", "退款", "退货"]):
            return TicketType.REFUND
        if any(k in c for k in ["调", "换", "改", "重发"]):
            return TicketType.RESCHEDULE
        if any(k in c for k in ["修", "质量", "损坏", "坏"]):
            return TicketType.REPAIR
        return TicketType.CONSULT

    def update_ticket(
        self, ticket_id: int, data: TicketUpdate
    ) -> Optional[SupportTicket]:
        row = self.get_ticket(ticket_id)
        if not row:
            return None
        payload = data.model_dump(exclude_unset=True)
        # 指派单独记一条流水，方便回溯「谁接的手」
        if "assignee_id" in payload:
            new_assignee = payload.pop("assignee_id")
            if new_assignee != row.assignee_id:
                row.assignee_id = new_assignee
                self._add_log(
                    row,
                    action=TicketLogAction.ASSIGN,
                    content=(
                        f"指派给 {_display_name(self._user(new_assignee))}"
                        if new_assignee
                        else "取消指派，退回公共池"
                    ),
                    operator_id=row.created_by,
                )
        for field, value in payload.items():
            setattr(row, field, value)
        self.db.commit()
        self.db.refresh(row)
        return row

    def transition(
        self, ticket_id: int, user_id: int, data: TicketTransitionRequest
    ) -> SupportTicket:
        """状态流转：校验合法性 → 改状态 → 落流水"""
        row = self.get_ticket(ticket_id)
        if not row:
            raise ValueError("工单不存在")

        target = data.to_status
        if target not in TicketStatus.ALL:
            raise ValueError(f"未知状态：{target}")
        if target == row.status:
            raise ValueError(f"工单已处于「{TicketStatus.LABELS.get(target)}」")

        allowed = TicketStatus.ALLOWED_TRANSITIONS.get(row.status, ())
        if target not in allowed:
            raise ValueError(
                f"不允许从「{TicketStatus.LABELS.get(row.status)}」"
                f"直接流转到「{TicketStatus.LABELS.get(target)}」"
            )

        from_status = row.status
        row.status = target
        now = _utcnow()
        if target == TicketStatus.RESOLVED and not row.resolved_at:
            row.resolved_at = now
        if target == TicketStatus.CLOSED and not row.closed_at:
            row.closed_at = now

        self._add_log(
            row,
            action=TicketLogAction.TRANSITION,
            from_status=from_status,
            to_status=target,
            content=data.content,
            operator_id=user_id,
        )
        self.db.commit()
        self.db.refresh(row)
        return row

    def add_comment(
        self, ticket_id: int, user_id: int, data: TicketCommentRequest
    ) -> SupportTicketLog:
        row = self.get_ticket(ticket_id)
        if not row:
            raise ValueError("工单不存在")
        log = self._add_log(
            row,
            action=TicketLogAction.COMMENT,
            content=data.content,
            operator_id=user_id,
        )
        self.db.commit()
        self.db.refresh(log)
        return log

    def delete_ticket(self, ticket_id: int) -> bool:
        row = self.get_ticket(ticket_id)
        if not row:
            return False
        self.db.delete(row)  # 流水靠外键 CASCADE 一并删除
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # 响应组装
    # ------------------------------------------------------------------

    def ticket_payload(self, row: SupportTicket) -> Dict[str, Any]:
        """单条工单响应（创建/流转后回调用）"""
        return self.ticket_payloads([row])[0]

    def ticket_payloads(self, rows: List[SupportTicket]) -> List[Dict[str, Any]]:
        """批量组装工单响应：客户与坐席一次查齐，避免列表 2N+1 次查询"""
        customer_ids = {row.customer_id for row in rows if row.customer_id}
        user_ids = {
            row.assignee_id for row in rows if row.assignee_id
        } | {row.created_by for row in rows if row.created_by}

        customers: Dict[int, SupportCustomer] = {}
        if customer_ids:
            customers = {
                item.id: item
                for item in self.db.query(SupportCustomer)
                .filter(SupportCustomer.id.in_(customer_ids))
                .all()
            }
        users: Dict[int, User] = {}
        if user_ids:
            users = {
                item.id: item
                for item in self.db.query(User).filter(User.id.in_(user_ids)).all()
            }

        now = _utcnow()
        return [
            self._ticket_dict(
                row,
                customers.get(row.customer_id) if row.customer_id else None,
                users.get(row.assignee_id) if row.assignee_id else None,
                now,
            )
            for row in rows
        ]

    def _ticket_dict(
        self,
        row: SupportTicket,
        customer: Optional[SupportCustomer],
        assignee: Optional[User],
        now: datetime,
    ) -> Dict[str, Any]:
        overdue = bool(row.due_at and row.due_at < now and row.status in OPEN_STATUSES)
        return {
            "id": row.id,
            "ticket_no": row.ticket_no,
            "customer_id": row.customer_id,
            "customer_name": customer.name if customer else "",
            "session_id": row.session_id,
            "type": row.type,
            "type_label": TicketType.LABELS.get(row.type, row.type),
            "title": row.title,
            "description": row.description,
            "status": row.status,
            "status_label": TicketStatus.LABELS.get(row.status, row.status),
            "priority": row.priority,
            "priority_label": TicketPriority.LABELS.get(row.priority, row.priority),
            "assignee_id": row.assignee_id,
            "assignee_name": _display_name(assignee),
            "due_at": row.due_at,
            "is_overdue": overdue,
            "resolved_at": row.resolved_at,
            "closed_at": row.closed_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def ticket_log_payloads(self, rows: List[SupportTicketLog]) -> List[Dict[str, Any]]:
        user_ids = {row.operator_id for row in rows if row.operator_id}
        users: Dict[int, User] = {}
        if user_ids:
            users = {
                item.id: item
                for item in self.db.query(User).filter(User.id.in_(user_ids)).all()
            }
        return [
            self._ticket_log_dict(row, users.get(row.operator_id) if row.operator_id else None)
            for row in rows
        ]

    def ticket_log_payload(self, row: SupportTicketLog) -> Dict[str, Any]:
        return self.ticket_log_payloads([row])[0]

    def _ticket_log_dict(
        self, row: SupportTicketLog, operator: Optional[User]
    ) -> Dict[str, Any]:
        return {
            "id": row.id,
            "ticket_id": row.ticket_id,
            "action": row.action,
            "from_status": row.from_status,
            "from_status_label": (
                TicketStatus.LABELS.get(row.from_status, "") if row.from_status else ""
            ),
            "to_status": row.to_status,
            "to_status_label": (
                TicketStatus.LABELS.get(row.to_status, "") if row.to_status else ""
            ),
            "content": row.content,
            "operator_id": row.operator_id,
            "operator_name": _display_name(operator),
            "created_at": row.created_at,
        }

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _resolve_customer(
        self, user_id: int, data: TicketCreate
    ) -> Optional[SupportCustomer]:
        """客户来源二选一：已有客户 ID，或现场录入一份客户资料"""
        if data.customer_id:
            return (
                self.db.query(SupportCustomer)
                .filter(SupportCustomer.id == data.customer_id)
                .first()
            )
        if data.customer_new:
            return self.support.create_customer(user_id, data.customer_new)
        return None

    def _user(self, user_id: Optional[int]) -> Optional[User]:
        if not user_id:
            return None
        return self.db.query(User).filter(User.id == user_id).first()

    def _add_log(
        self,
        ticket: SupportTicket,
        action: str,
        content: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        operator_id: Optional[int] = None,
    ) -> SupportTicketLog:
        log = SupportTicketLog(
            ticket_id=ticket.id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            content=content,
            operator_id=operator_id,
        )
        self.db.add(log)
        return log

    @staticmethod
    def _generate_no() -> str:
        """工单号：GD + 日期 + 4 位随机十六进制

        随机段而非自增序列：避免并发下先查后插导致的重复；
        唯一约束兜底，冲突概率极低（4 位十六进制 = 65536 种）。
        """
        return f"GD{datetime.now(UTC).strftime('%Y%m%d')}{secrets.token_hex(2).upper()}"


def get_support_ticket_service(db: Session) -> SupportTicketService:
    """工单服务工厂"""
    return SupportTicketService(db)
