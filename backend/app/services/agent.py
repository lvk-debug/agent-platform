"""
Agent 服务 — 使用 LangChain 的 create_agent 实现智能体编排
"""

import asyncio
import json
import re
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.app import App
from app.models.user import User
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentConfig
from app.schemas.chatbot import KnowledgeBaseConfig
from app.services.llm import LLMService
from app.services.tool_registry import ToolRegistry
from app.utils.logger import logger
from langchain.agents import create_agent, AgentState
from langchain.agents.middleware import after_model
from langgraph.runtime import Runtime
from langchain.messages import RemoveMessage

MAX_MESSAGES = 4  # 默认值，实际使用时从 config.memory_window 读取


def make_delete_old_messages(max_messages: int = MAX_MESSAGES):
    """创建可配置的中间件：裁剪历史消息，保留首尾"""

    @after_model
    def _delete_old_messages(state: AgentState, runtime: Runtime) -> dict | None:
        messages = state["messages"]
        if len(messages) > max_messages:
            tail = len(messages) - max_messages
            remove_messages = messages[3:tail]
            return {"messages": [RemoveMessage(id=m.id) for m in remove_messages]}
        return None

    return _delete_old_messages


def _get_checkpointer():
    """
    获取 LangGraph checkpointer 实例

    优先使用 SQLite checkpointer（持久化），复用现有数据库配置
    如果不可用则回退到 InMemorySaver
    """
    try:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from app.core.config import settings

        # 复用现有的数据库配置，提取数据库文件路径
        db_url = settings.DATABASE_URL
        if db_url.startswith("sqlite:///"):
            # 从 URL 提取数据库文件路径
            db_path = db_url.replace("sqlite:///", "")
            return AsyncSqliteSaver.from_conn_string(db_path)
        else:
            # 非 SQLite 数据库时回退到内存 checkpointer
            logger.warning("当前数据库不是 SQLite，使用内存 checkpointer")
            from langgraph.checkpoint.memory import InMemorySaver

            return InMemorySaver()
    except ImportError:
        logger.warning("langgraph-checkpoint-sqlite 未安装，使用内存 checkpointer")
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()


def _parse_thinking_tags(content: str) -> Tuple[str, str]:
    """
    解析内容中的思考标签，分离思考过程和最终回答

    支持格式:
    - <thinking>...</thinking>
    <think>...</think>
    - <think>...</think>

    Returns:
        (thinking, answer): 思考内容和回答内容
    """
    if not content:
        return "", ""

    # 匹配各种思考标签格式
    patterns = [
        r"<thinking>(.*?)</thinking>",  # <thinking>...</thinking>
        r"<think>(.*?)</think>",  # <think>...</think>
        r"<think>(.*?)</think>",  # <think>...</think>
    ]

    thinking_parts = []
    answer = content

    for pattern in patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        if matches:
            thinking_parts.extend(matches)
            # 从回答中移除思考标签
            answer = re.sub(pattern, "", content, flags=re.DOTALL).strip()

    thinking = "\n\n".join(thinking_parts).strip()
    return thinking, answer


