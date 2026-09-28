"""
智能客服多 Agent 编排（LangGraph）

严格遵循 `docs/智能客服.md` 描述的自主客服工作流：

    START → Router(意图识别) → 按意图路由
                              ├─ order_query   → Tool Agent(Function Calling 查业务数据)
                              ├─ product_inquiry / general → Knowledge Agent(RAG 起草)
                              └─ complaint      → Escalation Agent(生成工单)
                            ↓（三类汇合）
                         Summary Agent(汇总最终回复，流式输出)
                            → END

设计要点：
1. **图编排**：用 LangGraph 的 `StateGraph` 把 5 个 Agent 建模成节点，Router 通过条件边路由，
   语义清晰、易扩展（新增 Agent 只需加节点 + 路由分支）。
2. **真流式**：每个节点完成任务时通过 `state["sink"]` 回调实时发射
   `thought` / `tool_call` / `references` / `ticket` 事件；Summary 节点用 `stream_chat`
   逐 token 发射 `delta`。`support_chat.chat_stream` 并发消费队列转发 SSE，解决文档 8.7 的模拟流式问题。
3. **工具即查表**：4 个工具（query_order / track_shipment / check_return_policy / get_product_info）
   直接查新增的 Demo 业务表，结果回传 Summary 汇总，不耦合平台 `tools` 表。
4. **Escalation 复用既有工单体系**：投诉/复杂问题由 LLM 生成结构化工单，调
   `SupportTicketService.create_from_escalation` 落库并将会话置「待人工」，坐席在工单中心/工作台接管。
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
try:
    # langgraph >= 1.0：节点内获取运行配置的函数改名为 get_config
    from langgraph.config import get_config as get_running_config
except ImportError:
    try:
        # langgraph 0.2.x
        from langgraph.config import get_running_config  # type: ignore
    except ImportError:  # pragma: no cover - 极旧版本回退到 langchain_core
        from langchain_core.runnables import get_running_config  # type: ignore

# --- LangChain 结构化输出：客服助手的格式化输出统一收敛到 with_structured_output ---
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings as app_settings
from app.models.support import (
    IntentCategory,
    SessionStatus,
    SupportSession,
)
from app.models.support_business import (
    SupportOrder,
    SupportProduct,
    SupportReturnPolicy,
    SupportShipment,
)
from app.models.knowledge import KnowledgeBase
from app.services.knowledge import KnowledgeService
from app.services.llm import llm_service
from app.services.support_ticket import SupportTicketService

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# 工具定义（OpenAI Function Calling 格式）
# ------------------------------------------------------------------

SUPPORT_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "query_order",
            "description": "查询订单详情，包括订单状态、商品名称、金额。当用户问订单、下单情况时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 ORD-001",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "track_shipment",
            "description": "查询订单的物流轨迹、承运商与预计送达时间。当用户问物流、快递、到哪了、什么时候到时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "订单号，例如 ORD-001",
                    }
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_return_policy",
            "description": "查询某类商品的退换货政策。当用户问能不能退、怎么退、质保多久时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["electronics", "clothing", "books"],
                        "description": "商品分类：electronics=电子产品, clothing=服装, books=图书",
                    }
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": "查询商品信息，包括价格、功能卖点、质保时长。当用户问某商品怎么样、多少钱、有什么功能时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "商品号，例如 P001",
                    }
                },
                "required": ["product_id"],
            },
        },
    },
]


# ------------------------------------------------------------------
# 提示词
# ------------------------------------------------------------------

ROUTER_PROMPT = """你是一个电商智能客服的「意图路由器」。
根据用户问题判断意图类别，只能从以下 4 类中选择其一：
- order_query：查询订单状态、物流轨迹、配送进度、签收情况
- product_inquiry：咨询商品功能、参数、价格、质保、怎么用、对比
- complaint：投诉、差评、质量问题、要求退款/赔偿、情绪激动或复杂的售后问题
- general：问候、闲聊、或找不到明确意图的通用问题

