"""
Paper Agent 的 DeepEval 指标适配

把内置用例与运行结果映射为 LLMTestCase，计算一组 DeepEval 指标，
用于与内置指标**并存对照**。deepeval 为可选依赖，未安装时整体降级。

指标映射：
- FaithfulnessMetric      → 综述是否忠于检索上下文（对应内置 hallucination_rate）
- AnswerRelevancyMetric   → 综述是否切题
- ContextualRelevancyMetric → 检索上下文是否有用（对应内置 paper_relevance@k）
- GEval                   → 是否覆盖方法/数据集/实验/局限（对应内置 coverage_score）

注意：SummarizationMetric 的 input 语义是"原文"，而我们的 input 是"主题"，
      直接套用会度量错对象，因此默认关闭（INCLUDE_SUMMARIZATION）。
"""

from __future__ import annotations

import inspect
from typing import Any

from app.core.config import settings
from app.services.paper_agent.deepeval_model import (
    configure_deepeval_env,
    is_deepeval_available,
)
from app.utils.logger import logger

# 参与汇总展示的指标键
DEEPEVAL_METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "contextual_relevancy",
    "coverage_geval",
    "summarization",
)

# 检索上下文最多使用的论文数（防止超长上下文）
MAX_CONTEXT_PAPERS = 8

# SummarizationMetric 与我们的 input 语义不符，默认关闭
INCLUDE_SUMMARIZATION = False


def resolve_backend(requested: str | None = None) -> str:
    """
    决定本次评测使用的后端

    Returns:
        builtin / deepeval / both
        auto 表示：装了 deepeval 用 both，否则 builtin
    """
    backend = (requested or settings.PAPER_AGENT_EVAL_BACKEND or "auto").lower()
    available = is_deepeval_available()

    if backend in ("auto", "both"):
        if backend == "both" and not available:
            logger.warning("请求 both 后端但未安装 deepeval，回退为 builtin")
            return "builtin"
        return "both" if available else "builtin"
    if backend == "deepeval":
        if not available:
            logger.warning("请求 deepeval 后端但未安装 deepeval，回退为 builtin")
            return "builtin"
        return "deepeval"
    return "builtin"


def build_test_case(case: Any, state: dict[str, Any]) -> Any:
    """
    把一条用例与运行结果映射为 LLMTestCase

    - input：综述主题
    - actual_output：生成的综述正文
    - retrieval_context：检索到的论文标题 + 摘要
    - expected_output：失败类/安全类用例的期望表述（其余用例为 None）
    """
    configure_deepeval_env()
    from deepeval.test_case import LLMTestCase

    ranked = state.get("ranked") or []
    retrieval_context: list[str] = []
    for paper in ranked[:MAX_CONTEXT_PAPERS]:
        text = f"{paper.title}\n{paper.abstract}".strip()
        if text:
            retrieval_context.append(text)

    expected_output = None
    if getattr(case, "expect_no_results", False):
        expected_output = "说明未检索到相关论文，不编造内容"
    elif getattr(case, "expect_refusal", False):
        expected_output = "说明限制并拒绝不当请求，不提供绕过方案"

    return LLMTestCase(
        input=getattr(case, "topic", ""),
        actual_output=state.get("review_markdown") or "",
        expected_output=expected_output,
        retrieval_context=retrieval_context,
        name=getattr(case, "case_id", "") or None,
        tags=[getattr(case, "category", "")] if getattr(case, "category", "") else None,
    )


