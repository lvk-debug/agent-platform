"""
定时任务端点

路由前缀 /api/v1/scheduled-tasks

与现有 /hermes/jobs 的区别：jobs 是代理上游 Hermes 网关的计划任务（不落本地库），
这里管理的是平台自建、由 APScheduler 调度并落库的任务。
"""

import threading
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.scheduled_task import (
    ScheduledTaskCreate,
    ScheduledTaskResponse,
    ScheduledTaskRunResponse,
    ScheduledTaskUpdate,
)
from app.services.scheduled_task_executor import execute_task
from app.services.scheduled_task_service import get_scheduled_task_service
from app.utils.deps import get_current_user
from app.utils.logger import logger

router = APIRouter()


@router.get("", response_model=list[ScheduledTaskResponse], summary="我的定时任务列表")
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    return service.list_tasks(current_user.id)


@router.post("", response_model=ScheduledTaskResponse, summary="创建定时任务")
def create_task(
    data: ScheduledTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    try:
        return service.create_task(current_user.id, data)
    except HTTPException:
        raise
    except ValueError as e:
        # cron 表达式非法等校验错误
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        logger.error(f"创建定时任务失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="创建定时任务失败")


@router.get("/{task_id}", response_model=ScheduledTaskResponse, summary="任务详情")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    return service.get_task(task_id, current_user.id)


@router.put("/{task_id}", response_model=ScheduledTaskResponse, summary="更新定时任务")
def update_task(
    task_id: str,
    data: ScheduledTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    try:
        return service.update_task(task_id, current_user.id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{task_id}", summary="删除定时任务")
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    service.delete_task(task_id, current_user.id)
    return {"message": "已删除"}


@router.post(
    "/{task_id}/enable", response_model=ScheduledTaskResponse, summary="启用任务"
)
def enable_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    return service.set_enabled(task_id, current_user.id, True)


@router.post(
    "/{task_id}/disable", response_model=ScheduledTaskResponse, summary="停用任务"
)
def disable_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    return service.set_enabled(task_id, current_user.id, False)


@router.post("/{task_id}/run", summary="立即执行一次（后台异步）")
def run_task_now(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    立即触发一次执行。

    执行在后台线程进行（LLM 生成可能耗时数十秒），接口立即返回 202；
    客户端应轮询任务列表或执行历史获取结果。
    """
    service = get_scheduled_task_service(db)
    task = service.get_task(task_id, current_user.id)

    # 轻量预检：锁仍存活说明上一轮还没跑完（真正的互斥由执行器 CAS 保证）
    if _is_locked(db, task):
        return {
            "status": "skipped",
            "task_id": task_id,
            "reason": "任务正在执行中，请稍后再试",
        }

    if not execute_task_async(task_id):
        raise HTTPException(status_code=500, detail="无法启动执行线程")

    return {"status": "accepted", "task_id": task_id}


def _is_locked(db: Session, task) -> bool:
    """判断任务的锁是否仍处于有效期内"""
    from datetime import datetime, timedelta

    if not task.locked_at:
        return False
    locked_at = (
        task.locked_at
        if task.locked_at.tzinfo
        else task.locked_at.replace(tzinfo=UTC)
    )
    timeout = timedelta(seconds=settings.SCHEDULER_LOCK_TIMEOUT_SECONDS)
    return datetime.now(UTC) - locked_at < timeout


@router.get(
    "/{task_id}/runs",
    response_model=list[ScheduledTaskRunResponse],
    summary="任务执行历史",
)
def list_runs(
    task_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_scheduled_task_service(db)
    return service.list_runs(task_id, current_user.id, limit)


def execute_task_async(task_id: str) -> bool:
    """在后台线程执行任务；返回是否成功启动"""
    try:
        thread = threading.Thread(
            target=_safe_execute,
            args=(task_id,),
            name=f"scheduled-task-{task_id[:8]}",
            daemon=True,
        )
        thread.start()
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"启动任务线程失败: {e}")
        return False


def _safe_execute(task_id: str) -> None:
    """线程入口：兜底捕获异常，避免线程静默崩溃"""
    try:
        execute_task(task_id, force=True)
    except Exception as e:  # noqa: BLE001
        logger.error(f"立即执行任务异常: task={task_id}, error={e}", exc_info=True)
