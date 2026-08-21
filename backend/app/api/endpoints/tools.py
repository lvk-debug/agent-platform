from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.tool import Tool
from app.schemas.tool import ToolCreate, ToolUpdate, ToolResponse
from app.services.tool_templates import get_all_templates, get_template_by_id, get_categories
from app.services.mcp_import import import_mcp_tools
from app.utils.deps import get_current_user

router = APIRouter()


# ============ 请求 Schema ============

class MCPImportRequest(BaseModel):
    url: str


class ToolTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    category: str
    icon: str
    tool_type: str


@router.get("/", response_model=List[ToolResponse])
def read_tools(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    获取工具列表
    """
    tools = db.query(Tool).filter(
        Tool.is_active == True
    ).all()
    return tools


@router.post("/", response_model=ToolResponse)
def create_tool(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tool_in: ToolCreate,
) -> Any:
    """
    创建工具
    """
    tool = Tool(
        name=tool_in.name,
        description=tool_in.description,
        tool_type=tool_in.tool_type,
        icon=tool_in.icon,
        parameters_schema=tool_in.parameters_schema,
        return_schema=tool_in.return_schema,
        endpoint=tool_in.endpoint,
        auth_config=tool_in.auth_config,
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


@router.get("/{tool_id}", response_model=ToolResponse)
def read_tool(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tool_id: int,
) -> Any:
    """
    获取工具详情
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(
            status_code=404,
            detail="工具不存在",
        )
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
def update_tool(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tool_id: int,
    tool_in: ToolUpdate,
) -> Any:
    """
    更新工具
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(
            status_code=404,
            detail="工具不存在",
        )

    # 更新工具信息
    if tool_in.name is not None:
        tool.name = tool_in.name
    if tool_in.description is not None:
        tool.description = tool_in.description
    if tool_in.icon is not None:
        tool.icon = tool_in.icon
    if tool_in.parameters_schema is not None:
        tool.parameters_schema = tool_in.parameters_schema
    if tool_in.return_schema is not None:
        tool.return_schema = tool_in.return_schema
    if tool_in.endpoint is not None:
        tool.endpoint = tool_in.endpoint
    if tool_in.auth_config is not None:
        tool.auth_config = tool_in.auth_config
    if tool_in.is_active is not None:
        tool.is_active = tool_in.is_active

    db.commit()
    db.refresh(tool)
    return tool


@router.delete("/{tool_id}")
def delete_tool(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tool_id: int,
) -> Any:
    """
    删除工具
    """
    tool = db.query(Tool).filter(Tool.id == tool_id).first()
    if not tool:
        raise HTTPException(
            status_code=404,
            detail="工具不存在",
        )

    db.delete(tool)
    db.commit()
    return {"message": "工具已删除"}


# ============ 工具模板 / 安装 / MCP 导入 ============

@router.get("/templates", response_model=List[ToolTemplateResponse])
def list_templates() -> Any:
    """获取所有预置工具模板"""
    templates = get_all_templates()
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "description": t["description"],
            "category": t["category"],
            "icon": t["icon"],
            "tool_type": t["tool_type"],
        }
        for t in templates
    ]


@router.get("/templates/categories")
def list_categories() -> Any:
    """获取工具分类列表"""
    return get_categories()


@router.post("/install/{template_id}", response_model=ToolResponse)
def install_from_template(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    template_id: str,
) -> Any:
    """从模板安装工具"""
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 检查是否已安装同名工具
    existing = db.query(Tool).filter(Tool.name == template["name"]).first()
    if existing:
        raise HTTPException(status_code=400, detail="该工具已安装")

    tool = Tool(
        name=template["name"],
        description=template["description"],
        tool_type=template["tool_type"],
        icon=template.get("icon"),
        parameters_schema=template.get("parameters_schema"),
        return_schema=template.get("return_schema"),
        endpoint=template.get("endpoint"),
        auth_config=template.get("auth_config"),
    )
    db.add(tool)
    db.commit()
    db.refresh(tool)
    return tool


@router.post("/import/mcp", response_model=List[ToolResponse])
async def import_mcp(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    data: MCPImportRequest,
) -> Any:
    """从 MCP Server URL 导入工具"""
    try:
        tools_data = await import_mcp_tools(data.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"MCP 导入失败: {str(e)}")

    if not tools_data:
        raise HTTPException(status_code=404, detail="未从该 MCP Server 发现工具")

    created_tools = []
    for tool_data in tools_data:
        # 跳过已存在的同名工具
        existing = db.query(Tool).filter(Tool.name == tool_data["name"]).first()
        if existing:
            continue

        tool = Tool(
            name=tool_data["name"],
            description=tool_data["description"],
            tool_type=tool_data["tool_type"],
            icon=tool_data.get("icon"),
            parameters_schema=tool_data.get("parameters_schema"),
            endpoint=tool_data.get("endpoint"),
            auth_config=tool_data.get("auth_config"),
        )
        db.add(tool)
        db.flush()
        db.refresh(tool)
        created_tools.append(tool)

    db.commit()
    return created_tools
