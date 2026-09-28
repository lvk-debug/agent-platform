"""
客服 DeepEval 离线回归套件

用途：对客服评测数据集（人工黄金集 + 历史导出 + Synthesizer 生成）跑 DeepEval 指标，
做质量回归与数据校验。数据由 eval_golden.load_support_goldens() 合并加载。

运行方式：
    deepeval test run backend/test/test_support_deepeval.py
    # 或
    uv run pytest backend/test/test_support_deepeval.py

环境变量：
    SUPPORT_EVAL_CASE_IDS   可选，逗号分隔的 case_id 子集；默认跑全部有标准答案的用例
    SUPPORT_EVAL_MODEL_ID   可选，指定裁判模型 model_id；默认取平台客服评测模型

守卫：
- 未安装 deepeval → 依赖 deepeval 的用例 skip（importorskip 在 fixture 内）
- 无可用裁判模型   → 依赖模型的用例 skip
"""

from __future__ import annotations

import os
from typing import List

import pytest

from app.services.support_eval_golden import SupportGoldenCase, load_support_goldens


def _select_cases() -> List[SupportGoldenCase]:
    """选取有标准答案的用例（历史导出集无标准答案，不作为正样本回归）"""
    cases = load_support_goldens()
    ids = "synthesized-0000,synthesized-0001,synthesized-0002,synthesized-0003" # os.getenv("SUPPORT_EVAL_CASE_IDS", "").strip()
    if ids:
        wanted = {i.strip() for i in ids.split(",") if i.strip()}
        cases = [c for c in cases if c.case_id in wanted]
    return [c for c in cases if c.expected_answer]


CASES = _select_cases()


@pytest.fixture(scope="module")
def deepeval_model():
    """构建平台裁判模型；未装 deepeval 或无可用模型时跳过"""
    pytest.importorskip("deepeval", reason="未安装 deepeval：uv sync --extra paper-eval")

    from app.core.database import SessionLocal
    from app.models.model import Model
    from app.services.support_deepeval_eval import build_support_deepeval_model
    from app.services.support_evaluation import SupportEvaluationService

    db = SessionLocal()
    try:
        model_id = os.getenv("SUPPORT_EVAL_MODEL_ID", "").strip()
        row = None
        if model_id:
            row = db.query(Model).filter(Model.model_id == model_id).first()
        else:
            _cfg, row, _provider = SupportEvaluationService(db)._resolve_judge_model()
        if row is None:
            pytest.skip("无可用裁判模型（请配置平台模型或设置 SUPPORT_EVAL_MODEL_ID）")
        return build_support_deepeval_model(row)
    finally:
        db.close()


@pytest.mark.parametrize("case", CASES, ids=[c.case_id for c in CASES])
def test_support_answer_quality(case: SupportGoldenCase, deepeval_model):
    """用 DeepEval 指标校验单条客服样本（以标准答案为正样本做指标 sanity）"""
    from deepeval import assert_test

    from app.services.support_deepeval_eval import (
        build_support_metrics,
        build_support_test_case,
    )

    test_case = build_support_test_case(
        query=case.query,
        answer=case.expected_answer,
        references=case.references,
        expected_answer=case.expected_answer,
        intent=case.intent,
        name=case.case_id,
    )
    metrics = [
        metric
        for _, metric in build_support_metrics(
            deepeval_model,
            has_context=bool(test_case.retrieval_context),
            with_expected=bool(test_case.expected_output),
        )
    ]
    assert_test(test_case, metrics)


def test_support_dataset_sanity():
    """数据集结构校验（不消耗 LLM）：case_id 唯一、字段完整、标签正确"""
    all_cases = load_support_goldens()
    assert all_cases, "评测数据集为空（应有至少人工黄金集）"

    ids = [c.case_id for c in all_cases]
    assert len(ids) == len(set(ids)), "case_id 存在重复"

    for c in all_cases:
        assert c.query, f"{c.case_id} 缺少 query"
        assert isinstance(c.references, list), f"{c.case_id} references 非列表"
        assert isinstance(c.tags, list) and c.tags, f"{c.case_id} tags 为空"
