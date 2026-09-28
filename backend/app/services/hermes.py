"""
Hermes Agent 服务层

职责：
1. Session / Message / Run 的 CRUD（数据库操作）
2. 调用 HermesGateway 接收 SSE 事件流
3. 拼装完整 assistant 消息（累积 content + 提取工具信息）
4. 返回 Generator 供 API 层做 SSE 中继
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.hermes import (
    HermesAttachment,
    HermesMessage,
    HermesRun,
    HermesSession,
)
from app.services.attachment import AttachmentService
from app.services.hermes_gateway import HermesGateway
from app.services.hermes_skill import HermesSkillService
from app.utils.logger import logger


# ==================== SSE Event 格式化 ====================


def _sse_event(event: str, data: dict) -> str:
    """格式化 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ==================== 服务类 ====================


class HermesService:
    """
    Hermes Agent 服务

    负责 Session 管理 + SSE 中继，所有 Agent 逻辑由 Hermes API Server 完成。
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== Session CRUD ====================

    def create_session(
        self,
        user_id: int,
        title: str = "新会话",
        model: str = "",
        skills: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
    ) -> HermesSession:
        """创建新会话（可携带技能与工具偏好）"""
        session = HermesSession(
            user_id=user_id,
            title=title,
            model=model,
            skills=skills or [],
            tools=tools or [],
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update_session_config(
        self,
        session_id: str,
        user_id: int,
        model: Optional[str] = None,
        skills: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
    ) -> Optional[HermesSession]:
        """更新会话的能力配置（模型 / 技能 / 工具偏好），未传入的字段保持不变"""
        session = self.get_session(session_id, user_id)
        if not session:
            return None
        if model is not None:
            session.model = model
        if skills is not None:
            session.skills = skills
        if tools is not None:
            session.tools = tools
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_session(self, session_id: str, user_id: int) -> Optional[HermesSession]:
        """获取指定会话"""
        return (
            self.db.query(HermesSession)
            .filter(HermesSession.id == session_id, HermesSession.user_id == user_id)
            .first()
        )

    def list_sessions(self, user_id: int) -> List[HermesSession]:
        """列出用户所有会话（按更新时间倒序）"""
        return (
            self.db.query(HermesSession)
            .filter(HermesSession.user_id == user_id)
            .order_by(HermesSession.updated_at.desc())
            .all()
        )

    def delete_session(self, session_id: str, user_id: int) -> bool:
        """删除会话及关联数据"""
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def update_session_title(self, session_id: str, user_id: int, title: str) -> bool:
        """更新会话标题"""
        session = self.get_session(session_id, user_id)
        if not session:
            return False
        session.title = title
        self.db.commit()
        return True

    # ==================== Message CRUD ====================

    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tools_used: Optional[List[Dict]] = None,
        token_input: int = 0,
        token_output: int = 0,
    ) -> HermesMessage:
        """创建消息"""
        msg = HermesMessage(
            session_id=session_id,
            role=role,
            content=content,
            tools_used=tools_used or [],
            token_input=token_input,
            token_output=token_output,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def get_messages(self, session_id: str) -> List[HermesMessage]:
        """获取会话的消息列表"""
        return (
            self.db.query(HermesMessage)
            .filter(HermesMessage.session_id == session_id)
            .order_by(HermesMessage.created_at)
            .all()
        )

    def build_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        构建 OpenAI 格式的历史消息列表（截取最近 N 条）

        带附件的 user 消息会把 content 升级为 fragment 数组：
            [{"type": "text", "text": "..."},
             {"type": "image_url", "image_url": {"url": "data:..."}}]

        体积控制：只有最近 HERMES_HISTORY_IMAGE_TURNS 轮的 user 消息保留图片，
        更早的一律降级为文本占位，避免多轮带图撑爆请求体。

        Returns:
            [{"role": "...", "content": str | List[fragment]}]
        """
        messages = self.get_messages(session_id)
        recent = messages[-settings.HERMES_MAX_HISTORY_MESSAGES:]

        # 一次性取出会话附件并按 message_id 分组，避免逐条查库（N+1）
        attachments = (
            self.db.query(HermesAttachment)
            .filter(HermesAttachment.session_id == session_id)
            .order_by(HermesAttachment.created_at)
            .all()
        )
        by_message: Dict[str, List[HermesAttachment]] = {}
        for att in attachments:
            if att.message_id:
                by_message.setdefault(att.message_id, []).append(att)

        # 只有最后 N 轮的 user 消息保留图片
        user_ids = [m.id for m in recent if m.role == "user"]
        keep_image_ids = set(user_ids[-settings.HERMES_HISTORY_IMAGE_TURNS:])

        attachment_service = AttachmentService(self.db)
        result: List[Dict[str, Any]] = []
        for msg in recent:
            if msg.role not in ("user", "assistant") or not msg.content:
                continue

            atts = by_message.get(msg.id) or []
            if not atts:
                result.append({"role": msg.role, "content": msg.content})
                continue

            as_image = msg.role == "user" and msg.id in keep_image_ids
            fragments: List[Dict[str, Any]] = [{"type": "text", "text": msg.content}]
            for att in atts:
                fragment = attachment_service.to_content_fragment(att, as_image=as_image)
                if fragment:
                    fragments.append(fragment)
            result.append({"role": msg.role, "content": fragments})

        return result

    def build_system_instruction(
        self, skills: Optional[List[str]] = None, tools: Optional[List[str]] = None
    ) -> str:
        """
        拼装 system 指令（技能指令 + 工具偏好）

        Hermes 会把前端下发的 system 消息**叠加**在核心 prompt 之上，
        因此这里只做增量声明，不会削弱 agent 的内置能力。
        """
        parts: List[str] = []

        if skills:
            resolved = HermesSkillService(self.db).resolve_instructions(skills)
            for item in resolved:
                if item["instruction"]:
                    parts.append(f"【技能：{item['name']}】{item['instruction']}")
                else:
                    parts.append(f"请使用技能：{item['name']}")
            # 传入了但库中不存在的 slug，仍显式声明，保证用户意图不丢
            known = {item["name"] for item in resolved}
            unknown = [s for s in skills if s not in known]
            if unknown:
                parts.append(f"请使用以下技能：{', '.join(unknown)}")

        if tools:
            parts.append(
                "本轮请优先使用这些工具完成任务："
                + "、".join(tools)
                + "。若确有必要可使用其它工具，并说明原因。"
            )

        return "\n\n".join(parts).strip()

    def build_messages(
        self,
        session_id: str,
        skills: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        构建完整请求消息列表：可选 system 指令 + 历史消息

        无技能/工具偏好时不注入 system 消息，避免污染上下文。
        历史中带附件的消息 content 会是 fragment 数组（见 build_history）。
        """
        messages: List[Dict[str, Any]] = []
        instruction = self.build_system_instruction(skills, tools)
        if instruction:
            messages.append({"role": "system", "content": instruction})
        messages.extend(self.build_history(session_id))
        return messages

    # ==================== Run 管理 ====================

    def create_run(self, session_id: str) -> HermesRun:
        """创建运行记录"""
        run = HermesRun(session_id=session_id, status="running")
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def complete_run(
        self,
        run_id: str,
        status: str = "completed",
        tools_used: Optional[List[Dict]] = None,
        token_input: int = 0,
        token_output: int = 0,
        latency_ms: float = 0.0,
        error_message: str = "",
    ):
        """更新运行记录状态"""
        run = self.db.query(HermesRun).filter(HermesRun.id == run_id).first()
        if run:
            run.status = status
            run.tools_used = tools_used or []
            run.token_input = token_input
            run.token_output = token_output
            run.latency_ms = latency_ms
            run.error_message = error_message
            self.db.commit()

    def get_run(self, run_id: str, user_id: int) -> Optional[HermesRun]:
        """获取 run（校验会话归属，防止越权）"""
        return (
            self.db.query(HermesRun)
            .join(HermesSession, HermesRun.session_id == HermesSession.id)
            .filter(HermesRun.id == run_id, HermesSession.user_id == user_id)
            .first()
        )

    def create_run_with_external(
        self, session_id: str, external_run_id: str = "", status: str = "running"
    ) -> HermesRun:
        """创建 run 记录（可绑定 Hermes 上游 run_id，用于真正停止）"""
        run = HermesRun(
            session_id=session_id, status=status, external_run_id=external_run_id
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def attach_external_run(self, run_id: str, external_run_id: str) -> bool:
        """绑定本地 run 与上游 run_id"""
        run = self.db.query(HermesRun).filter(HermesRun.id == run_id).first()
        if not run:
            return False
        run.external_run_id = external_run_id
        self.db.commit()
        return True

    def mark_run_stopping(self, run_id: str) -> Optional[HermesRun]:
        """标记为停止中（等待上游在安全中断点退出）"""
        run = self.db.query(HermesRun).filter(HermesRun.id == run_id).first()
        if not run:
            return None
        run.status = "stopping"
        self.db.commit()
        self.db.refresh(run)
        return run

    # ==================== 核心：SSE 流式对话 ====================

    def chat_stream(
        self,
        session_id: str,
        user_message: str,
        model: str = "",
        skills: Optional[List[str]] = None,
        tools: Optional[List[str]] = None,
        attachment_ids: Optional[List[int]] = None,
    ) -> Generator[str, None, None]:
        """
        流式发送消息并返回 SSE 事件

        流程:
        1. 获取会话配置（模型 / 技能 / 工具）
        2. 保存用户消息到数据库
        3. 绑定附件到该消息（必须早于构建历史，否则 fragment 会缺失）
        4. 构建消息列表（含 system 指令 + 附件 content fragment）
        5. 创建 Run 记录
        6. 调用 Hermes API Server（流式）
        7. 产出 SSE 事件
        8. 保存助手消息到数据库
        9. 更新 Run 记录

        Args:
            skills: 本次请求选中的技能 slug；为空时回退到会话级配置
            tools: 本次请求的工具偏好；为空时回退到会话级配置
            attachment_ids: 随本条消息发送的附件 ID，需为已上传且归属本人的附件

        Yields:
            SSE 格式的事件字符串
        """
        import asyncio

        # 1. 获取 session 信息，决定模型与能力配置（user_id 也用于附件归属校验）
        session = self.db.query(HermesSession).filter(HermesSession.id == session_id).first()
        session_model = session.model if session and session.model else ""
        # 优先使用本次请求指定的模型，其次才是会话级配置
        use_model = model or session_model
        # 技能/工具同理：请求级 > 会话级
        use_skills = skills if skills is not None else (session.skills if session else []) or []
        use_tools = tools if tools is not None else (session.tools if session else []) or []

        # 2. 保存用户消息（需要拿到 id 供附件绑定）
        user_msg = self.create_message(
            session_id=session_id, role="user", content=user_message
        )

        # 3. 绑定附件到本条消息与会话
        #    必须在 build_messages 之前完成，build_history 依赖 message_id 收集附件
        if attachment_ids:
            AttachmentService(self.db).bind(
                attachment_ids,
                user_id=session.user_id if session else 0,
                session_id=session_id,
                message_id=user_msg.id,
            )

        # 4. 构建消息列表（含 system 指令 + 附件 fragment）
        history = self.build_messages(session_id, use_skills, use_tools)

        # 4. 创建 Run 记录
        run = self.create_run(session_id)

        # 5. 调用 Hermes API Server（同步包装异步）
        #    每次请求使用**独立的** gateway 实例：httpx.AsyncClient 会绑定到
        #    创建它的事件循环，而这里每次都新建 loop，复用全局单例会导致
        #    "Event loop is closed" / "attached to a different loop" 错误。
        gateway = HermesGateway()
        accumulated_content = ""
        # 工具调用按 toolCallId 索引，避免同名工具并发时串行配对出错
        tools_index: Dict[str, Dict[str, Any]] = {}
        tools_order: List[str] = []
        token_input = 0
        token_output = 0
        start_time = time.time()
        error_message = ""

        # 在同步上下文中运行异步生成器
        loop = asyncio.new_event_loop()
        try:
            agen = gateway.chat_stream(
                messages=history,
                model=use_model,
            )

            # 手动迭代异步生成器
            while True:
                try:
                    event = loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    break

                if event.event == "message_start":
                    yield _sse_event("message_start", {"session_id": session_id, "run_id": run.id})

                elif event.event == "content_delta":
                    accumulated_content += event.content
                    yield _sse_event("content_delta", {"content": event.content})

                elif event.event == "tool_start":
                    call_id = event.tool_call_id or f"_idx_{len(tools_order)}"
                    if call_id not in tools_index:
                        tools_index[call_id] = {
                            "name": event.tool_name,
                            "args": event.tool_args,
                        }
                        tools_order.append(call_id)
                    yield _sse_event("tool_start", {
                        "tool_name": event.tool_name,
                        "tool_args": event.tool_args,
                        "tool_call_id": event.tool_call_id,
                    })

                elif event.event == "tool_result":
                    call_id = event.tool_call_id or (tools_order[-1] if tools_order else "")
                    entry = tools_index.get(call_id)
                    if entry is None:
                        entry = {"name": event.tool_name, "args": ""}
                        tools_index[call_id] = entry
                        tools_order.append(call_id)
                    entry["output"] = (event.tool_output or "")[:500]
                    yield _sse_event("tool_result", {
                        "tool_name": event.tool_name,
                        "tool_output": event.tool_output,
                        "tool_call_id": event.tool_call_id,
                    })

                elif event.event == "message_end":
                    token_input = event.usage.get("prompt_tokens", 0)
                    token_output = event.usage.get("completion_tokens", 0)
                    yield _sse_event("message_end", {
                        "usage": event.usage,
                        "tools_used": [tools_index[c]["name"] for c in tools_order],
                    })

                elif event.event == "error":
                    error_message = event.error
                    yield _sse_event("error", {"message": event.error})

        except Exception as e:
            error_message = str(e)
            logger.error(f"chat_stream 异常: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)})
        finally:
            # 先关闭 HTTP 连接（必须在同一 loop 内），再关闭 loop
            try:
                loop.run_until_complete(gateway.close())
            except Exception as e:  # noqa: BLE001
                logger.warning(f"关闭 Hermes gateway 失败: {e}")
            finally:
                loop.close()

        # 6. 保存助手消息到数据库
        #    仅有工具调用而无文本时也要落库，否则整轮对话会丢失
        tools_used: List[Dict[str, Any]] = [tools_index[c] for c in tools_order]
        if accumulated_content or tools_used:
            self.create_message(
                session_id=session_id,
                role="assistant",
                content=accumulated_content,
                tools_used=tools_used,
                token_input=token_input,
                token_output=token_output,
            )

        # 7. 更新 Run 记录
        elapsed = (time.time() - start_time) * 1000
        self.complete_run(
            run_id=run.id,
            status="error" if error_message else "completed",
            tools_used=tools_used,
            token_input=token_input,
            token_output=token_output,
            latency_ms=round(elapsed, 1),
            error_message=error_message,
        )


# ==================== 工厂函数 ====================


def get_hermes_service(db: Session) -> HermesService:
    """获取 Hermes 服务实例"""
    return HermesService(db)
