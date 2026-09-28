"""
定时任务执行器

被 APScheduler 线程池调用（同步上下文），也可被「立即执行」接口直接调用。

可靠性设计：
1. **CAS 乐观锁**：执行前把 locked_at 从「空/已过期」改为当前时间，
   只有一个进程能改成功（UPDATE 的 rowcount==1），避免多 worker 重复执行。
2. **独立 DB Session**：不复用请求会话，执行完立即关闭。
3. **推送失败不影响任务状态**：仅记 warning。
4. **连续失败自动禁用**：超过 SCHEDULER_MAX_FAILURES 次后关闭任务并记错误。
"""

import json
from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.hermes import HermesSession
from app.models.scheduled_task import (
    RunStatus,
    ScheduledTask,
    ScheduledTaskRun,
    ScheduleType,
)
from app.services.schedule_utils import compute_next_run
from app.utils.logger import logger

SUMMARY_MAX_CHARS = 500


def _now() -> datetime:
    return datetime.now(UTC)


def _try_lock(db: Session, task: ScheduledTask) -> bool:
    """
    尝试获取执行锁（CAS）

    只把 locked_at 为空或已超过锁超时的记录改为当前时间，
    返回是否抢到锁。
    """
    stale_before = _now() - timedelta(seconds=settings.SCHEDULER_LOCK_TIMEOUT_SECONDS)
    # 只校验锁，不校验 enabled：「立即执行」允许对停用任务手动触发
    updated = (
        db.query(ScheduledTask)
        .filter(
            ScheduledTask.id == task.id,
            (ScheduledTask.locked_at.is_(None))
            | (ScheduledTask.locked_at < stale_before),
        )
        .update({ScheduledTask.locked_at: _now()}, synchronize_session=False)
    )
    db.commit()
    return updated == 1


def _release_lock(db: Session, task_id: str) -> None:
    db.query(ScheduledTask).filter(ScheduledTask.id == task_id).update(
        {ScheduledTask.locked_at: None}, synchronize_session=False
    )
    db.commit()


def _parse_sse(generator: Generator[str, None, None]) -> tuple[str, str | None]:
    """
    消费 Hermes 的 SSE 生成器，收集正文与错误

    SSE 帧格式（由 services/hermes.py::_sse_event 产出）：
        event: content_delta\\ndata: {"content": "..."}\\n\\n
    """
    chunks: list[str] = []
    error: str | None = None

    for raw in generator:
        for frame in (raw or "").split("\n\n"):
            if not frame.strip():
                continue
            event_name: str | None = None
            data_str: str | None = None
            for line in frame.splitlines():
                if line.startswith("event:"):
                    event_name = line[len("event:") :].strip()
                elif line.startswith("data:"):
                    data_str = line[len("data:") :].strip()

            if not data_str:
                continue
            try:
                payload = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            if event_name == "content_delta":
                chunks.append(str(payload.get("content") or ""))
            elif event_name == "error":
                error = str(payload.get("message") or "未知错误")

    return "".join(chunks), error


def _resolve_session(db: Session, task: ScheduledTask) -> HermesSession | None:
    """取（必要时创建）任务要写入的会话"""
    if task.session_id:
        session = (
            db.query(HermesSession).filter(HermesSession.id == task.session_id).first()
        )
        if session:
            return session

    session = HermesSession(
        user_id=task.user_id,
        title=f"定时任务 · {task.name}"[:255],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    task.session_id = session.id
    db.commit()
    return session


def _run_prompt(
    db: Session, task: ScheduledTask, session: HermesSession
) -> tuple[str, str | None]:
    """调用 Hermes 执行提示词，返回（正文, 错误）"""
    from app.services.hermes import get_hermes_service

    service = get_hermes_service(db)
    generator = service.chat_stream(
        session_id=session.id,
        user_message=task.prompt,
    )
    return _parse_sse(generator)


def execute_task(task_id: str, force: bool = False) -> bool:
    """
    执行一次任务

    :param force: True 表示「立即执行」，跳过 enabled 检查
    :return: 是否真正执行（False 表示任务不存在/未启用/未抢到锁）
    """
    db: Session = SessionLocal()
    try:
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            logger.warning(f"定时任务不存在，跳过执行: {task_id}")
            return False

        if not task.enabled and not force:
            return False

        # CAS 加锁：定时触发与「立即执行」共用，避免同一任务并发跑
        if not _try_lock(db, task):
            logger.info(f"任务 {task_id} 正在执行中（锁未释放），跳过本次触发")
            return False

        started = _now()
        run = ScheduledTaskRun(
            task_id=task.id,
            status=RunStatus.RUNNING,
            session_id=task.session_id,
            started_at=started,
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        content = ""
        error: str | None = None
        try:
            session = _resolve_session(db, task)
            run.session_id = session.id
            db.commit()

            content, error = _run_prompt(db, task, session)
        except Exception as e:  # noqa: BLE001
            error = str(e)
            logger.error(f"定时任务执行异常: task={task_id}, error={e}", exc_info=True)
        finally:
            finished = _now()
            duration_ms = int((finished - started).total_seconds() * 1000)

            status = RunStatus.FAILED if error else RunStatus.SUCCESS
            run.status = status
            run.summary = (content or "")[:SUMMARY_MAX_CHARS]
            run.error = error
            run.finished_at = finished
            run.duration_ms = duration_ms

            task.last_run_at = started
            task.last_status = status
            task.last_error = error
            task.fail_count = (task.fail_count or 0) + 1 if error else 0

            # 单次任务执行后自动禁用，其余类型计算下次时间
            if task.schedule_type == ScheduleType.ONCE:
                task.enabled = False
                task.next_run_at = None
            else:
                task.next_run_at = compute_next_run(
                    schedule_type=task.schedule_type,
                    timezone_name=task.timezone,
                    cron_expr=task.cron_expr,
                    run_at=task.run_at,
                    previous_fire=started,
                )

            # 连续失败过多自动停用，避免持续报错
            if (
                error
                and settings.SCHEDULER_MAX_FAILURES > 0
                and task.fail_count >= settings.SCHEDULER_MAX_FAILURES
            ):
                task.enabled = False
                task.last_error = (
                    f"连续失败 {task.fail_count} 次，已自动停用。{error or ''}"
                )
                logger.warning(
                    f"定时任务 {task_id} 连续失败 {task.fail_count} 次，已自动停用"
                )

            db.commit()
            _release_lock(db, task.id)

        # 推送结果（失败不影响任务状态）
        if task.deliver_push:
            try:
                from app.services.push import send_push

                title = f"定时任务完成 · {task.name}"
                body = (content or error or "任务执行完成")[:200]
                send_push(
                    db,
                    task.user_id,
                    title,
                    body,
                    data={
                        "taskId": task.id,
                        "runId": run.id,
                        "sessionId": run.session_id or "",
                        "screen": "ScheduledTaskList",
                    },
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"定时任务推送失败（不影响结果）: {e}")

        logger.info(
            f"定时任务执行完成: task={task_id}, status={run.status}, "
            f"duration={run.duration_ms}ms"
        )
        return True
    finally:
        db.close()
