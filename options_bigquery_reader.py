"""BigQuery read operations for the options flow + GEX Portal API.

Read path is kept separate from :mod:`options_bigquery_writer` (same convention as
``tracker.py`` reads vs ``bigquery_writer.py`` writes). Every function degrades to
an empty result when the table env is unset, BigQuery is unavailable, or the query
fails — the API layer turns that into a stable ``enabled: false`` envelope rather
than fabricating numbers (無數據幻覺紅線).
"""

from __future__ import annotations

import logging
from typing import Any

from config import (
    OPTIONS_GEX_BY_STRIKE_TABLE,
    OPTIONS_GEX_HISTORY_TABLE,
    OPTIONS_UNUSUAL_TRADES_TABLE,
)

logger = logging.getLogger(__name__)


def tables_configured() -> bool:
    """True when at least the GEX history table is set (BQ read path enabled)."""
    return bool(OPTIONS_GEX_HISTORY_TABLE)


def _query(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    try:
        from google.cloud import bigquery

        project = OPTIONS_GEX_HISTORY_TABLE.split(".", 1)[0]
        client = bigquery.Client(project=project)
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        )
        return [dict(row) for row in job.result()]
    except Exception as exc:  # noqa: BLE001 — read telemetry must never crash the API
        logger.warning("options BQ read failed: %s", exc)
        return []


def read_latest_gex(underlyings: list[str]) -> dict[str, dict[str, Any]]:
    """Latest GEX row per underlying. Returns {} when unavailable."""
    if not OPTIONS_GEX_HISTORY_TABLE or not underlyings:
        return {}
    from google.cloud import bigquery

    sql = f"""
        SELECT * EXCEPT(rn) FROM (
          SELECT *, ROW_NUMBER() OVER (
            PARTITION BY underlying ORDER BY trade_date DESC, computed_at DESC
          ) AS rn
          FROM `{OPTIONS_GEX_HISTORY_TABLE}`
          WHERE underlying IN UNNEST(@symbols)
        ) WHERE rn = 1
    """
    rows = _query(sql, [bigquery.ArrayQueryParameter("symbols", "STRING", underlyings)])
    return {str(r.get("underlying")): r for r in rows if r.get("underlying")}


def read_gex_history(underlying: str, days: int = 60) -> list[dict[str, Any]]:
    """GEX time series for one underlying (oldest→newest), for charting."""
    if not OPTIONS_GEX_HISTORY_TABLE or not underlying:
        return []
    from google.cloud import bigquery

    sql = f"""
        SELECT trade_date, total_gex, call_gex, put_gex, spot_price
        FROM `{OPTIONS_GEX_HISTORY_TABLE}`
        WHERE underlying = @underlying
          AND trade_date >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
        ORDER BY trade_date ASC
    """
    return _query(
        sql,
        [
            bigquery.ScalarQueryParameter("underlying", "STRING", underlying),
            bigquery.ScalarQueryParameter("days", "INT64", days),
        ],
    )


def read_latest_by_strike(underlying: str) -> list[dict[str, Any]]:
    """Latest trade_date's per-strike GEX rows (strike asc). [] when unset/empty."""
    if not OPTIONS_GEX_BY_STRIKE_TABLE or not underlying:
        return []
    from google.cloud import bigquery

    sql = f"""
        SELECT strike, call_gex, put_gex, net_gex
        FROM `{OPTIONS_GEX_BY_STRIKE_TABLE}`
        WHERE underlying = @underlying
          AND trade_date = (
            SELECT MAX(trade_date) FROM `{OPTIONS_GEX_BY_STRIKE_TABLE}` WHERE underlying = @underlying
          )
        ORDER BY strike ASC
    """
    return _query(sql, [bigquery.ScalarQueryParameter("underlying", "STRING", underlying)])


def read_recent_unusual(underlying: str, limit: int = 50) -> list[dict[str, Any]]:
    """Most recent unusual-flow signals for one underlying."""
    if not OPTIONS_UNUSUAL_TRADES_TABLE or not underlying:
        return []
    from google.cloud import bigquery

    sql = f"""
        SELECT trade_date, option_ticker, signal_type, score, premium, volume,
               open_interest, rationale, as_of
        FROM `{OPTIONS_UNUSUAL_TRADES_TABLE}`
        WHERE underlying = @underlying
        ORDER BY trade_date DESC, score DESC
        LIMIT @limit
    """
    return _query(
        sql,
        [
            bigquery.ScalarQueryParameter("underlying", "STRING", underlying),
            bigquery.ScalarQueryParameter("limit", "INT64", limit),
        ],
    )
