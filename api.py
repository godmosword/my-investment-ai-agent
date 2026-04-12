"""FastAPI backend for Q-Silicon Investment Report PWA.

Exposes daily metrics, trade recommendations, and report summaries
stored in BigQuery for consumption by the React PWA frontend.

Usage:
    uvicorn api:app --reload --port 8000
"""

import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from google.cloud import bigquery
from pydantic import BaseModel, Field

from config import PROJECT_ID, METRICS_TABLE, RECOMMENDATIONS_TABLE
from execution_intents import (
    ALLOWED_INTENT_STATUSES,
    latest_execution_intents,
    update_execution_intent_status,
)
from symbol_snapshot_service import (
    build_symbol_snapshot,
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)

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
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
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
        result.append(
            {k: v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in row.items()}
        )
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

    serialised = _rows_to_dicts(rows)
    latest = serialised[0]
    prev = serialised[1] if len(serialised) > 1 else None

    # Compute deltas（與 PWA Today 第二排 KPI 對齊）
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


@app.get("/api/trades")
def list_trades(
    status: str | None = Query(default=None, description="Filter: OPEN, HIT_TARGET, HIT_STOP, EXPIRED"),
    days: int = Query(default=60, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Return trade recommendations with optional status filter."""
    return _fetch_trades(status=status, days=days, limit=limit)


@app.get("/api/positions/open")
def list_open_positions(
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[dict[str, Any]]:
    """OPEN positions only (portfolio health / PWA 部位紅綠燈)."""
    return _fetch_trades(status="OPEN", days=days, limit=limit)


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
        stats["equity_curve"] = _rows_to_dicts(eq_rows)
    except Exception as exc:
        logger.warning("Could not fetch equity curve: %s", exc)
        stats["equity_curve"] = []

    return stats


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


class WebPushSubscribeBody(BaseModel):
    """預留 Web Push 訂閱 payload（與 browser PushSubscription JSON 對齊）。"""

    endpoint: str = Field(..., max_length=4096)
    keys: dict[str, str] | None = None


class WarRoomSnapshot(BaseModel):
    gate_failure: dict[str, Any] | None = None
    scratchpad: dict[str, Any] | None = None
    execution_intents: list[dict[str, Any]] = Field(default_factory=list)


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


class ExecutionIntentStatusBody(BaseModel):
    """Human / War Room workflow: advance intent lifecycle (no order placement)."""

    status: str = Field(..., description="One of ALLOWED_INTENT_STATUSES (case-insensitive).")
    note: str = Field(default="", max_length=2000)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent


def _read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Could not read JSON file %s: %s", path, exc)
        return None


def _latest_scratchpad_summary() -> dict[str, Any] | None:
    scratchpad_dir = _repo_root() / ".qsilicon" / "scratchpad"
    if not scratchpad_dir.is_dir():
        return None
    files = sorted(scratchpad_dir.glob("*.jsonl"))
    if not files:
        return None
    latest = files[-1]
    try:
        lines = [
            json.loads(line)
            for line in latest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("Could not read scratchpad %s: %s", latest, exc)
        return None
    if not lines:
        return {"path": str(latest), "events": []}
    init_event = next((line for line in lines if line.get("type") == "init"), None)
    gate_events = [line for line in lines if line.get("type") == "gate_result"]
    final_event = next((line for line in reversed(lines) if line.get("type") == "run_end"), None)
    return {
        "path": str(latest),
        "run_id": lines[0].get("runId"),
        "event_count": len(lines),
        "init_meta": (init_event or {}).get("meta", {}),
        "latest_gate_result": gate_events[-1] if gate_events else None,
        "final_status": (final_event or {}).get("status"),
        "final_event": final_event,
    }


def _latest_gate_failure_summary() -> dict[str, Any] | None:
    out_dir = _repo_root() / ".qsilicon" / "last_gate_failure"
    summary = _read_json_if_exists(out_dir / "validation_summary.json")
    if summary is None:
        return None
    issues_path = out_dir / "issues.txt"
    return {
        **summary,
        "issues_path": str(issues_path) if issues_path.is_file() else None,
        "artifact_dir": str(out_dir),
    }


def _validate_symbol(symbol: str) -> str:
    try:
        return validate_symbol_for_snapshot(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/execution-intents")
def list_execution_intents(
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """Latest execution intent per ``signal_id`` (append-only JSONL collapsed for Terminal blotter)."""
    return latest_execution_intents(limit=limit, dedupe=True)


@app.get("/api/execution-intents/allowed-statuses")
def execution_intent_allowed_statuses() -> dict[str, Any]:
    return {"statuses": sorted(ALLOWED_INTENT_STATUSES)}


@app.patch("/api/execution-intents/{signal_id}")
def patch_execution_intent_status(
    signal_id: str,
    body: ExecutionIntentStatusBody,
) -> dict[str, Any]:
    """Append-only status transition (review / paper handoff). Does **not** send orders."""
    updated = update_execution_intent_status(signal_id, body.status, note=body.note)
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail="signal_id not found, invalid status, or malformed prior row",
        )
    return updated


@app.get("/api/symbols/{symbol}/quote", response_model=SymbolQuote)
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


@app.get("/api/symbols/{symbol}/snapshot", response_model=SymbolSnapshot)
def get_symbol_snapshot(
    symbol: str,
    days: int = Query(default=30, ge=7, le=180),
    recommendation_limit: int = Query(default=12, ge=1, le=40),
) -> dict[str, Any]:
    """Terminal-style symbol snapshot for PWA focus cards/workspace."""
    normalized_symbol = _validate_symbol(symbol)
    try:
        client = _get_bq_client()
        return build_symbol_snapshot(
            client,
            normalized_symbol,
            days=days,
            recommendation_limit=recommendation_limit,
        )
    except Exception as exc:
        logger.error("BigQuery symbols/%s/snapshot failed: %s", normalized_symbol, exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc


@app.post("/api/push/subscribe")
def push_subscribe(_body: WebPushSubscribeBody) -> dict[str, Any]:
    """Web Push 訂閱預留：須 VAPID、持久化與 rate limit 審核後才啟用。

    設 **WEB_PUSH_ENABLED=1** 前一律 **501**，避免誤以為已可寫入生產訂閱。
    """
    if os.getenv("WEB_PUSH_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(
            status_code=501,
            detail=(
                "Web Push 未啟用。完成安全檢視後設 WEB_PUSH_ENABLED=1，"
                "並實作 VAPID／訂閱儲存（見 TODOS Direction 1A）。"
            ),
        )
    logger.warning("WEB_PUSH_ENABLED=1 but subscription persistence not implemented — no-op accept")
    return {"ok": True, "stored": False}


@app.get("/api/war-room/latest")
def get_war_room_latest() -> dict[str, Any]:
    """Read-only War Room snapshot from local gate-failure artifacts and scratchpad."""
    payload = WarRoomSnapshot(
        gate_failure=_latest_gate_failure_summary(),
        scratchpad=_latest_scratchpad_summary(),
        execution_intents=latest_execution_intents(limit=20),
    )
    return payload.model_dump(mode="json")
