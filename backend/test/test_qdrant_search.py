"""
直接测试 Qdrant 检索，排查无结果问题

用法:
    cd e:/OpenSource/agent-platform/backend && /d/AI/Miniconda3/envs/python311/python.exe test/test_qdrant_search.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def main():
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as rest

    client = QdrantClient(url=settings.QDRANT_URL, timeout=10)
    collection_name = settings.QDRANT_COLLECTION or "agent_platform"

    # 1. 基本信息
    info = client.get_collection(collection_name)
    print(f"collection: {collection_name}")
    print(f"points_count: {info.points_count}")

    if info.points_count == 0:
        print("\n✗ collection 为空，需要重新上传知识库数据")
        return

    # 2. 抽样一条，拿到真实 kb_id 和 content
    scroll = client.scroll(
        collection_name=collection_name,
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    sample = scroll[0][0]
    kb_id = sample.payload.get("kb_id", 1)
    sample_content = sample.payload.get("content", "")
    print(f"\n抽样数据:")
    print(f"  kb_id: {kb_id}")
    print(f"  content: {sample_content[:100]}...")

    # 3. 测试纯 dense 检索（最简单的方式）
    print(f"\n--- 测试 1: 纯 dense 检索 ---")
    try:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from app.services.vector_store import FastEmbedEmbeddings

        emb = FastEmbedEmbeddings()
        query_vec = emb.embed_query(sample_content[:50])  # 用抽样内容的前50字作为查询

        kb_filter = rest.Filter(
            must=[rest.FieldCondition(key="kb_id", match=rest.MatchValue(value=kb_id))]
        )

        result = client.query_points(
            collection_name=collection_name,
            query=query_vec,
            using="dense",
            query_filter=kb_filter,
            limit=3,
            with_payload=True,
        )
        print(f"  返回 {len(result.points)} 条")
        for hit in result.points:
            print(f"  score={hit.score:.4f} content={hit.payload.get('content', '')[:60]}")
    except Exception as e:
        import traceback
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()

    # 4. 测试纯 sparse 检索
    print(f"\n--- 测试 2: 纯 sparse (bm25) 检索 ---")
    try:
        from fastembed import SparseTextEmbedding

        model_name = settings.EMBEDDING_SPARSE_MODEL or "Qdrant/bm25"
        cache_dir = Path(settings.EMBEDDING_MODEL_PATH) if settings.EMBEDDING_MODEL_PATH else None
        kwargs = {"model_name": model_name}
        if cache_dir and cache_dir.exists():
            kwargs["cache_dir"] = cache_dir

        sparse = SparseTextEmbedding(**kwargs)
        query_sparse_list = list(sparse.embed([sample_content[:50]]))
        query_sparse = rest.SparseVector(
            indices=query_sparse_list[0].indices.tolist(),
            values=query_sparse_list[0].values.tolist(),
        )

        result = client.query_points(
            collection_name=collection_name,
            query=query_sparse,
            using="bm25",
            query_filter=kb_filter,
            limit=3,
            with_payload=True,
        )
        print(f"  返回 {len(result.points)} 条")
        for hit in result.points:
            print(f"  score={hit.score:.4f} content={hit.payload.get('content', '')[:60]}")
    except Exception as e:
        import traceback
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()

    # 5. 测试混合检索（RRF）
    print(f"\n--- 测试 3: Dense + Sparse 混合检索 (RRF) ---")
    try:
        result = client.query_points(
            collection_name=collection_name,
            prefetch=[
                rest.Prefetch(
                    query=query_vec,
                    using="dense",
                    limit=10,
                    filter=kb_filter,
                ),
                rest.Prefetch(
                    query=query_sparse,
                    using="bm25",
                    limit=10,
                    filter=kb_filter,
                ),
            ],
            query=rest.FusionQuery(fusion=rest.Fusion.RRF),
            limit=3,
            with_payload=True,
        )
        print(f"  返回 {len(result.points)} 条")
        for hit in result.points:
            print(f"  score={hit.score:.4f} content={hit.payload.get('content', '')[:60]}")
    except Exception as e:
        import traceback
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()

    # 6. 测试不用 filter 的情况
    print(f"\n--- 测试 4: 不带 kb_id 过滤的混合检索 ---")
    try:
        result = client.query_points(
            collection_name=collection_name,
            prefetch=[
                rest.Prefetch(
                    query=query_vec,
                    using="dense",
                    limit=10,
                ),
                rest.Prefetch(
                    query=query_sparse,
                    using="bm25",
                    limit=10,
                ),
            ],
            query=rest.FusionQuery(fusion=rest.Fusion.RRF),
            limit=3,
            with_payload=True,
        )
        print(f"  返回 {len(result.points)} 条")
        for hit in result.points:
            print(f"  score={hit.score:.4f} kb_id={hit.payload.get('kb_id')} content={hit.payload.get('content', '')[:60]}")
    except Exception as e:
        import traceback
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
