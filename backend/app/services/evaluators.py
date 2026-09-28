"""
评估器引擎 (v2)

参考 LangSmith 评估框架，支持四种评估器类型：
- heuristic: 启发式规则评估
- llm_judge: LLM 裁判评估
- trajectory: 轨迹评估
- custom: 自定义脚本评估

使用方式:
    engine = EvaluatorEngine(db)
    score = await engine.evaluate(evaluator, test_case, actual_answer, actual_output)
"""

import json
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.evaluation import Evaluator, TestCase, Trace
from app.utils.logger import logger


# ============================================================
# 评估结果数据类
# ============================================================


class EvaluationScore:
    """评估得分"""

    def __init__(
        self,
        score: float,
        passed: bool = True,
        details: Optional[Dict[str, Any]] = None,
        reasoning: Optional[str] = None,
    ):
        self.score = max(0.0, min(1.0, score))  # 限制在 0-1 范围
        self.passed = passed
        self.details = details or {}
        self.reasoning = reasoning

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "details": self.details,
            "reasoning": self.reasoning,
        }


# ============================================================
# 基础评估器
# ============================================================


class BaseEvaluator(ABC):
    """评估器基类"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @abstractmethod
    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        """执行评估"""
        pass


# ============================================================
# 启发式评估器
# ============================================================


class ExactMatchEvaluator(BaseEvaluator):
    """精确匹配评估器"""

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected = test_case.expected_answer
        if not expected:
            return EvaluationScore(score=1.0, details={"reason": "no expected answer"})

        if not actual_answer:
            return EvaluationScore(score=0.0, passed=False, details={"reason": "no actual answer"})

        # 标准化比较
        expected_norm = expected.strip().lower()
        actual_norm = actual_answer.strip().lower()

        match = expected_norm == actual_norm
        return EvaluationScore(
            score=1.0 if match else 0.0,
            passed=match,
            details={
                "expected": expected,
                "actual": actual_answer,
                "match": match,
            },
        )


class ContainsEvaluator(BaseEvaluator):
    """包含匹配评估器"""

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected = test_case.expected_answer
        if not expected:
            return EvaluationScore(score=1.0, details={"reason": "no expected answer"})

        if not actual_answer:
            return EvaluationScore(score=0.0, passed=False, details={"reason": "no actual answer"})

        expected_norm = expected.strip().lower()
        actual_norm = actual_answer.strip().lower()

        contains = expected_norm in actual_norm
        return EvaluationScore(
            score=1.0 if contains else 0.0,
            passed=contains,
            details={
                "expected": expected,
                "actual": actual_answer,
                "contains": contains,
            },
        )


class RegexMatchEvaluator(BaseEvaluator):
    """正则匹配评估器"""

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        pattern = self.config.get("pattern")
        if not pattern:
            # 从 expected_answer 中提取正则
            pattern = test_case.expected_answer

        if not pattern or not actual_answer:
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"reason": "missing pattern or actual answer"},
            )

        try:
            match = bool(re.search(pattern, actual_answer, re.IGNORECASE))
            return EvaluationScore(
                score=1.0 if match else 0.0,
                passed=match,
                details={"pattern": pattern, "actual": actual_answer, "match": match},
            )
        except re.error as e:
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"error": f"invalid regex: {e}"},
            )


class JsonMatchEvaluator(BaseEvaluator):
    """JSON 匹配评估器"""

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected_json = test_case.expected_answer
        if not expected_json:
            return EvaluationScore(score=1.0, details={"reason": "no expected JSON"})

        if not actual_answer:
            return EvaluationScore(score=0.0, passed=False, details={"reason": "no actual answer"})

        try:
            expected = json.loads(expected_json)
            actual = json.loads(actual_answer)
            match = expected == actual
            return EvaluationScore(
                score=1.0 if match else 0.0,
                passed=match,
                details={"expected": expected, "actual": actual, "match": match},
            )
        except json.JSONDecodeError:
            # 回退到字符串比较
            match = expected_json.strip() == actual_answer.strip()
            return EvaluationScore(
                score=1.0 if match else 0.0,
                passed=match,
                details={"expected": expected_json, "actual": actual_answer, "match": match},
            )


class ToolAccuracyEvaluator(BaseEvaluator):
    """工具调用准确性评估器"""

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected_tools = set(test_case.expected_tools or [])
        actual_tools = set()

        if actual_output:
            # 从 actual_output 中提取工具调用
            tool_calls = actual_output.get("tool_calls", [])
            for call in tool_calls:
                tool_name = call.get("tool", call.get("name", ""))
                if tool_name:
                    actual_tools.add(tool_name)

        if not expected_tools and not actual_tools:
            return EvaluationScore(
                score=1.0,
                details={"reason": "no tools expected or used"},
            )

        if not expected_tools:
            return EvaluationScore(
                score=0.5,
                details={"reason": "unexpected tools used", "actual_tools": list(actual_tools)},
            )

        if not actual_tools:
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"reason": "expected tools not used", "expected_tools": list(expected_tools)},
            )

        # 计算匹配度
        matches = expected_tools & actual_tools
        precision = len(matches) / len(actual_tools) if actual_tools else 0
        recall = len(matches) / len(expected_tools) if expected_tools else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

        return EvaluationScore(
            score=f1,
            passed=f1 >= 0.5,
            details={
                "expected_tools": list(expected_tools),
                "actual_tools": list(actual_tools),
                "matches": list(matches),
                "precision": precision,
                "recall": recall,
                "f1": f1,
            },
        )


class NumericMatchEvaluator(BaseEvaluator):
    """数值匹配评估器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.tolerance = self.config.get("tolerance", 0.01)

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected = test_case.expected_answer
        if not expected:
            return EvaluationScore(score=1.0, details={"reason": "no expected answer"})

        if not actual_answer:
            return EvaluationScore(score=0.0, passed=False, details={"reason": "no actual answer"})

        try:
            expected_num = float(expected.strip())
            actual_num = float(actual_answer.strip())
            diff = abs(expected_num - actual_num)
            match = diff <= self.tolerance
            return EvaluationScore(
                score=1.0 if match else max(0, 1 - diff / max(abs(expected_num), 1)),
                passed=match,
                details={
                    "expected": expected_num,
                    "actual": actual_num,
                    "diff": diff,
                    "tolerance": self.tolerance,
                    "match": match,
                },
            )
        except (ValueError, TypeError):
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"error": "cannot parse as number"},
            )


