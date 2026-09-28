"""
执行轨迹收集器

自动收集 Agent/Chatbot/Workflow 的执行轨迹，用于在线评估和调试。

使用方式:
    collector = TraceCollector(db)
    trace = collector.start_trace(app_id, "agent", query)
    collector.add_llm_call(trace, model, messages, response, tokens)
    collector.add_tool_call(trace, tool_name, input_data, output_data)
    collector.finish_trace(trace, answer)
"""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.evaluation import Trace
from app.utils.logger import logger


class TraceCollector:
    """执行轨迹收集器"""

    def __init__(self, db: Session):
        self.db = db
        self._active_traces: Dict[int, Dict[str, Any]] = {}

    def start_trace(
        self,
        app_id: int,
        trace_type: str,
        input_query: str,
        evaluation_result_id: Optional[int] = None,
        conversation_id: Optional[int] = None,
    ) -> Trace:
        """开始收集轨迹"""
        trace = Trace(
            app_id=app_id,
            trace_type=trace_type,
            status="running",
            evaluation_result_id=evaluation_result_id,
            conversation_id=conversation_id,
            input_query=input_query,
            steps=[],
            started_at=datetime.utcnow(),
        )
        self.db.add(trace)
        self.db.flush()

        # 记录开始时间
        self._active_traces[trace.id] = {
            "start_time": time.time(),
            "steps": [],
            "llm_calls": 0,
            "tool_calls": 0,
            "total_tokens": 0,
        }

        return trace

    def add_llm_call(
        self,
        trace: Trace,
        model: str,
        messages: List[Dict[str, str]],
        response: str,
        tokens: int = 0,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录 LLM 调用"""
        if trace.id not in self._active_traces:
            logger.warning(f"Trace {trace.id} not active, skipping LLM call recording")
            return

        step = {
            "step_type": "llm_call",
            "name": model,
            "input": {"messages": messages},
            "output": {"content": response},
            "tokens": tokens,
            "duration_ms": duration_ms,
            "status": "success",
            "metadata": metadata,
        }

        self._active_traces[trace.id]["steps"].append(step)
        self._active_traces[trace.id]["llm_calls"] += 1
        self._active_traces[trace.id]["total_tokens"] += tokens

    def add_tool_call(
        self,
        trace: Trace,
        tool_name: str,
        input_data: Dict[str, Any],
        output_data: Any,
        duration_ms: Optional[int] = None,
        status: str = "success",
        error: Optional[str] = None,
    ):
        """记录工具调用"""
        if trace.id not in self._active_traces:
            logger.warning(f"Trace {trace.id} not active, skipping tool call recording")
            return

        step = {
            "step_type": "tool_call",
            "name": tool_name,
            "input": input_data,
            "output": output_data if isinstance(output_data, dict) else {"result": output_data},
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
        }

        self._active_traces[trace.id]["steps"].append(step)
        self._active_traces[trace.id]["tool_calls"] += 1

    def add_workflow_node(
        self,
        trace: Trace,
        node_id: str,
        node_type: str,
        input_data: Dict[str, Any],
        output_data: Any,
        duration_ms: Optional[int] = None,
        status: str = "success",
        error: Optional[str] = None,
    ):
        """记录工作流节点执行"""
        if trace.id not in self._active_traces:
            logger.warning(f"Trace {trace.id} not active, skipping workflow node recording")
            return

        step = {
            "step_type": "workflow_node",
            "name": f"{node_type}:{node_id}",
            "input": input_data,
            "output": output_data if isinstance(output_data, dict) else {"result": output_data},
            "duration_ms": duration_ms,
            "status": status,
            "error": error,
            "metadata": {"node_id": node_id, "node_type": node_type},
        }

        self._active_traces[trace.id]["steps"].append(step)

    def add_custom_step(
        self,
        trace: Trace,
        step_type: str,
        name: str,
        input_data: Any = None,
        output_data: Any = None,
        duration_ms: Optional[int] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """记录自定义步骤"""
        if trace.id not in self._active_traces:
            logger.warning(f"Trace {trace.id} not active, skipping custom step recording")
            return

        step = {
            "step_type": step_type,
            "name": name,
            "input": input_data,
            "output": output_data,
            "duration_ms": duration_ms,
            "status": status,
            "metadata": metadata,
        }

        self._active_traces[trace.id]["steps"].append(step)

    def finish_trace(
        self,
        trace: Trace,
        output_answer: str,
        status: str = "completed",
        error_message: Optional[str] = None,
    ):
        """完成轨迹收集"""
        if trace.id not in self._active_traces:
            logger.warning(f"Trace {trace.id} not active, cannot finish")
            return

        trace_data = self._active_traces[trace.id]

        # 计算总耗时
        total_time_ms = int((time.time() - trace_data["start_time"]) * 1000)

        # 更新轨迹
        trace.steps = trace_data["steps"]
        trace.total_steps = len(trace_data["steps"])
        trace.total_llm_calls = trace_data["llm_calls"]
        trace.total_tool_calls = trace_data["tool_calls"]
        trace.total_time_ms = total_time_ms
        trace.total_tokens = trace_data["total_tokens"]
        trace.output_answer = output_answer
        trace.status = status
        trace.error_message = error_message
        trace.completed_at = datetime.utcnow()

        # 清理
        del self._active_traces[trace.id]

        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to save trace: {e}")
            self.db.rollback()

    def get_active_trace(self, trace_id: int) -> Optional[Trace]:
        """获取活跃的轨迹"""
        if trace_id in self._active_traces:
            return self.db.query(Trace).filter(Trace.id == trace_id).first()
        return None

    def get_trace_summary(self, trace: Trace) -> Dict[str, Any]:
        """获取轨迹摘要"""
        return {
            "id": trace.id,
            "trace_type": trace.trace_type,
            "status": trace.status,
            "total_steps": trace.total_steps,
            "total_llm_calls": trace.total_llm_calls,
            "total_tool_calls": trace.total_tool_calls,
            "total_time_ms": trace.total_time_ms,
            "total_tokens": trace.total_tokens,
            "input_query": trace.input_query,
            "output_answer": trace.output_answer,
        }


# 全局轨迹收集器实例
_collector_instance: Optional[TraceCollector] = None


def get_trace_collector(db: Session) -> TraceCollector:
    """获取轨迹收集器实例"""
    return TraceCollector(db)