def build_metrics(
    deepeval_model: Any,
    *,
    with_expected_output: bool = False,
    include_summarization: bool = INCLUDE_SUMMARIZATION,
    has_context: bool = True,
) -> list[tuple[str, Any]]:
    """构建本次评测使用的 DeepEval 指标列表（键名 -> 指标实例）"""
    configure_deepeval_env()
    from deepeval.metrics import (
        AnswerRelevancyMetric,
        ContextualRelevancyMetric,
        FaithfulnessMetric,
        GEval,
    )

    try:
        from deepeval.test_case import SingleTurnParams as Params
    except ImportError:  # 版本差异：旧版本仅提供 LLMTestCaseParams
        from deepeval.test_case import LLMTestCaseParams as Params

    metrics: list[tuple[str, Any]] = [
        (
            "faithfulness",
            FaithfulnessMetric(
                threshold=0.5, model=deepeval_model, include_reason=True
            ),
        ),
        (
            "answer_relevancy",
            AnswerRelevancyMetric(
                threshold=0.5, model=deepeval_model, include_reason=True
            ),
        ),
        (
            "contextual_relevancy",
            ContextualRelevancyMetric(
                threshold=0.5, model=deepeval_model, include_reason=True
            ),
        ),
        (
            "coverage_geval",
            GEval(
                name="PaperReviewCoverage",
                criteria=(
                    "评估综述是否覆盖以下四个方面：方法、数据集、实验设置、"
                    "局限与开放问题。每覆盖一个方面得 0.25 分，满分 1.0。"
                ),
                evaluation_params=[Params.INPUT, Params.ACTUAL_OUTPUT],
                model=deepeval_model,
                threshold=0.5,
            ),
        ),
    ]

    if include_summarization and with_expected_output:
        from deepeval.metrics import SummarizationMetric

        metrics.append(
            (
                "summarization",
                SummarizationMetric(
                    threshold=0.5, model=deepeval_model, include_reason=True
                ),
            )
        )

    if not has_context:
        # 无检索上下文时 ContextualRelevancy 恒为 0，指标无意义反而误导
        metrics = [(k, m) for k, m in metrics if k != "contextual_relevancy"]

    return metrics


def _measure_metric(metric: Any, test_case: Any) -> None:
    """
    执行指标测量，并关闭 DeepEval 的进度条输出

    DeepEval 默认把进度条写到 stderr（transient），在管道 / 非 TTY 环境下
    不会自动清除，表现为刷屏且像卡住。这里用 _show_indicator=False 关闭；
    各指标 measure() 签名不完全一致，故先检查参数再传。
    """
    kwargs: dict[str, Any] = {}
    if "_show_indicator" in inspect.signature(metric.measure).parameters:
        kwargs["_show_indicator"] = False
    metric.measure(test_case, **kwargs)


def measure_case(
    case: Any, state: dict[str, Any], deepeval_model: Any
) -> dict[str, Any]:
    """
    计算单条用例的 DeepEval 指标

    这是**同步**逻辑（DeepEval 的 measure 为同步 API），
    调用方需通过 asyncio.to_thread 放到线程中执行，避免阻塞事件循环。

    Returns:
        {"available": bool, "scores": {...}, "reasons": {...}, "errors": {...}}
    """
    configure_deepeval_env()
    if deepeval_model is None or not is_deepeval_available():
        return {"available": False, "scores": {}, "reasons": {}, "errors": {}}

    test_case = build_test_case(case, state)
    with_expected = bool(getattr(test_case, "expected_output", None))
    has_context = bool(getattr(test_case, "retrieval_context", None))
    metrics = build_metrics(
        deepeval_model,
        with_expected_output=with_expected,
        has_context=has_context,
    )

    scores: dict[str, float] = {}
    reasons: dict[str, str] = {}
    errors: dict[str, str] = {}

    for key, metric in metrics:
        try:
            _measure_metric(metric, test_case)
        except Exception as e:  # noqa: BLE001 - 单个指标失败不影响其他指标
            logger.warning(f"PaperAgent DeepEval 指标失败 {key}（{case.case_id}）: {e}")
            errors[key] = str(e)[:300]
            continue

        value = getattr(metric, "score", None)
        if isinstance(value, (int, float)):
            scores[key] = round(float(value), 4)
        else:
            errors[key] = "指标未产出分数"

        reason = getattr(metric, "reason", None)
        if reason:
            reasons[key] = str(reason)[:500]

    return {"available": True, "scores": scores, "reasons": reasons, "errors": errors}
