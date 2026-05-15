"""Earnings calendar + filing insight read API (queue 45 / P3).

Two read-only endpoints designed to surface what the repo already has:
- ``GET /api/earnings/upcoming?days=14`` — scans the mega-cap tech watchlist
  via ``earnings_watchlist.tickers_with_earnings_between`` and returns the next
  N days of earnings dates, tagged by pillar (AI / semiconductor / cloud /
  hardware / other).
- ``GET /api/earnings/{symbol}/insight`` — returns the existing
  ``DeepFilingAnalysis`` structure if scaffold data is available (JSONL file
  pointed at by ``DEEP_FILING_ANALYSIS_FILE``); otherwise responds with an
  explicit ``enabled: false`` so the UI can show a clean empty state without
  fabricating numbers.

The endpoint never falls back to LLMs or external services. yfinance calendar
lookups (already used by ``current_affairs_crew`` and the daily-brief
pipeline) are cached in-process for one hour to avoid hammering yfinance per
page load.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from earnings_watchlist import (
    MEGA_CAP_TECH_EARNINGS_TICKERS,
    pipeline_anchor_date,
    tickers_with_earnings_between,
)
from schemas import DeepFilingAnalysis


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/earnings", tags=["earnings"])


# Pillar mapping mirrors the daily-brief categorization. The list is hand-curated
# rather than inferred to keep the API deterministic; new tickers default to
# "other" until the maintainer slots them.
PILLAR_BY_TICKER: dict[str, str] = {
    # AI / cloud software
    "MSFT": "cloud_software", "GOOGL": "cloud_software", "META": "cloud_software",
    "AMZN": "cloud_software", "ORCL": "cloud_software", "CRM": "cloud_software",
    "NOW": "cloud_software", "SNOW": "cloud_software", "PLTR": "cloud_software",
    "CRWD": "cloud_software", "NET": "cloud_software",
    # AI silicon / accelerators
    "NVDA": "ai_silicon", "AMD": "ai_silicon", "AVGO": "ai_silicon",
    "MRVL": "ai_silicon", "QCOM": "ai_silicon", "ARM": "ai_silicon",
    # Foundry / memory
    "TSM": "semiconductor", "INTC": "semiconductor", "MU": "semiconductor",
    # AI server / ODM / networking
    "SMCI": "hardware", "DELL": "hardware", "HPE": "hardware",
    "ANET": "hardware", "CSCO": "hardware",
    # Optical / interconnect
    "LITE": "optical", "COHR": "optical", "FN": "optical",
    # Consumer
    "AAPL": "consumer_devices",
}


def _pillar_for(symbol: str) -> str:
    return PILLAR_BY_TICKER.get(symbol.upper(), "other")


# --- yfinance calendar cache --------------------------------------------------
# In-process cache keyed by (start_iso, end_iso, tuple-of-tickers). One hour TTL
# is plenty for an earnings calendar; the underlying ``yf.Ticker.calendar`` call
# is the slow part (~hundreds of ms each).
_EARNINGS_CACHE_TTL_SECONDS = 3600.0
_EARNINGS_CACHE: dict[tuple[str, str, tuple[str, ...]], tuple[float, list[tuple[str, date]]]] = {}


def _cache_get(key: tuple[str, str, tuple[str, ...]]) -> list[tuple[str, date]] | None:
    entry = _EARNINGS_CACHE.get(key)
    if not entry:
        return None
    ts, pairs = entry
    if time.time() - ts > _EARNINGS_CACHE_TTL_SECONDS:
        _EARNINGS_CACHE.pop(key, None)
        return None
    return pairs


def _cache_set(key: tuple[str, str, tuple[str, ...]], pairs: list[tuple[str, date]]) -> None:
    _EARNINGS_CACHE[key] = (time.time(), pairs)


def reset_cache_for_tests() -> None:
    _EARNINGS_CACHE.clear()


def _watchlist() -> tuple[str, ...]:
    """Tickers to scan. Allow override via env for staging / tests."""
    raw = (os.getenv("EARNINGS_WATCHLIST_OVERRIDE") or "").strip()
    if raw:
        parts = tuple(s.strip().upper() for s in raw.split(",") if s.strip())
        if parts:
            return parts
    return MEGA_CAP_TECH_EARNINGS_TICKERS


@router.get("/upcoming")
def get_upcoming(days: int = Query(default=14, ge=1, le=60)) -> dict[str, Any]:
    """Mega-cap tech earnings calendar for the next ``days`` (default 14).

    Cached for one hour to amortize yfinance calls. Returns ``{ as_of, days,
    items: [{symbol, pillar, next_earnings_date, days_until, status}] }``;
    ``status`` is always ``"unknown"`` because yfinance does not expose
    pre/post-market reliably — we keep the field so the UI contract is stable
    once a richer source lands.
    """
    anchor = pipeline_anchor_date()
    end = anchor + timedelta(days=days)
    tickers = _watchlist()
    key = (anchor.isoformat(), end.isoformat(), tickers)

    cached = _cache_get(key)
    if cached is not None:
        pairs = cached
    else:
        try:
            pairs = tickers_with_earnings_between(tickers, anchor, end)
        except Exception as exc:  # noqa: BLE001
            logger.warning("earnings upcoming: yfinance lookup failed: %s", exc)
            pairs = []
        _cache_set(key, pairs)

    items: list[dict[str, Any]] = []
    for symbol, ed in pairs:
        items.append(
            {
                "symbol": symbol,
                "pillar": _pillar_for(symbol),
                "next_earnings_date": ed.isoformat(),
                "days_until": (ed - anchor).days,
                "status": "unknown",
            }
        )

    return {
        "as_of": anchor.isoformat(),
        "days": days,
        "watchlist_size": len(tickers),
        "items": items,
    }


# --- Filing insight -----------------------------------------------------------

def _deep_filing_file() -> Path:
    raw = (os.getenv("DEEP_FILING_ANALYSIS_FILE") or "data/deep_filing_analysis.jsonl").strip()
    return Path(raw)


def _load_filing_record(symbol: str) -> dict[str, Any] | None:
    """Return the newest DeepFilingAnalysis record for ``symbol`` if scaffold data exists."""
    path = _deep_filing_file()
    if not path.exists():
        return None
    target = symbol.upper()
    latest: dict[str, Any] | None = None
    latest_as_of: str = ""
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict):
                    continue
                if str(row.get("ticker") or "").upper() != target:
                    continue
                row_as_of = str(row.get("as_of") or "")
                if latest is None or row_as_of >= latest_as_of:
                    latest = row
                    latest_as_of = row_as_of
    except OSError as exc:
        logger.warning("earnings insight: read %s failed: %s", path, exc)
        return None
    return latest


@router.get("/{symbol}/insight")
def get_insight(symbol: str) -> dict[str, Any]:
    """Return DeepFilingAnalysis scaffold for a ticker if available; else enabled=false."""
    sym = symbol.strip().upper()
    if not sym or not sym.replace("-", "").replace(".", "").isalnum() or len(sym) > 12:
        raise HTTPException(status_code=400, detail="invalid symbol")

    row = _load_filing_record(sym)
    if row is None:
        return {
            "enabled": False,
            "symbol": sym,
            "reason": "no_filing_scaffold_data",
            "hint": "Set DEEP_FILING_ANALYSIS_FILE and append a JSONL row with ticker/filing_type/answers/citations.",
        }

    try:
        analysis = DeepFilingAnalysis.model_validate(row)
    except ValidationError as exc:
        logger.warning("earnings insight %s: schema validation failed: %s", sym, exc)
        return {
            "enabled": False,
            "symbol": sym,
            "reason": "scaffold_invalid",
            "error_count": exc.error_count(),
            "error_messages": [str(err.get("msg", "")) for err in exc.errors(include_url=False)],
        }

    return {
        "enabled": True,
        "symbol": sym,
        "as_of": str(row.get("as_of") or ""),
        "analysis": analysis.model_dump(mode="json"),
    }
