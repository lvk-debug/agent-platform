"""
诊断 Qdrant 混合检索无结果问题

用法:
    cd e:/OpenSource/agent-platform/backend && /d/AI/Miniconda3/envs/python311/python.exe test/diagnose_qdrant.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def main():
    print("=" * 60)
    print("Qdrant 混合检索诊断")
    print("=" * 60)

    # 1. 检查配置
    print(f"\n[1] 配置检查")
    print(f"  QDRANT_URL:          {settings.QDRANT_URL}")
    print(f"  QDRANT_COLLECTION:   {settings.QDRANT_COLLECTION}")
    print(f"  EMBEDDING_MODEL:     {settings.EMBEDDING_MODEL}")
    print(f"  EMBEDDING_SPARSE_MODEL: {settings.EMBEDDING_SPARSE_MODEL}")
    print(f"  EMBEDDING_MODEL_PATH:   {settings.EMBEDDING_MODEL_PATH}")
    print(f"  EMBEDDING_DIMENSION: {settings.EMBEDDING_DIMENSION}")

    # 2. 检查 sparse 模型缓存
    print(f"\n[2] Sparse 模型缓存检查")
    cache_dir = Path(settings.EMBEDDING_MODEL_PATH) if settings.EMBEDDING_MODEL_PATH else None
    if cache_dir and cache_dir.exists():
        # fastembed 缓存目录结构
        subdirs = list(cache_dir.iterdir()) if cache_dir.exists() else []
        print(f"  缓存目录: {cache_dir.resolve()}")
        for d in subdirs:
            print(f"    - {d.name}")
        # 检查是否有 Qdrant/bm25 相关目录
        bm25_dirs = [d for d in subdirs if "bm25" in d.name.lower() or "qdrant" in d.name.lower()]
        if bm25_dirs:
            print(f"  ✓ 找到 BM25 缓存目录")
        else:
            print(f"  ✗ 未找到 BM25 缓存目录，可能需要先运行 download_sparse_model.py")
    else:
        print(f"  ✗ 缓存目录不存在: {cache_dir}")

    # 3. 检查 Qdrant collection 状态
    print(f"\n[3] Qdrant Collection 检查")
    kb_ids = {}
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=settings.QDRANT_URL, timeout=10)
        collection_name = settings.QDRANT_COLLECTION or "agent_platform"

        collections = client.get_collections().collections
        existing = {c.name for c in collections}
        print(f"  已有 collections: {existing}")

        if collection_name not in existing:
            print(f"  ✗ collection '{collection_name}' 不存在")
            return

        info = client.get_collection(collection_name)
        print(f"  collection: {collection_name}")
        print(f"  points_count: {info.points_count}")

        # 检查向量配置（兼容不同 qdrant-client 版本）
        config = info.config
        vectors = getattr(config.params, "vectors", None)
        sparse_vectors = getattr(config.params, "sparse_vectors", None)
        print(f"  vectors 配置: {vectors}")
        print(f"  sparse_vectors 配置: {sparse_vectors}")

        # 检查是否是 named vectors
        if isinstance(vectors, dict):
            print(f"  ✓ 使用 named vectors: {list(vectors.keys())}")
        elif vectors is not None:
            print(f"  ✗ 使用 unnamed vector（单向量模式），与代码不匹配")

        # 4. 检查实际数据
        print(f"\n[4] 数据抽样检查")
        if info.points_count == 0:
            print(f"  ✗ collection 为空，没有数据可检索")
            print(f"  → 需要重新上传知识库数据")
            return

        # 抽样查看几条记录
        from qdrant_client.http import models as rest

        scroll_result = client.scroll(
            collection_name=collection_name,
            limit=3,
            with_payload=True,
            with_vectors=False,
        )
        points = scroll_result[0]
        for i, pt in enumerate(points):
            payload = pt.payload or {}
            print(f"  [{i}] id={pt.id}")
            print(f"      kb_id={payload.get('kb_id')}")
            print(f"      content={payload.get('content', '')[:80]}...")

        # 5. 检查 kb_id 分布
        print(f"\n[5] kb_id 分布")
        kb_ids = {}
        if info.points_count > 0:
            all_points = client.scroll(
                collection_name=collection_name,
                limit=10000,
                with_payload=True,
                with_vectors=False,
            )
            for pt in all_points[0]:
                kid = pt.payload.get("kb_id", "unknown")
                kb_ids[kid] = kb_ids.get(kid, 0) + 1
            print(f"  kb_id 分布: {kb_ids}")
        else:
            print(f"  collection 为空，跳过")

    except Exception as e:
        print(f"  ✗ Qdrant 连接失败: {e}")
        return

    # 6. 测试 dense embedding
    print(f"\n[6] Dense Embedding 测试")
    try:
        import os
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from app.services.vector_store import FastEmbedEmbeddings

        emb = FastEmbedEmbeddings()
        test_vec = emb.embed_query("测试文本")
        print(f"  ✓ Dense embedding 成功，维度: {len(test_vec)}")
    except Exception as e:
        print(f"  ✗ Dense embedding 失败: {e}")

    # 7. 测试 sparse embedding
    print(f"\n[7] Sparse Embedding 测试")
    try:
        from fastembed import SparseTextEmbedding

        model_name = settings.EMBEDDING_SPARSE_MODEL or "Qdrant/bm25"
        cache_dir_path = Path(settings.EMBEDDING_MODEL_PATH) if settings.EMBEDDING_MODEL_PATH else None
        kwargs = {"model_name": model_name}
        if cache_dir_path and cache_dir_path.exists():
            kwargs["cache_dir"] = cache_dir_path

        sparse = SparseTextEmbedding(**kwargs)
        sparse_result = list(sparse.embed(["测试文本"]))
        indices = sparse_result[0].indices
        values = sparse_result[0].values
        print(f"  ✓ Sparse embedding 成功，非零维度: {len(indices)}")
        print(f"    indices 范围: [{indices.min()}, {indices.max()}]")
        print(f"    values 范围: [{values.min():.4f}, {values.max():.4f}]")
    except Exception as e:
        print(f"  ✗ Sparse embedding 失败: {e}")

    # 8. 端到端测试
    print(f"\n[8] 端到端混合检索测试")
    try:
        from app.services.vector_store import QdrantStoreService

        store = QdrantStoreService()
        # 用第一个 kb_id 测试
        test_kb_id = list(kb_ids.keys())[0] if kb_ids else 1
        test_query = "测试"
        print(f"  测试查询: kb_id={test_kb_id}, query='{test_query}'")

        results = store.similarity_search(test_kb_id, test_query, k=3)
        print(f"  混合检索返回 {len(results)} 条结果")
        for r in results:
            print(f"    score={r['score']:.4f} content={r['content'][:60]}...")

        if not results:
            print(f"  → 混合检索无结果，尝试纯 dense 检索...")
            # 直接用 client 测试
            dense_vec = store.embeddings.embed_query(test_query)
            kb_filter = store._kb_filter(test_kb_id)
            raw = client.query_points(
                collection_name=collection_name,
                query=dense_vec,
                using="dense",
                query_filter=kb_filter,
                limit=3,
                with_payload=True,
            )
            print(f"  纯 dense 检索返回 {len(raw.points)} 条结果")
            for hit in raw.points:
                print(f"    score={hit.score:.4f} content={hit.payload.get('content', '')[:60]}...")

    except Exception as e:
        import traceback
        print(f"  ✗ 端到端测试失败: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
