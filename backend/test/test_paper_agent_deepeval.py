"""
Paper Agent DeepEval 回归套件

用途：在 CI 或本地做论文综述质量的回归验证，与运行时评测（/evals）共用
同一套用例（eval_cases.py）与指标映射（deepeval_metrics.py）。

运行方式：
    deepeval test run backend/test/test_paper_agent_deepeval.py
    # 或
    uv run pytest backend/test/test_paper_agent_deepeval.py

环境变量：
    PAPER_AGENT_EVAL_MODEL_ID    必填，平台 models.model_id（裁判与综述共用）
    PAPER_AGENT_EVAL_CASE_IDS    可选，默认 "ts-01,fl-01"

守卫（避免 CI 因缺少依赖或模型而失败）：
- 未安装 deepeval  → importorskip
- 未配置模型        → skip
"""

from __future__ import annotations

import asyncio
import os

import pytest

from app.services.paper_agent.deepeval_metrics import (
    build_metrics,
    build_test_case,
)
from app.services.paper_agent.eval_cases import get_cases

# deepeval 为可选依赖：未安装时整个模块跳过
pytest.importorskip("deepeval", reason="未安装 deepeval：uv sync --extra paper-eval")

from app.core.config import settings  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.model import Model  # noqa: E402
from app.services.paper_agent.deepeval_model import build_deepeval_model  # noqa: E402
from app.services.paper_agent.graph import build_paper_agent_graph  # noqa: E402
from app.services.paper_agent.service import PaperAgentService  # noqa: E402

MODEL_ID = "mimo-v2.5"
PAPER_AGENT_EVAL_CASE_IDS = os.getenv("PAPER_AGENT_EVAL_CASE_IDS", "ts-01,fl-01")
CASE_IDS = [
    item.strip()
    for item in PAPER_AGENT_EVAL_CASE_IDS.split(",")
    if item.strip()
]

pytestmark = pytest.mark.skipif(
    not MODEL_ID,
    reason="需设置环境变量 PAPER_AGENT_EVAL_MODEL_ID（平台 models.model_id）",
)


@pytest.fixture(scope="module")
def llm():
    """加载平台模型并构建 LangChain ChatModel；模型不存在时跳过"""
    db = SessionLocal()
    try:
        model = db.query(Model).filter(Model.model_id == MODEL_ID).first()
        if model is None:
            pytest.skip(f"模型不存在: {MODEL_ID}")
        return PaperAgentService._build_llm(model)
    finally:
        db.close()


def _run_pipeline(chat_model, case):
    """跑一次完整流水线，返回终态"""
    initial = PaperAgentService._build_initial_state(
        case.topic,
        settings.PAPER_AGENT_MAX_PAPERS,
        case.year_from,
        case.year_to,
        source="arxiv",
        with_pdf=False,
        output_dir="",
    )
    graph = build_paper_agent_graph(chat_model)
    return asyncio.run(graph.ainvoke(initial))


def _selected_cases():
    return get_cases(case_ids=CASE_IDS)


@pytest.mark.parametrize(
    "case", _selected_cases(), ids=[c.case_id for c in _selected_cases()]
)
def test_paper_agent_review_quality(case, llm):
    """用 DeepEval 指标校验单条用例的综述质量"""
    from deepeval import assert_test

    if getattr(case, "expect_no_results", False):
        # 无结果类用例的正确行为是"诚实说明限制"：
        # 此时上下文必然为空、综述必然写"证据不足"，DeepEval 指标不适用
        pytest.skip("无结果类用例有专门判定口径，不适用 DeepEval 指标")

    state = _run_pipeline(llm, case)

    deepeval_model = build_deepeval_model(llm, MODEL_ID)
    test_case = build_test_case(case, state)
    metrics = [
        metric
        for _, metric in build_metrics(
            deepeval_model,
            with_expected_output=bool(getattr(test_case, "expected_output", None)),
            has_context=bool(getattr(test_case, "retrieval_context", None)),
        )
    ]

    assert_test(test_case, metrics)
