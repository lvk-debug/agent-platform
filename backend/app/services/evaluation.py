"""
评估引擎服务 (v2)

负责执行评估任务，包括：
- 执行测试用例
- 收集执行轨迹
- 使用多评估器评分
- 生成诊断信息
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.app import App
from app.models.evaluation import (
    Evaluation,
    EvaluationDataset,
    EvaluationResult,
    Evaluator,
    TestCase,
    Trace,
)
from app.models.user import User
from app.schemas.agent import AgentChatRequest
from app.services.agent import AgentService
from app.services.evaluators import EvaluatorEngine, EvaluationScore
from app.utils.logger import logger


class EvaluationEngine:
    """评估引擎"""

    def __init__(self, db: Session):
        self.db = db
        self.agent_service = AgentService(db)
        self.evaluator_engine = EvaluatorEngine(db)

    async def run_evaluation(self, evaluation_id: int):
        """执行评估任务"""
        evaluation = self.db.query(Evaluation).filter(Evaluation.id == evaluation_id).first()
        if not evaluation:
            logger.error(f"评估任务不存在: {evaluation_id}")
            return

        dataset = (
            self.db.query(EvaluationDataset)
            .filter(EvaluationDataset.id == evaluation.dataset_id)
            .first()
        )
        if not dataset:
            logger.error(f"数据集不存在: {evaluation.dataset_id}")
            evaluation.status = "failed"
            self.db.commit()
            return

        test_cases = (
            self.db.query(TestCase).filter(TestCase.dataset_id == dataset.id).all()
        )

        if not test_cases:
            logger.warning(f"数据集中没有测试用例: {dataset.id}")
            evaluation.status = "completed"
            evaluation.completed_at = datetime.utcnow()
            self.db.commit()
            return

        # 获取评估器
        evaluator_ids = evaluation.evaluator_ids or []
        evaluators = []
        for eid in evaluator_ids:
            evaluator = self.db.query(Evaluator).filter(Evaluator.id == eid).first()
            if evaluator:
                evaluators.append(evaluator)

        if not evaluators:
            logger.warning(f"没有找到有效的评估器: {evaluator_ids}")
            evaluation.status = "failed"
            evaluation.completed_at = datetime.utcnow()
            self.db.commit()
            return

        # 更新状态
        evaluation.status = "running"
        evaluation.started_at = datetime.utcnow()
        evaluation.total_cases = len(test_cases)
        self.db.commit()

        logger.info(
            f"开始执行评估任务: {evaluation_id}, "
            f"测试用例数: {len(test_cases)}, "
            f"评估器数: {len(evaluators)}"
        )

        # 获取并发配置
        config = evaluation.config or {}
        max_concurrency = config.get("max_concurrency", 3)
        timeout = config.get("timeout", 120)

        # 使用信号量控制并发
        semaphore = asyncio.Semaphore(max_concurrency)
        all_results = []

        async def run_with_semaphore(test_case: TestCase, index: int):
            async with semaphore:
                try:
                    results = await asyncio.wait_for(
                        self._execute_test_case(
                            evaluation.app_id,
                            test_case,
                            evaluators,
                            config,
                        ),
                        timeout=timeout,
                    )
                    return results
                except asyncio.TimeoutError:
                    logger.warning(f"测试用例超时: {test_case.case_id}")
                    return [self._create_timeout_result(test_case, evaluator)
                            for evaluator in evaluators]
                except Exception as e:
                    logger.error(f"测试用例执行失败: {test_case.case_id}: {e}")
                    return [self._create_error_result(test_case, evaluator, str(e))
                            for evaluator in evaluators]

        # 并发执行测试用例
        tasks = [run_with_semaphore(tc, i) for i, tc in enumerate(test_cases)]

        completed = 0
        for task in asyncio.as_completed(tasks):
            results = await task
            all_results.extend(results)

            # 保存结果
            for result in results:
                self.db.add(result)

            completed += 1

            # 更新进度
            evaluation.completed_cases = completed
            evaluation.progress = int(completed / len(test_cases) * 100)
            self.db.commit()

            logger.info(
                f"评估进度: {evaluation.progress}% ({completed}/{len(test_cases)})"
            )

        # 计算总分（按评估器分组）
        evaluator_scores = {}
        for result in all_results:
            if result.evaluator_id and result.score is not None:
                if result.evaluator_id not in evaluator_scores:
                    evaluator_scores[result.evaluator_id] = []
                evaluator_scores[result.evaluator_id].append(result.score)

        # 计算总体得分（所有评估器的平均分）
        all_scores = [s for scores in evaluator_scores.values() for s in scores]
        evaluation.overall_score = sum(all_scores) / len(all_scores) if all_scores else 0
        evaluation.success_cases = sum(1 for r in all_results if r.passed)
        evaluation.status = "completed"
        evaluation.completed_at = datetime.utcnow()
        self.db.commit()

        logger.info(
            f"评估任务完成: {evaluation_id}, "
            f"总分: {evaluation.overall_score:.2f}, "
            f"通过: {evaluation.success_cases}/{len(all_results)}"
        )

    async def _execute_test_case(
        self,
        app_id: int,
        test_case: TestCase,
        evaluators: List[Evaluator],
        config: dict,
    ) -> List[EvaluationResult]:
        """执行单个测试用例，返回每个评估器的结果"""
        start_time = time.time()

        # 构建请求
        request = AgentChatRequest(
            query=test_case.input_query,
            inputs=test_case.input_context.get("inputs", {}) if test_case.input_context else {},
        )

        # 获取当前用户（评估任务创建者）
        user_id = config.get("user_id")
        user = self.db.query(User).filter(User.id == user_id).first() if user_id else None

        # 执行 Agent
        try:
            response = await self.agent_service.chat(app_id, request, user)
        except Exception as e:
            logger.error(f"Agent 执行失败: {e}")
            return [self._create_error_result(test_case, evaluator, str(e))
                    for evaluator in evaluators]

        execution_time = int((time.time() - start_time) * 1000)

        # 构建实际输出
        actual_answer = response.answer
        actual_output = {
            "answer": response.answer,
            "tool_calls": response.intermediate_steps,
            "metadata": response.metadata,
        }

        # 创建执行轨迹
        trace = self._create_trace(
            app_id=app_id,
            test_case=test_case,
            response=response,
            execution_time=execution_time,
        )

        # 使用每个评估器评分
        results = []
        for evaluator in evaluators:
            try:
                score = await self.evaluator_engine.evaluate(
                    evaluator=evaluator,
                    test_case=test_case,
                    actual_answer=actual_answer,
                    actual_output=actual_output,
                    trace=trace,
                )

                result = EvaluationResult(
                    test_case_id=test_case.id,
                    evaluator_id=evaluator.id,
                    actual_answer=actual_answer,
                    actual_output=actual_output,
                    actual_trajectory=trace.steps if trace else None,
                    score=score.score,
                    score_details=score.details,
                    passed=score.passed,
                    execution_time=execution_time,
                    diagnostics={"reasoning": score.reasoning},
                )
                results.append(result)
            except Exception as e:
                logger.error(f"评估器 {evaluator.name} 执行失败: {e}")
                results.append(self._create_error_result(test_case, evaluator, str(e)))

        return results

    def _create_trace(
        self,
        app_id: int,
        test_case: TestCase,
        response: Any,
        execution_time: int,
    ) -> Trace:
        """创建执行轨迹"""
        steps = []

        # 从 intermediate_steps 提取轨迹
        if response.intermediate_steps:
            for step in response.intermediate_steps:
                trace_step = {
                    "step_type": "tool_call",
                    "name": step.get("tool", "unknown"),
                    "input": step.get("input", {}),
                    "output": step.get("output", {}),
                    "status": "success" if not step.get("error") else "error",
                    "error": step.get("error"),
                }
                steps.append(trace_step)

        # 添加 LLM 调用步骤
        if response.metadata:
            llm_calls = response.metadata.get("llm_calls", [])
            for call in llm_calls:
                trace_step = {
                    "step_type": "llm_call",
                    "name": call.get("model", "unknown"),
                    "input": {"messages": call.get("messages", [])},
                    "output": {"content": call.get("response", "")},
                    "tokens": call.get("tokens", 0),
                    "status": "success",
                }
                steps.append(trace_step)

        # 添加最终回答步骤
        steps.append({
            "step_type": "answer",
            "name": "final_answer",
            "input": {"query": test_case.input_query},
            "output": {"answer": response.answer},
            "status": "success",
        })

        trace = Trace(
            app_id=app_id,
            trace_type="agent",
            status="completed",
            steps=steps,
            total_steps=len(steps),
            total_llm_calls=sum(1 for s in steps if s.get("step_type") == "llm_call"),
            total_tool_calls=sum(1 for s in steps if s.get("step_type") == "tool_call"),
            total_time_ms=execution_time,
            total_tokens=response.metadata.get("total_tokens", 0) if response.metadata else 0,
            input_query=test_case.input_query,
            output_answer=response.answer,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        self.db.add(trace)
        self.db.flush()

        return trace

    def _create_timeout_result(self, test_case: TestCase, evaluator: Evaluator) -> EvaluationResult:
        """创建超时结果"""
        return EvaluationResult(
            test_case_id=test_case.id,
            evaluator_id=evaluator.id,
            actual_answer="",
            actual_output={"error": "执行超时"},
            score=0.0,
            score_details={"error": "timeout"},
            passed=False,
            execution_time=None,
            error_message="测试用例执行超时",
        )

    def _create_error_result(
        self, test_case: TestCase, evaluator: Evaluator, error_message: str
    ) -> EvaluationResult:
        """创建错误结果"""
        return EvaluationResult(
            test_case_id=test_case.id,
            evaluator_id=evaluator.id,
            actual_answer="",
            actual_output={"error": error_message},
            score=0.0,
            score_details={"error": error_message},
            passed=False,
            execution_time=None,
            error_message=error_message,
        )


def get_evaluation_engine(db: Session) -> EvaluationEngine:
    """获取评估引擎实例"""
    return EvaluationEngine(db)
