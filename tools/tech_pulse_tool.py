"""Tech pulse 外部摘要：僅注入 ``exclude_context``（非 ``price_context``）；預設關閉。

契約見 ``docs/ADR_TECH_PULSE_INTEGRATION.md``。Phase 1：``TECH_PULSE_URL`` HTTP GET JSON
（``summary`` 欄）或純文字；``MOCK_APIS=1`` 回傳固定 stub。
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

_CACHE: dict[tuple[Any, ...], tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SEC = 300.0
_CACHE_MAX = 64


def _get_cache(key: tuple[Any, ...]) -> str | None:
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
    if not hit:
        return None
    val, exp = hit
    if time.monotonic() > exp:
        with _CACHE_LOCK:
            _CACHE.pop(key, None)
        return None
    return val


def _set_cache(key: tuple[Any, ...], value: str) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            oldest = min(_CACHE.items(), key=lambda kv: kv[1][1])[0]
            _CACHE.pop(oldest, None)
        _CACHE[key] = (value, time.monotonic() + _CACHE_TTL_SEC)


def tech_pulse_in_brief_enabled() -> bool:
    return (os.getenv("TECH_PULSE_IN_BRIEF", "") or "").strip().lower() in ("1", "true", "yes", "on")


def _mock_apis() -> bool:
    return (os.getenv("MOCK_APIS", "") or "").strip().lower() in ("1", "true", "yes", "on")


def fetch_tech_pulse_exclusion_snippet() -> str:
    """Return plain-text block for ``exclude_context`` only; empty when disabled or no source."""
    if not tech_pulse_in_brief_enabled():
        return ""

    if _mock_apis():
        key = ("tech_pulse", "mock")
        cached = _get_cache(key)
        if cached is not None:
            return cached
        out = (
            "[DATA_MISSING:tech_pulse_mock] MOCK_APIS=1：未呼叫外部 tech-pulse；"
            "僅供 CI／本機 Gate 與版面迴歸。"
        )
        _set_cache(key, out)
        return out

    url = (os.getenv("TECH_PULSE_URL") or "").strip()
    if not url:
        key = ("tech_pulse", "no_url")
        cached = _get_cache(key)
        if cached is not None:
            return cached
        out = "[DATA_MISSING:tech_pulse_no_url]"
        _set_cache(key, out)
        return out

    key = ("tech_pulse", "http", url[:512])
    cached = _get_cache(key)
    if cached is not None:
        return cached

    try:
        req = urllib.request.Request(
            url,
            headers={"Accept": "application/json, text/plain;q=0.9,*/*;q=0.8"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("tech_pulse HTTP fetch failed: %s", exc)
        out = f"[DATA_MISSING:tech_pulse_http_error:{type(exc).__name__}]"
        _set_cache(key, out)
        return out

    text = _normalize_http_body(raw)
    if not text.strip():
        text = "[DATA_MISSING:tech_pulse_empty_body]"
    text = text.strip()[:8000]
    _set_cache(key, text)
    return text


def _normalize_http_body(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw
        if isinstance(data, dict):
            summ = data.get("summary")
            if isinstance(summ, str) and summ.strip():
                return summ.strip()
            return json.dumps(data, ensure_ascii=False)[:4000]
        return json.dumps(data, ensure_ascii=False)[:4000]
    return raw
