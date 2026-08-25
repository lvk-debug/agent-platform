"""
统一工具执行引擎
支持 builtin / plugin / mcp 三种类型工具的实际执行
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.models.tool import Tool
from app.utils.logger import logger


class ToolExecutor:
    """
    统一工具执行器

    根据工具类型分发到对应的执行逻辑：
    - builtin: 内置工具（web_search, web_browse, code_interpreter, calculator）
    - plugin:  HTTP API 插件（根据 endpoint + auth_config 发起请求）
    - mcp:     MCP 协议工具（JSON-RPC tools/call）
    """

    async def execute(
        self,
        db_tool: Tool,
        input_data: Dict[str, Any],
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        统一执行入口

        Args:
            db_tool: 数据库中的工具记录
            input_data: 工具输入参数
            timeout: 超时时间（秒）

        Returns:
            {
                "success": bool,
                "output": any,       # 工具返回的结果
                "error": str | None, # 错误信息（失败时）
                "duration_ms": int,  # 执行耗时
            }
        """
        start = time.time()
        tool_type = db_tool.tool_type

        try:
            if tool_type == "builtin":
                result = await self._execute_builtin(db_tool, input_data, timeout)
            elif tool_type == "plugin":
                result = await self._execute_plugin(db_tool, input_data, timeout)
            elif tool_type == "mcp":
                result = await self._execute_mcp(db_tool, input_data, timeout)
            else:
                result = {"success": False, "output": None, "error": f"不支持的工具类型: {tool_type}"}
        except asyncio.TimeoutError:
            result = {"success": False, "output": None, "error": f"工具执行超时 ({timeout}s)"}
        except Exception as e:
            logger.error(f"工具执行异常: tool={db_tool.name}, error={e}", exc_info=True)
            result = {"success": False, "output": None, "error": str(e)}

        duration_ms = int((time.time() - start) * 1000)
        result["duration_ms"] = duration_ms
        logger.info(
            f"工具执行完成: name={db_tool.name}, type={tool_type}, "
            f"success={result['success']}, duration={duration_ms}ms"
        )
        return result

    # ------------------------------------------------------------------
    # Builtin 工具
    # ------------------------------------------------------------------

    async def _execute_builtin(
        self, db_tool: Tool, input_data: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """执行内置工具"""
        name = db_tool.name

        if name == "web_search" or name == "tavily_search":
            return await self._builtin_web_search(input_data, timeout)
        elif name == "web_browse" or name == "web_scraper":
            return await self._builtin_web_browse(input_data, timeout)
        elif name == "code_interpreter" or name == "code_executor":
            return await self._builtin_code_interpreter(input_data)
        elif name == "calculator":
            return await self._builtin_calculator(input_data)
        elif name == "knowledge_retrieval":
            return {"success": True, "output": f"知识库检索: {input_data.get('query', '')}", "error": None}
        else:
            return {"success": False, "output": None, "error": f"未知的内置工具: {name}"}

    async def _builtin_web_search(
        self, input_data: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """Tavily 搜索"""
        query = input_data.get("query", "")
        if not query:
            return {"success": False, "output": None, "error": "缺少 query 参数"}

        api_key = settings.TAVILY_API_KEY
        if not api_key:
            return {"success": False, "output": None, "error": "未配置 TAVILY_API_KEY"}

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=api_key)
            response = await asyncio.to_thread(
                client.search,
                query=query,
                max_results=input_data.get("max_results", 5),
                search_depth=input_data.get("search_depth", "advanced"),
            )

            results = []
            for i, r in enumerate(response.get("results", [])[:5], 1):
                title = r.get("title", "无标题")
                url = r.get("url", "")
                content = r.get("content", "")[:300]
                results.append(f"[{i}] {title}\n    链接: {url}\n    摘要: {content}")

            output = f"搜索结果（共 {len(results)} 条）：\n\n" + "\n\n".join(results) if results else f"未找到与 '{query}' 相关的结果"
            return {"success": True, "output": output, "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": f"搜索失败: {e}"}

    async def _builtin_web_browse(
        self, input_data: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """网页抓取"""
        url = input_data.get("url", "")
        if not url:
            return {"success": False, "output": None, "error": "缺少 url 参数"}

        try:
            from bs4 import BeautifulSoup

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            text = "\n".join(lines)

            if len(text) > 3000:
                text = text[:3000] + f"\n\n[内容已截断，共 {len(text)} 字符]"

            title = soup.title.string if soup.title else "无标题"
            output = f"网页标题: {title}\n\n内容:\n{text}"
            return {"success": True, "output": output, "error": None}
        except httpx.TimeoutException:
            return {"success": False, "output": None, "error": f"抓取超时: {url}"}
        except httpx.HTTPStatusError as e:
            return {"success": False, "output": None, "error": f"HTTP {e.response.status_code}: {url}"}
        except Exception as e:
            return {"success": False, "output": None, "error": f"抓取失败: {e}"}

    async def _builtin_code_interpreter(
        self, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Python 代码执行"""
        code = input_data.get("code", "")
        if not code:
            return {"success": False, "output": None, "error": "缺少 code 参数"}

        try:
            import io
            import sys
            from contextlib import redirect_stdout

            env = {"__builtins__": __builtins__}
            stdout_capture = io.StringIO()

            with redirect_stdout(stdout_capture):
                exec(code, env)

            output = stdout_capture.getvalue()
            return {"success": True, "output": output if output else "代码执行成功（无输出）", "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": f"代码执行错误: {e}"}

    async def _builtin_calculator(
        self, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """数学计算"""
        expression = input_data.get("expression", input_data.get("query", ""))
        if not expression:
            return {"success": False, "output": None, "error": "缺少 expression 参数"}

        try:
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
                    return allowed_ops[type(node.op)](safe_eval(node.operand))
                else:
                    raise ValueError(f"不支持的表达式类型: {type(node)}")

            tree = ast.parse(expression, mode="eval")
            result = safe_eval(tree)
            return {"success": True, "output": str(result), "error": None}
        except Exception as e:
            return {"success": False, "output": None, "error": f"计算错误: {e}"}

    # ------------------------------------------------------------------
    # Plugin 工具 — HTTP API 调用
    # ------------------------------------------------------------------

    async def _execute_plugin(
        self, db_tool: Tool, input_data: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """
        执行 Plugin 类型工具

        根据 endpoint 和 auth_config 发起 HTTP 请求。
        auth_config 支持:
          - {"api_key": "xxx"}                    → Authorization: Bearer xxx
          - {"api_key": "xxx", "header": "X-API-Key"} → X-API-Key: xxx
          - {"method": "GET"}                     → 覆盖默认 POST
          - {"headers": {...}}                    → 额外请求头
        """
        endpoint = db_tool.endpoint
        if not endpoint:
            return {"success": False, "output": None, "error": "工具未配置 endpoint"}

        auth_config = db_tool.auth_config or {}
        method = auth_config.get("method", "POST").upper()

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        api_key = auth_config.get("api_key", "")
        if api_key:
            header_name = auth_config.get("header", "Authorization")
            if header_name == "Authorization":
                headers["Authorization"] = f"Bearer {api_key}"
            else:
                headers[header_name] = api_key

        # 额外请求头
        extra_headers = auth_config.get("headers", {})
        if isinstance(extra_headers, dict):
            headers.update(extra_headers)

        # URL 变量替换（支持 {city} 等占位符）
        url = endpoint
        for key, value in input_data.items():
            url = url.replace("{" + key + "}", str(value))

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers, params=input_data)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=input_data)
                elif method == "PUT":
                    resp = await client.put(url, headers=headers, json=input_data)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    return {"success": False, "output": None, "error": f"不支持的 HTTP 方法: {method}"}

                resp.raise_for_status()

                # 解析响应
                content_type = resp.headers.get("content-type", "")
                if "application/json" in content_type:
                    body = resp.json()
                else:
                    body = resp.text

                return {"success": True, "output": body, "error": None}

        except httpx.TimeoutException:
            return {"success": False, "output": None, "error": f"请求超时: {url}"}
        except httpx.HTTPStatusError as e:
            return {"success": False, "output": None, "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"success": False, "output": None, "error": f"请求失败: {e}"}

    # ------------------------------------------------------------------
    # MCP 工具 — JSON-RPC 协议
    # ------------------------------------------------------------------

    async def _execute_mcp(
        self, db_tool: Tool, input_data: Dict[str, Any], timeout: float
    ) -> Dict[str, Any]:
        """
        执行 MCP 类型工具

        通过 MCP JSON-RPC 协议调用远程工具:
        POST endpoint
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "tool_name", "arguments": {...}},
            "id": 1
        }
        """
        endpoint = db_tool.endpoint
        if not endpoint:
            return {"success": False, "output": None, "error": "MCP 工具未配置 endpoint"}

        auth_config = db_tool.auth_config or {}

        # 构建请求头
        headers = {"Content-Type": "application/json"}
        api_key = auth_config.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # MCP JSON-RPC 请求
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": db_tool.name,
                "arguments": input_data,
            },
            "id": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                resp.raise_for_status()

                data = resp.json()

                # 检查 JSON-RPC 错误
                if "error" in data:
                    error = data["error"]
                    return {
                        "success": False,
                        "output": None,
                        "error": f"MCP 错误 [{error.get('code', '?')}]: {error.get('message', '未知错误')}",
                    }

                # 提取结果
                result = data.get("result", {})
                # MCP 工具结果通常在 content 数组中
                content = result.get("content", [])
                if content:
                    # 合并所有 content 项的文本
                    texts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                texts.append(item.get("text", ""))
                            else:
                                texts.append(json.dumps(item, ensure_ascii=False))
                        else:
                            texts.append(str(item))
                    output = "\n".join(texts)
                else:
                    output = result

                return {"success": True, "output": output, "error": None}

        except httpx.TimeoutException:
            return {"success": False, "output": None, "error": f"MCP 请求超时: {endpoint}"}
        except httpx.HTTPStatusError as e:
            return {"success": False, "output": None, "error": f"MCP HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"success": False, "output": None, "error": f"MCP 调用失败: {e}"}


# ------------------------------------------------------------------
# 单例
# ------------------------------------------------------------------

_executor: Optional[ToolExecutor] = None


def get_tool_executor() -> ToolExecutor:
    """获取工具执行器单例"""
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
