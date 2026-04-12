"""Shared symbol snapshot builder for FastAPI and Streamlit (read-only, BQ + yfinance).

Keeps one implementation of the Terminal `/api/symbols/{symbol}/snapshot` payload shape
so the PWA and dashboard do not drift.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from google.cloud import bigquery

from config import METRICS_TABLE, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

_ohlc_cache: dict[tuple[str, int], tuple[datetime, list[dict[str, Any]]]] = {}
_OHLC_CACHE_TTL = timedelta(minutes=3)
_OHLC_CACHE_MAX_KEYS = 128


def rows_to_dicts(rows) -> list[dict[str, Any]]:
    """Convert BigQuery RowIterator rows to JSON-serialisable dicts."""
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append(
            {k: v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in row.items()}
        )
    return result


def validate_symbol_for_snapshot(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if not normalized or not re.fullmatch(r"[A-Z0-9._-]{1,15}", normalized):
        raise ValueError(
            "Invalid symbol format; use alphanumerics and ._- only (max 15 chars)"
        )
    return normalized


def to_yf_symbol(symbol: str) -> str:
    crypto_map = {
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
        "SOL": "SOL-USD",
        "BNB": "BNB-USD",
    }
    return crypto_map.get(symbol, symbol)


def fetch_symbol_ohlc(symbol: str, days: int) -> list[dict[str, Any]]:
    """Daily OHLC for *symbol* via yfinance; short TTL in-process cache."""
    now = datetime.now(timezone.utc)
    cache_key = (symbol, days)
    cached = _ohlc_cache.get(cache_key)
    if cached and now - cached[0] <= _OHLC_CACHE_TTL:
        return cached[1]

    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover
        logger.warning("yfinance unavailable for symbol snapshot: %s", exc)
        return cached[1] if cached else []

    yf_symbol = to_yf_symbol(symbol)
    try:
        hist = yf.Ticker(yf_symbol).history(period=f"{days}d", interval="1d")
    except Exception as exc:
        logger.warning("Could not fetch OHLC for %s via yfinance: %s", yf_symbol, exc)
        return cached[1] if cached else []

    rows: list[dict[str, Any]] = []
    if hist is None or hist.empty:
        return cached[1] if cached else rows
    for idx, row in hist.iterrows():
        try:
            ts = idx.to_pydatetime().date().isoformat()
            rows.append(
                {
                    "time": ts,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                }
            )
        except Exception:
            continue
    _ohlc_cache[cache_key] = (now, rows)
    if len(_ohlc_cache) > _OHLC_CACHE_MAX_KEYS:
        oldest_key = min(_ohlc_cache.items(), key=lambda item: item[1][0])[0]
        _ohlc_cache.pop(oldest_key, None)
    return rows


def build_symbol_snapshot(
    client: bigquery.Client,
    normalized_symbol: str,
    *,
    days: int = 30,
    recommendation_limit: int = 12,
) -> dict[str, Any]:
    """Assemble the same dict as ``GET /api/symbols/{symbol}/snapshot``."""
    latest_rows = list(
        client.query(
            f"""
            SELECT
                timestamp, dxy, etf_flow_millions, avg_risk_score,
                mvrv_z_score, sentiment_score, sopr, exchange_netflow,
                regime_score, grok_summary, gpt_summary
            FROM `{METRICS_TABLE}`
            ORDER BY timestamp DESC
            LIMIT 1
        """
        ).result()
    )
    history_rows = client.query(
        f"""
            SELECT
                timestamp, dxy, etf_flow_millions, avg_risk_score,
                mvrv_z_score, sentiment_score, sopr, exchange_netflow,
                regime_score
            FROM `{METRICS_TABLE}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            ORDER BY timestamp ASC
        """
    ).result()
    rec_rows = client.query(
        f"""
            SELECT
                report_date, asset, category, direction, confidence,
                narrative, trigger, invalidation, status,
                entry_price, target_price, stop_price, rr_ratio
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE UPPER(asset) = '{normalized_symbol}'
            ORDER BY report_date DESC, confidence DESC
            LIMIT {recommendation_limit}
        """
    ).result()

    latest_metrics = rows_to_dicts(latest_rows)[0] if latest_rows else {}
    history = rows_to_dicts(history_rows)
    recommendations = rows_to_dicts(rec_rows)
    price_series = fetch_symbol_ohlc(normalized_symbol, days=days)

    seen_dates: set[str] = set()
    report_links: list[dict[str, str]] = []
    event_markers: list[dict[str, Any]] = []
    for rec in recommendations:
        report_date = rec.get("report_date")
        if not report_date or report_date in seen_dates:
            if report_date:
                event_markers.append(
                    {
                        "time": report_date,
                        "type": "signal",
                        "label": f"{rec.get('direction', 'N/A')} {rec.get('status', 'N/A')}",
                        "entry_price": rec.get("entry_price"),
                        "target_price": rec.get("target_price"),
                        "stop_price": rec.get("stop_price"),
                    }
                )
            continue
        seen_dates.add(report_date)
        report_links.append(
            {
                "report_date": report_date,
                "href": f"/report/{report_date}",
                "api_href": f"/api/reports/{report_date}",
            }
        )
        event_markers.append(
            {
                "time": report_date,
                "type": "signal",
                "label": f"{rec.get('direction', 'N/A')} {rec.get('status', 'N/A')}",
                "entry_price": rec.get("entry_price"),
                "target_price": rec.get("target_price"),
                "stop_price": rec.get("stop_price"),
            }
        )
    event_markers.sort(key=lambda m: str(m.get("time", "")))

    ohlc_as_of = str(price_series[-1]["time"]) if price_series else ""
    if not ohlc_as_of:
        ohlc_as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data_provenance: dict[str, Any] = {
        "ohlc": {
            "source": "yfinance",
            "as_of": ohlc_as_of,
            "interval": "1d",
            "underlying_symbol": to_yf_symbol(normalized_symbol),
        },
        "daily_metrics": {
            "source": "bigquery",
            "table_id": METRICS_TABLE,
            "as_of": latest_metrics.get("timestamp"),
        },
        "recommendations": {
            "source": "bigquery",
            "table_id": RECOMMENDATIONS_TABLE,
            "query_window_days": days,
            "as_of": latest_metrics.get("timestamp"),
        },
    }

    return {
        "symbol": normalized_symbol,
        "as_of": latest_metrics.get("timestamp"),
        "source": "bigquery",
        "latest_metrics": latest_metrics,
        "history": history,
        "price_series": price_series,
        "event_markers": event_markers,
        "recommendations": recommendations,
        "report_links": report_links,
        "data_provenance": data_provenance,
    }
