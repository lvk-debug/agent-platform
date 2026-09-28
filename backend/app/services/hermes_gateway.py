"""
Hermes Agent 网关客户端

调用 Hermes API Server（端口 8642）。
接口: POST /v1/chat/completions，stream=True
认证: Bearer Token

⚠️ 上游协议**并非**纯 OpenAI 兼容，实测为双通道混合：

1. OpenAI 标准 chunk（帧内无 `event:` 行）
   delta.content 为文本增量，最后一个 chunk 带 finish_reason 与 usage。
2. 自定义事件 `event: hermes.tool.progress`（承载工具调用）
   {"tool": "terminal", "emoji": "...", "label": "ls -la",
    "toolCallId": "call_xxx", "status": "running"}
   {"tool": "terminal", "toolCallId": "call_xxx", "status": "completed"}

Hermes **不使用** `delta.tool_calls`，也不回传工具执行结果，
因此解析时必须读取 SSE 的 `event:` 行来分流，否则工具事件会被静默丢弃。

所有 Agent 逻辑（ReAct 循环、工具调用、LLM 决策）都在 Hermes 侧完成。
本模块只负责：
1. 发送 OpenAI 格式的请求
2. 解析 SSE 流式响应（含自定义事件）
3. 产出结构化事件供上层中继
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx

from app.core.config import settings
from app.services import hermes_cache
from app.utils.logger import logger


@dataclass
class GatewayEvent:
    """
    网关产出的结构化事件

    类型:
    - message_start: 开始接收
    - content_delta: 内容增量
    - tool_start: 工具开始执行
    - tool_result: 工具执行完成
    - message_end: 消息结束（含 usage）
    - error: 发生错误
    """

    event: str
    content: str = ""
    tool_name: str = ""
    tool_args: str = ""
    tool_output: str = ""
    tool_call_id: str = ""  # 用于 tool_start / tool_result 配对
    usage: Dict[str, int] = field(default_factory=dict)
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# Hermes 自定义工具进度事件名（实测得出，非 OpenAI 标准）
HERMES_TOOL_PROGRESS_EVENT = "hermes.tool.progress"


class GatewayError(Exception):
    """
    上游调用失败

    Attributes:
        message: 可安全返回前端的简短描述
        status_code: 上游 HTTP 状态码（无则为 0）
        unavailable: 上游整体不可用（未配置 / 连不上 / 版本不支持）时为 True
    """

    def __init__(self, message: str, status_code: int = 0, unavailable: bool = False):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.unavailable = unavailable


def _status_of(value: Any) -> str:
    """从健康检查项的多种形态中提取状态字符串"""
    if isinstance(value, dict):
        return str(value.get("status", value.get("state", "unknown")))
    if isinstance(value, bool):
        return "ok" if value else "error"
    return str(value)


# 允许透出给前端的计数型字段（只取数值，避免泄漏路径、配置值与载荷）
_HEALTH_COUNT_KEYS = (
    "active_runs",
    "active_api_runs",
    "pending_notifications",
    "active_delegations",
    "jobs",
    "sessions",
)


def _summarize_health(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    清洗 /health/detailed 响应

    只保留：整体状态、就绪标记、检查项名称+状态、计数型指标。
    路径、凭据、配置值、命令与原始错误信息一律不透出。
    """
    status = str(raw.get("status", "unknown"))
    result: Dict[str, Any] = {"status": status}

    readiness = raw.get("readiness") or {}
    if isinstance(readiness, dict):
        result["ready"] = bool(
            readiness.get("ready", readiness.get("ok", status == "ok"))
        )
        checks = readiness.get("checks")
        if isinstance(checks, dict):
            result["checks"] = [
                {"name": str(name), "status": _status_of(value)}
                for name, value in checks.items()
            ]
        elif isinstance(checks, list):
            result["checks"] = [
                {
                    "name": str(item.get("name", "")),
                    "status": _status_of(item.get("status", item)),
                }
                for item in checks
                if isinstance(item, dict)
            ]
    else:
        result["ready"] = status == "ok"

    counts: Dict[str, int] = {}
    for key in _HEALTH_COUNT_KEYS:
        value = raw.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            counts[key] = int(value)
        elif isinstance(value, list):
            counts[key] = len(value)
        elif isinstance(value, dict):
            inner = value.get("count", value.get("total"))
            if isinstance(inner, (int, float)):
                counts[key] = int(inner)
            else:
                counts[key] = len(value)
    result["counts"] = counts

    # 平台 / 模型等只读展示字段
    for key in ("platform", "model", "profile", "version"):
        value = raw.get(key)
        if isinstance(value, (str, int, float)):
            result[key] = value

    return result


