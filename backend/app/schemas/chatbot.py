"""
聊天助手 Schema 模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VariableType(str, Enum):
    """变量类型"""
    TEXT_INPUT = "text_input"
    PARAGRAPH = "paragraph"
    SELECT = "select"


class VariableOption(BaseModel):
    """变量选项"""
    value: str
    label: str


class ChatbotVariable(BaseModel):
    """聊天助手变量"""
    key: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    type: VariableType = VariableType.TEXT_INPUT
    required: bool = False
    default: Optional[str] = None
    options: Optional[List[VariableOption]] = None
    description: Optional[str] = None


class KnowledgeBaseConfig(BaseModel):
    """知识库配置"""
    knowledge_base_id: int
    name: str
    enabled: bool = True
    score_threshold: float = Field(0.5, ge=0.0, le=1.0)
    top_k: int = Field(3, ge=1, le=20)
    show_citation: bool = Field(False, description="是否在回答中附带引用信息")


class ChatbotPromptConfig(BaseModel):
    """提示词配置"""
    system_prompt: Optional[str] = None
    opening_statement: Optional[str] = None
    suggested_questions: Optional[List[str]] = None


class ModelParameters(BaseModel):
    """模型参数配置"""
    temperature: float = Field(0.7, ge=0.0, le=2.0, description="温度")
    top_p: float = Field(1.0, ge=0.0, le=1.0, description="Top P")
    top_k: int = Field(1, ge=1, le=100, description="Top K")
    presence_penalty: float = Field(0, ge=-2.0, le=2.0, description="存在惩罚")
    frequency_penalty: float = Field(0, ge=-2.0, le=2.0, description="频率惩罚")
    max_tokens: int = Field(512, ge=1, le=8192, description="最大生成长度")
    skip_content_review: bool = Field(False, description="跳过内容审核")


class ChatbotConfig(BaseModel):
    """聊天助手完整配置"""
    prompt: ChatbotPromptConfig = Field(default_factory=ChatbotPromptConfig)
    variables: List[ChatbotVariable] = Field(default_factory=list)
    knowledge_bases: List[KnowledgeBaseConfig] = Field(default_factory=list)
    model_id: Optional[int] = None
    model_name: Optional[str] = None
    model_parameters: ModelParameters = Field(default_factory=ModelParameters)
    memory_enabled: bool = True
    memory_window: int = Field(50, ge=1, le=500)
    metadata_filter_enabled: bool = False


class ChatbotUpdate(BaseModel):
    """聊天助手更新请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    config: Optional[ChatbotConfig] = None


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """聊天请求"""
    query: str = Field(..., min_length=1, max_length=10000)
    conversation_id: Optional[int] = None
    inputs: Optional[Dict[str, str]] = None
    response_mode: str = Field("blocking", pattern="^(blocking|streaming)$")


class ChatResponse(BaseModel):
    """聊天响应"""
    answer: str
    conversation_id: int
    message_id: int
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    """会话响应"""
    id: int
    app_id: int
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """消息响应"""
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True
