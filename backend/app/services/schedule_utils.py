"""
调度表达式工具

独立模块：服务层与执行器都要用，避免二者互相导入形成循环。
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from app.models.scheduled_task import ScheduleType

DEFAULT_TIMEZONE = "Asia/Shanghai"


def get_timezone(name: str | None) -> ZoneInfo:
    """解析时区，失败回退到 Asia/Shanghai"""
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except Exception:  # noqa: BLE001
        return ZoneInfo(DEFAULT_TIMEZONE)


def build_cron_expr(
    schedule_type: str,
    cron_expr: str | None = None,
    run_time: str | None = None,
    weekday: int | None = None,
) -> str | None:
    """
    归一化为 5 段 crontab 表达式

    - cron: 直接用 cron_expr
    - daily: run_time "HH:MM" -> "M H * * *"
    - weekly: run_time + weekday（0=周一 … 6=周日）-> "M H * * D"
    """
    if schedule_type == ScheduleType.CRON:
        return (cron_expr or "").strip() or None

    if schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY):
        if cron_expr and cron_expr.strip():
            return cron_expr.strip()
        if not run_time:
            return None
        try:
            hour, minute = (int(x) for x in run_time.split(":"))
        except (ValueError, AttributeError):
            return None
        if schedule_type == ScheduleType.DAILY:
            return f"{minute} {hour} * * *"
        if weekday is None:
            return None
        # Python: 周一=0 … 周日=6  ->  crontab: 周日=0, 周一=1 … 周六=6
        dow = (weekday + 1) % 7
        return f"{minute} {hour} * * {dow}"

    return None


def build_trigger(
    schedule_type: str,
    timezone_name: str | None,
    cron_expr: str | None = None,
    run_at: datetime | None = None,
) -> BaseTrigger | None:
    """构造 APScheduler 触发器；表达式非法时返回 None"""
    tz = get_timezone(timezone_name)

    if schedule_type == ScheduleType.ONCE:
        if not run_at:
            return None
        run_date = run_at if run_at.tzinfo else run_at.replace(tzinfo=tz)
        return DateTrigger(run_date=run_date, timezone=tz)

    cron = build_cron_expr(schedule_type, cron_expr)
    if not cron:
        return None
    try:
        return CronTrigger.from_crontab(cron, timezone=tz)
    except ValueError:
        return None


def compute_next_run(
    schedule_type: str,
    timezone_name: str | None,
    cron_expr: str | None = None,
    run_at: datetime | None = None,
    previous_fire: datetime | None = None,
    now: datetime | None = None,
) -> datetime | None:
    """计算下一次执行时间（UTC）"""
    trigger = build_trigger(schedule_type, timezone_name, cron_expr, run_at)
    if not trigger:
        return None
    reference = now or datetime.now(get_timezone(timezone_name))
    return trigger.get_next_fire_time(previous_fire, reference)