只输出一个 JSON，格式：{"intent":"类别","confidence":0到1之间的把握度}。不要输出其他内容。"""

ESCALATION_PROMPT = """你是一个客服投诉升级助手。
根据用户诉求，生成一张结构化工单 JSON，字段如下：
- ticket_summary：一句话工单标题（20 字内）
- issue_category：问题类别（如「物流延迟」「商品质量问题」「退款纠纷」「服务态度」）
- detail：问题详情描述（客观、包含关键信息，100 字内）
- urgency：紧急程度，只能是 high / normal / low 之一
- suggested_action：建议坐席的处理动作（50 字内）

只输出一个 JSON，不要输出其他内容。
用户诉求："""

SUMMARY_PROMPT = """你是电商智能客服的「最终回复生成器」。
请综合下方信息，用友好的中文口语化回复用户（面向终端消费者）。
要求：
1. 回复不超过 200 字，自然亲切，不要列编号式机器人腔；
2. 若已查到订单/物流/商品信息，直接给出关键结果（状态、物流位置、价格、功能亮点）；
3. 若有参考资料，取其要点作答，不要整段照抄；
4. 若已生成工单，告知用户工单号并说明已升级人工处理，安抚情绪；
5. 结尾加一句友好的反问或引导（如「还需要我帮您做点别的吗？」）。
只输出最终回复正文，不要解释你的思考过程。"""


# ------------------------------------------------------------------
# 工具：意图识别与供应商解析
# ------------------------------------------------------------------

def _llm_provider_type(provider: Optional[str], model: Optional[str]) -> str:
    """把 CRM 知识库供应商映射到 LLM 服务支持的 openai / anthropic 两类。"""
    p = (provider or "").lower()
    if p == "anthropic":
        return "anthropic"
    return "openai"


def _extract_json(text: str) -> Dict[str, Any]:
    """从模型输出里抠出第一个 JSON 对象"""
    if not text:
        return {}
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _keyword_fallback(query: str) -> str:
    """LLM 意图识别失败时的关键词兜底"""
    q = query
    if any(k in q for k in ["投诉", "差评", "退款", "赔偿", "太差", "生气", "维权", "欺骗", "质量差"]):
        return IntentCategory.COMPLAINT
    if any(k in q for k in ["订单", "物流", "快递", "发货", "配送", "到哪", "签收", "运单", "什么时候到"]):
        return IntentCategory.ORDER_QUERY
    if any(k in q for k in ["商品", "产品", "怎么用", "功能", "参数", "价格", "多少钱", "质保", "保修", "说明书"]):
        return IntentCategory.PRODUCT_INQUIRY
    return IntentCategory.GENERAL


# 退货 / 退款高风险操作关键词：命中后需 human-in-the-loop 人工确认
_RETURN_KEYWORDS = ("退货", "退款", "退换", "换货", "退订", "取消订单并退款", "七天无理由")


def is_return_request(query: str) -> bool:
    """判断用户诉求是否涉及退货 / 退款（需要人工确认的高风险操作）"""
    q = (query or "").lower()
    return any(k in q for k in _RETURN_KEYWORDS)


def _format_history(history: List[Any]) -> str:
    """把历史轮次格式化为可读文本，供各节点注入提示词（多轮上下文记忆）。

    history 元素为 {"role": "user" | "assistant", "content": str}。
    不含标题行，由调用方按需添加「【历史对话】」等标签。
    """
    if not history:
        return ""
    lines = []
    for turn in history:
        if not isinstance(turn, dict):
            continue
        role = "客户" if turn.get("role") == "user" else "助手"
        content = (turn.get("content") or "").strip()
        if content:
            lines.append(f"{role}：{content}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# LangChain 结构化输出：客服助手的格式化输出（意图识别 / 工单）统一走 with_structured_output
# ------------------------------------------------------------------

class IntentResult(BaseModel):
    """Router 意图识别的结构化输出（with_structured_output 的目标 schema）"""
    intent: Literal["order_query", "product_inquiry", "complaint", "general", "other"]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class EscalationTicket(BaseModel):
    """Escalation 投诉升级工单的结构化输出（字段名需对齐 create_from_escalation）"""
    ticket_summary: str = Field(description="一句话工单标题（20 字内）")
    issue_category: str = Field(description="问题类别，如物流延迟/商品质量问题/退款纠纷/服务态度")
    detail: str = Field(description="问题详情描述（客观、含关键信息，100 字内）")
    urgency: Literal["high", "normal", "low"]
    suggested_action: str = Field(description="建议坐席的处理动作（50 字内）")


class _StructuredOutputRunnable(Runnable):
    """SupportChatModel.with_structured_output 的落地实现。

    采用「JSON Schema 注入 system 提示 + 普通 chat 输出 JSON + 稳健解析」策略：
    - 只依赖已验证可用的普通 chat 接口，不强依赖 endpoint 支持 function calling / response_format，
      对自托管或兼容 endpoint 更稳健；
    - Pydantic 校验失败返回 None，供上层走关键词 / 兜底降级。
    """

    def __init__(self, model: "SupportChatModel", schema: Any, include_raw: bool = False):
        super().__init__()
        self._model = model
        self._schema = schema
        self._include_raw = include_raw
        # 最近一次 ainvoke 的 token 用量，供节点级日志采集
        self.last_tokens: Any = None

    @staticmethod
    def _as_records(messages) -> List[Dict[str, str]]:
        """LangChain 消息 / dict 统一转成 OpenAI 格式 records"""
        records: List[Dict[str, str]] = []
        for m in messages:
            if isinstance(m, BaseMessage):
                role = "assistant" if m.type == "ai" else m.type
                content = m.content
            elif isinstance(m, dict):
                role = "assistant" if m.get("role") == "ai" else m.get("role")
                content = m.get("content")
            else:
                continue
            role = "user" if role == "human" else role
            if role in ("system", "user", "assistant"):
                records.append({"role": role, "content": content})
        return records

    def _with_schema(self, messages):
        schema_obj = self._schema
        if isinstance(schema_obj, type) and issubclass(schema_obj, BaseModel):
            schema_text = schema_obj.model_json_schema()
        else:
            schema_text = schema_obj
        instr = (
            "你必须只输出一个 JSON 对象，禁止输出任何解释、Markdown 代码块或前后缀文字。"
            "JSON 的字段与类型必须严格符合以下 JSON Schema：\n"
            + json.dumps(schema_text, ensure_ascii=False)
        )
        out = []
        injected = False
        for m in messages:
            if isinstance(m, BaseMessage) and m.type == "system":
                out.append(SystemMessage(content=f"{m.content}\n\n{instr}"))
                injected = True
            else:
                out.append(m)
        if not injected:
            out.insert(0, SystemMessage(content=instr))
        return out

    def _parse(self, content: str):
        parsed = _extract_json(content)
        if isinstance(self._schema, type) and issubclass(self._schema, BaseModel):
            try:
                return self._schema.model_validate(parsed)
            except ValidationError:
                return None
        return parsed

    def invoke(self, input, config=None, **kwargs):
        return asyncio.run(self.ainvoke(input, config, **kwargs))

    async def ainvoke(self, input, config=None, **kwargs):
        msgs = self._with_schema(input if isinstance(input, list) else [input])
        records = self._as_records(msgs)
        resp = await llm_service.chat(
            records,
            model=self._model.model,
            provider=self._model.provider_type,
            temperature=self._model.temperature,
            max_tokens=self._model.max_tokens,
            timeout=self._model.timeout,
        )
        self.last_tokens = (resp or {}).get("tokens_used")
        content = resp.get("content", "")
        obj = self._parse(content)
        if self._include_raw:
            return {"raw": AIMessage(content=content), "parsed": obj}
        return obj


class SupportChatModel(BaseModel):
    """客服助手结构化输出的 ChatModel 配置持有者（包裹现有 llm_service）。

    不继承 langchain 的 BaseChatModel：本项目 with_structured_output 完全由
    _StructuredOutputRunnable 落地（普通 chat + JSON 解析），无需 BaseChatModel 的抽象
    方法契约，从而规避不同 langchain 版本下的抽象类 / 字段差异问题。
    """

    provider_type: str
    model: str
    temperature: float = 0.0
    max_tokens: int = 1024
    timeout: int = 30

    def with_structured_output(self, schema, *, method="function_calling", include_raw=False, **kwargs):
        return _StructuredOutputRunnable(self, schema, include_raw)


async def detect_intent(
    query: str, chat_model: str, provider_type: str, intent_timeout: int, history_text: str = ""
) -> tuple:
    """识别意图（4 类），返回 (intent, confidence, tokens)，格式化输出走 with_structured_output"""
    prompt = ROUTER_PROMPT
    if history_text:
        prompt += (
            f"\n以下是之前的对话历史，用于辅助理解当前问题"
            f"（尤其是省略了指代的追问，如「那什么时候到」「可以退款吗」）：\n"
            f"{history_text}\n"
        )
    prompt += f"\n用户问题：{query}\n只输出 JSON："
    tokens = None
    try:
        model = SupportChatModel(
            provider_type=provider_type,
            model=chat_model,
            temperature=0,
            max_tokens=256,
            timeout=intent_timeout,
        )
        runnable = model.with_structured_output(IntentResult)
        result = await runnable.ainvoke([{"role": "user", "content": prompt}])
        tokens = runnable.last_tokens
        if result is None:
            intent = _keyword_fallback(query)
            return intent, 0.3, tokens
        intent = result.intent
        if intent not in IntentCategory.ALL:
            intent = _keyword_fallback(query)
        return intent, result.confidence, tokens
    except Exception as e:  # 识别失败降级关键词，不让整次问答挂掉
        logger.warning(f"意图识别失败，降级关键词：{e}")
        return _keyword_fallback(query), 0.3, tokens


async def build_context(
    query: str, crm_settings: Any, db
) -> tuple:
    """检索知识库，返回 (context_text, references, retrieved_docs)

    `KnowledgeService.search` 仅接受单个 kb_id，而 `knowledge_base_ids` 是列表，
    因此需逐库检索后合并（与 `SupportChatService._retrieve_knowledge` 保持一致）。
    若直接把列表当 kb_id 传入，向量库会用列表作缓存 dict 的 key，报
    `unhashable type: 'list'`。
    """
    kb_ids = [int(x) for x in getattr(crm_settings, "knowledge_base_ids", None) or [] if x]
    if not kb_ids:
        return "", [], []

    top_k = getattr(crm_settings, "top_k", 5) or 5
    score_threshold = getattr(crm_settings, "score_threshold", 0.0) or 0.0
    search_mode = getattr(crm_settings, "search_mode", "rrf") or "rrf"
    enable_rerank = getattr(crm_settings, "enable_rerank", False) or False
    kb_names = {
        row.id: row.name
        for row in db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(kb_ids)).all()
    }

    try:
        service = KnowledgeService(db)
        hits: List[Dict[str, Any]] = []
        seen: set = set()  # (kb_id, segment_id) 去重
        for kb_id in kb_ids:
            try:
                kb_hits = await service.search(
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    search_mode=search_mode,
                    enable_rerank=enable_rerank,
                )
            except Exception as e:
                logger.warning(f"知识库检索失败 kb={kb_id}: {e}")
                continue
            for h in kb_hits or []:
                key = (kb_id, h.get("segment_id"))
                if key in seen:
                    continue
                seen.add(key)
                h = dict(h)
                h["kb_id"] = kb_id
                h["kb_name"] = kb_names.get(kb_id, "")
                hits.append(h)
        # 跨库统一按分数排序并截断
        hits.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        hits = hits[:top_k]
    except Exception as e:
        logger.warning(f"知识库检索失败：{e}")
        return "", [], []

    references: List[Dict[str, Any]] = []
    parts: List[str] = []
    for h in hits:
        references.append(
            {
                "kb_id": h.get("kb_id"),
                "kb_name": h.get("kb_name"),
                "document_id": h.get("document_id"),
                "document_name": h.get("document_name"),
                "segment_id": h.get("segment_id"),
                "content": h.get("content"),
                "score": h.get("score"),
            }
        )
        parts.append(h.get("content", ""))
    context_text = "\n\n".join(parts)[: getattr(crm_settings, "context_chars", 4000) or 4000]
    return context_text, references, hits


# ------------------------------------------------------------------
# 工具执行器（查 Demo 业务表）
# ------------------------------------------------------------------

async def run_support_tool(db, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """执行单个客服工具，返回 {success, name, result}"""
    try:
        if name == "query_order":
            order = (
                db.query(SupportOrder)
                .filter(SupportOrder.order_no == arguments.get("order_id"))
                .first()
            )
            if not order:
                return {"success": True, "name": name, "result": f"未找到订单 {arguments.get('order_id')}"}
            return {
                "success": True,
                "name": name,
                "result": (
                    f"订单 {order.order_no}：商品「{order.product}」，金额 ¥{order.amount}，"
                    f"状态「{order.status}」，下单时间 {order.ordered_at.date() if order.ordered_at else '未知'}"
                ),
            }
        if name == "track_shipment":
            ship = (
                db.query(SupportShipment)
                .filter(SupportShipment.order_no == arguments.get("order_id"))
                .first()
            )
            if not ship:
                return {"success": True, "name": name, "result": f"未找到订单 {arguments.get('order_id')} 的物流信息"}
            return {
                "success": True,
                "name": name,
                "result": (
                    f"订单 {ship.order_no} 物流：承运商 {ship.carrier or '未知'}，"
                    f"运单号 {ship.tracking_no or '未知'}，当前位置「{ship.current_location or '未知'}」，"
                    f"状态「{ship.status or '未知'}」，预计 {ship.estimated_text or '另行通知'}"
                ),
            }
        if name == "check_return_policy":
            policy = (
                db.query(SupportReturnPolicy)
                .filter(SupportReturnPolicy.category == arguments.get("category"))
                .first()
            )
            if not policy:
                return {"success": True, "name": name, "result": f"未找到分类 {arguments.get('category')} 的退换货政策"}
            return {
                "success": True,
                "name": name,
                "result": f"{policy.category_label or policy.category}退换货政策：{policy.policy_content}",
            }
        if name == "get_product_info":
            product = (
                db.query(SupportProduct)
                .filter(SupportProduct.product_no == arguments.get("product_id"))
                .first()
            )
            if not product:
                return {"success": True, "name": name, "result": f"未找到商品 {arguments.get('product_id')}"}
            features = "、".join(product.features or [])
            return {
                "success": True,
                "name": name,
                "result": (
                    f"商品「{product.name}」（{product.product_no}）：价格 ¥{product.price}，"
                    f"质保 {product.warranty or '无'}，卖点：{features}。"
                    f"{product.description or ''}"
                ),
            }
        return {"success": False, "name": name, "result": f"未知工具：{name}"}
    except Exception as e:
        logger.error(f"工具执行失败 {name}: {e}")
        return {"success": False, "name": name, "result": f"工具执行出错：{e}"}


# ------------------------------------------------------------------
# LangGraph 状态与节点
# ------------------------------------------------------------------

class SupportAgentState(TypedDict, total=False):
    """图状态（total=False 的 TypedDict，节点返回部分字段即可被合并）

    LangGraph 用本 TypedDict 推断状态 channel，因此所有「初始注入」与「节点回写」
    的字段都必须在此声明，否则 ainvoke 会报「输入/返回包含未在 schema 定义的键」。
    """

    # ---- 初始注入（db/cfg/session/sink 等不可序列化对象经 config 注入，不进 checkpoint）----
    provider_type: str
    customer_id: Any
    query: str
    history: List[Any]
    retrieved_docs: List[Any]

    # ---- 节点产生 ----
    intent: Optional[str]
    intent_label: str
    confidence: float
    context_text: str
    references: List[Any]
    tool_results: List[Any]
    escalation_ticket: Any
    final_response: str
    return_confirmed: bool
    return_decision: Optional[Any]


async def router(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    cfg = config["configurable"]["cfg"]
    t0 = time.perf_counter()
    intent, confidence, tokens = await detect_intent(
        state["query"],
        cfg.chat_model,
        state["provider_type"],
        app_settings.SUPPORT_AGENT_INTENT_TIMEOUT,
        history_text=_format_history(state.get("history") or []),
    )
    duration_ms = int((time.perf_counter() - t0) * 1000)
    label = IntentCategory.LABELS.get(intent, intent)
    await sink(
        "thought",
        {
            "node": "router",
            "summary": f"识别意图：{label}（把握度 {confidence:.0%}）",
            "duration_ms": duration_ms,
            "model": cfg.chat_model,
            "tokens": tokens,
            "input": {"query": state["query"]},
            "output": {"intent": intent, "confidence": confidence},
        },
    )
    return {"intent": intent, "intent_label": label, "confidence": confidence}


async def knowledge(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    cfg = config["configurable"]["cfg"]
    db = config["configurable"]["db"]
    t0 = time.perf_counter()
    context_text, references, _ = await build_context(state["query"], cfg, db)
    duration_ms = int((time.perf_counter() - t0) * 1000)
    suggest_human = state.get("intent") in IntentCategory.SENSITIVE
    await sink(
        "references",
        {
            "intent": state.get("intent"),
            "intent_label": state.get("intent_label"),
            "confidence": state.get("confidence", 0),
            "references": references,
            "suggest_human": suggest_human,
        },
    )
    await sink(
        "thought",
        {
            "node": "knowledge",
            "summary": "检索知识库并整理参考资料",
            "duration_ms": duration_ms,
            "input": {"query": state["query"]},
            "output": {"reference_count": len(references)},
        },
    )
    return {"context_text": context_text, "references": references}


async def tool_agent(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    cfg = config["configurable"]["cfg"]
    db = config["configurable"]["db"]
    query = state["query"]
    history_text = _format_history(state.get("history") or [])
    prompt = (
        "你是客服工具调度助手。根据用户的订单/物流/商品问题，决定调用哪些工具查询信息，"
        "最多调用 2 个工具。"
    )
    if history_text:
        prompt += f"\n历史对话：\n{history_text}\n"
    prompt += "用户问题：" + query
    tool_results: List[Dict[str, Any]] = []
    try:
        t0 = time.perf_counter()
        decision = await asyncio.wait_for(
            llm_service.chat_with_tools(
                [{"role": "user", "content": prompt}],
                SUPPORT_TOOLS,
                model=cfg.chat_model,
                provider=state["provider_type"],
                temperature=0.2,
                max_tokens=1024,
            ),
            timeout=app_settings.SUPPORT_AGENT_TOOL_TIMEOUT,
        )
        decision_ms = int((time.perf_counter() - t0) * 1000)
        tool_calls = decision.get("tool_calls", [])[: app_settings.SUPPORT_AGENT_MAX_TOOL_ROUNDS]
        await sink(
            "thought",
            {
                "node": "tool",
                "summary": f"工具调度决策：识别需调用 {len(tool_calls)} 个工具",
                "duration_ms": decision_ms,
                "model": decision.get("model") or cfg.chat_model,
                "tokens": decision.get("tokens_used"),
                "input": {"query": query},
                "output": {
                    "tool_count": len(tool_calls),
                    "tools": [tc.get("name") for tc in tool_calls],
                },
            },
        )
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("arguments", {})
            ct0 = time.perf_counter()
            res = await run_support_tool(db, name, args)
            ct_ms = int((time.perf_counter() - ct0) * 1000)
            await sink(
                "thought",
                {
                    "node": "tool",
                    "summary": f"调用工具 {name}({args})",
                    "duration_ms": ct_ms,
                    "input": args,
                    "output": {"success": res["success"]},
                },
            )
            tool_results.append(res)
            await sink(
                "tool_call",
                {
                    "name": res["name"],
                    "arguments": args,
                    "result": res["result"],
                    "success": res["success"],
                },
            )
    except Exception as e:
        logger.warning(f"Tool Agent 执行异常：{e}")
        await sink("thought", {"node": "tool", "summary": "工具调用异常，转知识库兜底"})
    return {"tool_results": tool_results}


async def escalation(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    cfg = config["configurable"]["cfg"]
    db = config["configurable"]["db"]
    session = config["configurable"]["session"]
    try:
        t0 = time.perf_counter()
        model = SupportChatModel(
            provider_type=state["provider_type"],
            model=cfg.chat_model,
            temperature=0.3,
            max_tokens=1024,
            timeout=app_settings.SUPPORT_AGENT_ESCALATION_TIMEOUT,
        )
        runnable = model.with_structured_output(EscalationTicket)
        ticket = await runnable.ainvoke(
            [{"role": "user", "content": ESCALATION_PROMPT + state["query"]}]
        )
        tokens = runnable.last_tokens
        duration_ms = int((time.perf_counter() - t0) * 1000)
        if ticket is None:
            raise ValueError("工单结构化输出解析失败")
        ticket_service = SupportTicketService(db)
        ticket_data = ticket_service.create_from_escalation(
            session, ticket.model_dump(), state["customer_id"]
        )
        # 会话置待人工，坐席在工单中心/工作台接管
        session.status = SessionStatus.PENDING_HUMAN
        db.commit()
        await sink(
            "thought",
            {
                "node": "escalation",
                "summary": f"已生成工单 {ticket_data['ticket_no']} 并升级人工",
                "duration_ms": duration_ms,
                "model": cfg.chat_model,
                "tokens": tokens,
                "input": {"query": state["query"]},
                "output": {"ticket_no": ticket_data["ticket_no"]},
            },
        )
        await sink("ticket", ticket_data)
        return {"escalation_ticket": ticket_data}
    except Exception as e:
        logger.warning(f"Escalation 异常：{e}")
        return {"escalation_ticket": None}


async def summary(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    cfg = config["configurable"]["cfg"]
    t0 = time.perf_counter()

    sections: List[str] = [f"用户意图：{state.get('intent_label', '')}", f"用户问题：{state['query']}"]
    history_text = _format_history(state.get("history") or [])
    if history_text:
        sections.append(f"【历史对话】\n{history_text}")
    ctx = state.get("context_text")
    if ctx:
        sections.append(f"【知识库参考】\n{ctx}")
    tool_results = state.get("tool_results") or []
    if tool_results:
        lines = "\n".join(f"- {t['result']}" for t in tool_results)
        sections.append(f"【工具查询结果】\n{lines}")
    ticket = state.get("escalation_ticket")
    if ticket:
        sections.append(
            f"【已升级工单】工单号 {ticket['ticket_no']}（{ticket.get('type_label','')}），"
            f"优先级 {ticket.get('priority_label','')}：{ticket.get('title','')}"
        )
    # 退货 / 退款 human-in-the-loop 结果：把人工决策纳入最终回复语境
    if state.get("return_confirmed"):
        decision = state.get("return_decision")
        action = decision.get("decision") if isinstance(decision, dict) else decision
        if action == "rejected":
            sections.append(
                "【人工确认】本次退货/退款诉求已被人工拒绝，请勿自动执行退款，"
                "请说明需由坐席介入处理，或引导用户补充材料。"
            )
        elif action == "approved":
            sections.append(
                "【人工确认】退货/退款已获人工确认，可依据退换货政策继续协助用户办理。"
            )
    user_prompt = "\n\n".join(sections)
    build_ms = int((time.perf_counter() - t0) * 1000)
    await sink(
        "thought",
        {
            "node": "summary",
            "summary": "汇总信息生成最终回复",
            "duration_ms": build_ms,
            "model": cfg.chat_model,
            "input": {
                "intent_label": state.get("intent_label", ""),
                "query": state["query"],
            },
            "output": {
                "context_len": len(ctx or ""),
                "tool_result_count": len(tool_results),
            },
        },
    )

    answer = ""
    try:
        async for chunk in llm_service.stream_chat(
            [
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=cfg.chat_model,
            provider=state["provider_type"],
            temperature=cfg.chat_temperature,
            max_tokens=cfg.chat_max_tokens,
            timeout=app_settings.SUPPORT_AGENT_SUMMARY_TIMEOUT,
        ):
            if not isinstance(chunk, str) or not chunk:
                continue
            answer += chunk
            await sink("delta", {"content": chunk})
    except Exception as e:
        logger.warning(f"Summary 流式失败：{e}")
        answer = answer or "抱歉，我暂时无法处理您的问题，已为您转接人工客服，请稍候。"
        await sink("delta", {"content": answer})
    return {"final_response": answer}


def route_by_intent(state: SupportAgentState) -> str:
    """Router 条件边：意图 → 下游 Agent"""
    return IntentCategory.ROUTE.get(state.get("intent"), "knowledge")


async def confirm_return(state: SupportAgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Human-in-the-loop 闸门：退货 / 退款诉求先挂起，等人工确认后再继续。

    用 langgraph 的 interrupt 暂停图执行；前端收到 human_confirm 事件后弹出确认，
    坐席通过 /support/sessions/{id}/confirm 回传决策，后端用 Command(resume=...) 唤醒图。
    interrupt 的 payload 即 human_confirm 事件内容；resume 时 interrupt() 返回人工决策。
    """
    if not isinstance(config, dict):
        config = get_running_config()
    sink = config["configurable"]["sink"]
    t0 = time.perf_counter()
    if not is_return_request(state["query"]):
        return {}
    decision = interrupt(
        {
            "type": "return_confirm",
            "title": "退货 / 退款操作需人工确认",
            "query": state["query"],
            "message": "用户诉求涉及退货或退款，请在继续前确认是否由 AI 直接处理。",
            "options": ["approved", "rejected"],
        }
    )
    logger.info(f"退货确认收到人工决策：{decision}")
    await sink(
        "thought",
        {
            "node": "confirm_return",
            "summary": "已收到人工确认，继续处理退货/退款诉求",
            "duration_ms": int((time.perf_counter() - t0) * 1000),
            "input": {"query": state["query"]},
            "output": {
                "decision": decision.get("decision") if isinstance(decision, dict) else decision
            },
        },
    )
    return {"return_confirmed": True, "return_decision": decision}


