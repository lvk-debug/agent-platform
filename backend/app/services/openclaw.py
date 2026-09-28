"""
工作助理 - OpenClaw 代理服务

核心架构：OpenClaw 无状态，每次请求需传入完整历史消息数组。
FastAPI 层负责消息持久化、用户隔离、任务管理。
"""

import json
import asyncio
from typing import AsyncGenerator, Optional, List, Dict, Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.openclaw import OpenClawSession, OpenClawMessage, OpenClawRun
from app.utils.logger import logger

# ==================== 全局连接池 ====================
_http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20,
        keepalive_expiry=30.0,
    ),
    timeout=httpx.Timeout(
        connect=10.0,
        read=float(settings.OPENCLAW_REQUEST_TIMEOUT),
        write=10.0,
        pool=5.0,
    ),
    verify=False,  # OpenClaw 自签名证书，禁用 SSL 验证
)


async def close_http_client():
    """应用关闭时调用"""
    await _http_client.aclose()


# ==================== 常量 ====================
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"

RUN_STATUS_PENDING = "pending"
RUN_STATUS_IN_PROGRESS = "in_progress"
RUN_STATUS_COMPLETED = "completed"
RUN_STATUS_CANCELLED = "cancelled"
RUN_STATUS_FAILED = "failed"

# SSE 事件类型
SSE_EVENT_DONE = "done"
SSE_EVENT_ERROR = "error"
SSE_EVENT_RESPONSE_CREATED = "response.created"
SSE_EVENT_RESPONSE_OUTPUT_ITEM_ADDED = "response.output_item.added"
SSE_EVENT_RESPONSE_CONTENT_PART_ADDED = "response.content_part.added"
SSE_EVENT_RESPONSE_CONTENT_PART_DONE = "response.content_part.done"
SSE_EVENT_RESPONSE_OUTPUT_ITEM_DONE = "response.output_item.done"
SSE_EVENT_RESPONSE_DONE = "response.done"


