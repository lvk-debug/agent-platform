from typing import Any, Dict, List, Optional, AsyncIterator
import httpx
from app.core.config import settings
from app.utils.logger import logger


class LLMService:
    """
    LLM服务 - 统一的大语言模型调用接口
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

        async with httpx.AsyncClient() as client:
            logger.info(f"调用 OpenAI API: endpoint={api_endpoint}, model={model}")
            response = await client.post(
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
                timeout=60.0,
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

        async with httpx.AsyncClient() as client:
            async with client.stream(
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
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        line = line[6:]
                        if line.strip() == "[DONE]":
                            break
                        import json
                        data = json.loads(line)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]

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

        async with httpx.AsyncClient() as client:
            response = await client.post(
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
                timeout=60.0,
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

        async with httpx.AsyncClient() as client:
            async with client.stream(
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
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        line = line[6:]
                        import json
                        data = json.loads(line)
                        if data["type"] == "content_block_delta":
                            yield data["delta"]["text"]


# 创建全局LLM服务实例
llm_service = LLMService()
