"""
向量存储服务 — 支持 SQLiteVec 和 Qdrant 两种后端

将 fastembed 封装为 LangChain Embeddings 接口，
提供统一的向量存储和检索接口。
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.embeddings import Embeddings

from app.core.config import settings
from app.utils.logger import logger


class VectorStoreBase(ABC):
    """向量存储抽象基类"""

    # True = score 是距离（越小越相似，如余弦距离）
    # False = score 是相似度/融合分数（越大越好，如 RRF）
    score_is_distance: bool = True

    @abstractmethod
    def add_texts(
        self,
        kb_id: int,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """添加文本向量"""
        pass

    @abstractmethod
    def similarity_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """向量相似度检索"""
        pass

    @abstractmethod
    def bm25_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """BM25 全文检索"""
        pass

    @abstractmethod
    def delete_by_metadata(
        self,
        kb_id: int,
        filter_key: str,
        filter_value: str,
    ) -> int:
        """按元数据条件删除向量"""
        pass

    @abstractmethod
    def delete_collection(self, kb_id: int) -> bool:
        """删除整个知识库的向量数据"""
        pass


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
            )
            logger.info("fastembed embedding 模型已加载")
        return self._embedder

    # BGE-small-zh max_length=512 tokens，中文 1字≈1~2 tokens
    # chunk_size=500 字符，800 留足余量避免截断表格数据
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


# ============ SQLiteVec 后端 ============

try:
    import sqlite_vec
    from langchain_community.vectorstores import SQLiteVec

    class ConfigurableSQLiteVec(SQLiteVec):
        """支持显式指定维度的 SQLiteVec 子类，避免每次创建表时做 dummy embedding"""

        _dimension: int = 0

        def get_dimensionality(self) -> int:
            if self._dimension > 0:
                return self._dimension
            return super().get_dimensionality()

    SQLITE_VEC_AVAILABLE = True
except ImportError:
    SQLITE_VEC_AVAILABLE = False
    logger.warning("sqlite-vec 未安装，SQLiteVec 后端不可用")


class SQLiteVecStoreService(VectorStoreBase):
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

    def _get_fts_table_name(self, kb_id: int) -> str:
        """获取 FTS5 虚拟表名称"""
        return f"kb_{kb_id}_fts"

    def _ensure_fts_table(self, kb_id: int) -> None:
        """确保 FTS5 虚拟表已创建（unicode61 tokenizer 支持中文）"""
        store = self.get_store(kb_id)
        fts_table = self._get_fts_table_name(kb_id)
        store._connection.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table}
            USING fts5(content, metadata, segment_id UNINDEXED, tokenize='unicode61 remove_diacritics 2')
            """)
        store._connection.commit()

    def get_store(self, kb_id: int) -> SQLiteVec:
        """获取或创建知识库对应的 SQLiteVec 实例"""
        if kb_id not in self._stores:
            db_file = self._get_db_path(kb_id)
            table = self._get_collection_name(kb_id)
            connection = sqlite3.connect(db_file, check_same_thread=False)
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
            self._ensure_fts_table(kb_id)
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
        向知识库添加文本向量，同时同步写入 FTS5 索引

        SQLiteVec.add_texts 内部已使用 embed_documents 批量 embed + executemany 批量插入，
        此处额外用 executemany 批量写入 FTS5 索引，避免逐条 INSERT 开销。

        Args:
            kb_id: 知识库 ID
            texts: 文本列表
            metadatas: 元数据列表
            ids: 自定义 ID 列表

        Returns:
            添加的向量 ID 列表
        """
        import json

        store = self.get_store(kb_id)
        fts_table = self._get_fts_table_name(kb_id)

        if not texts:
            return []

        # 1) SQLiteVec 原生批量插入（内部 embed_documents + executemany）
        vector_ids = store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

        # 2) executemany 批量写入 FTS5 索引
        if metadatas is None:
            metadatas = [{} for _ in texts]
        fts_rows = [
            (text, json.dumps(meta, ensure_ascii=False), meta.get("segment_id", ""))
            for text, meta in zip(texts, metadatas)
        ]
        store._connection.executemany(
            f"INSERT INTO {fts_table}(content, metadata, segment_id) VALUES (?, ?, ?)",
            fts_rows,
        )
        store._connection.commit()

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

    def bm25_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        BM25 全文检索（基于 FTS5）

        Args:
            kb_id: 知识库 ID
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索结果列表，每项包含 content, metadata, score
        """
        store = self.get_store(kb_id)
        fts_table = self._get_fts_table_name(kb_id)

        try:
            # FTS5 的 bm25() 函数返回负值（越小越相关），取反转为正分
            cursor = store._connection.execute(
                f"""
                SELECT content, metadata, segment_id, bm25({fts_table}) AS rank
                FROM {fts_table}
                WHERE {fts_table} MATCH ?
                ORDER BY rank
                LIMIT ?
                """,
                (query, k),
            )
            rows = cursor.fetchall()

            items = []
            import json

            for row in rows:
                meta = json.loads(row["metadata"]) if row["metadata"] else {}
                # bm25 返回负值，取反使其越大越好
                items.append(
                    {
                        "content": row["content"],
                        "metadata": meta,
                        "score": -float(row["rank"]),
                    }
                )
            return items
        except Exception as e:
            logger.warning("BM25 检索失败 kb_id=%d: %s", kb_id, e)
            return []

    def delete_by_metadata(
        self,
        kb_id: int,
        filter_key: str,
        filter_value: str,
    ) -> int:
        """
        按元数据条件删除向量，同时清理 FTS5 索引

        Args:
            kb_id: 知识库 ID
            filter_key: 过滤键
            filter_value: 过滤值

        Returns:
            删除的向量数量
        """
        store = self.get_store(kb_id)
        table = self._get_collection_name(kb_id)
        fts_table = self._get_fts_table_name(kb_id)
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
            # 同步删除 FTS5 索引
            store._connection.execute(
                f"DELETE FROM {fts_table} WHERE segment_id IN ({placeholders})",
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
        删除整个知识库的向量数据及 FTS5 索引

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


# ============ Qdrant 后端 ============


class QdrantStoreService(VectorStoreBase):
    """
    Qdrant 向量存储服务 — Dense + Sparse BM25 混合检索

    每个知识库使用独立的 collection（kb_{id}），同时存储 dense 和 sparse 向量。
    检索时使用 Qdrant Prefetch API 做 dense + sparse 混合检索，内部 RRF 融合排名。
    """

    score_is_distance = False  # RRF 融合分数，越大越好

    def __init__(self):
        self._client = None
        self._embeddings: Optional[FastEmbedEmbeddings] = None
        self._sparse_embedder = None
        self._collections_cache: set = set()

    @property
    def embeddings(self) -> FastEmbedEmbeddings:
        if self._embeddings is None:
            self._embeddings = FastEmbedEmbeddings()
        return self._embeddings

    @property
    def sparse_embedder(self):
        """懒加载 fastembed 稀疏模型（BM25）"""
        if self._sparse_embedder is None:
            from fastembed import SparseTextEmbedding

            model_name = settings.EMBEDDING_SPARSE_MODEL or "Qdrant/bm25"
            cache_dir = settings.EMBEDDING_MODEL_PATH or None
            kwargs = {"model_name": model_name}
            if cache_dir and Path(cache_dir).exists():
                kwargs["cache_dir"] = Path(cache_dir)
            self._sparse_embedder = SparseTextEmbedding(**kwargs)
            logger.info("fastembed 稀疏模型已加载: %s", model_name)
        return self._sparse_embedder

    @property
    def client(self):
        """懒加载 Qdrant 客户端"""
        if self._client is None:
            from qdrant_client import QdrantClient

            url = settings.QDRANT_URL
            if not url:
                raise ValueError("QDRANT_URL 未配置")

            self._client = QdrantClient(
                url=url,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=30,
            )
            logger.info("Qdrant 客户端已连接: %s", url)
        return self._client

    def _get_collection_name(self, kb_id: int) -> str:
        """获取 collection 名称（统一使用同一个 collection，按 kb_id payload 隔离）"""
        return settings.QDRANT_COLLECTION or "agent_platform"

    def _kb_filter(self, kb_id: int):
        """构建 kb_id payload 过滤条件（kb_id 在 payload 中存储为字符串）"""
        from qdrant_client.http import models as rest

        return rest.Filter(
            must=[
                rest.FieldCondition(
                    key="kb_id",
                    match=rest.MatchValue(value=str(kb_id)),
                )
            ]
        )

    def _has_named_vectors(self, collection_name: str) -> bool:
        """检查 collection 是否已配置 named vectors（dense + bm25）"""
        try:
            info = self.client.get_collection(collection_name)
            config = info.config
            # 检查是否存在名为 dense 的向量和名为 bm25 的稀疏向量
            has_dense = (
                config.params.vectors is not None
                and isinstance(config.params.vectors, dict)
                and "dense" in config.params.vectors
            )
            has_bm25 = (
                config.params.sparse_vectors is not None
                and "bm25" in config.params.sparse_vectors
            )
            return has_dense and has_bm25
        except Exception:
            return False

    def _ensure_collection(self, kb_id: int) -> str:
        """确保 collection 存在，同时配置 dense + sparse 向量"""
        from qdrant_client.http import models as rest

        collection_name = self._get_collection_name(kb_id)

        if collection_name not in self._collections_cache:
            try:
                collections = self.client.get_collections().collections
                existing = {c.name for c in collections}

                need_create = collection_name not in existing
                need_recreate = False

                if not need_create:
                    # collection 已存在，检查向量配置是否匹配
                    if not self._has_named_vectors(collection_name):
                        logger.warning(
                            "Qdrant collection %s 向量配置不匹配（缺少 dense/bm25 named vectors），将重建",
                            collection_name,
                        )
                        self.client.delete_collection(collection_name)
                        need_recreate = True

                if need_create or need_recreate:
                    dimension = settings.EMBEDDING_DIMENSION or 512
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config={
                            "dense": rest.VectorParams(
                                size=dimension,
                                distance=rest.Distance.COSINE,
                            ),
                        },
                        sparse_vectors_config={
                            "bm25": rest.SparseVectorParams(
                                index=rest.SparseIndexParams(),
                            ),
                        },
                    )
                    logger.info(
                        "Qdrant collection 已创建: %s (dense=%d, sparse=bm25)",
                        collection_name,
                        dimension,
                    )

                # kb_id 过滤每次检索都要走，建 keyword 索引避免全量扫描
                try:
                    self.client.create_payload_index(
                        collection_name=collection_name,
                        field_name="kb_id",
                        field_schema=rest.PayloadSchemaType.KEYWORD,
                    )
                except Exception as idx_err:  # 索引已存在时会报冲突，忽略即可
                    logger.debug("kb_id payload 索引跳过: %s", idx_err)

                self._collections_cache.add(collection_name)
            except Exception as e:
                logger.error("Qdrant collection 检查失败: %s", e)
                raise

        return collection_name

    def _embed_sparse(self, texts: List[str]):
        """批量生成稀疏向量"""
        results = list(self.sparse_embedder.embed(texts))
        sparse_vectors = []
        for embedding in results:
            from qdrant_client.http import models as rest

            sparse_vectors.append(
                rest.SparseVector(
                    indices=embedding.indices.tolist(),
                    values=embedding.values.tolist(),
                )
            )
        return sparse_vectors

    def add_texts(
        self,
        kb_id: int,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """
        向知识库添加文本向量（同时写入 dense 和 sparse 向量）

        Args:
            kb_id: 知识库 ID
            texts: 文本列表
            metadatas: 元数据列表
            ids: 自定义 ID 列表

        Returns:
            添加的向量 ID 列表
        """
        from qdrant_client.http import models as rest
        from uuid import uuid4

        collection_name = self._ensure_collection(kb_id)

        if not texts:
            return []

        # 生成 dense + sparse embedding
        dense_embeddings = self.embeddings.embed_documents(texts)
        sparse_embeddings = self._embed_sparse(texts)

        # 生成 ID
        if ids is None:
            ids = [str(uuid4()) for _ in texts]

        if metadatas is None:
            metadatas = [{} for _ in texts]

        # 构建 Qdrant points（named vectors: dense + bm25）
        points = []
        for i, (text, dense_emb, sparse_emb, metadata) in enumerate(
            zip(texts, dense_embeddings, sparse_embeddings, metadatas)
        ):
            payload = {
                "content": text,
                # 统一存字符串：过滤条件用 MatchValue(str) 匹配
                "kb_id": str(kb_id),
                **metadata,
            }
            points.append(
                rest.PointStruct(
                    id=ids[i],
                    vector={
                        "dense": dense_emb,
                        "bm25": sparse_emb,
                    },
                    payload=payload,
                )
            )

        # 批量上传
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=collection_name,
                points=batch,
            )

        logger.info(
            "已添加 %d 条向量到 Qdrant collection %s (dense + sparse)",
            len(ids),
            collection_name,
        )
        return ids

    def similarity_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Dense + Sparse BM25 混合检索（Qdrant Prefetch + RRF 融合）

        使用 Qdrant 原生 Query API：
        - Prefetch 同时查询 dense 和 sparse 向量
        - fusion=RRECIPROCAL_RRF 做排名融合
        - 最终取 top-k 结果

        Args:
            kb_id: 知识库 ID
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索结果列表，每项包含 content, metadata, score
        """
        from qdrant_client.http import models as rest

        collection_name = self._ensure_collection(kb_id)

        # 生成查询向量（dense + sparse）
        query_dense = self.embeddings.embed_query(query)
        query_sparse_list = list(self.sparse_embedder.embed([query]))
        query_sparse = rest.SparseVector(
            indices=query_sparse_list[0].indices.tolist(),
            values=query_sparse_list[0].values.tolist(),
        )

        try:
            # kb_id 过滤（共享 collection 时隔离不同知识库）
            kb_filter = self._kb_filter(kb_id)

            # Qdrant Query API: Prefetch + Fusion
            results = self.client.query_points(
                collection_name=collection_name,
                prefetch=[
                    rest.Prefetch(
                        query=query_dense,
                        using="dense",
                        limit=k * 3,
                        filter=kb_filter,
                    ),
                    rest.Prefetch(
                        query=query_sparse,
                        using="bm25",
                        limit=k * 3,
                        filter=kb_filter,
                    ),
                ],
                query=rest.FusionQuery(fusion=rest.Fusion.RRF),
                query_filter=kb_filter,
                limit=k,
                with_payload=True,
            )

            items = []
            for hit in results.points:
                payload = hit.payload or {}
                items.append(
                    {
                        "content": payload.get("content", ""),
                        "metadata": {
                            k: v
                            for k, v in payload.items()
                            if k not in ("content", "kb_id")
                        },
                        "score": float(hit.score) if hit.score else 0.0,
                    }
                )

            return items
        except Exception as e:
            logger.error("Qdrant 混合检索失败 kb_id=%d: %s", kb_id, e)
            # 回退到纯 dense 检索
            try:
                kb_filter = self._kb_filter(kb_id)
                results = self.client.query_points(
                    collection_name=collection_name,
                    query=query_dense,
                    using="dense",
                    query_filter=kb_filter,
                    limit=k,
                    with_payload=True,
                )
                return [
                    {
                        "content": hit.payload.get("content", ""),
                        "metadata": {
                            k: v
                            for k, v in (hit.payload or {}).items()
                            if k not in ("content", "kb_id")
                        },
                        "score": float(hit.score) if hit.score else 0.0,
                    }
                    for hit in results.points
                ]
            except Exception as e2:
                logger.error("Qdrant 回退检索也失败 kb_id=%d: %s", kb_id, e2)
                return []

    def bm25_search(
        self,
        kb_id: int,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        纯 Sparse BM25 检索（使用 Qdrant 稀疏向量）

        Args:
            kb_id: 知识库 ID
            query: 查询文本
            k: 返回结果数量

        Returns:
            检索结果列表，每项包含 content, metadata, score
        """
        from qdrant_client.http import models as rest

        collection_name = self._ensure_collection(kb_id)

        # 生成查询稀疏向量
        query_sparse_list = list(self.sparse_embedder.embed([query]))
        query_sparse = rest.SparseVector(
            indices=query_sparse_list[0].indices.tolist(),
            values=query_sparse_list[0].values.tolist(),
        )

        try:
            kb_filter = self._kb_filter(kb_id)
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_sparse,
                using="bm25",
                query_filter=kb_filter,
                limit=k,
                with_payload=True,
            )

            items = []
            for hit in results.points:
                payload = hit.payload or {}
                items.append(
                    {
                        "content": payload.get("content", ""),
                        "metadata": {
                            k: v
                            for k, v in payload.items()
                            if k not in ("content", "kb_id")
                        },
                        "score": float(hit.score) if hit.score else 0.0,
                    }
                )

            return items
        except Exception as e:
            logger.warning("Qdrant BM25 检索失败 kb_id=%d: %s", kb_id, e)
            return []

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
        from qdrant_client.http import models as rest

        collection_name = self._ensure_collection(kb_id)

        try:
            # 构建过滤条件（共享 collection 时追加 kb_id 隔离）
            conditions = [
                rest.FieldCondition(
                    key="kb_id",
                    match=rest.MatchValue(value=str(kb_id)),
                ),
                rest.FieldCondition(
                    key=filter_key,
                    match=rest.MatchValue(value=filter_value),
                ),
            ]

            # 查询匹配的记录
            results = self.client.scroll(
                collection_name=collection_name,
                scroll_filter=rest.Filter(must=conditions),
                limit=10000,
                with_payload=False,
                with_vectors=False,
            )
            points = results[0]

            if not points:
                return 0

            # 删除匹配的点
            point_ids = [point.id for point in points]
            self.client.delete(
                collection_name=collection_name,
                points_selector=rest.PointIdsList(points=point_ids),
            )

            logger.info(
                "已删除 %d 条向量 (kb_id=%d, %s=%s)",
                len(point_ids),
                kb_id,
                filter_key,
                filter_value,
            )
            return len(point_ids)
        except Exception as e:
            logger.warning("Qdrant 删除向量失败 kb_id=%d: %s", kb_id, e)
            return 0

    def delete_collection(self, kb_id: int) -> bool:
        """
        删除知识库的向量数据（按 kb_id 过滤删除对应 points，不影响其他知识库）

        Args:
            kb_id: 知识库 ID

        Returns:
            是否删除成功
        """
        from qdrant_client.http import models as rest

        collection_name = self._get_collection_name(kb_id)

        try:
            collections = self.client.get_collections().collections
            existing = {c.name for c in collections}

            if collection_name not in existing:
                return True

            self.client.delete(
                collection_name=collection_name,
                points_selector=rest.FilterSelector(
                    filter=self._kb_filter(kb_id),
                ),
            )
            logger.info("已删除 Qdrant 知识库 %d 的向量 (collection: %s)", kb_id, collection_name)
            return True
        except Exception as e:
            logger.error("删除 Qdrant 向量失败 kb_id=%d: %s", kb_id, e)
            return False


# ============ 工厂函数 ============


def create_vector_store_service() -> VectorStoreBase:
    """
    根据配置创建向量存储服务实例

    Returns:
        VectorStoreBase 子类实例
    """
    store_type = settings.VECTOR_STORE

    if store_type == "qdrant_vector":
        if not settings.QDRANT_URL:
            raise ValueError("VECTOR_STORE=qdrant_vector 但 QDRANT_URL 未配置")
        logger.info("使用 Qdrant 向量数据库: %s", settings.QDRANT_URL)
        return QdrantStoreService()
    elif store_type == "sqlite_vector":
        if not SQLITE_VEC_AVAILABLE:
            raise ImportError("VECTOR_STORE=sqlite_vector 但 sqlite-vec 未安装")
        logger.info("使用 SQLiteVec 向量数据库")
        return SQLiteVecStoreService()
    else:
        raise ValueError(f"不支持的向量数据库类型: {store_type}")


# 全局单例（延迟初始化）
_vector_store_service: Optional[VectorStoreBase] = None


def get_vector_store_service() -> VectorStoreBase:
    """获取向量存储服务单例"""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = create_vector_store_service()
    return _vector_store_service


# 兼容旧代码的别名
vector_store_service = None  # 将在首次访问时初始化
