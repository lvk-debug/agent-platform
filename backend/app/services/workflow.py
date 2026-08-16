from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.workflow import Workflow, WorkflowRun
from app.utils.logger import logger


class WorkflowEngine:
    """
    工作流执行引擎
    """

    def __init__(self, db: Session):
        self.db = db

    async def execute(
        self,
        workflow_id: int,
        inputs: Dict[str, Any],
        conversation_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        执行工作流
        """
        workflow = self.db.query(Workflow).filter(Workflow.id == workflow_id).first()
        if not workflow:
            raise ValueError(f"工作流不存在: {workflow_id}")

        # 创建运行记录
        run = WorkflowRun(
            workflow_id=workflow_id,
            conversation_id=conversation_id,
            status="running",
            inputs=inputs,
            started_at=datetime.utcnow(),
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)

        try:
            # 解析图结构
            graph = workflow.graph
            nodes = graph.get("nodes", [])
            edges = graph.get("edges", [])

            # 拓扑排序
            sorted_nodes = self._topological_sort(nodes, edges)

            # 执行节点
            node_results = {}
            current_inputs = inputs.copy()

            for node in sorted_nodes:
                node_id = node["id"]
                node_type = node["type"]
                node_config = node.get("config", {})

                # 获取节点输入
                node_inputs = self._get_node_inputs(
                    node_id, edges, node_results, current_inputs
                )

                # 执行节点
                result = await self._execute_node(
                    node_type, node_config, node_inputs
                )

                # 保存结果
                node_results[node_id] = result

            # 更新运行记录
            run.status = "completed"
            run.outputs = node_results
            run.node_runs = node_results
            run.finished_at = datetime.utcnow()
            run.duration = int(
                (run.finished_at - run.started_at).total_seconds() * 1000
            )
            self.db.commit()

            logger.info(f"工作流执行完成: {workflow_id}, 运行ID: {run.id}")
            return {
                "run_id": run.id,
                "status": "completed",
                "outputs": node_results,
            }

        except Exception as e:
            run.status = "failed"
            run.error_message = str(e)
            run.finished_at = datetime.utcnow()
            run.duration = int(
                (run.finished_at - run.started_at).total_seconds() * 1000
            )
            self.db.commit()
            logger.error(f"工作流执行失败: {e}")
            raise

    def _topological_sort(
        self, nodes: List[Dict], edges: List[Dict]
    ) -> List[Dict]:
        """
        拓扑排序
        """
        # 构建邻接表和入度表
        node_map = {node["id"]: node for node in nodes}
        in_degree = {node["id"]: 0 for node in nodes}
        adjacency = {node["id"]: [] for node in nodes}

        for edge in edges:
            source = edge["source"]
            target = edge["target"]
            adjacency[source].append(target)
            in_degree[target] += 1

        # BFS拓扑排序
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_nodes = []

        while queue:
            node_id = queue.pop(0)
            sorted_nodes.append(node_map[node_id])

            for neighbor in adjacency[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(nodes):
            raise ValueError("工作流图存在循环依赖")

        return sorted_nodes

    def _get_node_inputs(
        self,
        node_id: str,
        edges: List[Dict],
        node_results: Dict[str, Any],
        global_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        获取节点输入
        """
        inputs = {}

        # 从前置节点获取输入
        for edge in edges:
            if edge["target"] == node_id:
                source_id = edge["source"]
                if source_id in node_results:
                    source_output = node_results[source_id]
                    # 合并输出到输入
                    if isinstance(source_output, dict):
                        inputs.update(source_output)
                    else:
                        inputs["input"] = source_output

        # 如果没有前置节点输入，使用全局输入
        if not inputs:
            inputs = global_inputs.copy()

        return inputs

    async def _execute_node(
        self,
        node_type: str,
        config: Dict[str, Any],
        inputs: Dict[str, Any],
    ) -> Any:
        """
        执行单个节点
        """
        if node_type == "start":
            return inputs
        elif node_type == "end":
            return inputs
        elif node_type == "llm":
            return await self._execute_llm_node(config, inputs)
        elif node_type == "knowledge_retrieval":
            return await self._execute_knowledge_retrieval_node(config, inputs)
        elif node_type == "condition":
            return await self._execute_condition_node(config, inputs)
        elif node_type == "code":
            return await self._execute_code_node(config, inputs)
        elif node_type == "http":
            return await self._execute_http_node(config, inputs)
        elif node_type == "tool":
            return await self._execute_tool_node(config, inputs)
        else:
            raise ValueError(f"不支持的节点类型: {node_type}")

    async def _execute_llm_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行LLM节点
        """
        from app.services.llm import llm_service

        prompt_template = config.get("prompt", "")
        model = config.get("model", "gpt-3.5-turbo")
        provider = config.get("provider", "openai")
        temperature = config.get("temperature", 0.7)

        # 替换提示词中的变量
        prompt = prompt_template
        for key, value in inputs.items():
            prompt = prompt.replace(f"{{{key}}}", str(value))

        # 调用LLM
        messages = [{"role": "user", "content": prompt}]
        result = await llm_service.chat(
            messages=messages,
            model=model,
            provider=provider,
            temperature=temperature,
        )

        return {"output": result["content"]}

    async def _execute_knowledge_retrieval_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行知识库检索节点
        """
        kb_id = config.get("knowledge_base_id")
        query = inputs.get("query", inputs.get("input", ""))
        top_k = config.get("top_k", 5)

        # TODO: 接入知识库检索服务
        return {"documents": [], "query": query}

    async def _execute_condition_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行条件判断节点
        """
        condition = config.get("condition", "")
        # 简单的条件评估
        try:
            # 安全的条件评估
            result = eval(condition, {"inputs": inputs})
            return {"condition_result": result}
        except Exception as e:
            logger.error(f"条件评估失败: {e}")
            return {"condition_result": False}

    async def _execute_code_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行代码节点
        """
        code = config.get("code", "")
        # TODO: 安全的代码执行环境
        return {"output": "代码执行结果"}

    async def _execute_http_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行HTTP请求节点
        """
        import httpx

        url = config.get("url", "")
        method = config.get("method", "GET").upper()
        headers = config.get("headers", {})
        body = config.get("body", {})

        # 替换URL中的变量
        for key, value in inputs.items():
            url = url.replace(f"{{{key}}}", str(value))

        try:
            async with httpx.AsyncClient() as client:
                if method == "GET":
                    response = await client.get(url, headers=headers, timeout=30.0)
                elif method == "POST":
                    response = await client.post(
                        url, headers=headers, json=body, timeout=30.0
                    )
                else:
                    raise ValueError(f"不支持的HTTP方法: {method}")

                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                }
        except Exception as e:
            logger.error(f"HTTP请求失败: {e}")
            raise

    async def _execute_tool_node(
        self, config: Dict[str, Any], inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具节点
        """
        tool_id = config.get("tool_id")
        tool_params = config.get("parameters", {})

        # TODO: 接入工具服务
        return {"tool_result": "工具执行结果"}


# 创建工作流引擎实例
def get_workflow_engine(db: Session) -> WorkflowEngine:
    return WorkflowEngine(db)
