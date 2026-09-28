"""
客服助手评测服务

职责：
- auto_evaluate：对单条 AI 回答跑 DeepEval 自动评测（当前线上唯一自动裁判，
  已移除原自研四维度 LLM 裁判）。
- manual_score：坐席/管理员人工标注打分（人工四维度保留不变）。
- list_queue / quality_summary：待标注队列与质量看板聚合。
- evaluate_session_messages：会话级批量回填（串行，避免打爆模型配额）。

设计要点：
1. **自动评测统一走 DeepEval**：指标为 answer_relevancy / faithfulness /
   contextual_relevancy / GEval×3（安全/帮助/准确），结果写入 deepeval_* 字段。
2. **DeepEval 不可用（未启用或未安装）时返回 None**，不写自动分、不阻断主链路。
3. **一条 AI 回答只评一次**：message_id 唯一，自动/人工都是 upsert。
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.support import IntentCategory, MessageRole, SupportMessage
from app.models.support_evaluation import SupportEvaluation
from app.models.user import User
from app.services.support_deepeval_eval import (
    build_support_deepeval_model,
    is_deepeval_available,
    measure_support_case,
)
from app.utils.logger import logger

# 自研四维度 LLM 裁判已移除：自动评测统一走 DeepEval（见 support/deepeval_eval.py）


def _mean(scores: Dict[str, float]) -> Optional[float]:
    vals = [v for v in scores.values() if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


class SupportEvaluationService:
    """客服评测服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 自动评测
    # ------------------------------------------------------------------

    async def auto_evaluate(
        self, message_id: int, user_id: Optional[int] = None
    ) -> Optional[SupportEvaluation]:
        """对单条 AI 消息跑 DeepEval 自动评测（upsert）

        返回更新后的 SupportEvaluation；消息不存在、非 AI 消息、DeepEval 未启用/
        未安装、无可用裁判模型，或未产出任何指标分时返回 None。
        """
        message = (
            self.db.query(SupportMessage)
            .filter(SupportMessage.id == message_id)
            .first()
        )
        if not message or message.role != MessageRole.AI or message.error:
            return None

        if not (settings.SUPPORT_DEEPEVAL_ENABLED and is_deepeval_available()):
            logger.warning("DeepEval 未启用或未安装，跳过客服自动评测")
            return None

        _cfg, model_row, _provider = self._resolve_judge_model()
        if model_row is None:
            logger.warning("未找到可用的客服评测模型，跳过 DeepEval 自动评测")
            return None
        try:
            deepeval_model = build_support_deepeval_model(model_row)
        except Exception as exc:  # noqa: BLE001 - 评测旁路，失败不阻断主链路
            logger.warning(f"构建 DeepEval 裁判模型失败: {exc}")
            return None

        query = self._preceding_customer_query(message)
        answer = message.content or ""
        references = message.references or []

        try:
            result = await asyncio.to_thread(
                measure_support_case,
                query=query or "",
                answer=answer,
                references=references,
                intent=message.intent,
                name=f"msg-{message.id}",
                deepeval_model=deepeval_model,
            )
        except Exception as exc:  # noqa: BLE001 - 自动评测旁路，失败不应阻断
            logger.warning(f"客服 DeepEval 自动评测失败: {exc}")
            return None

        scores: Dict[str, float] = result.get("scores") or {}
        if not scores:
            logger.warning(f"客服 DeepEval 未产出指标分（msg={message.id}）")
            return None

        reasoning = self._compose_reasoning(
            result.get("reasons") or {}, result.get("errors") or {}
        )
        evaluation = self._upsert(
            message_id=message.id,
            session_id=message.session_id,
            query=query,
            intent=message.intent,
            deepeval_scores=scores,
            deepeval_overall=_mean(scores),
            deepeval_reasoning=reasoning,
            status="auto",
        )
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    @staticmethod
    def _compose_reasoning(
        reasons: Dict[str, str], errors: Dict[str, str]
    ) -> Optional[str]:
        """把各 DeepEval 指标理由拼成一条备注；含失败指标则一并标注"""
        parts = [f"{key}: {reason}" for key, reason in reasons.items()]
        if errors:
            parts.append("失败指标: " + ", ".join(errors.keys()))
        return "\n".join(parts) if parts else None

    def _resolve_judge_model(self):
        """解析自动评测用的模型：优先客服配置模型，否则第一个可用模型"""
        from sqlalchemy.orm import joinedload

        from app.models.model import Model
        from app.services.support import SupportService

        cfg = SupportService(self.db).get_settings()
        base = (
            self.db.query(Model)
            .options(joinedload(Model.provider))
            .filter(Model.is_active.is_(True))
        )
        for candidate in (cfg.model_id, None):
            if not candidate:
                continue
            row = base.filter(Model.id == candidate).first()
            if row and row.provider and row.provider.is_active:
                return cfg, row, row.provider
        for row in base.all():
            if row.provider and row.provider.is_active:
                return cfg, row, row.provider
        return cfg, None, None

    # ------------------------------------------------------------------
    # 人工标注
    # ------------------------------------------------------------------

    def manual_score(
        self, message_id: int, data: Any, annotator_id: int
    ) -> Optional[SupportEvaluation]:
        """人工标注打分（upsert），status 置 done"""
        message = (
            self.db.query(SupportMessage)
            .filter(SupportMessage.id == message_id)
            .first()
        )
        if not message or message.role != MessageRole.AI:
            return None

        manual_scores = {
            "accuracy": float(data.accuracy),
            "helpfulness": float(data.helpfulness),
            "safety": float(data.safety),
            "fluency": float(data.fluency),
        }
        manual_overall = _mean(manual_scores)
        evaluation = self._upsert(
            message_id=message.id,
            session_id=message.session_id,
            query=self._preceding_customer_query(message),
            intent=message.intent,
            manual_scores=manual_scores,
            manual_overall=manual_overall,
            annotator_id=annotator_id,
            comment=(data.comment or None),
            status="done",
        )
        self.db.commit()
        self.db.refresh(evaluation)
        return evaluation

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_by_message(self, message_id: int) -> Optional[SupportEvaluation]:
        return (
            self.db.query(SupportEvaluation)
            .filter(SupportEvaluation.message_id == message_id)
            .first()
        )

    def list_queue(
        self, status: Optional[str] = None, page: int = 1, page_size: int = 50
    ) -> Tuple[List[SupportEvaluation], int]:
        """待标注队列：未人工标注的评测（pending / auto）"""
        q = self.db.query(SupportEvaluation)
        if status:
            q = q.filter(SupportEvaluation.status == status)
        else:
            q = q.filter(SupportEvaluation.status != "done")
        total = q.count()
        items = (
            q.order_by(SupportEvaluation.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total

    def quality_summary(self, days: int = 7) -> Dict[str, Any]:
        """质量看板聚合（Python 端聚合，数据量小足够）"""
        since = datetime.now(UTC) - timedelta(days=max(days, 1))
        rows = (
            self.db.query(SupportEvaluation)
            .filter(SupportEvaluation.created_at >= since)
            .all()
        )

        total = len(rows)
        # 自动分来源改为 DeepEval（deepeval_overall）；输出键保留 auto_* 以兼容前端
        auto_rows = [r for r in rows if r.deepeval_overall is not None]
        manual_rows = [r for r in rows if r.manual_overall is not None]
        pending_count = sum(1 for r in rows if r.status != "done")

        auto_avg = round(sum(r.deepeval_overall for r in auto_rows) / len(auto_rows), 4) if auto_rows else None
        manual_avg = round(sum(r.manual_overall for r in manual_rows) / len(manual_rows), 4) if manual_rows else None
        annotated_rate = round(len(manual_rows) / total, 4) if total else 0.0

        overview = {
            "total": total,
            "auto_count": len(auto_rows),
            "manual_count": len(manual_rows),
            "pending_count": pending_count,
            "auto_avg": auto_avg,
            "manual_avg": manual_avg,
            "annotated_rate": annotated_rate,
        }

        # 按日趋势
        trend_map: Dict[str, List[SupportEvaluation]] = {}
        for r in rows:
            key = r.created_at.date().isoformat()
            trend_map.setdefault(key, []).append(r)
        trend = []
        for date_str in sorted(trend_map.keys()):
            grp = trend_map[date_str]
            a = [x.deepeval_overall for x in grp if x.deepeval_overall is not None]
            m = [x.manual_overall for x in grp if x.manual_overall is not None]
            trend.append(
                {
                    "date": date_str,
                    "count": len(grp),
                    "auto_avg": round(sum(a) / len(a), 4) if a else None,
                    "manual_avg": round(sum(m) / len(m), 4) if m else None,
                }
            )

        # 按意图分布
        intent_map: Dict[str, List[SupportEvaluation]] = {}
        for r in rows:
            intent_map.setdefault(r.intent or "other", []).append(r)
        by_intent = []
        for intent, grp in intent_map.items():
            a = [x.deepeval_overall for x in grp if x.deepeval_overall is not None]
            m = [x.manual_overall for x in grp if x.manual_overall is not None]
            by_intent.append(
                {
                    "intent": intent,
                    "label": IntentCategory.LABELS.get(intent, intent or "其他"),
                    "count": len(grp),
                    "auto_avg": round(sum(a) / len(a), 4) if a else None,
                    "manual_avg": round(sum(m) / len(m), 4) if m else None,
                }
            )
        by_intent.sort(key=lambda x: x["count"], reverse=True)

        return {"overview": overview, "trend": trend, "by_intent": by_intent}

    # ------------------------------------------------------------------
    # 会话级批量回填（串行，控制配额）
    # ------------------------------------------------------------------

    async def evaluate_session_messages(
        self, session_id: int, limit: int = 50
    ) -> int:
        """对会话里尚未评测的 AI 消息做自动评测回填，返回处理条数"""
        messages = (
            self.db.query(SupportMessage)
            .filter(
                SupportMessage.session_id == session_id,
                SupportMessage.role == MessageRole.AI,
                SupportMessage.error.is_(None),
            )
            .order_by(SupportMessage.id.desc())
            .limit(limit)
            .all()
        )
        done = 0
        for message in messages:
            existing = self.get_by_message(message.id)
            if existing and existing.deepeval_overall is not None:
                continue
            await self.auto_evaluate(message.id)
            done += 1
        return done

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------

    def _preceding_customer_query(self, message: SupportMessage) -> Optional[str]:
        """取该 AI 消息前最近一条客户提问作为问题快照"""
        customer = (
            self.db.query(SupportMessage)
            .filter(
                SupportMessage.session_id == message.session_id,
                SupportMessage.role == MessageRole.CUSTOMER,
                SupportMessage.id < message.id,
            )
            .order_by(SupportMessage.id.desc())
            .first()
        )
        return customer.content if customer else None

    def _upsert(
        self,
        message_id: int,
        session_id: int,
        query: Optional[str],
        intent: Optional[str],
        auto_scores: Optional[Dict[str, float]] = None,
        auto_overall: Optional[float] = None,
        auto_reasoning: Optional[str] = None,
        deepeval_scores: Optional[Dict[str, float]] = None,
        deepeval_overall: Optional[float] = None,
        deepeval_reasoning: Optional[str] = None,
        manual_scores: Optional[Dict[str, float]] = None,
        manual_overall: Optional[float] = None,
        annotator_id: Optional[int] = None,
        comment: Optional[str] = None,
        status: str = "pending",
    ) -> SupportEvaluation:
        """按 message_id upsert 评测记录；已人工标注过的保留人工分"""
        evaluation = self.get_by_message(message_id)
        if evaluation is None:
            evaluation = SupportEvaluation(
                message_id=message_id,
                session_id=session_id,
                query=query,
                intent=intent,
            )
            self.db.add(evaluation)

        if auto_scores is not None:
            evaluation.auto_scores = auto_scores
            evaluation.auto_overall = auto_overall
            evaluation.auto_reasoning = auto_reasoning
            if evaluation.status in ("pending", None):
                evaluation.status = status
        if deepeval_scores is not None:
            evaluation.deepeval_scores = deepeval_scores
            evaluation.deepeval_overall = deepeval_overall
            evaluation.deepeval_reasoning = deepeval_reasoning
            if evaluation.status in ("pending", None):
                evaluation.status = status
        if manual_scores is not None:
            evaluation.manual_scores = manual_scores
            evaluation.manual_overall = manual_overall
            evaluation.annotator_id = annotator_id
            evaluation.comment = comment
            evaluation.status = "done"
        if query is not None and evaluation.query is None:
            evaluation.query = query
        return evaluation


def get_support_evaluation_service(db: Session) -> SupportEvaluationService:
    """客服评测服务工厂"""
    return SupportEvaluationService(db)
