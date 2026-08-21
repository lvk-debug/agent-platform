"""
工作流 Schema 模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# 节点类型枚举
# ------------------------------------------------------------------

class NodeType(str, Enum):
    """节点类型"""
    START = "start"
    END = "end"
    LLM = "llm"
    KNOWLEDGE_RETRIEVAL = "knowledge_retrieval"
    CONDITION = "condition"
    QUESTION_CLASSIFIER = "question_classifier"
    CODE = "code"
    HTTP = "http"
    TOOL = "tool"
    HUMAN_INTERVENTION = "human_intervention"


# ------------------------------------------------------------------
# 节点配置
# ------------------------------------------------------------------

class NodePosition(BaseModel):
    """节点位置"""
    x: float
    y: float


class StartNodeConfig(BaseModel):
    """开始节点配置"""
    variables: List[Dict[str, Any]] = Field(default_factory=list, description="输入变量定义")


class EndNodeConfig(BaseModel):
    """结束节点配置"""
    output_keys: List[str] = Field(default_factory=list, description="输出的变量键名列表")


class LLMContextVariable(BaseModel):
    """LLM 上下文变量"""
    variable_selector: List[str] = Field(default_factory=list, description="变量选择器路径")
    variable_type: str = Field("string", description="变量类型: string, number, object, array")


class LLMMemoryConfig(BaseModel):
    """LLM 记忆配置"""
    enabled: bool = True
    window: int = Field(10, ge=1, le=100, description="记忆窗口大小")
    role_prefix: str = Field("USER", description="角色前缀")


class LLMNodeConfig(BaseModel):
    """LLM 节点配置"""
    model_id: Optional[int] = None
    model: Optional[str] = None
    prompt: str = ""
    system_prompt: Optional[str] = None
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1, le=8192)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    output_key: str = "output"
    # 新增字段
    context: List[LLMContextVariable] = Field(default_factory=list, description="上下文变量列表")
    memory: LLMMemoryConfig = Field(default_factory=LLMMemoryConfig, description="记忆配置")
    vision: bool = Field(False, description="是否启用视觉")
    thinking_tag: bool = Field(False, description="是否启用推理标签分离")
    structured_output: bool = Field(False, description="是否启用结构化输出")
    retry_on_failure: bool = Field(False, description="失败时重试")


class KnowledgeRetrievalConfig(BaseModel):
    """知识库检索节点配置"""
    knowledge_base_id: Optional[int] = None
    top_k: int = Field(5, ge=1, le=20)
    score_threshold: float = Field(0.5, ge=0.0, le=1.0)
    query_key: str = "query"
    output_key: str = "documents"


class ConditionBranch(BaseModel):
    """条件分支"""
    variable: str = Field("", description="变量名")
    operator: str = Field("contains", description="操作符: contains, equals, gt, lt, default")
    value: str = Field("", description="比较值")
    branch: str = Field("", description="分支名称")


class ConditionNodeConfig(BaseModel):
    """条件节点配置"""
    branches: List[ConditionBranch] = Field(default_factory=list)


class CodeNodeConfig(BaseModel):
    """代码节点配置"""
    code: str = ""
    language: str = "python"
    output_key: str = "output"


class HTTPNodeConfig(BaseModel):
    """HTTP 节点配置"""
    url: str = ""
    method: str = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    timeout: int = 30
    output_key: str = "response"


class ToolNodeConfig(BaseModel):
    """工具节点配置"""
    tool_id: Optional[int] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    output_key: str = "result"


class HumanInterventionConfig(BaseModel):
    """人工介入节点配置"""
    timeout: int = Field(300, ge=1, le=3600, description="超时时间（秒）")
    timeout_output: str = Field("timeout", description="超时输出值")
    message: str = Field("", description="提示消息")
    output_key: str = "output"


class QuestionClassifierCategory(BaseModel):
    """问题分类类别"""
    id: str = Field("", description="类别 ID")
    name: str = Field("", description="类别名称")
    description: str = Field("", description="类别描述/主题内容")


class QuestionClassifierConfig(BaseModel):
    """问题分类器节点配置"""
    model_id: Optional[int] = None
    model: Optional[str] = None
    input_variable: str = Field("", description="输入变量，如 sys.query")
    vision: bool = Field(False, description="是否启用视觉")
    categories: List[QuestionClassifierCategory] = Field(default_factory=list, description="分类列表")
    output_key: str = "classification"


class NodeData(BaseModel):
    """节点显示数据"""
    label: str = ""
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class WorkflowNode(BaseModel):
    """工作流节点"""
    id: str
    type: NodeType
    position: NodePosition = Field(default_factory=lambda: NodePosition(x=0, y=0))
    data: NodeData = Field(default_factory=lambda: NodeData())


class WorkflowEdge(BaseModel):
    """工作流边"""
    id: str
    source: str
    target: str
    sourceHandle: Optional[str] = None
    targetHandle: Optional[str] = None
    label: Optional[str] = None


class WorkflowGraph(BaseModel):
    """工作流图结构"""
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


# ------------------------------------------------------------------
# 工作流配置
# ------------------------------------------------------------------

class WorkflowConfig(BaseModel):
    """工作流完整配置"""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    name: Optional[str] = None
    description: Optional[str] = None
    version: int = 1


class WorkflowCreate(BaseModel):
    """创建工作流请求"""
    graph: WorkflowGraph = Field(default_factory=WorkflowGraph)
    name: Optional[str] = None
    description: Optional[str] = None


class WorkflowUpdate(BaseModel):
    """更新工作流请求"""
    graph: Optional[WorkflowGraph] = None
    name: Optional[str] = None
    description: Optional[str] = None


# ------------------------------------------------------------------
# 响应模型
# ------------------------------------------------------------------

class WorkflowResponse(BaseModel):
    """工作流响应"""
    id: int
    app_id: int
    graph: WorkflowGraph
    version: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkflowRunResponse(BaseModel):
    """工作流运行记录响应"""
    id: int
    workflow_id: int
    status: str
    inputs: Optional[Dict[str, Any]] = None
    outputs: Optional[Dict[str, Any]] = None
    node_runs: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class WorkflowRunRequest(BaseModel):
    """工作流执行请求"""
    inputs: Dict[str, Any] = Field(default_factory=dict)
    thread_id: Optional[str] = None


# ------------------------------------------------------------------
# DSL 导入导出
# ------------------------------------------------------------------

class DSLData(BaseModel):
    """DSL 数据格式"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: int = 1
    nodes: List[WorkflowNode] = Field(default_factory=list)
    edges: List[WorkflowEdge] = Field(default_factory=list)


class DSLImportRequest(BaseModel):
    """DSL 导入请求"""
    dsl: DSLData


class DSLExportResponse(BaseModel):
    """DSL 导出响应"""
    dsl: DSLData
