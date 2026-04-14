"""Shared symbol snapshot builder for FastAPI and Streamlit (read-only, BQ + yfinance).

Keeps one implementation of the Terminal `/api/symbols/{symbol}/snapshot` payload shape
so the PWA and dashboard do not drift.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from google.cloud import bigquery

from config import METRICS_TABLE, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

_ohlc_cache: dict[tuple[str, int], tuple[datetime, list[dict[str, Any]]]] = {}
_OHLC_CACHE_TTL = timedelta(minutes=3)
_OHLC_CACHE_MAX_KEYS = 128

# Lightweight last / 1d change for Terminal KPI strip (no BigQuery).
_quote_cache: dict[str, tuple[datetime, dict[str, Any]]] = {}
_QUOTE_CACHE_TTL = timedelta(seconds=45)
_QUOTE_CACHE_MAX_KEYS = 256


def _quote_cache_put(sym: str, payload: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc)
    store = {k: v for k, v in payload.items() if k != "cached"}
    _quote_cache[sym] = (now, store)
    if len(_quote_cache) > _QUOTE_CACHE_MAX_KEYS:
        oldest = min(_quote_cache.items(), key=lambda x: x[1][0])[0]
        _quote_cache.pop(oldest, None)


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


def fetch_symbol_quote(normalized_symbol: str) -> dict[str, Any]:
    """Latest daily close + optional 1d % change via yfinance; short TTL cache (M3 Terminal).

    Does not query BigQuery. On failure returns a dict with ``last`` null and ``error`` set
    (caller maps to HTTP 503).
    """
    now = datetime.now(timezone.utc)
    sym = normalized_symbol.strip().upper()
    cached = _quote_cache.get(sym)
    if cached and now - cached[0] <= _QUOTE_CACHE_TTL:
        return {**cached[1], "cached": True}

    try:
        import yfinance as yf
    except Exception as exc:  # pragma: no cover
        logger.warning("yfinance unavailable for symbol quote: %s", exc)
        return {
            "symbol": sym,
            "as_of": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "yfinance",
            "underlying_symbol": to_yf_symbol(sym),
            "last": None,
            "currency": None,
            "change_pct_1d": None,
            "error": "yfinance_unavailable",
            "cached": False,
        }

    yf_symbol = to_yf_symbol(sym)
    out: dict[str, Any] = {
        "symbol": sym,
        "as_of": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "yfinance",
        "underlying_symbol": yf_symbol,
        "last": None,
        "currency": None,
        "change_pct_1d": None,
        "error": None,
        "cached": False,
    }

    try:
        hist = yf.Ticker(yf_symbol).history(period="10d", interval="1d")
    except Exception as exc:
        logger.warning("Could not fetch quote history for %s: %s", yf_symbol, exc)
        out["error"] = "yfinance_history_failed"
        return out

    if hist is None or hist.empty:
        out["error"] = "no_price_data"
        return out

    try:
        last_row = hist.iloc[-1]
        last_idx = hist.index[-1]
        ts = last_idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        out["as_of"] = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        out["last"] = float(last_row["Close"])
        if len(hist) >= 2:
            prev_close = float(hist.iloc[-2]["Close"])
            if prev_close:
                out["change_pct_1d"] = round((float(last_row["Close"]) - prev_close) / prev_close * 100.0, 4)
    except Exception as exc:
        logger.warning("Could not parse quote row for %s: %s", yf_symbol, exc)
        out["error"] = "parse_failed"
        return out

    try:
        cur = yf.Ticker(yf_symbol).fast_info.get("currency")
        if cur:
            out["currency"] = str(cur)
    except Exception:
        pass

    _quote_cache_put(sym, out)
    return {**{k: v for k, v in out.items() if k != "cached"}, "cached": False}


def _last_ohlc_bar(price_series: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not price_series:
        return None
    return price_series[-1]


def _align_snapshot_price(
    normalized_symbol: str,
    price_series: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cross-route alignment probe: snapshot ``price_series`` tail vs standalone ``/quote`` (yfinance).

    ``latest_metrics`` 仍來自 BigQuery（見 ``build_symbol_snapshot``）；本欄位僅描述 **OHLC 尾端 vs quote** 兩條 yfinance 路徑是否一致。
    """
    out: dict[str, Any] = {
        "ohlc_last_close": None,
        "quote_last": None,
        "abs_diff": None,
        "rel_diff": None,
        "aligned": None,
        "quote_error": None,
        "ohlc_source": "yfinance",
        "quote_source": "yfinance",
        "daily_metrics_source": "bigquery",
        "routes": {
            "ohlc": "fetch_symbol_ohlc → price_series[-1].close",
            "quote": "fetch_symbol_quote → last (same symbol, separate HTTP 路徑於 /quote)",
        },
    }
    bar = _last_ohlc_bar(price_series)
    if not bar or bar.get("close") is None:
        out["quote_error"] = "no_ohlc_close"
        return out
    try:
        ohlc_close = float(bar["close"])
    except (TypeError, ValueError):
        out["quote_error"] = "ohlc_close_unparseable"
        return out
    out["ohlc_last_close"] = ohlc_close

    try:
        q = fetch_symbol_quote(normalized_symbol)
    except Exception as exc:  # pragma: no cover - defensive
        out["quote_error"] = f"quote_fetch:{exc.__class__.__name__}"
        return out

    if q.get("error"):
        out["quote_error"] = str(q.get("error"))
        return out
    if q.get("last") is None:
        out["quote_error"] = "quote_last_null"
        return out

    try:
        ql = float(q["last"])
    except (TypeError, ValueError):
        out["quote_error"] = "quote_last_unparseable"
        return out

    out["quote_last"] = ql
    diff = abs(ohlc_close - ql)
    out["abs_diff"] = round(diff, 8)
    denom = max(abs(ohlc_close), 1e-12)
    out["rel_diff"] = round(diff / denom, 8)
    out["aligned"] = diff <= max(1e-6, 1e-4 * denom)
    return out


