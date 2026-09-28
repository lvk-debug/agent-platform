"""
智能客服问答服务

职责：知识库检索 → 意图识别 → 组装 prompt → 流式回答 → 落库与转人工判定。

设计要点：
1. **知识库检索复用平台 KnowledgeService**，不另建 FAQ 索引；
   多个知识库串行检索（Session 非并发安全，且库数量通常只有 1~3 个），
   合并后按分数取 top_k。
2. **没把握就别硬答**。绑定了知识库却检索不到或分数过低时，
   直接输出配置的兜底话术并引导转人工——客服场景里编造价格与政策的代价远高于少答一句。
   未绑定知识库时不判低置信，允许模型凭系统提示词作答（此时配置者自担口径）。
3. **意图识别失败不影响主链路**：LLM 超时/返回非法 JSON 时降级为关键词规则。
4. **转人工是配置驱动的**：敏感意图、显式关键词、连续低置信三条触发规则
   全部取自 SupportSettings，不写死在代码里。
"""

import asyncio
import json
import re
import time
from datetime import UTC, datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import httpx

from sqlalchemy.orm import Session, joinedload

from app.core.config import settings

# 兼容别名：部分遗留代码用 app_settings 访问同一配置对象，避免 NameError
app_settings = settings
from app.models.knowledge import KnowledgeBase
from app.models.model import Model, ModelProvider
from app.models.support import (
    IntentCategory,
    MessageRole,
    SessionStatus,
    SupportMessage,
    SupportSession,
    SupportSettings,
)
from app.services.knowledge import KnowledgeService
from app.services.llm import LLMService, llm_service
from app.services.support import SupportService
from app.utils.logger import logger

# 意图识别 prompt：强制纯 JSON，避免模型输出多余解释导致解析失败。
# 与 docs/智能客服.md 对齐的 4 类电商语义 + other 兜底。
INTENT_PROMPT = """你是客服意图识别助手。判断下面这条客户消息的意图。

可选意图（只能从中选一个）：
- product_inquiry 商品咨询：问商品/课程功能、价格、优惠、质保、售后维修等
- order_query 订单/物流查询：问订单状态、物流进度、发货时间、配送等
- complaint 投诉/复杂问题：表达不满、要退款退课、需要人工介入处理
- general 问候/闲聊/其他：打招呼、闲聊或无法归类的一般性问题

只输出一个 JSON 对象，不要任何解释、不要代码块：
{{"intent": "<上面某个取值>", "confidence": <0到1之间的小数>}}

客户消息：
{query}"""

# LLM 不可用时的关键词兜底规则：按优先级从上往下匹配，映射到新的 4 类意图
KEYWORD_RULES: List[Tuple[Tuple[str, ...], str]] = [
    # 投诉 / 退款退课类 → 升级（自动建工单）
    (("投诉", "举报", "太差", "态度", "差评", "退费", "退款", "退课", "不想学了", "退钱"),
     IntentCategory.COMPLAINT),
    # 订单 / 物流类 → 工具 Agent
    (("订单", "物流", "快递", "发货", "到哪", "查单", "单号", "运单", "配送", "寄"),
     IntentCategory.ORDER_QUERY),
    # 商品 / 价格 / 课程 / 售后咨询类 → 知识库 Agent
    (("多少钱", "价格", "收费", "优惠", "折扣", "学费", "课程", "学什么", "内容", "介绍",
      "选课", "推荐", "适合", "几岁", "年龄", "几点", "时间", "课表", "周末", "上课",
      "调课", "换课", "转班", "改时间", "请假", "补课", "坏了", "维修", "打不开", "故障",
      "登不上", "质保", "功能"),
     IntentCategory.PRODUCT_INQUIRY),
]

# 历史消息的角色映射：客户视作 user，AI 与坐席视作 assistant
_ROLE_MAP = {
    MessageRole.CUSTOMER: "user",
    MessageRole.AI: "assistant",
    MessageRole.AGENT: "assistant",
}


def _llm_provider_type(provider: ModelProvider) -> str:
    """平台供应商类型 → LLMService 认识的类型

    LLMService 只实现 openai / anthropic；平台还能配 local、custom，
    而这些基本都是 OpenAI 兼容端点，一律按 openai 处理。
    """
    return provider.provider_type if provider.provider_type == "anthropic" else "openai"