def _get_support_checkpointer():
    """获取客服图 LangGraph checkpointer（持久化）。

    参考 agent.py：优先用 AsyncSqliteSaver 复用现有数据库文件路径（checkpoint 落盘、跨进程/重启保留），
    不可用时（非 SQLite / 未装 langgraph-checkpoint-sqlite）回退 InMemorySaver。
    """

    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from app.core.config import settings

        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            db_path = db_url.replace("sqlite:///", "")
            return AsyncSqliteSaver.from_conn_string(db_path)
        logger.warning("当前数据库不是 SQLite，使用内存 checkpointer")
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()
    except ImportError:
        logger.warning("langgraph-checkpoint-sqlite 未安装，使用内存 checkpointer")
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()


_BUILDER = None


def _get_builder() -> StateGraph:
    """构建客服多 Agent 图的节点/边结构并缓存（不含 checkpointer）。

    checkpointer 在调用方按请求通过 `async with _get_support_checkpointer()` 注入，
    这样每个请求使用独立 SQLite 连接生命周期，但 checkpoint 数据持久化在同一数据库文件。
    """
    global _BUILDER
    if _BUILDER is not None:
        return _BUILDER
    b = StateGraph(SupportAgentState)
    b.add_node("router", router)
    b.add_node("confirm_return", confirm_return)
    b.add_node("knowledge", knowledge)
    b.add_node("tool", tool_agent)
    b.add_node("escalation", escalation)
    b.add_node("summary", summary)

    # START → Router → 全部意图先过 confirm_return 闸门（仅退货/退款会真正挂起）
    b.add_edge(START, "router")
    b.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "knowledge": "confirm_return",
            "tool": "confirm_return",
            "escalation": "confirm_return",
        },
    )
    # confirm_return 之后仍按意图路由到对应的 Agent
    b.add_conditional_edges(
        "confirm_return",
        route_by_intent,
        {
            "knowledge": "knowledge",
            "tool": "tool",
            "escalation": "escalation",
        },
    )
    b.add_edge("knowledge", "summary")
    b.add_edge("tool", "summary")
    b.add_edge("escalation", "summary")
    b.add_edge("summary", END)
    _BUILDER = b
    return b


def build_graph(checkpointer):
    """编译客服多 Agent 图并注入 checkpointer。

    参考 agent.py：checkpointer 由调用方通过 `async with _get_support_checkpointer()` 管理生命周期，
    以 session.id 作为 thread_id 保存会话窗口，并支持 interrupt 恢复。
    不可序列化运行时对象（db / cfg / session / sink）经 config 传入，不进入 checkpoint。
    """
    return _get_builder().compile(checkpointer=checkpointer)
