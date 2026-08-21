"""
MCP 工具导入服务
从 MCP Server URL 自动解析并导入工具
"""

import json
from typing import Any, Dict, List, Optional

import httpx


async def fetch_mcp_tools(url: str) -> List[Dict[str, Any]]:
    """
    从 MCP Server 获取工具列表

    支持两种方式：
    1. 标准 MCP Server HTTP 端点 (POST /mcp)
    2. SSE 端点 (GET /sse)
    """
    tools = []

    # 尝试标准 MCP HTTP 方式
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # MCP 标准协议：POST 请求获取工具列表
            response = await client.post(
                url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/list",
                    "params": {}
                },
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                data = response.json()
                if "result" in data and "tools" in data["result"]:
                    for tool in data["result"]["tools"]:
                        tools.append({
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "input_schema": tool.get("inputSchema", {}),
                        })
                    return tools
    except Exception:
        pass

    # 尝试从常见路径获取
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 尝试 /tools 路径
            response = await client.get(f"{url}/tools")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    for tool in data:
                        tools.append({
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "input_schema": tool.get("inputSchema", {}),
                        })
                    return tools
    except Exception:
        pass

    # 尝试从 mcp.so 解析
    if "mcp.so" in url:
        tools = await _parse_mcp_so(url)

    return tools


async def _parse_mcp_so(url: str) -> List[Dict[str, Any]]:
    """从 mcp.so 解析工具信息"""
    tools = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                # mcp.so 页面通常包含 JSON-LD 或 script 数据
                # 这里简化处理，实际可能需要更复杂的解析
                data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                if "tools" in data:
                    for tool in data["tools"]:
                        tools.append({
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "input_schema": tool.get("inputSchema", {}),
                        })
    except Exception:
        pass
    return tools


def build_tool_from_mcp(
    mcp_tool: Dict[str, Any],
    server_url: str,
) -> Dict[str, Any]:
    """
    从 MCP 工具信息构建 Tool 模型数据
    """
    return {
        "name": mcp_tool.get("name", "Unknown Tool"),
        "description": mcp_tool.get("description", ""),
        "tool_type": "mcp",
        "icon": "🔌",
        "parameters_schema": mcp_tool.get("input_schema", {}),
        "endpoint": server_url,
        "auth_config": {},
    }


async def import_mcp_tools(
    server_url: str,
) -> List[Dict[str, Any]]:
    """
    从 MCP Server 导入所有工具

    返回可用于创建 Tool 的数据列表
    """
    mcp_tools = await fetch_mcp_tools(server_url)
    return [build_tool_from_mcp(t, server_url) for t in mcp_tools]
