"""
DeepEval 与平台模型的适配层

把平台数据库中配置的 Model/Provider 包装成 DeepEval 可用的模型，
使评测裁判与平台其他功能共用同一套模型管理，无需额外配置 API Key。

deepeval 是可选依赖：本模块**不在顶层 import deepeval**，
而是在运行期动态导入，未安装时所有入口安全降级。
"""

from __future__ import annotations

import asyncio
import importlib
import os
from typing import Any

from app.core.config import settings
from app.utils.logger import logger

# DeepEval 关闭遥测的取值（见 deepeval 文档）
_TELEMETRY_OFF = "YES"


def configure_deepeval_env() -> None:
    """在导入 deepeval 之前应用配置（环境变量需在 import 前生效）"""
    if settings.DEEPEVAL_TELEMETRY_OPT_OUT:
        os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", _TELEMETRY_OFF)
    if settings.DEEPEVAL_PER_TASK_TIMEOUT_SECONDS > 0:
        os.environ.setdefault(
            "DEEPEVAL_PER_TASK_TIMEOUT_SECONDS_OVERRIDE",
            str(settings.DEEPEVAL_PER_TASK_TIMEOUT_SECONDS),
        )


def is_deepeval_available() -> bool:
    """deepeval 是否已安装"""
    try:
        importlib.import_module("deepeval")
        return True
    except ImportError:
        return False


def _text_of(resp: Any) -> str:
    """从 LangChain 响应中取文本（兼容推理模型的 reasoning_content）"""
    from app.services.paper_agent.tools import message_text

    return message_text(resp)


def build_deepeval_model(llm: Any, model_name: str = "platform-model") -> Any:
    """
    把 LangChain ChatModel 包装成 DeepEval 可用的模型实例

    Args:
        llm: LangChain ChatModel（需支持 ainvoke）
        model_name: 展示与日志用的模型名
    """
    configure_deepeval_env()
    from deepeval.models.base_model import DeepEvalBaseLLM

    class PlatformDeepEvalLLM(DeepEvalBaseLLM):
        """复用平台已配置模型的 DeepEval 适配器"""

        def __init__(self, chat_model: Any, name: str) -> None:
            self._chat_model = chat_model
            self._name = name

        def load_model(self) -> Any:
            return self._chat_model

        def get_model_name(self) -> str:
            return self._name

        def generate(self, prompt: str) -> str:
            """
            同步生成

            DeepEval 的 measure() 是同步 API，而平台模型是异步接口。
            调用方会在独立线程中执行本方法，因此这里可安全新建事件循环。
            """
            return asyncio.run(self.a_generate(prompt))

        async def a_generate(self, prompt: str) -> str:
            resp = await self._chat_model.ainvoke(prompt)
            return _text_of(resp)

    return PlatformDeepEvalLLM(llm, model_name)


def build_deepeval_model_from_db(model: Any) -> Any:
    """
    从平台数据库的 Model 行构建 DeepEval 模型

    Args:
        model: app.models.model.Model 实例
    """
    from app.services.paper_agent.service import PaperAgentService

    llm = PaperAgentService._build_llm(model)
    name = getattr(model, "model_id", None) or "platform-model"
    logger.info(f"PaperAgent DeepEval 裁判模型: {name}")
    return build_deepeval_model(llm, name)
