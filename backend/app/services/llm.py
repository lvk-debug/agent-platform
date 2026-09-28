from typing import Any, Dict, List, Optional, AsyncIterator
import json
import httpx
from app.core.config import settings
from app.utils.logger import logger

# ==================== 全局连接池（复用 TCP + TLS） ====================
_http_client = httpx.AsyncClient(
    limits=httpx.Limits(
        max_keepalive_connections=20,   # 同一 host 最多保持 20 个空闲连接
        max_connections=50,             # 总连接数上限
        keepalive_expiry=30.0,          # 空闲连接保持 30 秒
    ),
    timeout=httpx.Timeout(
        connect=10.0,                   # TCP 握手超时
        read=120.0,                     # 读超时（LLM 生成可能较慢）
        write=10.0,                     # 写超时
        pool=5.0,                       # 从连接池获取连接的等待超时
    ),
)


async def close_http_client():
    """应用关闭时调用，释放连接池"""
    await _http_client.aclose()


class LLMService:
    """
    LLM服务 - 统一的大语言模型调用接口（复用全局连接池）
    """

    def __init__(self):
        self.providers = {}

    async def register_provider(
        self,
        provider_type: str,
        api_key: str,
        api_endpoint: Optional[str] = None,
        **kwargs,
    ):
        """
        注册模型供应商
        """
        self.providers[provider_type] = {
            "api_key": api_key,
            "api_endpoint": api_endpoint,
            **kwargs,
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        provider: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        同步对话
        """
        provider_config = self.providers.get(provider)
        if not provider_config:
            raise ValueError(f"未找到供应商配置: {provider}")

        try:
            if provider == "openai":
                return await self._openai_chat(
                    messages, model, provider_config, temperature, max_tokens, **kwargs
                )
            elif provider == "anthropic":
                return await self._anthropic_chat(
                    messages, model, provider_config, temperature, max_tokens, **kwargs
                )
            else:
                raise ValueError(f"不支持的供应商: {provider}")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        provider: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        流式对话
        """
        provider_config = self.providers.get(provider)
        if not provider_config:
            raise ValueError(f"未找到供应商配置: {provider}")

        try:
            if provider == "openai":
                async for chunk in self._openai_stream_chat(
                    messages, model, provider_config, temperature, max_tokens, **kwargs
                ):
                    yield chunk
            elif provider == "anthropic":
                async for chunk in self._anthropic_stream_chat(
                    messages, model, provider_config, temperature, max_tokens, **kwargs
                ):
                    yield chunk
            else:
                raise ValueError(f"不支持的供应商: {provider}")
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            raise

    async def _openai_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        OpenAI同步对话
        """
        api_endpoint = config.get("api_endpoint", "https://api.openai.com/v1")
        api_key = config.get("api_key")

        logger.info(f"调用 OpenAI API: endpoint={api_endpoint}, model={model}")
        response = await _http_client.post(
            f"{api_endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                **kwargs,
            },
        )
        logger.info(f"OpenAI API 响应状态: {response.status_code}")
        if response.status_code != 200:
            logger.error(f"OpenAI API 错误: {response.text}")
        response.raise_for_status()
        data = response.json()

        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data["model"],
            "tokens_used": data.get("usage", {}),
            "finish_reason": data["choices"][0]["finish_reason"],
        }

    async def _openai_stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        OpenAI流式对话
        """
        api_endpoint = config.get("api_endpoint", "https://api.openai.com/v1")
        api_key = config.get("api_key")

        async with _http_client.stream(
            "POST",
            f"{api_endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
                **kwargs,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line = line[6:]
                    if line.strip() == "[DONE]":
                        break
                    data = json.loads(line)
                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        yield content

    async def _anthropic_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Anthropic同步对话
        """
        api_endpoint = config.get("api_endpoint", "https://api.anthropic.com")
        api_key = config.get("api_key")

        # 转换消息格式
        system_message = None
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append(msg)

        response = await _http_client.post(
            f"{api_endpoint}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_message or "",
                "messages": formatted_messages,
                **kwargs,
            },
        )
        response.raise_for_status()
        data = response.json()

        return {
            "content": data["content"][0]["text"],
            "model": data["model"],
            "tokens_used": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            "finish_reason": data["stop_reason"],
        }

    async def _anthropic_stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        **kwargs,
    ) -> AsyncIterator[str]:
        """
        Anthropic流式对话
        """
        api_endpoint = config.get("api_endpoint", "https://api.anthropic.com")
        api_key = config.get("api_key")

        # 转换消息格式
        system_message = None
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append(msg)

        async with _http_client.stream(
            "POST",
            f"{api_endpoint}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_message or "",
                "messages": formatted_messages,
                "stream": True,
                **kwargs,
            },
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line = line[6:]
                    data = json.loads(line)
                    if data["type"] == "content_block_delta":
                        yield data["delta"]["text"]


    async def chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str = "gpt-3.5-turbo",
        provider: str = "openai",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        """带工具调用的对话（Function Calling）

        用于客服 Tool Agent 等需要模型自主选择并调用工具的场景。
        tools 为 OpenAI 格式：[{type:"function", function:{name, description, parameters}}]。
        返回统一结构：{content, tool_calls:[{id, name, arguments}], model, tokens_used, finish_reason}。
        tool_calls 为空表示模型本轮未选择任何工具。
        """
        provider_config = self.providers.get(provider)
        if not provider_config:
            raise ValueError(f"未找到供应商配置: {provider}")

        try:
            if provider == "openai":
                return await self._openai_chat_with_tools(
                    messages, tools, model, provider_config,
                    temperature, max_tokens, tool_choice, **kwargs,
                )
            elif provider == "anthropic":
                return await self._anthropic_chat_with_tools(
                    messages, tools, model, provider_config,
                    temperature, max_tokens, tool_choice, **kwargs,
                )
            else:
                raise ValueError(f"不支持的供应商: {provider}")
        except Exception as e:
            logger.error(f"LLM 工具调用失败: {e}")
            raise

    async def _openai_chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        tool_choice: str,
        **kwargs,
    ) -> Dict[str, Any]:
        api_endpoint = config.get("api_endpoint", "https://api.openai.com/v1")
        api_key = config.get("api_key")
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }
        response = await _http_client.post(
            f"{api_endpoint}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content") or ""
        tool_calls: List[Dict[str, Any]] = []
        for tc in msg.get("tool_calls") or []:
            if tc.get("type") != "function":
                continue
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                {"id": tc.get("id"), "name": tc["function"]["name"], "arguments": args}
            )
        return {
            "content": content,
            "tool_calls": tool_calls,
            "model": data.get("model"),
            "tokens_used": data.get("usage", {}),
            "finish_reason": data["choices"][0].get("finish_reason"),
        }

    async def _anthropic_chat_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        model: str,
        config: Dict[str, Any],
        temperature: float,
        max_tokens: int,
        tool_choice: str,
        **kwargs,
    ) -> Dict[str, Any]:
        api_endpoint = config.get("api_endpoint", "https://api.anthropic.com")
        api_key = config.get("api_key")

        # OpenAI 工具格式 → Anthropic 工具格式
        anthropic_tools = [
            {
                "name": t["function"]["name"],
                "description": t["function"].get("description", ""),
                "input_schema": t["function"].get("parameters", {"type": "object"}),
            }
            for t in tools
        ]

        system_message = None
        formatted_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                formatted_messages.append(msg)

        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_message or "",
            "messages": formatted_messages,
            "tools": anthropic_tools,
            **kwargs,
        }
        response = await _http_client.post(
            f"{api_endpoint}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        content = ""
        tool_calls: List[Dict[str, Any]] = []
        for block in data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    {
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "arguments": block.get("input", {}) or {},
                    }
                )
        return {
            "content": content,
            "tool_calls": tool_calls,
            "model": data.get("model"),
            "tokens_used": {
                "prompt_tokens": data.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": data.get("usage", {}).get("output_tokens", 0),
            },
            "finish_reason": data.get("stop_reason"),
        }


# 创建全局LLM服务实例
llm_service = LLMService()
