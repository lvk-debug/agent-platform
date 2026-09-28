"""
Paper Agent 提示词

- planner：把用户主题拆解成可执行的检索计划
- synthesis：基于论文与证据生成可追溯的 Markdown 综述
- claim：从论文正文抽取带证据的 claim（M2）
- comparison：多篇论文对比维度对齐（M3）
- eval：评测裁判（M4）
"""

from __future__ import annotations

from app.services.paper_agent.tools import PaperMetadata

# 综述必须遵循的 Markdown 骨架
REVIEW_STRUCTURE = """# 主题综述：{topic}

## 结论先行

## 代表论文

| Paper | Year | Core Idea | Evidence |
|:---|:---:|:---|:---|

## 方法谱系

## 实验设置对比

## 局限与开放问题

## 延伸阅读
"""

PLANNER_SYSTEM = """你是一个学术论文检索规划助手。

任务：根据用户的综述主题，产出一份简短的检索计划，用于指导 arXiv 检索。

要求：
1. 只输出计划本身，不要解释、不要客套、不要 Markdown 代码块包裹。
2. 计划包含 2-4 条要点，每条形如「检索词/角度 —— 关注什么」。
3. 检索词必须是适合 arXiv 检索的英文关键词短语，用空格或 AND/OR 连接。
4. 覆盖主题的核心方法、代表性系统/模型、以及评测或应用角度。
5. 总长度控制在 200 字以内。"""

SYNTHESIS_SYSTEM = """你是论文综述写作助手，服务于科研与算法调研。

硬性要求（违反视为不合格）：
1. 只依据给定的论文元数据与证据写内容，禁止编造论文、作者、数字或结论。
2. 每一条实质性结论、每一篇被提及的论文，都必须附上原文链接作为证据。
3. 证据不足时，必须明确写出「证据不足/尚不明确」，而不是推测或补全。
4. 不得跨越不同任务、不同数据集去硬比较指标；比较时必须注明各自的实验条件。
5. 严格按给定的 Markdown 骨架输出，保留全部二级标题，不要增删标题。
6. 用中文写作，论文标题保留英文原文。"""

# ---------------- M2：claim 抽取 ----------------

CLAIM_EXTRACTION_SYSTEM = """你是论文结构化信息抽取助手。

任务：从论文正文中抽取关键论断（claim），每条都必须有原文依据。

要求：
1. 只输出 JSON 数组，不要任何解释文字，不要用代码块包裹。
2. 每项格式：
   {"claim": "一句话论断",
    "category": "contribution|method|dataset|metric|limitation",
    "evidence": {"page": 页码数字或 null, "section": "所属章节标题",
                 "quote": "不超过 40 字的原文摘录"}}
3. category 含义：contribution=论文贡献，method=方法，dataset=数据集，
   metric=实验指标，limitation=局限。
4. quote 必须是正文中真实出现的片段，不得改写或杜撰；找不到原文依据的论断直接丢弃。
5. 每类最多 3 条，总共不超过 12 条。"""

# ---------------- M3：对比 ----------------

COMPARISON_SYSTEM = """你是论文对比分析助手。

任务：把多篇论文按可比较的维度对齐，产出对比矩阵。

要求：
1. 只输出 JSON 对象，不要解释文字，不要用代码块包裹。
2. 输出格式：
   {"dimensions": ["维度1", "维度2", ...],
    "rows": [{"paper": "论文标题", "url": "原文链接",
              "values": {"维度1": "取值（注明实验条件）",
                         "维度2": "取值或 n/a"},
              "evidence": {"page": 页码或 null, "section": "章节"}}]}
3. 维度建议包含：任务、方法、数据集、核心指标、实验条件。
4. 不同任务或不同数据集的指标不可直接比较，必须在取值中注明条件；
   无法判断时填 "n/a"，不要猜测。
5. 行数与输入的论文数一致，不要遗漏或新增论文。"""

# ---------------- M4：评测裁判 ----------------

EVAL_JUDGE_SYSTEM = """你是论文综述质量评审助手，只依据给定内容打分，不得引入外部知识。

任务：对一次论文综述运行的产出按三个维度打分。

输出 JSON 对象，不要解释文字，不要用代码块包裹：
{"citation_precision": 0-1 的小数,
 "coverage_score": 0-1 的小数,
 "hallucination_rate": 0-1 的小数}

评分标准：
- citation_precision：被提及的论文/结论是否都有可核查的原文链接或页码证据。
  每条结论都有证据为 1.0，部分缺失按比例扣减。
- coverage_score：是否覆盖了方法、数据集、实验、局限四个方面的程度（各占 0.25）。
- hallucination_rate：无证据支撑的断言占全部断言的比例。
  全部有证据为 0.0，全部无证据为 1.0。"""


def build_planner_prompt(topic: str, max_papers: int) -> str:
    """构建 planner 用户消息"""
    return (
        f"综述主题：{topic}\n"
        f"目标论文数量：约 {max_papers} 篇\n\n"
        "请输出检索计划。"
    )


def _format_papers(papers: list[PaperMetadata], abstract_limit: int = 800) -> str:
    """把论文元数据格式化为给 LLM 的上下文（摘要截断，防止超长上下文）"""
    blocks = []
    for idx, paper in enumerate(papers, start=1):
        abstract = paper.abstract or ""
        if len(abstract) > abstract_limit:
            abstract = abstract[:abstract_limit] + "…"
        authors = ", ".join(paper.authors[:5])
        if len(paper.authors) > 5:
            authors += " 等"
        blocks.append(
            f"[{idx}] 标题：{paper.title}\n"
            f"年份：{paper.year or '未知'}\n"
            f"作者：{authors or '未知'}\n"
            f"链接：{paper.url}\n"
            f"分类：{', '.join(paper.categories) or '未知'}\n"
            f"摘要：{abstract}"
        )
    return "\n\n".join(blocks)


