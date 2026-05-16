"""Binance USD-M futures funding-rate fetcher for the on-chain dashboard.

Reads ``GET /fapi/v1/premiumIndex?symbol=...`` (public, no auth) and annualizes
the 8-hour ``lastFundingRate`` into a yearly % for ``/api/macro/onchain``'s
``funding_rate`` block. Used only when ``ONCHAIN_FUNDING_LIVE=1``; failures
fall back to the local mock fixture without raising.

Governance entry: ``docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`` §2 / §7.1.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# Asset → Binance symbol pair. Order matches the dashboard row order.
ASSET_SYMBOLS: list[tuple[str, str]] = [
    ("BTC", "BTCUSDT"),
    ("ETH", "ETHUSDT"),
]

_BASE_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"
_REQUEST_TIMEOUT_SEC = 10.0
_CACHE_TTL_SEC = 300.0  # 5 min; funding rate updates every 8h, so this is plenty.

# Funding rate is the 8h fraction; annualize ×3 ×365 to APR%.
_FUNDING_TO_APR = 3 * 365 * 100.0

_CACHE: tuple[list[dict[str, Any]] | None, float] | None = None
_CACHE_LOCK = threading.Lock()


def reset_cache_for_tests() -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def _user_agent() -> str:
    email = (os.getenv("SEC_EDGAR_CONTACT_EMAIL") or "").strip()
    return f"q-silicon-research/1.0 ({email})" if email else "q-silicon-research/1.0"


def _cache_get() -> list[dict[str, Any]] | None | str:
    with _CACHE_LOCK:
        hit = _CACHE
    if not hit:
        return "MISS"
    val, exp = hit
    if time.monotonic() > exp:
        reset_cache_for_tests()
        return "MISS"
    return val


def _cache_set(value: list[dict[str, Any]] | None) -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = (value, time.monotonic() + _CACHE_TTL_SEC)


def _fetch_one(symbol: str) -> dict[str, Any] | None:
    url = f"{_BASE_URL}?symbol={symbol}"
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.warning("binance funding HTTP %s for %s", exc.code, symbol)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("binance funding network error for %s: %s", symbol, exc)
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("binance funding JSON parse error for %s: %s", symbol, exc)
        return None


def fetch_funding_rates() -> list[dict[str, Any]] | None:
    """Return list of ``{asset, venue, funding_apr_pct, as_of, source}`` or ``None``.

    All-or-nothing: any single symbol failure rejects the batch so the dashboard
    doesn't show half-live / half-mock numbers. ``lastFundingRate`` is the 8h
    fraction; annualized as ``rate × 3 × 365 × 100`` percent.
    """
    cached = _cache_get()
    if cached != "MISS":
        return cached

    today_iso = datetime.now(timezone.utc).date().isoformat()
    items: list[dict[str, Any]] = []
    for asset, symbol in ASSET_SYMBOLS:
        payload = _fetch_one(symbol)
        if not isinstance(payload, dict):
            _cache_set(None)
            return None
        raw_rate = payload.get("lastFundingRate")
        try:
            rate = float(raw_rate)
        except (TypeError, ValueError):
            logger.warning("binance funding: missing/invalid lastFundingRate for %s", symbol)
            _cache_set(None)
            return None
        items.append(
            {
                "asset": asset,
                "venue": "Binance",
                "funding_apr_pct": round(rate * _FUNDING_TO_APR, 4),
                "as_of": today_iso,
                "source": "binance_fapi",
                "symbol": symbol,
            }
        )

    _cache_set(items)
    return items
