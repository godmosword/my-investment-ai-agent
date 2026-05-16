"""SEC EDGAR XBRL company-concept fetcher for hyperscaler quarterly capex.

Pulls ``us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`` from EDGAR's
companyconcept API for the five hyperscaler tickers exposed by
``/api/macro/compute-memory``. Used only when ``COMPUTE_MEMORY_CAPEX_LIVE=1``;
failures fall back to the local mock fixture without raising.

SEC fair-use policy requires a descriptive User-Agent with a contact email;
the email is read from ``SEC_EDGAR_CONTACT_EMAIL`` (no hard-coded default).
Governance entry: ``docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`` §2 / §6.1.
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

# Ticker -> CIK (zero-padded to 10 digits is required by EDGAR URLs).
HYPERSCALER_CIKS: dict[str, str] = {
    "MSFT": "0000789019",
    "GOOG": "0001652044",  # Alphabet Inc.
    "META": "0001326801",
    "AMZN": "0001018724",
    "ORCL": "0001341439",
}

_CONCEPT = "us-gaap/PaymentsToAcquirePropertyPlantAndEquipment"
_REQUEST_TIMEOUT_SEC = 10.0
_CACHE_TTL_SEC = 24 * 3600.0  # capex is quarterly; 24h cache is plenty.

_CACHE: dict[str, tuple[dict[str, Any] | None, float]] = {}
_CACHE_LOCK = threading.Lock()


def _user_agent() -> str | None:
    """SEC requires User-Agent ``<company> <email>``; return ``None`` when unset."""
    email = (os.getenv("SEC_EDGAR_CONTACT_EMAIL") or "").strip()
    if not email:
        return None
    return f"q-silicon-research/1.0 {email}"


def _cache_get(ticker: str) -> dict[str, Any] | None | str:
    """Return cached value, ``None`` (cached miss), or the sentinel ``"MISS"``."""
    with _CACHE_LOCK:
        hit = _CACHE.get(ticker)
    if not hit:
        return "MISS"
    val, exp = hit
    if time.monotonic() > exp:
        with _CACHE_LOCK:
            _CACHE.pop(ticker, None)
        return "MISS"
    return val


def _cache_set(ticker: str, value: dict[str, Any] | None) -> None:
    with _CACHE_LOCK:
        _CACHE[ticker] = (value, time.monotonic() + _CACHE_TTL_SEC)


def reset_cache_for_tests() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def _fetch_companyconcept(cik: str, ua: str) -> dict[str, Any] | None:
    url = f"https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/{_CONCEPT}.json"
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        logger.warning("sec_edgar capex HTTP %s for CIK %s", exc.code, cik)
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("sec_edgar capex network error for CIK %s: %s", cik, exc)
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("sec_edgar capex JSON parse error for CIK %s: %s", cik, exc)
        return None


def _latest_quarterly_record(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Pick the most recent 10-Q / 10-K USD entry."""
    units = (payload.get("units") or {}).get("USD") or []
    if not isinstance(units, list):
        return None
    candidates = [
        rec
        for rec in units
        if isinstance(rec, dict)
        and str(rec.get("form") or "") in {"10-Q", "10-K", "10-Q/A", "10-K/A"}
        and isinstance(rec.get("val"), (int, float))
        and rec.get("end")
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: str(r.get("end") or ""), reverse=True)
    return candidates[0]


def fetch_latest_capex(ticker: str) -> dict[str, Any] | None:
    """Return ``{ticker, quarter, capex_b_usd, as_of, source, form, accn}`` or ``None``.

    Returns ``None`` for any failure mode (unknown ticker, missing User-Agent,
    HTTP error, parse error, no quarterly record). Callers should fall back to
    the local mock fixture; do **not** synthesize numbers.
    """
    cik = HYPERSCALER_CIKS.get(ticker.upper())
    if not cik:
        return None

    cached = _cache_get(ticker.upper())
    if cached != "MISS":
        return cached  # may be a prior None (cached negative)

    ua = _user_agent()
    if not ua:
        logger.warning("SEC_EDGAR_CONTACT_EMAIL unset; skipping live capex fetch for %s", ticker)
        # Negative cache short window only — let env fix retry quickly.
        _cache_set(ticker.upper(), None)
        return None

    payload = _fetch_companyconcept(cik, ua)
    if not isinstance(payload, dict):
        _cache_set(ticker.upper(), None)
        return None

    record = _latest_quarterly_record(payload)
    if not record:
        _cache_set(ticker.upper(), None)
        return None

    val_usd = float(record["val"])
    out = {
        "ticker": ticker.upper(),
        "quarter": f"{record.get('fy')}-{record.get('fp')}" if record.get("fy") else None,
        "capex_b_usd": round(val_usd / 1_000_000_000.0, 3),
        "as_of": record.get("end"),
        "source": "sec_edgar",
        "form": record.get("form"),
        "accn": record.get("accn"),
    }
    _cache_set(ticker.upper(), out)
    return out


def fetch_all_hyperscaler_capex() -> list[dict[str, Any]] | None:
    """Fetch all 5 hyperscalers; return list when **every** ticker succeeds.

    Returns ``None`` if any single fetch fails — the router treats this as a
    fallback signal (we want all-or-nothing for the dashboard panel to avoid
    half-mock half-live confusion).
    """
    items: list[dict[str, Any]] = []
    for ticker in HYPERSCALER_CIKS:
        rec = fetch_latest_capex(ticker)
        if rec is None:
            return None
        items.append(rec)
    return items
