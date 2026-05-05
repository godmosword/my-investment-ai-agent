"""NotebookLM 工具 Phase 1：預設關閉；介面與 cache 契約預留（見 ``docs/architecture/notebooklm_research.md`` §14）。"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_CACHE: dict[tuple[Any, ...], tuple[str, float]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SEC = 600.0
_CACHE_MAX = 128


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


def notebooklm_enabled() -> bool:
    return os.getenv("NOTEBOOKLM_ENABLED", "0").strip().lower() in ("1", "true", "yes")


def notebooklm_query(question: str, *, notebook_id: str = "") -> str:
    """同步問答 stub：未接 notebooklm-client 前回傳 DATA_MISSING；預設關閉。"""
    if not notebooklm_enabled():
        return "[DATA_MISSING:notebooklm_disabled]"
    key = ("notebooklm_q", notebook_id.strip(), (question or "").strip()[:512])
    cached = _get_cache(key)
    if cached is not None:
        return cached
    out = "[DATA_MISSING:notebooklm_not_implemented]"
    _set_cache(key, out)
    logger.info("notebooklm_query stub (Phase 1); NOTEBOOKLM_ENABLED=1 but no client wired")
    return out
