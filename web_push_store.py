"""
Web Push：log-only、程序內、**Redis** 或 **BigQuery** 稽核／持久化（T4a）。

- ``WEB_PUSH_ENABLED=1`` + ``WEB_PUSH_REDIS_URL``：訂閱寫入 Redis **HASH**（field=endpoint fingerprint）；可搭配 **Redis INCR** 做分散式 rate limit；內容預設為 **完整** ``endpoint``+``keys`` JSON（供 ``pywebpush``）。
- ``WEB_PUSH_ENABLED=1`` + ``WEB_PUSH_STORE=1``：程序內 dict（可選 ``WEB_PUSH_STORE_FULL_SUBSCRIPTION=1`` 存完整 JSON）。
- ``WEB_PUSH_BQ_PERSIST`` / ``WEB_PUSH_BQ_AUDIT``：可選寫入 BQ（表結構見 ``docs/SQL/web_push_subscriptions.sql``）。

環境變數見 ``ENV_TEMPLATE.txt`` 與 ``docs/PWA_WEB_PUSH.md``。
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()
_BY_FP: dict[str, dict[str, Any]] = {}
_IP_HITS: dict[str, list[float]] = {}
_redis_client: Any = None  # lazy: Redis client or False if unavailable


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


def _endpoint_fp(endpoint: str) -> str:
    if not endpoint:
        return ""
    return hashlib.sha256(endpoint.encode("utf-8", errors="replace")).hexdigest()[:16]


def _redis_url() -> str:
    return (os.getenv("WEB_PUSH_REDIS_URL") or "").strip()


def _get_redis():
    """Lazy Redis；失敗時設 sentinel ``False`` 避免重試風暴。"""
    global _redis_client
    if _redis_client is False:
        return None
    if _redis_client is not None:
        return _redis_client
    url = _redis_url()
    if not url:
        return None
    try:
        import redis as redis_lib

        r = redis_lib.from_url(url, decode_responses=True)
        r.ping()
        _redis_client = r
        logger.info("Web Push: Redis connected")
        return _redis_client
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push: Redis unavailable: %s", exc)
        _redis_client = False
        return None


def reset_redis_client_for_tests() -> None:
    """測試用：重設 lazy Redis 狀態。"""
    global _redis_client
    _redis_client = None


def _redis_store_full_json() -> bool:
    """Redis 預設存完整 subscription；``WEB_PUSH_REDIS_SUMMARY_ONLY=1`` 僅摘要（無法 ``pywebpush``）。"""
    if not _redis_url():
        return _truthy("WEB_PUSH_STORE_FULL_SUBSCRIPTION")
    return not _truthy("WEB_PUSH_REDIS_SUMMARY_ONLY")


def _prune_ip_hits(now: float) -> None:
    cutoff = now - 60.0
    for ip, hits in list(_IP_HITS.items()):
        fresh = [t for t in hits if t >= cutoff]
        if fresh:
            _IP_HITS[ip] = fresh
        else:
            _IP_HITS.pop(ip, None)


def _rate_limited_memory(client_ip: str) -> bool:
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


def _rate_limited_redis(client_ip: str) -> bool:
    r = _get_redis()
    if not r:
        return _rate_limited_memory(client_ip)
    limit = _int_env("WEB_PUSH_SUBSCRIBE_RATE_PER_MIN", 30)
    if limit <= 0:
        return False
    key = f"webpush:rl:{client_ip}"
    try:
        n = r.incr(key)
        if n == 1:
            r.expire(key, 70)
        return n > limit
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push Redis rate limit: %s", exc)
        return _rate_limited_memory(client_ip)


def _rate_limited(client_ip: str) -> bool:
    if _get_redis():
        return _rate_limited_redis(client_ip)
    return _rate_limited_memory(client_ip)


def _trim_memory_store() -> None:
    max_n = _int_env("WEB_PUSH_STORE_MAX_SUBSCRIPTIONS", 512)
    if max_n <= 0 or len(_BY_FP) <= max_n:
        return
    items = sorted(_BY_FP.items(), key=lambda kv: float(kv[1].get("updated_at") or 0))
    for fp, _ in items[: max(1, len(_BY_FP) - max_n)]:
        _BY_FP.pop(fp, None)


def _bq_client():
    if (os.getenv("SKIP_BIGQUERY") or "").lower() in ("1", "true", "yes"):
        return None
    try:
        from google.cloud import bigquery

        from config import PROJECT_ID

        return bigquery.Client(project=PROJECT_ID)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push BQ: client unavailable: %s", exc)
        return None


def _bq_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _bq_persist_row(fp: str, endpoint: str, keys: dict[str, str] | None, client_ip: str) -> None:
    if not _truthy("WEB_PUSH_BQ_PERSIST"):
        return
    try:
        from config import WEB_PUSH_SUBSCRIPTIONS_TABLE

        client = _bq_client()
        if not client:
            return
        ts = _bq_ts()
        row = {
            "endpoint_fingerprint": fp,
            "endpoint_prefix": (endpoint or "")[:120],
            "has_p256dh": bool(keys and keys.get("p256dh")),
            "has_auth": bool(keys and keys.get("auth")),
            "last_client_ip": (client_ip or "")[:64],
            "first_seen": ts,
            "last_seen": ts,
        }
        errors = client.insert_rows_json(WEB_PUSH_SUBSCRIPTIONS_TABLE, [row])
        if errors:
            logger.warning("Web Push BQ persist: %s", errors[:3])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push BQ persist failed: %s", exc)


def _bq_audit_row(
    fp: str,
    *,
    client_ip: str,
    stored: bool,
    deduped: bool,
    rate_limited: bool,
    detail: str = "",
) -> None:
    if not _truthy("WEB_PUSH_BQ_AUDIT"):
        return
    try:
        from config import WEB_PUSH_SUBSCRIPTIONS_TABLE

        client = _bq_client()
        if not client:
            return
        base = WEB_PUSH_SUBSCRIPTIONS_TABLE.rsplit(".", 1)[0]
        audit_table = (os.getenv("WEB_PUSH_AUDIT_TABLE") or f"{base}.web_push_subscribe_audit").strip()
        row = {
            "event_ts": _bq_ts(),
            "endpoint_fingerprint": fp,
            "client_ip": (client_ip or "")[:64],
            "stored": stored,
            "deduped": deduped,
            "rate_limited": rate_limited,
            "detail": (detail or "")[:500],
        }
        errors = client.insert_rows_json(audit_table, [row])
        if errors:
            logger.warning("Web Push BQ audit: %s", errors[:3])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push BQ audit failed: %s", exc)


def _push_pref_fields(body: dict[str, Any]) -> dict[str, str]:
    """Optional subscribe metadata for deep-link prefs (stored alongside endpoint/keys)."""
    out: dict[str, str] = {}
    rd = body.get("report_date")
    if isinstance(rd, str) and rd.strip():
        out["report_date"] = rd.strip()
    bid = body.get("block_id")
    if isinstance(bid, str) and bid.strip():
        out["block_id"] = bid.strip()
    return out


def _redis_store_subscription(fp: str, body: dict[str, Any], client_ip: str) -> tuple[bool, int]:
    r = _get_redis()
    if not r:
        return False, 0
    endpoint = str(body.get("endpoint") or "")
    keys = body.get("keys")
    if not isinstance(keys, dict):
        keys = {}
    key_hash = "webpush:subscriptions"
    now = time.time()
    try:
        existed = bool(r.hexists(key_hash, fp))
        if _redis_store_full_json():
            row: dict[str, Any] = {
                "endpoint": endpoint,
                "keys": keys,
                "updated_at": now,
                "last_ip": client_ip,
            }
            row.update(_push_pref_fields(body))
            val = json.dumps(row, ensure_ascii=False)
        else:
            val = json.dumps(
                {
                    "updated_at": now,
                    "last_ip": client_ip,
                    "has_p256dh": bool(keys.get("p256dh")),
                    "has_auth": bool(keys.get("auth")),
                },
                ensure_ascii=False,
            )
        r.hset(key_hash, fp, val)
        n = int(r.hlen(key_hash))
        return existed, n
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push Redis HSET failed: %s", exc)
        return False, 0


def _redis_subscription_count() -> int:
    r = _get_redis()
    if not r:
        return 0
    try:
        return int(r.hlen("webpush:subscriptions"))
    except Exception:
        return 0


def _redis_list_subscription_dicts() -> list[dict[str, Any]]:
    r = _get_redis()
    if not r:
        return []
    out: list[dict[str, Any]] = []
    try:
        raw = r.hgetall("webpush:subscriptions")
        for _fp, val in raw.items():
            try:
                d = json.loads(val)
                ep = d.get("endpoint")
                ks = d.get("keys")
                if ep and isinstance(ks, dict):
                    out.append({"endpoint": ep, "keys": ks})
            except (json.JSONDecodeError, TypeError):
                continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("Web Push Redis HGETALL failed: %s", exc)
    return out


def record_subscription(body: dict[str, Any], *, client_ip: str = "") -> dict[str, Any]:
    endpoint = str(body.get("endpoint") or "")
    fp = _endpoint_fp(endpoint)
    keys = body.get("keys")
    if not isinstance(keys, dict):
        keys = None
    ip = (client_ip or "unknown").strip() or "unknown"

    if _rate_limited(ip):
        logger.warning("Web Push rate-limited (ip=%s)", ip)
        _bq_audit_row(fp, client_ip=ip, stored=False, deduped=False, rate_limited=True, detail="rate_limit")
        return {
            "stored": False,
            "count": subscription_count(),
            "endpoint_fp": fp,
            "rate_limited": True,
        }

    if _get_redis():
        store_body: dict[str, Any] = {"endpoint": endpoint, "keys": keys or {}}
        store_body.update(_push_pref_fields(body))
        deduped, n = _redis_store_subscription(fp, store_body, ip)
        _bq_persist_row(fp, endpoint, keys, ip)
        _bq_audit_row(fp, client_ip=ip, stored=True, deduped=deduped, rate_limited=False, detail="redis")
        logger.info("Web Push Redis (fp=%s, n=%s, deduped=%s)", fp, n, deduped)
        return {"stored": True, "count": n, "endpoint_fp": fp, "deduped": deduped, "backend": "redis"}

    if _truthy("WEB_PUSH_STORE"):
        row: dict[str, Any] = {
            "has_p256dh": bool(keys and keys.get("p256dh")),
            "has_auth": bool(keys and keys.get("auth")),
            "last_ip": ip,
            "updated_at": time.time(),
        }
        row.update(_push_pref_fields(body))
        if _truthy("WEB_PUSH_STORE_FULL_SUBSCRIPTION"):
            row["endpoint"] = endpoint
            row["keys"] = keys
        deduped = False
        with _LOCK:
            if fp and fp in _BY_FP:
                deduped = True
            if fp:
                _BY_FP[fp] = {**(_BY_FP.get(fp) or {}), **row}
            _trim_memory_store()
            n = len(_BY_FP)
        _bq_persist_row(fp, endpoint, keys, ip)
        _bq_audit_row(fp, client_ip=ip, stored=True, deduped=deduped, rate_limited=False, detail="memory")
        logger.info("Web Push memory (fp=%s, n=%d, deduped=%s)", fp, n, deduped)
        return {"stored": True, "count": n, "endpoint_fp": fp, "deduped": deduped, "backend": "memory"}

    _bq_audit_row(fp, client_ip=ip, stored=False, deduped=False, rate_limited=False, detail="log_only")
    logger.info("Web Push log-only (fp=%s)", fp or "empty")
    return {"stored": False, "count": 0, "endpoint_fp": fp, "backend": "log"}


def subscription_count() -> int:
    if _get_redis():
        return _redis_subscription_count()
    with _LOCK:
        return len(_BY_FP)


def list_subscription_infos_for_send() -> list[dict[str, Any]]:
    if _get_redis():
        return _redis_list_subscription_dicts()
    out: list[dict[str, Any]] = []
    with _LOCK:
        for _fp, row in _BY_FP.items():
            ep = row.get("endpoint")
            ks = row.get("keys")
            if ep and isinstance(ks, dict) and (ks.get("p256dh") or ks.get("auth")):
                out.append({"endpoint": ep, "keys": ks})
    return out


def clear_subscriptions_for_tests() -> None:
    with _LOCK:
        _BY_FP.clear()
        _IP_HITS.clear()
    reset_redis_client_for_tests()
    r = _get_redis()
    if r:
        try:
            r.delete("webpush:subscriptions")
        except Exception:
            pass


# Web Push 通知 body 上限（payload 須小；全文在 Portal 看）。
_PUSH_BODY_MAX = 180


def broadcast(
    title: str,
    body: str,
    url: str | None = None,
    *,
    cap: int | None = None,
    timeout: int = 15,
) -> dict[str, Any]:
    """以 ``pywebpush`` 對所有訂閱者發送一則 JSON 通知（標題＋短 body＋可選深連結）。

    payload schema：``{title, body, url?}``（body 截斷至 ``_PUSH_BODY_MAX``）。SW 的
    ``resolveNotificationUrl`` 讀 ``data.url``（須絕對 http(s)）。回傳
    ``{ok: sent>0, sent, attempted, errors, error?}`` — 全失敗或無訂閱不得記成功。
    """
    priv = (os.getenv("WEB_PUSH_VAPID_PRIVATE_KEY") or "").strip()
    if not priv:
        return {"ok": False, "error": "vapid_unset", "sent": 0, "attempted": 0}
    mailto = (os.getenv("WEB_PUSH_VAPID_MAILTO") or "mailto:ops@example.com").strip()
    try:
        from pywebpush import webpush
    except ImportError:
        return {"ok": False, "error": "pywebpush_unavailable", "sent": 0, "attempted": 0}

    subs = list_subscription_infos_for_send()
    if not subs:
        return {"ok": False, "error": "no_subscriptions", "sent": 0, "attempted": 0}

    data: dict[str, str] = {"title": str(title), "body": str(body)[:_PUSH_BODY_MAX]}
    if url and isinstance(url, str) and url.startswith(("http://", "https://")):
        data["url"] = url
    payload = json.dumps(data, ensure_ascii=False)

    resolved_cap = cap if cap is not None else _int_env("WEB_PUSH_SEND_MAX", 50)
    sent = 0
    errors: list[str] = []
    for info in subs[:resolved_cap]:
        try:
            webpush(
                subscription_info=info,
                data=payload,
                vapid_private_key=priv,
                vapid_claims={"sub": mailto},
                timeout=timeout,
            )
            sent += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc)[:200])
    return {"ok": sent > 0, "sent": sent, "attempted": min(len(subs), resolved_cap), "errors": errors[:5]}


def send_test_push(title: str, body: str) -> dict[str, Any]:
    """管理用測試推送（``/api/push/test-send``）。delegate 到 :func:`broadcast`。"""
    return broadcast(title, body)
