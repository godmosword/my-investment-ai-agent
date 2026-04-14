"""
In-process Web Push subscription buffer（開發／staging 用）。

- 預設關閉：`WEB_PUSH_ENABLED=0` 時 API 仍回 501。
- `WEB_PUSH_ENABLED=1` 且未設 `WEB_PUSH_STORE=1`：僅驗證 payload 並 log（不落庫）。
- `WEB_PUSH_ENABLED=1` 且 `WEB_PUSH_STORE=1`：寫入本 process 記憶體（**重啟即失**；非生產持久化）。

生產若要真推送，仍須 VAPID、持久化與 rate limit（見 `docs/PWA_WEB_PUSH.md`）。
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from collections import deque
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_BUFFER: deque[dict[str, Any]] = deque(maxlen=256)


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


def web_push_enabled() -> bool:
    return _truthy("WEB_PUSH_ENABLED")


def web_push_store_enabled() -> bool:
    return web_push_enabled() and _truthy("WEB_PUSH_STORE")


def record_subscription(body: dict[str, Any]) -> dict[str, Any]:
    """回傳 { stored, count, endpoint_fp }；stored=False 時僅 log。"""
    endpoint = str(body.get("endpoint") or "")
    fp = hashlib.sha256(endpoint.encode("utf-8", errors="replace")).hexdigest()[:16] if endpoint else ""
    keys = body.get("keys")
    if not isinstance(keys, dict):
        keys = None

    if web_push_store_enabled():
        row = {"endpoint_fp": fp, "has_p256dh": bool(keys and keys.get("p256dh")), "has_auth": bool(keys and keys.get("auth"))}
        with _LOCK:
            _BUFFER.append(row)
            n = len(_BUFFER)
        logger.info("Web Push subscription stored in-memory (fp=%s, buffer=%d)", fp, n)
        return {"stored": True, "count": n, "endpoint_fp": fp}

    logger.info(
        "Web Push subscribe received (log-only, fp=%s); set WEB_PUSH_STORE=1 for in-memory buffer",
        fp or "empty",
    )
    return {"stored": False, "count": 0, "endpoint_fp": fp}


def subscription_count() -> int:
    with _LOCK:
        return len(_BUFFER)


def clear_subscriptions_for_tests() -> None:
    """測試用：清空程序內訂閱 buffer。"""
    with _LOCK:
        _BUFFER.clear()
