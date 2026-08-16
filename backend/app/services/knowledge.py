import os
import re
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.knowledge import Document, DocumentSegment, KnowledgeBase
from app.utils.logger import logger
from app.core.config import settings
from app.services.vector_store import vector_store_service


class KnowledgeService:
    """
    知识库服务 — 文档解析、语义分段、向量化、混合检索
    """

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 文档处理流水线
    # ------------------------------------------------------------------

    async def process_document(self, document_id: int) -> bool:
        """
        处理文档：解析 → 分段 → 向量化 → 更新状态
        """
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            logger.error(f"文档不存在: {document_id}")
            return False

        try:
            # 更新状态为处理中
            document.status = "processing"
            self.db.commit()

            # 1. 解析文档为 Markdown
            markdown_text = await self._convert_to_markdown(
                document.file_path, document.file_type
            )
            if not markdown_text or not markdown_text.strip():
                raise ValueError("文档解析结果为空")

            # 2. 后处理清理
            cleaned_text = self._clean_markdown(markdown_text)
            document.content = cleaned_text

            # 3. 语义分段
            metadata = {
                "source": document.name,
                "file_type": document.file_type,
            }
            chunks = self._split_text_semantic(cleaned_text, metadata)

            # 4. 存储分段记录到主数据库
            segments = []
            for i, chunk in enumerate(chunks):
                segment = DocumentSegment(
                    document_id=document.id,
                    content=chunk["content"],
                    token_count=len(chunk["content"]),
                    position=i,
                    metadata_=chunk.get("metadata"),
                )
                self.db.add(segment)
                segments.append(segment)

            # 刷新以获取 segment.id
            self.db.flush()

            # 5. 批量写入向量到 SQLiteVec
            texts = [seg.content for seg in segments]
            metadatas = [
                {
                    "segment_id": str(seg.id),
                    "document_id": str(document.id),
                    "kb_id": str(document.knowledge_base_id),
                    **(seg.metadata_ or {}),
                }
                for seg in segments
            ]
            vector_store_service.add_texts(
                kb_id=document.knowledge_base_id,
                texts=texts,
                metadatas=metadatas,
            )

            # 更新文档状态
            document.status = "completed"
            document.chunk_count = len(chunks)
            document.processed_at = datetime.utcnow()
            self.db.commit()

            # 更新知识库统计
            self._update_knowledge_base_stats(document.knowledge_base_id)

            logger.info(f"文档处理完成: {document.name}, 分段数: {len(chunks)}")
            return True

        except Exception as e:
            document.status = "failed"
            document.error_message = str(e)[:500]
            self.db.commit()
            logger.error(f"文档处理失败: {document.name} - {e}")
            return False

    # ------------------------------------------------------------------
    # 文档解析：统一转 Markdown
    # ------------------------------------------------------------------

    async def _convert_to_markdown(self, file_path: str, file_type: str) -> str:
        """
        使用 markitdown 将各种格式统一转为 Markdown
        """
        # 对 HTML 文件先做主体提取预处理
        if file_type == "html":
            file_path = self._preprocess_html(file_path)

        try:
            from markitdown import MarkItDown

            converter = MarkItDown()
            result = converter.convert(file_path)
            return (
                result.text_content if hasattr(result, "text_content") else str(result)
            )
        except ImportError:
            logger.warning("markitdown 未安装，使用 fallback 解析")
            return await self._fallback_parse(file_path, file_type)
        except Exception as e:
            logger.warning(f"markitdown 转换失败: {e}，使用 fallback 解析")
            return await self._fallback_parse(file_path, file_type)

    def _preprocess_html(self, file_path: str) -> str:
        """
        HTML 预处理：用 BeautifulSoup 提取主体内容，移除导航/页脚/广告
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
            if main:
                content = str(main)
            else:
                content = str(soup)

            # 写入临时文件
            temp_path = file_path + ".cleaned.html"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            return temp_path
        except ImportError:
            return file_path
        except Exception as e:
            logger.warning(f"HTML 预处理失败: {e}")
            return file_path

    async def _fallback_parse(self, file_path: str, file_type: str) -> str:
        """
        markitdown 不可用时的 fallback 解析
        """
        if file_type == "txt" or file_type == "markdown":
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
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
                    return text
            except ImportError:
                logger.warning("PyPDF2 未安装，无法解析 PDF")
                return ""

        if file_type == "docx":
            try:
                from docx import Document as DocxDocument

                doc = DocxDocument(file_path)
                text = ""
                for para in doc.paragraphs:
                    text += para.text + "\n"
                return text
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

    # ------------------------------------------------------------------
    # Markdown 后处理清理
    # ------------------------------------------------------------------

    def _clean_markdown(self, text: str) -> str:
        """
        清理 Markdown 文本：过滤页眉页脚、去重空行、移除页码行
        """
        lines = text.split("\n")

        # 1. 统计每行出现频率，移除重复超过 3 次的行（页眉/页脚）
        line_counts = Counter(line.strip() for line in lines if line.strip())
        repeated_lines = {line for line, count in line_counts.items() if count >= 3}

        # 页码行模式
        page_pattern = re.compile(
            r"^\s*(第\s*\d+\s*页|-\s*\d+\s*-|\d+\s*/\s*\d+|page\s*\d+)\s*$",
            re.IGNORECASE,
        )

        cleaned = []
        for line in lines:
            stripped = line.strip()
            # 跳过重复行（页眉页脚）
            if stripped in repeated_lines and len(stripped) < 80:
                continue
            # 跳过页码行
            if page_pattern.match(stripped):
                continue
            cleaned.append(line)

        # 2. 合并连续空行（超过 2 行合并为 1 行）
        result = []
        empty_count = 0
        for line in cleaned:
            if not line.strip():
                empty_count += 1
                if empty_count <= 1:
                    result.append(line)
            else:
                empty_count = 0
                result.append(line)

        return "\n".join(result).strip()

    # ------------------------------------------------------------------
    # 语义分段策略
    # ------------------------------------------------------------------

    def _split_text_semantic(
        self,
        text: str,
        metadata: dict,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        按 Markdown 标题层级切分，表格不拆行，超长段落再用滑动窗口细分
        """
        if not text:
            return []

        # 1. 按标题切分段落
        sections = self._split_by_headers(text)

        chunks = []
        for section in sections:
            header_path = section["header_path"]
            content = section["content"].strip()
            if not content:
                continue

            # 2. 检测段落中的表格块和普通文本
            blocks = self._split_into_blocks(content)

            for block in blocks:
                if block["type"] == "table":
                    # 表格作为整体，不拆行
                    if len(block["content"]) <= chunk_size:
                        chunks.append(
                            {
                                "content": block["content"],
                                "metadata": {
                                    **metadata,
                                    "header_path": header_path,
                                    "has_table": True,
                                },
                            }
                        )
                    else:
                        # 超大表格：按行分片，保留表头
                        table_chunks = self._split_large_table(
                            block["content"], chunk_size, chunk_overlap
                        )
                        for tc in table_chunks:
                            chunks.append(
                                {
                                    "content": tc,
                                    "metadata": {
                                        **metadata,
                                        "header_path": header_path,
                                        "has_table": True,
                                    },
                                }
                            )
                else:
                    # 普通文本：滑动窗口细分
                    if len(block["content"]) <= chunk_size:
                        chunks.append(
                            {
                                "content": block["content"],
                                "metadata": {
                                    **metadata,
                                    "header_path": header_path,
                                    "has_table": False,
                                },
                            }
                        )
                    else:
                        text_chunks = self._sliding_window_split(
                            block["content"], chunk_size, chunk_overlap
                        )
                        for tc in text_chunks:
                            chunks.append(
                                {
                                    "content": tc,
                                    "metadata": {
                                        **metadata,
                                        "header_path": header_path,
                                        "has_table": False,
                                    },
                                }
                            )

        # 3. 编号
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i

        return chunks

    def _split_by_headers(self, text: str) -> List[Dict[str, str]]:
        """
        按 Markdown 标题 (# ## ###) 切分，返回带 header_path 的段落列表
        """
        header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        matches = list(header_pattern.finditer(text))

        if not matches:
            return [{"header_path": "", "content": text}]

        sections = []
        # 标题前的内容
        if matches[0].start() > 0:
            preamble = text[: matches[0].start()].strip()
            if preamble:
                sections.append({"header_path": "", "content": preamble})

        # 维护标题层级栈
        header_stack: List[str] = []

        for i, match in enumerate(matches):
            level = len(match.group(1))
            title = match.group(2).strip()

            # 更新标题栈
            while header_stack and len(header_stack) >= level:
                header_stack.pop()
            header_stack.append(title)

            # 获取段落内容（到下一个同级或更高级标题）
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            if content:
                sections.append(
                    {
                        "header_path": " > ".join(header_stack),
                        "content": content,
                    }
                )

        return sections

    def _split_into_blocks(self, text: str) -> List[Dict[str, Any]]:
        """
        将段落拆分为表格块和普通文本块
        """
        lines = text.split("\n")
        blocks = []
        current_text_lines: List[str] = []
        current_table_lines: List[str] = []
        in_table = False

        for line in lines:
            is_table_line = line.strip().startswith("|")

            if is_table_line:
                if current_text_lines:
                    blocks.append(
                        {
                            "type": "text",
                            "content": "\n".join(current_text_lines),
                        }
                    )
                    current_text_lines = []
                in_table = True
                current_table_lines.append(line)
            else:
                if in_table and current_table_lines:
                    blocks.append(
                        {
                            "type": "table",
                            "content": "\n".join(current_table_lines),
                        }
                    )
                    current_table_lines = []
                    in_table = False
                current_text_lines.append(line)

        # 收尾
        if current_table_lines:
            blocks.append(
                {
                    "type": "table",
                    "content": "\n".join(current_table_lines),
                }
            )
        if current_text_lines:
            blocks.append(
                {
                    "type": "text",
                    "content": "\n".join(current_text_lines),
                }
            )

        return blocks

    def _split_large_table(
        self, table_text: str, chunk_size: int, chunk_overlap: int
    ) -> List[str]:
        """
        超大表格按行分片，每个子 chunk 保留表头行
        """
        lines = table_text.split("\n")
        if len(lines) < 2:
            return [table_text]

        # 前两行通常是表头和分隔线
        header_lines = lines[:2]
        data_lines = lines[2:]
        header_text = "\n".join(header_lines)

        chunks = []
        current_lines: List[str] = []
        current_size = len(header_text)

        for line in data_lines:
            line_size = len(line) + 1  # +1 for newline
            if current_size + line_size > chunk_size and current_lines:
                chunk_content = header_text + "\n" + "\n".join(current_lines)
                chunks.append(chunk_content)
                # overlap: 保留最后几行
                overlap_lines = current_lines[
                    -(chunk_overlap // (len(line) + 1) or 1) :
                ]
                current_lines = overlap_lines
                current_size = len(header_text) + sum(len(l) + 1 for l in current_lines)

            current_lines.append(line)
            current_size += line_size

        if current_lines:
            chunks.append(header_text + "\n" + "\n".join(current_lines))

        return chunks

    def _sliding_window_split(
        self, text: str, chunk_size: int, chunk_overlap: int
    ) -> List[str]:
        """
        按句子边界滑动窗口分段
        """
        if not text:
            return []

        segments = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)

            # 尝试在句子边界断开
            if end < text_len:
                for sep in ["。", "\n", "！", "？", ".", "!", "?", "；", ";"]:
                    pos = text.rfind(sep, start, end)
                    if pos > start:
                        end = pos + 1
                        break

            segment = text[start:end].strip()
            if segment:
                segments.append(segment)

            # 下一个窗口起点
            next_start = end - chunk_overlap
            if next_start <= start:
                # 防止死循环
                next_start = end
            start = next_start

        return segments

    # ------------------------------------------------------------------
    # 混合检索
    # ------------------------------------------------------------------

    async def search(
        self,
        kb_id: int,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """
        混合检索：SQLiteVec 向量相似度 + 关键词匹配
        """
        # 1. SQLiteVec 向量检索（多取一些用于混合重排）
        vector_results = vector_store_service.similarity_search(
            kb_id=kb_id,
            query=query,
            k=top_k * 3,
        )

        if not vector_results:
            return []

        # 2. 收集 segment_id，批量查询主库补充完整信息
        segment_ids = []
        for item in vector_results:
            meta = item.get("metadata", {})
            sid = meta.get("segment_id")
            if sid:
                segment_ids.append(int(sid))

        segments_map = {}
        if segment_ids:
            segments = (
                self.db.query(DocumentSegment)
                .filter(DocumentSegment.id.in_(segment_ids))
                .all()
            )
            segments_map = {seg.id: seg for seg in segments}

        # 批量查询文档名
        doc_ids = {seg.document_id for seg in segments_map.values()}
        docs_map = {}
        if doc_ids:
            docs = self.db.query(Document).filter(Document.id.in_(doc_ids)).all()
            docs_map = {doc.id: doc for doc in docs}

        # 3. 混合打分：向量相似度 + 关键词匹配
        query_words = set(query.lower().split())
        results = []

        for item in vector_results:
            meta = item.get("metadata", {})
            sid = meta.get("segment_id")
            if not sid:
                continue

            segment = segments_map.get(int(sid))
            if not segment:
                continue

            # 向量相似度分数（SQLiteVec 返回的距离，越小越相似，取反转为越大越好）
            vector_score = max(0.0, 1.0 - item["score"])

            # 关键词匹配加分
            content_lower = segment.content.lower()
            keyword_hits = sum(1 for word in query_words if word in content_lower)
            keyword_score = keyword_hits / max(len(query_words), 1) * 0.3

            # 综合分数
            final_score = vector_score * 0.7 + keyword_score * 0.3

            if final_score >= score_threshold:
                doc = docs_map.get(segment.document_id)
                results.append(
                    {
                        "segment_id": segment.id,
                        "document_id": segment.document_id,
                        "document_name": doc.name if doc else "",
                        "content": segment.content,
                        "score": round(final_score, 4),
                        "metadata": segment.metadata_,
                    }
                )

        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    # ------------------------------------------------------------------
    # 文档删除
    # ------------------------------------------------------------------

    def delete_document(self, document_id: int) -> bool:
        """删除文档及其所有分段"""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False

        kb_id = document.knowledge_base_id

        # 删除向量数据
        vector_store_service.delete_by_metadata(
            kb_id=kb_id,
            filter_key="document_id",
            filter_value=str(document_id),
        )

        # 删除分段
        self.db.query(DocumentSegment).filter(
            DocumentSegment.document_id == document_id
        ).delete()

        # 删除文件
        if document.file_path and os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except OSError:
                pass

        # 删除文档记录
        self.db.delete(document)
        self.db.commit()

        # 更新知识库统计
        self._update_knowledge_base_stats(kb_id)
        return True

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _update_knowledge_base_stats(self, kb_id: int):
        """更新知识库统计信息"""
        kb = self.db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.document_count = (
                self.db.query(Document)
                .filter(
                    Document.knowledge_base_id == kb_id, Document.status == "completed"
                )
                .count()
            )
            kb.chunk_count = (
                self.db.query(DocumentSegment)
                .join(Document)
                .filter(Document.knowledge_base_id == kb_id)
                .count()
            )
            self.db.commit()


def get_knowledge_service(db: Session) -> KnowledgeService:
    return KnowledgeService(db)
