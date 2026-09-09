"""Daily metrics endpoints — JSONL first, BigQuery optional."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api_deps import get_bq_client, rows_to_dicts, skip_bigquery
from config import METRICS_TABLE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

_METRICS_JSONL = "daily_metrics.jsonl"
_DELTA_KEYS = [
    "dxy",
    "etf_flow_millions",
    "avg_risk_score",
    "mvrv_z_score",
    "sentiment_score",
    "sopr",
    "exchange_netflow",
    "regime_score",
]
_LATEST_KEYS = [
    "timestamp",
    *_DELTA_KEYS,
    "grok_summary",
    "gpt_summary",
]
_HISTORY_KEYS = ["timestamp", *_DELTA_KEYS]


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _load_metrics_jsonl_newest_first() -> list[dict[str, Any]]:
    from state_store import read_jsonl

    dated: list[tuple[datetime, dict[str, Any]]] = []
    for row in read_jsonl(_METRICS_JSONL):
        if not isinstance(row, dict):
            continue
        parsed = _parse_ts(row.get("timestamp"))
        if parsed is None:
            continue
        dated.append((parsed, row))
    dated.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in dated]


def _pick(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in keys:
        value = row.get(key)
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _with_deltas(serialised: list[dict[str, Any]]) -> dict[str, Any]:
    latest = serialised[0]
    prev = serialised[1] if len(serialised) > 1 else None
    deltas: dict[str, float | None] = {}
    if prev:
        for key in _DELTA_KEYS:
            cur, old = latest.get(key), prev.get(key)
            if cur is not None and old is not None:
                try:
                    deltas[f"delta_{key}"] = round(float(cur) - float(old), 4)
                except (TypeError, ValueError):
                    deltas[f"delta_{key}"] = None
            else:
                deltas[f"delta_{key}"] = None
    else:
        for key in _DELTA_KEYS:
            deltas[f"delta_{key}"] = None
    return {**latest, **deltas}


@router.get("/latest")
def get_metrics_latest() -> dict[str, Any]:
    """Return the most recent daily_metrics row with day-over-day deltas."""
    jsonl_rows = _load_metrics_jsonl_newest_first()
    if jsonl_rows:
        serialised = [_pick(row, _LATEST_KEYS) for row in jsonl_rows[:2]]
        return _with_deltas(serialised)

    if skip_bigquery():
        raise HTTPException(status_code=404, detail="No metrics data found")

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

    return _with_deltas(rows_to_dicts(rows))


@router.get("/history")
def get_metrics_history(
    days: int = Query(default=30, ge=7, le=180),
) -> list[dict[str, Any]]:
    """Return historical daily_metrics for the past N days (default 30)."""
    jsonl_rows = _load_metrics_jsonl_newest_first()
    if jsonl_rows:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        window = [
            row
            for row in reversed(jsonl_rows)
            if (parsed := _parse_ts(row.get("timestamp"))) is not None and parsed >= cutoff
        ]
        return [_pick(row, _HISTORY_KEYS) for row in window]

    if skip_bigquery():
        return []

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
