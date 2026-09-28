"""
Paper Agent LangGraph 流水线

完整流水线：
planner → searcher → ranker → pdf_reader → claim_extractor → comparator → synthesis

- planner：LLM 拆解检索计划
- searcher：多源检索（arXiv / Semantic Scholar / OpenAlex）并去重
- ranker：按主题相关性排序
- pdf_reader（M2）：下载并解析公开 PDF，得到 section/page 正文
- claim_extractor（M2）：LLM 抽取带证据的 claim
- comparator（M3）：对齐可比较维度，生成对比矩阵
- synthesis：LLM 生成可追溯的 Markdown 综述

每个节点都会往 state["trace"] 追加一条记录，供评测（M4）与排障使用。
"""

from __future__ import annotations

import asyncio
import operator
import re
import time
from typing import Annotated, Any, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.paper_agent.prompts import (
    PLANNER_SYSTEM,
    SYNTHESIS_SYSTEM,
    build_planner_prompt,
    build_synthesis_prompt,
)
from app.services.paper_agent.tools import (
    PaperMetadata,
    compare_papers,
    download_pdf,
    extract_claims,
    heuristic_comparison,
    message_text,
    parse_pdf,
    search_papers_with_status,
)
from app.utils.logger import logger

# 综述中最多使用的论文数（防止上下文过长）
MAX_PAPERS_FOR_SYNTHESIS = 8

# 单节点 LLM 超时（秒）：任一节点超时只降级该节点，不拖垮整条流水线
PLANNER_TIMEOUT = 45
CLAIM_TIMEOUT = 120
COMPARE_TIMEOUT = 90
SYNTHESIS_TIMEOUT = 150


class PaperAgentState(TypedDict, total=False):
    """流水线状态"""

    topic: str
    max_papers: int
    year_from: int | None
    year_to: int | None
    source: str
    with_pdf: bool
    output_dir: str

    plan: str
    papers: list[PaperMetadata]
    ranked: list[PaperMetadata]

    # M2
    sections_by_paper: dict[str, list[dict[str, Any]]]
    claims: list[dict[str, Any]]

    # M3
    comparison: dict[str, Any] | None

    review_markdown: str
    # add reducer：节点只返回新增的轨迹，LangGraph 自动追加，无需手动拼接
    trace: Annotated[list[dict[str, Any]], operator.add]
    error: str | None


def _now_ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def _trace(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """包装单条轨迹记录（trace 已配 add reducer，返回即追加）"""
    return [entry]


def _topic_terms(topic: str) -> list[str]:
    """
    从主题中提取用于相关性打分的关键词

    中文主题无法按空格切分，整体作为一个 term 参与「包含」匹配。
    """
    terms = [t for t in re.split(r"[^\w]+", topic.lower()) if len(t) > 1]
    if re.search(r"[\u4e00-\u9fff]", topic):
        terms.append(topic.lower())
    return terms or [topic.lower()]


def _relevance_score(paper: PaperMetadata, terms: list[str]) -> float:
    """启发式相关性打分：标题命中加权 + 摘要命中 + 引用数 + 轻微新近度"""
    title = (paper.title or "").lower()
    abstract = (paper.abstract or "").lower()
    text = f"{title} {abstract}"

    score = 0.0
    for term in terms:
        if term in title:
            score += 2.0
        if term in text:
            score += 1.0

    # 被引次数做轻度加权（对数缩放，避免头部论文垄断）
    if paper.citation_count:
        score += min(paper.citation_count, 1000) ** 0.25
    # 新近度：2015 年之后每年 +0.05，最多 +0.5
    if paper.year:
        score += min(max(paper.year - 2015, 0), 10) * 0.05
    return score


def _no_results_review(topic: str) -> str:
    """
    无检索结果时生成的综述

    必须诚实说明限制（而不是让模型凭记忆编造论文），并给出可操作的改进建议。
    """
    return (
        f"# 主题综述：{topic}\n\n"
        "## 结论先行\n\n"
        f"未检索到与「{topic}」相关的论文，未生成实质结论。\n"
        "建议：调整检索关键词（使用英文术语）、放宽年份范围，或稍后重试。\n\n"
        "## 代表论文\n\n暂无。\n\n"
        "## 方法谱系\n\n证据不足。\n\n"
        "## 实验设置对比\n\n证据不足。\n\n"
        "## 局限与开放问题\n\n"
        "本次检索无结果，未形成可评估的证据基础。\n\n"
        "## 延伸阅读\n\n暂无。\n"
    )


async def _planner_text(llm: BaseChatModel, topic: str, max_papers: int) -> str:
    """生成检索计划；超时或失败时回退为直接使用主题检索"""
    try:
        resp = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=PLANNER_SYSTEM),
                    HumanMessage(content=build_planner_prompt(topic, max_papers)),
                ]
            ),
            timeout=PLANNER_TIMEOUT,
        )
        return message_text(resp)
    except TimeoutError:
        logger.warning("PaperAgent planner 超时，回退为直接使用主题检索")
    except Exception as e:  # noqa: BLE001 - 规划失败不应中断流水线
        logger.warning(f"PaperAgent planner 失败，回退为直接使用主题检索: {e}")
    return f"直接以主题「{topic}」检索"


