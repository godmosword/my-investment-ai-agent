"""
HTTP session、JSON 回應解析與 in-memory tool 快取（由舊 monolith／`tools_legacy` 拆分）。

遷移自舊 monolith — 行為不變；Crew 仍從 ``tools`` 套件取得工具，不直接 import 本檔。
"""

from __future__ import annotations

import logging
import threading
import time

import requests

logger = logging.getLogger(__name__)

# ── in-memory cache（同一次執行內避免重複打外部 API）────────────
_CACHE: dict[tuple, tuple] = {}
_CACHE_TTL = 600  # 10 分鐘內相同 query 直接回傳 cache
_CACHE_MAX_SIZE = 256
_CACHE_LOCK = threading.Lock()

_HTTP_SESSION: requests.Session | None = None
_INIT_LOCK = threading.Lock()  # protects lazy-init singletons


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        with _INIT_LOCK:
            if _HTTP_SESSION is None:  # double-check
                s = requests.Session()
                s.headers.update({"User-Agent": "Q-Silicon/1.0"})
                _HTTP_SESSION = s
    return _HTTP_SESSION


def _http_get(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    timeout: float | int | tuple = 10,
) -> requests.Response:
    """模組級 Session 的 GET，供連線重用與統一出口。"""
    return _get_http_session().get(url, params=params, headers=headers, timeout=timeout)


def _response_json_dict(resp: requests.Response, source: str) -> dict | None:
    try:
        raw = resp.json()
    except ValueError as e:
        logger.warning("%s JSON decode failed: %s", source, e)
        return None
    try:
        from api_schema import require_json_dict

        return require_json_dict(raw, source=source)
    except ValueError:
        return None


def _response_json_list(resp: requests.Response, source: str) -> list | None:
    try:
        raw = resp.json()
    except ValueError as e:
        logger.warning("%s JSON decode failed: %s", source, e)
        return None
    try:
        from api_schema import require_json_list

        return require_json_list(raw, source=source)
    except ValueError:
        return None


def _get_cache(key: tuple) -> str | None:
    if key in _CACHE:
        result, expire = _CACHE[key]
        if time.time() < expire:
            return result
        with _CACHE_LOCK:
            _CACHE.pop(key, None)
    return None


def _set_cache(key: tuple, value: str) -> None:
    with _CACHE_LOCK:
        if len(_CACHE) >= _CACHE_MAX_SIZE:
            oldest_keys = sorted(_CACHE, key=lambda k: _CACHE[k][1])[: len(_CACHE) // 4]
            for k in oldest_keys:
                del _CACHE[k]
        _CACHE[key] = (value, time.time() + _CACHE_TTL)
