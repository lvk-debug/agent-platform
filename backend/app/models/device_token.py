"""
推送设备令牌

移动端登录后把 Expo Push Token 登记到这里，定时任务执行完成后据此下发通知。
同一 token 只保留一条（unique），跨用户重复登记时覆盖 user_id。
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DevicePushToken(Base):
    """移动端推送令牌"""

    __tablename__ = "device_push_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # ExpoPushToken[...]，长度约 40-60
    token = Column(String(255), nullable=False, unique=True, index=True)
    platform = Column(String(20), nullable=False, default="unknown")  # ios / android
    enabled = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<DevicePushToken(user={self.user_id}, platform={self.platform})>"
