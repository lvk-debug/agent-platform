from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.tool import Tool
from app.schemas.tool import ToolCreate, ToolUpdate, ToolResponse
from app.utils.deps import get_current_user

router = APIRouter()


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
