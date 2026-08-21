"""检查 Qdrant 中 kb_id 字段的实际类型"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import time
t0 = time.time()
from app.core.config import settings
from app.services.vector_store import get_vector_store_service
vs = get_vector_store_service()
client = vs.client

COLLECTION = settings.QDRANT_COLLECTION

# 抽样几个点看 payload
results = client.scroll(
    collection_name=COLLECTION,
    limit=5,
    with_payload=True,
    with_vectors=False,
)
print(f"耗时: {time.time()-t0:.1f}s\n")

for point in results[0]:
    kb_val = point.payload.get("kb_id")
    print(f"point_id={point.id}")
    print(f"  kb_id = {kb_val!r}  (type={type(kb_val).__name__})")
    content = point.payload.get("content", "")[:80]
    print(f"  content = {content}...")
    print()

# 测试：用字符串值过滤
from qdrant_client.models import Filter, FieldCondition, MatchValue

print("=== 类型对比测试 ===")
for val in [1, "1", 1.0]:
    flt = Filter(must=[FieldCondition(key="kb_id", match=MatchValue(value=val))])
    cnt = client.count(collection_name=COLLECTION, count_filter=flt, exact=True)
    print(f"  MatchValue(value={val!r}) -> count={cnt.count}")
