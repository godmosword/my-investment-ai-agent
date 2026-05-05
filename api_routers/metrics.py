"""BigQuery-backed daily metrics endpoints (mounted from ``api.py``)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api_deps import get_bq_client, rows_to_dicts
from config import METRICS_TABLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/latest")
def get_metrics_latest() -> dict[str, Any]:
    """Return the most recent daily_metrics row with day-over-day deltas."""
    try:
        client = get_bq_client()
        rows = list(
            client.query(
                f"""
            SELECT
                timestamp, dxy, etf_flow_millions, avg_risk_score,
                mvrv_z_score, sentiment_score, sopr, exchange_netflow,
                regime_score, grok_summary, gpt_summary
            FROM `{METRICS_TABLE}`
            ORDER BY timestamp DESC
            LIMIT 2
        """
            ).result()
        )
    except Exception as exc:
        logger.error("BigQuery metrics/latest failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        raise HTTPException(status_code=404, detail="No metrics data found")

    serialised = rows_to_dicts(rows)
    latest = serialised[0]
    prev = serialised[1] if len(serialised) > 1 else None

    delta_keys = [
        "dxy",
        "etf_flow_millions",
        "avg_risk_score",
        "mvrv_z_score",
        "sentiment_score",
        "sopr",
        "exchange_netflow",
        "regime_score",
    ]
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


@router.get("/history")
def get_metrics_history(
    days: int = Query(default=30, ge=7, le=180),
) -> list[dict[str, Any]]:
    """Return historical daily_metrics for the past N days (default 30)."""
    try:
        client = get_bq_client()
        rows = client.query(
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
    except Exception as exc:
        logger.error("BigQuery metrics/history failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    return rows_to_dicts(rows)
