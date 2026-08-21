"""
下载 EMBEDDING_SPARSE_MODEL 到 EMBEDDING_MODEL_PATH

用法:
    cd e:/OpenSource/agent-platform/backend && /d/AI/Miniconda3/envs/python311/python.exe test/download_sparse_model.py
"""

import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，以便导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def main():
    model_name = settings.EMBEDDING_SPARSE_MODEL or "Qdrant/bm25"
    cache_dir = settings.EMBEDDING_MODEL_PATH

    if not cache_dir:
        print("错误: EMBEDDING_MODEL_PATH 未配置，请在 .env.local 中设置")
        sys.exit(1)

    cache_path = Path(cache_dir)
    print(f"稀疏模型: {model_name}")
    print(f"下载路径: {cache_path.resolve()}")

    # 确保目录存在
    cache_path.mkdir(parents=True, exist_ok=True)

    # 关闭离线模式，允许从网络下载
    import os
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)

    from fastembed import SparseTextEmbedding

    print("开始下载...")
    embedder = SparseTextEmbedding(
        model_name=model_name,
        cache_dir=cache_path,
    )

    # 用一条简单文本验证模型可用
    test_embedding = list(embedder.embed(["测试文本"]))
    dim = len(test_embedding[0].indices)
    print(f"验证通过! 稀疏向量非零维度: {dim}")
    print(f"模型已缓存到: {cache_path.resolve()}")


if __name__ == "__main__":
    main()
