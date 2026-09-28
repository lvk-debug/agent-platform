"""
Paper Agent 工具层

M1：search_papers（arXiv，免 API Key）
M2：download_pdf / parse_pdf（复用已安装的 markitdown）/ extract_claims（LLM）
M3：Semantic Scholar + OpenAlex 多源检索、expand_citations、compare_papers

说明：
- 综述渲染（write_review）由 LangGraph 的 synthesis 节点配合 prompts.py 完成。
- 所有外部调用失败均降级为空结果/None，不抛异常，保证流水线整体可用。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings
from app.utils.logger import logger

# 支持的检索源；all 表示多源融合后去重
SUPPORTED_SOURCES = ("arxiv", "semantic_scholar", "openalex", "all")

S2_API_BASE = "https://api.semanticscholar.org/graph/v1"
OPENALEX_API_BASE = "https://api.openalex.org"

# 引用网络扩展的硬上限，防止无限扩展
MAX_CITATION_DEPTH = 2

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$", re.MULTILINE)


@dataclass
class PaperMetadata:
    """论文元数据（跨数据源统一结构）"""

    paper_id: str  # 源内 ID（arXiv 含版本 / S2 corpusId / OpenAlex W 号）
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    year: int | None = None
    published: str | None = None  # ISO 日期
    url: str = ""  # 详情/原文页
    pdf_url: str = ""
    source: str = "arxiv"
    categories: list[str] = field(default_factory=list)
    doi: str | None = None
    citation_count: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "published": self.published,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "source": self.source,
            "categories": self.categories,
            "doi": self.doi,
            "citation_count": self.citation_count,
        }


# ==================================================================
# 通用工具
# ==================================================================


def _normalize_title(title: str) -> str:
    """标题归一化：小写 + 仅保留字母数字"""
    return re.sub(r"[^a-z0-9]+", "", (title or "").lower())


def _strip_version(paper_id: str) -> str:
    """去掉 arXiv id 的版本后缀（v1/v2...）"""
    return re.sub(r"v\d+$", "", paper_id or "")


def _normalize_ws(text: str) -> str:
    """压缩空白，用于页码定位时的文本匹配"""
    return re.sub(r"\s+", " ", text or "").strip()


def _signature(text: str) -> str:
    """
    去掉所有非字母数字字符

    markitdown 与 pdfminer 的换行/断字规则不同，直接子串匹配容易失败；
    用「仅字母数字」的签名比对可以规避这些差异。
    """
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def message_text(resp: Any) -> str:
    """
    从 LLM 响应中提取文本

    兼容三种返回形态：
    - 常规模型：content 是字符串
    - 多段内容：content 是 [{"type": "text", "text": ...}]
    - 推理模型（mimo / DeepSeek-R1 风格）：content 为空，
      实际内容在 additional_kwargs["reasoning_content"]
    """
    content = getattr(resp, "content", None)
    if isinstance(content, str) and content.strip():
        return content.strip()
    if isinstance(content, list):
        parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        joined = "".join(parts).strip()
        if joined:
            return joined

    additional = getattr(resp, "additional_kwargs", None) or {}
    for key in ("reasoning_content", "reasoning", "thought"):
        value = additional.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _parse_json_from_llm(content: str) -> Any:
    """
    从 LLM 输出中解析 JSON

    兼容场景：
    - ```json 代码块包裹
    - 推理模型输出 <think> 思考块（如 mimo / DeepSeek-R1 风格）
    - JSON 之后还跟着解释性文本（用 raw_decode 截到合法 JSON 的结束位置）
    """
    text = _THINK_BLOCK_RE.sub("", (content or "").strip()).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()

    candidates = [i for i in (text.find("["), text.find("{")) if i != -1]
    if not candidates:
        return None

    start = min(candidates)
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
        return value
    except (ValueError, TypeError):
        return None


async def _get_json(
    url: str,
    params: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict | None:
    """GET JSON，失败返回 None"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:  # noqa: BLE001 - 外部数据源失败降级为空
        logger.warning(f"PaperAgent 请求失败 {url}: {e}")
        return None


def dedup_papers(papers: list[PaperMetadata]) -> list[PaperMetadata]:
    """按「DOI + 标题归一化 + 去版本号 id」去重，保留首次出现的条目"""
    seen: set[str] = set()
    result: list[PaperMetadata] = []
    for paper in papers:
        keys = {
            _normalize_title(paper.title),
            _strip_version(paper.paper_id),
            (paper.doi or "").lower(),
        }
        keys.discard("")
        if keys & seen:
            continue
        seen |= keys
        result.append(paper)
    return result


# ==================================================================
# M1 + M3：多源检索
# ==================================================================


def _within_year_range(
    year: int | None, year_from: int | None, year_to: int | None
) -> bool:
    """判断发表年份是否落在过滤区间内（无年份信息时保留）"""
    if year is None:
        return True
    if year_from is not None and year < year_from:
        return False
    if year_to is not None and year > year_to:
        return False
    return True


def _to_arxiv_paper(result: Any) -> PaperMetadata:
    """把 arXiv 单条结果转换为统一的论文元数据"""
    published = result.published
    return PaperMetadata(
        paper_id=result.get_short_id(),
        title=(result.title or "").replace("\n", " ").strip(),
        authors=[a.name for a in result.authors],
        abstract=(result.summary or "").replace("\n", " ").strip(),
        year=published.year if published else None,
        published=published.date().isoformat() if published else None,
        url=result.entry_id or "",
        pdf_url=result.pdf_url or "",
        source="arxiv",
        categories=list(result.categories or []),
        doi=getattr(result, "doi", None),
    )


def _arxiv_search_sync(
    query: str,
    max_results: int,
    year_from: int | None,
    year_to: int | None,
) -> list[PaperMetadata]:
    """
    同步执行 arXiv 检索（arxiv 客户端为阻塞式，需在线程中运行）

    arXiv 无官方 API Key，公开接口有速率限制，
    通过 arxiv.Client 的 delay_seconds / num_retries 做基本限流与重试。
    """
    import arxiv

    client = arxiv.Client(
        page_size=min(max_results, 100),
        delay_seconds=3.0,
        num_retries=3,
    )
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )

    papers: list[PaperMetadata] = []
    for result in client.results(search):
        paper = _to_arxiv_paper(result)
        # 年份过滤（arXiv API 不支持年份参数，本地过滤）
        if not _within_year_range(paper.year, year_from, year_to):
            continue
        papers.append(paper)
    return papers


async def _search_arxiv(
    query: str, max_results: int, year_from: int | None, year_to: int | None
) -> tuple[list[PaperMetadata], str | None]:
    """arXiv 检索，返回 (论文列表, 错误信息)"""
    try:
        papers = await asyncio.wait_for(
            asyncio.to_thread(
                _arxiv_search_sync, query, max_results, year_from, year_to
            ),
            timeout=settings.ARXIV_REQUEST_TIMEOUT,
        )
        return papers, None
    except TimeoutError:
        message = f"arXiv 检索超时（{settings.ARXIV_REQUEST_TIMEOUT}s）"
        logger.error(f"{message}: {query!r}")
        return [], message
    except Exception as e:  # noqa: BLE001
        logger.error(f"arXiv 检索失败: {e}", exc_info=True)
        return [], str(e)


async def _search_semantic_scholar(
    query: str, max_results: int, year_from: int | None, year_to: int | None
) -> tuple[list[PaperMetadata], str | None]:
    """Semantic Scholar 检索（免 Key 可用，配 Key 可提高配额）"""
    year_filter = None
    if year_from or year_to:
        year_filter = f"{year_from or 1900}-{year_to or 2100}"

    params: dict[str, Any] = {
        "query": query,
        "limit": min(max_results, 100),
        "fields": "paperId,externalIds,title,abstract,year,authors,url,"
        "openAccessPdf,citationCount,publicationDate,venue",
    }
    if year_filter:
        params["year"] = year_filter

    headers = {"Accept": "application/json"}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    data = await _get_json(
        f"{S2_API_BASE}/paper/search",
        params,
        headers,
        timeout=settings.ARXIV_REQUEST_TIMEOUT,
    )
    if not data or not isinstance(data.get("data"), list):
        return [], "Semantic Scholar 请求失败（可能触发限流）"

    papers: list[PaperMetadata] = []
    for item in data["data"]:
        external = item.get("externalIds") or {}
        pdf = item.get("openAccessPdf") or {}
        papers.append(
            PaperMetadata(
                paper_id=item.get("paperId") or "",
                title=(item.get("title") or "").strip(),
                authors=[a.get("name", "") for a in (item.get("authors") or [])],
                abstract=(item.get("abstract") or "").strip(),
                year=item.get("year"),
                published=item.get("publicationDate"),
                url=item.get("url") or "",
                pdf_url=pdf.get("url") or "",
                source="semantic_scholar",
                categories=[item["venue"]] if item.get("venue") else [],
                doi=external.get("DOI"),
                citation_count=item.get("citationCount"),
            )
        )
    filtered = [p for p in papers if _within_year_range(p.year, year_from, year_to)]
    return filtered, None


def _abstract_from_inverted_index(inv: dict[str, list[int]] | None) -> str:
    """OpenAlex 的摘要是倒排索引，还原为文本"""
    if not inv:
        return ""
    slots: list[str] = []
    for word, positions in inv.items():
        for pos in positions:
            while len(slots) <= pos:
                slots.append("")
            slots[pos] = word
    return " ".join(w for w in slots if w).strip()


async def _search_openalex(
    query: str, max_results: int, year_from: int | None, year_to: int | None
) -> tuple[list[PaperMetadata], str | None]:
    """OpenAlex 检索（免 Key，建议配置 mailto）"""
    filters: list[str] = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")

    params: dict[str, Any] = {
        "search": query,
        "per-page": min(max_results, 100),
    }
    if filters:
        params["filter"] = ",".join(filters)
    if settings.OPENALEX_MAILTO:
        params["mailto"] = settings.OPENALEX_MAILTO

    data = await _get_json(
        f"{OPENALEX_API_BASE}/works",
        params,
        None,
        timeout=settings.ARXIV_REQUEST_TIMEOUT,
    )
    if not data or not isinstance(data.get("results"), list):
        return [], "OpenAlex 请求失败"

    papers: list[PaperMetadata] = []
    for item in data["results"]:
        location = item.get("primary_location") or {}
        pdf_url = location.get("pdf_url") or ""
        doi = (item.get("doi") or "").replace("https://doi.org/", "") or None
        papers.append(
            PaperMetadata(
                paper_id=(item.get("id") or "").split("/")[-1],
                title=(item.get("display_name") or item.get("title") or "").strip(),
                authors=[
                    a.get("author", {}).get("display_name", "")
                    for a in (item.get("authorships") or [])
                ],
                abstract=_abstract_from_inverted_index(item.get("abstract_inverted_index")),
                year=item.get("publication_year"),
                published=item.get("publication_date"),
                url=location.get("landing_page_url") or item.get("doi") or "",
                pdf_url=pdf_url,
                source="openalex",
                categories=[],
                doi=doi,
                citation_count=item.get("cited_by_count"),
            )
        )
    return papers, None


async def search_papers_with_status(
    query: str,
    max_results: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str = "arxiv",
) -> tuple[list[PaperMetadata], str | None]:
    """
    检索论文元数据（带错误状态）

    Args:
        query: 检索关键词
        max_results: 期望条数，受 ARXIV_MAX_RESULTS 上限约束
        year_from / year_to: 发表年份过滤
        source: arxiv / semantic_scholar / openalex / all（多源融合）

    检索论文元数据

    Args:
        query: 检索关键词
        max_results: 期望条数，受 ARXIV_MAX_RESULTS 上限约束
        year_from / year_to: 发表年份过滤
        source: arxiv / semantic_scholar / openalex / all（多源融合）

    Returns:
        (去重后的论文列表, 错误信息)
        错误信息仅在「一个源都没拿到结果且确实出错」时非空；
        这样调用方能区分「检索失败」与「确实没有相关论文」。
    """
    if source not in SUPPORTED_SOURCES:
        raise ValueError(
            f"暂不支持的数据源: {source}（支持 {SUPPORTED_SOURCES}）"
        )

    limit = min(
        max_results or settings.PAPER_AGENT_MAX_PAPERS, settings.ARXIV_MAX_RESULTS
    )
    limit = max(1, limit)
    logger.info(
        f"PaperAgent 检索: source={source}, query={query!r}, max_results={limit}"
    )

    raw: list[PaperMetadata] = []
    errors: list[str] = []

    if source == "all":
        results = await asyncio.gather(
            _search_arxiv(query, limit, year_from, year_to),
            _search_semantic_scholar(query, limit, year_from, year_to),
            _search_openalex(query, limit, year_from, year_to),
            return_exceptions=True,
        )
        for item in results:
            if isinstance(item, Exception):
                errors.append(str(item))
                continue
            papers, error = item
            raw.extend(papers)
            if error:
                errors.append(error)
    else:
        if source == "arxiv":
            papers, error = await _search_arxiv(query, limit, year_from, year_to)
        elif source == "semantic_scholar":
            papers, error = await _search_semantic_scholar(
                query, limit, year_from, year_to
            )
        else:
            papers, error = await _search_openalex(query, limit, year_from, year_to)
        raw.extend(papers)
        if error:
            errors.append(error)

    result = dedup_papers(raw)
    logger.info(f"PaperAgent 检索完成: 原始 {len(raw)} 条，去重后 {len(result)} 条")

    # 多源场景下部分源失败不算失败，只有当一条都没拿到且确实出错时才报错
    error = errors[0] if not result and errors else None
    return result, error


async def search_papers(
    query: str,
    max_results: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str = "arxiv",
) -> list[PaperMetadata]:
    """检索论文元数据（只返回列表，忽略错误状态）"""
    papers, _ = await search_papers_with_status(
        query,
        max_results=max_results,
        year_from=year_from,
        year_to=year_to,
        source=source,
    )
    return papers


# ==================================================================
# M2：PDF 下载与解析
# ==================================================================


async def download_pdf(pdf_url: str, dest_dir: str | Path) -> dict[str, Any]:
    """
    下载公开可访问的 PDF

    安全约束：仅 http(s)；校验 content-type / 扩展名；限制体积与超时。

    Returns:
        成功：{"path": 本地路径, "sha256": 文件 hash, "bytes": 字节数}
        失败：{"path": None, "error": 原因}
    """
    if not pdf_url or not pdf_url.lower().startswith(("http://", "https://")):
        return {"path": None, "error": f"非法或非公开 PDF 地址: {pdf_url}"}

    limit_mb = settings.PAPER_AGENT_PDF_MAX_MB
    max_bytes = limit_mb * 1024 * 1024
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    raw_name = pdf_url.split("?")[0].split("/")[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name) or "paper.pdf"
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    target = dest / name

    try:
        async with httpx.AsyncClient(
            timeout=settings.PAPER_AGENT_PDF_TIMEOUT, follow_redirects=True
        ) as client:
            async with client.stream("GET", pdf_url) as resp:
                resp.raise_for_status()
                ctype = (resp.headers.get("content-type") or "").lower()
                if "pdf" not in ctype and not pdf_url.lower().endswith(".pdf"):
                    return {
                        "path": None,
                        "error": f"响应不是 PDF（content-type={ctype}）",
                    }
                declared = resp.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    return {
                        "path": None,
                        "error": f"PDF 超过体积上限 {limit_mb}MB",
                    }

                hasher = hashlib.sha256()
                size = 0
                with target.open("wb") as f:
                    async for chunk in resp.aiter_bytes():
                        size += len(chunk)
                        if size > max_bytes:
                            f.close()
                            target.unlink(missing_ok=True)
                            return {
                                "path": None,
                                "error": "PDF 下载超出体积上限，已中止",
                            }
                        hasher.update(chunk)
                        f.write(chunk)
    except Exception as e:  # noqa: BLE001 - 下载失败不应中断流水线
        logger.warning(f"PaperAgent PDF 下载失败 {pdf_url}: {e}")
        target.unlink(missing_ok=True)
        return {"path": None, "error": str(e)}

    logger.info(f"PaperAgent PDF 下载完成: {target.name} ({size} bytes)")
    return {"path": str(target), "sha256": hasher.hexdigest(), "bytes": size}


def _page_texts_pdfminer(path: str) -> list[str] | None:
    """
    尽力用 pdfminer 提取逐页文本（markitdown 不提供页码）

    pdfminer 是 markitdown[pdf] 的既有依赖；不可用时返回 None，
    此时证据退化为仅 section 级（page=None）。
    """
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer
    except ImportError:
        return None

    pages: list[str] = []
    try:
        for layout in extract_pages(path):
            chunks = [
                el.get_text() for el in layout if isinstance(el, LTTextContainer)
            ]
            pages.append("".join(chunks))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"pdfminer 逐页提取失败: {e}")
        return None
    return pages or None


def _split_markdown_sections(md_text: str) -> list[dict[str, Any]]:
    """按 Markdown 标题切分章节"""
    matches = list(_HEADING_RE.finditer(md_text))
    if not matches:
        text = md_text.strip()
        return [{"section": "全文", "text": text, "page": None}] if text else []

    sections: list[dict[str, Any]] = []
    head = md_text[: matches[0].start()].strip()
    if head:
        sections.append({"section": "前言", "text": head, "page": None})

    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(md_text)
        body = md_text[start:end].strip()
        if body:
            sections.append(
                {"section": match.group(2).strip(), "text": body, "page": None}
            )
    return sections


async def parse_pdf(path: str) -> list[dict[str, Any]]:
    """
    解析 PDF，保留 section 与（尽力获取）page

    使用已安装的 markitdown 抽取正文，再按标题切分章节；
    页码通过 pdfminer 逐页文本匹配定位，不可用时 page=None。

    Returns:
        [{"page": int | None, "section": str, "text": str}, ...]
    """
    source = Path(path)
    if not source.exists():
        logger.warning(f"PaperAgent PDF 不存在: {path}")
        return []

    def _convert() -> str:
        from markitdown import MarkItDown

        result = MarkItDown().convert(str(source))
        return getattr(result, "text_content", None) or str(result)

    try:
        md_text = await asyncio.to_thread(_convert)
    except Exception as e:  # noqa: BLE001
        logger.error(f"PaperAgent PDF 解析失败 {path}: {e}", exc_info=True)
        return []

    sections = _split_markdown_sections(md_text)
    if not sections:
        logger.warning(f"PaperAgent PDF 无有效文本: {path}")
        return []

    page_texts = await asyncio.to_thread(_page_texts_pdfminer, str(source))
    if page_texts:
        if len(sections) <= 1:
            # 没识别出标题结构：直接按页切分，保证证据至少能定位到页
            sections = [
                {"page": page_no, "section": f"第 {page_no} 页", "text": text}
                for page_no, text in enumerate(page_texts, start=1)
                if _normalize_ws(text)
            ]
        else:
            signatures = [_signature(t) for t in page_texts]
            for section in sections:
                key = _signature(section["text"])[:60]
                if not key:
                    continue
                for page_no, signature in enumerate(signatures, start=1):
                    if key and key in signature:
                        section["page"] = page_no
                        break

    logger.info(f"PaperAgent PDF 解析完成: {source.name}, {len(sections)} 个章节")
    return sections


async def _request_claims(
    llm: Any,
    sections: list[dict[str, Any]],
    paper_title: str,
    max_sections: int,
) -> list[Any] | None:
    """
    发起一次 claim 抽取请求

    Returns:
        解析后的 JSON 数组；调用失败或拿不到合法 JSON 时返回 None
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    from app.services.paper_agent.prompts import (
        CLAIM_EXTRACTION_SYSTEM,
        build_claim_prompt,
    )

    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(content=CLAIM_EXTRACTION_SYSTEM),
                HumanMessage(
                    content=build_claim_prompt(
                        sections,
                        paper_title=paper_title,
                        max_chars=settings.PAPER_AGENT_MAX_SECTION_CHARS,
                        max_sections=max_sections,
                    )
                ),
            ]
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"PaperAgent claim 抽取失败（{paper_title}）: {e}", exc_info=True
        )
        return None

    raw_content = message_text(resp)
    parsed = _parse_json_from_llm(raw_content)
    if isinstance(parsed, list):
        return parsed

    logger.warning(
        f"PaperAgent claim 抽取未拿到 JSON（{paper_title}）：{raw_content[:200]!r}"
    )
    return None


def _build_claims(
    parsed: list[Any],
    *,
    paper_id: str,
    paper_title: str,
    paper_url: str,
) -> list[dict[str, Any]]:
    """把模型返回的 JSON 规范化为 claim 列表，丢弃无原文引用的条目"""
    claims: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence") or {}
        quote = (evidence.get("quote") or "").strip()
        claim_text = (item.get("claim") or "").strip()
        # 硬约束：无正文引用的一律丢弃，避免产生无证据断言
        if not claim_text or not quote:
            continue
        claims.append(
            {
                "claim": claim_text,
                "category": item.get("category") or "contribution",
                "evidence": {
                    "page": evidence.get("page"),
                    "section": evidence.get("section") or "",
                    "quote": quote[:500],
                },
                "paper_id": paper_id,
                "title": paper_title,
                "url": paper_url,
            }
        )
    return claims


async def extract_claims(
    sections: list[dict[str, Any]],
    llm: Any,
    *,
    paper_title: str = "",
    paper_url: str = "",
    paper_id: str = "",
) -> list[dict[str, Any]]:
    """
    从已解析的论文正文中抽取带证据的 claim

    Args:
        sections: parse_pdf 的输出
        llm: LangChain ChatModel
        paper_title / paper_url / paper_id: 论文标识，写回每条 claim

    Returns:
        [{"claim": str, "category": contribution|method|dataset|metric|limitation,
          "evidence": {"page": int|None, "section": str, "quote": str},
          "paper_id": str, "title": str, "url": str}, ...]
        硬约束：无 evidence 的 claim 会被丢弃。
    """
    if not sections or llm is None:
        return []

    parsed: list[Any] | None = None
    # 最多两次：先用完整正文，失败则缩小负载重试（推理模型容易输出为空）
    for max_sections in (6, 3):
        parsed = await _request_claims(llm, sections, paper_title, max_sections)
        if parsed is not None:
            break

    if not parsed:
        return []

    claims = _build_claims(
        parsed, paper_id=paper_id, paper_title=paper_title, paper_url=paper_url
    )
    logger.info(f"PaperAgent claim 抽取完成: {paper_title} -> {len(claims)} 条")
    return claims


# ==================================================================
# M3：引用扩展与对比
# ==================================================================


async def expand_citations(paper_id: str, depth: int = 1) -> list[PaperMetadata]:
    """
    引用/被引关系扩展（Semantic Scholar）

    Args:
        paper_id: S2 paperId，或 arXiv:xxxx.xxxxx / DOI:xxx 形式
        depth: 扩展深度，硬上限 MAX_CITATION_DEPTH，防止无限扩展

    Returns:
        引用与被引用论文列表（去重）
    """
    depth = max(1, min(depth, MAX_CITATION_DEPTH))
    headers = {"Accept": "application/json"}
    if settings.SEMANTIC_SCHOLAR_API_KEY:
        headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

    fields = (
        "paperId,externalIds,title,abstract,year,authors,url,"
        "openAccessPdf,citationCount"
    )
    collected: list[PaperMetadata] = []

    for relation in ("citations", "references"):
        data = await _get_json(
            f"{S2_API_BASE}/paper/{paper_id}/{relation}",
            {"limit": 20, "fields": fields},
            headers,
            timeout=settings.ARXIV_REQUEST_TIMEOUT,
        )
        if not data or not isinstance(data.get("data"), list):
            continue
        for entry in data["data"]:
            item = entry.get("citingPaper") or entry.get("citedPaper") or entry
            external = item.get("externalIds") or {}
            pdf = item.get("openAccessPdf") or {}
            collected.append(
                PaperMetadata(
                    paper_id=item.get("paperId") or "",
                    title=(item.get("title") or "").strip(),
                    authors=[a.get("name", "") for a in (item.get("authors") or [])],
                    abstract=(item.get("abstract") or "").strip(),
                    year=item.get("year"),
                    url=item.get("url") or "",
                    pdf_url=pdf.get("url") or "",
                    source="semantic_scholar",
                    doi=external.get("DOI"),
                    citation_count=item.get("citationCount"),
                )
            )

    papers = dedup_papers(collected)
    logger.info(f"PaperAgent 引用扩展: {paper_id} depth={depth} -> {len(papers)} 篇")
    return papers


async def compare_papers(
    entries: list[dict[str, Any]],
    llm: Any = None,
    *,
    topic: str = "",
) -> dict[str, Any]:
    """
    多篇论文对比矩阵

    Args:
        entries: [{"paper_id","title","url","year","claims":[...]}, ...]
        llm: 可选 ChatModel，用于对齐对比维度
        topic: 综述主题，用于提示词

    Returns:
        {"dimensions": [...], "rows": [{"paper": str, "url": str,
          "values": {dim: value}, "evidence": {...}}]}
        不同任务/数据集的指标不硬比较，维度由 LLM 按可比性对齐，
        不可比时在取值中标注实验条件。
    """
    if not entries:
        return {"dimensions": [], "rows": []}

    if llm is None:
        return heuristic_comparison(entries)

    from langchain_core.messages import HumanMessage, SystemMessage

    from app.services.paper_agent.prompts import (
        COMPARISON_SYSTEM,
        build_comparison_prompt,
    )

    try:
        resp = await llm.ainvoke(
            [
                SystemMessage(content=COMPARISON_SYSTEM),
                HumanMessage(content=build_comparison_prompt(entries, topic=topic)),
            ]
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"PaperAgent 对比生成失败: {e}", exc_info=True)
        return heuristic_comparison(entries)

    parsed = _parse_json_from_llm(message_text(resp))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("rows"), list):
        return heuristic_comparison(entries)

    dimensions = parsed.get("dimensions") or []
    if not dimensions and parsed.get("rows"):
        dimensions = list((parsed["rows"][0].get("values") or {}).keys())

    logger.info(
        f"PaperAgent 对比完成: {len(parsed['rows'])} 行 x {len(dimensions)} 维度"
    )
    return {"dimensions": dimensions, "rows": parsed["rows"]}


def heuristic_comparison(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """无 LLM 时的兜底对比：按 claim 类别聚合"""
    dimensions = ["method", "dataset", "metric"]
    rows = []
    for entry in entries:
        values: dict[str, str] = {d: "" for d in dimensions}
        for claim in entry.get("claims") or []:
            category = (claim.get("category") or "").lower()
            key = category if category in values else "method"
            text = claim.get("claim", "")
            if text and (not values[key] or len(values[key]) > len(text)):
                values[key] = text[:200]
        rows.append(
            {
                "paper": entry.get("title", ""),
                "url": entry.get("url", ""),
                "values": values,
                "evidence": {"source": "claim_heuristic"},
            }
        )
    return {"dimensions": dimensions, "rows": rows}
