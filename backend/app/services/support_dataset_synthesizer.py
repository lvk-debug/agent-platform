"""
用 DeepEval Synthesizer 生成客服评测数据集

从客服知识库上下文批量生成 Goldens（客户问题 input + 标准答案 expected_output
+ 参考上下文 context），转为 SupportGoldenCase，打 "synthesized" 标签，用于低成本
扩充评测覆盖。生成与主请求链路解耦，仅由 scripts/generate_support_eval_dataset.py
按需调用，结果缓存为 JSONL，离线套件加载时与人工/历史集合并。

deepeval 为可选依赖：未安装时 generate_support_goldens 直接返回空列表。
"""

from __future__ import annotations

import logging
import math
from typing import Any, List

from app.services.support_eval_golden import SupportGoldenCase

logger = logging.getLogger(__name__)


def _to_support_golden(golden: Any, index: int) -> SupportGoldenCase:
    """把一个 DeepEval Golden 转为 SupportGoldenCase"""
    contexts: List[str] = list(getattr(golden, "context", []) or [])
    references = [{"document_name": "knowledge", "content": c} for c in contexts if c]
    return SupportGoldenCase(
        case_id=f"synthesized-{index:04d}",
        query=getattr(golden, "input", "") or "",
        expected_answer=getattr(golden, "expected_output", "") or "",
        references=references,
        intent=None,
        tags=["synthesized"],
    )


def generate_support_goldens(
    model: Any,
    contexts: List[List[str]],
    max_goldens: int = 50,
) -> List[SupportGoldenCase]:
    """
    用 DeepEval Synthesizer 从知识库上下文生成 Goldens

    Args:
        model: app.models.model.Model 实例（平台配置的裁判模型）
        contexts: 上下文组列表，每组是一段知识库文本列表，对应一个潜在场景
        max_goldens: 生成上限

    Returns:
        SupportGoldenCase 列表（tags=["synthesized"]）
    """
    try:
        from deepeval.synthesizer import Synthesizer
    except ImportError:
        logger.warning("未安装 deepeval，跳过 Synthesizer 生成")
        return []

    from app.services.paper_agent.deepeval_model import (
        build_deepeval_model_from_db as build_support_deepeval_model,
        configure_deepeval_env,
    )

    configure_deepeval_env()
    try:
        deepeval_model = build_support_deepeval_model(model)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"构建 Synthesizer 裁判模型失败，跳过生成: {e}")
        return []

    if not contexts:
        return []

    synthesizer = Synthesizer(model=deepeval_model)
    # deepeval 4.x：generate_goldens_from_contexts 返回 List[Golden]，
    # 参数是「每上下文生成数」；这里把 max_goldens 视为总量预算做换算。
    per_context = max(1, math.ceil(max_goldens / max(len(contexts), 1)))
    try:
        goldens = synthesizer.generate_goldens_from_contexts(
            contexts=contexts,
            include_expected_output=True,
            max_goldens_per_context=per_context,
        )
    except AttributeError:
        # 兼容更旧版 deepeval 的 generate_goldens(contexts=..., max_goldens=...) API
        try:
            synthesizer.generate_goldens(contexts=contexts, max_goldens=max_goldens)  # type: ignore[attr-defined]
            goldens = getattr(synthesizer, "synthesizer_goldens", []) or []
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Synthesizer 生成失败: {e}")
            return []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Synthesizer 生成失败: {e}")
        return []

    goldens = list(goldens or [])[:max_goldens]
    cases = [_to_support_golden(g, i) for i, g in enumerate(goldens)]
    logger.info(f"Synthesizer 生成 {len(cases)} 条客服评测 Goldens")
    return cases


async def contexts_from_kb_search(
    kb_search_fn: Any,
    seed_queries: List[str],
    top_k: int = 4,
) -> List[List[str]]:
    """
    辅助：用知识库检索结果组装 Synthesizer 的 contexts

    Args:
        kb_search_fn: 形如 async search(query, top_k) -> List[Dict] 的协程函数
        seed_queries: 种子问题（可来自人工黄金集的 query）
        top_k: 每个种子问题检索的片段数

    Returns:
        上下文组列表，每组是一段文本列表
    """
    contexts: List[List[str]] = []
    for q in seed_queries:
        try:
            results = await kb_search_fn(q, top_k=top_k)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"知识库检索失败（{q}）: {e}")
            continue
        texts = [r.get("content") or "" for r in results if r.get("content")]
        if texts:
            contexts.append(texts)
    return contexts