class OpenClawService:
    """
    OpenClaw 代理服务

    职责：
    - 透传 SSE 流式响应
    - 会话和消息持久化
    - 用户隔离校验
    - 任务生命周期管理
    """

    def __init__(self, db: Session):
        self.db = db

    # ==================== 会话管理 ====================

    def list_sessions(self, user_id: int) -> List[OpenClawSession]:
        """获取用户会话列表"""
        return (
            self.db.query(OpenClawSession)
            .filter(OpenClawSession.user_id == user_id)
            .order_by(OpenClawSession.updated_at.desc())
            .all()
        )

    def create_session(
        self, user_id: int, agent_id: str = "main", title: str = None
    ) -> OpenClawSession:
        """创建新会话"""
        session = OpenClawSession(
            user_id=user_id,
            agent_id=agent_id,
            title=title,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def delete_session(self, session_id: int, user_id: int) -> bool:
        """删除会话（级联删除 messages + runs）"""
        session = (
            self.db.query(OpenClawSession)
            .filter(
                OpenClawSession.id == session_id,
                OpenClawSession.user_id == user_id,
            )
            .first()
        )
        if not session:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def get_session(self, session_id: int, user_id: int) -> Optional[OpenClawSession]:
        """获取单个会话（带用户校验）"""
        return (
            self.db.query(OpenClawSession)
            .filter(
                OpenClawSession.id == session_id,
                OpenClawSession.user_id == user_id,
            )
            .first()
        )

    # ==================== 消息管理 ====================

    def get_messages(self, session_id: int, user_id: int) -> List[OpenClawMessage]:
        """获取会话消息历史（带用户校验）"""
        session = self.get_session(session_id, user_id)
        if not session:
            return []
        return (
            self.db.query(OpenClawMessage)
            .filter(OpenClawMessage.session_id == session_id)
            .order_by(OpenClawMessage.created_at)
            .all()
        )

    def save_user_message(
        self, session_id: int, content: str, run_id: str = None
    ) -> OpenClawMessage:
        """
        保存用户消息（立刻入库，不等流结束）

        content 包装为 OpenClaw 多模态格式
        """
        openclaw_content = [{"type": "output_text", "text": content}]
        msg = OpenClawMessage(
            session_id=session_id,
            role=ROLE_USER,
            content=openclaw_content,
            run_id=run_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    def save_assistant_message(
        self, session_id: int, content: Any, run_id: str = None
    ) -> OpenClawMessage:
        """保存助手消息"""
        msg = OpenClawMessage(
            session_id=session_id,
            role=ROLE_ASSISTANT,
            content=content,
            run_id=run_id,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return msg

    # ==================== 任务管理 ====================

    def create_run_placeholder(self, session_id: int, user_id: int) -> str:
        """
        创建临时 run 占位记录

        真实 runId 由 OpenClaw 返回（event:response.created），
        此时先用临时 ID 占位，收到真实 ID 后更新。
        """
        import uuid

        temp_id = f"temp_{uuid.uuid4().hex[:12]}"
        run = OpenClawRun(
            id=temp_id,
            session_id=session_id,
            user_id=user_id,
            status=RUN_STATUS_PENDING,
        )
        self.db.add(run)
        self.db.commit()
        return temp_id

    def update_run_id(self, temp_id: str, real_run_id: str) -> None:
        """收到真实 runId 后更新记录"""
        run = self.db.query(OpenClawRun).filter(OpenClawRun.id == temp_id).first()
        if run:
            # 删除临时记录，创建真实记录（主键不能直接更新）
            self.db.delete(run)
            self.db.commit()

            real_run = OpenClawRun(
                id=real_run_id,
                session_id=run.session_id,
                user_id=run.user_id,
                status=RUN_STATUS_IN_PROGRESS,
            )
            self.db.add(real_run)
            self.db.commit()

    def update_run_status(self, run_id: str, status: str, error: Any = None) -> None:
        """更新任务状态"""
        run = self.db.query(OpenClawRun).filter(OpenClawRun.id == run_id).first()
        if run:
            run.status = status
            if error:
                run.error = error
            self.db.commit()

    def check_session_running_run(self, session_id: int) -> Optional[OpenClawRun]:
        """检查 session 是否有正在运行的 run"""
        return (
            self.db.query(OpenClawRun)
            .filter(
                OpenClawRun.session_id == session_id,
                OpenClawRun.status == RUN_STATUS_IN_PROGRESS,
            )
            .first()
        )

    def cancel_run(self, run_id: str, user_id: int) -> bool:
        """
        取消任务（幂等）

        已是 cancelled/completed/failed 状态直接返回成功
        """
        run = (
            self.db.query(OpenClawRun)
            .filter(
                OpenClawRun.id == run_id,
                OpenClawRun.user_id == user_id,
            )
            .first()
        )
        if not run:
            return False

        # 幂等：已终态直接返回
        if run.status in (
            RUN_STATUS_CANCELLED,
            RUN_STATUS_COMPLETED,
            RUN_STATUS_FAILED,
        ):
            return True

        run.status = RUN_STATUS_CANCELLED
        self.db.commit()
        return True

    # ==================== 标题生成 ====================

    def should_generate_title(self, session_id: int) -> bool:
        """判断是否需要生成标题（仅第一条对话结束后执行一次）"""
        session = (
            self.db.query(OpenClawSession)
            .filter(OpenClawSession.id == session_id)
            .first()
        )
        if not session or session.title:
            return False
        msg_count = (
            self.db.query(OpenClawMessage)
            .filter(OpenClawMessage.session_id == session_id)
            .count()
        )
        # 至少有一轮完整对话（user + assistant）
        return msg_count >= 2

    def update_session_title(self, session_id: int, title: str) -> None:
        """更新会话标题"""
        session = (
            self.db.query(OpenClawSession)
            .filter(OpenClawSession.id == session_id)
            .first()
        )
        if session:
            session.title = title
            self.db.commit()

    # ==================== SSE 流式代理 ====================

    async def chat_stream(
        self,
        session_id: int,
        user_input: str,
        current_user_id: int,
        agent_id: str = None,
    ) -> AsyncGenerator[str, None]:
        """
        聊天流式代理

        核心流程：
        1. 用户校验
        2. 并发控制
        3. 立刻存 user 消息
        4. 取历史窗口
        5. 调用 OpenClaw SSE
        6. 透传事件流
        7. 流结束后存 assistant 消息
        """
        agent_id = agent_id or settings.OPENCLAW_AGENT_ID
        temp_run_id = None

        try:
            # 1. 用户校验
            session = self.get_session(session_id, current_user_id)
            if not session:
                yield f"event: error\ndata: {json.dumps({'error': '会话不存在'})}\n\n"
                return

            # 2. 并发控制：检查是否有正在运行的 run
            running_run = self.check_session_running_run(session_id)
            if running_run:
                yield f"event: error\ndata: {json.dumps({'error': '当前会话有正在运行的任务，请等待完成或取消'})}\n\n"
                return

            # 3. 立刻存 user 消息
            self.save_user_message(session_id, user_input)

            # 4. 创建 run 占位
            temp_run_id = self.create_run_placeholder(session_id, current_user_id)

            # 5. 获取上一轮 response ID（用于上下文关联）
            previous_response_id = session.previous_response_id

            # 6. 调用 OpenClaw（input 为字符串，通过 previous_response_id 关联上下文）
            payload = {
                "model": "openclaw",
                "stream": True,
                "input": user_input,
            }
            if previous_response_id:
                payload["previous_response_id"] = previous_response_id

            headers = {
                "Authorization": f"Bearer {settings.OPENCLAW_API_KEY}",
                "Content-Type": "application/json",
                "x-openclaw-agent-id": agent_id,
            }

            url = f"{settings.OPENCLAW_API_URL}/v1/responses"
            print(f"请求url: {url}")

            real_run_id = None
            assistant_content_parts = []

            async with _http_client.stream(
                "POST", url, json=payload, headers=headers
            ) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    error_msg = (
                        f"OpenClaw 返回 {response.status_code}: {error_body.decode()}"
                    )
                    logger.error(error_msg)
                    yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                    self.update_run_status(
                        temp_run_id, RUN_STATUS_FAILED, {"message": error_msg}
                    )
                    return

                # 7. 透传 SSE 事件流
                async for line in response.aiter_lines():
                    if not line:
                        continue

                    # 解析 SSE 事件
                    if line.startswith("event:"):
                        event_type = line[len("event:") :].strip()
                        yield f"{line}\n"
                    elif line.startswith("data:"):
                        data_str = line[len("data:") :].strip()
                        yield f"{line}\n\n"

                        # 处理特殊事件
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # 获取真实 runId（即 response ID）
                        if event_type == SSE_EVENT_RESPONSE_CREATED and not real_run_id:
                            real_run_id = data.get("id")
                            if real_run_id:
                                self.update_run_id(temp_run_id, real_run_id)
                                temp_run_id = None  # 已更新为真实 ID
                                # 保存到 session 供下次请求使用
                                session.previous_response_id = real_run_id
                                self.db.commit()

                        # 拼接 assistant content
                        if event_type == SSE_EVENT_RESPONSE_CONTENT_PART_DONE:
                            part = data.get("part", {})
                            if part.get("type") == "output_text":
                                assistant_content_parts.append(part.get("text", ""))

                        # 流正常结束
                        if event_type == SSE_EVENT_RESPONSE_DONE:
                            break

            # 8. 流结束 - 存 assistant 消息
            final_content = "".join(assistant_content_parts)
            if final_content:
                self.save_assistant_message(
                    session_id,
                    [{"type": "output_text", "text": final_content}],
                    run_id=real_run_id,
                )

            # 更新 run 状态
            if real_run_id:
                self.update_run_status(real_run_id, RUN_STATUS_COMPLETED)

            # 9. 尝试生成标题
            if self.should_generate_title(session_id):
                # 异步生成标题，不阻塞主流程
                try:
                    title = user_input[:50] + ("..." if len(user_input) > 50 else "")
                    self.update_session_title(session_id, title)
                except Exception as e:
                    logger.warning(f"生成会话标题失败: {e}")

        except httpx.TimeoutException:
            error_msg = "OpenClaw 请求超时"
            logger.error(error_msg)
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
            if temp_run_id:
                self.update_run_status(
                    temp_run_id, RUN_STATUS_FAILED, {"message": error_msg}
                )

        except httpx.ConnectError as e:
            error_msg = f"无法连接 OpenClaw 服务: {e}"
            logger.error(error_msg)
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
            if temp_run_id:
                self.update_run_status(
                    temp_run_id, RUN_STATUS_FAILED, {"message": error_msg}
                )

        except asyncio.CancelledError:
            # 客户端断开连接
            logger.warning(f"客户端断开连接, session={session_id}")
            if temp_run_id:
                self.update_run_status(temp_run_id, RUN_STATUS_CANCELLED)
                self.save_assistant_message(
                    session_id,
                    [{"type": "output_text", "text": "[消息已中断]"}],
                    run_id=temp_run_id,
                )

        except Exception as e:
            error_msg = f"OpenClaw 代理异常: {e}"
            logger.error(error_msg, exc_info=True)
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
            if temp_run_id:
                self.update_run_status(
                    temp_run_id, RUN_STATUS_FAILED, {"message": error_msg}
                )

    # ==================== 取消任务 ====================

    async def cancel_remote_run(self, run_id: str, user_id: int) -> bool:
        """
        取消 OpenClaw 远端任务

        幂等：已终态直接返回成功
        """
        # 本地状态校验
        if not self.cancel_run(run_id, user_id):
            return False

        # 调用远端取消接口
        try:
            url = f"{settings.OPENCLAW_API_URL}/v1/runs/{run_id}/cancel"
            headers = {
                "Authorization": f"Bearer {settings.OPENCLAW_API_KEY}",
                "Content-Type": "application/json",
            }
            response = await _http_client.post(url, headers=headers)
            return response.status_code in (200, 204, 404)  # 404 也视为成功（已结束）
        except Exception as e:
            logger.warning(f"取消远端任务失败: {e}")
            return True  # 本地已标记取消

    # ==================== 健康检查 ====================

    async def check_health(self) -> Dict[str, Any]:
        """探测 OpenClaw 服务可用性"""
        try:
            url = f"{settings.OPENCLAW_API_URL}/v1/responses"
            response = await _http_client.get(url)
            return {
                "status": "healthy",
                "openclaw_url": settings.OPENCLAW_API_URL,
                "openclaw_status": response.status_code,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "openclaw_url": settings.OPENCLAW_API_URL,
                "error": str(e),
            }


def get_openclaw_service(db: Session) -> OpenClawService:
    """获取 OpenClaw 服务实例"""
    return OpenClawService(db)