class HermesGateway:
    """
    Hermes API Server 客户端

    参考文档: docs/hermes-migration-plan .md - 3.2 Gateway 完整代码
    接口: POST /v1/chat/completions, stream=True
    """

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self._client = client
        self._own_client = client is None
        self._base_url = settings.HERMES_API_URL.rstrip("/")
        self._api_key = settings.HERMES_API_KEY
        self._model = settings.HERMES_MODEL
        self._timeout = settings.HERMES_REQUEST_TIMEOUT

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=float(self._timeout),
                    write=10.0,
                    pool=5.0,
                ),
                verify=False,  # 自签名证书
            )
        return self._client

    def _headers(self, accept: str = "text/event-stream") -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": accept,
        }

    @property
    def _origin(self) -> str:
        """
        站点根地址（去掉 /v1 后缀）

        HERMES_API_URL 形如 http://host:8642/v1，而 /health 与 /api/jobs
        都挂在根路径下，因此需要回退一级。
        """
        base = self._base_url.rstrip("/")
        return base[: -len("/v1")] if base.endswith("/v1") else base

    # ==================== 通用 JSON 请求 ====================

    async def _request_json(
        self,
        method: str,
        url: str,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: float = 15.0,
    ) -> Any:
        """
        发送普通 JSON 请求并解析响应

        Raises:
            GatewayError: 未配置 / 连不上 / 上游报错 / 响应非 JSON
        """
        if not self._base_url:
            raise GatewayError("Hermes API Server 未配置", unavailable=True)

        client = await self._get_client()
        try:
            response = await client.request(
                method,
                url,
                headers=self._headers(accept="application/json"),
                json=json_body,
                timeout=timeout,
            )
        except httpx.ConnectError as e:
            logger.error(f"无法连接 Hermes API Server: {e}")
            raise GatewayError("无法连接 Hermes API Server", unavailable=True) from e
        except httpx.TimeoutException as e:
            logger.error(f"Hermes API 请求超时: {url}")
            raise GatewayError("Hermes API 请求超时", unavailable=True) from e
        except Exception as e:  # noqa: BLE001
            logger.error(f"Hermes API 请求异常: {e}")
            raise GatewayError(f"Hermes API 请求失败: {e}", unavailable=True) from e

        if response.status_code == 404 or response.status_code == 405:
            raise GatewayError(
                "当前 Hermes 版本不支持该能力", status_code=response.status_code
            )
        if response.status_code >= 400:
            body = (response.text or "")[:500]
            logger.error(f"Hermes API 返回错误 {response.status_code}: {body}")
            raise GatewayError(
                f"Hermes API 错误 {response.status_code}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as e:
            logger.error(f"Hermes API 响应不是合法 JSON: {url}")
            raise GatewayError("Hermes API 响应格式异常") from e

    # ==================== 能力发现 / 模型 / 健康 ====================

    async def get_capabilities(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GET /v1/capabilities —— 机器可读的能力清单

        结果缓存 TTL 秒；上游故障时返回上一次成功结果（stale-while-error）。
        """
        if not force_refresh:
            hit, value = hermes_cache.get_fresh(hermes_cache.KEY_CAPABILITIES)
            if hit:
                return value

        try:
            data = await self._request_json("GET", f"{self._base_url}/capabilities")
        except GatewayError:
            stale = hermes_cache.get_stale(hermes_cache.KEY_CAPABILITIES)
            if stale is not None:
                logger.warning("capabilities 上游失败，返回缓存结果")
                return stale
            raise

        result = data if isinstance(data, dict) else {}
        hermes_cache.set_value(hermes_cache.KEY_CAPABILITIES, result)
        return result

    async def get_models(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GET /v1/models —— 可用模型列表

        Returns:
            {"model": "hermes-agent", "models": [{"id": "...", "name": "..."}]}
        """
        if not force_refresh:
            hit, value = hermes_cache.get_fresh(hermes_cache.KEY_MODELS)
            if hit:
                return value

        try:
            data = await self._request_json("GET", f"{self._base_url}/models")
        except GatewayError:
            stale = hermes_cache.get_stale(hermes_cache.KEY_MODELS)
            if stale is not None:
                logger.warning("models 上游失败，返回缓存结果")
                return stale
            raise

        raw_items = (data or {}).get("data", []) if isinstance(data, dict) else []
        models: List[Dict[str, str]] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get("id") or item.get("name") or "")
            if not model_id:
                continue
            models.append(
                {
                    "id": model_id,
                    "name": str(item.get("name") or model_id),
                    "owned_by": str(item.get("owned_by") or "hermes"),
                }
            )

        result = {"model": self._model, "models": models}
        hermes_cache.set_value(hermes_cache.KEY_MODELS, result)
        return result

    async def get_health(self) -> Dict[str, Any]:
        """GET /health —— 轻量存活探针"""
        try:
            data = await self._request_json("GET", f"{self._origin}/health", timeout=8.0)
        except GatewayError as e:
            return {"status": "unreachable", "error": e.message}
        return {
            "status": str((data or {}).get("status", "unknown")),
            "api_url": self._base_url,
        }

    async def get_health_detailed(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        GET /health/detailed —— 就绪检查

        只向调用方暴露**状态与计数**，不透出路径、凭据、配置值或原始错误。
        """
        if not force_refresh:
            hit, value = hermes_cache.get_fresh(hermes_cache.KEY_HEALTH_DETAIL)
            if hit:
                return value

        try:
            data = await self._request_json(
                "GET", f"{self._origin}/health/detailed", timeout=10.0
            )
        except GatewayError:
            stale = hermes_cache.get_stale(hermes_cache.KEY_HEALTH_DETAIL)
            if stale is not None:
                logger.warning("health/detailed 上游失败，返回缓存结果")
                return stale
            raise

        result = _summarize_health(data if isinstance(data, dict) else {})
        hermes_cache.set_value(hermes_cache.KEY_HEALTH_DETAIL, result)
        return result

    # ==================== Runs API ====================

    async def create_run(
        self,
        user_input: str,
        session_id: str = "",
        instructions: str = "",
    ) -> Dict[str, Any]:
        """
        POST /v1/runs —— 提交一次 agent run

        Returns:
            {"run_id": "...", "status": "started"}
        """
        payload: Dict[str, Any] = {"input": user_input}
        if session_id:
            payload["session_id"] = session_id
        if instructions:
            payload["instructions"] = instructions

        data = await self._request_json(
            "POST", f"{self._base_url}/runs", json_body=payload, timeout=30.0
        )
        return {
            "run_id": str((data or {}).get("run_id", "")),
            "status": str((data or {}).get("status", "started")),
        }

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        """GET /v1/runs/{run_id} —— 轮询 run 状态"""
        data = await self._request_json("GET", f"{self._base_url}/runs/{run_id}")
        return data if isinstance(data, dict) else {}

    async def stop_run(self, run_id: str) -> Dict[str, Any]:
        """
        POST /v1/runs/{run_id}/stop —— 请求中断正在运行的 run

        上游立即返回 {"status": "stopping"}，实际停止发生在下一个安全中断点。
        """
        data = await self._request_json(
            "POST", f"{self._base_url}/runs/{run_id}/stop", timeout=10.0
        )
        return {
            "run_id": run_id,
            "status": str((data or {}).get("status", "stopping")),
        }

    # ==================== Jobs API（后台计划任务） ====================

    def _jobs_url(self, job_id: str = "", action: str = "") -> str:
        """拼接 /api/jobs 系列路径（注意不是 /v1 前缀）"""
        url = f"{self._origin}/api/jobs"
        if job_id:
            url = f"{url}/{job_id}"
        if action:
            url = f"{url}/{action}"
        return url

    async def list_jobs(self) -> Dict[str, Any]:
        """GET /api/jobs —— 列出所有计划任务"""
        data = await self._request_json("GET", self._jobs_url())
        if isinstance(data, list):
            return {"jobs": data, "total": len(data)}
        return {"jobs": (data or {}).get("jobs", []), "total": (data or {}).get("total", 0)}

    async def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST /api/jobs —— 创建计划任务"""
        data = await self._request_json(
            "POST", self._jobs_url(), json_body=payload, timeout=20.0
        )
        return data if isinstance(data, dict) else {"job": data}

    async def update_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """PATCH /api/jobs/{job_id} —— 部分更新"""
        data = await self._request_json(
            "PATCH", self._jobs_url(job_id), json_body=payload, timeout=20.0
        )
        return data if isinstance(data, dict) else {"job": data}

    async def delete_job(self, job_id: str) -> Dict[str, Any]:
        """DELETE /api/jobs/{job_id} —— 删除任务（同时取消进行中的 run）"""
        data = await self._request_json(
            "DELETE", self._jobs_url(job_id), timeout=20.0
        )
        return data if isinstance(data, dict) else {"ok": True}

    async def control_job(self, job_id: str, action: str) -> Dict[str, Any]:
        """
        POST /api/jobs/{job_id}/{action}

        action: pause | resume | run
        """
        if action not in ("pause", "resume", "run"):
            raise GatewayError(f"不支持的任务操作: {action}", status_code=400)
        data = await self._request_json(
            "POST", self._jobs_url(job_id, action), timeout=20.0
        )
        return data if isinstance(data, dict) else {"ok": True}

    # ==================== 核心：流式 Chat ====================

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        model: str = "",
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[GatewayEvent, None]:
        """
        流式调用 Hermes API Server

        实测 Hermes 通过**两种通道**产出数据：

        1. OpenAI 标准 chunk（帧内无 `event:` 行）
           `delta.content` 为文本增量。
        2. 自定义事件 `event: hermes.tool.progress`
           {"tool": "terminal", "label": "ls -la", "toolCallId": "call_xxx", "status": "running"}
           {"tool": "terminal", "toolCallId": "call_xxx", "status": "completed"}

        重要：Hermes **不使用** OpenAI 的 `delta.tool_calls` 协议，
        且正文阶段 `finish_reason` 始终为 null。若只按标准协议解析，
        工具事件会被当成"无 choices 的空 chunk"静默丢弃 —— 因此必须读取
        `event:` 行来分流。

        Args:
            messages: OpenAI 格式的消息列表
            model: 模型名（空则用默认）
            tools: 工具列表（Hermes 内置工具，一般不需要）
            temperature: 温度
            max_tokens: 最大 token 数

        Yields:
            GatewayEvent: 结构化事件
        """
        url = f"{self._base_url}/chat/completions"
        model = model or self._model

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        client = await self._get_client()

        try:
            accumulated_content = ""
            # OpenAI 标准 tool_calls 协议的累积状态（兼容通道 1）
            current_tool_id = ""
            current_tool_name = ""
            current_tool_args = ""
            chunk_count = 0
            usage: Dict[str, int] = {}

            async with client.stream(
                "POST", url, headers=self._headers(), json=payload
            ) as response:
                response.raise_for_status()

                # 连接建立成功后才通知前端开始接收，
                # 避免"连接失败"场景下先发 message_start 再发 error
                yield GatewayEvent(event="message_start")

                buffer = ""
                # 当前 SSE 帧的事件名（SSE 规范：无 event 行时默认为 message）
                frame_event = ""
                stream_done = False

                async for raw_bytes in response.aiter_bytes():
                    if stream_done:
                        continue
                    buffer += raw_bytes.decode("utf-8", errors="replace")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.rstrip("\r")

                        # 空行标志一个 SSE 帧结束 -> 重置事件名
                        if not line.strip():
                            frame_event = ""
                            continue

                        # 必须先读取 event 行，否则自定义事件会被误判为标准 chunk
                        if line.startswith("event:"):
                            frame_event = line[6:].strip()
                            continue

                        if not line.startswith("data:"):
                            continue  # 忽略注释行等

                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            stream_done = True
                            break

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        chunk_count += 1

                        # ---- 通道 2：Hermes 自定义工具进度事件 ----
                        if frame_event == HERMES_TOOL_PROGRESS_EVENT:
                            for ev in self._parse_tool_progress(chunk):
                                yield ev
                            continue

                        # ---- 通道 1：OpenAI 标准 chunk ----
                        choices = chunk.get("choices", [])
                        if not choices:
                            # 可能是 usage chunk（Hermes 实测不下发 usage）
                            if "usage" in chunk:
                                usage = chunk["usage"]
                            continue

                        delta = choices[0].get("delta") or {}

                        # 文本内容
                        content = delta.get("content")
                        if content:
                            accumulated_content += content
                            yield GatewayEvent(event="content_delta", content=content)

                        # 工具调用（标准协议；Hermes 当前不用，保留以兼容）
                        for tc in delta.get("tool_calls") or []:
                            tc_id = tc.get("id", "")
                            tc_function = tc.get("function") or {}
                            if tc_id and tc_id != current_tool_id:
                                # 遇到新工具：先把上一个收尾
                                if current_tool_id:
                                    yield GatewayEvent(
                                        event="tool_start",
                                        tool_name=current_tool_name,
                                        tool_args=current_tool_args,
                                        tool_call_id=current_tool_id,
                                    )
                                current_tool_id = tc_id
                                current_tool_name = tc_function.get("name", "")
                                current_tool_args = tc_function.get("arguments", "")
                            else:
                                # 同一工具的 arguments 增量
                                current_tool_args += tc_function.get("arguments", "")

                        # finish_reason：收尾最后一个尚未发出的工具调用
                        finish_reason = choices[0].get("finish_reason")
                        if finish_reason in ("tool_calls", "stop") and current_tool_id:
                            yield GatewayEvent(
                                event="tool_start",
                                tool_name=current_tool_name,
                                tool_args=current_tool_args,
                                tool_call_id=current_tool_id,
                            )
                            current_tool_id = ""
                            current_tool_name = ""
                            current_tool_args = ""

                        if "usage" in chunk:
                            usage = chunk["usage"]

                # ---- 流结束：冲刷残留数据 ----
                # 1) 缓冲区中可能残留一行没有以 \n 结尾的数据
                residue = buffer.strip()
                if residue.startswith("data:"):
                    ds = residue[5:].strip()
                    if ds and ds != "[DONE]":
                        try:
                            chunk = json.loads(ds)
                            if frame_event == HERMES_TOOL_PROGRESS_EVENT:
                                for ev in self._parse_tool_progress(chunk):
                                    yield ev
                        except json.JSONDecodeError:
                            pass
                # 2) 标准协议下最后一个工具可能还没来得及发出
                if current_tool_id:
                    yield GatewayEvent(
                        event="tool_start",
                        tool_name=current_tool_name,
                        tool_args=current_tool_args,
                        tool_call_id=current_tool_id,
                    )

        except httpx.ConnectError as e:
            logger.error(f"无法连接 Hermes API Server: {e}")
            yield GatewayEvent(
                event="error", error=f"无法连接 Hermes API Server: {e}"
            )
            return
        except httpx.TimeoutException:
            logger.error("Hermes API Server 请求超时")
            yield GatewayEvent(event="error", error="请求超时")
            return
        except httpx.HTTPStatusError as e:
            error_body = ""
            try:
                error_body = e.response.text[:500]
            except Exception:
                pass
            logger.error(f"Hermes API 返回错误: {e.response.status_code} {error_body}")
            yield GatewayEvent(
                event="error",
                error=f"API 错误 {e.response.status_code}: {error_body}",
            )
            return
        except Exception as e:
            logger.error(f"Hermes API 调用异常: {e}", exc_info=True)
            yield GatewayEvent(event="error", error=str(e))
            return

        # 最终事件
        yield GatewayEvent(
            event="message_end",
            content=accumulated_content,
            usage=usage,
            metadata={"chunk_count": chunk_count},
        )

    # ==================== 工具函数 ====================

    @staticmethod
    def _parse_tool_progress(chunk: Dict[str, Any]) -> List[GatewayEvent]:
        """
        解析 Hermes 自定义工具进度事件 -> tool_start / tool_result

        入参样例:
          {"tool": "terminal", "emoji": "...", "label": "ls -la",
           "toolCallId": "call_xxx", "status": "running"}
          {"tool": "terminal", "toolCallId": "call_xxx", "status": "completed"}

        注意 Hermes 不回传工具执行结果内容：completed 帧里只有工具名与 ID。
        因此 tool_output 只能拿到 running 帧的 label（可能是空），
        这里如实置空，不做伪造；调用方据此把工具标记为完成即可。

        Returns:
            GatewayEvent 列表（0 或 1 个元素）
        """
        tool = chunk.get("tool", "")
        call_id = chunk.get("toolCallId", "") or chunk.get("tool_call_id", "")
        status = chunk.get("status", "")
        label = chunk.get("label", "")
        emoji = chunk.get("emoji", "")

        meta: Dict[str, Any] = {"status": status}
        if emoji:
            meta["emoji"] = emoji

        if status in ("running", "started", "pending"):
            return [
                GatewayEvent(
                    event="tool_start",
                    tool_name=tool,
                    tool_args=label,
                    tool_call_id=call_id,
                    metadata={**meta, "label": label},
                )
            ]

        if status in ("completed", "failed", "error", "cancelled"):
            return [
                GatewayEvent(
                    event="tool_result",
                    tool_name=tool,
                    tool_output=label,
                    tool_call_id=call_id,
                    metadata=meta,
                )
            ]

        return []

    async def close(self):
        """关闭内部 HTTP 客户端"""
        if self._own_client and self._client:
            await self._client.aclose()
            self._client = None


# ==================== 单例 ====================

_gateway: Optional[HermesGateway] = None


def get_hermes_gateway(client: Optional[httpx.AsyncClient] = None) -> HermesGateway:
    """获取 Hermes 网关单例"""
    global _gateway
    if _gateway is None:
        _gateway = HermesGateway(client)
    return _gateway
