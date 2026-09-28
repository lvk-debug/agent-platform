"""
文档分页解析服务

按文件类型分派到各自的解析器，产出「分页内容」供前端渲染：

| 类型     | 后端职责                                | 前端职责                    |
|----------|-----------------------------------------|-----------------------------|
| PDF      | 只取页数与大纲（Pages/Outline）         | pdfjs-dist 渲染 canvas+文本层 |
| PPTX     | 逐 slide 抽取 shape 的文本/图片/表格，按 slide 宽高归一化 | 绝对定位还原 |
| EPUB     | 按 spine 拆章节，HTML 安全净化，图片落盘 | 受控渲染净化后的 HTML       |
| Markdown | 按 H1/H2 标题切页                       | marked 渲染 + 代码高亮      |

设计要点：
1. **不复用 utils/file_parser.py**：知识库链路为「整篇转 Markdown 再切片」，
   学习助手要保留**分页结构**，两者目标不同；且避免改动影响既有知识库功能。
2. **EPUB HTML 必须净化**：EPUB 是第三方内容，内含 script/外链会造成 XSS，
   统一过白名单后再返回给前端。
3. **依赖延迟导入 + 友好报错**：pypdf / python-pptx / ebooklib 任一缺失时，
   只降级对应格式，其余功能不受影响。
"""

import importlib
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

from app.core.config import settings
from app.models.learning import DocumentFileType, LearningResource
from app.utils.logger import logger


class DocumentParseError(Exception):
    """文档解析失败（依赖缺失或文件损坏）"""


def _require(module_name: str, pip_name: str) -> Any:
    """延迟导入可选依赖，缺失时给出可执行的安装提示"""
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise DocumentParseError(
            f"缺少依赖 {pip_name}，无法解析该格式。请执行：pip install {pip_name}"
        ) from exc


def _learning_root() -> str:
    """学习模块的文件根目录：UPLOAD_DIR/learning"""
    return os.path.join(settings.UPLOAD_DIR, settings.LEARNING_UPLOAD_SUBDIR)


def resource_dir(resource_id: int) -> str:
    """单个资源的目录（文档原文与其 assets 都放这里）"""
    return os.path.join(_learning_root(), str(resource_id))


def assets_dir(resource_id: int) -> str:
    """资源内联图片目录"""
    return os.path.join(resource_dir(resource_id), "assets")


# ------------------------------------------------------------------
# 上传落盘
# ------------------------------------------------------------------


def detect_file_type(filename: str) -> str:
    """按扩展名判定文档类型"""
    ext = os.path.splitext((filename or "").lower())[1]
    file_type = DocumentFileType.EXT_MAP.get(ext)
    if file_type is None:
        raise ValueError(f"不支持的文档格式：{ext or '未知'}，仅支持 PDF / PPTX / EPUB / Markdown")
    return file_type


def save_upload(resource_id: int, content: bytes, filename: str, file_type: str) -> str:
    """
    保存上传文档

    用 `{file_type}{原扩展名}` 的 UUID 文件名，**不使用原始文件名**，
    规避同名覆盖与路径穿越（现有知识库链路的 `knowledge.py:246` 即用原始名拼接）。

    Returns:
        落盘的绝对路径
    """
    directory = resource_dir(resource_id)
    os.makedirs(directory, exist_ok=True)
    ext = os.path.splitext(filename.lower())[1]
    # 文件名带上类型前缀，便于运维排障时直接从磁盘辨认格式
    stored_name = f"{file_type}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(directory, stored_name)
    with open(path, "wb") as handle:
        handle.write(content)
    logger.info(f"文档落盘成功 resource={resource_id} type={file_type} size={len(content)}")
    return path


def delete_resource_files(resource_id: int) -> None:
    """删除资源目录下的全部文件（删除资源时调用）"""
    import shutil

    directory = resource_dir(resource_id)
    if os.path.isdir(directory):
        shutil.rmtree(directory, ignore_errors=True)


# ------------------------------------------------------------------
# Markdown 切页
# ------------------------------------------------------------------

_MD_HEADING_RE = re.compile(r"^(#{1,2})\s+(.*)$", re.MULTILINE)
_MD_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)


