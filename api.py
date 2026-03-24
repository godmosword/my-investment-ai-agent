"""FastAPI backend for Q-Silicon Investment Report PWA.

Exposes daily metrics, trade recommendations, and report summaries
stored in BigQuery for consumption by the React PWA frontend.

Usage:
    uvicorn api:app --reload --port 8000
"""

import logging
import os
from datetime import date, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Q-Silicon Investment API",
    description="Daily crypto/AI investment report data API",
    version="1.0.0",
)

# Allow local dev (Vite) and same-origin production
_CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:4173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ── BigQuery client singleton ───────────────────────────────────────────────
_bq_client: bigquery.Client | None = None


def _get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def _rows_to_dicts(rows) -> list[dict[str, Any]]:
    """Convert BigQuery RowIterator rows to JSON-serialisable dicts."""
    result = []
    for row in rows:
        d = dict(row)
        for k, v in d.items():
            if isinstance(v, (datetime, date)):
                d[k] = v.isoformat()
        result.append(d)
    return result


# ── /api/metrics ─────────────────────────────────────────────────────────────

@app.get("/api/metrics/latest")
def get_metrics_latest() -> dict[str, Any]:
    """Return the most recent daily_metrics row with day-over-day deltas."""
    try:
        client = _get_bq_client()
        rows = list(client.query(f"""
            SELECT
                timestamp, dxy, etf_flow_millions, avg_risk_score,
                mvrv_z_score, sentiment_score, sopr, exchange_netflow,
                regime_score, grok_summary, gpt_summary
            FROM `{METRICS_TABLE}`
            ORDER BY timestamp DESC
            LIMIT 2
        """).result())
    except Exception as exc:
        logger.error("BigQuery metrics/latest failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No metrics data found")

    latest = dict(rows[0])
    prev = dict(rows[1]) if len(rows) > 1 else None

    # Serialise timestamps
    for k, v in latest.items():
        if isinstance(v, (datetime, date)):
            latest[k] = v.isoformat()

    # Compute deltas
    delta_keys = ["dxy", "etf_flow_millions", "avg_risk_score", "mvrv_z_score"]
    deltas: dict[str, float | None] = {}
    if prev:
        for k in delta_keys:
            cur, old = latest.get(k), prev.get(k)
            if cur is not None and old is not None:
                try:
                    deltas[f"delta_{k}"] = round(float(cur) - float(old), 4)
                except (TypeError, ValueError):
                    deltas[f"delta_{k}"] = None
            else:
                deltas[f"delta_{k}"] = None
    else:
        for k in delta_keys:
            deltas[f"delta_{k}"] = None

    return {**latest, **deltas}


@app.get("/api/metrics/history")
def get_metrics_history(
    days: int = Query(default=30, ge=7, le=180),
) -> list[dict[str, Any]]:
    """Return historical daily_metrics for the past N days (default 30)."""
    try:
        client = _get_bq_client()
        rows = client.query(f"""
            SELECT
                timestamp, dxy, etf_flow_millions, avg_risk_score,
                mvrv_z_score, sentiment_score, sopr, exchange_netflow,
                regime_score
            FROM `{METRICS_TABLE}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {days} DAY)
            ORDER BY timestamp ASC
        """).result()
    except Exception as exc:
        logger.error("BigQuery metrics/history failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    return _rows_to_dicts(rows)


# ── /api/reports ─────────────────────────────────────────────────────────────

@app.get("/api/reports")
def list_reports(
    limit: int = Query(default=30, ge=1, le=90),
) -> list[dict[str, Any]]:
    """List recent daily reports (summary cards).

    Each entry contains the date, key metrics snapshot, and agent
    summaries (grok_summary, gpt_summary) — the full report text is
    accessible via Telegram; this endpoint provides the structured
    data layer for the PWA archive view.
    """
    try:
        client = _get_bq_client()
        rows = client.query(f"""
            SELECT
                DATE(timestamp) AS report_date,
                timestamp,
                dxy,
                etf_flow_millions,
                avg_risk_score,
                mvrv_z_score,
                regime_score,
                sentiment_score,
                grok_summary,
                gpt_summary,
                news_titles
            FROM `{METRICS_TABLE}`
            ORDER BY timestamp DESC
            LIMIT {limit}
        """).result()
    except Exception as exc:
        logger.error("BigQuery reports list failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    return _rows_to_dicts(rows)


@app.get("/api/reports/{report_date}")
def get_report(report_date: str) -> dict[str, Any]:
    """Return the report summary for a specific date (YYYY-MM-DD)."""
    # Validate date format
    try:
        datetime.strptime(report_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format; use YYYY-MM-DD") from exc

    try:
        client = _get_bq_client()
        rows = list(client.query(f"""
            SELECT
                DATE(timestamp) AS report_date,
                timestamp,
                dxy,
                etf_flow_millions,
                avg_risk_score,
                mvrv_z_score,
                regime_score,
                sentiment_score,
                sopr,
                exchange_netflow,
                grok_summary,
                gpt_summary,
                news_titles
            FROM `{METRICS_TABLE}`
            WHERE DATE(timestamp) = '{report_date}'
            ORDER BY timestamp DESC
            LIMIT 1
        """).result())
    except Exception as exc:
        logger.error("BigQuery report/%s failed: %s", report_date, exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        raise HTTPException(status_code=404, detail=f"No report found for {report_date}")

    report = _rows_to_dicts(rows)[0]

    # Attach that day's trade recommendations
    try:
        rec_rows = client.query(f"""
            SELECT
                asset, direction, entry_price, target_price, stop_price,
                confidence, narrative, trigger, invalidation,
                position_pct, timeframe, category,
                status, exit_price, exit_date, pnl_pct, rr_ratio
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date = '{report_date}'
            ORDER BY confidence DESC, asset ASC
        """).result()
        report["recommendations"] = _rows_to_dicts(rec_rows)
    except Exception as exc:
        logger.warning("Could not attach recommendations for %s: %s", report_date, exc)
        report["recommendations"] = []

    return report


# ── /api/trades ──────────────────────────────────────────────────────────────

@app.get("/api/trades")
def list_trades(
    status: str | None = Query(default=None, description="Filter: OPEN, HIT_TARGET, HIT_STOP, EXPIRED"),
    days: int = Query(default=60, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Return trade recommendations with optional status filter."""
    where_clauses = [
        f"report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)"
    ]
    if status:
        valid_statuses = {"OPEN", "HIT_TARGET", "HIT_STOP", "EXPIRED"}
        if status.upper() not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid_statuses}")
        where_clauses.append(f"status = '{status.upper()}'")

    where_sql = " AND ".join(where_clauses)

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

    return _rows_to_dicts(rows)


@app.get("/api/trades/performance")
def get_trades_performance(
    days: int = Query(default=90, ge=7, le=365),
) -> dict[str, Any]:
    """Return aggregated trade performance statistics."""
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
        stats["by_category"] = _rows_to_dicts(cat_rows)
    except Exception as exc:
        logger.warning("Could not fetch category breakdown: %s", exc)
        stats["by_category"] = []

    return stats


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
