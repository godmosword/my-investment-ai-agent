"""Options flow + GEX read API for the Portal (queue: options frontend).

Read-only over the BigQuery history written by the daily options pipeline. Before
Polygon is subscribed / BigQuery tables are configured, every endpoint returns a
stable ``enabled: false`` envelope with a ``reason`` — never fabricated numbers
(無數據幻覺紅線). The contract stays identical once data lights up.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

import options_bigquery_reader as reader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/options", tags=["options"])

_DEFAULT_WATCHLIST = ("MU", "NVDA", "AMD", "TSM", "AVGO", "SMH")
_PENDING_HINT = (
    "Subscribe Polygon Options + set POLYGON_API_KEY, run scripts/options_flow_tick.py, "
    "and set OPTIONS_GEX_HISTORY_TABLE / OPTIONS_UNUSUAL_TRADES_TABLE."
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _watchlist() -> list[str]:
    raw = (os.getenv("OPTIONS_WATCHLIST") or "").strip()
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    return list(_DEFAULT_WATCHLIST)


def _pending(extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = {
        "enabled": False,
        "reason": "polygon_options_pending",
        "hint": _PENDING_HINT,
        "as_of": _now_iso(),
    }
    if extra:
        payload.update(extra)
    return payload


@router.get("/summary")
def get_options_summary() -> dict[str, Any]:
    """Watchlist-level latest GEX + unusual-flow counts."""
    watchlist = _watchlist()
    if not reader.tables_configured():
        return _pending({"watchlist": watchlist, "items": []})

    latest = reader.read_latest_gex(watchlist)
    items: list[dict[str, Any]] = []
    for sym in watchlist:
        row = latest.get(sym)
        unusual = reader.read_recent_unusual(sym, limit=50)
        if row is None:
            items.append({"underlying": sym, "gex": None, "unusual_count": len(unusual)})
            continue
        total = row.get("total_gex")
        items.append(
            {
                "underlying": sym,
                "gex": {
                    "total_gex": total,
                    "call_gex": row.get("call_gex"),
                    "put_gex": row.get("put_gex"),
                    "spot_price": row.get("spot_price"),
                    "regime": ("positive" if (total or 0) >= 0 else "negative"),
                    "trade_date": str(row.get("trade_date") or ""),
                },
                "unusual_count": len(unusual),
            }
        )
    return {"enabled": True, "as_of": _now_iso(), "watchlist": watchlist, "items": items}


@router.get("/gex/{underlying}")
def get_options_gex(underlying: str) -> dict[str, Any]:
    """Latest GEX detail + history series for one underlying."""
    sym = (underlying or "").strip().upper()
    if not reader.tables_configured():
        return _pending({"underlying": sym})

    latest = reader.read_latest_gex([sym]).get(sym)
    history = reader.read_gex_history(sym, days=60)
    if latest is None and not history:
        return {
            "enabled": True,
            "underlying": sym,
            "as_of": _now_iso(),
            "gex": None,
            "history": [],
            "reason": "no_data_yet",
        }
    return {
        "enabled": True,
        "underlying": sym,
        "as_of": _now_iso(),
        "gex": latest,
        "history": [
            {
                "trade_date": str(h.get("trade_date") or ""),
                "total_gex": h.get("total_gex"),
                "call_gex": h.get("call_gex"),
                "put_gex": h.get("put_gex"),
                "spot_price": h.get("spot_price"),
            }
            for h in history
        ],
    }


@router.get("/flow/{underlying}")
def get_options_flow(underlying: str) -> dict[str, Any]:
    """Recent unusual-flow signals for one underlying."""
    sym = (underlying or "").strip().upper()
    if not reader.tables_configured():
        return _pending({"underlying": sym})
    signals = reader.read_recent_unusual(sym, limit=50)
    return {
        "enabled": True,
        "underlying": sym,
        "as_of": _now_iso(),
        "signals": [
            {
                "trade_date": str(s.get("trade_date") or ""),
                "option_ticker": s.get("option_ticker"),
                "signal_type": s.get("signal_type"),
                "score": s.get("score"),
                "premium": s.get("premium"),
                "volume": s.get("volume"),
                "open_interest": s.get("open_interest"),
                "rationale": s.get("rationale"),
            }
            for s in signals
        ],
    }
