"""
Paper Agent 评测执行器（里程碑4）

对每条评测用例跑一次完整流水线，计算指标并落盘：
- paper_relevance@k：前 k 篇命中期盼关键词的比例
- citation_precision：结论是否都有可核查证据（优先 LLM 裁判，失败时按 claim 证据比例）
- coverage_score：是否覆盖方法/数据集/实验/局限四个方面
- hallucination_rate：无证据断言占比
- avg_latency / avg_steps：成本与效率

产物写入 <PAPER_AGENT_EVAL_DIR>/<eval_id>/：
- results.jsonl   每条用例的明细
- eval_summary.md 汇总报告
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.paper_agent.deepeval_metrics import (
    DEEPEVAL_METRIC_KEYS,
    measure_case,
    resolve_backend,
)
from app.services.paper_agent.eval_cases import REFUSAL_HINTS, EvalCase
from app.services.paper_agent.graph import build_paper_agent_graph
from app.services.paper_agent.prompts import (
    EVAL_JUDGE_SYSTEM,
    build_eval_judge_prompt,
)
from app.services.paper_agent.tools import message_text
from app.utils.logger import logger

RELEVANCE_K = 5
COVERAGE_SECTIONS = ("方法", "数据集", "实验", "局限")


def _relevance_at_k(
    papers: list[Any], terms: list[str], k: int = RELEVANCE_K
) -> float | None:
    """前 k 篇中命中期盼关键词的比例"""
    if not papers:
        return 0.0 if terms else None
    top = papers[:k]
    hits = 0
    for paper in top:
        text = f"{paper.title} {paper.abstract}".lower()
        if any(term.lower() in text for term in terms):
            hits += 1
    return hits / len(top)


def _coverage_score(review: str) -> float:
    """综述是否覆盖方法/数据集/实验/局限"""
    if not review:
        return 0.0
    present = sum(1 for section in COVERAGE_SECTIONS if section in review)
    return present / len(COVERAGE_SECTIONS)


def _claim_based_metrics(claims: list[dict]) -> tuple[float | None, float | None]:
    """
    基于 claim 证据的兜底指标

    Returns:
        (citation_precision, hallucination_rate)
    """
    if not claims:
        return None, None
    supported = 0
    for claim in claims:
        evidence = claim.get("evidence") or {}
        if evidence.get("quote") and claim.get("url"):
            supported += 1
    precision = supported / len(claims)
    return precision, 1.0 - precision


def _refusal_ok(review: str) -> bool:
    """安全类用例：是否出现说明限制/拒绝的表述"""
    return any(hint in (review or "") for hint in REFUSAL_HINTS)


class PaperAgentEvaluator:
    """评测执行器"""

    def __init__(self, llm: Any, deepeval_model: Any = None):
        self.llm = llm
        # DeepEval 裁判模型（可选，为 None 时只用内置指标）
        self.deepeval_model = deepeval_model

    async def _judge(self, topic: str, review: str, claims: list[dict]) -> dict:
        """用 LLM 裁判打分，失败返回空 dict（由兜底指标补位）"""
        from langchain_core.messages import HumanMessage, SystemMessage

        try:
            resp = await self.llm.ainvoke(
                [
                    SystemMessage(content=EVAL_JUDGE_SYSTEM),
                    HumanMessage(
                        content=build_eval_judge_prompt(topic, review, claims)
                    ),
                ]
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"PaperAgent 评测裁判调用失败: {e}")
            return {}

        content = message_text(resp)
        start, end = content.find("{"), content.rfind("}")
        if start == -1 or end <= start:
            return {}
        try:
            parsed = json.loads(content[start : end + 1])
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def run_case(
        self,
        case: EvalCase,
        *,
        with_pdf: bool = False,
        backend: str = "builtin",
    ) -> dict[str, Any]:
        """执行单条用例并返回指标"""
        # 延迟导入，避免 service 与 evaluator 循环依赖
        from app.services.paper_agent.service import PaperAgentService

        started = time.time()
        initial = PaperAgentService._build_initial_state(
            case.topic,
            settings.PAPER_AGENT_MAX_PAPERS,
            case.year_from,
            case.year_to,
            source="arxiv",
            with_pdf=with_pdf,
            output_dir="",
        )
        graph = build_paper_agent_graph(self.llm)

        try:
            state = await graph.ainvoke(initial)
        except Exception as e:  # noqa: BLE001
            logger.error(f"PaperAgent 用例执行失败 {case.case_id}: {e}", exc_info=True)
            return {
                "case_id": case.case_id,
                "category": case.category,
                "topic": case.topic,
                "status": "failed",
                "error": str(e),
                "duration_ms": int((time.time() - started) * 1000),
            }

        duration_ms = int((time.time() - started) * 1000)
        ranked = state.get("ranked") or []
        review = state.get("review_markdown") or ""
        claims = state.get("claims") or []
        trace = state.get("trace") or []

        relevance = _relevance_at_k(ranked, case.expected_terms)
        coverage = _coverage_score(review)
        claim_precision, claim_hallucination = _claim_based_metrics(claims)

        judged = await self._judge(case.topic, review, claims)
        citation_precision = judged.get("citation_precision")
        if not isinstance(citation_precision, (int, float)):
            citation_precision = claim_precision
        hallucination_rate = judged.get("hallucination_rate")
        if not isinstance(hallucination_rate, (int, float)):
            hallucination_rate = claim_hallucination
        if isinstance(judged.get("coverage_score"), (int, float)):
            coverage = float(judged["coverage_score"])

        result = {
            "case_id": case.case_id,
            "category": case.category,
            "topic": case.topic,
            "status": "completed",
            "duration_ms": duration_ms,
            "paper_count": len(ranked),
            "claim_count": len(claims),
            "steps": len(trace),
            "paper_relevance_at_k": relevance,
            "citation_precision": citation_precision,
            "coverage_score": coverage,
            "hallucination_rate": hallucination_rate,
        }

        # 检索失败等原因要能在结果里看到，否则只看到指标为 0 却不知为何
        if state.get("error"):
            result["error"] = state["error"]

        # 类型专属校验
        if case.expect_no_results:
            result["no_results_handled"] = (len(ranked) == 0) and ("未检索到" in review)
        if case.expect_refusal:
            result["refusal_handled"] = _refusal_ok(review)

        # DeepEval 指标（同步 API，放到线程执行避免阻塞事件循环）
        if backend in ("deepeval", "both") and self.deepeval_model is not None:
            result["deepeval"] = await asyncio.to_thread(
                measure_case, case, state, self.deepeval_model
            )

        return result

    async def run(
        self,
        eval_id: str,
        cases: list[EvalCase],
        *,
        with_pdf: bool = False,
        backend: str | None = None,
    ) -> dict[str, Any]:
        """执行全部用例，落盘并汇总"""
        resolved = resolve_backend(backend)
        logger.info(f"PaperAgent 评测后端: {resolved}")

        eval_dir = Path(settings.PAPER_AGENT_EVAL_DIR) / eval_id
        eval_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, Any]] = []
        for case in cases:
            logger.info(f"PaperAgent 评测用例开始: {case.case_id} ({case.category})")
            results.append(
                await self.run_case(case, with_pdf=with_pdf, backend=resolved)
            )

        results_path = eval_dir / "results.jsonl"
        with results_path.open("w", encoding="utf-8") as f:
            for item in results:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        summary = self._summarize(results)
        summary_path = eval_dir / "eval_summary.md"
        summary_path.write_text(
            self._render_summary(eval_id, results, summary), encoding="utf-8"
        )

        logger.info(f"PaperAgent 评测完成: {eval_id}, {len(results)} 条用例")
        return {
            "eval_id": eval_id,
            "total_cases": len(results),
            "summary": summary,
            "output_dir": str(eval_dir),
            "results_path": str(results_path),
            "summary_path": str(summary_path),
            "results": results,
        }

    @staticmethod
    def _summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
        """汇总各项指标的均值与分类统计"""
        def _avg(key: str) -> float | None:
            values = [
                r[key] for r in results if isinstance(r.get(key), (int, float))
            ]
            return round(statistics.fmean(values), 4) if values else None

        completed = [r for r in results if r.get("status") == "completed"]
        by_category: dict[str, dict[str, Any]] = {}
        for item in completed:
            bucket = by_category.setdefault(
                item["category"], {"count": 0, "relevance": [], "coverage": []}
            )
            bucket["count"] += 1
            if isinstance(item.get("paper_relevance_at_k"), (int, float)):
                bucket["relevance"].append(item["paper_relevance_at_k"])
            if isinstance(item.get("coverage_score"), (int, float)):
                bucket["coverage"].append(item["coverage_score"])

        for bucket in by_category.values():
            bucket["avg_relevance"] = (
                round(statistics.fmean(bucket["relevance"]), 4)
                if bucket["relevance"]
                else None
            )
            bucket["avg_coverage"] = (
                round(statistics.fmean(bucket["coverage"]), 4)
                if bucket["coverage"]
                else None
            )
            bucket.pop("relevance")
            bucket.pop("coverage")

        summary = {
            "completed_cases": len(completed),
            "failed_cases": len(results) - len(completed),
            "paper_relevance_at_k": _avg("paper_relevance_at_k"),
            "citation_precision": _avg("citation_precision"),
            "coverage_score": _avg("coverage_score"),
            "hallucination_rate": _avg("hallucination_rate"),
            "avg_latency_ms": _avg("duration_ms"),
            "avg_steps": _avg("steps"),
            "no_results_handled_rate": _rate(results, "no_results_handled"),
            "refusal_handled_rate": _rate(results, "refusal_handled"),
            "by_category": by_category,
        }
        deepeval = _deepeval_summary(results)
        if deepeval:
            summary["deepeval"] = deepeval
        return summary

    @staticmethod
    def _render_summary(
        eval_id: str, results: list[dict[str, Any]], summary: dict[str, Any]
    ) -> str:
        """渲染汇总报告"""
        rows = "\n".join(
            "| {case_id} | {category} | {paper_count} | {rel} | {cov} | {dur} |".format(
                case_id=r.get("case_id", "-"),
                category=r.get("category", "-"),
                paper_count=r.get("paper_count", "-"),
                rel=_fmt(r.get("paper_relevance_at_k")),
                cov=_fmt(r.get("coverage_score")),
                dur=r.get("duration_ms", "-"),
            )
            for r in results
        )
        category_rows = "\n".join(
            f"| {name} | {data['count']} | {_fmt(data['avg_relevance'])} | "
            f"{_fmt(data['avg_coverage'])} |"
            for name, data in (summary.get("by_category") or {}).items()
        )
        deepeval = summary.get("deepeval")
        deepeval_section = ""
        if deepeval:
            metric_rows = "\n".join(
                f"| {key} | {_fmt(value)} |"
                for key, value in (deepeval.get("averages") or {}).items()
            )
            deepeval_section = (
                "\n## DeepEval 指标（与内置指标对照）\n\n"
                f"- 参与用例数：{deepeval['cases_measured']}\n"
                f"- 指标失败次数：{deepeval['error_count']}\n\n"
                f"| 指标 | 均值 |\n|:---|:---|\n{metric_rows}\n"
            )
        return f"""# Paper Agent 评测报告

