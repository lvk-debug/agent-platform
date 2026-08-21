"""
工作流 API 端点
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.app import App
from app.schemas.workflow import (
    DSLData,
    DSLExportResponse,
    DSLImportRequest,
    WorkflowConfig,
    WorkflowRunRequest,
    WorkflowRunResponse,
)
from app.services.workflow import get_workflow_service
from app.utils.deps import get_current_user

router = APIRouter()


def _verify_app(db: Session, user: User, app_id: int) -> App:
    """验证应用存在且属于当前用户"""
    app = db.query(App).filter(
        App.id == app_id,
        App.owner_id == user.id,
    ).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    return app


# ------------------------------------------------------------------
# 配置管理
# ------------------------------------------------------------------

@router.get("/{app_id}/config", response_model=WorkflowConfig)
def get_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """获取工作流配置"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    config = service.get_workflow_config(app_id)
    if not config:
        return WorkflowConfig()
    return config


@router.put("/{app_id}/config", response_model=dict)
def update_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    config: WorkflowConfig,
) -> Any:
    """保存工作流配置"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    success = service.save_workflow_config(app_id, config)
    if not success:
        raise HTTPException(status_code=500, detail="保存配置失败")

    return {"message": "配置已保存"}


# ------------------------------------------------------------------
# 工作流执行
# ------------------------------------------------------------------

@router.post("/{app_id}/run", response_model=dict)
async def run_workflow(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    request: WorkflowRunRequest,
) -> Any:
    """执行工作流"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    try:
        result = await service.run_workflow(
            app_id=app_id,
            inputs=request.inputs,
            thread_id=request.thread_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {str(e)}")


# ------------------------------------------------------------------
# 运行记录
# ------------------------------------------------------------------

@router.get("/{app_id}/runs", response_model=List[WorkflowRunResponse])
def list_runs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    limit: int = 20,
) -> Any:
    """获取运行记录列表"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    runs = service.list_runs(app_id, limit=limit)
    return runs


@router.get("/{app_id}/runs/{run_id}", response_model=WorkflowRunResponse)
def get_run(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    run_id: int,
) -> Any:
    """获取单次运行详情"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    run = service.get_run(app_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return run


# ------------------------------------------------------------------
# DSL 导入导出
# ------------------------------------------------------------------

@router.post("/{app_id}/dsl/export", response_model=DSLExportResponse)
def export_dsl(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """导出 DSL"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    dsl = service.export_dsl(app_id)
    if not dsl:
        raise HTTPException(status_code=404, detail="工作流不存在")
    return DSLExportResponse(dsl=dsl)


@router.post("/{app_id}/dsl/import", response_model=dict)
def import_dsl(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    request: DSLImportRequest,
) -> Any:
    """导入 DSL"""
    _verify_app(db, current_user, app_id)

    service = get_workflow_service(db)
    success = service.import_dsl(app_id, request.dsl)
    if not success:
        raise HTTPException(status_code=500, detail="导入失败")

    return {"message": "DSL 已导入"}