# ============================================================
# LLM 裁判评估器
# ============================================================


class LLMJudgeEvaluator(BaseEvaluator):
    """LLM 裁判评估器

    使用 LLM 评估回答质量，支持自定义评分提示词
    """

    DEFAULT_PROMPT = """你是一个专业的 AI 回答质量评估专家。

请根据以下标准评估 AI 的回答质量，给出 0-10 的分数。

## 评估标准
- 准确性：回答是否正确
- 完整性：是否完整回答了问题
- 相关性：是否与问题相关
- 清晰度：表达是否清晰

## 测试用例
问题: {query}
期望答案: {expected_answer}

## AI 回答
{actual_answer}

## 输出格式
请以 JSON 格式输出：
{{"score": <0-10>, "reasoning": "<评估理由>"}}
"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.judge_model = self.config.get("judge_model", "gpt-3.5-turbo")
        self.judge_prompt = self.config.get("judge_prompt", self.DEFAULT_PROMPT)
        self._llm_service = None

    def _get_llm_service(self):
        """延迟初始化 LLM 服务"""
        if self._llm_service is None:
            from app.services.llm import LLMService
            self._llm_service = LLMService()
        return self._llm_service

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        if not actual_answer:
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"reason": "no actual answer"},
            )

        # 构建提示词
        prompt = self.judge_prompt.format(
            query=test_case.input_query,
            expected_answer=test_case.expected_answer or "无",
            actual_answer=actual_answer,
        )

        try:
            # 调用 LLM 进行评估
            llm = self._get_llm_service()
            response = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self.judge_model,
                temperature=0.1,
                max_tokens=500,
            )

            # 解析响应
            content = response.get("content", "")
            result = self._parse_judge_response(content)

            score = result.get("score", 0) / 10.0  # 转换为 0-1
            reasoning = result.get("reasoning", "")

            return EvaluationScore(
                score=score,
                passed=score >= 0.6,
                details={"raw_response": content},
                reasoning=reasoning,
            )
        except Exception as e:
            logger.error(f"LLM judge evaluation failed: {e}")
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"error": str(e)},
            )

    def _parse_judge_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 裁判的响应"""
        try:
            # 尝试直接解析 JSON
            return json.loads(content)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'\{[^}]+\}', content)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # 尝试提取分数
            score_match = re.search(r'score["\s:]+(\d+)', content, re.IGNORECASE)
            if score_match:
                return {"score": int(score_match.group(1)), "reasoning": content}

            return {"score": 0, "reasoning": content}


