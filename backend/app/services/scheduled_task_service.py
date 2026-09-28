"""
定时任务服务层（CRUD + 调度同步）

职责：
1. 任务增删改查，强制用户隔离（越权一律 404，不暴露资源存在性）
2. 把 daily / weekly 的 run_time + weekday 归一化为 cron_expr 落库
3. 变更时同步 APScheduler 中的 job，并回写 next_run_at
"""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.scheduled_task import ScheduledTask, ScheduledTaskRun, ScheduleType
from app.services.schedule_utils import build_cron_expr, build_trigger
from app.utils.logger import logger


class ScheduledTaskService:
    def __init__(self, db: Session):
        self.db = db

    # ---------------- 查询 ----------------

    def list_tasks(self, user_id: int) -> list[ScheduledTask]:
        return (
            self.db.query(ScheduledTask)
            .filter(ScheduledTask.user_id == user_id)
            .order_by(ScheduledTask.created_at.desc())
            .all()
        )

    def get_task(self, task_id: str, user_id: int) -> ScheduledTask:
        task = (
            self.db.query(ScheduledTask)
            .filter(ScheduledTask.id == task_id, ScheduledTask.user_id == user_id)
            .first()
        )
        if not task:
            raise HTTPException(status_code=404, detail="定时任务不存在")
        return task

    def list_runs(
        self, task_id: str, user_id: int, limit: int = 20
    ) -> list[ScheduledTaskRun]:
        self.get_task(task_id, user_id)  # 校验归属
        return (
            self.db.query(ScheduledTaskRun)
            .filter(ScheduledTaskRun.task_id == task_id)
            .order_by(ScheduledTaskRun.started_at.desc())
            .limit(limit)
            .all()
        )

    # ---------------- 写入 ----------------

    def create_task(self, user_id: int, data) -> ScheduledTask:
        task = ScheduledTask(
            user_id=user_id,
            name=data.name,
            prompt=data.prompt,
            schedule_type=data.schedule_type,
            timezone=data.timezone,
            session_id=data.session_id,
            app_id=data.app_id,
            enabled=data.enabled,
            deliver_push=data.deliver_push,
            run_at=data.run_at,
        )
        task.cron_expr = build_cron_expr(
            schedule_type=data.schedule_type,
            cron_expr=data.cron_expr,
            run_time=getattr(data, "run_time", None),
            weekday=getattr(data, "weekday", None),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        self.sync_job(task)
        return task

    def update_task(self, task_id: str, user_id: int, data) -> ScheduledTask:
        task = self.get_task(task_id, user_id)

        for field in (
            "name",
            "prompt",
            "timezone",
            "session_id",
            "app_id",
            "enabled",
            "deliver_push",
            "run_at",
        ):
            value = getattr(data, field, None)
            if value is not None:
                setattr(task, field, value)

        if data.schedule_type is not None:
            task.schedule_type = data.schedule_type

        # 调度表达式：优先用显式 cron_expr，否则由 run_time/weekday 重新生成
        schedule_type = data.schedule_type or task.schedule_type
        if data.cron_expr is not None:
            task.cron_expr = data.cron_expr or None
        elif (
            getattr(data, "run_time", None) is not None
            or getattr(data, "weekday", None) is not None
        ):
            task.cron_expr = build_cron_expr(
                schedule_type=schedule_type,
                cron_expr=None,
                run_time=getattr(data, "run_time", None),
                weekday=getattr(data, "weekday", None),
            )

        self.db.commit()
        self.db.refresh(task)
        self.sync_job(task)
        return task

    def delete_task(self, task_id: str, user_id: int) -> None:
        task = self.get_task(task_id, user_id)
        self.remove_job(task.id)
        self.db.delete(task)
        self.db.commit()

    def set_enabled(self, task_id: str, user_id: int, enabled: bool) -> ScheduledTask:
        task = self.get_task(task_id, user_id)
        task.enabled = enabled
        if enabled:
            # 重新启用时清零失败计数，避免刚修复又被自动停用
            task.fail_count = 0
        self.db.commit()
        self.db.refresh(task)
        self.sync_job(task)
        return task

    # ---------------- 调度同步 ----------------

    def sync_job(self, task: ScheduledTask) -> None:
        """把任务同步到 APScheduler（未启用调度器时只算 next_run_at）"""
        from app.services.scheduler import get_scheduler, is_running

        trigger = build_trigger(
            schedule_type=task.schedule_type,
            timezone_name=task.timezone,
            cron_expr=task.cron_expr,
            run_at=task.run_at,
        )

        should_register = (
            task.enabled and trigger is not None and not _is_expired_once(task)
        )

        if is_running():
            scheduler = get_scheduler()
            if should_register:
                from app.services.scheduled_task_executor import execute_task

                scheduler.add_job(
                    func=execute_task,
                    trigger=trigger,
                    id=task.id,
                    args=[task.id],
                    replace_existing=True,
                    misfire_grace_time=None,  # 用 job_defaults
                )
            else:
                self.remove_job(task.id)

        task.next_run_at = (
            trigger.get_next_fire_time(None, datetime.now(UTC))
            if should_register and trigger
            else None
        )
        self.db.commit()

    def remove_job(self, task_id: str) -> None:
        from app.services.scheduler import get_scheduler, is_running

        if not is_running():
            return
        scheduler = get_scheduler()
        job = scheduler.get_job(task_id)
        if job:
            scheduler.remove_job(task_id)


def _is_expired_once(task: ScheduledTask) -> bool:
    """once 类型且执行时间已过，不再注册"""
    if task.schedule_type != ScheduleType.ONCE or not task.run_at:
        return False
    run_at = (
        task.run_at if task.run_at.tzinfo else task.run_at.replace(tzinfo=UTC)
    )
    return run_at <= datetime.now(UTC)


def get_scheduled_task_service(db: Session) -> ScheduledTaskService:
    return ScheduledTaskService(db)


def bootstrap_scheduled_jobs() -> int:
    """
    进程启动时把数据库中已启用的任务重新注册到调度器

    :return: 成功注册的任务数
    """
    from app.services.scheduler import is_running

    if not is_running():
        return 0

    db: Session = SessionLocal()
    try:
        tasks = (
            db.query(ScheduledTask)
            .filter(ScheduledTask.enabled == True)  # noqa: E712
            .all()
        )
        service = ScheduledTaskService(db)
        count = 0
        for task in tasks:
            try:
                service.sync_job(task)
                if task.next_run_at:
                    count += 1
            except Exception as e:  # noqa: BLE001
                logger.error(f"注册定时任务失败: task={task.id}, error={e}")
        return count
    finally:
        db.close()


__all__ = [
    "ScheduledTaskService",
    "get_scheduled_task_service",
    "bootstrap_scheduled_jobs",
]
