"""
文档解析工具（模块级，与数据库无关）

把「任意支持格式 → Markdown 文本」的能力从 KnowledgeService 中抽出，
供知识库入库与会话附件两条链路复用，避免重复实现。

设计要点：
- 同步实现（markitdown / PyPDF2 等都是阻塞 IO），调用方按需决定是否
  丢进线程池：IO 密集场景用 `asyncio.to_thread(convert_to_markdown_sync, ...)`
- 任何解析异常都向外抛出，由调用方决定降级策略（标记 failed 还是重试）
"""

from __future__ import annotations

from app.utils.logger import logger


def preprocess_html(file_path: str) -> str:
    """
    HTML 预处理：用 BeautifulSoup 提取主体内容，移除导航/页脚/广告。

    返回处理后的文件路径（处理失败时原样返回入参）。
    """
    try:
        from bs4 import BeautifulSoup

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            soup = BeautifulSoup(f.read(), "html.parser")

        # 移除非内容标签
        for tag in soup.find_all(
            ["nav", "footer", "header", "aside", "script", "style"]
        ):
            tag.decompose()

        # 尝试提取主体内容
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find("div", class_="content")
        )
        content = str(main) if main else str(soup)

        temp_path = file_path + ".cleaned.html"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        return temp_path
    except ImportError:
        return file_path
    except Exception as e:
        logger.warning(f"HTML 预处理失败: {e}")
        return file_path


def fallback_parse(file_path: str, file_type: str) -> str:
    """
    markitdown 不可用时的兜底解析。

    对不支持的类型抛出 ValueError，由调用方处理。
    """
    if file_type in ("txt", "markdown"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    if file_type == "html":
        try:
            from bs4 import BeautifulSoup

            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                soup = BeautifulSoup(f.read(), "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except ImportError:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    if file_type == "pdf":
        try:
            import PyPDF2

            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                return "".join(page.extract_text() + "\n" for page in reader.pages)
        except ImportError:
            logger.warning("PyPDF2 未安装，无法解析 PDF")
            return ""

    if file_type == "docx":
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(file_path)
            return "".join(para.text + "\n" for para in doc.paragraphs)
        except ImportError:
            logger.warning("python-docx 未安装，无法解析 Word 文档")
            return ""

    if file_type == "excel":
        try:
            import pandas as pd

            df = pd.read_excel(file_path)
            return df.to_markdown(index=False)
        except ImportError:
            logger.warning("pandas 未安装，无法解析 Excel")
            return ""

    raise ValueError(f"不支持的文件类型: {file_type}")


def convert_to_markdown_sync(file_path: str, file_type: str) -> str:
    """
    同步：使用 markitdown 将各种格式统一转为 Markdown，失败时走 fallback。
    """
    if file_type == "html":
        file_path = preprocess_html(file_path)

    try:
        from markitdown import MarkItDown

        converter = MarkItDown()
        result = converter.convert(file_path)
        return result.text_content if hasattr(result, "text_content") else str(result)
    except ImportError:
        logger.warning("markitdown 未安装，使用 fallback 解析")
        return fallback_parse(file_path, file_type)
    except Exception as e:
        logger.warning(f"markitdown 转换失败: {e}，使用 fallback 解析")
        return fallback_parse(file_path, file_type)


async def convert_to_markdown(file_path: str, file_type: str) -> str:
    """
    异步包装，供既有的 async 调用方（如 KnowledgeService）直接委托。
    """
    return convert_to_markdown_sync(file_path, file_type)
