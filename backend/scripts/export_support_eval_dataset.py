"""
从 support_messages 导出历史评测数据集（JSONL，无标准答案）

抽取真实 AI 回答（role=ai、有 references、非 error）作为回归基准，
主要跑无监督指标（answer_relevancy / faithfulness / contextual_relevancy）。
问题快照取该 AI 消息前最近一条客户消息。

用法（在 backend 目录下）：
    python scripts/export_support_eval_dataset.py --limit 200
"""

import argparse
import json
import logging
import os
import sys
from typing import Optional

from sqlalchemy import desc

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.support import MessageRole, SupportMessage
from app.services.support_eval_golden import DEFAULT_DATA_DIR, SupportGoldenCase

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("export_support_eval_dataset")


def _preceding_customer_query(db, message: SupportMessage) -> Optional[str]:
    """取该 AI 消息前最近一条客户提问作为问题快照"""
    customer = (
        db.query(SupportMessage)  # type: ignore[assignment]
        .filter(
            SupportMessage.session_id == message.session_id,
            SupportMessage.role == MessageRole.CUSTOMER,
            SupportMessage.id < message.id,
        )
        .order_by(desc(SupportMessage.id))
        .first()
    )
    return customer.content if customer else None


def main(limit: int, out_path: str) -> None:
    db = SessionLocal()
    try:
        messages = (
            db.query(SupportMessage)
            .filter(
                SupportMessage.role == MessageRole.AI,
                SupportMessage.error.is_(None),
            )
            .order_by(desc(SupportMessage.id))
            .limit(limit)
            .all()
        )

        cases: list[SupportGoldenCase] = []
        for m in messages:
            refs = m.references or []
            if not refs:
                # 无参考上下文的 AI 回答：faithfulness/contextual 无意义，跳过
                continue
            cases.append(
                SupportGoldenCase(
                    case_id=f"history-{m.id}",
                    query=_preceding_customer_query(db, m) or "",
                    expected_answer="",
                    references=[dict(r) for r in refs],
                    intent=m.intent,
                    tags=["history"],
                )
            )

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for c in cases:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"已导出 {len(cases)} 条历史评测集到 {out_path}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="从 support_messages 导出历史评测数据集")
    parser.add_argument("--limit", type=int, default=200, help="最多导出条数")
    parser.add_argument(
        "--out",
        type=str,
        default=os.path.join(DEFAULT_DATA_DIR, "history.jsonl"),
        help="输出 JSONL 路径",
    )
    args = parser.parse_args()
    main(args.limit, args.out)
