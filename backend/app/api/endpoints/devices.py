"""
推送设备端点

路由前缀 /api/v1/devices

移动端登录后登记 Expo Push Token，定时任务执行完成后据此下发通知。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.device_token import DevicePushToken
from app.models.user import User
from app.schemas.scheduled_task import DeviceRegisterRequest, DeviceUnregisterRequest
from app.utils.deps import get_current_user

router = APIRouter()


@router.post("/register", summary="登记推送令牌")
def register_device(
    data: DeviceRegisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    登记（或重新绑定）当前设备的推送令牌。

    token 唯一：同一台设备重复登记只更新 user_id / platform / enabled，
    避免用户换账号登录后把通知推给上一个账号。
    """
    row = db.query(DevicePushToken).filter(DevicePushToken.token == data.token).first()
    if row:
        row.user_id = current_user.id
        row.platform = data.platform
        row.enabled = True
    else:
        row = DevicePushToken(
            user_id=current_user.id,
            token=data.token,
            platform=data.platform,
            enabled=True,
        )
        db.add(row)
    db.commit()
    return {"message": "已登记", "platform": data.platform}


@router.post("/unregister", summary="解绑推送令牌（登出时调用）")
def unregister_device(
    data: DeviceUnregisterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = (
        db.query(DevicePushToken)
        .filter(
            DevicePushToken.token == data.token,
            DevicePushToken.user_id == current_user.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"message": "已解绑", "removed": deleted}
