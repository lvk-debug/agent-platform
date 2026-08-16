"""
向量存储服务 — 基于 LangChain SQLiteVec + sqlite-vec

将 fastembed 封装为 LangChain Embeddings 接口，
使用 SQLiteVec 管理向量的存储和相似度检索。
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlite_vec
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import SQLiteVec

from app.core.config import settings
from app.utils.logger import logger


class ConfigurableSQLiteVec(SQLiteVec):
    """支持显式指定维度的 SQLiteVec 子类，避免每次创建表时做 dummy embedding"""

    _dimension: int = 0

    def get_dimensionality(self) -> int:
        if self._dimension > 0:
            return self._dimension
        return super().get_dimensionality()

# 强制离线模式，使用本地缓存的 embedding 模型
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"


class FastEmbedEmbeddings(Embeddings):
    """
    将 fastembed 封装为 LangChain Embeddings 接口
    """

    def __init__(
        self, model_name: Optional[str] = None, cache_dir: Optional[str] = None
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._cache_dir = cache_dir or settings.EMBEDDING_MODEL_PATH
        self._embedder = None

    def _get_embedder(self):
        if self._embedder is None:
            from fastembed import TextEmbedding

            cache_path = Path(self._cache_dir)
            if cache_path.exists():
                logger.info("Using local embedding model: %s", self._cache_dir)
            else:
                logger.warning(
                    "Local model not found at %s, will use remote", self._cache_dir
                )

            self._embedder = TextEmbedding(
                model_name=self._model_name,
                cache_dir=Path(self._cache_dir),
                local_files_only=True,
                max_length=512,
            )
            logger.info("fastembed embedding 模型已加载")
        return self._embedder

    # 大多数 fastembed 模型的 max_seq_length 为 512 tokens
    # 中文约 1-2 字符/token，保守截断到 800 字符
    MAX_CHARS = 800
    # 每批处理的文本数，控制 ONNX 内存峰值
    BATCH_SIZE = 8

    @staticmethod
    def _truncate(text: str) -> str:
        """截断超长文本，避免 ONNX 内存溢出"""
        if len(text) > FastEmbedEmbeddings.MAX_CHARS:
            return text[: FastEmbedEmbeddings.MAX_CHARS]
        return text

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """单批 embedding，内部使用"""
        embedder = self._get_embedder()
        embeddings = list(embedder.embed(texts))
        return [
            emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings
        ]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """分批生成文档 embedding，避免 ONNX 内存溢出"""
        truncated = [self._truncate(t) for t in texts]
        results: List[List[float]] = []
        for i in range(0, len(truncated), self.BATCH_SIZE):
            batch = truncated[i : i + self.BATCH_SIZE]
            results.extend(self._embed_batch(batch))
        return results

    def embed_query(self, text: str) -> List[float]:
        """生成查询 embedding"""
        return self._embed_batch([self._truncate(text)])[0]


class VectorStoreService:
    """
    向量存储服务 — 管理 SQLiteVec 实例，提供统一的向量操作接口

    每个知识库使用独立的 collection（kb_{id}），向量数据存放在 VECTOR_DB_DIR 目录下。
    """

    def __init__(self):
        self._stores: Dict[int, SQLiteVec] = {}
        self._embeddings: Optional[FastEmbedEmbeddings] = None

    @property
    def embeddings(self) -> FastEmbedEmbeddings:
        if self._embeddings is None:
            self._embeddings = FastEmbedEmbeddings()
        return self._embeddings

    def _get_db_path(self, kb_id: int) -> str:
        """获取知识库向量数据库文件路径"""
        db_dir = Path(settings.VECTOR_DB_DIR)
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / f"kb_{kb_id}.db")

    def _get_collection_name(self, kb_id: int) -> str:
        """获取知识库 collection 名称"""
        return f"kb_{kb_id}"

    def get_store(self, kb_id: int) -> SQLiteVec:
        """获取或创建知识库对应的 SQLiteVec 实例"""
        if kb_id not in self._stores:
            db_file = self._get_db_path(kb_id)
            table = self._get_collection_name(kb_id)
            connection = sqlite3.connect(db_file)
            connection.row_factory = sqlite3.Row
            connection.enable_load_extension(True)
            sqlite_vec.load(connection)
            store = ConfigurableSQLiteVec(
                connection=connection,
                table=table,
                embedding=self.embeddings,
            )
            store._dimension = settings.EMBEDDING_DIMENSION
            self._stores[kb_id] = store
            logger.info(
                "SQLiteVec 实例已创建: kb_id=%d, db=%s, table=%s", kb_id, db_file, table
            )
        return self._stores[kb_id]

    def add_texts(
        self,
        kb_id: int,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        向知识库添加文本向量

        Args:
            kb_id: 知识库 ID
            texts: 文本列表
            metadatas: 元数据列表
            ids: 自定义 ID 列表

        Returns:
            添加的向量 ID 列表
        """
        store = self.get_store(kb_id)
        vector_ids = store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        logger.info("已添加 %d 条向量到知识库 %d", len(vector_ids), kb_id)
        return vector_ids

    def similarity_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        向量相似度检索

        Args:
            kb_id: 知识库 ID
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索结果列表，每项包含 content, metadata, score
        """
        store = self.get_store(kb_id)

        try:
            # similarity_search_with_score 返回 (Document, score) 元组
            results = store.similarity_search_with_score(query, k=k)
        except Exception as e:
            logger.error("向量检索失败 kb_id=%d: %s", kb_id, e)
            # 回退到无 score 的检索
            docs = store.similarity_search(query, k=k)
            results = [(doc, 0.0) for doc in docs]

        items = []
        for doc, score in results:
            items.append(
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
            )

        return items

    def delete_by_metadata(
        self,
        kb_id: int,
        filter_key: str,
        filter_value: str,
    ) -> int:
        """
        按元数据条件删除向量

        Args:
            kb_id: 知识库 ID
            filter_key: 过滤键
            filter_value: 过滤值

        Returns:
            删除的向量数量
        """
        store = self.get_store(kb_id)
        table = self._get_collection_name(kb_id)
        try:
            # SQLiteVec 存储表包含 rowid 和 metadata 列
            # 先查出匹配的 rowid，再删除
            cursor = store._connection.execute(
                f"SELECT rowid FROM {table} WHERE json_extract(metadata, '$.{filter_key}') = ?",
                (filter_value,),
            )
            rows = cursor.fetchall()
            if not rows:
                return 0

            rowids = [row[0] for row in rows]
            placeholders = ",".join("?" * len(rowids))
            store._connection.execute(
                f"DELETE FROM {table} WHERE rowid IN ({placeholders})",
                rowids,
            )
            store._connection.commit()
            logger.info(
                "已删除 %d 条向量 (kb_id=%d, %s=%s)",
                len(rowids),
                kb_id,
                filter_key,
                filter_value,
            )
            return len(rowids)
        except Exception as e:
            logger.warning("删除向量失败 kb_id=%d: %s", kb_id, e)
            return 0

    def delete_collection(self, kb_id: int) -> bool:
        """
        删除整个知识库的向量数据

        Args:
            kb_id: 知识库 ID

        Returns:
            是否删除成功
        """
        # 关闭连接并清理缓存
        if kb_id in self._stores:
            store = self._stores.pop(kb_id)
            # SQLiteVec 内部持有 connection，尝试关闭
            try:
                store._connection.close()
            except Exception:
                pass

        # 删除数据库文件
        db_file = self._get_db_path(kb_id)
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
                # 同时删除 WAL 和 SHM 文件
                for suffix in ["-wal", "-shm"]:
                    wal_file = db_file + suffix
                    if os.path.exists(wal_file):
                        os.remove(wal_file)
                logger.info("已删除向量数据库: %s", db_file)
                return True
            except OSError as e:
                logger.error("删除向量数据库失败: %s - %s", db_file, e)
                return False
        return True


# 全局单例
vector_store_service = VectorStoreService()
