"""
工具注册表

全局统一管理工具的注册与查找。
Agent 只需通过 tool_ids 从注册表获取 LangChain StructuredTool，无需关心工具类型。

用法:
    registry = ToolRegistry()
    tools = registry.get_tools(tool_ids, db, knowledge_base_ids)
"""

import asyncio
import json
from typing import Any, Dict, List, Optional

from app.models.tool import Tool
from app.services.tool_executor import ToolExecutor
from app.utils.logger import logger


class ToolRegistry:
    """
    工具注册表

    核心设计:
    - 每种工具类型 (builtin/plugin/mcp) 对应一个工厂方法
    - 工厂方法返回 LangChain StructuredTool
    - 执行逻辑通过 ToolExecutor 统一处理
    - Agent 调用: registry.get_tools(tool_ids, db) → List[StructuredTool]
    """

    def __init__(self):
        self._executor = ToolExecutor()

    def get_tools(
        self,
        tool_ids: List[int],
        db,
        knowledge_base_ids: Optional[List[int]] = None,
    ) -> List:
        """
        根据 tool_id 列表批量获取 LangChain StructuredTool

        Args:
            tool_ids: 工具 ID 列表
            db: 数据库会话
            knowledge_base_ids: 知识库 ID 列表 (knowledge_retrieval 专用)

        Returns:
            LangChain StructuredTool 列表
        """
        tools = []
        for tid in tool_ids:
            t = self._build(tid, db, knowledge_base_ids)
            if t:
                tools.append(t)
        logger.info(f"ToolRegistry: 加载 {len(tools)}/{len(tool_ids)} 个工具")
        return tools

    def _build(self, tool_id: int, db, kb_ids: Optional[List[int]] = None):
        """构建单个 StructuredTool"""
        db_tool = db.query(Tool).filter(Tool.id == tool_id, Tool.is_active == True).first()
        if not db_tool:
            logger.warning(f"工具不存在或已禁用: tool_id={tool_id}")
            return None

        # 工厂分发 — 字典映射替代 if-elif
        factory = self._FACTORIES.get(db_tool.tool_type)
        if not factory:
            logger.warning(f"不支持的工具类型: {db_tool.tool_type}")
            return None

        try:
            return factory(self, db_tool, kb_ids)
        except Exception as e:
            logger.error(f"创建工具失败: {db_tool.name}, error={e}", exc_info=True)
            return None

    # ==================================================================
    # 工厂方法 — 每种工具类型一个
    # ==================================================================

    # 显示名 → 内部 key 映射（兼容已安装的旧模板数据）
    _NAME_ALIASES = {
        "Tavily Search":    "web_search",
        "DuckDuckGo Search":"web_search",
        "Web Scraper":      "web_browse",
        "Code Interpreter": "code_interpreter",
        "Knowledge Retrieval":"knowledge_retrieval",
        "Calculator":       "calculator",
        "web_search":       "web_search",
        "web_browse":       "web_browse",
        "code_interpreter": "code_interpreter",
        "knowledge_retrieval":"knowledge_retrieval",
        "calculator":       "calculator",
    }

    def _create_builtin(self, db_tool: Tool, kb_ids: Optional[List[int]] = None):
        """内置工具工厂: 直接映射到 ToolExecutor 的具体方法"""
        from langchain_core.tools import StructuredTool

        # name → (显示名, 描述, 执行函数, 默认schema)
        ROUTES = {
            "web_search":        ("web_search",        "搜索互联网获取最新信息",           self._run_search,       {"query": "搜索关键词"}),
            "web_browse":        ("web_browse",        "访问指定URL并提取网页内容",        self._run_browse,       {"url": "要访问的网页URL"}),
            "code_interpreter":  ("code_interpreter",  "执行Python代码进行计算和数据处理", self._run_code,         {"code": "要执行的Python代码"}),
            "knowledge_retrieval":("knowledge_retrieval","从知识库中检索相关信息",           self._run_knowledge,    {"query": "检索查询内容"}),
            "calculator":        ("calculator",         "数学计算器",                       self._run_calculator,   {"expression": "数学表达式"}),
        }

        # 先通过别名映射获取内部 key
        internal_key = self._NAME_ALIASES.get(db_tool.name, db_tool.name)
        route = ROUTES.get(internal_key)
        if not route:
            logger.warning(f"未知的内置工具: {db_tool.name}")
            return None

        name, desc, runner, param_hints = route

        # 构建 args_schema
        schema = self._make_schema(name, desc, param_hints)

        # 绑定 knowledge_base_ids 到知识库工具
        if db_tool.name == "knowledge_retrieval" and kb_ids:
            exec_fn = lambda **kw: runner(kb_ids=kb_ids, **kw)
        else:
            exec_fn = runner

        # 同步占位（LangChain 的 run() 走 sync 路径，实际不应被调用）
        def _sync(**kwargs):
            raise RuntimeError("此工具仅支持异步调用")

        return StructuredTool.from_function(
            func=_sync,
            coroutine=exec_fn,  # ← 显式指定 async 协程
            name=name, description=desc, args_schema=schema,
        )

    def _create_plugin(self, db_tool: Tool, kb_ids=None):
        """HTTP API 插件工具工厂"""
        return self._create_api_tool(db_tool)

    def _create_mcp(self, db_tool: Tool, kb_ids=None):
        """MCP 协议工具工厂"""
        return self._create_api_tool(db_tool)

    def _create_api_tool(self, db_tool: Tool):
        """plugin / mcp 共用的工厂逻辑"""
        from langchain_core.tools import StructuredTool

        desc = db_tool.description or f"调用 {db_tool.name} 工具"
        params = db_tool.parameters_schema or {}
        props = params.get("properties", {})
        if props:
            desc += "\n参数: " + ", ".join(
                f"{k}({v.get('type', 'any')})" for k, v in props.items()
            )

        # 捕获 db_tool 到闭包
        _db_tool = db_tool
        executor = self._executor

        async def _exec(**kwargs):
            result = await executor.execute(_db_tool, kwargs)
            if result.get("success"):
                out = result.get("output", "")
                return json.dumps(out, ensure_ascii=False, indent=2) if isinstance(out, (dict, list)) else str(out)
            return f"[错误] {result.get('error', '未知错误')}"

        # 同步占位
        def _sync(**kwargs):
            raise RuntimeError("此工具仅支持异步调用")

        schema = params if props else None
        return StructuredTool.from_function(
            func=_sync,
            coroutine=_exec,  # ← 显式指定 async 协程
            name=db_tool.name, description=desc, args_schema=schema,
        )

    # 工厂分发表
    _FACTORIES = {
        "builtin": _create_builtin,
        "plugin":  _create_plugin,
        "mcp":     _create_mcp,
    }

    # ==================================================================
    # 内置工具执行 — 直接调用 ToolExecutor 对应方法
    # ==================================================================

    async def _run_search(self, query: str, **kw) -> str:
        r = await self._executor._builtin_web_search({"query": query}, 30)
        return self._format_result(r)

    async def _run_browse(self, url: str, **kw) -> str:
        r = await self._executor._builtin_web_browse({"url": url}, 30)
        return self._format_result(r)

    async def _run_code(self, code: str, **kw) -> str:
        r = await self._executor._builtin_code_interpreter({"code": code})
        return self._format_result(r)

    async def _run_knowledge(self, query: str, kb_ids: Optional[List[int]] = None, **kw) -> str:
        # 知识库检索走独立流程，这里返回占位
        return f"知识库检索: 正在搜索 '{query}' ..."

    async def _run_calculator(self, expression: str, **kw) -> str:
        r = await self._executor._builtin_calculator({"expression": expression})
        return self._format_result(r)

    @staticmethod
    def _format_result(r: dict) -> str:
        if r.get("success"):
            out = r.get("output", "")
            return json.dumps(out, ensure_ascii=False, indent=2) if isinstance(out, (dict, list)) else str(out)
        return f"[错误] {r.get('error', '未知错误')}"

    # ==================================================================
    # 工具函数
    # ==================================================================

    @staticmethod
    def _make_schema(name: str, description: str, param_hints: dict) -> dict:
        """从参数提示生成 JSON Schema"""
        properties = {}
        for param_name, param_desc in param_hints.items():
            properties[param_name] = {
                "title": param_name,
                "description": param_desc,
                "type": "string",
            }
        return {
            "title": name,
            "description": description,
            "type": "object",
            "properties": properties,
            "required": list(param_hints.keys()),
        }
