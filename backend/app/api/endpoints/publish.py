from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.publish import (
    PublishConfigListResponse,
    PublishConfigResponse,
    PublishConfigUpdate,
)
from app.services.publish import get_publish_service
from app.utils.deps import get_current_user

router = APIRouter()


def _verify_app(db: Session, user: User, app_id: int):
    """验证应用存在且属于当前用户"""
    from app.models.app import App

    app = db.query(App).filter(App.id == app_id, App.owner_id == user.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="应用不存在")
    return app


@router.get("/", response_model=PublishConfigListResponse)
def get_all_configs(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
) -> Any:
    """获取应用所有发布渠道配置"""
    app = _verify_app(db, current_user, app_id)
    service = get_publish_service(db)
    configs = service.get_all_configs(app_id)
    return PublishConfigListResponse(
        app_id=app.id,
        app_name=app.name,
        configs=configs,
    )


@router.get("/{channel}", response_model=PublishConfigResponse)
def get_channel_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    channel: str,
) -> Any:
    """获取单个渠道配置"""
    _verify_app(db, current_user, app_id)
    service = get_publish_service(db)
    config = service.get_config(app_id, channel)
    if not config:
        raise HTTPException(status_code=404, detail="渠道配置不存在")
    return config


@router.put("/{channel}", response_model=PublishConfigResponse)
def update_channel_config(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    channel: str,
    data: PublishConfigUpdate,
) -> Any:
    """更新渠道配置"""
    _verify_app(db, current_user, app_id)
    service = get_publish_service(db)
    config = service.update_config(app_id, channel, data.model_dump(exclude_unset=True))
    if not config:
        raise HTTPException(status_code=404, detail="更新失败")
    return config


@router.post("/{channel}/enable", response_model=PublishConfigResponse)
def enable_channel(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    channel: str,
) -> Any:
    """启用发布渠道"""
    _verify_app(db, current_user, app_id)
    service = get_publish_service(db)
    config = service.enable_channel(app_id, channel)
    if not config:
        raise HTTPException(status_code=404, detail="启用失败")
    return config


@router.post("/{channel}/disable", response_model=PublishConfigResponse)
def disable_channel(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    app_id: int,
    channel: str,
) -> Any:
    """禁用发布渠道"""
    _verify_app(db, current_user, app_id)
    service = get_publish_service(db)
    config = service.disable_channel(app_id, channel)
    if not config:
        raise HTTPException(status_code=404, detail="禁用失败")
    return config