def _is_in_code_fence(text: str, position: int) -> bool:
    """判断标题行是否位于代码块围栏内（避免把注释里的 # 当标题）"""
    fences = [m.start() for m in _MD_CODE_FENCE_RE.finditer(text)]
    opened = False
    for fence_position in fences:
        if fence_position > position:
            break
        opened = not opened
    return opened


def split_markdown_pages(text: str) -> List[Tuple[str, str]]:
    """
    按 H1/H2 标题切页

    Returns:
        [(页面标题, 页面正文), ...]；无标题时整篇作为一页
    """
    if not text.strip():
        return [("正文", "")]

    matches = [
        match
        for match in _MD_HEADING_RE.finditer(text)
        if not _is_in_code_fence(text, match.start())
    ]
    if not matches:
        return [("正文", text.strip())]

    pages: List[Tuple[str, str]] = []
    preamble = text[: matches[0].start()].strip()
    if preamble:
        pages.append(("概览", preamble))

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end].strip()
        pages.append((match.group(2).strip() or "正文", body))

    return pages or [("正文", text.strip())]


# ------------------------------------------------------------------
# HTML 净化（EPUB 章节）
# ------------------------------------------------------------------

_ALLOWED_TAGS = {
    "p", "br", "hr", "span", "div", "section", "article",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s", "sub", "sup", "code", "pre",
    "blockquote", "q", "cite",
    "ul", "ol", "li", "dl", "dt", "dd",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "img", "figure", "figcaption", "a",
}
_ALLOWED_ATTRS = {
    "a": {"href", "title"},
    "img": {"src", "alt", "width", "height"},
    "table": {"border"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
}
_SAFE_URL_RE = re.compile(r"^(https?://|mailto:|#|/)", re.IGNORECASE)


def sanitize_html(html: str) -> str:
    """
    净化 EPUB 章节 HTML

    移除 script/style/iframe 等危险标签、所有 on* 事件属性与非安全协议的 URL。

    ⚠️ 只净化 <body> 内部：EPUB 章节是**完整 XHTML 文档**（含 <html>/<head>/<body>），
    而这些结构标签并不在排版白名单里。若对全文做白名单过滤，根节点 <html> 会被
    decompose，连带整章内容全部被清空（表现为「导入成功但一页都没有」）。
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")
    body = soup.body or soup

    # 清理 body 自身的事件属性（它不在遍历范围内，需单独处理）
    for attr in list(body.attrs.keys()):
        if attr.lower().startswith("on") or attr.lower() in ("background", "bgcolor"):
            del body[attr]

    # find_all 只返回 body 的后代，不含 body 自身，故结构标签不会被误删
    for tag in body.find_all():
        name = tag.name.lower()
        if name == "font":
            # font 只承载样式：unwrap 保留其内部文字，不至于丢掉正文
            tag.unwrap()
            continue
        if name not in _ALLOWED_TAGS:
            tag.decompose()
            continue

        allowed = _ALLOWED_ATTRS.get(name, set())
        for attr in list(tag.attrs.keys()):
            lower_attr = attr.lower()
            if lower_attr.startswith("on") or attr not in allowed:
                del tag[attr]

        # 协议白名单，挡掉 javascript: / data:text/html 等
        if name == "a" and tag.get("href") and not _SAFE_URL_RE.match(tag["href"]):
            del tag["href"]
        if name == "img":
            # 外链图片大多被防盗链拦截，且有隐私泄露风险：只保留已落盘的本地资源
            src = tag.get("src") or ""
            if not src or src.startswith(("http://", "https://", "data:")):
                tag.decompose()

    return "".join(str(child) for child in body.contents)


def _localize_epub_images(
    book_items: Dict[str, bytes], html: str, asset_prefix: str, asset_dir: str
) -> str:
    """把 EPUB 内嵌图片落盘并把 src 改写为本地路径"""
    soup = BeautifulSoup(html, "html.parser")
    changed = False

    for img in soup.find_all("img"):
        src = (img.get("src") or "").strip()
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        candidates = (src, os.path.basename(src), src.lstrip("./").replace("//", "/"))
        payload = None
        for candidate in candidates:
            if candidate in book_items:
                payload = book_items[candidate]
                break
        if payload is None:
            continue

        stored_name = f"{uuid.uuid4().hex}_{os.path.basename(candidates[1]) or 'image'}"
        os.makedirs(asset_dir, exist_ok=True)
        with open(os.path.join(asset_dir, stored_name), "wb") as handle:
            handle.write(payload)
        img["src"] = f"{asset_prefix}/{stored_name}"
        changed = True

    return str(soup) if changed else html


# ------------------------------------------------------------------
# 各格式解析器
# ------------------------------------------------------------------


def _html_to_text(html: str) -> str:
    """
    HTML → 纯文本（供 AI 索引使用）

    块级元素后补换行，否则 EPUB 的段落会首尾相接连成一片，
    既影响切片质量也让模型难以断句。
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(
        ["p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6"]
    ):
        tag.insert_after("\n")
    text = soup.get_text()
    # 去掉行尾空白，并把 3 行以上连续空行压成 2 行
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_pdf_meta(path: str) -> Tuple[int, List[Dict[str, Any]]]:
    """PDF：页数 + 书签大纲"""
    pypdf = _require("pypdf", "pypdf")
    reader = pypdf.PdfReader(path)
    page_count = len(reader.pages)

    outline: List[Dict[str, Any]] = []

    def _walk(items: Any, _reader: Any) -> None:
        for item in items or []:
            if isinstance(item, list):
                _walk(item, _reader)
                continue
            try:
                page_index = _reader.get_destination_page_number(item)
            except Exception:  # noqa: BLE001 - 书签损坏时跳过，不该中断整本书解析
                continue
            outline.append({"title": str(item.title or "").strip(), "page_index": page_index})

    # get_outlines 在部分 PDF 上抛异常，容忍
    if not getattr(reader, "is_encrypted", False) or reader.decrypt("") == 1:
        try:
            _walk(reader.outline, reader)
        except Exception:  # noqa: BLE001
            pass

    return page_count, outline


def _parse_pptx_slides(resource_id: int, path: str) -> Tuple[List[List[dict]], float, float]:
    """PPTX：逐页抽取 shape（文本/图片/表格），坐标按 slide 宽高归一化"""
    pptx = _require("pptx", "python-pptx")
    presentation = pptx.Presentation(path)
    slide_width = float(presentation.slide_width or 1)
    slide_height = float(presentation.slide_height or 1)

    asset_dir = assets_dir(resource_id)
    asset_prefix = f"/api/v1/learning/assets/{resource_id}"
    pages: List[List[dict]] = []

    for slide in presentation.slides:
        blocks: List[dict] = []
        for shape in slide.shapes:
            left = float(shape.left or 0)
            top = float(shape.top or 0)
            width = float(shape.width or 0)
            height = float(shape.height or 0)
            box = {
                "x": left / slide_width,
                "y": top / slide_height,
                "w": width / slide_width,
                "h": height / slide_height,
            }

            if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
                paragraphs = shape.text_frame.paragraphs
                style: Dict[str, Any] = {}
                if paragraphs and paragraphs[0].runs:
                    run = paragraphs[0].runs[0]
                    font_size = None
                    try:
                        font_size = run.font.size.pt if run.font.size else None
                    except Exception:  # noqa: BLE001
                        font_size = None
                    if font_size:
                        # 归一化字号：pt→EMU 后相对页高
                        style["fontSize"] = round(font_size * 12700 / slide_height, 4)
                    if run.font.bold:
                        style["bold"] = True
                    if run.font.color and run.font.color.rgb:
                        style["color"] = f"#{run.font.color.rgb}"
                if paragraphs and paragraphs[0].alignment is not None:
                    style["align"] = str(paragraphs[0].alignment).split()[0]

                blocks.append(
                    {
                        "kind": "text",
                        "text": shape.text_frame.text,
                        "style": style,
                        **box,
                    }
                )
                continue

            if getattr(shape, "has_table", False):
                rows = []
                for row in shape.table.rows:
                    rows.append(" | ".join(cell.text.strip() for cell in row.cells))
                blocks.append({"kind": "table", "text": "\n".join(rows), **box})
                continue

            if str(shape.shape_type or "").startswith("PICTURE") or hasattr(shape, "image"):
                try:
                    image = shape.image
                    ext = (image.content_type or "image/png").split("/")[-1]
                    stored_name = f"{uuid.uuid4().hex}.{ext}"
                    os.makedirs(asset_dir, exist_ok=True)
                    with open(os.path.join(asset_dir, stored_name), "wb") as handle:
                        handle.write(image.blob)
                    blocks.append({"kind": "image", "src": f"{asset_prefix}/{stored_name}", **box})
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"PPTX 图片抽取失败: {exc}")

        pages.append(blocks)

    return pages, slide_width, slide_height


