"""
工作流服务 — 基于 LangGraph 的工作流执行引擎 + 配置管理
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Literal, AsyncGenerator

from sqlalchemy.orm import Session

from app.models.app import App
from app.models.workflow import Workflow, WorkflowRun
from app.schemas.workflow import (
    DSLData,
    DSLExportResponse,
    DSLImportRequest,
    WorkflowConfig,
    WorkflowGraph,
    WorkflowNode,
    WorkflowEdge,
)
from app.utils.logger import logger

# ------------------------------------------------------------------
# 共用：LLM 节点执行逻辑
# ------------------------------------------------------------------


async def execute_llm_node(
    *,
    db: Session,
    model_id: int,
    prompt: str,
    user_message: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
    top_p: float = 1.0,
    output_type: str = "text",
    output_schema: Any = None,
    output_variables: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    统一的 LLM 节点执行逻辑，供 /llm-run 和 /run 共用。

    Returns:
        {
            "content": str,
            "reasoning_content": str | None,
            "usage": dict,
            "model": str,
            "structured_output": dict | None,
            "node_output": dict,       # 供工作流写入 node_outputs
        }
    """
    import re
    from app.services.llm import LLMService
    from app.models.model import Model

    # 防御性处理 None 值
    prompt = prompt or ""
    user_message = user_message or ""

    # 结构化输出：将 schema 指令拼接到 user_message 前面
    if output_type == "structured" and output_schema:
        if isinstance(output_schema, str):
            try:
                schema_obj = json.loads(output_schema)
            except Exception:
                schema_obj = output_schema
        else:
            schema_obj = output_schema
        schema_str = (
            json.dumps(schema_obj, ensure_ascii=False, indent=2)
            if isinstance(schema_obj, (dict, list))
            else str(schema_obj)
        )
        schema_instruction = (
            "请严格按照以下 JSON Schema 格式输出，不要输出任何其他内容：\n"
            f"```json\n{schema_str}\n```\n\n"
        )
        user_message = schema_instruction + user_message

    # 构建消息
    messages: List[Dict[str, str]] = []
    if prompt.strip():
        messages.append({"role": "system", "content": prompt})
    messages.append({"role": "user", "content": user_message})

    # 查找模型
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model or not model.provider:
        raise ValueError("模型不存在或未配置供应商")

    provider_config = model.provider
    llm_service = LLMService()
    await llm_service.register_provider(
        provider_type=provider_config.provider_type,
        api_key=provider_config.api_key,
        api_endpoint=provider_config.api_endpoint,
    )

    response = await llm_service.chat(
        messages=messages,
        model=model.model_id,
        provider=provider_config.provider_type,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
    result_text = response.get("content", "")
    reasoning_content = response.get("reasoning_content")
    usage = response.get("tokens_used", {})

    # 结构化输出解析
    structured = None
    node_output: Dict[str, Any] = {}

    if output_type == "structured" and output_variables:
        try:
            parsed = None
            try:
                parsed = json.loads(result_text)
            except json.JSONDecodeError:
                json_match = re.search(
                    r"```(?:json)?\s*\n?(.*?)\n?```", result_text, re.DOTALL
                )
                if json_match:
                    parsed = json.loads(json_match.group(1))
            if parsed and isinstance(parsed, dict):
                structured = {}
                for var in output_variables:
                    name = var.get("name", "") if isinstance(var, dict) else getattr(var, "name", "")
                    if name and name in parsed:
                        structured[name] = parsed[name]
                        node_output[name] = parsed[name]
                node_output["output"] = result_text
            else:
                node_output["output"] = result_text
        except Exception:
            node_output["output"] = result_text
    else:
        node_output["output"] = result_text

    if reasoning_content:
        node_output["reasoning_content"] = reasoning_content
    if usage:
        node_output["usage"] = usage

    return {
        "content": result_text,
        "reasoning_content": reasoning_content,
        "usage": usage,
        "model": response.get("model"),
        "structured_output": structured,
        "node_output": node_output,
    }


# ------------------------------------------------------------------
# LangGraph 导入
# ------------------------------------------------------------------
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, Annotated
import operator

# ------------------------------------------------------------------
# LangGraph State 定义
# ------------------------------------------------------------------


class WorkflowState(TypedDict):
    """工作流执行状态"""

    # 用户输入
    inputs: Dict[str, Any]
    # 各节点输出（or reducer 自动合并字典）
    node_outputs: Annotated[Dict[str, Any], operator.or_]
    # 执行日志（add reducer 自动追加列表）
    execution_log: Annotated[List[Dict[str, Any]], operator.add]


# ------------------------------------------------------------------
# 节点工厂
# ------------------------------------------------------------------


def _make_start_node(node_id: str):
    """开始节点：透传 inputs 到 node_outputs"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[Start] node={node_id}")
        return {
            "node_outputs": {node_id: state["inputs"]},
            "execution_log": [
                {
                    "node_id": node_id,
                    "type": "start",
                    "status": "done",
                    "ts": datetime.utcnow().isoformat(),
                }
            ],
        }

    return _run


def _make_end_node(node_id: str, output_keys: Optional[List[str]] = None):
    """结束节点：收集上游输出作为最终结果"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[End] node={node_id}, output_keys={output_keys}")
        # 收集所有上游输出
        all_outputs = dict(state["node_outputs"])
        if output_keys:
            final = {k: all_outputs.get(k) for k in output_keys}
        else:
            # 取最后一个节点的输出
            final = list(all_outputs.values())[-1] if all_outputs else {}
        return {
            "node_outputs": {node_id: final},
            "execution_log": [
                {
                    "node_id": node_id,
                    "type": "end",
                    "status": "done",
                    "ts": datetime.utcnow().isoformat(),
                }
            ],
        }

    return _run