def _describe_exception(exc: BaseException) -> str:
    """异常整理成人话

    httpx 的超时类异常 str() 是空串，直接拼进提示只剩「模型调用失败：」，
    看不出原因；这里带上类型名，并对 HTTP 错误补上响应体。
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        # 流式响应未消费时读 .text 会抛 ResponseNotRead，
        # 那样会把「模型调用失败」包装成另一个异常，反而看不到真实原因
        try:
            body = (exc.response.text or "").strip()
        except Exception:  # noqa: BLE001
            body = ""
        if len(body) > 300:
            body = body[:300] + "…"
        return f"供应商返回 HTTP {status}：{body or exc.response.reason_phrase}"

    text = str(exc).strip()
    return f"{type(exc).__name__}：{text}" if text else type(exc).__name__


def _parse_intent_json(raw: str) -> Optional[Tuple[str, float]]:
    """从模型输出里抠出第一个 JSON 对象

    模型常在外面裹 ```json 或加前后缀，这里不要求整体合法，只取首个 {...}。
    """
    match = re.search(r"\{[^{}]*\}", raw or "", re.S)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    intent = str(data.get("intent", "")).strip()
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    if intent not in IntentCategory.ALL:
        return None
    return intent, max(0.0, min(confidence, 1.0))


def _keyword_intent(query: str) -> Tuple[str, float]:
    """关键词规则兜底：命中即返回，固定给一个中等置信度"""
    text = query or ""
    for keywords, intent in KEYWORD_RULES:
        if any(word in text for word in keywords):
            return intent, 0.6
    return IntentCategory.OTHER, 0.3


def _contains_keyword(query: str, keywords: List[str]) -> bool:
    text = query or ""
    return any(word and word in text for word in keywords)


async def _pending_interrupt(graph: Any, run_config: Dict[str, Any]) -> Any:
    """图若因 human-in-the-loop（interrupt）挂起，返回其 payload；否则返回 None。

    通过 checkpoint 的 aget_state 读取当前被挂起的节点与中断值，前端据此弹出确认。
    """
    try:
        snap = await graph.aget_state(run_config)
    except Exception:
        return None
    if not snap:
        return None
    for task in getattr(snap, "tasks", None) or ():
        interrupts = getattr(task, "interrupts", None) or ()
        if interrupts:
            return interrupts[0].value
    return None


def _is_graph_interrupt(exc: Exception) -> bool:
    """兼容不同 langgraph 版本：interrupt 可能以 GraphInterrupt 异常形式从 ainvoke 抛出"""
    return "interrupt" in exc.__class__.__name__.lower()


class SupportChatService:
    """客服问答服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 模型解析
    # ------------------------------------------------------------------

    def resolve_model(
        self, cfg: SupportSettings, model_id: Optional[int] = None
    ) -> Tuple[Optional[Model], Optional[ModelProvider]]:
        """优先用请求指定模型，其次配置模型，最后回退第一个可用模型"""
        base = (
            self.db.query(Model)
            .options(joinedload(Model.provider))
            .filter(Model.is_active.is_(True))
        )
        for candidate in (model_id, cfg.model_id, None):
            if candidate is None:
                continue
            row = base.filter(Model.id == candidate).first()
            if row and row.provider and row.provider.is_active:
                return row, row.provider

        for row in base.all():
            if row.provider and row.provider.is_active:
                return row, row.provider
        return None, None

    # ------------------------------------------------------------------
    # 知识库检索
    # ------------------------------------------------------------------

    async def build_context(
        self, query: str, cfg: SupportSettings
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """
        检索绑定的知识库

        Returns:
            (references, context_text, confident)
            confident=False 表示「没把握」，调用方应走兜底话术并引导转人工。
        """
        kb_ids = [int(item) for item in (cfg.knowledge_base_ids or []) if item]
        if not kb_ids:
            # 没绑知识库：不判低置信，交给系统提示词约束，避免配置期就完全答不了
            return [], "", True

        top_k = min(
            max(int(cfg.top_k or app_settings.SUPPORT_CHAT_TOP_K), 1),
            app_settings.SUPPORT_CHAT_MAX_TOP_K,
        )
        search_mode = cfg.search_mode or "rrf"

        knowledge = KnowledgeService(self.db)
        kb_names = self._kb_names(kb_ids)

        # 串行检索：SQLAlchemy Session 不是并发安全的，
        # 而知识库数量通常只有 1~3 个，串行的耗时远小于一次 LLM 调用。
        merged: List[Dict[str, Any]] = []
        for kb_id in kb_ids:
            try:
                hits = await knowledge.search(
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    score_threshold=cfg.score_threshold or 0.0,
                    search_mode=search_mode,
                    enable_rerank=bool(cfg.enable_rerank),
                )
            except Exception as exc:  # noqa: BLE001 - 单库检索失败不能拖垮整次问答
                logger.warning(f"客服知识库检索失败 kb={kb_id}: {exc}")
                continue

            for hit in hits or []:
                merged.append(
                    {
                        "kb_id": kb_id,
                        "kb_name": kb_names.get(kb_id, ""),
                        "document_id": hit.get("document_id"),
                        "document_name": hit.get("document_name") or "",
                        "segment_id": hit.get("segment_id"),
                        "content": hit.get("content") or "",
                        "score": float(hit.get("score") or 0.0),
                    }
                )

        merged.sort(key=lambda item: item["score"], reverse=True)
        merged = merged[:top_k]

        # 字符预算：超长片段整体截断，避免打爆 prompt
        budget = app_settings.SUPPORT_CHAT_CONTEXT_CHARS
        references: List[Dict[str, Any]] = []
        used = 0
        for item in merged:
            content = item["content"]
            limit = max(app_settings.SUPPORT_CHAT_REFERENCE_CHARS, 1)
            if used + len(content) > budget:
                remaining = budget - used
                if remaining < 80:  # 剩下的塞不下有效内容，直接停
                    break
                content = content[:remaining]
            clipped = {**item, "content": content}
            references.append(clipped)
            used += len(content)

        confident = bool(references) and (
            references[0]["score"] >= (cfg.low_confidence_threshold or 0.0)
        )
        return references, self._compose_context(references), confident

    def _kb_names(self, kb_ids: List[int]) -> Dict[int, str]:
        rows = (
            self.db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
        )
        return {row.id: row.name for row in rows}

    @staticmethod
    def _compose_context(references: List[Dict[str, Any]]) -> str:
        if not references:
            return ""
        lines = ["【知识库资料】以下是机构资料中与本问题相关的片段，请优先依据它们作答。"]
        for index, item in enumerate(references, 1):
            source = item.get("document_name") or item.get("kb_name") or "资料"
            lines.append(f"[{index}] 来源：{source}\n{item.get('content') or ''}")
        return "\n\n".join(lines)

    # ------------------------------------------------------------------
    # 意图识别
    # ------------------------------------------------------------------

    async def detect_intent(
        self, query: str, cfg: SupportSettings, model_id: Optional[int] = None
    ) -> Tuple[str, float]:
        """识别意图；LLM 不可用或超时时降级为关键词规则"""
        model_row, provider = self.resolve_model(cfg, model_id)
        if not model_row or not provider:
            return _keyword_intent(query)

        prompt = INTENT_PROMPT.format(query=query[:500])
        try:
            llm = llm_service
            await llm.register_provider(
                provider_type=_llm_provider_type(provider),
                api_key=provider.api_key,
                api_endpoint=provider.api_endpoint,
            )
            result = await asyncio.wait_for(
                llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_row.model_id,
                    provider=_llm_provider_type(provider),
                    temperature=0.0,
                    max_tokens=120,
                ),
                timeout=settings.SUPPORT_INTENT_TIMEOUT,
            )
            parsed = _parse_intent_json(result.get("content", ""))
            if parsed:
                return parsed
            logger.warning("客服意图识别返回非法 JSON，降级关键词规则")
        except asyncio.TimeoutError:
            logger.warning("客服意图识别超时，降级关键词规则")
        except Exception as exc:  # noqa: BLE001 - 意图识别是旁路，失败不该影响回答
            logger.warning(f"客服意图识别失败，降级关键词规则: {exc}")

        return _keyword_intent(query)

    def should_handoff(
        self, query: str, intent: str, cfg: SupportSettings, streak: int
    ) -> Tuple[bool, str]:
        """是否建议转人工

        Returns:
            (是否转人工, 原因)
        """
        human_intents = list(cfg.human_intents or [])
        if intent in human_intents:
            return True, f"命中需人工处理的意图（{IntentCategory.LABELS.get(intent, intent)}）"

        keywords = list(cfg.human_keywords or [])
        if _contains_keyword(query, keywords):
            return True, "客户明确要求人工处理"

        threshold = max(int(cfg.low_confidence_streak or 1), 1)
        if streak >= threshold:
            return True, f"连续 {streak} 次未能给出有把握的回答"

        return False, ""

    # ------------------------------------------------------------------
    # 历史与落库
    # ------------------------------------------------------------------

    def _build_messages(
        self, session: SupportSession, cfg: SupportSettings, context_text: str, query: str
    ) -> List[Dict[str, str]]:
        system_prompt = (cfg.system_prompt or "").replace(
            "{bot_name}", cfg.bot_name or "智能客服助手"
        )
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt or "你是智能客服助手。"}
        ]

        turns = max(int(cfg.history_turns or 0), 0)
        if turns:
            history = (
                self.db.query(SupportMessage)
                .filter(
                    SupportMessage.session_id == session.id,
                    SupportMessage.error.is_(None),
                )
                .order_by(SupportMessage.id.desc())
                .limit(turns * 2)
                .all()
            )
            history.reverse()
            for row in history:
                role = _ROLE_MAP.get(row.role)
                if role and row.content:
                    messages.append({"role": role, "content": row.content})

        if context_text:
            messages.append(
                {"role": "user", "content": f"{context_text}\n\n【客户问题】{query}"}
            )
        else:
            messages.append({"role": "user", "content": f"【客户问题】{query}"})
        return messages

    def _load_history(
        self, session: SupportSession, before_id: Optional[int] = None, turns: int = 0
    ) -> List[Dict[str, str]]:
        """加载会话历史轮次，注入多 Agent 图的状态 history 字段以记住上下文。

        仅取 error 为空的消息，默认排除当前这条客户提问（before_id），
        按 history_turns 控制保留的最近轮数（1 轮 = 1 问 1 答）。
        """
        turns = max(int(turns or 0), 0)
        if not turns:
            return []
        q = self.db.query(SupportMessage).filter(
            SupportMessage.session_id == session.id,
            SupportMessage.error.is_(None),
        )
        if before_id is not None:
            q = q.filter(SupportMessage.id < before_id)
        rows = q.order_by(SupportMessage.id.desc()).limit(turns * 2).all()
        rows.reverse()
        history: List[Dict[str, str]] = []
        for row in rows:
            role = _ROLE_MAP.get(row.role)
            if role and row.content:
                history.append({"role": role, "content": row.content})
        return history

    def _save_message(
        self,
        session: SupportSession,
        role: str,
        content: str,
        references: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        confidence: Optional[float] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
        operator_id: Optional[int] = None,
        trace: Optional[Dict[str, Any]] = None,
    ) -> SupportMessage:
        row = SupportMessage(
            session_id=session.id,
            role=role,
            content=content or "",
            references=references,
            intent=intent,
            confidence=confidence,
            model=model,
            latency_ms=latency_ms,
            error=error,
            operator_id=operator_id,
            trace=trace,
        )
        self.db.add(row)
        session.message_count = (session.message_count or 0) + 1
        session.last_message_preview = " ".join((content or "").split())[:100]
        session.last_message_at = datetime.now(UTC)
        session.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(row)
        return row

    @staticmethod
    def _emit_trace(trace: Dict[str, Any], item: Dict[str, Any]) -> None:
        """把 SSE 事件累积进 trace 字典，供历史消息回看 Agent 处理过程"""
        event = item["event"]
        if event == "thought":
            trace["steps"].append(item["data"])
        elif event == "references":
            trace["references"] = item["data"]
        elif event == "tool_call":
            trace["tool_calls"].append(item["data"])
        elif event == "ticket":
            trace["ticket"] = item["data"]

    def _apply_intent(self, session: SupportSession, intent: str, confidence: float) -> None:
        session.intent = intent
        session.intent_confidence = confidence

    def _mark_pending_human(self, session: SupportSession, reason: str) -> None:
        """置为待人工并写一条系统提示消息（坐席在列表页与会话里都能看到原因）"""
        if session.status == SessionStatus.CLOSED:
            return
        session.status = SessionStatus.PENDING_HUMAN
        self._save_message(
            session,
            MessageRole.SYSTEM,
            f"已标记为待人工：{reason}",
        )

    # ------------------------------------------------------------------
    # 流式问答
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        session: SupportSession,
        query: str,
        user_id: int,
        model_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """AI 模式流式回答（驱动 LangGraph 多 Agent 自主客服）

        事件顺序：thought… → references（意图）→ tool_call… → ticket（可选）
                 → delta…（Summary 流式）→ done | error
        """
        started = time.perf_counter()
        cfg = self._settings()
        model_row, provider = self.resolve_model(cfg, model_id)
        if model_row is None or provider is None:
            yield self.sse_event(
                "error", {"message": "未配置可用的客服模型，请在机器人设置中选择模型"}
            )
            return
        # 图节点按 cfg.chat_model / chat_temperature / chat_max_tokens 取参，
        # SupportSettings 未单独存这些字段，这里由已解析的模型/配置注入为临时属性（不落库）
        cfg.chat_model = model_row.model_id
        cfg.chat_temperature = cfg.temperature
        cfg.chat_max_tokens = cfg.max_tokens
        provider_type = _llm_provider_type(provider)

        # 在单例 llm_service 上注册供应商：图节点（router/tool/summary）通过
        # 单例调用 LLM，若不注册则 providers 为空，会抛「未找到供应商配置」。
        await llm_service.register_provider(
            provider_type=provider_type,
            api_key=provider.api_key,
            api_endpoint=provider.api_endpoint,
        )

        # 先把客户消息落库，再跑图：保证「提问」不会因编排异常而丢失
        current_message = self._save_message(session, MessageRole.CUSTOMER, query)
        # 加载历史轮次（排除当前提问），注入图状态，让多 Agent 记住会话上下文
        history = self._load_history(
            session, before_id=current_message.id, turns=cfg.history_turns or 0
        )

        try:
            from app.services.support_agents import build_graph, _get_support_checkpointer

            # 参考 agent.py：checkpointer 用 AsyncSqliteSaver 持久化到数据库文件，
            # 以 async with 管理连接生命周期；thread_id=session.id 保存会话窗口 + 支持 interrupt 恢复
            async with _get_support_checkpointer() as checkpointer:
                graph = build_graph(checkpointer)
                queue: "asyncio.Queue" = asyncio.Queue()

                async def sink(event: str, data: Any) -> None:
                    await queue.put({"event": event, "data": data})

                # 可序列化的图状态（按 thread_id 维度持久化在 checkpoint 中，保存会话窗口）
                init_state = {
                    "provider_type": provider_type,
                    "customer_id": session.customer_id,
                    "query": query,
                    "history": history,
                    "retrieved_docs": [],
                    "intent": None,
                    "intent_label": "",
                    "confidence": 0.0,
                    "context_text": "",
                    "references": [],
                    "tool_results": [],
                    "escalation_ticket": None,
                    "final_response": "",
                    "return_confirmed": False,
                    "return_decision": None,
                }
                # 不可序列化运行时对象（db/cfg/session/sink）走 config；thread_id 用于 checkpoint
                run_config = {
                    "configurable": {
                        "thread_id": str(session.id),
                        "db": self.db,
                        "cfg": cfg,
                        "session": session,
                        "sink": sink,
                    }
                }

                run_task = asyncio.ensure_future(
                    graph.ainvoke(init_state, config=run_config)
                )

                trace: Dict[str, Any] = {
                    "steps": [],
                    "tool_calls": [],
                    "ticket": None,
                    "references": None,
                }
                final_state: Dict[str, Any] = {}

                while True:
                    get_task = asyncio.ensure_future(queue.get())
                    wait_set = {get_task}
                    if not run_task.done():
                        wait_set.add(run_task)
                    done, _ = await asyncio.wait(
                        wait_set, return_when=asyncio.FIRST_COMPLETED
                    )
                    if get_task in done:
                        item = get_task.result()
                        if item["event"] == "done":
                            break
                        self._emit_trace(trace, item)
                        yield self.sse_event(item["event"], item["data"])
                    if run_task in done:
                        # 图编排结束，排空队列中剩余事件（保证顺序）
                        while not queue.empty():
                            item = queue.get_nowait()
                            if item["event"] == "done":
                                continue
                            self._emit_trace(trace, item)
                            yield self.sse_event(item["event"], item["data"])
                        # 图结束：正常完成，或因 human-in-the-loop 被 interrupt 挂起
                        # （不同 langgraph 版本下 interrupt 可能以 GraphInterrupt 形式抛出，也可能直接返回）
                        try:
                            final_state = run_task.result()
                            pending = await _pending_interrupt(graph, run_config)
                        except Exception as exc:
                            if _is_graph_interrupt(exc):
                                pending = await _pending_interrupt(graph, run_config) or {
                                    "type": "return_confirm",
                                    "query": query,
                                    "message": "用户诉求涉及退货或退款，请在继续前确认是否由 AI 直接处理。",
                                    "options": ["approved", "rejected"],
                                }
                            else:
                                raise
                        if pending is not None:
                            yield self.sse_event("human_confirm", pending)
                            yield self.sse_event(
                                "done",
                                {
                                    "pending_confirm": True,
                                    "session_id": session.id,
                                    "latency_ms": int(
                                        (time.perf_counter() - started) * 1000
                                    ),
                                },
                            )
                            return
                        break

            answer = (final_state or {}).get("final_response", "")
            intent = (final_state or {}).get("intent")
            references = (final_state or {}).get("references") or []
            latency_ms = int((time.perf_counter() - started) * 1000)
            message = self._save_message(
                session,
                MessageRole.AI,
                answer,
                references=references,
                intent=intent,
                trace=trace,
                latency_ms=latency_ms,
            )
            self.db.commit()
            yield self.sse_event(
                "done",
                {
                    "message_id": message.id,
                    "suggest_human": intent in IntentCategory.SENSITIVE,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"客服多 Agent 编排失败 session={session.id}: {exc}", exc_info=True)
            detail = f"客服处理失败：{_describe_exception(exc)}"
            self._save_message(session, MessageRole.AI, "", error=detail[:500], intent=None)
            self.db.commit()
            yield self.sse_event("error", {"detail": detail})

    async def confirm_stream(
        self,
        session: SupportSession,
        decision: Dict[str, Any],
        user_id: int,
    ) -> AsyncGenerator[str, None]:
        """human-in-the-loop 续跑：坐席确认退货/退款后，用 Command(resume=...) 唤醒被挂起的图。

        前端收到 human_confirm 事件后弹出确认，坐席回传 decision（approved/rejected）与可选
        comment；本方法用同一 thread_id 恢复图，继续跑 agent → summary 并流式输出最终回复。
        """
        started = time.perf_counter()
        cfg = self._settings()
        model_row, provider = self.resolve_model(cfg, None)
        if model_row is None or provider is None:
            yield self.sse_event("error", {"message": "未配置可用的客服模型，请在机器人设置中选择模型"})
            return
        cfg.chat_model = model_row.model_id
        cfg.chat_temperature = cfg.temperature
        cfg.chat_max_tokens = cfg.max_tokens
        provider_type = _llm_provider_type(provider)
        await llm_service.register_provider(
            provider_type=provider_type,
            api_key=provider.api_key,
            api_endpoint=provider.api_endpoint,
        )

        from app.services.support_agents import build_graph, _get_support_checkpointer
        from langgraph.types import Command

        try:
            async with _get_support_checkpointer() as checkpointer:
                graph = build_graph(checkpointer)
                queue: "asyncio.Queue" = asyncio.Queue()

                async def sink(event: str, data: Any) -> None:
                    await queue.put({"event": event, "data": data})

                run_config = {
                    "configurable": {
                        "thread_id": str(session.id),
                        "db": self.db,
                        "cfg": cfg,
                        "session": session,
                        "sink": sink,
                    }
                }
                # 把人工决策回灌给被 interrupt 挂起的节点（复用同一 thread_id 的 checkpoint）
                command = Command(
                    resume={
                        "decision": decision.get("decision"),
                        "comment": decision.get("comment", ""),
                    }
                )

                trace: Dict[str, Any] = {
                    "steps": [],
                    "tool_calls": [],
                    "ticket": None,
                    "references": None,
                }
                run_task = asyncio.ensure_future(
                    graph.ainvoke(command, config=run_config)
                )

                while True:
                    get_task = asyncio.ensure_future(queue.get())
                    wait_set = {get_task}
                    if not run_task.done():
                        wait_set.add(run_task)
                    done, _ = await asyncio.wait(
                        wait_set, return_when=asyncio.FIRST_COMPLETED
                    )
                    if get_task in done:
                        item = get_task.result()
                        if item["event"] == "done":
                            break
                        self._emit_trace(trace, item)
                        yield self.sse_event(item["event"], item["data"])
                    if run_task in done:
                        while not queue.empty():
                            item = queue.get_nowait()
                            if item["event"] == "done":
                                continue
                            self._emit_trace(trace, item)
                            yield self.sse_event(item["event"], item["data"])
                        final_state = run_task.result()
                        break

            answer = (final_state or {}).get("final_response", "")
            intent = (final_state or {}).get("intent")
            references = (final_state or {}).get("references") or []
            latency_ms = int((time.perf_counter() - started) * 1000)
            message = self._save_message(
                session,
                MessageRole.AI,
                answer,
                references=references,
                intent=intent,
                trace=trace,
                latency_ms=latency_ms,
            )
            self.db.commit()
            yield self.sse_event(
                "done",
                {
                    "message_id": message.id,
                    "suggest_human": intent in IntentCategory.SENSITIVE,
                    "latency_ms": latency_ms,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"客服退货确认续跑失败 session={session.id}: {exc}", exc_info=True)
            detail = f"客服处理失败：{_describe_exception(exc)}"
            self._save_message(session, MessageRole.AI, "", error=detail[:500], intent=None)
            self.db.commit()
            yield self.sse_event("error", {"detail": detail})

    # ------------------------------------------------------------------
    # 建议回复（人工模式辅助）
    # ------------------------------------------------------------------

    async def suggest_reply(
        self, session: SupportSession, model_id: Optional[int] = None
    ) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
        """给坐席生成一版 AI 建议回复

        取会话最后一条客户消息作为问题；非流式，整体限时，超时返回空内容，
        坐席手动回复的节奏不能被 AI 拖住。
        """
        cfg = self._settings()
        last_customer = (
            self.db.query(SupportMessage)
            .filter(
                SupportMessage.session_id == session.id,
                SupportMessage.role == MessageRole.CUSTOMER,
            )
            .order_by(SupportMessage.id.desc())
            .first()
        )
        if not last_customer:
            return "", [], "会话中还没有客户消息"

        query = last_customer.content or ""
        references, context_text, _ = await self.build_context(query, cfg)

        model_row, provider = self.resolve_model(cfg, model_id)
        if not model_row or not provider:
            return "", references, "未找到可用模型，请先在「模型管理」中配置"

        messages = self._build_messages(session, cfg, context_text, query)
        messages.append(
            {
                "role": "system",
                "content": "你现在是为人工坐席起草回复。只输出可直接发送给客户的正文，不要加解释与前缀。",
            }
        )

        try:
            llm = llm_service
            await llm.register_provider(
                provider_type=_llm_provider_type(provider),
                api_key=provider.api_key,
                api_endpoint=provider.api_endpoint,
            )
            result = await asyncio.wait_for(
                llm.chat(
                    messages=messages,
                    model=model_row.model_id,
                    provider=_llm_provider_type(provider),
                    temperature=cfg.temperature or app_settings.SUPPORT_CHAT_TEMPERATURE,
                    max_tokens=cfg.max_tokens or app_settings.SUPPORT_CHAT_MAX_TOKENS,
                ),
                timeout=settings.SUPPORT_SUGGEST_TIMEOUT,
            )
            return (result.get("content") or "").strip(), references, None
        except asyncio.TimeoutError:
            return "", references, "生成建议超时，请重试或手动回复"
        except Exception as exc:  # noqa: BLE001
            logger.error(f"客服建议回复失败 session={session.id}: {exc}", exc_info=True)
            return "", references, f"生成建议失败：{_describe_exception(exc)}"

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _settings(self) -> SupportSettings:
        return SupportService(self.db).get_settings()

    @staticmethod
    def sse_event(event: str, data: Any) -> str:
        """格式化 SSE 事件（与学习助手、chatbot 模块保持一致）"""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def get_support_chat_service(db: Session) -> SupportChatService:
    """客服问答服务工厂"""
    return SupportChatService(db)
