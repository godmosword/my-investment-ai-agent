"""Symbol quote and snapshot APIs."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api_deps import get_bq_client
from symbol_snapshot_service import (
    build_symbol_snapshot,
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])

QUOTE_TTL_SECONDS = 45


class SymbolSnapshot(BaseModel):
    symbol: str
    as_of: str | None = None
    source: str = "bigquery"
    latest_metrics: dict[str, Any]
    history: list[dict[str, Any]]
    price_series: list[dict[str, Any]]
    event_markers: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    report_links: list[dict[str, str]]
    data_provenance: dict[str, Any] = Field(default_factory=dict)
    price_alignment: dict[str, Any] | None = None


class SymbolQuote(BaseModel):
    """Lightweight last close + 1d % change (yfinance only; M3 Terminal KPI strip)."""

    symbol: str
    as_of: str
    source: str = "yfinance"
    underlying_symbol: str
    last: float | None = None
    currency: str | None = None
    change_pct_1d: float | None = None
    cached: bool = False
    data_provenance: dict[str, Any] = Field(default_factory=dict)


def _validate_symbol(symbol: str) -> str:
    try:
        return validate_symbol_for_snapshot(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{symbol}/quote", response_model=SymbolQuote)
def get_symbol_quote(symbol: str) -> dict[str, Any]:
    """Terminal-style last price strip; no BigQuery. Cached ~45s server-side."""
    normalized_symbol = _validate_symbol(symbol)
    raw = fetch_symbol_quote(normalized_symbol)
    if raw.get("error") or raw.get("last") is None:
        raise HTTPException(
            status_code=503,
            detail=str(raw.get("error") or "quote_unavailable"),
        )
    provenance = {
        "price": {
            "source": "yfinance",
            "as_of": raw.get("as_of"),
            "interval": "1d",
            "underlying_symbol": raw.get("underlying_symbol"),
            "ttl_seconds": QUOTE_TTL_SECONDS,
        }
    }
    return {
        "symbol": raw["symbol"],
        "as_of": str(raw.get("as_of") or ""),
        "source": "yfinance",
        "underlying_symbol": str(raw.get("underlying_symbol") or ""),
        "last": raw.get("last"),
        "currency": raw.get("currency"),
        "change_pct_1d": raw.get("change_pct_1d"),
        "cached": bool(raw.get("cached")),
        "data_provenance": provenance,
    }


@router.get("/{symbol}/snapshot", response_model=SymbolSnapshot)
def get_symbol_snapshot(
    symbol: str,
    days: int = Query(default=30, ge=7, le=180),
    recommendation_limit: int = Query(default=12, ge=1, le=40),
) -> dict[str, Any]:
    """Terminal-style symbol snapshot for PWA focus cards/workspace."""
    normalized_symbol = _validate_symbol(symbol)
    try:
        client = get_bq_client()
        return build_symbol_snapshot(
            client,
            normalized_symbol,
            days=days,
            recommendation_limit=recommendation_limit,
        )
    except Exception as exc:
        logger.error("BigQuery symbols/%s/snapshot failed: %s", normalized_symbol, exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc
