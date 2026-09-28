"""
用 DeepEval Synthesizer 从客服知识库生成评测数据集（JSONL）

用法（在 backend 目录下）：
    python scripts/generate_support_eval_dataset.py --kb-id 1 --max-goldens 50

依赖 deepeval（paper-eval extra）。未安装时仅告警退出，不生成。
生成结果写入 backend/data/support_eval/synthesized.jsonl，离线回归套件会自动合并加载。
"""

import argparse
import asyncio
import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.services.knowledge import KnowledgeService
from app.services.support_dataset_synthesizer import (
    contexts_from_kb_search,
    generate_support_goldens,
)
from app.services.support_eval_golden import DEFAULT_DATA_DIR, GOLDEN_CASES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("generate_support_eval_dataset")


async def main(kb_id: int, max_goldens: int, out_path: str) -> None:
    from app.services.support_evaluation import SupportEvaluationService

    db = SessionLocal()
    try:
        svc = SupportEvaluationService(db)
        _cfg, model_row, _provider = svc._resolve_judge_model()
        if model_row is None:
            logger.error("未找到可用的客服评测模型，无法生成（请先配置模型）")
            return

        seed_queries = [c.query for c in GOLDEN_CASES if c.query]
        kb = KnowledgeService(db)

        async def search_q(query: str, top_k: int = 4):
            return await kb.search(kb_id, query, top_k=top_k)

        contexts = await contexts_from_kb_search(search_q, seed_queries, top_k=4)
        if not contexts:
            logger.error("知识库检索无结果，请检查 --kb-id 是否正确或知识库是否已索引")
            return

        cases = generate_support_goldens(model_row, contexts, max_goldens=max_goldens)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"已写入 {len(cases)} 条 Synthesizer 生成集到 {out_path}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="用 DeepEval Synthesizer 生成客服评测数据集")
    parser.add_argument("--kb-id", type=int, required=True, help="知识库 ID")
    parser.add_argument("--max-goldens", type=int, default=50, help="生成 Goldens 上限")
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(DEFAULT_DATA_DIR, "synthesized.jsonl"),
        help="输出 JSONL 路径",
    )
    args = parser.parse_args()
    asyncio.run(main(args.kb_id, args.max_goldens, args.out))
