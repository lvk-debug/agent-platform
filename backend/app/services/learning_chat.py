"""
学习助手 AI 问答服务

职责：上下文组装 → 流式问答 → 会话落库 → 推荐问题生成。

设计要点：
1. **上下文 = 检索片段 + 当前位置窗口**。窗口优先保留，保证回答「懂你正在看哪」；
   检索片段按相关度补齐，整体受字符预算约束，避免长字幕/大文档打爆 prompt。
2. **问答永不因索引失败而中断**。索引未就绪或 embedding 不可用时，
   退化为「当前位置窗口 + 关键词召回」，只是召回质量下降。
3. **模型复用平台已配置的模型与供应商**（models / model_providers 表），
   未指定 model_id 时自动挑第一个可用模型。
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
from app.models.learning import (
    ChatRole,
    LearningChatMessage,
    LearningChatSession,
    LearningPageText,
    LearningResource,
    LearningTranscript,
    ResourceType,
    TranscriptSource,
)
from app.models.model import Model, ModelProvider
from app.schemas.learning import ContextRef
from app.services.learning_index import LearningIndexService, ensure_page_texts
from app.services.llm import LLMService
from app.utils.logger import logger

SYSTEM_PROMPT = """你是「学习助手」，正在陪用户学习一份具体的资料（文档或视频）。

规则：
1. 只依据【资料内容】作答。资料里没有的信息，要明确说明"资料中没有提到"，不要编造。
2. 回答具体、有依据，尽量引用资料中的原话、数据或结论。
3. 用中文回答，条理清晰，必要时分点说明。
4. 资料片段后的 [1] [2] 是引用编号，回答中如需标明出处请用同样的编号。
5. 若用户的问题与当前资料无关，简要说明你只能围绕这份资料提供帮助。
"""

# 截断时能保留的最小片段长度，短于它就不如整段丢弃
MIN_SNIPPET_CHARS = 120


def _llm_provider_type(provider: ModelProvider) -> str:
    """
    把平台的供应商类型映射到 LLMService 认识的类型

    LLMService 只实现 openai / anthropic 两种协议；平台里还能配 local、custom，
    而这些基本都是 OpenAI 兼容端点（vLLM / Ollama / LM Studio 等），
    一律按 openai 处理即可，否则会报「不支持的供应商」。
    """
    return provider.provider_type if provider.provider_type == "anthropic" else "openai"


def _describe_exception(exc: BaseException) -> str:
    """
    把异常整理成人话

    有些异常（典型是 httpx 的超时类）`str()` 是空串，直接拼进提示就只剩
    「模型调用失败：」，完全看不出原因。这里一律带上类型名，
    并对 HTTP 状态错误补上响应体，方便定位是鉴权、模型名还是配额问题。
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        body = (exc.response.text or "").strip()
        if len(body) > 300:
            body = body[:300] + "…"
        return f"供应商返回 HTTP {status}：{body or exc.response.reason_phrase}"

    text = str(exc).strip()
    return f"{type(exc).__name__}：{text}" if text else type(exc).__name__


def _item_key(item: Dict[str, Any]) -> tuple:
    """片段去重键：类型 + 定位坐标"""
    return (item.get("type"), item.get("page_index"), item.get("start_ms"))


def _overlaps_pinned(item: Dict[str, Any], pinned: List[Dict[str, Any]]) -> bool:
    """
    判断视频片段是否与用户已指定的区间重叠

    只按 start_ms 去重不够：默认上下文是 [pos, pos+30s]，当前位置窗口是
    [pos-30s, pos+30s]，起点不同却讲的是同一段字幕，会被重复塞进 prompt。
    """
    if item.get("type") != "transcript":
        return False
    start = item.get("start_ms") or 0
    end = item.get("end_ms") or start
    for pin in pinned:
        if pin.get("type") != "transcript":
            continue
        pin_start = pin.get("start_ms") or 0
        pin_end = pin.get("end_ms") or pin_start
        if start < pin_end and end > pin_start:
            return True
    return False


def _clip_items(
    items: List[Dict[str, Any]], budget: int
) -> Tuple[List[Dict[str, Any]], int]:
    """
    按字符预算截断片段列表

    Returns:
        (保留的片段, 已占用字符数)——调用方据此算出剩余预算
    """
    used = 0
    kept: List[Dict[str, Any]] = []
    for item in items:
        snippet = item.get("snippet") or ""
        if used + len(snippet) > budget:
            remaining = budget - used
            if remaining >= MIN_SNIPPET_CHARS:
                kept.append({**item, "snippet": snippet[:remaining]})
                used += remaining
            break
        kept.append(item)
        used += len(snippet)
    return kept, used


