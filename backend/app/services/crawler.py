"""
网站爬虫服务 — BFS 深度爬取，提取页面正文内容
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.utils.logger import logger


@dataclass
class CrawlPage:
    """单个爬取页面结果"""
    url: str
    title: str
    content: str  # 正文 Markdown


@dataclass
class CrawlResult:
    """爬取任务结果"""
    pages: List[CrawlPage] = field(default_factory=list)
    total_pages: int = 0
    errors: List[str] = field(default_factory=list)


class WebCrawler:
    """
    BFS 网站爬虫

    - 同域限制：只爬与起始 URL 相同域名的页面
    - 去重：已访问 URL 不重复爬取
    - 正文提取：去掉 nav/footer/script/style 等噪音标签
    """

    # 请求头，模拟浏览器
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }

    # 需要移除的噪音标签
    REMOVE_TAGS = ["nav", "footer", "header", "aside", "script", "style",
                   "noscript", "iframe", "svg", "form", "button"]

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def crawl(
        self,
        start_url: str,
        max_depth: int = 3,
        max_pages: int = 50,
    ) -> CrawlResult:
        """
        BFS 爬取网站

        Args:
            start_url: 起始 URL
            max_depth: 最大爬取深度（0=只爬起始页）
            max_pages: 最大爬取页面数
        """
        parsed_start = urlparse(start_url)
        start_domain = parsed_start.netloc

        visited: Set[str] = set()
        result = CrawlResult()

        # BFS 队列: (url, depth)
        queue: deque = deque([(start_url, 0)])
        visited.add(self._normalize_url(start_url))

        logger.info(f"开始爬取: {start_url}, max_depth={max_depth}, max_pages={max_pages}")

        async with httpx.AsyncClient(
            headers=self.HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
            verify=False,
        ) as client:
            while queue and len(result.pages) < max_pages:
                url, depth = queue.popleft()

                # 超过最大深度，跳过（但当前页仍爬取）
                if depth > max_depth:
                    continue

                try:
                    page = await self._fetch_page(client, url)
                    if page:
                        result.pages.append(page)
                        logger.info(
                            f"  [{len(result.pages)}/{max_pages}] depth={depth} "
                            f"OK: {page.title[:50]} ({url})"
                        )

                        # 提取链接加入队列（仅同域 + 未访问 + 未超深度）
                        if depth < max_depth:
                            links = self._extract_links(page.content, url, start_domain)
                            for link in links:
                                norm = self._normalize_url(link)
                                if norm not in visited:
                                    visited.add(norm)
                                    queue.append((link, depth + 1))

                except Exception as e:
                    error_msg = f"爬取失败 {url}: {e}"
                    logger.warning(error_msg)
                    result.errors.append(error_msg)

        result.total_pages = len(result.pages)
        logger.info(f"爬取完成: {result.total_pages} 页, {len(result.errors)} 个错误")
        return result

    async def _fetch_page(self, client: httpx.AsyncClient, url: str) -> Optional[CrawlPage]:
        """请求页面并提取正文"""
        resp = await client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None

        # 根据响应编码解码
        resp.encoding = resp.encoding or "utf-8"
        html = resp.text

        soup = BeautifulSoup(html, "html.parser")

        # 提取标题
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # 移除噪音标签
        for tag_name in self.REMOVE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # 尝试提取正文主体
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|article|post|entry", re.I))
            or soup.find("div", id=re.compile(r"content|article|post|entry", re.I))
            or soup.body
            or soup
        )

        # 提取文本，转为简单 Markdown
        text = self._html_to_markdown(main_content)

        if not text.strip():
            return None

        return CrawlPage(url=url, title=title or urlparse(url).path, content=text)

    def _html_to_markdown(self, element) -> str:
        """将 HTML 元素转为简单 Markdown 文本"""
        lines = []
        for child in element.descendants:
            if child.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
                level = int(child.name[1])
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n{'#' * level} {text}\n")
            elif child.name == "p":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"\n{text}\n")
            elif child.name == "li":
                text = child.get_text(strip=True)
                if text:
                    lines.append(f"- {text}")
            elif child.name == "br":
                lines.append("\n")
            elif child.name is None and isinstance(child, str):
                text = child.strip()
                if text:
                    lines.append(text)

        return "\n".join(lines)

    def _extract_links(self, content: str, base_url: str, target_domain: str) -> List[str]:
        """从页面中提取同域链接"""
        soup = BeautifulSoup(content, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()

            # 跳过锚点、javascript、mailto
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # 解析为绝对 URL
            absolute = urljoin(base_url, href)
            parsed = urlparse(absolute)

            # 只保留同域 + http(s) 链接
            if parsed.netloc == target_domain and parsed.scheme in ("http", "https"):
                # 去掉 fragment
                clean = parsed._replace(fragment="").geturl()
                links.append(clean)

        return links

    @staticmethod
    def _normalize_url(url: str) -> str:
        """URL 归一化：去掉 fragment、末尾斜杠、统一 scheme"""
        parsed = urlparse(url)
        # 去掉 fragment，统一为 https
        scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
        return parsed._replace(scheme=scheme, fragment="").geturl().rstrip("/")