def build_paper_agent_graph(llm: BaseChatModel):
    """
    构建并编译 Paper Agent 流水线

    Args:
        llm: LangChain ChatModel（由 service 根据数据库 Model/Provider 构建）
    """

    async def planner(state: PaperAgentState) -> dict[str, Any]:
        start = time.time()
        topic = state["topic"]
        want = state.get("max_papers", 10)
        plan = await _planner_text(llm, topic, want)

        logger.info(f"PaperAgent planner 完成: {_now_ms(start)}ms")
        return {
            "plan": plan,
            "trace": _trace(
                {"node": "planner", "duration_ms": _now_ms(start), "output": plan},
            ),
        }

    async def searcher(state: PaperAgentState) -> dict[str, Any]:
        start = time.time()
        topic = state["topic"]
        # 多取一些再排序，提升命中质量
        want = max(state.get("max_papers", 10) * 2, settings.PAPER_AGENT_MAX_PAPERS)
        papers, search_error = await search_papers_with_status(
            query=topic,
            max_results=want,
            year_from=state.get("year_from"),
            year_to=state.get("year_to"),
            source=state.get("source", "arxiv"),
        )

        # 检索失败必须显式上报，不能被误判成「确实没有相关论文」
        if papers:
            error = None
        elif search_error:
            error = f"检索失败：{search_error}"
        else:
            error = "未检索到相关论文"
        logger.info(f"PaperAgent searcher 完成: {len(papers)} 篇, {_now_ms(start)}ms")
        return {
            "papers": papers,
            "error": error,
            "trace": _trace(
                {
                    "node": "searcher",
                    "duration_ms": _now_ms(start),
                    "paper_count": len(papers),
                    "titles": [p.title for p in papers],
                },
            ),
        }

    async def ranker(state: PaperAgentState) -> dict[str, Any]:
        start = time.time()
        papers = state.get("papers", [])
        terms = _topic_terms(state["topic"])
        ranked = sorted(papers, key=lambda p: _relevance_score(p, terms), reverse=True)

        logger.info(f"PaperAgent ranker 完成: {len(ranked)} 篇, {_now_ms(start)}ms")
        return {
            "ranked": ranked,
            "trace": _trace(
                {
                    "node": "ranker",
                    "duration_ms": _now_ms(start),
                    "top_titles": [p.title for p in ranked[:10]],
                },
            ),
        }

    async def pdf_reader(state: PaperAgentState) -> dict[str, Any]:
        """M2：下载并解析公开 PDF（受数量上限约束）"""
        start = time.time()
        ranked = state.get("ranked", [])
        sections_by_paper: dict[str, list[dict[str, Any]]] = {}

        if state.get("with_pdf", True):
            output_dir = state.get("output_dir") or settings.PAPER_AGENT_OUTPUT_DIR
            pdf_dir = f"{output_dir}/pdfs"
            limit = settings.PAPER_AGENT_MAX_PDF_PAPERS
            targets = [p for p in ranked if p.pdf_url][:limit]

            for paper in targets:
                result = await download_pdf(paper.pdf_url, pdf_dir)
                if not result.get("path"):
                    logger.warning(
                        f"PaperAgent PDF 跳过（{paper.title}）: {result.get('error')}"
                    )
                    continue
                sections = await parse_pdf(result["path"])
                if sections:
                    sections_by_paper[paper.paper_id] = sections

        logger.info(
            f"PaperAgent pdf_reader 完成: {len(sections_by_paper)} 篇解析, "
            f"{_now_ms(start)}ms"
        )
        return {
            "sections_by_paper": sections_by_paper,
            "trace": _trace(
                {
                    "node": "pdf_reader",
                    "duration_ms": _now_ms(start),
                    "parsed_papers": len(sections_by_paper),
                },
            ),
        }

    async def claim_extractor(state: PaperAgentState) -> dict[str, Any]:
        """M2：从已解析正文抽取带证据的 claim"""
        start = time.time()
        sections_by_paper = state.get("sections_by_paper", {}) or {}
        ranked = state.get("ranked", [])
        index = {p.paper_id: p for p in ranked}

        async def _extract_one(paper_id: str, sections: list[dict[str, Any]]):
            paper = index.get(paper_id)
            try:
                return await asyncio.wait_for(
                    extract_claims(
                        sections,
                        llm,
                        paper_title=paper.title if paper else paper_id,
                        paper_url=paper.url if paper else "",
                        paper_id=paper_id,
                    ),
                    timeout=CLAIM_TIMEOUT,
                )
            except TimeoutError:
                logger.warning(f"PaperAgent claim 抽取超时: {paper_id}")
            except Exception as e:  # noqa: BLE001 - 单篇失败不影响整体
                logger.warning(f"PaperAgent claim 抽取失败 {paper_id}: {e}")
            return []

        # 并发抽取：多篇串行会把整体预算耗尽（实测两篇串行耗时 162s）
        gathered = await asyncio.gather(
            *(_extract_one(pid, sec) for pid, sec in sections_by_paper.items())
        )
        claims = [claim for group in gathered for claim in group]

        logger.info(
            f"PaperAgent claim_extractor 完成: {len(claims)} 条, {_now_ms(start)}ms"
        )
        return {
            "claims": claims,
            "trace": _trace(
                {
                    "node": "claim_extractor",
                    "duration_ms": _now_ms(start),
                    "claim_count": len(claims),
                },
            ),
        }

    async def comparator(state: PaperAgentState) -> dict[str, Any]:
        """M3：生成多论文对比矩阵"""
        start = time.time()
        claims = state.get("claims", []) or []
        ranked = state.get("ranked", [])

        entries: list[dict[str, Any]] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for claim in claims:
            grouped.setdefault(claim.get("paper_id", ""), []).append(claim)

        for paper_id, paper_claims in grouped.items():
            paper = next((p for p in ranked if p.paper_id == paper_id), None)
            fallback = paper_claims[0] if paper_claims else {}
            entries.append(
                {
                    "paper_id": paper_id,
                    "title": paper.title if paper else fallback.get("title", ""),
                    "url": paper.url if paper else fallback.get("url", ""),
                    "year": paper.year if paper else None,
                    "claims": paper_claims,
                }
            )

        comparison = None
        if entries:
            try:
                comparison = await asyncio.wait_for(
                    compare_papers(entries, llm, topic=state.get("topic", "")),
                    timeout=COMPARE_TIMEOUT,
                )
            except TimeoutError:
                logger.warning("PaperAgent comparator 超时，回退为启发式对比")
                comparison = heuristic_comparison(entries)
            except Exception as e:  # noqa: BLE001 - 对比失败不应中断综述
                logger.warning(f"PaperAgent comparator 失败，回退启发式对比: {e}")
                comparison = heuristic_comparison(entries)

        logger.info(f"PaperAgent comparator 完成: {_now_ms(start)}ms")
        return {
            "comparison": comparison,
            "trace": _trace(
                {
                    "node": "comparator",
                    "duration_ms": _now_ms(start),
                    "rows": len(comparison.get("rows", [])) if comparison else 0,
                },
            ),
        }

    async def synthesis(state: PaperAgentState) -> dict[str, Any]:
        start = time.time()
        topic = state["topic"]
        ranked = state.get("ranked", [])

        if not ranked:
            if (state.get("error") or "").startswith("检索失败"):
                # 检索失败不是「没有结果」，不应伪装成无结果综述
                logger.error(f"PaperAgent synthesis 跳过：{state.get('error')}")
                return {
                    "review_markdown": "",
                    "error": state.get("error"),
                    "trace": _trace(
                        {
                            "node": "synthesis",
                            "duration_ms": _now_ms(start),
                            "skipped": True,
                            "reason": "search_failed",
                        },
                    ),
                }
            # 无检索结果时诚实说明限制，避免模型凭记忆编造论文
            review = _no_results_review(topic)
            logger.warning(
                f"PaperAgent synthesis 跳过 LLM 调用: 无检索结果（{topic!r}）"
            )
            return {
                "review_markdown": review,
                "trace": _trace(
                    {
                        "node": "synthesis",
                        "duration_ms": _now_ms(start),
                        "skipped": True,
                        "reason": "no_papers",
                    },
                ),
            }

        selected = ranked[:MAX_PAPERS_FOR_SYNTHESIS]
        try:
            resp = await asyncio.wait_for(
                llm.ainvoke(
                    [
                        SystemMessage(content=SYNTHESIS_SYSTEM),
                        HumanMessage(
                            content=build_synthesis_prompt(
                                topic=topic,
                                plan=state.get("plan", ""),
                                papers=selected,
                                claims=state.get("claims", []),
                                comparison=state.get("comparison"),
                            )
                        ),
                    ]
                ),
                timeout=SYNTHESIS_TIMEOUT,
            )
            review = message_text(resp)
        except Exception as e:  # noqa: BLE001 - 生成失败时保留错误信息
            logger.error(f"PaperAgent synthesis 失败: {e}", exc_info=True)
            return {
                "review_markdown": "",
                "error": f"综述生成失败: {e}",
                "trace": _trace(
                    {
                        "node": "synthesis",
                        "duration_ms": _now_ms(start),
                        "error": str(e),
                    },
                ),
            }

        logger.info(
            f"PaperAgent synthesis 完成: {len(review)} 字符, {_now_ms(start)}ms"
        )
        return {
            "review_markdown": review,
            "trace": _trace(
                {
                    "node": "synthesis",
                    "duration_ms": _now_ms(start),
                    "paper_count": len(selected),
                    "review_chars": len(review),
                },
            ),
        }

    graph = StateGraph(PaperAgentState)
    graph.add_node("planner", planner)
    graph.add_node("searcher", searcher)
    graph.add_node("ranker", ranker)
    graph.add_node("pdf_reader", pdf_reader)
    graph.add_node("claim_extractor", claim_extractor)
    graph.add_node("comparator", comparator)
    graph.add_node("synthesis", synthesis)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "searcher")
    graph.add_edge("searcher", "ranker")
    graph.add_edge("ranker", "pdf_reader")
    graph.add_edge("pdf_reader", "claim_extractor")
    graph.add_edge("claim_extractor", "comparator")
    graph.add_edge("comparator", "synthesis")
    graph.add_edge("synthesis", END)

    return graph.compile()
