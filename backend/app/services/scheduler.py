"""
APScheduler 单例

部署形态（二选一，避免重复触发）：
1. 单 API worker 内置调度器：SCHEDULER_ENABLED=true（默认，开发环境）
2. 独立调度进程 + 多个 API worker：仅调度进程开 SCHEDULER_ENABLED，其余关闭

即使多进程同时开启，执行器也用数据库 CAS 乐观锁兜底（见 ScheduledTask.locked_at），
保证同一时刻只有一个进程真正执行。

Job 存内存（MemoryJobStore）：进程启动时由 scheduled_task_service.bootstrap_jobs()
从数据库重新注册，无需维护额外的 APScheduler 表。
"""

import atexit
import threading
from collections.abc import Callable

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import settings
from app.utils.logger import logger

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def get_scheduler() -> BackgroundScheduler:
    """获取（必要时创建）全局调度器实例"""
    global _scheduler
    with _lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler(
                jobstores={"default": MemoryJobStore()},
                executors={
                    "default": ThreadPoolExecutor(
                        max_workers=settings.SCHEDULER_MAX_WORKERS
                    )
                },
                job_defaults={
                    "coalesce": True,  # 错过的多次触发合并为一次
                    "max_instances": 1,  # 同一任务不并发
                    "misfire_grace_time": settings.SCHEDULER_MISFIRE_GRACE_SECONDS,
                },
                timezone=settings.SCHEDULER_TIMEZONE,
            )
            logger.info(
                f"调度器已创建（workers={settings.SCHEDULER_MAX_WORKERS}, "
                f"tz={settings.SCHEDULER_TIMEZONE}）"
            )
        return _scheduler


def start_scheduler(bootstrap: Callable[[], int] | None = None) -> None:
    """
    启动调度器

    :param bootstrap: 注册数据库中已启用任务的回调，返回注册数量
    """
    if not settings.SCHEDULER_ENABLED:
        logger.info("SCHEDULER_ENABLED=false，未启动调度器")
        return

    sched = get_scheduler()
    if sched.running:
        logger.warning("调度器已在运行，跳过重复启动")
        return

    sched.start()
    atexit.register(lambda: shutdown_scheduler())

    count = 0
    if bootstrap:
        try:
            count = bootstrap()
        except Exception as e:  # noqa: BLE001
            logger.error(f"加载定时任务失败: {e}", exc_info=True)
    logger.info(f"调度器已启动，已注册 {count} 个定时任务")


def shutdown_scheduler() -> None:
    """优雅关闭：不等待正在执行的任务（wait=False），避免阻塞进程退出"""
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            logger.info("调度器已关闭")
        _scheduler = None


def is_running() -> bool:
    sched = _scheduler
    return bool(sched and sched.running)