- eval_id：{eval_id}
- 用例总数：{summary['completed_cases'] + summary['failed_cases']}
- 完成/失败：{summary['completed_cases']} / {summary['failed_cases']}

## 总体指标

| 指标 | 值 |
|:---|:---|
| paper_relevance@{RELEVANCE_K} | {_fmt(summary['paper_relevance_at_k'])} |
| citation_precision | {_fmt(summary['citation_precision'])} |
| coverage_score | {_fmt(summary['coverage_score'])} |
| hallucination_rate | {_fmt(summary['hallucination_rate'])} |
| avg_latency (ms) | {_fmt(summary['avg_latency_ms'])} |
| avg_steps | {_fmt(summary['avg_steps'])} |
| 无结果处理率 | {_fmt(summary['no_results_handled_rate'])} |
| 安全拒绝率 | {_fmt(summary['refusal_handled_rate'])} |

## 分类统计

| 类别 | 用例数 | 平均相关性 | 平均覆盖率 |
|:---|:---|:---|:---|
{category_rows}
{deepeval_section}
## 用例明细

| case | 类别 | 论文数 | 相关性 | 覆盖率 | 耗时(ms) |
|:---|:---|:---|:---|:---|:---|
{rows}
"""


def _deepeval_summary(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    """汇总 DeepEval 指标均值；本次没有 DeepEval 结果时返回 None"""
    measured = [
        r["deepeval"]
        for r in results
        if isinstance(r.get("deepeval"), dict) and r["deepeval"].get("available")
    ]
    if not measured:
        return None

    averages: dict[str, float] = {}
    for key in DEEPEVAL_METRIC_KEYS:
        values = [
            item["scores"][key]
            for item in measured
            if isinstance(item.get("scores", {}).get(key), (int, float))
        ]
        if values:
            averages[key] = round(statistics.fmean(values), 4)

    return {
        "cases_measured": len(measured),
        "averages": averages,
        "error_count": sum(len(item.get("errors") or {}) for item in measured),
    }


def _rate(results: list[dict[str, Any]], key: str) -> float | None:
    """统计布尔型校验的通过率"""
    values = [r[key] for r in results if isinstance(r.get(key), bool)]
    if not values:
        return None
    return round(sum(1 for v in values if v) / len(values), 4)


def _fmt(value: Any) -> str:
    """格式化指标值"""
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def build_evaluator(
    model: Any, deepeval_model: Any = None
) -> PaperAgentEvaluator | None:
    """根据数据库 Model 构建评测执行器"""
    from app.services.paper_agent.service import PaperAgentService

    try:
        llm = PaperAgentService._build_llm(model)
    except ValueError as e:
        logger.warning(f"PaperAgent 评测无法构建 LLM: {e}")
        return None
    return PaperAgentEvaluator(llm, deepeval_model=deepeval_model)
