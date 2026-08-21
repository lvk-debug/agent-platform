"""
Agent 服务 — 使用 LangGraph create_react_agent 实现智能体编排
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.app import App
from app.models.user import User
from app.schemas.agent import (
    AgentChatRequest,
    AgentChatResponse,
    AgentConfig,
    AgentUpdate,
)
from app.schemas.chatbot import KnowledgeBaseConfig
from app.services.llm import LLMService
from app.utils.logger import logger


class AgentService:
    """
    Agent 服务 - 使用 LangGraph create_react_agent
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
    # 对话处理 - 使用 LangGraph create_react_agent
    # ------------------------------------------------------------------

    async def chat(
        self,
        app_id: int,
        request: AgentChatRequest,
        user: User,
    ) -> AgentChatResponse:
        """
        处理 Agent 聊天请求

        使用 LangGraph 的 create_react_agent 实现工具调用循环

        流程:
        1. 获取配置
        2. 变量替换
        3. 知识库检索（如有）
        4. 创建 React Agent
        5. 执行 Agent
        6. 返回结果
        """
        config = self.get_agent_config(app_id)
        if not config:
            raise ValueError("Agent 配置不存在")

        logger.info(
            f"Agent 聊天请求: app_id={app_id}, model_id={config.model_id}, 工具数量: {len(config.tools) if config.tools else 0}"
        )

        # 1. 变量替换
        query = request.query
        if request.inputs:
            query = self._replace_variables(query, request.inputs, config)

        # 2. 知识库检索
        context_text = ""
        citations: List[Dict[str, Any]] = []
        if config.knowledge_bases:
            context_text, citations = await self._retrieve_knowledge(
                config.knowledge_bases, query
            )

        # 3. 获取或创建会话
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = self._create_conversation(app_id, user.id, query)

        # 4. 保存用户消息
        self._save_message(conversation_id, "user", query)

        # 5. 使用 LangGraph 执行 Agent
        try:
            result = await self._execute_agent(
                config=config,
                query=query,
                context_text=context_text,
                conversation_id=conversation_id,
            )
            answer = result["answer"]
            intermediate_steps = result.get("intermediate_steps", [])
            thoughts = result.get("thoughts", [])
        except ValueError as e:
            # 配置错误（如未配置模型），直接返回错误信息
            logger.warning(f"Agent 配置错误: {e}")
            answer = f"⚠️ {str(e)}"
            intermediate_steps = []
            thoughts = []
        except Exception as e:
            logger.error(f"Agent 执行失败: {e}", exc_info=True)
            answer = self._generate_demo_response(query, context_text)
            intermediate_steps = []
            thoughts = []

        # 6. 保存助手回复（包含 tool_calls 到 metadata）
        metadata = {
            "model": config.model_name,
            "tools_used": [t.name for t in config.tools if t.enabled],
            "knowledge_context": context_text[:500] if context_text else None,
            "citations": citations if citations else None,
            "tool_calls": intermediate_steps,  # 保存工具调用记录
            "thoughts": thoughts,  # 保存思考过程
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
    # 流式对话处理
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
        流式处理 Agent 聊天请求

        逐步 yield SSE 事件:
        - tool_start: 工具调用开始
        - tool_end: 工具调用完成
        - thinking: Agent 推理过程
        - message: 最终回答的文本片段
        - done: 执行完成
        - error: 错误
        """
        config = self.get_agent_config(app_id)
        if not config:
            yield self._sse_event("error", {"message": "Agent 配置不存在"})
            return

        logger.info(
            f"Agent 流式聊天请求: app_id={app_id}, model_id={config.model_id}"
        )

        # 1. 变量替换
        query = request.query
        if request.inputs:
            query = self._replace_variables(query, request.inputs, config)

        # 2. 知识库检索
        context_text = ""
        citations: List[Dict[str, Any]] = []
        if config.knowledge_bases:
            context_text, citations = await self._retrieve_knowledge(
                config.knowledge_bases, query
            )

        # 3. 获取或创建会话
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = self._create_conversation(app_id, user.id, query)

        # 4. 保存用户消息
        self._save_message(conversation_id, "user", query)

        # 5. 获取 LLM 和工具
        llm = await self._get_llm(config)
        if not llm:
            error_msg = "请先在 Agent 编排页面配置模型" if not config.model_id else "模型配置无效"
            yield self._sse_event("error", {"message": error_msg})
            return

        tools = await self._get_tools(config)
        system_prompt = self._build_system_prompt(config, context_text)

        # 6. 创建 Agent 并流式执行
        try:
            from langchain.agents import create_agent
            from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

            agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=system_prompt or "你是一个有用的AI助手。",
            )

            inputs = {"messages": [HumanMessage(content=query)]}

            logger.info(f"执行流式 LangChain Agent, 工具数: {len(tools)}")
            start_time = time.time()

            # 使用 agent.stream 流式执行
            intermediate_steps = []
            all_thoughts = []
            answer = ""

            try:
                async for event in agent.astream(inputs):
                    # 解析 Agent 执行事件
                    if isinstance(event, dict):
                        # 检查是否有 Agent 步骤
                        if "agent" in event:
                            agent_output = event["agent"]
                            if isinstance(agent_output, dict) and "messages" in agent_output:
                                for msg in agent_output["messages"]:
                                    if isinstance(msg, AIMessage):
                                        if msg.content:
                                            thought = msg.content
                                            all_thoughts.append(thought)
                                            yield self._sse_event("thinking", {"content": thought})

                                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                                            for tool_call in msg.tool_calls:
                                                tool_name = tool_call.get("name", "unknown")
                                                tool_input = str(tool_call.get("args", {}))
                                                intermediate_steps.append({
                                                    "tool": tool_name,
                                                    "input": tool_input,
                                                    "output": "",
                                                    "thought": "",
                                                    "status": "running",
                                                    "duration": None,
                                                })
                                                yield self._sse_event("tool_start", {
                                                    "tool": tool_name,
                                                    "input": tool_input,
                                                })

                        # 检查工具执行结果
                        if "tools" in event:
                            tools_output = event["tools"]
                            if isinstance(tools_output, dict) and "messages" in tools_output:
                                for msg in tools_output["messages"]:
                                    if isinstance(msg, ToolMessage):
                                        step_idx = len(intermediate_steps) - 1
                                        if step_idx >= 0:
                                            intermediate_steps[step_idx]["output"] = str(msg.content)
                                            intermediate_steps[step_idx]["status"] = "success"
                                            yield self._sse_event("tool_end", {
                                                "tool": intermediate_steps[step_idx]["tool"],
                                                "output": str(msg.content)[:500],
                                                "status": "success",
                                            })

            except asyncio.TimeoutError:
                logger.error("Agent 流式执行超时")
                yield self._sse_event("error", {"message": "Agent 执行超时，请简化问题"})
                return

            total_duration = int((time.time() - start_time) * 1000)
            logger.info(f"Agent 流式执行完成, 耗时: {total_duration}ms")

            # 7. 获取最终回答 - 逐字流式输出
            # 从最后的 AIMessage 提取最终回答
            final_answer = answer or "Agent 未能生成回答"

            # 使用 LLM 的 stream 逐字输出最终回答
            if config.model_id:
                try:
                    from app.models.model import Model
                    model = self.db.query(Model).filter(Model.id == config.model_id).first()
                    if model and model.provider:
                        llm_service = LLMService()
                        await llm_service.register_provider(
                            provider_type=model.provider.provider_type,
                            api_key=model.provider.api_key,
                            api_endpoint=model.provider.api_endpoint,
                        )
                        params = config.model_parameters

                        # 构建包含历史的消息用于生成最终回答
                        gen_messages = [
                            {"role": "system", "content": system_prompt or "你是一个有用的AI助手。"},
                            {"role": "user", "content": query},
                        ]

                        # 流式输出
                        final_answer = ""
                        async for chunk in llm_service.stream_chat(
                            messages=gen_messages,
                            model=model.model_id,
                            provider=model.provider.provider_type,
                            temperature=params.temperature if params else 0.7,
                            max_tokens=params.max_tokens if params else 2048,
                        ):
                            final_answer += chunk
                            yield self._sse_event("message", {"content": chunk})
                except Exception as e:
                    logger.warning(f"流式生成最终回答失败: {e}")
                    # 降级：一次性输出
                    yield self._sse_event("message", {"content": final_answer})
            else:
                yield self._sse_event("message", {"content": final_answer})

            # 8. 保存助手回复
            metadata = {
                "model": config.model_name,
                "tools_used": [t.name for t in config.tools if t.enabled],
                "knowledge_context": context_text[:500] if context_text else None,
                "citations": citations if citations else None,
                "tool_calls": intermediate_steps,
                "thoughts": all_thoughts,
            }
            message_id = self._save_message(conversation_id, "assistant", final_answer, metadata)

            # 9. 发送完成事件
            yield self._sse_event("done", {
                "answer": final_answer,
                "conversation_id": conversation_id,
                "message_id": message_id,
                "intermediate_steps": intermediate_steps,
                "metadata": metadata,
            })

        except ImportError as e:
            logger.error(f"langchain 导入失败: {e}")
            yield self._sse_event("error", {"message": "请安装 langchain: pip install langchain"})
        except Exception as e:
            logger.error(f"Agent 流式执行异常: {e}", exc_info=True)
            yield self._sse_event("error", {"message": f"Agent 执行失败: {str(e)}"})

    async def _execute_agent(
        self,
        config: AgentConfig,
        query: str,
        context_text: str,
        conversation_id: int,
    ) -> Dict[str, Any]:
        """
        使用 langchain create_agent 执行 Agent

        React Agent 会自动循环调用工具直到得到最终答案
        """
        import time

        # 获取 LLM 模型
        llm = await self._get_llm(config)
        if not llm:
            if not config.model_id:
                raise ValueError("请先在 Agent 编排页面配置模型")
            else:
                raise ValueError("模型配置无效，请检查模型 ID 和 API Key")

        # 获取工具列表
        tools = await self._get_tools(config)

        # 构建系统提示词
        system_prompt = self._build_system_prompt(config, context_text)

        try:
            from langchain.agents import create_agent
            from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

            # 创建 Agent
            agent = create_agent(
                model=llm,
                tools=tools,
                system_prompt=(
                    system_prompt if system_prompt else "你是一个有用的AI助手。"
                ),
            )

            # 构建输入
            from langchain_core.messages import HumanMessage

            inputs = {"messages": [HumanMessage(content=query)]}

            # 执行 Agent
            logger.info(f"执行 LangChain Agent, 工具数: {len(tools)}")
            start_time = time.time()
            try:
                result = await asyncio.wait_for(agent.ainvoke(inputs), timeout=150)  # 2.5分钟超时
            except asyncio.TimeoutError:
                total_duration = int((time.time() - start_time) * 1000)
                logger.error(f"Agent 执行超时: {total_duration}ms")
                return {
                    "answer": "⚠️ Agent 执行超时，请尝试简化问题或减少工具数量。",
                    "intermediate_steps": [],
                    "total_duration": total_duration,
                }
            total_duration = int((time.time() - start_time) * 1000)
            logger.info(f"Agent 执行完成, 耗时: {total_duration}ms")

            # 提取最终回答和工具调用记录
            answer = ""
            intermediate_steps = []
            step_index = 0
            last_thought = ""  # 保存最近的思考内容

            if "messages" in result:
                for msg in result["messages"]:
                    if isinstance(msg, AIMessage):
                        # AIMessage 的 content 通常包含 Agent 的思考过程
                        if msg.content:
                            last_thought = msg.content
                        answer = msg.content
                        # 检查是否有工具调用
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            for tool_call in msg.tool_calls:
                                intermediate_steps.append(
                                    {
                                        "tool": tool_call.get("name", "unknown"),
                                        "input": str(tool_call.get("args", {})),
                                        "output": "",
                                        "thought": last_thought,  # 使用 AIMessage 的 content 作为思考
                                        "status": "running",
                                        "duration": None,
                                    }
                                )
                                last_thought = ""  # 清空，避免重复使用
                    elif isinstance(msg, ToolMessage):
                        # 更新对应工具调用的输出
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

            # 收集所有的思考过程
            all_thoughts = []
            for step in intermediate_steps:
                if step.get("thought"):
                    all_thoughts.append(step["thought"])

            return {
                "answer": answer or "Agent 未能生成回答",
                "intermediate_steps": intermediate_steps,
                "total_duration": total_duration,
                "thoughts": all_thoughts,  # 所有思考过程
            }

        except ImportError as e:
            logger.error(f"langchain 导入失败: {e}")
            raise ValueError("请安装 langchain: pip install langchain")
        except Exception as e:
            logger.error(f"langchain Agent 执行异常: {e}", exc_info=True)
            raise

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

        将数据库中的工具配置转换为 LangChain Tool
        """
        tools = []
        if not config.tools:
            return tools

        for tool_config in config.tools:
            if not tool_config.enabled:
                continue

            try:
                from app.models.tool import Tool

                db_tool = (
                    self.db.query(Tool).filter(Tool.id == tool_config.tool_id).first()
                )
                if not db_tool:
                    logger.warning(f"工具不存在: tool_id={tool_config.tool_id}")
                    continue

                logger.info(
                    f"加载工具: id={db_tool.id}, name={db_tool.name}, type={db_tool.tool_type}"
                )

                # 根据工具类型创建 LangChain Tool
                langchain_tool = self._create_langchain_tool(
                    db_tool, tool_config.config
                )
                if langchain_tool:
                    tools.append(langchain_tool)
                    logger.info(f"工具加载成功: {db_tool.name}")
            except Exception as e:
                logger.warning(f"加载工具 {tool_config.tool_id} 失败: {e}")

        return tools

    def _create_langchain_tool(self, db_tool, tool_config: Optional[Dict] = None):
        """
        将数据库工具转换为 LangChain Tool

        支持内置工具和 API 工具
        """
        from langchain_core.tools import tool as tool_decorator

        # 内置工具示例：搜索、计算等
        if db_tool.tool_type == "builtin":
            if db_tool.name == "web_search":

                @tool_decorator
                def search_tool(query: str) -> str:
                    """使用 Tavily 搜索互联网获取信息。输入应该是搜索查询字符串。"""
                    try:
                        from tavily import TavilyClient

                        api_key = settings.TAVILY_API_KEY
                        if not api_key:
                            return "搜索失败：未配置 TAVILY_API_KEY，请在环境变量或工具配置中设置"

                        client = TavilyClient(api_key=api_key)
                        response = client.search(
                            query=query, max_results=5, search_depth="advanced"
                        )

                        results = []
                        for i, result in enumerate(response.get("results", [])[:5], 1):
                            title = result.get("title", "无标题")
                            url = result.get("url", "")
                            content = result.get("content", "")[:300]
                            results.append(
                                f"[{i}] {title}\n    链接: {url}\n    摘要: {content}"
                            )

                        if results:
                            return (
                                f"搜索结果（共 {len(results)} 条）：\n\n"
                                + "\n\n".join(results)
                            )
                        else:
                            return f"未找到与 '{query}' 相关的结果"

                    except Exception as e:
                        logger.error(f"Tavily 搜索失败: {e}")
                        return f"搜索出错: {str(e)}"

                return search_tool

            elif db_tool.name == "web_browse":

                @tool_decorator
                def web_scraper(url: str) -> str:
                    """抓取并读取网页内容。输入应该是完整的 URL 地址。"""
                    try:
                        import httpx
                        from bs4 import BeautifulSoup

                        # 设置请求头，模拟浏览器
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        }

                        with httpx.Client(
                            follow_redirects=True, timeout=15.0
                        ) as client:
                            response = client.get(url, headers=headers)
                            response.raise_for_status()

                        # 解析 HTML
                        soup = BeautifulSoup(response.text, "html.parser")

                        # 移除 script 和 style 标签
                        for tag in soup(["script", "style", "nav", "footer", "header"]):
                            tag.decompose()

                        # 提取主要文本
                        text = soup.get_text(separator="\n", strip=True)

                        # 清理多余空行
                        lines = [
                            line.strip() for line in text.splitlines() if line.strip()
                        ]
                        text = "\n".join(lines)

                        # 限制长度
                        if len(text) > 3000:
                            text = (
                                text[:3000]
                                + "\n\n[内容已截断，共 "
                                + str(len(text))
                                + " 字符]"
                            )

                        title = soup.title.string if soup.title else "无标题"
                        return f"网页标题: {title}\n\n内容:\n{text}"

                    except httpx.TimeoutException:
                        return f"抓取超时: {url}"
                    except httpx.HTTPStatusError as e:
                        return f"HTTP 错误 {e.response.status_code}: {url}"
                    except Exception as e:
                        logger.error(f"网页抓取失败: {e}")
                        return f"抓取出错: {str(e)}"

                return web_scraper

            elif db_tool.name == "code_interpreter":

                @tool_decorator
                def code_interpreter(code: str) -> str:
                    """执行 Python 代码并返回结果。输入应该是 Python 代码字符串。"""
                    try:
                        import io
                        import sys
                        from contextlib import redirect_stdout

                        # 安全执行环境
                        env = {"__builtins__": __builtins__}
                        stdout_capture = io.StringIO()

                        with redirect_stdout(stdout_capture):
                            exec(code, env)

                        output = stdout_capture.getvalue()
                        return output if output else "代码执行成功（无输出）"

                    except Exception as e:
                        return f"代码执行错误: {str(e)}"

                return code_interpreter

            elif db_tool.name == "knowledge_retrieval":

                @tool_decorator
                def knowledge_search(query: str) -> str:
                    """在知识库中搜索相关信息。输入应该是搜索查询字符串。"""
                    # 这个工具在 Agent 执行时会通过知识库检索单独处理
                    return f"知识库检索: 正在搜索 '{query}' 相关内容..."

                return knowledge_search

            elif db_tool.name == "calculator":

                @tool_decorator
                def calculator_tool(expression: str) -> str:
                    """计算数学表达式。输入应该是数学表达式字符串。"""
                    try:
                        # 安全的数学计算
                        import ast
                        import operator

                        allowed_ops = {
                            ast.Add: operator.add,
                            ast.Sub: operator.sub,
                            ast.Mult: operator.mul,
                            ast.Div: operator.truediv,
                            ast.Pow: operator.pow,
                            ast.USub: operator.neg,
                        }

                        def safe_eval(node):
                            if isinstance(node, ast.Expression):
                                return safe_eval(node.body)
                            elif isinstance(node, ast.Constant):
                                return node.value
                            elif isinstance(node, ast.BinOp):
                                left = safe_eval(node.left)
                                right = safe_eval(node.right)
                                return allowed_ops[type(node.op)](left, right)
                            elif isinstance(node, ast.UnaryOp):
                                return allowed_ops[type(node.op)](
                                    safe_eval(node.operand)
                                )
                            else:
                                raise ValueError(f"不支持的表达式类型: {type(node)}")

                        tree = ast.parse(expression, mode="eval")
                        result = safe_eval(tree)
                        return str(result)
                    except Exception as e:
                        return f"计算错误: {e}"

                return calculator_tool

        # API/插件工具
        elif db_tool.tool_type in ("plugin", "mcp"):

            @tool_decorator
            def api_tool(query: str) -> str:
                """调用外部 API 工具"""
                # TODO: 实际实现 API 调用逻辑
                return f"API 工具 '{db_tool.name}' 调用结果: 处理查询 '{query}'"

            return api_tool

        return None

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

    def _save_message(self, conversation_id: int, role: str, content: str, metadata: Optional[Dict] = None) -> int:
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
