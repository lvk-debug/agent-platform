"""
诊断：模拟 API 搜索路径（带 kb_id 过滤）
对比诊断脚本（无 filter）和 API 路径（有 filter）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import time
t0 = time.time()
from app.core.config import settings
from app.services.vector_store import get_vector_store_service

print(f"[{time.time()-t0:.1f}s] 模块加载完成")

vs = get_vector_store_service()
client = vs.client

from qdrant_client import models as rest

COLLECTION = settings.QDRANT_COLLECTION

# Step 1: 基本信息
info = client.get_collection(COLLECTION)
print(f"\n=== Collection: {COLLECTION} ===")
print(f"points_count: {info.points_count}")
print(f"vectors_config: {info.config.params.vectors}")
print(f"sparse_vectors: {info.config.params.sparse_vectors}")

# Step 2: 按 kb_id 统计
try:
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    for kid in range(1, 6):
        flt = Filter(must=[FieldCondition(key="kb_id", match=MatchValue(value=kid))])
        count = client.count(collection_name=COLLECTION, count_filter=flt, exact=True)
        if count.count > 0:
            print(f"  kb_id={kid}: {count.count} points")
except Exception as e:
    print(f"  kb_id 统计失败: {e}")

# Step 3: 模拟 API search 路径（带 kb_id=1 的 filter）
print("\n=== 模拟 API search（kb_id=1 过滤）===")
t1 = time.time()
kb_filter = vs._kb_filter(1)
print(f"kb_filter: {kb_filter}")

query_dense = vs.embeddings.embed_query("测试")
sparse_list = list(vs.sparse_embedder.embed(["测试"]))
query_sparse = rest.SparseVector(
    indices=sparse_list[0].indices.tolist(),
    values=sparse_list[0].values.tolist(),
)

results = client.query_points(
    collection_name=COLLECTION,
    prefetch=[
        rest.Prefetch(query=query_dense, using="dense", limit=15, filter=kb_filter),
        rest.Prefetch(query=query_sparse, using="bm25", limit=15, filter=kb_filter),
    ],
    query=rest.FusionQuery(fusion=rest.Fusion.RRF),
    query_filter=kb_filter,
    limit=5,
    with_payload=True,
)
t2 = time.time()

print(f"结果数: {len(results.points)}  耗时: {(t2-t1)*1000:.0f}ms")
for i, hit in enumerate(results.points):
    print(f"\n  [{i+1}] score={hit.score:.4f}")
    print(f"      kb_id={hit.payload.get('kb_id', 'N/A')}")
    print(f"      doc_id={hit.payload.get('document_id', 'N/A')}")
    print(f"      content={hit.payload.get('content', '')[:100]}...")

if len(results.points) == 0:
    print("\n>>> kb_id=1 过滤后无结果，检查该 kb_id 是否有数据 <<<")
    # 无 filter 搜一次看是否有数据
    print("\n=== 无 filter 对照 ===")
    results2 = client.query_points(
        collection_name=COLLECTION,
        prefetch=[
            rest.Prefetch(query=query_dense, using="dense", limit=15),
            rest.Prefetch(query=query_sparse, using="bm25", limit=15),
        ],
        query=rest.FusionQuery(fusion=rest.Fusion.RRF),
        limit=5,
        with_payload=True,
    )
    print(f"无 filter 结果数: {len(results2.points)}")
    for i, hit in enumerate(results2.points):
        print(f"  [{i+1}] kb_id={hit.payload.get('kb_id', 'N/A')}, score={hit.score:.4f}")

print(f"\n总耗时: {time.time()-t0:.1f}s")