def _format_claims(claims: list[dict], limit: int = 24) -> str:
    """把带证据的 claim 格式化为综述上下文"""
    if not claims:
        return "（本次未抽取到 PDF 正文证据，结论只能基于标题与摘要，请保守表述）"
    lines = []
    for claim in claims[:limit]:
        ev = claim.get("evidence") or {}
        page = f"p{ev['page']}" if ev.get("page") else "页码未知"
        lines.append(
            f"- [{claim.get('category', 'contribution')}] {claim.get('claim', '')}\n"
            f"  来源：{claim.get('title', '')}\n"
            f"  章节：{ev.get('section') or '未知'} | {page}\n"
            f"  原文：{ev.get('quote', '')}\n"
            f"  链接：{claim.get('url', '')}"
        )
    return "\n".join(lines)


def build_synthesis_prompt(
    topic: str,
    plan: str,
    papers: list[PaperMetadata],
    claims: list[dict] | None = None,
    comparison: dict | None = None,
) -> str:
    """构建 synthesis 用户消息（M2/M3 后补充证据与对比）"""
    structure = REVIEW_STRUCTURE.format(topic=topic)
    parts = [
        f"综述主题：{topic}\n",
        f"检索计划：\n{plan or '（无）'}\n",
        f"检索到的论文（共 {len(papers)} 篇）：\n\n{_format_papers(papers)}\n",
        f"论文正文证据（claim 级）：\n{_format_claims(claims or [])}\n",
    ]
    if comparison and comparison.get("rows"):
        parts.append(f"多论文对比矩阵：\n{_format_comparison(comparison)}\n")

    parts.append(
        f"请严格按以下骨架输出 Markdown 综述：\n\n{structure}\n\n"
        "补充要求：\n"
        "- 「代表论文」表格中 Evidence 列填原文链接。\n"
        "- 引用正文证据时，在句末标注 (章节, pX) 形式；页码未知则只标章节。\n"
        "- 「方法谱系」按技术路线的演进关系组织，提及论文时附链接。\n"
        "- 「实验设置对比」优先使用对比矩阵；若论文任务/数据集不可比，"
        "请明确说明并分小节描述。\n"
        "- 「局限与开放问题」需区分「论文自述的局限」与「你基于证据的判断」。\n"
        "- 「延伸阅读」列出未充分展开但相关的方向与代表性链接。\n"
        "- 若检索结果不足以支撑某个小节，直接写明「证据不足」。"
    )
    return "\n".join(parts)


def _format_comparison(comparison: dict) -> str:
    """把对比矩阵格式化为可读文本"""
    dimensions = comparison.get("dimensions") or []
    rows = comparison.get("rows") or []
    lines = ["| " + " | ".join(["Paper", *dimensions]) + " |",
             "|" + "|".join([":---"] * (len(dimensions) + 1)) + "|"]
    for row in rows:
        values = row.get("values") or {}
        cells = [row.get("paper", ""), *[str(values.get(d, "n/a")) for d in dimensions]]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def build_claim_prompt(
    sections: list[dict],
    *,
    paper_title: str = "",
    max_chars: int = 6000,
    max_sections: int = 6,
) -> str:
    """
    构建 claim 抽取的用户消息

    同时限制章节数与总字符数：推理模型输出很慢，
    负载过大会直接把节点拖到超时。
    """
    blocks = []
    used = 0
    for section in sections[:max_sections]:
        page = f"p{section['page']}" if section.get("page") else "页码未知"
        header = f"## 章节：{section.get('section', '未知')}（{page}）"
        text = section.get("text", "")
        remaining = max_chars - used
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining] + "…"
        blocks.append(f"{header}\n{text}")
        used += len(text)

    return (
        f"论文标题：{paper_title or '未知'}\n\n"
        f"正文（按章节）：\n\n" + "\n\n".join(blocks) + "\n\n"
        "请按系统要求输出 JSON 数组。"
    )


def build_comparison_prompt(entries: list[dict], *, topic: str = "") -> str:
    """构建对比矩阵的用户消息"""
    blocks = []
    for idx, entry in enumerate(entries, start=1):
        claims = entry.get("claims") or []
        lines = []
        for claim in claims[:8]:
            evidence = claim.get("evidence") or {}
            page = evidence.get("page")
            section = evidence.get("section") or "未知"
            loc = f"{section}, p{page}" if page else section
            lines.append(
                f"  - [{claim.get('category', '')}] {claim.get('claim', '')} ({loc})"
            )
        claim_text = "\n".join(lines) or "  （无正文证据）"
        blocks.append(
            f"[{idx}] 标题：{entry.get('title', '')}\n"
            f"链接：{entry.get('url', '')}\n"
            f"年份：{entry.get('year', '未知')}\n"
            f"论断：\n{claim_text}"
        )

    return (
        f"对比主题：{topic or '（未指定）'}\n\n"
        f"待对比论文：\n\n" + "\n\n".join(blocks) + "\n\n"
        "请按系统要求输出 JSON 对象。"
    )


def build_eval_judge_prompt(
    topic: str, review_markdown: str, claims: list[dict]
) -> str:
    """构建评测裁判的用户消息"""
    evidence_lines = "\n".join(
        f"- {c.get('claim', '')}（证据：{c.get('evidence', {})})"
        for c in (claims or [])[:20]
    ) or "（无 claim 级证据）"
    review = (review_markdown or "")[:6000] or "（无综述内容）"
    return (
        f"综述主题：{topic}\n\n"
        f"综述正文：\n{review}\n\n"
        f"可用的 claim 级证据：\n{evidence_lines}\n\n"
        "请按系统要求输出 JSON 对象。"
    )
