"""
下载 BAAI/bge-reranker-base 重排序模型到 EMBEDDING_MODEL_PATH

用法:
    cd e:/OpenSource/agent-platform/backend && /d/AI/Miniconda3/envs/python311/python.exe test/download_reranker_model.py
"""

import sys
from pathlib import Path

# 将 backend/ 加入 sys.path，以便导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings


def main():
    model_name = "BAAI/bge-reranker-base"
    cache_dir = settings.EMBEDDING_MODEL_PATH

    if not cache_dir:
        print("错误: EMBEDDING_MODEL_PATH 未配置，请在 .env.local 中设置")
        sys.exit(1)

    cache_path = Path(cache_dir)
    print(f"重排序模型: {model_name}")
    print(f"下载路径: {cache_path.resolve()}")

    # 确保目录存在
    cache_path.mkdir(parents=True, exist_ok=True)

    # 关闭离线模式，允许从网络下载
    import os
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)

    from fastembed.rerank.cross_encoder import TextCrossEncoder

    print("开始下载...")
    encoder = TextCrossEncoder(
        model_name=model_name,
        cache_dir=cache_path,
    )

    # 用简单文本验证模型可用
    query = "什么是机器学习？"
    documents = [
        "机器学习是人工智能的一个分支，它让计算机从数据中学习。",
        "今天天气很好，适合出去散步。",
    ]
    scores = list(encoder.rerank(query, documents))
    print(f"验证通过! 原始分数: {[round(s, 4) for s in scores]}")
    print(f"模型已缓存到: {cache_path.resolve()}")


if __name__ == "__main__":
    main()