def _price_alignment_e2e_overrides() -> dict[str, dict[str, Any]]:
    """Optional JSON map for Playwright / staging: force OHLC vs quote numbers without yfinance.

    Env ``PRICE_ALIGNMENT_E2E_OVERRIDES`` example::

        {"NVDA":{"ohlc_last_close":100,"quote_last":105.5}}

    Keys are uppercased symbols. Values may include ``ohlc_last_close`` and/or ``quote_last`` floats.
    """
    raw = (os.getenv("PRICE_ALIGNMENT_E2E_OVERRIDES") or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("PRICE_ALIGNMENT_E2E_OVERRIDES is not valid JSON; ignoring")
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in data.items():
        sym = str(k).strip().upper()
        if sym and isinstance(v, dict):
            out[sym] = v
    return out


def _apply_price_alignment_e2e_override(normalized_symbol: str, align: dict[str, Any]) -> None:
    ov = _price_alignment_e2e_overrides().get(normalized_symbol)
    if not ov:
        return
    ohlc_v = ov.get("ohlc_last_close")
    quote_v = ov.get("quote_last")
    try:
        ohlc_close = float(ohlc_v) if ohlc_v is not None else align.get("ohlc_last_close")
        ql = float(quote_v) if quote_v is not None else align.get("quote_last")
    except (TypeError, ValueError):
        return
    if ohlc_close is None or ql is None:
        return
    align["ohlc_last_close"] = ohlc_close
    align["quote_last"] = ql
    diff = abs(ohlc_close - ql)
    align["abs_diff"] = round(diff, 8)
    denom = max(abs(ohlc_close), 1e-12)
    align["rel_diff"] = round(diff / denom, 8)
    align["aligned"] = diff <= max(1e-6, 1e-4 * denom)
    align["quote_error"] = None
    align["e2e_override"] = True


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

    align = _align_snapshot_price(normalized_symbol, price_series)
    _apply_price_alignment_e2e_override(normalized_symbol, align)

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
        "price_alignment": {
            "ohlc_vs_quote": align,
            "note": (
                "KPI（latest_metrics）來自 BigQuery；OHLC 與 /quote 之 last 皆來自 yfinance。"
                " 不一致多為快取邊界或資料延遲；跨「BQ 數字 vs yfinance 數字」目前無單一自動對齊欄位。"
            ),
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
        "price_alignment": align,
    }
