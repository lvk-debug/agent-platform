"""
Expo Push 推送下发

直接调用 Expo 官方 HTTP 接口（https://exp.host/--/api/v2/push/send），
不引入第三方 SDK。

约定：
- 推送失败**不允许**让定时任务失败，只记 warning 日志
- 日志中不输出设备令牌
"""

from typing import Any

import httpx

from app.core.config import settings
from app.utils.logger import logger

EXPO_PUSH_ENDPOINT = settings.EXPO_PUSH_API_URL
EXPO_TIMEOUT = 10.0
# Expo 单批最多 100 条
BATCH_SIZE = 100


def is_valid_expo_token(token: str | None) -> bool:
    """Expo Push Token 形如 ExponentPushToken[xxxx] / ExpoPushToken[xxxx]"""
    if not token:
        return False
    return token.startswith("ExponentPushToken[") or token.startswith("ExpoPushToken[")


def get_user_tokens(db, user_id: int) -> list[str]:
    """取用户已登记的推送令牌"""
    from app.models.device_token import DevicePushToken

    rows = (
        db.query(DevicePushToken)
        .filter(
            DevicePushToken.user_id == user_id,
            DevicePushToken.enabled == True,  # noqa: E712
        )
        .all()
    )
    return [r.token for r in rows if is_valid_expo_token(r.token)]


def _build_message(
    token: str, title: str, body: str, data: dict[str, Any] | None
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "to": token,
        "sound": "default",
        "title": title,
        "body": body[:200],
        "data": data or {},
    }
    # Android 渠道（与移动端 setNotificationChannelAsync 对应）
    message["channelId"] = settings.EXPO_PUSH_CHANNEL
    return message


def send_push(
    db,
    user_id: int,
    title: str,
    body: str,
    data: dict[str, Any] | None = None,
) -> int:
    """
    向用户的所有设备推送通知

    :return: 成功下发的消息条数（0 表示无设备或全部失败）
    """
    if not settings.EXPO_PUSH_ENABLED:
        return 0

    tokens = get_user_tokens(db, user_id)
    if not tokens:
        logger.debug(f"用户 {user_id} 无可用推送令牌，跳过下发")
        return 0

    sent = 0
    try:
        with httpx.Client(timeout=EXPO_TIMEOUT) as client:
            for i in range(0, len(tokens), BATCH_SIZE):
                batch = tokens[i : i + BATCH_SIZE]
                payload = [_build_message(t, title, body, data) for t in batch]
                resp = client.post(
                    EXPO_PUSH_ENDPOINT,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        # 有 access token 时带上，可提高配额
                        **(
                            {"Authorization": f"Bearer {settings.EXPO_ACCESS_TOKEN}"}
                            if settings.EXPO_ACCESS_TOKEN
                            else {}
                        ),
                    },
                )
                if resp.status_code >= 400:
                    logger.warning(
                        f"推送下发失败: HTTP {resp.status_code}（设备数={len(batch)}）"
                    )
                    continue
                # Expo 返回逐条 ticket，失败项在 data 里带 status=error
                try:
                    tickets = resp.json().get("data", [])
                    sent += sum(
                        1
                        for t in tickets
                        if isinstance(t, dict) and t.get("status") == "ok"
                    )
                except Exception:  # noqa: BLE001
                    sent += len(batch)
    except httpx.HTTPError as e:
        logger.warning(f"推送请求异常（不影响任务结果）: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"推送下发异常（不影响任务结果）: {e}")

    if tokens:
        logger.info(
            f"定时任务推送完成: 用户={user_id}, 设备数={len(tokens)}, 成功={sent}"
        )
    return sent