def _is_chinese_lang(lang: Optional[str]) -> bool:
    """是否为中文轨道（yt-dlp 语言代码形如 zh-Hans / zh-CN）"""
    return (lang or "").lower().startswith("zh")


def _build_translate_prompt(texts: List[str], target_lang: str) -> str:
    """构造字幕翻译 prompt：强制按行号逐条输出，避免模型合并或漏行"""
    numbered = "\n".join(f"{index}. {text}" for index, text in enumerate(texts, 1))
    language = "简体中文" if _is_chinese_lang(target_lang) else target_lang
    return (
        f"把下面逐行编号的字幕翻译成{language}。\n"
        "要求：\n"
        "1. 严格按相同的行号逐行输出译文，每行一条，不要合并、拆分或增删行数。\n"
        "2. 只输出译文本身，不要解释，不要保留原文。\n"
        "3. 数字、专有名词按目标语言的自然习惯处理。\n\n"
        f"{numbered}"
    )


def _parse_translation(raw: str, expected: int) -> List[str]:
    """
    按行号解析译文

    用行号定位而不是按顺序取行：模型偶尔会漏某一行，
    顺序取值会让后面所有译文整体错位——那样比漏一句更糟。
    """
    result = [""] * expected
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^(\d+)\s*[.、．)）:：]\s*(.*)$", line)
        if not match:
            continue
        index = int(match.group(1))
        if 1 <= index <= expected:
            result[index - 1] = match.group(2).strip()
    return result


