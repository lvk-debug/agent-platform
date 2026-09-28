"""
Paper Agent 产物落盘

每次运行写入 outputs/paper-agent/<run_id>/：
- review.md        综述正文
- papers.bib       BibTeX
- trace.jsonl      流水线轨迹（供 M4 评测复用）
- evidence.jsonl   证据记录（M2 起含 claim 级证据）
- comparison.csv   对比表（M3 起按对齐维度填充）
- eval_summary.md  本次运行的耗时/步骤等统计
- pdfs/            下载的 PDF（M2）
- sections.jsonl   解析出的章节正文（M2，便于回溯）
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from app.core.config import settings
from app.services.paper_agent.tools import PaperMetadata
from app.utils.logger import logger

# M1 只有论文级证据；M2 解析 PDF 后补充 claim 级证据
EVIDENCE_NOTE = "M1 论文级证据；M2 将补充 claim 级证据（page/section/quote）"


def ensure_run_dir(run_id: str) -> Path:
    """创建并返回本次运行的产物目录"""
    run_dir = Path(settings.PAPER_AGENT_OUTPUT_DIR) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _eprint_id(paper_id: str) -> str:
    """去掉 arXiv 版本号后缀"""
    return re.sub(r"v\d+$", "", paper_id or "")


def _cite_key(paper: PaperMetadata) -> str:
    """生成 BibTeX cite key：第一作者姓 + 年份 + 标题首词"""
    author = paper.authors[0] if paper.authors else "anon"
    last_name = re.sub(r"[^a-z0-9]", "", author.split()[-1].lower()) if author else ""
    year = paper.year or "nd"
    first_word = ""
    if paper.title:
        first_word = re.sub(r"[^a-z0-9]", "", paper.title.split()[0].lower())
    return f"{last_name or 'anon'}{year}{first_word}"


def _bibtex_entry(paper: PaperMetadata) -> str:
    """生成一条 BibTeX 记录"""
    title = (paper.title or "").replace("{", "").replace("}", "")
    authors = " and ".join(paper.authors) if paper.authors else "Unknown"
    entry_type = "misc" if paper.source == "arxiv" else "article"
    lines = [
        f"@{entry_type}{{{_cite_key(paper)},",
        f"  title  = {{{title}}},",
        f"  author = {{{authors}}},",
        f"  year   = {{{paper.year or 'n.d.'}}},",
    ]
    if paper.doi:
        lines.append(f"  doi    = {{{paper.doi}}},")
    if paper.source == "arxiv":
        lines.append(f"  eprint = {{{_eprint_id(paper.paper_id)}}},")
        lines.append("  archivePrefix = {arXiv},")
    lines.append(f"  url    = {{{paper.url}}},")
    lines.append("}")
    return "\n".join(lines)


def _write_trace(run_dir: Path, run_id: str, topic: str, trace: list[dict]) -> Path:
    path = run_dir / "trace.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for entry in trace:
            payload = {"run_id": run_id, "topic": topic, **entry}
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return path


def _write_evidence(
    run_dir: Path, run_id: str, ranked: list[PaperMetadata], claims: list[dict]
) -> Path:
    """
    写入证据记录

    论文级（元数据 + 原文链接）始终写入；
    M2 解析 PDF 后追加 claim 级证据（page / section / quote）。
    """
    path = run_dir / "evidence.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for paper in ranked:
            f.write(
                json.dumps(
                    {
                        "run_id": run_id,
                        "level": "paper",
                        "paper_id": paper.paper_id,
                        "title": paper.title,
                        "year": paper.year,
                        "url": paper.url,
                        "pdf_url": paper.pdf_url,
                        "source": paper.source,
                        "note": EVIDENCE_NOTE,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        for claim in claims:
            f.write(
                json.dumps(
                    {"run_id": run_id, "level": "claim", **claim},
                    ensure_ascii=False,
                )
                + "\n"
            )
    return path


def _write_sections(run_dir: Path, sections_by_paper: dict) -> Path | None:
    """写入解析出的章节正文（M2），便于人工回溯"""
    if not sections_by_paper:
        return None
    path = run_dir / "sections.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for paper_id, sections in sections_by_paper.items():
            for section in sections:
                f.write(
                    json.dumps(
                        {"paper_id": paper_id, **section},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    return path


def _write_comparison(
    run_dir: Path, ranked: list[PaperMetadata], comparison: dict | None
) -> Path:
    """
    写入对比表

    M3 有对比矩阵时按对齐维度输出；否则退化为基础列。
    """
    path = run_dir / "comparison.csv"
    year_by_title = {p.title: p.year for p in ranked}
    dimensions = (comparison or {}).get("dimensions") or []
    rows = (comparison or {}).get("rows") or []

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if rows and dimensions:
            writer.writerow(["paper", "year", "url", *dimensions])
            for row in rows:
                values = row.get("values") or {}
                writer.writerow(
                    [
                        row.get("paper", ""),
                        year_by_title.get(row.get("paper", ""), "") or "",
                        row.get("url", ""),
                        *[str(values.get(d, "n/a")) for d in dimensions],
                    ]
                )
        else:
            writer.writerow(
                ["paper", "year", "url", "task", "dataset", "method", "metric", "notes"]
            )
            for paper in ranked:
                writer.writerow(
                    [
                        paper.title,
                        paper.year or "",
                        paper.url,
                        "",
                        "",
                        "",
                        "",
                        "未生成对比矩阵（需解析 PDF 得到 claim 后由 comparator 生成）",
                    ]
                )
    return path


def _write_eval_summary(
    run_dir: Path,
    run_id: str,
    topic: str,
    ranked: list[PaperMetadata],
    claims: list[dict],
    trace: list[dict],
    duration_ms: int,
) -> Path:
    """写入本次运行的统计摘要（完整评测见 M4 的评测运行）"""
    node_rows = "\n".join(
        f"| {entry.get('node', '-')} | {entry.get('duration_ms', '-')} |"
        for entry in trace
    )
    content = f"""# 运行统计

