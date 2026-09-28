"""
Hermes 上游数据缓存

用途：
1. 缓存 /v1/capabilities、/v1/models、/health/detailed 等低频变动数据
2. 支持 stale-while-error：上游故障时返回上一次成功结果，避免面板整体不可用

实现为进程内 TTL 缓存（dict + 过期时间戳），不引入第三方依赖，
多实例部署时每份缓存互不影响，语义上可接受（数据均为只读展示）。
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings


@dataclass
class _CacheEntry:
    """缓存条目：值 + 过期时间戳"""

    value: Any
    expires_at: float


# 缓存存储（key -> entry）
_store: Dict[str, _CacheEntry] = {}
_lock = threading.Lock()

# 缓存键
KEY_CAPABILITIES = "hermes:capabilities"
KEY_MODELS = "hermes:models"
KEY_HEALTH_DETAIL = "hermes:health_detail"


def default_ttl() -> int:
    """默认缓存时长（秒），<=0 表示不缓存"""
    return max(int(getattr(settings, "HERMES_CAPABILITY_CACHE_TTL", 60) or 0), 0)


def get_fresh(key: str) -> Tuple[bool, Any]:
    """
    读取未过期的缓存

    Returns:
        (是否命中新鲜数据, 缓存值)
    """
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return False, None
        if entry.expires_at < time.time():
            return False, None
        return True, entry.value


def get_stale(key: str) -> Optional[Any]:
    """读取缓存（允许过期），用于上游故障时的降级展示"""
    with _lock:
        entry = _store.get(key)
        return entry.value if entry is not None else None


def set_value(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """写入缓存；ttl 为空则使用默认时长，<=0 时不写入"""
    seconds = default_ttl() if ttl is None else ttl
    if seconds <= 0:
        return
    with _lock:
        _store[key] = _CacheEntry(value=value, expires_at=time.time() + seconds)


def invalidate(key: Optional[str] = None) -> None:
    """清除指定 key 或全部缓存"""
    with _lock:
        if key is None:
            _store.clear()
        else:
            _store.pop(key, None)