# ============================================================
# 轨迹评估器
# ============================================================


class TrajectoryMatchEvaluator(BaseEvaluator):
    """轨迹匹配评估器

    评估执行轨迹是否符合期望
    """

    async def evaluate(
        self,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        expected_trajectory = test_case.expected_trajectory
        if not expected_trajectory:
            return EvaluationScore(score=1.0, details={"reason": "no expected trajectory"})

        if not trace:
            return EvaluationScore(
                score=0.0,
                passed=False,
                details={"reason": "no trace available"},
            )

        actual_steps = trace.steps or []

        # 比较轨迹
        score, details = self._compare_trajectories(expected_trajectory, actual_steps)

        return EvaluationScore(
            score=score,
            passed=score >= 0.7,
            details=details,
        )

    def _compare_trajectories(
        self,
        expected: List[Dict[str, Any]],
        actual: List[Dict[str, Any]],
    ) -> Tuple[float, Dict[str, Any]]:
        """比较两条轨迹"""
        if not expected:
            return 1.0, {"reason": "empty expected trajectory"}

        if not actual:
            return 0.0, {"reason": "empty actual trajectory"}

        # 提取步骤类型序列
        expected_types = [s.get("step_type", "") for s in expected]
        actual_types = [s.get("step_type", "") for s in actual]

        # 计算序列匹配度（LCS 算法）
        lcs_length = self._lcs_length(expected_types, actual_types)
        sequence_score = lcs_length / max(len(expected_types), len(actual_types))

        # 比较每个步骤的详细信息
        step_scores = []
        for i, (exp, act) in enumerate(zip(expected, actual)):
            step_score = self._compare_step(exp, act)
            step_scores.append(step_score)

        avg_step_score = sum(step_scores) / len(step_scores) if step_scores else 0

        # 综合得分
        final_score = 0.6 * sequence_score + 0.4 * avg_step_score

        return final_score, {
            "expected_steps": len(expected),
            "actual_steps": len(actual),
            "sequence_score": sequence_score,
            "avg_step_score": avg_step_score,
            "final_score": final_score,
        }

    def _lcs_length(self, seq1: List[str], seq2: List[str]) -> int:
        """计算最长公共子序列长度"""
        m, n = len(seq1), len(seq2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if seq1[i - 1] == seq2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[m][n]

    def _compare_step(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> float:
        """比较单个步骤"""
        score = 0.0
        checks = 0

        # 比较步骤类型
        if "step_type" in expected:
            checks += 1
            if expected["step_type"] == actual.get("step_type"):
                score += 1

        # 比较名称
        if "name" in expected:
            checks += 1
            if expected["name"] == actual.get("name"):
                score += 1

        # 比较输入（部分匹配）
        if "input" in expected:
            checks += 1
            exp_input = json.dumps(expected["input"], sort_keys=True)
            act_input = json.dumps(actual.get("input", {}), sort_keys=True)
            if exp_input == act_input:
                score += 1
            elif exp_input in act_input or act_input in exp_input:
                score += 0.5

        return score / checks if checks > 0 else 1.0


# ============================================================
# 评估器引擎
# ============================================================


# 评估器类型映射
EVALUATOR_REGISTRY = {
    # 启发式评估器
    "exact_match": ExactMatchEvaluator,
    "contains": ContainsEvaluator,
    "regex": RegexMatchEvaluator,
    "json_match": JsonMatchEvaluator,
    "tool_accuracy": ToolAccuracyEvaluator,
    "numeric_match": NumericMatchEvaluator,
    # LLM 裁判
    "llm_judge": LLMJudgeEvaluator,
    # 轨迹评估
    "trajectory_match": TrajectoryMatchEvaluator,
}


class EvaluatorEngine:
    """评估器引擎"""

    def __init__(self, db: Session):
        self.db = db

    def get_evaluator(self, evaluator: Evaluator) -> BaseEvaluator:
        """根据评估器配置创建评估器实例"""
        # 确定评估器类型
        if evaluator.evaluator_type == "heuristic":
            metric_type = evaluator.metric_type
            if metric_type and metric_type in EVALUATOR_REGISTRY:
                evaluator_class = EVALUATOR_REGISTRY[metric_type]
            else:
                raise ValueError(f"Unknown metric type: {metric_type}")
        elif evaluator.evaluator_type == "llm_judge":
            evaluator_class = LLMJudgeEvaluator
        elif evaluator.evaluator_type == "trajectory":
            evaluator_class = TrajectoryMatchEvaluator
        elif evaluator.evaluator_type == "custom":
            # TODO: 支持自定义脚本评估器
            raise NotImplementedError("Custom evaluator not yet implemented")
        else:
            raise ValueError(f"Unknown evaluator type: {evaluator.evaluator_type}")

        # 构建配置
        config = evaluator.config or {}
        if evaluator.judge_model:
            config["judge_model"] = evaluator.judge_model
        if evaluator.judge_prompt:
            config["judge_prompt"] = evaluator.judge_prompt

        return evaluator_class(config)

    async def evaluate(
        self,
        evaluator: Evaluator,
        test_case: TestCase,
        actual_answer: Optional[str],
        actual_output: Optional[Dict[str, Any]],
        trace: Optional[Trace] = None,
    ) -> EvaluationScore:
        """执行评估"""
        evaluator_instance = self.get_evaluator(evaluator)
        return await evaluator_instance.evaluate(
            test_case, actual_answer, actual_output, trace
        )

    def create_builtin_evaluators(self) -> List[Evaluator]:
        """创建内置评估器"""
        builtin_evaluators = [
            # 启发式评估器
            Evaluator(
                name="精确匹配",
                description="比较实际答案与期望答案是否完全一致",
                evaluator_type="heuristic",
                metric_type="exact_match",
                is_builtin=True,
            ),
            Evaluator(
                name="包含匹配",
                description="检查期望答案是否包含在实际答案中",
                evaluator_type="heuristic",
                metric_type="contains",
                is_builtin=True,
            ),
            Evaluator(
                name="数值匹配",
                description="比较数值答案是否在容差范围内",
                evaluator_type="heuristic",
                metric_type="numeric_match",
                config={"tolerance": 0.01},
                is_builtin=True,
            ),
            Evaluator(
                name="工具准确性",
                description="评估工具调用的准确性（精确率、召回率、F1）",
                evaluator_type="heuristic",
                metric_type="tool_accuracy",
                is_builtin=True,
            ),
            Evaluator(
                name="JSON 匹配",
                description="比较 JSON 格式的答案是否一致",
                evaluator_type="heuristic",
                metric_type="json_match",
                is_builtin=True,
            ),
            # LLM 裁判
            Evaluator(
                name="LLM 裁判 (通用)",
                description="使用 LLM 评估回答质量（准确性、完整性、相关性、清晰度）",
                evaluator_type="llm_judge",
                judge_model="gpt-3.5-turbo",
                judge_prompt=LLMJudgeEvaluator.DEFAULT_PROMPT,
                is_builtin=True,
            ),
            # 轨迹评估
            Evaluator(
                name="轨迹匹配",
                description="评估执行轨迹是否符合期望路径",
                evaluator_type="trajectory",
                is_builtin=True,
            ),
        ]

        # 保存到数据库
        for evaluator in builtin_evaluators:
            existing = self.db.query(Evaluator).filter(
                Evaluator.name == evaluator.name,
                Evaluator.is_builtin == True,
            ).first()
            if not existing:
                self.db.add(evaluator)

        self.db.commit()
        return builtin_evaluators
