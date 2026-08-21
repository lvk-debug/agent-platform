from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class PublishConfig(Base):
    """
    发布配置模型
    存储每个应用在不同渠道的发布配置
    """

    __tablename__ = "publish_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    app_id = Column(
        Integer,
        ForeignKey("apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = Column(
        Enum("api", "mcp", "embed", "wechat", "h5", name="publish_channel_enum"),
        nullable=False,
    )
    enabled = Column(Boolean, default=False, nullable=False)
    # 渠道特定配置（JSON），如 API key、webhook URL 等
    config = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # 关系
    app = relationship("App", backref="publish_configs")