def _format_ms(ms: Optional[int]) -> str:
    """毫秒 → mm:ss / hh:mm:ss"""
    total = max(int(ms or 0) // 1000, 0)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


class LearningChatService:
    """学习助手问答服务"""

    def __init__(self, db: Session):
        self.db = db
        self.index_service = LearningIndexService(db)

    # ------------------------------------------------------------------
    # 会话与历史
    # ------------------------------------------------------------------

    def get_or_create_session(
        self, resource_id: int, user_id: int, model_name: str = ""
    ) -> LearningChatSession:
        """一个资源一条会话；已存在则沿用并按需更新最近使用的模型"""
        session = (
            self.db.query(LearningChatSession)
            .filter(
                LearningChatSession.resource_id == resource_id,
                LearningChatSession.user_id == user_id,
            )
            .first()
        )
        if session:
            if model_name and session.model_name != model_name:
                session.model_name = model_name
                self.db.commit()
            return session

        session = LearningChatSession(
            resource_id=resource_id, user_id=user_id, model_name=model_name
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_messages(
        self, resource_id: int, user_id: int, limit: int = 100
    ) -> List[LearningChatMessage]:
        """按时间正序返回该资源的问答历史"""
        session = (
            self.db.query(LearningChatSession)
            .filter(
                LearningChatSession.resource_id == resource_id,
                LearningChatSession.user_id == user_id,
            )
            .first()
        )
        if not session:
            return []
        rows = (
            self.db.query(LearningChatMessage)
            .filter(LearningChatMessage.session_id == session.id)
            .order_by(LearningChatMessage.id.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return rows

    def list_page_options(self, resource: LearningResource) -> List[Dict[str, Any]]:
        """
        文档各页的 {page_index, title}，供前端 @ 选择器列出可添加的页

        页面文本尚未抽取时先落库（解析一次复用，后续检索也用得到）；
        解析失败则退回纯页码列表，保证选择器永远有东西可选。
        """
        rows = (
            self.db.query(LearningPageText)
            .filter(LearningPageText.resource_id == resource.id)
            .order_by(LearningPageText.page_index.asc())
            .all()
        )
        if not rows:
            # 用**同一个 Session** 落库：若走独立 Session 提交，本 Session 在更高
            # 的隔离级别下可能读不到新行（SQLite 侥幸可用，PG/MySQL 会出问题）
            self.index_service.ensure_page_texts(resource)
            rows = (
                self.db.query(LearningPageText)
                .filter(LearningPageText.resource_id == resource.id)
                .order_by(LearningPageText.page_index.asc())
                .all()
            )
        if rows:
            return [
                {
                    "page_index": row.page_index,
                    "title": row.title or f"第 {row.page_index + 1} 页",
                }
                for row in rows
            ]

        count = max(resource.page_count or 0, 1)
        return [
            {"page_index": index, "title": f"第 {index + 1} 页"} for index in range(count)
        ]

    def clear_messages(self, resource_id: int, user_id: int) -> int:
        """清空问答历史（保留会话本身），返回删除条数"""
        session = (
            self.db.query(LearningChatSession)
            .filter(
                LearningChatSession.resource_id == resource_id,
                LearningChatSession.user_id == user_id,
            )
            .first()
        )
        if not session:
            return 0
        count = (
            self.db.query(LearningChatMessage)
            .filter(LearningChatMessage.session_id == session.id)
            .delete(synchronize_session=False)
        )
        session.message_count = 0
        self.db.commit()
        return count

    # ------------------------------------------------------------------
    # 上下文
    # ------------------------------------------------------------------

    async def build_context(
        self,
        resource: LearningResource,
        query: str,
        position: float,
        context_refs: Optional[List[ContextRef]] = None,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        组装上下文：用户指定的片段（强制） + 当前位置窗口 + 检索片段

        手动 @ 的内容排在最前、且优先占用预算——用户显式圈定的范围就是本次回答的
        "必读材料"，不该被检索结果挤掉；其余预算再给窗口与检索。

        Returns:
            (references, context_text)
        """
        pinned, pinned_used = _clip_items(
            self._resolve_pinned(resource, context_refs or []),
            settings.LEARNING_CHAT_PINNED_CONTEXT_CHARS,
        )

        window = self.index_service.get_window(resource, position)
        hits = await self.index_service.search(resource, query)

        # 合并去重：已被用户点名的片段不再重复出现
        # 视频侧还要按区间重叠判断，否则"默认上下文"与"当前位置窗口"会重复
        seen: set = {_item_key(item) for item in pinned}
        merged: List[Dict[str, Any]] = []
        for item in list(window) + list(hits):
            key = _item_key(item)
            if key in seen or _overlaps_pinned(item, pinned):
                continue
            seen.add(key)
            merged.append(item)

        rest_budget = max(settings.LEARNING_CHAT_CONTEXT_CHARS - pinned_used, 0)
        rest, _ = _clip_items(merged, rest_budget)

        kept = pinned + rest
        return kept, self._compose_context_text(resource, kept, position, len(pinned))

    def _resolve_pinned(
        self, resource: LearningResource, refs: List[ContextRef]
    ) -> List[Dict[str, Any]]:
        """把前端传入的上下文引用解析成带正文的片段（读库取真实内容）"""
        if not refs:
            return []

        if resource.type == ResourceType.DOCUMENT:
            page_indexes = [
                ref.page_index
                for ref in refs
                if ref.type == "page" and ref.page_index is not None
            ]
            if not page_indexes:
                return []
            # IN 查询一次取回，避免逐页打库
            rows = (
                self.db.query(LearningPageText)
                .filter(
                    LearningPageText.resource_id == resource.id,
                    LearningPageText.page_index.in_(page_indexes),
                )
                .order_by(LearningPageText.page_index.asc())
                .all()
            )
            return [
                {
                    "type": "page",
                    "page_index": row.page_index,
                    "start_ms": None,
                    "end_ms": None,
                    "title": row.title,
                    "snippet": (row.content or "")[
                        : settings.LEARNING_INDEX_CHUNK_CHARS
                    ],
                    "score": 0.0,
                    "is_pinned": True,
                }
                for row in rows
            ]

        pinned: List[Dict[str, Any]] = []
        seen: set = set()
        for ref in refs:
            if ref.type != "transcript" or ref.start_ms is None:
                continue
            # 未给结束时间时按一个窗口兜底，否则只命中一两条字幕、内容过窄
            end_ms = (
                ref.end_ms
                if ref.end_ms is not None
                else ref.start_ms + settings.LEARNING_CHAT_TRANSCRIPT_WINDOW_MS
            )
            key = ref.start_ms
            if key in seen:
                continue
            seen.add(key)

            cues = (
                self.db.query(LearningTranscript)
                .filter(
                    LearningTranscript.resource_id == resource.id,
                    # 排除 AI 译文：它和原文时间轴重合，混进来会中英夹杂
                    LearningTranscript.source != TranscriptSource.LLM,
                    LearningTranscript.end_ms >= ref.start_ms,
                    LearningTranscript.start_ms <= end_ms,
                )
                .order_by(LearningTranscript.start_ms.asc())
                .all()
            )
            if cues:
                original_lang = cues[0].language
                cues = [cue for cue in cues if cue.language == original_lang]
            if not cues:
                continue
            pinned.append(
                {
                    "type": "transcript",
                    "page_index": None,
                    "start_ms": cues[0].start_ms,
                    "end_ms": cues[-1].end_ms,
                    "title": "",
                    "snippet": "\n".join(cue.text for cue in cues if cue.text)[
                        : settings.LEARNING_INDEX_CHUNK_CHARS
                    ],
                    "score": 0.0,
                    "is_pinned": True,
                }
            )
        return pinned

    def _compose_context_text(
        self,
        resource: LearningResource,
        items: List[Dict[str, Any]],
        position: float,
        pinned_count: int = 0,
    ) -> str:
        if resource.type == ResourceType.DOCUMENT:
            header = f"【资料】{resource.title}（文档，共 {resource.page_count} 页）"
            current = f"【用户当前位置】第 {int(position or 0) + 1} 页"
        else:
            header = f"【资料】{resource.title}（视频，时长 {_format_ms(resource.duration_seconds * 1000)}）"
            current = f"【用户当前位置】{_format_ms(int((position or 0) * 1000))}"

        lines = [header]
        if resource.summary:
            lines.append(f"【资料摘要】{resource.summary}")
        lines.append(current)

        if not items:
            lines.append("【相关资料片段】暂无可用内容（资料可能还没有可检索的文本）。")
            return "\n".join(lines)

        # 前 pinned_count 项是用户手动 @ 的，单独成段并明确其优先级
        pinned_items = items[:pinned_count]
        rest_items = items[pinned_count:]

        def render(item: Dict[str, Any], index: int, flag: str) -> str:
            if item.get("type") == "page":
                location = f"第 {(item.get('page_index') or 0) + 1} 页"
            else:
                location = _format_ms(item.get("start_ms"))
            title = item.get("title") or ""
            title_part = f" {title}" if title else ""
            return f"[{index}] {location}{flag}{title_part}\n{item.get('snippet') or ''}"

        if pinned_items:
            lines.append("【用户指定的上下文】以下是用户明确圈定的内容，请优先依据它们作答。")
            for offset, item in enumerate(pinned_items, 1):
                lines.append(render(item, offset, "（用户指定）"))

        if rest_items:
            lines.append("【相关资料片段】")
            for offset, item in enumerate(rest_items, 1):
                flag = "（用户正在看）" if item.get("is_current") else ""
                lines.append(render(item, len(pinned_items) + offset, flag))

        return "\n\n".join(lines)

    def _build_messages(
        self,
        resource: LearningResource,
        session: LearningChatSession,
        context_text: str,
        query: str,
    ) -> List[Dict[str, str]]:
        """组装 messages：system + 历史若干轮 + 本次（带上下文的提问）"""
        messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

        turns = settings.LEARNING_CHAT_HISTORY_TURNS
        history = (
            self.db.query(LearningChatMessage)
            .filter(
                LearningChatMessage.session_id == session.id,
                LearningChatMessage.error.is_(None),
            )
            .order_by(LearningChatMessage.id.desc())
            .limit(turns * 2)
            .all()
        )
        history.reverse()
        for row in history:
            messages.append({"role": row.role, "content": row.content})

        messages.append(
            {"role": "user", "content": f"{context_text}\n\n【我的问题】{query}"}
        )
        return messages

    # ------------------------------------------------------------------
    # 模型解析
    # ------------------------------------------------------------------

    def _resolve_model(
        self, model_id: Optional[int]
    ) -> Tuple[Optional[Model], Optional[ModelProvider]]:
        """按 model_id 取模型与供应商；未指定或不可用时回退第一个可用模型"""
        base = (
            self.db.query(Model)
            .options(joinedload(Model.provider))
            .filter(Model.is_active.is_(True))
        )
        if model_id:
            row = base.filter(Model.id == model_id).first()
            if row and row.provider and row.provider.is_active:
                return row, row.provider
            logger.warning(f"指定模型不可用，回退默认模型 model_id={model_id}")

        for row in base.all():
            if row.provider and row.provider.is_active:
                return row, row.provider
        return None, None

    # ------------------------------------------------------------------
    # 流式问答
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        resource: LearningResource,
        user_id: int,
        query: str,
        position: float,
        model_id: Optional[int] = None,
        context_refs: Optional[List[ContextRef]] = None,
    ) -> AsyncGenerator[str, None]:
        """流式问答，逐步 yield SSE 事件"""
        started = time.perf_counter()
        session = self.get_or_create_session(resource.id, user_id)

        # 文档要先有自己的页面文本才能检索；这里同步保证一次，
        # 否则首次提问（向量索引尚未构建）会拿到空上下文，回答质量很差。
        if resource.type == ResourceType.DOCUMENT:
            await asyncio.to_thread(ensure_page_texts, resource.id)

        references, context_text = await self.build_context(
            resource, query, position, context_refs
        )
        # 先发来源：用户能在答案生成时就看到引用，边读边可跳转
        yield self._sse_event("references", {"references": references})

        # 先取历史再存本次提问，否则本次问题会被当成历史重复拼进 messages
        messages = self._build_messages(resource, session, context_text, query)
        self._save_message(session, resource.id, user_id, ChatRole.USER, query)

        model_row, provider = self._resolve_model(model_id)
        if not model_row or not provider:
            detail = "未找到可用模型，请先在平台「模型管理」中配置供应商与模型"
            self._save_message(
                session, resource.id, user_id, ChatRole.ASSISTANT, "", error=detail
            )
            yield self._sse_event("error", {"detail": detail})
            return

        # 记下本次使用的模型，下次打开助手可直接沿用
        if model_row and session.model_name != model_row.model_id:
            session.model_name = model_row.model_id
            self.db.commit()

        answer = ""
        try:
            llm = LLMService()
            await llm.register_provider(
                provider_type=_llm_provider_type(provider),
                api_key=provider.api_key,
                api_endpoint=provider.api_endpoint,
            )
            async for chunk in llm.stream_chat(
                messages=messages,
                model=model_row.model_id,
                provider=_llm_provider_type(provider),
                temperature=settings.LEARNING_CHAT_TEMPERATURE,
                max_tokens=settings.LEARNING_CHAT_MAX_TOKENS,
            ):
                if not chunk:
                    continue
                answer += chunk
                yield self._sse_event("delta", {"content": chunk})
        except Exception as exc:  # noqa: BLE001 - 模型调用失败要降级为错误事件，不能断流
            logger.error(f"学习助手问答失败 resource={resource.id}: {exc}", exc_info=True)
            detail = f"模型调用失败：{_describe_exception(exc)}"
            self._save_message(
                session,
                resource.id,
                user_id,
                ChatRole.ASSISTANT,
                "",
                error=detail[:500],
            )
            yield self._sse_event("error", {"detail": detail})
            return

        latency_ms = int((time.perf_counter() - started) * 1000)
        message = self._save_message(
            session,
            resource.id,
            user_id,
            ChatRole.ASSISTANT,
            answer,
            references=references,
            model=model_row.model_id,
            latency_ms=latency_ms,
        )
        yield self._sse_event(
            "done", {"message_id": message.id, "latency_ms": latency_ms}
        )

    # ------------------------------------------------------------------
    # 字幕翻译（双语兜底）
    # ------------------------------------------------------------------

    # 每批翻译的条数：一次喂太多，模型容易漏行或串行，且单次响应可能超时
    TRANSLATE_BATCH = 25

    async def translate_transcripts(
        self, resource: LearningResource, target_lang: str = "zh-CN"
    ) -> int:
        """
        把原文字幕翻译为目标语言并入库（source=llm）

        平台没给译文轨道时（B站、或 YouTube 无中文翻译）用它兜底。
        幂等：已有该语言的译文就直接返回，不重复消耗 token。
        """
        if resource.type != ResourceType.VIDEO:
            return 0

        rows = (
            self.db.query(LearningTranscript)
            .filter(LearningTranscript.resource_id == resource.id)
            .order_by(LearningTranscript.start_ms.asc())
            .all()
        )
        if not rows:
            return 0
        # 已有任意中文轨道就跳过。不能精确比对 code：
        # 平台轨常是 zh-Hans，而我们默认写入 zh-CN，精确比对会重复翻译出第二条中文轨。
        if any(_is_chinese_lang(row.language) for row in rows):
            return 0

        # 原文 = 时间最早那条所属的语言；原文已是中文则无需翻译
        original_lang = rows[0].language
        if _is_chinese_lang(original_lang):
            return 0
        source_rows = [row for row in rows if row.language == original_lang]
        if not source_rows:
            return 0

        model_row, provider = self._resolve_model(None)
        if not model_row or not provider:
            logger.warning(f"无可用模型，跳过字幕翻译 resource={resource.id}")
            return 0

        llm = LLMService()
        await llm.register_provider(
            provider_type=_llm_provider_type(provider),
            api_key=provider.api_key,
            api_endpoint=provider.api_endpoint,
        )

        translated: List[Tuple[LearningTranscript, str]] = []
        for start in range(0, len(source_rows), self.TRANSLATE_BATCH):
            batch = source_rows[start : start + self.TRANSLATE_BATCH]
            try:
                result = await llm.chat(
                    messages=[
                        {
                            "role": "user",
                            "content": _build_translate_prompt(
                                [row.text for row in batch], target_lang
                            ),
                        }
                    ],
                    model=model_row.model_id,
                    provider=_llm_provider_type(provider),
                    temperature=0.2,
                    max_tokens=2048,
                )
                lines = _parse_translation(result.get("content", ""), len(batch))
            except Exception as exc:  # noqa: BLE001 - 单批失败不该中断整条翻译
                logger.warning(f"字幕翻译批次失败 resource={resource.id}: {exc}")
                continue

            for row, text in zip(batch, lines):
                if text:
                    translated.append((row, text))

        if not translated:
            return 0

        # 先清再写：重复触发时不至于把译文越堆越多
        self.db.query(LearningTranscript).filter(
            LearningTranscript.resource_id == resource.id,
            LearningTranscript.language == target_lang,
            LearningTranscript.source == TranscriptSource.LLM,
        ).delete(synchronize_session=False)

        objects = [
            LearningTranscript(
                resource_id=resource.id,
                user_id=resource.user_id,
                seq=row.seq,
                start_ms=row.start_ms,
                end_ms=row.end_ms,
                text=text,
                language=target_lang,
                source=TranscriptSource.LLM,
            )
            for row, text in translated
        ]
        for start in range(0, len(objects), 500):
            self.db.bulk_save_objects(objects[start : start + 500])

        # 把译文轨道登记到资源上，前端与列表接口据此判断「已有双语」
        tracks = [item for item in (resource.subtitle_tracks or []) if isinstance(item, dict)]
        if not any(item.get("lang") == target_lang for item in tracks):
            tracks.append(
                {
                    "lang": target_lang,
                    "name": target_lang,
                    "source": TranscriptSource.LLM,
                    "is_original": False,
                }
            )
            resource.subtitle_tracks = tracks

        self.db.commit()
        logger.info(f"字幕翻译完成 resource={resource.id} count={len(objects)}")
        return len(objects)

    # ------------------------------------------------------------------
    # 推荐问题
    # ------------------------------------------------------------------

    async def suggest_questions(self, resource: LearningResource) -> List[str]:
        """
        生成 3 个推荐问题并缓存到资源上

        失败或超时一律回退固定模板，绝不让「打开助手」这个动作卡住。
        """
        if resource.suggested_questions:
            return list(resource.suggested_questions)

        model_row, provider = self._resolve_model(None)
        if not model_row or not provider:
            return self._fallback_questions(resource)

        summary = await self._ensure_summary(resource)
        if not summary:
            return self._fallback_questions(resource)

        prompt = (
            "下面是用户正在学习的一份资料的信息。请基于它提出 3 个最有价值的问题，"
            "帮助用户快速理解这份资料。\n\n"
            f"标题：{resource.title}\n"
            f"类型：{'文档' if resource.type == ResourceType.DOCUMENT else '视频'}\n"
            f"内容摘要：\n{summary[: settings.LEARNING_SUMMARY_CHARS]}\n\n"
            "要求：\n"
            "1. 只输出 3 个问题，一行一个，不要编号、不要多余解释。\n"
            "2. 问题要具体，能在这份资料里找到答案（如背景、核心观点、关键步骤、结论）。\n"
            "3. 每个问题不超过 30 个字。\n"
            "4. 用中文。"
        )

        try:
            llm = LLMService()
            await llm.register_provider(
                provider_type=_llm_provider_type(provider),
                api_key=provider.api_key,
                api_endpoint=provider.api_endpoint,
            )
            # 推荐问题不需要流式，但必须限时，避免用户干等
            result = await _with_timeout(
                llm.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=model_row.model_id,
                    provider=provider.provider_type,
                    temperature=0.7,
                    max_tokens=300,
                ),
                settings.LEARNING_SUGGEST_TIMEOUT,
            )
            questions = _parse_questions(result.get("content", ""))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"推荐问题生成失败，回退模板 resource={resource.id}: {exc}")
            questions = []

        if len(questions) < 3:
            questions = self._fallback_questions(resource)

        resource.suggested_questions = questions[:3]
        resource.suggested_questions_at = datetime.now(UTC)
        self.db.commit()
        return questions[:3]

    async def _ensure_summary(self, resource: LearningResource) -> str:
        """取资源摘要；没有则现场从内容里截取一段（不调 LLM，避免连锁等待）"""
        if resource.summary:
            return resource.summary

        if resource.type == ResourceType.DOCUMENT:
            from app.models.learning import LearningPageText

            # 文档要先解析落库才有内容；解析较重，放进线程避免阻塞事件循环
            await asyncio.to_thread(ensure_page_texts, resource.id)
            rows = (
                self.db.query(LearningPageText)
                .filter(LearningPageText.resource_id == resource.id)
                .order_by(LearningPageText.page_index.asc())
                .limit(5)
                .all()
            )
            text = "\n".join(row.content or "" for row in rows)
        else:
            from app.models.learning import LearningTranscript

            rows = (
                self.db.query(LearningTranscript)
                .filter(
                    LearningTranscript.resource_id == resource.id,
                    LearningTranscript.source != TranscriptSource.LLM,
                )
                .order_by(LearningTranscript.start_ms.asc())
                .limit(60)
                .all()
            )
            if rows:
                original_lang = rows[0].language
                rows = [row for row in rows if row.language == original_lang]
            text = " ".join(row.text or "" for row in rows)

        text = (text or "").strip()
        if not text:
            return ""
        summary = text[: settings.LEARNING_SUMMARY_CHARS]
        resource.summary = summary
        self.db.commit()
        return summary

    @staticmethod
    def _fallback_questions(resource: LearningResource) -> List[str]:
        """固定模板：LLM 不可用时的兜底"""
        if resource.type == ResourceType.DOCUMENT:
            return [
                f"《{resource.title}》的背景和定位是什么？",
                "这份文档的核心观点有哪些？",
                "里面提到的关键概念怎么理解？",
            ]
        return [
            f"《{resource.title}》主要讲了什么？",
            "这个视频的核心要点有哪些？",
            "最后的结论和延伸建议是什么？",
        ]

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _save_message(
        self,
        session: LearningChatSession,
        resource_id: int,
        user_id: int,
        role: str,
        content: str,
        references: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        latency_ms: Optional[int] = None,
        error: Optional[str] = None,
    ) -> LearningChatMessage:
        row = LearningChatMessage(
            session_id=session.id,
            resource_id=resource_id,
            user_id=user_id,
            role=role,
            content=content,
            references=references,
            model=model,
            latency_ms=latency_ms,
            error=error,
        )
        self.db.add(row)
        session.message_count = (session.message_count or 0) + 1
        self.db.commit()
        self.db.refresh(row)
        return row

    @staticmethod
    def _sse_event(event: str, data: Any) -> str:
        """格式化 SSE 事件（与 chatbot 模块保持一致）"""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _with_timeout(awaitable, seconds: int):
    """给模型调用加超时，避免推荐问题卡住整个助手面板"""
    return await asyncio.wait_for(awaitable, timeout=seconds)


def _parse_questions(raw: str) -> List[str]:
    """解析模型输出：一行一个问题，容忍编号与引号"""
    questions: List[str] = []
    for line in (raw or "").splitlines():
        text = line.strip().strip("-•·").strip()
        # 只去掉 "1." "1、" 这类编号前缀；直接 lstrip 数字会误伤 "3 个要点是什么"
        text = re.sub(r"^\d+\s*[.、)）]\s*", "", text).strip().strip('"“”').strip()
        if not text:
            continue
        if len(text) > 60:
            text = text[:60]
        questions.append(text)
        if len(questions) >= 3:
            break
    return questions


def get_learning_chat_service(db: Session) -> LearningChatService:
    """问答服务工厂"""
    return LearningChatService(db)
