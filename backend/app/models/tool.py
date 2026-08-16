from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text, JSON
from sqlalchemy.orm import relationship

from app.core.database import Base


class Tool(Base):
    """
    工具表
    """
    __tablename__ = "tools"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    tool_type = Column(
        Enum("builtin", "plugin", "mcp", name="tool_type_enum"),
        nullable=False,
        default="builtin"
    )

    # 工具配置
    icon = Column(String(500), nullable=True)
    parameters_schema = Column(JSON, nullable=True)  # 参数JSON Schema
    return_schema = Column(JSON, nullable=True)  # 返回值JSON Schema

    # 对于插件和MCP工具
    endpoint = Column(String(500), nullable=True)
    auth_config = Column(JSON, nullable=True)

    # 状态
    is_active = Column(Boolean, default=True)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    app_tools = relationship("AppTool", back_populates="tool")

    def __repr__(self):
        return f"<Tool(id={self.id}, name={self.name}, type={self.tool_type})>"


class AppTool(Base):
    """
    应用与工具的关联表
    """
    __tablename__ = "app_tools"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)
    tool_id = Column(Integer, ForeignKey("tools.id"), nullable=False)
    config = Column(JSON, nullable=True)  # 工具在该应用中的特定配置
    created_at = Column(DateTime, default=datetime.utcnow)

    # 关系
    app = relationship("App")
    tool = relationship("Tool", back_populates="app_tools")

    def __repr__(self):
        return f"<AppTool(app_id={self.app_id}, tool_id={self.tool_id})>"