def _make_llm_node(node_id: str, config: Dict[str, Any], db: Session):
    """LLM 节点：调用 LLM 服务"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[LLM] node={node_id}")
        try:
            prompt_template = config.get("prompt") or ""
            user_message_template = config.get("user_message") or ""
            model_id = config.get("model_id")
            temperature = config.get("temperature") or 0.7
            max_tokens = config.get("max_tokens") or 2048
            top_p = config.get("top_p") or 1.0
            output_type = config.get("output_type") or "text"
            output_schema = config.get("output_schema")
            output_variables = config.get("output_variables") or []

            # 变量替换
            merged = _merge_outputs(state)
            prompt = _replace_vars(prompt_template, merged) or ""
            user_message = _replace_vars(user_message_template, merged) or ""

            if not model_id:
                return {
                    "node_outputs": {node_id: {"output": "[LLM 模型未配置]"}},
                    "execution_log": [{"node_id": node_id, "type": "llm", "status": "error", "error": "no model_id", "ts": datetime.utcnow().isoformat()}],
                }

            result = await execute_llm_node(
                db=db,
                model_id=model_id,
                prompt=prompt,
                user_message=user_message,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                output_type=output_type,
                output_schema=output_schema,
                output_variables=output_variables,
            )

            return {
                "node_outputs": {node_id: result["node_output"]},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "llm",
                        "status": "done",
                        "output_len": len(result["content"]),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        except Exception as e:
            logger.error(f"[LLM] node={node_id} error: {e}", exc_info=True)
            return {
                "node_outputs": {
                    node_id: {"output": f"[LLM 错误] {e}"}
                },
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "llm",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_llm_node_streaming(
    node_id: str,
    config: Dict[str, Any],
    db: Session,
    token_queue: asyncio.Queue,
):
    """LLM 节点（流式版本）：逐 token 推送到 token_queue"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[LLM-streaming] node={node_id}")
        try:
            prompt_template = config.get("prompt") or ""
            user_message_template = config.get("user_message") or ""
            model_id = config.get("model_id")
            temperature = config.get("temperature") or 0.7
            max_tokens = config.get("max_tokens") or 2048
            top_p = config.get("top_p") or 1.0
            output_type = config.get("output_type") or "text"
            output_schema = config.get("output_schema")
            output_variables = config.get("output_variables") or []

            merged = _merge_outputs(state)
            prompt = _replace_vars(prompt_template, merged) or ""
            user_message = _replace_vars(user_message_template, merged) or ""

            if not model_id:
                return {
                    "node_outputs": {node_id: {"output": "[LLM 模型未配置]"}},
                    "execution_log": [{"node_id": node_id, "type": "llm", "status": "error", "error": "no model_id", "ts": datetime.utcnow().isoformat()}],
                }

            # 结构化输出：拼接 schema 指令
            if output_type == "structured" and output_schema:
                if isinstance(output_schema, str):
                    try:
                        schema_obj = json.loads(output_schema)
                    except Exception:
                        schema_obj = output_schema
                else:
                    schema_obj = output_schema
                schema_str = (
                    json.dumps(schema_obj, ensure_ascii=False, indent=2)
                    if isinstance(schema_obj, (dict, list))
                    else str(schema_obj)
                )
                schema_instruction = (
                    "请严格按照以下 JSON Schema 格式输出，不要输出任何其他内容：\n"
                    f"```json\n{schema_str}\n```\n\n"
                )
                user_message = schema_instruction + user_message

            # 构建消息
            messages: List[Dict[str, str]] = []
            if prompt.strip():
                messages.append({"role": "system", "content": prompt})
            messages.append({"role": "user", "content": user_message})

            # 查找模型
            from app.models.model import Model
            model = db.query(Model).filter(Model.id == model_id).first()
            if not model or not model.provider:
                raise ValueError("模型不存在或未配置供应商")

            provider_config = model.provider
            from app.services.llm import LLMService
            llm_service = LLMService()
            await llm_service.register_provider(
                provider_type=provider_config.provider_type,
                api_key=provider_config.api_key,
                api_endpoint=provider_config.api_endpoint,
            )

            # 流式调用，逐 token 推送到队列
            full_content = ""
            async for chunk in llm_service.stream_chat(
                messages=messages,
                model=model.model_id,
                provider=provider_config.provider_type,
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            ):
                full_content += chunk
                await token_queue.put({"event": "llm_token", "data": {"node_id": node_id, "token": chunk}})

            # 结构化输出解析
            node_output: Dict[str, Any] = {}
            if output_type == "structured" and output_variables:
                import re
                try:
                    parsed = None
                    try:
                        parsed = json.loads(full_content)
                    except json.JSONDecodeError:
                        json_match = re.search(
                            r"```(?:json)?\s*\n?(.*?)\n?```", full_content, re.DOTALL
                        )
                        if json_match:
                            parsed = json.loads(json_match.group(1))
                    if parsed and isinstance(parsed, dict):
                        for var in output_variables:
                            name = var.get("name", "") if isinstance(var, dict) else getattr(var, "name", "")
                            if name and name in parsed:
                                node_output[name] = parsed[name]
                        node_output["output"] = full_content
                    else:
                        node_output["output"] = full_content
                except Exception:
                    node_output["output"] = full_content
            else:
                node_output["output"] = full_content

            return {
                "node_outputs": {node_id: node_output},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "llm",
                        "status": "done",
                        "output_len": len(full_content),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        except Exception as e:
            logger.error(f"[LLM-streaming] node={node_id} error: {e}", exc_info=True)
            return {
                "node_outputs": {node_id: {"output": f"[LLM 错误] {e}"}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "llm",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_knowledge_node(node_id: str, config: Dict[str, Any], db: Session):
    """知识库检索节点"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[Knowledge] node={node_id}")
        try:
            from app.services.knowledge import get_knowledge_service

            # 支持 knowledge_base_ids (数组) 和 knowledge_base_id (单个)
            kb_ids = config.get("knowledge_base_ids") or []
            if not kb_ids:
                single = config.get("knowledge_base_id")
                if single:
                    kb_ids = [single]
            top_k = config.get("top_k", 5)
            score_threshold = config.get("score_threshold", 0.5)
            query_key = config.get("query_key", "query")
            output_key = config.get("output_key", "documents")
            rerank_enabled = config.get("rerank_enabled", False)
            rerank_top_k = config.get("rerank_top_k", 3)

            merged = _merge_outputs(state)

            # 优先从 query_variable（PromptEditor 存储的模板文本）获取，替换变量
            # 纯变量引用（如 {{start.query}}）直接返回原始值（支持数组）
            query_variable = config.get("query_variable", "")
            if query_variable:
                raw_query = _resolve_var_template(query_variable, merged)
            else:
                raw_query = merged.get(query_key, "")

            # 支持数组查询：拆分为多个 query
            if isinstance(raw_query, list):
                queries = [str(q) for q in raw_query if q]
            else:
                queries = [str(raw_query)]

            if not kb_ids or not any(queries):
                return {
                    "node_outputs": {node_id: {output_key: [], "query": raw_query}},
                    "execution_log": [
                        {
                            "node_id": node_id,
                            "type": "knowledge",
                            "status": "skipped",
                            "reason": "no kb_id or empty query",
                            "ts": datetime.utcnow().isoformat(),
                        }
                    ],
                }

            knowledge_service = get_knowledge_service(db)

            # 按 (kb_id, query) 组合检索，合并去重
            all_results: List[Dict[str, Any]] = []
            seen_contents: set = set()
            for kb_id in kb_ids:
                for query in queries:
                    if not query.strip():
                        continue
                    results = await knowledge_service.search(
                        kb_id=kb_id,
                        query=query,
                        top_k=top_k,
                        score_threshold=score_threshold,
                    )
                    for r in results:
                        content = r.get("content", "")
                        if content not in seen_contents:
                            seen_contents.add(content)
                            all_results.append(r)

            # 重排序（如果启用）
            if rerank_enabled and all_results:
                try:
                    from app.services.reranker import get_reranker_service

                    reranker = get_reranker_service()
                    logger.info(
                        f"[Knowledge] node={node_id} 启用重排序, 原始结果: {len(all_results)}, top_k: {rerank_top_k}"
                    )
                    # 用第一个 query 做重排序的参考
                    all_results = await reranker.rerank(
                        query=queries[0],
                        documents=all_results,
                        top_k=rerank_top_k,
                    )
                    logger.info(
                        f"[Knowledge] node={node_id} 重排序完成, 结果数: {len(all_results)}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[Knowledge] node={node_id} 重排序失败，使用原始结果: {e}",
                        exc_info=True,
                    )

            # 最终截断到 top_k
            all_results = all_results[:top_k]
            print(f'all_results: {all_results}')
            return {
                "node_outputs": {
                    node_id: {output_key: all_results, "query": raw_query}
                },
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "knowledge",
                        "status": "done",
                        "results_count": len(all_results),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        except Exception as e:
            logger.error(f"[Knowledge] node={node_id} error: {e}", exc_info=True)
            return {
                "node_outputs": {node_id: {config.get("output_key", "documents"): []}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "knowledge",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_condition_router(
    node_id: str, config: Dict[str, Any], edges: List[Dict[str, str]]
):
    """条件路由函数：根据条件评估返回分支名"""
    branches = config.get("branches", [])

    def _route(state: WorkflowState) -> str:
        logger.info(f"[Condition] node={node_id}, branches={len(branches)}")
        merged = _merge_outputs(state)

        for branch in branches:
            var_name = branch.get("variable", "")
            op = branch.get("operator", "default")
            value = branch.get("value", "")
            branch_name = branch.get("branch", "__end__")

            if op == "default":
                logger.info(
                    f"[Condition] node={node_id} → default branch: {branch_name}"
                )
                return branch_name

            var_value = str(merged.get(var_name, ""))

            if op == "contains" and value in var_value:
                logger.info(f"[Condition] node={node_id} → branch: {branch_name}")
                return branch_name
            elif op == "equals" and var_value == value:
                logger.info(f"[Condition] node={node_id} → branch: {branch_name}")
                return branch_name
            elif op == "not_contains" and value not in var_value:
                logger.info(f"[Condition] node={node_id} → branch: {branch_name}")
                return branch_name
            elif op == "gt":
                try:
                    if float(var_value) > float(value):
                        return branch_name
                except ValueError:
                    pass
            elif op == "lt":
                try:
                    if float(var_value) < float(value):
                        return branch_name
                except ValueError:
                    pass

        # 没有匹配的分支，走 default 或结束
        for branch in branches:
            if branch.get("operator") == "default":
                return branch.get("branch", "__end__")

        return "__end__"

    return _route


def _make_code_node(node_id: str, config: Dict[str, Any]):
    """代码执行节点（受限沙箱）"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[Code] node={node_id}")
        code = config.get("code", "")
        output_key = config.get("output_key", "output")

        merged = _merge_outputs(state)

        try:
            # 受限沙箱：只暴露 inputs 和 node_outputs
            sandbox = {
                "inputs": state.get("inputs", {}),
                "node_outputs": state.get("node_outputs", {}),
                "merged": merged,
            }
            exec(code, {"__builtins__": {}}, sandbox)
            result = sandbox.get(
                "result", sandbox.get(output_key, "代码未设置 result 变量")
            )

            return {
                "node_outputs": {node_id: {output_key: result}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "code",
                        "status": "done",
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        except Exception as e:
            logger.error(f"[Code] node={node_id} error: {e}", exc_info=True)
            return {
                "node_outputs": {node_id: {output_key: f"[代码执行错误] {e}"}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "code",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_http_node(node_id: str, config: Dict[str, Any]):
    """HTTP 请求节点"""

    async def _run(state: WorkflowState) -> dict:
        import httpx

        logger.info(f"[HTTP] node={node_id}")

        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body")
        timeout = config.get("timeout", 30)
        output_key = config.get("output_key", "response")

        merged = _merge_outputs(state)

        # URL 变量替换
        url = _replace_vars(url, merged)
        # Body 变量替换
        if isinstance(body, str):
            body = _replace_vars(body, merged)

        try:
            from app.services.llm import _http_client as http_client

            kwargs = {"headers": headers, "timeout": float(timeout)}
            if method == "GET":
                resp = await http_client.get(url, **kwargs)
            elif method == "POST":
                resp = await http_client.post(url, json=body, **kwargs)
            elif method == "PUT":
                resp = await http_client.put(url, json=body, **kwargs)
            elif method == "DELETE":
                resp = await http_client.delete(url, **kwargs)
            else:
                raise ValueError(f"不支持的 HTTP 方法: {method}")

            content_type = resp.headers.get("content-type", "")
            if "application/json" in content_type:
                resp_body = resp.json()
            else:
                resp_body = resp.text

                result = {
                    "status_code": resp.status_code,
                    "body": resp_body,
                }
                return {
                    "node_outputs": {node_id: {output_key: result}},
                    "execution_log": [
                        {
                            "node_id": node_id,
                            "type": "http",
                            "status": "done",
                            "status_code": resp.status_code,
                            "ts": datetime.utcnow().isoformat(),
                        }
                    ],
                }
        except Exception as e:
            logger.error(f"[HTTP] node={node_id} error: {e}", exc_info=True)
            return {
                "node_outputs": {node_id: {output_key: {"error": str(e)}}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "http",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_tool_node(node_id: str, config: Dict[str, Any], db: Session):
    """工具执行节点 — 通过 ToolExecutor 执行实际工具调用"""

    async def _run(state: WorkflowState) -> dict:
        from app.models.tool import Tool
        from app.services.tool_executor import get_tool_executor

        tool_id = config.get("tool_id")
        output_key = config.get("output_key", "result")
        parameters = config.get("parameters", {})
        error_action = config.get("error_action", "retry")
        retry_count = config.get("retry_count", 3)
        timeout = config.get("timeout", 30)

        logger.info(f"[Tool] node={node_id}, tool_id={tool_id}")

        if not tool_id:
            return {
                "node_outputs": {node_id: {output_key: "[工具节点未配置 tool_id]"}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "tool",
                        "status": "skipped",
                        "reason": "no tool_id",
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

        # 加载工具
        db_tool = db.query(Tool).filter(Tool.id == tool_id).first()
        if not db_tool:
            return {
                "node_outputs": {node_id: {output_key: f"[工具不存在: id={tool_id}]"}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "tool",
                        "status": "error",
                        "error": f"tool not found: {tool_id}",
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

        # 参数变量替换
        merged = _merge_outputs(state)
        resolved_params = {}
        for key, value in parameters.items():
            if isinstance(value, str):
                resolved_params[key] = _replace_vars(value, merged)
            else:
                resolved_params[key] = value

        # 执行工具（支持重试）
        executor = get_tool_executor()
        last_error = None
        attempts = retry_count if error_action == "retry" else 1

        for attempt in range(attempts):
            result = await executor.execute(
                db_tool, resolved_params, timeout=float(timeout)
            )
            if result["success"]:
                return {
                    "node_outputs": {node_id: {output_key: result["output"]}},
                    "execution_log": [
                        {
                            "node_id": node_id,
                            "type": "tool",
                            "status": "done",
                            "tool_name": db_tool.name,
                            "duration_ms": result["duration_ms"],
                            "ts": datetime.utcnow().isoformat(),
                        }
                    ],
                }
            last_error = result["error"]
            if attempt < attempts - 1:
                logger.warning(
                    f"[Tool] node={node_id} 重试 {attempt + 1}/{attempts}: {last_error}"
                )

        # 所有重试都失败
        if error_action == "skip":
            return {
                "node_outputs": {node_id: {output_key: None}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "tool",
                        "status": "skipped",
                        "error": last_error,
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        elif error_action == "fallback":
            fallback_value = config.get("fallback_value", "")
            return {
                "node_outputs": {node_id: {output_key: fallback_value}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "tool",
                        "status": "fallback",
                        "error": last_error,
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        else:
            # stop 或默认：返回错误信息
            return {
                "node_outputs": {node_id: {output_key: f"[工具执行失败] {last_error}"}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "tool",
                        "status": "error",
                        "error": last_error,
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_human_intervention_node(node_id: str, config: Dict[str, Any]):
    """人工介入节点 — 等待人工审批"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[HumanIntervention] node={node_id}")
        timeout = config.get("timeout", 300)
        message = config.get("message", "")
        output_key = config.get("output_key", "output")
        timeout_output = config.get("timeout_output", "timeout")

        # TODO: 接入人工审批系统（消息队列/WebSocket 等）
        # 当前实现：模拟自动通过
        merged = _merge_outputs(state)
        result = {
            "status": "approved",
            "message": message,
            "input": merged,
        }

        return {
            "node_outputs": {node_id: {output_key: result}},
            "execution_log": [
                {
                    "node_id": node_id,
                    "type": "human_intervention",
                    "status": "done",
                    "action": "approved",
                    "ts": datetime.utcnow().isoformat(),
                }
            ],
        }

    return _run


def _make_question_classifier_node(node_id: str, config: Dict[str, Any], db: Session):
    """问题分类器节点：调用 LLM 对输入进行分类"""

    async def _run(state: WorkflowState) -> dict:
        logger.info(f"[QuestionClassifier] node={node_id}")
        try:
            from app.services.llm import LLMService
            from app.models.model import Model

            model_id = config.get("model_id")
            input_variable = config.get("input_variable", "")
            categories = config.get("categories", [])
            output_key = config.get("output_key", "classification")

            # 从合并输出中获取输入值
            merged = _merge_outputs(state)
            # 支持 "node_id.key" 格式的变量引用
            if "." in input_variable:
                parts = input_variable.split(".", 1)
                input_text = str(merged.get(parts[0], merged.get(input_variable, "")))
            else:
                input_text = str(merged.get(input_variable, ""))

            # 构建分类提示词
            category_list = "\n".join(
                [
                    f"{i+1}. {c.get('name', '')}: {c.get('description', '')}"
                    for i, c in enumerate(categories)
                ]
            )
            classification_prompt = (
                f"请将以下输入文本分类到给定的类别中。\n\n"
                f"类别列表：\n{category_list}\n\n"
                f"输入文本：{input_text}\n\n"
                f"请只输出类别的名称（如 CLASS 1、CLASS 2 等），不要输出其他内容。"
            )

            # 调用 LLM
            if model_id:
                model = db.query(Model).filter(Model.id == model_id).first()
                if model and model.provider:
                    provider_config = model.provider
                    llm_service = LLMService()
                    await llm_service.register_provider(
                        provider_type=provider_config.provider_type,
                        api_key=provider_config.api_key,
                        api_endpoint=provider_config.api_endpoint,
                    )
                    response = await llm_service.chat(
                        messages=[{"role": "user", "content": classification_prompt}],
                        model=model.model_id,
                        provider=provider_config.provider_type,
                        temperature=0.1,
                        max_tokens=100,
                    )
                    result_text = response.get("content", "").strip()
                else:
                    # 模型未配置，返回第一个分类
                    result_text = (
                        categories[0].get("name", "CLASS 1")
                        if categories
                        else "CLASS 1"
                    )
            else:
                result_text = (
                    categories[0].get("name", "CLASS 1") if categories else "CLASS 1"
                )

            return {
                "node_outputs": {node_id: {output_key: result_text}},
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "question_classifier",
                        "status": "done",
                        "classification": result_text,
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }
        except Exception as e:
            logger.error(
                f"[QuestionClassifier] node={node_id} error: {e}", exc_info=True
            )
            return {
                "node_outputs": {
                    node_id: {
                        config.get("output_key", "classification"): f"[分类错误] {e}"
                    }
                },
                "execution_log": [
                    {
                        "node_id": node_id,
                        "type": "question_classifier",
                        "status": "error",
                        "error": str(e),
                        "ts": datetime.utcnow().isoformat(),
                    }
                ],
            }

    return _run


def _make_question_classifier_router(
    node_id: str, config: Dict[str, Any], edges: List[Dict[str, str]]
):
    """问题分类器路由函数：根据 LLM 分类结果选择输出分支"""
    categories = config.get("categories", [])
    output_key = config.get("output_key", "classification")

    def _route(state: WorkflowState) -> str:
        logger.info(
            f"[QuestionClassifier] route node={node_id}, categories={len(categories)}"
        )
        node_output = state.get("node_outputs", {}).get(node_id, {})
        classification = str(node_output.get(output_key, "")).strip()

        # 将分类结果与类别名匹配
        for cat in categories:
            cat_name = cat.get("name", "")
            if cat_name and cat_name in classification:
                logger.info(f"[QuestionClassifier] node={node_id} → branch: {cat_name}")
                return cat_name

        # 未匹配到任何类别，走第一个类别或结束
        if categories:
            first_name = categories[0].get("name", "")
            logger.info(f"[QuestionClassifier] node={node_id} → fallback: {first_name}")
            return first_name

        return "__end__"

    return _route


# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------


def _merge_outputs(state: WorkflowState) -> Dict[str, Any]:
    """合并所有 node_outputs 为一个扁平字典，支持 node_id.key 格式"""
    merged = {}
    merged.update(state.get("inputs", {}))
    for node_id, output in state.get("node_outputs", {}).items():
        if isinstance(output, dict):
            merged.update(output)
            # 同时注册 node_id.key 格式（前端 {{node_id.key}} 语法）
            for key, value in output.items():
                merged[f"{node_id}.{key}"] = value
        else:
            merged[node_id] = output
    return merged


def _replace_vars(text: Any, variables: Dict[str, Any]) -> str:
    """替换文本中的 {variable} 和 {{variable}} 占位符"""
    if not isinstance(text, str):
        text = str(text) if text is not None else ""
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", str(value))
        text = text.replace("{" + key + "}", str(value))
    return text


def _resolve_var_template(template: Any, variables: Dict[str, Any]) -> Any:
    """解析模板文本：如果整个模板是单个变量引用则返回原始值（可能是数组），否则做字符串替换"""
    import re

    if not isinstance(template, str):
        template = str(template) if template is not None else ""

    # 匹配整个模板是否只有一个 {{key}} 或 {key}
    pattern = r"^\{\{(\w[\w.]*)\}\}$"
    m = re.match(pattern, template.strip())
    if m:
        var_name = m.group(1)
        if var_name in variables:
            return variables[var_name]
    # 多个变量引用或混合文本，走字符串替换
    return _replace_vars(template, variables)


def _make_noop_node(node_id: str):
    """空操作节点（用于 condition 计算占位）"""

    async def _run(state: WorkflowState) -> dict:
        return {
            "execution_log": [
                {
                    "node_id": node_id,
                    "type": "noop",
                    "status": "done",
                    "ts": datetime.utcnow().isoformat(),
                }
            ]
        }

    return _run


# ------------------------------------------------------------------
# 图构建器
# ------------------------------------------------------------------


class GraphBuilder:
    """从 DSL 配置动态构建 LangGraph StateGraph"""

    def __init__(self, nodes: List[Dict], edges: List[Dict], db: Session, token_queue: Optional[asyncio.Queue] = None):
        self.nodes = {n["id"]: n for n in nodes}
        self.edges = edges
        self.db = db
        self.node_fns: Dict[str, Any] = {}
        self.token_queue = token_queue

    def build(self):
        """构建并编译 StateGraph"""
        g = StateGraph(WorkflowState)

        # 1. 注册所有节点
        for node_id, node in self.nodes.items():
            node_type = node["type"]
            node_config = node.get("data", {}).get("config", {})

            if node_type == "condition":
                # condition 节点用路由函数，不注册普通节点
                # 但 LangGraph 要求路由源节点必须存在，注册一个 noop
                g.add_node(node_id, _make_noop_node(node_id))
            else:
                fn = self._create_node_fn(node_type, node_id, node_config)
                g.add_node(node_id, fn)

        # 2. 注册边
        # 找出所有 condition 和 question_classifier 节点（都需要条件路由）
        condition_nodes = {
            nid: n
            for nid, n in self.nodes.items()
            if n["type"] in ("condition", "question_classifier")
        }

        # 先处理 condition/question_classifier 节点的条件边
        condition_edge_sources = set()
        for edge in self.edges:
            source = edge["source"]
            if source in condition_nodes:
                condition_edge_sources.add(source)

        for cond_id in condition_edge_sources:
            cond_node = self.nodes[cond_id]
            cond_config = cond_node.get("data", {}).get("config", {})
            # 收集该节点的所有出边
            cond_edges = [e for e in self.edges if e["source"] == cond_id]
            # 构建 branch_name -> target_node_id 映射
            branch_map = {}
            for e in cond_edges:
                handle = e.get("sourceHandle", "")
                if handle:
                    branch_map[handle] = e["target"]
            # 添加 __end__ 映射
            branch_map["__end__"] = END

            # 根据节点类型选择路由函数
            if cond_node["type"] == "question_classifier":
                router = _make_question_classifier_router(
                    cond_id, cond_config, cond_edges
                )
            else:
                router = _make_condition_router(cond_id, cond_config, cond_edges)
            g.add_conditional_edges(cond_id, router, branch_map)

        # 3. 注册普通边（排除 condition 的出边，已通过 conditional_edges 处理）
        has_start_edge = False
        for edge in self.edges:
            source = edge["source"]
            target = edge["target"]
            if source in condition_edge_sources:
                continue  # 已处理

            # 自动将 START 连接到没有入边的节点
            g.add_edge(source, target)

        # 4. 自动连接 START 和 END
        # 找出没有入边的节点（除了 condition 的入边也算）
        nodes_with_incoming = set()
        for e in self.edges:
            nodes_with_incoming.add(e["target"])

        # 找出没有出边的节点（除了 condition 的出边）
        nodes_with_outgoing = set()
        for e in self.edges:
            nodes_with_outgoing.add(e["source"])

        root_nodes = [nid for nid in self.nodes if nid not in nodes_with_incoming]
        leaf_nodes = [
            nid
            for nid in self.nodes
            if nid not in nodes_with_outgoing and nid not in condition_edge_sources
        ]

        if root_nodes:
            for root in root_nodes:
                g.add_edge(START, root)
        if leaf_nodes:
            for leaf in leaf_nodes:
                g.add_edge(leaf, END)

        return g.compile()

    def _create_node_fn(self, node_type: str, node_id: str, config: Dict[str, Any]):
        """根据节点类型创建执行函数"""
        if node_type == "start":
            return _make_start_node(node_id)
        elif node_type == "end":
            output_keys = config.get("output_keys", [])
            return _make_end_node(node_id, output_keys or None)
        elif node_type == "llm":
            if self.token_queue is not None:
                return _make_llm_node_streaming(node_id, config, self.db, self.token_queue)
            return _make_llm_node(node_id, config, self.db)
        elif node_type == "knowledge_retrieval":
            return _make_knowledge_node(node_id, config, self.db)
        elif node_type == "code":
            return _make_code_node(node_id, config)
        elif node_type == "http":
            return _make_http_node(node_id, config)
        elif node_type == "tool":
            return _make_tool_node(node_id, config, self.db)
        elif node_type == "human_intervention":
            return _make_human_intervention_node(node_id, config)
        elif node_type == "question_classifier":
            # question_classifier 用路由函数，不注册普通节点
            return _make_noop_node(node_id)
        else:
            raise ValueError(f"不支持的节点类型: {node_type}")


# ------------------------------------------------------------------
# WorkflowService — 配置管理 + 执行
# ------------------------------------------------------------------


class WorkflowService:
    """工作流服务"""

    def __init__(self, db: Session):
        self.db = db
        # 全局 checkpoint 存储（进程内）
        self._checkpointer = MemorySaver()

    # ------------------------------------------------------------------
    # 配置管理
    # ------------------------------------------------------------------

    def get_workflow_config(self, app_id: int) -> Optional[WorkflowConfig]:
        """获取工作流配置"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            return None

        graph_data = workflow.graph or {}
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])

        nodes = [WorkflowNode(**n) for n in nodes_data]
        edges = [WorkflowEdge(**e) for e in edges_data]

        return WorkflowConfig(
            graph=WorkflowGraph(nodes=nodes, edges=edges),
            version=workflow.version,
        )

    def save_workflow_config(self, app_id: int, config: WorkflowConfig) -> bool:
        """保存工作流配置"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            # 自动创建工作流记录
            workflow = Workflow(app_id=app_id, graph={}, nodes_config={})
            self.db.add(workflow)

        # 序列化图结构
        graph_dict = config.graph.model_dump()
        workflow.graph = graph_dict
        workflow.version = (workflow.version or 0) + 1
        workflow.updated_at = datetime.utcnow()

        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # 工作流执行
    # ------------------------------------------------------------------

    async def run_workflow(
        self,
        app_id: int,
        inputs: Dict[str, Any],
        thread_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行工作流"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            raise ValueError("工作流不存在")

        graph_data = workflow.graph or {}
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])

        if not nodes_data:
            raise ValueError("工作流图为空，请先配置节点")

        # 创建运行记录
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            inputs=inputs,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            # 构建 LangGraph
            builder = GraphBuilder(nodes_data, edges_data, self.db)
            compiled_graph = builder.build()

            # 执行
            tid = thread_id or str(uuid.uuid4())
            config = {"configurable": {"thread_id": tid}}

            result = await compiled_graph.ainvoke(
                {"inputs": inputs, "node_outputs": {}, "execution_log": []},
                config=config,
            )

            # 提取最终输出
            final_output = {}
            for node_id, node_data in self.nodes_iter(nodes_data):
                if node_data["type"] == "end":
                    final_output = result.get("node_outputs", {}).get(node_id, {})
                    break

            if not final_output:
                # 没有 end 节点，取最后一个节点的输出
                all_outputs = result.get("node_outputs", {})
                if all_outputs:
                    final_output = list(all_outputs.values())[-1]

            # 更新运行记录
            run.status = "completed"
            run.outputs = final_output
            run.node_runs = result.get("node_outputs", {})
            run.finished_at = datetime.utcnow()
            run.duration = int(
                (run.finished_at - run.started_at).total_seconds() * 1000
            )
            self.db.commit()

            logger.info(f"工作流执行完成: app_id={app_id}, run_id={run.id}")

            return {
                "run_id": run.id,
                "status": "completed",
                "outputs": final_output,
                "node_runs": result.get("node_outputs", {}),
                "execution_log": result.get("execution_log", []),
            }

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.finished_at = datetime.utcnow()
            if run.started_at:
                run.duration = int(
                    (run.finished_at - run.started_at).total_seconds() * 1000
                )
            self.db.commit()
            logger.error(f"工作流执行失败: app_id={app_id}, error={e}", exc_info=True)
            raise

    async def run_workflow_stream(
        self,
        app_id: int,
        inputs: Dict[str, Any],
        thread_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式执行工作流

        逐步 yield 事件:
        - {"event": "node_start", "data": {"node_id": ..., "type": ...}}
        - {"event": "node_log",    "data": {execution_log_entry}}
        - {"event": "llm_token",   "data": {"node_id": ..., "token": ...}}
        - {"event": "done",        "data": {"outputs": ..., "execution_log": ...}}
        - {"event": "error",       "data": {"message": ...}}
        """
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            yield {"event": "error", "data": {"message": "工作流不存在"}}
            return

        graph_data = workflow.graph or {}
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])

        if not nodes_data:
            yield {"event": "error", "data": {"message": "工作流图为空，请先配置节点"}}
            return

        # 创建运行记录
        run = WorkflowRun(
            workflow_id=workflow.id,
            status="running",
            inputs=inputs,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        # LLM token 队列
        token_queue: asyncio.Queue = asyncio.Queue()

        try:
            # 构建 LangGraph（传入 token_queue 以启用 LLM 流式节点）
            builder = GraphBuilder(nodes_data, edges_data, self.db, token_queue=token_queue)
            compiled_graph = builder.build()

            # 节点类型映射（用于 node_start 事件）
            node_type_map = {n["id"]: n["type"] for n in nodes_data}

            # 用后台任务执行 graph，主协程从 token_queue 读取事件
            tid = thread_id or str(uuid.uuid4())
            graph_config = {"configurable": {"thread_id": tid}}

            async def _run_graph():
                return await compiled_graph.ainvoke(
                    {"inputs": inputs, "node_outputs": {}, "execution_log": []},
                    config=graph_config,
                )

            graph_task = asyncio.create_task(_run_graph())

            # 已发出的 node_start 事件跟踪
            seen_starts: set = set()

            while not graph_task.done():
                try:
                    event = await asyncio.wait_for(token_queue.get(), timeout=0.1)
                    # 如果是 llm_token 且该节点未发过 node_start，先发 node_start
                    if event.get("event") == "llm_token":
                        nid = event["data"]["node_id"]
                        if nid not in seen_starts:
                            seen_starts.add(nid)
                            yield {"event": "node_start", "data": {"node_id": nid, "type": "llm"}}
                    yield event
                except asyncio.TimeoutError:
                    continue

            # graph 执行完毕，收集结果
            result = graph_task.result()

            # 排空队列中剩余的 token
            while not token_queue.empty():
                try:
                    event = token_queue.get_nowait()
                    yield event
                except asyncio.QueueEmpty:
                    break

            # 发送执行日志
            for log_entry in result.get("execution_log", []):
                yield {"event": "node_log", "data": log_entry}

            # 提取最终输出
            final_output = {}
            for node_id, node_data in self.nodes_iter(nodes_data):
                if node_data["type"] == "end":
                    final_output = result.get("node_outputs", {}).get(node_id, {})
                    break

            if not final_output:
                all_outputs = result.get("node_outputs", {})
                if all_outputs:
                    final_output = list(all_outputs.values())[-1]

            # 更新运行记录
            run.status = "completed"
            run.outputs = final_output
            run.node_runs = result.get("node_outputs", {})
            run.finished_at = datetime.utcnow()
            run.duration = int(
                (run.finished_at - run.started_at).total_seconds() * 1000
            )
            self.db.commit()

            yield {
                "event": "done",
                "data": {
                    "run_id": run.id,
                    "status": "completed",
                    "outputs": final_output,
                    "execution_log": result.get("execution_log", []),
                    "duration": run.duration,
                },
            }

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.finished_at = datetime.utcnow()
            if run.started_at:
                run.duration = int(
                    (run.finished_at - run.started_at).total_seconds() * 1000
                )
            self.db.commit()
            logger.error(f"工作流流式执行失败: app_id={app_id}, error={e}", exc_info=True)
            yield {"event": "error", "data": {"message": str(e)}}

    @staticmethod
    def nodes_iter(nodes_data):
        """迭代节点数据"""
        for n in nodes_data:
            yield n["id"], n

    # ------------------------------------------------------------------
    # DSL 导入导出
    # ------------------------------------------------------------------

    def export_dsl(self, app_id: int) -> Optional[DSLData]:
        """导出 DSL"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            return None

        graph_data = workflow.graph or {}
        nodes_data = graph_data.get("nodes", [])
        edges_data = graph_data.get("edges", [])

        nodes = [WorkflowNode(**n) for n in nodes_data]
        edges = [WorkflowEdge(**e) for e in edges_data]

        # 获取应用名称
        app = self.db.query(App).filter(App.id == app_id).first()
        name = app.name if app else "未命名工作流"

        return DSLData(
            name=name,
            version=workflow.version or 1,
            nodes=nodes,
            edges=edges,
        )

    def import_dsl(self, app_id: int, dsl: DSLData) -> bool:
        """导入 DSL"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            workflow = Workflow(app_id=app_id, graph={}, nodes_config={})
            self.db.add(workflow)

        graph_dict = {
            "nodes": [n.model_dump() for n in dsl.nodes],
            "edges": [e.model_dump() for e in dsl.edges],
        }
        workflow.graph = graph_dict
        workflow.version = dsl.version or 1
        workflow.updated_at = datetime.utcnow()

        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # 运行记录
    # ------------------------------------------------------------------

    def list_runs(self, app_id: int, limit: int = 20) -> List[WorkflowRun]:
        """获取运行记录列表"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            return []

        return (
            self.db.query(WorkflowRun)
            .filter(WorkflowRun.workflow_id == workflow.id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_run(self, app_id: int, run_id: int) -> Optional[WorkflowRun]:
        """获取单次运行详情"""
        workflow = self.db.query(Workflow).filter(Workflow.app_id == app_id).first()
        if not workflow:
            return None

        return (
            self.db.query(WorkflowRun)
            .filter(
                WorkflowRun.id == run_id,
                WorkflowRun.workflow_id == workflow.id,
            )
            .first()
        )


# ------------------------------------------------------------------
# 工厂函数
# ------------------------------------------------------------------


def get_workflow_service(db: Session) -> WorkflowService:
    return WorkflowService(db)
