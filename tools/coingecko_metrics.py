"""CoinGecko / Alternative.me valuation fetcher for on-chain dashboard (FA-1).

Reads CoinGecko ``/global`` and Alternative.me Fear & Greed (public, no auth).
Used only when ``ONCHAIN_VALUATION_LIVE=1``; failures return ``None`` so the
router can fall back to the local fixture without raising.

Governance entry: ``docs/REALTIME_DATA_SOURCES_GOVERNANCE.md``.
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

_COINGECKO_URL = "https://api.coingecko.com/api/v3/global"
_FNG_URL = "https://api.alternative.me/fng/?limit=1"
_REQUEST_TIMEOUT_SEC = 10.0
_CACHE_TTL_SEC = 300.0

_CACHE: tuple[dict[str, Any] | None, float] | None = None
_CACHE_LOCK = threading.Lock()


def reset_cache_for_tests() -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = None


def _user_agent() -> str:
    email = (os.getenv("SEC_EDGAR_CONTACT_EMAIL") or "").strip()
    return f"q-silicon-research/1.0 ({email})" if email else "q-silicon-research/1.0"


def _cache_get() -> dict[str, Any] | None | str:
    with _CACHE_LOCK:
        hit = _CACHE
    if not hit:
        return "MISS"
    val, exp = hit
    if time.monotonic() > exp:
        reset_cache_for_tests()
        return "MISS"
    return val


def _cache_set(value: dict[str, Any] | None) -> None:
    global _CACHE
    with _CACHE_LOCK:
        _CACHE = (value, time.monotonic() + _CACHE_TTL_SEC)


def _fetch_json(url: str) -> dict[str, Any] | None:
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent(), "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.warning("coingecko_metrics HTTP %s for %s", exc.code, url)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("coingecko_metrics network error for %s: %s", url, exc)
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("coingecko_metrics JSON parse error for %s: %s", url, exc)
        return None
    return payload if isinstance(payload, dict) else None


def fetch_valuation_snapshot() -> dict[str, Any] | None:
    """Return valuation block for ``btc_valuation`` or ``None`` on any failure."""
    cached = _cache_get()
    if cached != "MISS":
        return cached

    global_payload = _fetch_json(_COINGECKO_URL)
    if not isinstance(global_payload, dict):
        _cache_set(None)
        return None

    data = global_payload.get("data")
    if not isinstance(data, dict):
        _cache_set(None)
        return None

    mcap_pct = data.get("market_cap_percentage")
    total_mcap = data.get("total_market_cap")
    if not isinstance(mcap_pct, dict) or not isinstance(total_mcap, dict):
        _cache_set(None)
        return None

    try:
        btc_dom = float(mcap_pct.get("btc"))
        market_cap_usd = float(total_mcap.get("usd"))
    except (TypeError, ValueError):
        _cache_set(None)
        return None

    fng_payload = _fetch_json(_FNG_URL)
    if not isinstance(fng_payload, dict):
        _cache_set(None)
        return None

    fng_rows = fng_payload.get("data")
    if not isinstance(fng_rows, list) or not fng_rows:
        _cache_set(None)
        return None

    first = fng_rows[0]
    if not isinstance(first, dict):
        _cache_set(None)
        return None

    try:
        fng_value = int(str(first.get("value", "")).strip())
    except (TypeError, ValueError):
        _cache_set(None)
        return None

    fng_regime = str(first.get("value_classification") or "").strip() or "neutral"
    today_iso = datetime.now(timezone.utc).date().isoformat()

    block = {
        "as_of": today_iso,
        "source": "coingecko_altme",
        "note": "Free valuation proxy: CoinGecko global + Alternative.me Fear & Greed.",
        "items": [
            {"metric": "BTC Dominance", "value": round(btc_dom, 4), "regime": "neutral"},
            {
                "metric": "Total Crypto Market Cap",
                "value": round(market_cap_usd, 2),
                "regime": "neutral",
            },
            {"metric": "Fear & Greed", "value": fng_value, "regime": fng_regime},
        ],
    }
    _cache_set(block)
    return block