- run_id：{run_id}
- 主题：{topic}
- 检索论文数：{len(ranked)}
- claim 级证据数：{len(claims)}
- 流水线步骤数：{len(trace)}
- 总耗时：{duration_ms} ms

## 指标说明

完整评测（引用准确率 / 覆盖率 / 幻觉率）由里程碑4的评测运行产出，
见 `POST /paper-agent/evals` 与 `{settings.PAPER_AGENT_EVAL_DIR}`。

## 节点耗时

| 节点 | 耗时(ms) |
|:---|:---|
{node_rows}
"""
    path = run_dir / "eval_summary.md"
    path.write_text(content, encoding="utf-8")
    return path


def _write_plan(run_dir: Path, plan: str) -> str:
    path = run_dir / "plan.md"
    path.write_text(plan or "", encoding="utf-8")
    return str(path)


def write_outputs(
    run_dir: Path,
    *,
    run_id: str,
    topic: str,
    plan: str,
    papers: list[PaperMetadata],
    ranked: list[PaperMetadata],
    review_markdown: str,
    trace: list[dict],
    duration_ms: int,
    claims: list[dict] | None = None,
    sections_by_paper: dict | None = None,
    comparison: dict | None = None,
) -> dict[str, str]:
    """
    写入全部产物，返回各产物路径

    Args:
        papers: 检索去重后的全部论文
        ranked: 排序后用于综述的论文
        claims: M2 claim 级证据
        sections_by_paper: M2 解析出的章节正文
        comparison: M3 对比矩阵
    """
    claims = claims or []
    sections_by_paper = sections_by_paper or {}

    review_path = run_dir / "review.md"
    review_path.write_text(review_markdown or "", encoding="utf-8")

    bib_path = run_dir / "papers.bib"
    bib_path.write_text(
        "\n\n".join(_bibtex_entry(p) for p in ranked) + ("\n" if ranked else ""),
        encoding="utf-8",
    )

    trace_path = _write_trace(run_dir, run_id, topic, trace)
    evidence_path = _write_evidence(run_dir, run_id, ranked, claims)
    comparison_path = _write_comparison(run_dir, ranked, comparison)
    eval_path = _write_eval_summary(
        run_dir, run_id, topic, ranked, claims, trace, duration_ms
    )
    sections_path = _write_sections(run_dir, sections_by_paper)

    paths = {
        "dir": str(run_dir),
        "review": str(review_path),
        "papers_bib": str(bib_path),
        "evidence": str(evidence_path),
        "comparison": str(comparison_path),
        "trace": str(trace_path),
        "eval_summary": str(eval_path),
        "plan": _write_plan(run_dir, plan),
    }
    if sections_path:
        paths["sections"] = str(sections_path)

    logger.info(f"PaperAgent 产物已写入: {run_dir}")
    return paths