class DocumentPageService:
    """文档分页解析服务"""

    # ---------- 查询接口 ----------

    def get_meta(self, resource: LearningResource) -> Tuple[int, List[Dict[str, Any]]]:
        """
        获取文档页数与大纲

        结果会被写回 resource.page_count，故二次打开不必重新解析整本书。
        """
        if not resource.file_path or not os.path.isfile(resource.file_path):
            raise DocumentParseError("文档文件缺失，请重新上传")

        file_type = resource.file_type
        if file_type == DocumentFileType.PDF:
            return _parse_pdf_meta(resource.file_path)
        if file_type == DocumentFileType.PPTX:
            pptx = _require("pptx", "python-pptx")
            presentation = pptx.Presentation(resource.file_path)
            return len(presentation.slides), []
        if file_type == DocumentFileType.EPUB:
            return self._read_epub(resource)[1], []
        if file_type == DocumentFileType.MARKDOWN:
            return self._read_markdown(resource)[1], []

        raise DocumentParseError(f"不支持的文档类型：{file_type}")

    def get_page(self, resource: LearningResource, page_index: int) -> Dict[str, Any]:
        """获取指定页内容；返回结构对齐 DocumentPageResponse"""
        if not resource.file_path or not os.path.isfile(resource.file_path):
            raise DocumentParseError("文档文件缺失，请重新上传")

        file_type = resource.file_type
        if file_type == DocumentFileType.PDF:
            page_count, _ = _parse_pdf_meta(resource.file_path)
            return {
                "file_type": file_type,
                "page_count": max(page_count, 1),
                "page_index": page_index,
                "title": f"第 {page_index + 1} 页",
                "html": "",
                "raw": "",
                "blocks": [],
            }

        if file_type == DocumentFileType.PPTX:
            pages, slide_width, slide_height = _parse_pptx_slides(resource.id, resource.file_path)
            if not pages:
                raise DocumentParseError("PPTX 未解析到任何页面")
            page_index = min(max(page_index, 0), len(pages) - 1)
            return {
                "file_type": file_type,
                "page_count": len(pages),
                "page_index": page_index,
                "width": slide_width,
                "height": slide_height,
                "title": f"第 {page_index + 1} 页",
                "html": "",
                "raw": "",
                "blocks": pages[page_index],
            }

        if file_type == DocumentFileType.EPUB:
            chapters, _ = self._read_epub(resource)
            if not chapters:
                raise DocumentParseError("EPUB 未解析到任何章节")
            page_index = min(max(page_index, 0), len(chapters) - 1)
            title, html = chapters[page_index]
            return {
                "file_type": file_type,
                "page_count": len(chapters),
                "page_index": page_index,
                "title": title,
                "html": html,
                "raw": "",
                "blocks": [],
            }

        if file_type == DocumentFileType.MARKDOWN:
            pages, _ = self._read_markdown(resource)
            page_index = min(max(page_index, 0), len(pages) - 1)
            title, body = pages[page_index]
            return {
                "file_type": file_type,
                "page_count": len(pages),
                "page_index": page_index,
                "title": title,
                "html": "",
                "raw": body,
                "blocks": [],
            }

        raise DocumentParseError(f"不支持的文档类型：{file_type}")

    # ---------- AI 索引用：全文纯文本抽取 ----------

    def extract_page_texts(self, resource: LearningResource) -> List[Dict[str, Any]]:
        """
        逐页抽取**纯文本**，供 AI 问答的索引构建与降级检索使用

        与 get_page 的区别：get_page 返回渲染所需结构（HTML / blocks / 原始 md），
        这里只要纯文本，且一次性遍历全部页——索引需要全文，不能按页懒加载。
        落库由索引服务负责，本服务保持无 DB 依赖的纯解析定位。

        Returns:
            [{"page_index": int, "title": str, "content": str}]，按页序
        """
        if not resource.file_path or not os.path.isfile(resource.file_path):
            raise DocumentParseError("文档文件缺失，请重新上传")

        file_type = resource.file_type
        if file_type == DocumentFileType.PDF:
            return self._extract_pdf(resource.file_path)

        if file_type == DocumentFileType.PPTX:
            pages, _, _ = _parse_pptx_slides(resource.id, resource.file_path)
            # 表格块也已把单元格拼进 text（" | " 分隔），统一取 text 即可
            return [
                {
                    "page_index": index,
                    "title": f"第 {index + 1} 页",
                    "content": "\n".join(
                        text
                        for text in ((block.get("text") or "").strip() for block in blocks)
                        if text
                    ),
                }
                for index, blocks in enumerate(pages)
            ]

        if file_type == DocumentFileType.EPUB:
            chapters, _ = self._read_epub(resource)
            return [
                {"page_index": index, "title": title, "content": _html_to_text(html)}
                for index, (title, html) in enumerate(chapters)
            ]

        if file_type == DocumentFileType.MARKDOWN:
            pages, _ = self._read_markdown(resource)
            # Markdown 保留原文：# / ## 这类标题层级本身就是给模型的结构线索
            return [
                {"page_index": index, "title": title, "content": body}
                for index, (title, body) in enumerate(pages)
            ]

        raise DocumentParseError(f"不支持的文档类型：{file_type}")

    @staticmethod
    def _extract_pdf(path: str) -> List[Dict[str, Any]]:
        """PDF 逐页抽取文本；单页失败只记警告，不中断整本"""
        pypdf = _require("pypdf", "pypdf")
        reader = pypdf.PdfReader(path)

        results: List[Dict[str, Any]] = []
        for index, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # noqa: BLE001 - 单页损坏不应拖垮整本
                logger.warning(f"PDF 第 {index + 1} 页文本抽取失败: {exc}")
                text = ""
            results.append(
                {"page_index": index, "title": f"第 {index + 1} 页", "content": text}
            )
        return results

    # ---------- 内部读取 ----------

    @staticmethod
    def _read_markdown(resource: LearningResource) -> Tuple[List[Tuple[str, str]], int]:
        with open(resource.file_path, "r", encoding="utf-8", errors="ignore") as handle:
            pages = split_markdown_pages(handle.read())
        return pages, len(pages)

    @staticmethod
    def _read_epub(resource: LearningResource) -> Tuple[List[Tuple[str, str]], int]:
        """按 spine 顺序读出所有章节（含图片落盘与 HTML 净化）"""
        _require("ebooklib", "ebooklib")  # 仅用于缺失时给出安装提示
        # 注意：`read_epub` 位于 ebooklib.epub 子模块，顶层没有；
        # 而 ITEM_DOCUMENT / ITEM_IMAGE 常量反而只在顶层，二者来源不同，别写混。
        from ebooklib import ITEM_DOCUMENT, ITEM_IMAGE, epub as epub_module  # noqa: PLC0415

        book = epub_module.read_epub(resource.file_path)

        # 先把所有图片资源收集成 {file_name: bytes}，供 src 改写时查表。
        # 必须用 get_content()：EpubItem.content 默认是 None，直接读会得到空内容。
        images: Dict[str, bytes] = {}
        for item in book.get_items_of_type(ITEM_IMAGE):
            try:
                images[item.file_name] = item.get_content()
            except Exception:  # noqa: BLE001 - 单张图损坏不应中断整书
                continue

        asset_prefix = f"/api/v1/learning/assets/{resource.id}"
        asset_dir = assets_dir(resource.id)

        chapters: List[Tuple[str, str]] = []
        for item in book.get_items_of_type(ITEM_DOCUMENT):
            try:
                raw_html = item.get_content().decode("utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            if not raw_html.strip():
                continue

            localized = _localize_epub_images(images, raw_html, asset_prefix, asset_dir)
            html = sanitize_html(localized)

            parsed = BeautifulSoup(html, "html.parser")
            if not parsed.get_text(strip=True) and "<img" not in html:
                continue

            # 标题优先取正文首个标题标签（比 chapter1.xhtml 这类文件名友好得多），
            # 其次回退文件名，最后才用序号兜底
            heading = parsed.find(["h1", "h2", "h3"])
            title = heading.get_text(strip=True) if heading else ""
            if not title:
                title = (item.get_name() or "").strip()
            title = title or f"章节 {len(chapters) + 1}"
            chapters.append((title[:80], html))

        return chapters, len(chapters)


def get_document_page_service() -> DocumentPageService:
    """文档分页服务工厂（无状态，不依赖 DB Session）"""
    return DocumentPageService()
