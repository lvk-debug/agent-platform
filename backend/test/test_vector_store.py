"""
向量存储测试脚本 — 验证 fastembed + sqlite-vec 加载和使用
用法: cd backend && python -m test.test_vector_store
"""

import os
import sys
import sqlite3
import tempfile

# ── 1. 测试 fastembed 模型加载 ──────────────────────────────────────
print("=" * 60)
print("1. 测试 fastembed 模型加载")
print("=" * 60)

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from app.core.config import settings
print(f"  EMBEDDING_MODEL      = {repr(settings.EMBEDDING_MODEL)}")
print(f"  EMBEDDING_MODEL_PATH = {repr(settings.EMBEDDING_MODEL_PATH)}")

from fastembed import TextEmbedding

model_name = settings.EMBEDDING_MODEL or "BAAI/bge-small-zh-v1.5"
cache_dir = settings.EMBEDDING_MODEL_PATH or "./temp/fastembed_cache"

print(f"  实际使用 model_name  = {repr(model_name)}")
print(f"  实际使用 cache_dir   = {repr(cache_dir)}")

try:
    embedder = TextEmbedding(
        model_name=model_name,
        cache_dir=cache_dir,
        local_files_only=True,
    )
    embeddings = list(embedder.embed(["你好世界", "测试文本"]))
    print(f"  ✅ 模型加载成功, 向量维度={len(embeddings[0])}")
except Exception as e:
    print(f"  ❌ 模型加载失败: {e}")
    sys.exit(1)

# ── 2. 测试 sqlite-vec 扩展加载 ─────────────────────────────────────
print()
print("=" * 60)
print("2. 测试 sqlite-vec 扩展加载")
print("=" * 60)

try:
    import sqlite_vec
    print(f"  sqlite_vec 版本: {sqlite_vec.__version__ if hasattr(sqlite_vec, '__version__') else 'unknown'}")

    conn = sqlite3.connect(":memory:")
    sqlite_vec.load(conn)

    # 验证 vec0 虚拟表可用
    conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[4])")
    conn.execute("INSERT INTO test_vec(rowid, embedding) VALUES (1, '[1.0, 0.0, 0.0, 0.0]')")
    conn.execute("INSERT INTO test_vec(rowid, embedding) VALUES (2, '[0.0, 1.0, 0.0, 0.0]')")

    rows = conn.execute(
        "SELECT rowid, distance FROM test_vec WHERE embedding MATCH '[1.0, 0.0, 0.0, 0.0]' ORDER BY distance LIMIT 2"
    ).fetchall()
    print(f"  ✅ vec0 查询成功: {rows}")
    conn.close()
except Exception as e:
    print(f"  ❌ sqlite-vec 加载失败: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── 3. 测试 LangChain SQLiteVec 集成 ────────────────────────────────
print()
print("=" * 60)
print("3. 测试 LangChain SQLiteVec 集成")
print("=" * 60)

from langchain_community.vectorstores import SQLiteVec
from app.services.vector_store import FastEmbedEmbeddings

try:
    embeddings_model = FastEmbedEmbeddings(model_name=model_name, cache_dir=cache_dir)

    db_path = os.path.join(tempfile.gettempdir(), "test_vec.db")
    conn = sqlite3.connect(db_path)
    sqlite_vec.load(conn)

    store = SQLiteVec(
        connection=conn,
        table="test_collection",
        embedding=embeddings_model,
    )

    # 写入
    ids = store.add_texts(
        texts=["Python 是一种编程语言", "机器学习是 AI 的子领域", "今天天气很好"],
        metadatas=[
            {"source": "doc1.txt"},
            {"source": "doc2.txt"},
            {"source": "doc3.txt"},
        ],
    )
    print(f"  ✅ 写入 {len(ids)} 条向量")

    # 检索
    results = store.similarity_search_with_score("编程语言", k=2)
    for doc, score in results:
        print(f"  📄 {doc.page_content[:40]}  score={score:.4f}  meta={doc.metadata}")

    # 清理
    conn.close()
    os.remove(db_path)
    for suffix in ["-wal", "-shm"]:
        p = db_path + suffix
        if os.path.exists(p):
            os.remove(p)

    print("  ✅ LangChain SQLiteVec 测试通过")
except Exception as e:
    print(f"  ❌ SQLiteVec 集成失败: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── 4. 测试 VectorStoreService ──────────────────────────────────────
print()
print("=" * 60)
print("4. 测试 VectorStoreService (完整流程)")
print("=" * 60)

from app.services.vector_store import vector_store_service

KB_ID = 9999  # 测试用 ID
try:
    # 写入
    vector_store_service.add_texts(
        kb_id=KB_ID,
        texts=["FastAPI 是一个现代 Web 框架", "SQLite 是轻量级数据库"],
        metadatas=[
            {"segment_id": "1", "document_id": "100", "kb_id": str(KB_ID)},
            {"segment_id": "2", "document_id": "100", "kb_id": str(KB_ID)},
        ],
    )
    print(f"  ✅ add_texts 成功")

    # 检索
    results = vector_store_service.similarity_search(KB_ID, "Web 框架", k=2)
    for r in results:
        print(f"  📄 {r['content'][:40]}  score={r['score']:.4f}")

    # 按 metadata 删除
    deleted = vector_store_service.delete_by_metadata(KB_ID, "document_id", "100")
    print(f"  ✅ delete_by_metadata: 删除 {deleted} 条")

    # 删除整个 collection
    ok = vector_store_service.delete_collection(KB_ID)
    print(f"  ✅ delete_collection: {ok}")

except Exception as e:
    print(f"  ❌ VectorStoreService 失败: {e}")
    import traceback; traceback.print_exc()
    # 清理
    vector_store_service.delete_collection(KB_ID)
    sys.exit(1)

print()
print("=" * 60)
print("🎉 所有测试通过!")
print("=" * 60)
