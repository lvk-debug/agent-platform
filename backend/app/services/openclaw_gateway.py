"""
OpenClaw 网关 RPC 客户端

只负责两个调用：
1. list_installed_skills — 获取 ClawHub 安装的社区 skill 元数据
2. invoke_skill — 执行 skill（复用 OpenClaw 的 docker 沙箱、权限、审批、审计）
"""

from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.utils.logger import logger


class OpenClawGateway:
    """OpenClaw 网关 HTTP 客户端"""

    def __init__(self, client: httpx.AsyncClient = None):
        self._client = client
        self._own_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=float(settings.OPENCLAW_REQUEST_TIMEOUT),
                    write=10.0,
                    pool=5.0,
                ),
                verify=False,  # 自签名证书
            )
        return self._client

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.OPENCLAW_API_KEY}",
            "Content-Type": "application/json",
        }

    # ==================== 技能发现 ====================

    async def list_installed_skills(self) -> List[Dict[str, Any]]:
        """
        获取 OpenClaw 网关已安装的 skill 列表

        返回格式:
        [
            {
                "name": "weather_query",
                "description": "查询天气信息",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "城市名"}
                    },
                    "required": ["city"]
                }
            },
            ...
        ]
        """
        client = await self._get_client()
        url = f"{settings.OPENCLAW_API_URL}/rpc/skills"

        try:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
            # 兼容不同返回格式
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("skills", data.get("data", []))
            return []
        except httpx.ConnectError as e:
            logger.error(f"无法连接 OpenClaw 网关: {e}")
            return []
        except httpx.TimeoutException:
            logger.error("获取技能列表超时")
            return []
        except Exception as e:
            logger.error(f"获取技能列表失败: {e}", exc_info=True)
            return []

    # ==================== 技能执行 ====================

    async def invoke_skill(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行 OpenClaw skill

        Args:
            tool_name: 技能名称
            arguments: 技能参数

        Returns:
            {"output": "...", "error": null} 或 {"output": "", "error": "错误信息"}
        """
        client = await self._get_client()
        url = f"{settings.OPENCLAW_API_URL}/rpc/tools/execute"

        payload = {
            "tool_name": tool_name,
            "arguments": arguments,
        }

        try:
            resp = await client.post(
                url, headers=self._headers(), json=payload
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError as e:
            error_msg = f"无法连接 OpenClaw 网关: {e}"
            logger.error(error_msg)
            return {"output": "", "error": error_msg}
        except httpx.TimeoutException:
            error_msg = f"技能执行超时: {tool_name}"
            logger.error(error_msg)
            return {"output": "", "error": error_msg}
        except httpx.HTTPStatusError as e:
            error_msg = f"技能执行失败 ({e.response.status_code}): {e.response.text[:200]}"
            logger.error(error_msg)
            return {"output": "", "error": error_msg}
        except Exception as e:
            error_msg = f"技能执行异常: {e}"
            logger.error(error_msg, exc_info=True)
            return {"output": "", "error": error_msg}

    # ==================== 清理 ====================

    async def close(self):
        """关闭内部 HTTP 客户端（仅自创建的）"""
        if self._own_client and self._client:
            await self._client.aclose()
            self._client = None


# 全局单例（复用连接池）
_gateway: Optional[OpenClawGateway] = None


def get_openclaw_gateway(client: httpx.AsyncClient = None) -> OpenClawGateway:
    """获取 OpenClaw 网关客户端（可选传入共享连接池）"""
    global _gateway
    if _gateway is None:
        _gateway = OpenClawGateway(client)
    return _gateway
