"""
重排序服务 — 使用 fastembed TextCrossEncoder 对检索结果进行二次排序

模型: BAAI/bge-reranker-base（fastembed 内置支持）
无需额外依赖，复用 fastembed 包。
"""

import asyncio
from typing import Any, Dict, Iterable, List, Optional

from app.utils.logger import logger


class RerankerService:
    """
    Cross-Encoder 重排序服务

    使用 fastembed 的 TextCrossEncoder 对初始检索结果进行重排序，
    提升检索精度。模型在首次调用时懒加载。
    """

    DEFAULT_MODEL = "BAAI/bge-reranker-base"

    def __init__(self, model_name: Optional[str] = None):
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None

    def _load_model(self):
        """懒加载 Cross-Encoder 模型"""
        if self._model is not None:
            return

        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            logger.info(f"加载重排序模型: {self._model_name}")
            self._model = TextCrossEncoder(model_name=self._model_name)
            logger.info("重排序模型加载完成")
        except Exception as e:
            logger.error(f"重排序模型加载失败: {e}")
            raise

    async def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        对检索结果进行重排序

        Args:
            query: 查询文本
            documents: 检索结果列表，每个结果需包含 "content" 字段
            top_k: 返回 top-k 结果，None 时返回全部

        Returns:
            重排序后的结果列表，新增 "rerank_score" 字段
        """
        if not documents:
            return []

        # 在线程池中加载模型和执行推理（阻塞操作）
        def _do_rerank():
            import math

            self._load_model()

            # 提取文档内容
            doc_contents = [doc["content"] for doc in documents]

            # 批量计算相关性分数（原始 logits）
            scores: Iterable[float] = self._model.rerank(query, doc_contents)
            raw_scores = list(scores)

            # Sigmoid 归一化到 0-1
            normalized = [
                1.0 / (1.0 + math.exp(-score)) for score in raw_scores
            ]

            # 将分数附加到结果上
            for doc, score in zip(documents, normalized):
                doc["rerank_score"] = round(float(score), 4)

            # 按重排序分数降序排序
            documents.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

            # 截取 top_k
            if top_k is not None:
                return documents[:top_k]

            return documents

        return await asyncio.to_thread(_do_rerank)


# 全局单例
_reranker_instance: Optional[RerankerService] = None


def get_reranker_service(model_name: Optional[str] = None) -> RerankerService:
    """获取重排序服务单例"""
    global _reranker_instance
    if _reranker_instance is None:
        _reranker_instance = RerankerService(model_name)
    return _reranker_instance
