"""
Agent Schema 模型 - 使用 LangGraph create_react_agent
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.chatbot import (
    ChatbotVariable,
    KnowledgeBaseConfig,
    ModelParameters,
)


class AgentPromptConfig(BaseModel):
    """Agent 提示词配置"""
    system_prompt: Optional[str] = Field(
        None,
        description="系统提示词，定义 Agent 的角色和行为规范"
    )


class ToolConfig(BaseModel):
    """工具配置"""
    tool_id: int
    name: str
    enabled: bool = True
    config: Optional[Dict[str, Any]] = None


class AgentConfig(BaseModel):
    """
    Agent 完整配置

    使用 LangGraph 的 create_react_agent 实现智能体编排
    """
    # 提示词
    prompt: AgentPromptConfig = Field(default_factory=AgentPromptConfig)

    # 变量
    variables: List[ChatbotVariable] = Field(default_factory=list)

    # 模型配置
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    model_parameters: ModelParameters = Field(default_factory=ModelParameters)

    # 知识库
    knowledge_bases: List[KnowledgeBaseConfig] = Field(default_factory=list)
    metadata_filter_enabled: bool = False

    # 工具
    tools: List[ToolConfig] = Field(default_factory=list)

    # 对话记忆
    memory_enabled: bool = True
    memory_window: int = Field(50, ge=1, le=500)

    # 最大迭代次数 (React Agent 循环次数)
    max_iterations: int = Field(10, ge=1, le=50, description="Agent 最大迭代次数")


class AgentUpdate(BaseModel):
    """Agent 更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    config: Optional[AgentConfig] = None


class AgentChatRequest(BaseModel):
    """Agent 聊天请求"""
    query: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[int] = None
    inputs: Optional[Dict[str, str]] = None
    response_mode: str = Field("blocking", pattern="^(blocking|streaming)$")


class AgentChatResponse(BaseModel):
    """Agent 聊天响应"""
    answer: str
    conversation_id: int
    message_id: int
    # Agent 执行轨迹 -用于运行日志调试
    intermediate_steps: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentConfigResponse(BaseModel):
    """Agent 配置响应"""
    app_id: int
    app_name: str
    config: AgentConfig

    class Config:
        from_attributes = True
