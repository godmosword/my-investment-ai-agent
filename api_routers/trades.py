"""``/api/trades*``, positions, analysis, and quant routes — single slice file.

Bucket for trades + positions + analysis + quant (no ``analysis.py`` /
``quant.py`` split). Moved verbatim from ``api.py``: paths, query bounds,
payload keys, and error codes unchanged. Declaration order is load-bearing
as moved.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api_deps import get_bq_client as _bq_singleton
from api_deps import rows_to_dicts, skip_bigquery
from config import RECOMMENDATIONS_TABLE
from execution_intents import latest_execution_intents
from symbol_snapshot_service import (
    build_symbol_snapshot,
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)
from track_record import normalize_closed_intent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["trades"])


def _get_bq_client() -> Any:
    """BQ client accessor; tests monkeypatch ``api_routers.trades._get_bq_client``."""
    return _bq_singleton()


_RECS_JSONL = "trade_recommendations.jsonl"


def _as_iso_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            date.fromisoformat(text[:10])
        except ValueError:
            return None
        return text[:10]
    return None


def _json_serialise_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def _fetch_trades_from_jsonl(
    *,
    status: str | None,
    days: int,
    limit: int,
) -> list[dict[str, Any]]:
    from state_store import read_jsonl

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    wanted = status.upper() if status else None
    rows: list[dict[str, Any]] = []
    for raw in read_jsonl(_RECS_JSONL):
        if not isinstance(raw, dict):
            continue
        report_date = _as_iso_date(raw.get("report_date"))
        if report_date is None:
            continue
        try:
            parsed = date.fromisoformat(report_date)
        except ValueError:
            continue
        if parsed < cutoff:
            continue
        row_status = str(raw.get("status") or "").upper()
        if wanted and row_status != wanted:
            continue
        serialised = {key: _json_serialise_value(value) for key, value in raw.items()}
        if "entry_price" not in serialised and "entry" in serialised:
            serialised["entry_price"] = serialised["entry"]
        if "target_price" not in serialised and "target" in serialised:
            serialised["target_price"] = serialised["target"]
        if "stop_price" not in serialised and "stop" in serialised:
            serialised["stop_price"] = serialised["stop"]
        rows.append(serialised)
    rows.sort(
        key=lambda row: (str(row.get("report_date") or ""), float(row.get("confidence") or 0)),
        reverse=True,
    )
    return rows[:limit]


# ── /api/trades ──────────────────────────────────────────────────────────────


def _fetch_trades(
    *,
    status: str | None,
    days: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Load recommendation rows from BigQuery (shared by /api/trades and /api/positions/open)."""
    where_clauses = [
        f"report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
    ]
    if status:
        valid_statuses = {"OPEN", "HIT_TARGET", "HIT_STOP", "EXPIRED"}
        if status.upper() not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")
        where_clauses.append(f"status = '{status.upper()}'")

    where_sql = " AND ".join(where_clauses)

    jsonl_rows = _fetch_trades_from_jsonl(status=status, days=days, limit=limit)
    if jsonl_rows:
        return jsonl_rows
    if skip_bigquery():
        return []

    try:
        client = _get_bq_client()
        rows = client.query(f"""
            SELECT
                report_date, asset, direction, category,
                entry_price, target_price, stop_price,
                confidence, narrative, trigger, invalidation,
                position_pct, timeframe, rr_ratio,
                status, exit_price, exit_date, pnl_pct, days_held,
                regime_at_signal, created_at
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE {where_sql}
            ORDER BY report_date DESC, confidence DESC
            LIMIT {limit}
        """).result()
    except Exception as exc:
        logger.error("BigQuery trades failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    return rows_to_dicts(rows)


@router.get("/api/trades")
def list_trades(
    status: str | None = Query(default=None, description="Filter: OPEN, HIT_TARGET, HIT_STOP, EXPIRED"),
    days: int = Query(default=60, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Return trade recommendations with optional status filter."""
    return _fetch_trades(status=status, days=days, limit=limit)


@router.get("/api/positions/open")
def list_open_positions(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """OPEN positions only (portfolio health / PWA 部位紅綠燈)."""
    return _fetch_trades(status="OPEN", days=days, limit=limit)


@router.get("/api/positions")
def list_positions_m4(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(
        default=None,
        description="Optional status filter (e.g. OPEN). Defaults to OPEN when omitted.",
    ),
) -> list[dict[str, Any]]:
    """Positions list (M4). Defaults to OPEN when ``status`` is omitted."""
    st = (status or "OPEN").strip().upper() or "OPEN"
    return _fetch_trades(status=st, days=days, limit=limit)


@router.get("/api/analysis/{symbol}")
def get_analysis_bundle_m6(
    symbol: str,
    days: int = Query(default=30, ge=7, le=180),
    recommendation_limit: int = Query(default=12, ge=1, le=40),
) -> dict[str, Any]:
    """Analysis bundle (M6): quote + optional BigQuery snapshot (errors surfaced, no 503 on BQ-only failure)."""
    norm = _validate_symbol(symbol)
    quote_raw = fetch_symbol_quote(norm)
    snap: dict[str, Any] | None = None
    snap_error: str | None = None
    if skip_bigquery():
        return {"symbol": norm, "quote": quote_raw, "snapshot": None, "snapshot_error": None}
    try:
        client = _get_bq_client()
        snap = build_symbol_snapshot(
            client,
            norm,
            days=days,
            recommendation_limit=recommendation_limit,
        )
    except Exception as exc:  # noqa: BLE001
        snap_error = str(exc)
        logger.warning("analysis bundle snapshot failed for %s: %s", norm, exc)
    return {"symbol": norm, "quote": quote_raw, "snapshot": snap, "snapshot_error": snap_error}


@router.get("/api/quant/signals")
def list_quant_signals_m7() -> dict[str, Any]:
    """Quant signals (M7). Educational only — no auto-trading or performance claims."""
    rows = latest_execution_intents(limit=100, dedupe=True, sort_by="updated_desc")
    active_statuses = {"PENDING_REVIEW", "APPROVED_FOR_PAPER", "PAPER_SUBMITTED", "PAPER_FILLED"}
    signals: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "").strip().upper()
        symbol = str(row.get("asset") or "").strip().upper().lstrip("$")
        direction = str(row.get("direction") or "").strip().lower()
        if status not in active_statuses or not symbol:
            continue
        try:
            confidence = max(0.0, min(1.0, float(row.get("star_rating") or 0) / 2.0))
        except (TypeError, ValueError):
            confidence = 0.0
        signals.append(
            {
                "id": row.get("signal_id") or f"{symbol}-{status}".lower(),
                "symbol": symbol,
                "asset": symbol,
                "label": row.get("thesis_one_liner") or f"{symbol} {direction or 'signal'}",
                "direction": direction or "neutral",
                "confidence": round(confidence, 3),
                "status": status,
                "category": row.get("category") or "",
                "created_at": row.get("created_at") or "",
                "updated_at": row.get("status_updated_at") or row.get("created_at") or "",
                "quality": row.get("quality_grade") or row.get("quality") or None,
                "reference_entry_price": row.get("reference_entry_price"),
                "reference_target_price": row.get("reference_target_price"),
                "reference_stop_price": row.get("reference_stop_price"),
            }
        )
    if signals:
        return {
            "disclaimer": "Paper / educational only; no performance guarantee; not investment advice.",
            "source": "execution_intents.jsonl",
            "count": len(signals),
            "signals": signals,
        }
    return {
        "disclaimer": "Paper / educational only; no performance guarantee; not investment advice.",
        "source": "placeholder",
        "count": 1,
        "signals": [
            {
                "id": "placeholder-neutral",
                "symbol": "",
                "label": "RSI14 neutral band (example)",
                "direction": "neutral",
                "confidence": 0.0,
            },
        ],
    }


@router.get("/api/quant/backtest")
def get_quant_backtest(
    symbol: str = Query(..., description="Ticker symbol, e.g. BTC or SPY"),
    start_date: str | None = Query(default=None, description="YYYY-MM-DD start (optional)"),
    end_date: str | None = Query(default=None, description="YYYY-MM-DD end (optional)"),
) -> dict[str, Any]:
    """Backtest v1 (Q33 M7). Builds a deterministic paper curve from closed execution intents.

    Disabled unless ``QUANT_BACKTEST_ENABLED=1``.
    Not investment advice; does not auto-trade.
    """
    if os.getenv("QUANT_BACKTEST_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="Backtest disabled; set QUANT_BACKTEST_ENABLED=1")
    norm = _validate_symbol(symbol)
    rows = latest_execution_intents(limit=1000, dedupe=True, sort_by="updated_desc")
    records = []
    for row in rows:
        if str(row.get("asset") or "").strip().upper().lstrip("$") != norm:
            continue
        record = normalize_closed_intent(row)
        if record is None:
            continue
        closed_at = str(record.get("closed_at") or "")
        closed_day = closed_at[:10]
        if start_date and closed_day and closed_day < start_date:
            continue
        if end_date and closed_day and closed_day > end_date:
            continue
        records.append(record)
    records.sort(key=lambda record: str(record.get("closed_at") or record.get("opened_at") or ""))

    value = 10_000.0
    equity_curve = [{"date": start_date or "start", "value": round(value, 2)}]
    peak = value
    max_drawdown = 0.0
    returns = []
    for record in records:
        ret = float(record["return_pct"]) / 100.0
        returns.append(ret)
        value *= 1.0 + ret
        peak = max(peak, value)
        drawdown = (peak - value) / peak if peak > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        equity_curve.append(
            {
                "date": str(record.get("closed_at") or record.get("opened_at") or "")[:10] or f"trade_{len(equity_curve)}",
                "value": round(value, 2),
                "signal_id": record.get("signal_id"),
                "return_pct": round(float(record["return_pct"]), 4),
            }
        )
    total_return = (value - 10_000) / 10_000
    if len(returns) > 1:
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        stdev = variance ** 0.5
        sharpe = mean / stdev * (len(returns) ** 0.5) if stdev > 0 else 0.0
    else:
        sharpe = 0.0
    return {
        "symbol": norm,
        "start_date": start_date,
        "end_date": end_date,
        "equity_curve": equity_curve,
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_drawdown, 4),
        "sharpe": round(sharpe, 3),
        "trade_count": len(records),
        "source": "execution_intents.jsonl",
        "disclaimer": "Paper-derived backtest; educational only; not investment advice.",
    }


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _performance_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def status_of(row: dict[str, Any]) -> str:
        return str(row.get("status") or "").upper()

    total = len(rows)
    wins = sum(1 for row in rows if status_of(row) == "HIT_TARGET")
    losses = sum(1 for row in rows if status_of(row) == "HIT_STOP")
    expired = sum(1 for row in rows if status_of(row) == "EXPIRED")
    open_count = sum(1 for row in rows if status_of(row) == "OPEN")
    closed = [row for row in rows if status_of(row) in {"HIT_TARGET", "HIT_STOP", "EXPIRED"}]
    pnls = [value for row in closed if (value := _safe_float(row.get("pnl_pct"))) is not None]
    rrs = [value for row in rows if (value := _safe_float(row.get("rr_ratio"))) is not None]
    decided = wins + losses

    by_cat: dict[str, dict[str, Any]] = {}
    for row in rows:
        category = row.get("category")
        if not category:
            continue
        bucket = by_cat.setdefault(category, {"total": 0, "wins": 0, "pnls": []})
        bucket["total"] += 1
        if status_of(row) == "HIT_TARGET":
            bucket["wins"] += 1
        if status_of(row) in {"HIT_TARGET", "HIT_STOP", "EXPIRED"}:
            pnl = _safe_float(row.get("pnl_pct"))
            if pnl is not None:
                bucket["pnls"].append(pnl)
    by_category: list[dict[str, Any]] = []
    for category in sorted(by_cat):
        bucket = by_cat[category]
        cat_decided = sum(
            1
            for row in rows
            if row.get("category") == category and status_of(row) in {"HIT_TARGET", "HIT_STOP"}
        )
        pnls_cat: list[float] = bucket["pnls"]
        by_category.append(
            {
                "category": category,
                "total": bucket["total"],
                "wins": bucket["wins"],
                "win_rate_pct": round(bucket["wins"] / cat_decided * 100, 1) if cat_decided else None,
                "avg_pnl_pct": round(sum(pnls_cat) / len(pnls_cat), 2) if pnls_cat else None,
            }
        )

    daily: dict[str, float] = {}
    for row in closed:
        day = _as_iso_date(row.get("exit_date"))
        pnl = _safe_float(row.get("pnl_pct"))
        if day and pnl is not None:
            daily[day] = daily.get(day, 0.0) + pnl
    curve: list[dict[str, Any]] = []
    cumulative = 0.0
    for day in sorted(daily):
        cumulative += daily[day]
        curve.append({"date": day, "cumulative_pnl": round(cumulative, 2)})

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "expired": expired,
        "open_count": open_count,
        "avg_pnl_pct": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "avg_rr": round(sum(rrs) / len(rrs), 2) if rrs else None,
        "max_loss_pct": round(min(pnls), 2) if pnls else None,
        "max_gain_pct": round(max(pnls), 2) if pnls else None,
        "win_rate_pct": round(wins / decided * 100, 1) if decided else None,
        "by_category": by_category,
        "equity_curve": curve,
    }


@router.get("/api/trades/performance")
def get_trades_performance(
    days: int = Query(default=90, ge=7, le=365),
) -> dict[str, Any]:
    """Return aggregated trade performance statistics."""
    jsonl_rows = _fetch_trades_from_jsonl(status=None, days=days, limit=10_000)
    if jsonl_rows or skip_bigquery():
        return _performance_from_rows(jsonl_rows)

    try:
        client = _get_bq_client()
        rows = list(client.query(f"""
            SELECT
                COUNT(*)                                                AS total,
                COUNTIF(status = 'HIT_TARGET')                         AS wins,
                COUNTIF(status = 'HIT_STOP')                           AS losses,
                COUNTIF(status = 'EXPIRED')                            AS expired,
                COUNTIF(status = 'OPEN')                               AS open_count,
                ROUND(AVG(CASE WHEN status IN ('HIT_TARGET','HIT_STOP','EXPIRED')
                               THEN pnl_pct END), 2)                   AS avg_pnl_pct,
                ROUND(AVG(rr_ratio), 2)                                AS avg_rr,
                ROUND(MIN(pnl_pct), 2)                                 AS max_loss_pct,
                ROUND(MAX(pnl_pct), 2)                                 AS max_gain_pct,
                ROUND(SAFE_DIVIDE(
                    COUNTIF(status = 'HIT_TARGET'),
                    COUNTIF(status IN ('HIT_TARGET','HIT_STOP'))
                ) * 100, 1)                                            AS win_rate_pct
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
        """).result())
    except Exception as exc:
        logger.error("BigQuery trades/performance failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        return {}

    stats = dict(rows[0])

    # Per-category breakdown
    try:
        cat_rows = client.query(f"""
            SELECT
                category,
                COUNT(*) AS total,
                COUNTIF(status = 'HIT_TARGET') AS wins,
                ROUND(SAFE_DIVIDE(
                    COUNTIF(status = 'HIT_TARGET'),
                    COUNTIF(status IN ('HIT_TARGET','HIT_STOP'))
                ) * 100, 1) AS win_rate_pct,
                ROUND(AVG(CASE WHEN status IN ('HIT_TARGET','HIT_STOP','EXPIRED')
                               THEN pnl_pct END), 2) AS avg_pnl_pct
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
              AND category IS NOT NULL
            GROUP BY category
            ORDER BY category
        """).result()
        stats["by_category"] = rows_to_dicts(cat_rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch category breakdown: %s", exc)
        stats["by_category"] = []

    try:
        eq_rows = client.query(f"""
            WITH closed_trades AS (
              SELECT exit_date AS d, pnl_pct
              FROM `{RECOMMENDATIONS_TABLE}`
              WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
                AND status IN ('HIT_TARGET', 'HIT_STOP', 'EXPIRED')
                AND exit_date IS NOT NULL
                AND pnl_pct IS NOT NULL
            ),
            daily_sum AS (
              SELECT d, SUM(pnl_pct) AS day_pnl
              FROM closed_trades
              GROUP BY d
            )
            SELECT
              d AS `date`,
              SUM(day_pnl) OVER (ORDER BY d ROWS UNBOUNDED PRECEDING) AS cumulative_pnl
            FROM daily_sum
            ORDER BY d
        """).result()
        stats["equity_curve"] = rows_to_dicts(eq_rows)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not fetch equity curve: %s", exc)
        stats["equity_curve"] = []

    return stats


def _validate_symbol(symbol: str) -> str:
    try:
        return validate_symbol_for_snapshot(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