class AgentService:
    """
    Agent 服务 - LangChain 的 create_agent
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def get_agent_config(self, app_id: int) -> Optional[AgentConfig]:
        """获取 Agent 配置"""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return None

        config_data = app.config or {}
        logger.info(
            f"加载 Agent 配置: app_id={app_id}, config_keys={list(config_data.keys())}"
        )

        # 检查 model_id
        model_id = config_data.get("model_id")
        logger.info(f"配置中的 model_id: {model_id}")

        # 如果有 model_id，从数据库加载模型名称
        if model_id:
            try:
                from app.models.model import Model

                model = self.db.query(Model).filter(Model.id == model_id).first()
                if model:
                    config_data["model_name"] = model.name
                    logger.info(f"加载模型名称: {model.name}")
            except Exception as e:
                logger.warning(f"加载模型名称失败: {e}")

        return AgentConfig(**config_data)

    def save_agent_config(self, app_id: int, config: AgentConfig) -> bool:
        """保存完整配置"""
        app = self.db.query(App).filter(App.id == app_id).first()
        if not app:
            return False

        config_dict = config.model_dump()
        logger.info(
            f"保存 Agent 配置: app_id={app_id}, model_id={config_dict.get('model_id')}, 工具数量: {len(config_dict.get('tools', []))}"
        )
        app.config = config_dict
        app.updated_at = datetime.utcnow()
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Agent 构建（公共逻辑）
    # ------------------------------------------------------------------

    async def _build_agent(
        self,
        config: AgentConfig,
        query: str,
        context_text: str,
        conversation_id: int,
        checkpointer=None,
    ):
        """
        构建 Agent 及执行参数（chat / chat_stream 共用）

        Args:
            checkpointer: 可选，由调用方传入（流式场景需 async with 管理生命周期）

        Returns:
            (agent, agent_config, inputs, system_prompt)
        Raises:
            ValueError: LLM 配置无效
        """
        llm = await self._get_llm(config)
        if not llm:
            raise ValueError(
                "请先在 Agent 编排页面配置模型"
                if not config.model_id
                else "模型配置无效，请检查模型 ID 和 API Key"
            )

        tools = await self._get_tools(config)
        system_prompt = self._build_system_prompt(config, context_text)

        from langchain_core.messages import HumanMessage

        # 根据配置决定是否使用 checkpointer（对话记忆）
        if config.memory_enabled:
            if checkpointer is None:
                checkpointer = _get_checkpointer()
        else:
            checkpointer = None

        # 使用配置的 memory_window 作为消息裁剪上限
        delete_middleware = make_delete_old_messages(config.memory_window)

        agent = create_agent(
            model=llm,
            tools=tools,
            middleware=[delete_middleware],
            system_prompt=system_prompt or "你是一个有用的AI助手。",
            checkpointer=checkpointer,
        )

        inputs = {"messages": [HumanMessage(content=query)]}
        agent_config = {
            "recursion_limit": config.max_iterations * 2,
            "configurable": {"thread_id": str(conversation_id)},
        }

        logger.info(
            f"Agent 就绪: tools={len(tools)}, max_iterations={config.max_iterations}, "
            f"thread_id={conversation_id}"
        )
        return agent, agent_config, inputs, system_prompt

    def _extract_result(self, result: dict) -> tuple[str, list, list]:
        """
        从 ainvoke 结果中提取 answer / intermediate_steps / thoughts
        """
        from langchain_core.messages import AIMessage, ToolMessage

        answer = ""
        intermediate_steps = []
        step_index = 0
        last_thought = ""

        for msg in result.get("messages", []):
            if isinstance(msg, AIMessage):
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        intermediate_steps.append(
                            {
                                "tool": tc.get("name", "unknown"),
                                "input": str(tc.get("args", {})),
                                "output": "",
                                "thought": last_thought,
                                "status": "running",
                                "duration": None,
                            }
                        )
                        last_thought = ""
            elif isinstance(msg, ToolMessage):
                if step_index < len(intermediate_steps):
                    intermediate_steps[step_index]["output"] = str(msg.content)
                    intermediate_steps[step_index]["status"] = "success"
                    step_index += 1
                else:
                    intermediate_steps.append(
                        {
                            "tool": msg.name or "unknown",
                            "input": "",
                            "output": str(msg.content),
                            "thought": "",
                            "status": "success",
                        }
                    )

        # 回退：取最后一条无 tool_calls 的 AIMessage
        if not answer:
            for msg in reversed(result.get("messages", [])):
                if (
                    isinstance(msg, AIMessage)
                    and msg.content
                    and not (hasattr(msg, "tool_calls") and msg.tool_calls)
                ):
                    answer = msg.content
                    break

        thoughts = [s["thought"] for s in intermediate_steps if s.get("thought")]
        return answer or "Agent 未能生成回答", intermediate_steps, thoughts

    # ------------------------------------------------------------------
    # 对话公共准备（变量替换 / 知识库 / 会话 / 消息保存）
    # ------------------------------------------------------------------

    async def _prepare_conversation(
        self,
        app_id: int,
        request: AgentChatRequest,
        user: User,
        config: AgentConfig,
    ) -> tuple[int, str, str, list]:
        """
        公共前置逻辑：变量替换、知识库检索、会话管理、保存用户消息

        Returns:
            (conversation_id, query, context_text, citations)
        """
        query = request.query
        if request.inputs:
            query = self._replace_variables(query, request.inputs, config)

        context_text = ""
        citations: list = []
        if config.knowledge_bases:
            context_text, citations = await self._retrieve_knowledge(
                config.knowledge_bases, query
            )

        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = self._create_conversation(app_id, user.id, query)

        self._save_message(conversation_id, "user", query)
        return conversation_id, query, context_text, citations

    # ------------------------------------------------------------------
    # 非流式对话
    # ------------------------------------------------------------------

    async def chat(
        self,
        app_id: int,
        request: AgentChatRequest,
        user: User,
    ) -> AgentChatResponse:
        """非流式 Agent 聊天 — ainvoke 整体返回"""
        config = self.get_agent_config(app_id)
        if not config:
            raise ValueError("Agent 配置不存在")

        logger.info(f"Agent 聊天: app_id={app_id}, model_id={config.model_id}")

        conversation_id, query, context_text, citations = (
            await self._prepare_conversation(app_id, request, user, config)
        )

        try:
            agent, agent_config, inputs, _ = await self._build_agent(
                config, query, context_text, conversation_id
            )
            result = await asyncio.wait_for(
                agent.ainvoke(inputs, config=agent_config), timeout=150
            )
            answer, intermediate_steps, thoughts = self._extract_result(result)
        except ValueError as e:
            logger.warning(f"Agent 配置错误: {e}")
            answer, intermediate_steps, thoughts = f"⚠️ {e}", [], []
        except asyncio.TimeoutError:
            logger.error("Agent 执行超时")
            answer, intermediate_steps, thoughts = (
                "⚠️ Agent 执行超时，请简化问题",
                [],
                [],
            )
        except Exception as e:
            logger.error(f"Agent 执行失败: {e}", exc_info=True)
            answer = self._generate_demo_response(query, context_text)
            intermediate_steps, thoughts = [], []

        metadata = {
            "model": config.model_name,
            "tools_used": [t.name for t in config.tools if t.enabled],
            "knowledge_context": context_text[:500] if context_text else None,
            "citations": citations or None,
            "tool_calls": intermediate_steps,
            "thoughts": thoughts,
        }
        message_id = self._save_message(conversation_id, "assistant", answer, metadata)

        return AgentChatResponse(
            answer=answer,
            conversation_id=conversation_id,
            message_id=message_id,
            intermediate_steps=intermediate_steps,
            metadata=metadata,
        )

    # ------------------------------------------------------------------
    # 流式对话
    # ------------------------------------------------------------------

    @staticmethod
    def _sse_event(event: str, data: Any) -> str:
        """格式化 SSE 事件"""
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def chat_stream(
        self,
        app_id: int,
        request: AgentChatRequest,
        user: User,
    ) -> AsyncGenerator[str, None]:
        """
        流式 Agent 聊天 — astream_events 逐 token yield SSE 事件

        事件类型: message / tool_start / tool_end / thinking / done / error
        """
        config = self.get_agent_config(app_id)
        if not config:
            yield self._sse_event("error", {"message": "Agent 配置不存在"})
            return

        logger.info(f"Agent 流式聊天: app_id={app_id}, model_id={config.model_id}")

        # 公共前置
        conversation_id, query, context_text, citations = (
            await self._prepare_conversation(app_id, request, user, config)
        )

        # 创建 Agent（checkpointer 由 async with 管理生命周期）
        try:
            from langchain_core.messages import AIMessage

            start_time = time.time()
            intermediate_steps: list = []
            final_answer = ""
            streamed_any = False

            # 根据配置决定是否创建 checkpointer
            async def _run_agent_events(agent, agent_config, inputs):
                nonlocal final_answer, streamed_any
                async for event in agent.astream_events(inputs, config=agent_config, version="v2"):
                    kind = event.get("event", "")
                    evt_data = event.get("data", {})

                    # LLM 流式输出（逐 token）
                    if kind == "on_chat_model_stream":
                        chunk = evt_data.get("chunk")
                        text = getattr(chunk, "content", "") or ""
                        if text:
                            final_answer += text
                            streamed_any = True
                            yield self._sse_event("message", {"content": text})

                    # LLM 完成（含完整响应）
                    elif kind == "on_chat_model_end":
                        msg = evt_data.get("output")
                        if isinstance(msg, AIMessage):
                            if msg.content and not final_answer:
                                final_answer = msg.content
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    tool_name = tc.get("name", "unknown")
                                    tool_input = str(tc.get("args", {}))
                                    tc_id = tc.get("id", "")
                                    intermediate_steps.append(
                                        {
                                            "tool": tool_name,
                                            "tool_call_id": tc_id,
                                            "input": tool_input,
                                            "output": "",
                                            "thought": "",
                                            "status": "running",
                                            "duration": None,
                                        }
                                    )
                                    yield self._sse_event(
                                        "tool_start",
                                        {
                                            "tool": tool_name,
                                            "tool_call_id": tc_id,
                                            "input": tool_input,
                                        },
                                    )

                    # 工具执行完成
                    elif kind == "on_tool_end":
                        tool_output = str(evt_data.get("output", ""))
                        # on_tool_end 的 data 中有 tool_call_id
                        done_tc_id = evt_data.get("tool_call_id", "")
                        for step in reversed(intermediate_steps):
                            if step["status"] == "running":
                                # 优先用 tool_call_id 精确匹配，回退到 name 匹配
                                if (
                                    done_tc_id
                                    and step.get("tool_call_id") == done_tc_id
                                ):
                                    step["output"] = tool_output
                                    step["status"] = "success"
                                    yield self._sse_event(
                                        "tool_end",
                                        {
                                            "tool": step["tool"],
                                            "tool_call_id": done_tc_id,
                                            "output": tool_output[:500],
                                            "status": "success",
                                        },
                                    )
                                    break
                                elif not done_tc_id and step["tool"] == event.get(
                                    "name", ""
                                ):
                                    step["output"] = tool_output
                                    step["status"] = "success"
                                    yield self._sse_event(
                                        "tool_end",
                                        {
                                            "tool": step["tool"],
                                            "tool_call_id": step.get(
                                                "tool_call_id", ""
                                            ),
                                            "output": tool_output[:500],
                                            "status": "success",
                                        },
                                    )
                                    break

            # 根据配置决定是否创建 checkpointer
            if config.memory_enabled:
                async with _get_checkpointer() as checkpointer:
                    agent, agent_config, inputs, _ = await self._build_agent(
                        config, query, context_text, conversation_id,
                        checkpointer=checkpointer,
                    )
                    async for event in _run_agent_events(agent, agent_config, inputs):
                        yield event
            else:
                agent, agent_config, inputs, _ = await self._build_agent(
                    config, query, context_text, conversation_id,
                )
                async for event in _run_agent_events(agent, agent_config, inputs):
                    yield event

            total_duration = int((time.time() - start_time) * 1000)
            logger.info(f"Agent 流式执行完成, 耗时: {total_duration}ms")

            if not final_answer:
                final_answer = "Agent 未能生成回答"
            if not streamed_any:
                yield self._sse_event("message", {"content": final_answer})

            metadata = {
                "model": config.model_name,
                "tools_used": [t.name for t in config.tools if t.enabled],
                "knowledge_context": context_text[:500] if context_text else None,
                "citations": citations or None,
                "tool_calls": intermediate_steps,
            }
            message_id = self._save_message(
                conversation_id, "assistant", final_answer, metadata
            )

            yield self._sse_event(
                "done",
                {
                    "answer": final_answer,
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "intermediate_steps": intermediate_steps,
                    "metadata": metadata,
                },
            )

        except ImportError as e:
            logger.error(f"langchain 导入失败: {e}")
            yield self._sse_event(
                "error", {"message": "请安装 langchain: pip install langchain"}
            )
        except Exception as e:
            logger.error(f"Agent 流式执行异常: {e}", exc_info=True)
            yield self._sse_event("error", {"message": f"Agent 执行失败: {str(e)}"})

    async def _get_llm(self, config: AgentConfig):
        """获取 LangChain LLM 实例"""
        logger.info(f"获取 LLM: model_id={config.model_id}")

        if not config.model_id:
            logger.warning("未配置 model_id")
            return None

        try:
            from app.models.model import Model

            model = self.db.query(Model).filter(Model.id == config.model_id).first()

            if not model:
                logger.warning(f"模型不存在: model_id={config.model_id}")
                return None

            if not model.provider:
                logger.warning(f"模型未关联供应商: model_id={config.model_id}")
                return None

            provider_config = model.provider
            params = config.model_parameters

            logger.info(
                f"创建 LLM: provider_type={provider_config.provider_type}, model_id={model.model_id}, api_endpoint={provider_config.api_endpoint}"
            )
            logger.info(
                f"模型参数: temperature={params.temperature}, max_tokens={params.max_tokens}"
            )

            # 根据供应商类型创建对应的 LLM
            if provider_config.provider_type == "openai":
                from langchain_openai import ChatOpenAI

                return ChatOpenAI(
                    model=model.model_id,
                    api_key=provider_config.api_key,
                    base_url=provider_config.api_endpoint,
                    temperature=params.temperature,
                    max_tokens=params.max_tokens,
                    top_p=params.top_p,
                )
            elif provider_config.provider_type == "anthropic":
                from langchain_anthropic import ChatAnthropic

                return ChatAnthropic(
                    model=model.model_id,
                    api_key=provider_config.api_key,
                    temperature=params.temperature,
                    max_tokens=params.max_tokens,
                )
            else:
                logger.warning(f"不支持的供应商类型: {provider_config.provider_type}")
                return None

        except Exception as e:
            logger.error(f"创建 LLM 实例失败: {e}", exc_info=True)
            return None

    async def _get_tools(self, config: AgentConfig) -> list:
        """
        获取 Agent 可用工具列表

        通过 ToolRegistry 统一加载，无需关心工具类型分支
        """
        if not config.tools:
            return []

        tool_ids = [t.tool_id for t in config.tools if t.enabled]
        if not tool_ids:
            return []

        knowledge_base_ids = (
            [kb.id for kb in config.knowledge_bases] if config.knowledge_bases else None
        )

        registry = ToolRegistry()
        return registry.get_tools(tool_ids, self.db, knowledge_base_ids)

    def _build_system_prompt(self, config: AgentConfig, context_text: str) -> str:
        """构建系统提示词"""
        prompt = config.prompt.system_prompt or "你是一个有用的AI助手。"

        if context_text:
            prompt += f"\n\n参考以下知识库内容回答问题：\n\n{context_text}"

        return prompt

    def _replace_variables(
        self,
        text: str,
        inputs: Dict[str, str],
        config: AgentConfig,
    ) -> str:
        """替换文本中的变量"""
        for var in config.variables:
            if var.key in inputs:
                text = text.replace("{{" + var.key + "}}", inputs[var.key])
        return text

    async def _retrieve_knowledge(
        self,
        kb_configs: List[KnowledgeBaseConfig],
        query: str,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """从知识库检索相关信息"""
        all_context = []
        all_citations = []

        for kb_config in kb_configs:
            if not kb_config.enabled:
                continue

            try:
                from app.services.knowledge import get_knowledge_service

                knowledge_service = get_knowledge_service(self.db)
                results = await knowledge_service.search(
                    kb_id=kb_config.knowledge_base_id,
                    query=query,
                    top_k=kb_config.top_k,
                    score_threshold=kb_config.score_threshold,
                )

                for result in results:
                    all_context.append(
                        f"[来源: {result.get('document_name', '未知')}]\n"
                        f"{result['content']}"
                    )
                    if kb_config.show_citation:
                        all_citations.append(
                            {
                                "knowledge_base_id": kb_config.knowledge_base_id,
                                "knowledge_base_name": kb_config.name,
                                "document_name": result.get("document_name", "未知"),
                                "content": result["content"][:200],
                                "score": round(result.get("score", 0), 4),
                            }
                        )
            except Exception as e:
                logger.warning(f"知识库 {kb_config.knowledge_base_id} 检索失败: {e}")

        context_text = "\n\n---\n\n".join(all_context) if all_context else ""
        return context_text, all_citations

    def _create_conversation(
        self, app_id: int, user_id: int, first_message: str
    ) -> int:
        """创建新会话"""
        from app.models.conversation import Conversation

        title = first_message[:20] + ("..." if len(first_message) > 20 else "")
        conversation = Conversation(
            app_id=app_id,
            user_id=user_id,
            title=title,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation.id

    def _save_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> int:
        """保存消息"""
        from app.models.conversation import Message, Conversation

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata_=metadata,
        )
        self.db.add(message)

        conversation = (
            self.db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        if conversation:
            conversation.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(message)
        return message.id

    def _generate_demo_response(self, query: str, context_text: str) -> str:
        """生成演示回复（当没有配置 LLM 时使用）"""
        if context_text:
            return f"（演示模式）根据知识库内容，关于「{query[:50]}」的信息如下：\n\n{context_text[:200]}...\n\n如需获得更准确的回答，请配置模型供应商。"
        return f"（演示模式）您问的是：「{query}」\n\n当前未配置 LLM 模型，请在「模型管理」中配置模型供应商后即可正常使用。"


def get_agent_service(db: Session) -> AgentService:
    return AgentService(db)
