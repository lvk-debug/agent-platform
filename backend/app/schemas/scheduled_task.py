"""
定时任务 / 推送设备 Schema

校验规则集中在这里，服务层只做业务校验（如 cron 表达式合法性）。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.scheduled_task import RunStatus, ScheduleType

# cron 表达式（标准 5 段：分 时 日 月 周）
CRON_FIELD_COUNT = 5
MAX_CRON_LEN = 100
MAX_PROMPT_LEN = 8000


class ScheduledTaskBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT_LEN)
    schedule_type: str = Field(ScheduleType.DAILY)
    cron_expr: str | None = Field(None, max_length=MAX_CRON_LEN)
    run_at: datetime | None = None
    timezone: str = Field("Asia/Shanghai", max_length=64)
    session_id: str | None = None
    app_id: str | None = None
    enabled: bool = True
    deliver_push: bool = True

    # daily / weekly 的友好入参，服务层据此生成 cron_expr
    # run_time: "HH:MM"；weekday: 0=周一 … 6=周日
    run_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weekday: int | None = Field(None, ge=0, le=6)

    @field_validator("schedule_type")
    @classmethod
    def check_schedule_type(cls, v: str) -> str:
        if v not in ScheduleType.ALL:
            raise ValueError(f"schedule_type 必须是 {ScheduleType.ALL} 之一")
        return v

    @model_validator(mode="after")
    def check_schedule_payload(self):
        if self.schedule_type == ScheduleType.CRON:
            if not self.cron_expr or not self.cron_expr.strip():
                raise ValueError("schedule_type=cron 时必须提供 cron_expr")
            parts = self.cron_expr.split()
            if len(parts) != CRON_FIELD_COUNT:
                raise ValueError(
                    "cron_expr 必须是 5 段标准 cron 表达式（分 时 日 月 周）"
                )
        elif self.schedule_type == ScheduleType.ONCE:
            if not self.run_at:
                raise ValueError("schedule_type=once 时必须提供 run_at")
        elif self.schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY):
            if not self.cron_expr and not self.run_time:
                raise ValueError(
                    f"schedule_type={self.schedule_type} 时"
                    "必须提供 run_time 或 cron_expr"
                )
            if self.schedule_type == ScheduleType.WEEKLY and not self.cron_expr:
                if self.weekday is None:
                    raise ValueError("schedule_type=weekly 时必须提供 weekday")
        return self


class ScheduledTaskCreate(ScheduledTaskBase):
    pass


class ScheduledTaskUpdate(BaseModel):
    """全量可选更新；未提供的字段保持不变"""

    name: str | None = Field(None, min_length=1, max_length=100)
    prompt: str | None = Field(None, min_length=1, max_length=MAX_PROMPT_LEN)
    schedule_type: str | None = None
    cron_expr: str | None = Field(None, max_length=MAX_CRON_LEN)
    run_at: datetime | None = None
    timezone: str | None = Field(None, max_length=64)
    session_id: str | None = None
    app_id: str | None = None
    enabled: bool | None = None
    deliver_push: bool | None = None
    run_time: str | None = Field(None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    weekday: int | None = Field(None, ge=0, le=6)

    @field_validator("schedule_type")
    @classmethod
    def check_schedule_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ScheduleType.ALL:
            raise ValueError(f"schedule_type 必须是 {ScheduleType.ALL} 之一")
        return v


class ScheduledTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: int
    session_id: str | None = None
    app_id: str | None = None
    name: str
    prompt: str
    schedule_type: str
    cron_expr: str | None = None
    run_at: datetime | None = None
    timezone: str
    enabled: bool
    deliver_push: bool
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_status: str | None = None
    last_error: str | None = None
    fail_count: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ScheduledTaskRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    task_id: str
    status: str
    summary: str | None = None
    error: str | None = None
    session_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int


class DeviceRegisterRequest(BaseModel):
    """移动端登记推送令牌"""

    token: str = Field(..., min_length=10, max_length=255)
    platform: str = Field("unknown", max_length=20)


class DeviceUnregisterRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=255)


class TaskRunNowResponse(ScheduledTaskRunResponse):
    """立即执行的返回，额外带回是否被跳过"""

    skipped: bool = False
    reason: str | None = None


__all__ = [
    "ScheduledTaskCreate",
    "ScheduledTaskUpdate",
    "ScheduledTaskResponse",
    "ScheduledTaskRunResponse",
    "DeviceRegisterRequest",
    "DeviceUnregisterRequest",
    "TaskRunNowResponse",
    "RunStatus",
    "ScheduleType",
]
