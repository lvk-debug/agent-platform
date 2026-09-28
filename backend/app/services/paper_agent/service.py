"""
Paper Agent 服务

编排一次「主题检索 + 综述生成」运行：
加载 LLM → 执行 LangGraph 流水线 → 落盘产物 → 持久化运行记录。
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.model import Model
from app.models.paper_agent import PaperAgentEvalRun, PaperAgentRun
from app.services.paper_agent.deepeval_metrics import resolve_backend
from app.services.paper_agent.eval_cases import get_cases
from app.services.paper_agent.evaluator import build_evaluator
from app.services.paper_agent.graph import build_paper_agent_graph
from app.services.paper_agent.outputs import ensure_run_dir, write_outputs
from app.utils.logger import logger

# 整体超时（安全网）：任务在后台执行，单节点已各自限时，
# 这里只兜底防止异常挂死；真正的耗时控制由 graph 的节点级超时负责。
RUN_TIMEOUT_SECONDS = 900

# 综述生成参数：偏向稳定与可复现
SYNTHESIS_TEMPERATURE = 0.3
# 推理模型会先消耗大量 token 在思考上，配额太小会导致正文被截断为空
SYNTHESIS_MAX_TOKENS = 8192


class PaperAgentService:
    """Paper Agent 运行服务"""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # 运行
    # ------------------------------------------------------------------

    def create_run(
        self,
        *,
        topic: str,
        model_id: str,
        user_id: int | None = None,
    ) -> PaperAgentRun:
        """
        创建运行记录（仅落库，不执行流水线）

        流水线耗时较长（PDF 解析 + claim 抽取实测可达数分钟），
        由后台任务异步执行，避免 HTTP 请求被拖到超时。

        Raises:
            ValueError: 模型不存在（由 API 层转为 400）
        """
        model = self.db.query(Model).filter(Model.model_id == model_id).first()
        if not model:
            raise ValueError(f"模型不存在: model_id={model_id}")

        record = self._create_record(topic, model, user_id)
        logger.info(
            f"PaperAgent 运行已创建: run_id={record.run_id}, topic={topic!r}, "
            f"model={model.name}"
        )
        return record

    async def execute_run(
        self,
        run_id: str,
        *,
        topic: str,
        model_id: str,
        max_papers: int | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        source: str = "arxiv",
        with_pdf: bool = True,
    ) -> None:
        """执行流水线并把结果写回运行记录（供后台任务调用）"""
        record = self.get_run(run_id)
        if not record:
            logger.warning(f"PaperAgent 运行记录不存在: {run_id}")
            return

        model = self.db.query(Model).filter(Model.model_id == model_id).first()
        if not model:
            self._mark_failed(record, f"模型不存在: {model_id}")
            return

        try:
            llm = self._build_llm(model)
        except ValueError as e:
            logger.warning(f"PaperAgent LLM 配置无效: {e}")
            self._mark_failed(record, str(e))
            return

        logger.info(
            f"PaperAgent 运行开始: run_id={run_id}, topic={topic!r}, "
            f"model={model.name}"
        )
        initial = self._build_initial_state(
            topic,
            self._clamp_paper_count(max_papers),
            year_from,
            year_to,
            source=source,
            with_pdf=with_pdf,
            output_dir=record.output_dir,
        )

        outcome = await self._execute_pipeline(llm, record, initial)
        if outcome is None:
            return

        self._persist_result(record, outcome["state"], outcome["duration_ms"])

    # ------------------------------------------------------------------
    # 运行内部步骤
    # ------------------------------------------------------------------

    @staticmethod
    def _build_initial_state(
        topic: str,
        max_papers: int,
        year_from: int | None,
        year_to: int | None,
        *,
        source: str = "arxiv",
        with_pdf: bool = True,
        output_dir: str = "",
    ) -> dict[str, Any]:
        """构造流水线初始状态"""
        return {
            "topic": topic,
            "max_papers": max_papers,
            "year_from": year_from,
            "year_to": year_to,
            "source": source,
            "with_pdf": with_pdf,
            "output_dir": output_dir,
            "plan": "",
            "papers": [],
            "ranked": [],
            "sections_by_paper": {},
            "claims": [],
            "comparison": None,
            "review_markdown": "",
            "trace": [],
            "error": None,
        }

    @staticmethod
    def _clamp_paper_count(max_papers: int | None) -> int:
        """把期望论文数收敛到 [1, ARXIV_MAX_RESULTS]"""
        limit = min(
            max_papers or settings.PAPER_AGENT_MAX_PAPERS, settings.ARXIV_MAX_RESULTS
        )
        return max(1, limit)

    def _create_record(
        self, topic: str, model: Model, user_id: int | None
    ) -> PaperAgentRun:
        """创建运行记录与产物目录"""
        run_id = str(uuid.uuid4())
        run_dir = ensure_run_dir(run_id)
        record = PaperAgentRun(
            run_id=run_id,
            user_id=user_id,
            topic=topic,
            status="running",
            model_id=model.id,
            model_name=model.name,
            output_dir=str(run_dir),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def _mark_failed(self, record: PaperAgentRun, error: str) -> None:
        """把运行标记为失败"""
        record.status = "failed"
        record.error = error
        self.db.commit()

    async def _execute_pipeline(
        self, llm: Any, record: PaperAgentRun, initial: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        执行 LangGraph 流水线

        Returns:
            {"state": 终态, "duration_ms": 耗时}；失败时已标记记录并返回 None
        """
        started = time.time()
        try:
            graph = build_paper_agent_graph(llm)
            state = await asyncio.wait_for(
                graph.ainvoke(initial), timeout=RUN_TIMEOUT_SECONDS
            )
        except TimeoutError:
            logger.error(f"PaperAgent 运行超时: run_id={record.run_id}")
            self._mark_failed(record, f"运行超时（{RUN_TIMEOUT_SECONDS}s）")
            return None
        except Exception as e:  # noqa: BLE001 - 记录失败原因，避免接口 500
            logger.error(f"PaperAgent 运行失败: {e}", exc_info=True)
            self._mark_failed(record, str(e))
            return None

        return {"state": state, "duration_ms": int((time.time() - started) * 1000)}

    def _persist_result(
        self, record: PaperAgentRun, state: dict[str, Any], duration_ms: int
    ) -> None:
        """落盘产物并写回运行记录"""
        ranked = state.get("ranked") or []
        review_markdown = state.get("review_markdown") or ""
        trace = state.get("trace") or []
        claims = state.get("claims") or []
        sections_by_paper = state.get("sections_by_paper") or {}
        comparison = state.get("comparison")
        error = state.get("error")

        # 检索无结果时 synthesis 生成「诚实说明限制」的综述，不判定为失败
        no_results = error == "未检索到相关论文"
        if no_results:
            error = None

        paths = write_outputs(
            Path(record.output_dir),
            run_id=record.run_id,
            topic=record.topic,
            plan=state.get("plan", ""),
            papers=state.get("papers") or [],
            ranked=ranked,
            review_markdown=review_markdown,
            trace=trace,
            duration_ms=duration_ms,
            claims=claims,
            sections_by_paper=sections_by_paper,
            comparison=comparison,
        )

        record.paper_count = len(ranked)
        record.review_path = paths["review"]
        record.summary = json.dumps(
            {
                "paper_count": len(ranked),
                "claim_count": len(claims),
                "parsed_papers": len(sections_by_paper),
                "comparison_rows": len(comparison.get("rows", [])) if comparison else 0,
                "duration_ms": duration_ms,
                "steps": len(trace),
                "no_results": no_results,
                "plan": state.get("plan", ""),
                "artifacts": paths,
            },
            ensure_ascii=False,
        )
        record.status = "completed" if review_markdown else "failed"
        record.error = error if not review_markdown else None

        self.db.commit()
        self.db.refresh(record)

        logger.info(
            f"PaperAgent 运行结束: run_id={record.run_id}, status={record.status}, "
            f"papers={len(ranked)}, {duration_ms}ms"
        )

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    def get_run(self, run_id: str) -> PaperAgentRun | None:
        """按 run_id 查询运行记录"""
        return (
            self.db.query(PaperAgentRun)
            .filter(PaperAgentRun.run_id == run_id)
            .first()
        )

    def list_runs(
        self,
        *,
        user_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[PaperAgentRun]:
        """运行记录列表（按创建时间倒序）"""
        query = self.db.query(PaperAgentRun)
        if user_id:
            query = query.filter(PaperAgentRun.user_id == user_id)
        return (
            query.order_by(PaperAgentRun.created_at.desc()).offset(offset).limit(limit).all()
        )

    @staticmethod
    def read_review(record: PaperAgentRun) -> str | None:
        """读取综述正文（文件不存在返回 None）"""
        if not record.review_path:
            return None
        path = Path(record.review_path)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # 评测（里程碑4）
    # ------------------------------------------------------------------

    def create_eval_record(
        self, *, model: Model, user_id: int | None, case_count: int
    ) -> PaperAgentEvalRun:
        """创建评测运行记录"""
        record = PaperAgentEvalRun(
            eval_id=str(uuid.uuid4()),
            user_id=user_id,
            model_id=model.id,
            model_name=model.name,
            status="running",
            case_count=case_count,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_eval(self, eval_id: str) -> PaperAgentEvalRun | None:
        """按 eval_id 查询评测运行"""
        return (
            self.db.query(PaperAgentEvalRun)
            .filter(PaperAgentEvalRun.eval_id == eval_id)
            .first()
        )

    def list_evals(
        self, *, user_id: int | None = None, limit: int = 20, offset: int = 0
    ) -> list[PaperAgentEvalRun]:
        """评测运行列表（按创建时间倒序）"""
        query = self.db.query(PaperAgentEvalRun)
        if user_id:
            query = query.filter(PaperAgentEvalRun.user_id == user_id)
        return (
            query.order_by(PaperAgentEvalRun.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    async def run_eval(
        self,
        eval_id: str,
        *,
        case_ids: list[str] | None = None,
        category: str | None = None,
        with_pdf: bool = False,
        eval_backend: str | None = None,
    ) -> None:
        """执行评测并把结果写回记录"""
        record = self.get_eval(eval_id)
        if not record:
            logger.warning(f"PaperAgent 评测记录不存在: {eval_id}")
            return

        model = (
            self.db.query(Model).filter(Model.id == record.model_id).first()
            if record.model_id
            else None
        )
        if not model:
            self._mark_eval_failed(record, "模型不存在")
            return

        # 按后端决定是否构建 DeepEval 裁判模型（未装 deepeval 时自动回退）
        backend = resolve_backend(eval_backend)
        deepeval_model = None
        if backend in ("deepeval", "both"):
            deepeval_model = self._build_deepeval_model(model)

        evaluator = build_evaluator(model, deepeval_model=deepeval_model)
        if not evaluator:
            self._mark_eval_failed(record, "无法构建评测所需的 LLM（请检查供应商配置）")
            return

        cases = get_cases(category=category, case_ids=case_ids)
        record.case_count = len(cases)
        self.db.commit()

        try:
            outcome = await evaluator.run(
                eval_id, cases, with_pdf=with_pdf, backend=backend
            )
        except Exception as e:  # noqa: BLE001 - 评测失败需记录原因
            logger.error(f"PaperAgent 评测执行失败: {e}", exc_info=True)
            self._mark_eval_failed(record, str(e))
            return

        record.status = "completed"
        record.summary = json.dumps(outcome["summary"], ensure_ascii=False)
        record.output_dir = outcome["output_dir"]
        self.db.commit()
        logger.info(f"PaperAgent 评测完成: eval_id={eval_id}, cases={len(cases)}")

    @staticmethod
    def _build_deepeval_model(model: Model) -> Any:
        """构建 DeepEval 裁判模型；失败返回 None（评测自动回退内置指标）"""
        try:
            from app.services.paper_agent.deepeval_model import (
                build_deepeval_model_from_db,
            )

            return build_deepeval_model_from_db(model)
        except Exception as e:  # noqa: BLE001 - 裁判模型不可用时不应中断评测
            logger.warning(f"PaperAgent DeepEval 模型构建失败，回退内置指标: {e}")
            return None

    def _mark_eval_failed(self, record: PaperAgentEvalRun, error: str) -> None:
        """把评测运行标记为失败"""
        record.status = "failed"
        record.error = error
        self.db.commit()

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    @staticmethod
    def _build_llm(model: Model):
        """
        根据数据库 Model/Provider 构建 LangChain ChatModel

        与 app/services/agent.py 的 _get_llm 保持一致的行为。
        """
        provider = model.provider
        if not provider:
            raise ValueError(f"模型未关联供应商: model_id={model.id}")

        if provider.provider_type == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model.model_id,
                api_key=provider.api_key,
                base_url=provider.api_endpoint,
                temperature=SYNTHESIS_TEMPERATURE,
                max_tokens=SYNTHESIS_MAX_TOKENS,
            )
        if provider.provider_type == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model.model_id,
                api_key=provider.api_key,
                temperature=SYNTHESIS_TEMPERATURE,
                max_tokens=SYNTHESIS_MAX_TOKENS,
            )

        raise ValueError(f"不支持的供应商类型: {provider.provider_type}")


def get_paper_agent_service(db: Session) -> PaperAgentService:
    return PaperAgentService(db)


async def run_paper_agent_task(
    run_id: str,
    *,
    topic: str,
    model_id: str,
    max_papers: int | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
    source: str = "arxiv",
    with_pdf: bool = True,
) -> None:
    """
    后台执行综述运行

    使用独立数据库会话，避免依赖请求会话的生命周期。
    """
    db = SessionLocal()
    try:
        await PaperAgentService(db).execute_run(
            run_id,
            topic=topic,
            model_id=model_id,
            max_papers=max_papers,
            year_from=year_from,
            year_to=year_to,
            source=source,
            with_pdf=with_pdf,
        )
    finally:
        db.close()


async def run_eval_task(
    eval_id: str,
    *,
    case_ids: list[str] | None = None,
    category: str | None = None,
    with_pdf: bool = False,
    eval_backend: str | None = None,
) -> None:
    """
    后台评测任务

    使用独立数据库会话，避免依赖请求会话的生命周期。
    """
    db = SessionLocal()
    try:
        await PaperAgentService(db).run_eval(
            eval_id,
            case_ids=case_ids,
            category=category,
            with_pdf=with_pdf,
            eval_backend=eval_backend,
        )
    finally:
        db.close()
