"""
In-process Web Push subscription buffer（開發／staging 用）。

- 預設關閉：`WEB_PUSH_ENABLED=0` 時 API 仍回 501。
- `WEB_PUSH_ENABLED=1` 且未設 `WEB_PUSH_STORE=1`：僅驗證 payload 並 log（不落庫）。
- `WEB_PUSH_ENABLED=1` 且 `WEB_PUSH_STORE=1`：寫入本 process 記憶體（**重啟即失**；非生產持久化）。
  同一 endpoint 以 **SHA256 fingerprint** 去重（更新時間戳）；可選 **`WEB_PUSH_SUBSCRIBE_RATE_PER_MIN`** 限制每 IP 每分鐘 POST 次數。

生產若要真推送，仍須 VAPID、持久化與完整 rate limit（見 `docs/PWA_WEB_PUSH.md`）。
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
# endpoint_fp -> { "updated_at": unix_ts, "has_p256dh": bool, "has_auth": bool, "last_ip": str }
_BY_FP: dict[str, dict[str, Any]] = {}
# client_ip -> list of unix timestamps (last minute) for cheap rate limit
_IP_HITS: dict[str, list[float]] = {}


def _truthy(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes")


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def web_push_enabled() -> bool:
    return _truthy("WEB_PUSH_ENABLED")


def web_push_store_enabled() -> bool:
    return web_push_enabled() and _truthy("WEB_PUSH_STORE")


def _endpoint_fp(endpoint: str) -> str:
    if not endpoint:
        return ""
    return hashlib.sha256(endpoint.encode("utf-8", errors="replace")).hexdigest()[:16]


def _prune_ip_hits(now: float) -> None:
    cutoff = now - 60.0
    for ip, hits in list(_IP_HITS.items()):
        fresh = [t for t in hits if t >= cutoff]
        if fresh:
            _IP_HITS[ip] = fresh
        else:
            _IP_HITS.pop(ip, None)


def _rate_limited(client_ip: str) -> bool:
    limit = _int_env("WEB_PUSH_SUBSCRIBE_RATE_PER_MIN", 30)
    if limit <= 0:
        return False
    now = time.time()
    with _LOCK:
        _prune_ip_hits(now)
        hits = _IP_HITS.get(client_ip, [])
        if len(hits) >= limit:
            return True
        hits.append(now)
        _IP_HITS[client_ip] = hits
    return False


def _trim_store_if_needed() -> None:
    max_n = _int_env("WEB_PUSH_STORE_MAX_SUBSCRIPTIONS", 512)
    if max_n <= 0 or len(_BY_FP) <= max_n:
        return
    # drop oldest by updated_at
    items = sorted(_BY_FP.items(), key=lambda kv: float(kv[1].get("updated_at") or 0))
    for fp, _ in items[: max(1, len(_BY_FP) - max_n)]:
        _BY_FP.pop(fp, None)


def record_subscription(body: dict[str, Any], *, client_ip: str = "") -> dict[str, Any]:
    """回傳 { stored, count, endpoint_fp, deduped?, rate_limited? }；stored=False 時僅 log。"""
    endpoint = str(body.get("endpoint") or "")
    fp = _endpoint_fp(endpoint)
    keys = body.get("keys")
    if not isinstance(keys, dict):
        keys = None

    ip = (client_ip or "unknown").strip() or "unknown"
    if web_push_store_enabled() and _rate_limited(ip):
        logger.warning("Web Push subscribe rate-limited (ip=%s)", ip)
        return {"stored": False, "count": len(_BY_FP), "endpoint_fp": fp, "rate_limited": True}

    if web_push_store_enabled():
        row = {
            "has_p256dh": bool(keys and keys.get("p256dh")),
            "has_auth": bool(keys and keys.get("auth")),
            "last_ip": ip,
            "updated_at": time.time(),
        }
        deduped = False
        with _LOCK:
            if fp and fp in _BY_FP:
                deduped = True
            if fp:
                _BY_FP[fp] = {**(_BY_FP.get(fp) or {}), **row}
            _trim_store_if_needed()
            n = len(_BY_FP)
        logger.info(
            "Web Push subscription stored in-memory (fp=%s, count=%d, deduped=%s)",
            fp or "empty",
            n,
            deduped,
        )
        return {"stored": True, "count": n, "endpoint_fp": fp, "deduped": deduped}

    logger.info(
        "Web Push subscribe received (log-only, fp=%s); set WEB_PUSH_STORE=1 for in-memory buffer",
        fp or "empty",
    )
    return {"stored": False, "count": 0, "endpoint_fp": fp}


def subscription_count() -> int:
    with _LOCK:
        return len(_BY_FP)


def clear_subscriptions_for_tests() -> None:
    """測試用：清空程序內訂閱 buffer。"""
    with _LOCK:
        _BY_FP.clear()
        _IP_HITS.clear()
