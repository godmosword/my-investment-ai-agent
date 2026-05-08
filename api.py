"""FastAPI backend for Q-Silicon Investment Report PWA.

Exposes daily metrics, trade recommendations, and report summaries
stored in BigQuery for consumption by the React PWA frontend.

Usage:
    uvicorn api:app --reload --port 8000
"""

import asyncio
import json
import logging
import os
import re
import time

import yaml
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.cloud import bigquery
from pydantic import BaseModel, Field, field_validator

from config import METRICS_TABLE, RECOMMENDATIONS_TABLE, LLM_RUN_LOG_TABLE
from execution_intents import (
    ALLOWED_INTENT_STATUSES,
    CLIENT_PATCHABLE_STATUSES,
    intent_store_mtime,
    latest_execution_intents,
    update_execution_intent_status,
)
from paper_execution import run_paper_execution_tick
from war_room_stream import get_war_room_stream_version
from symbol_snapshot_service import (
    build_symbol_snapshot,
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)

from api_deps import get_bq_client as _bq_singleton, rows_to_dicts
from api_routers import health as health_router
from api_routers import metrics as metrics_router

logger = logging.getLogger(__name__)


def _get_bq_client() -> bigquery.Client:
    """BQ client accessor; tests monkeypatch ``api._get_bq_client``."""
    return _bq_singleton()

_REPO_ROOT = Path(__file__).resolve().parent

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

app.include_router(health_router.router)
app.include_router(metrics_router.router)


def _qsilicon_master_key_required() -> str:
    """非空時，所有 ``/api/*``（除 SSE 專線）須 Header ``X-Q-Silicon-Key`` 與其完全一致。"""
    return (os.getenv("QSILICON_MASTER_KEY") or "").strip()


def _path_exempt_from_silicon_master_key(path: str) -> bool:
    """EventSource 無法自訂 Header；SSE 仍用 ``API_STREAM_AUTH_KEY``／query。"""
    return path == "/api/stream/war-room" or path.startswith("/api/stream/war-room/")


@app.middleware("http")
async def _qsilicon_master_key_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if not path.startswith("/api/") or _path_exempt_from_silicon_master_key(path):
        return await call_next(request)
    master = _qsilicon_master_key_required()
    if not master:
        return await call_next(request)
    hdr = (request.headers.get("X-Q-Silicon-Key") or "").strip()
    if hdr != master:
        from starlette.responses import Response

        return Response(status_code=401, content="Unauthorized", media_type="text/plain")
    return await call_next(request)


@app.middleware("http")
async def _api_request_observability_middleware(request: Request, call_next):
    """Lightweight latency / outcome logging for Terminal-facing API routes (T1b)."""
    path = request.url.path
    t0 = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        if path.startswith("/api/"):
            logger.warning(
                "api_request path=%s method=%s status=exception elapsed_ms=%.1f",
                path,
                request.method,
                elapsed_ms,
            )
        raise
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    if path.startswith("/api/") and os.getenv("API_HTTP_REQUEST_LOG", "0").lower() in (
        "1",
        "true",
        "yes",
    ):
        log_fn = logger.warning if response.status_code >= 400 else logger.info
        log_fn(
            "api_request path=%s method=%s status=%s elapsed_ms=%.1f",
            path,
            request.method,
            response.status_code,
            elapsed_ms,
        )
    return response


# ── /api/reports ─────────────────────────────────────────────────────────────

@app.get("/api/reports")
def list_reports(
    limit: int = Query(default=30, ge=1, le=90),
    profile: str | None = Query(
        default=None,
        description=(
            "Optional brief profile (full, lite, crypto-only). When set, only report "
            "dates that appear in llm_run_log with this profile are listed."
        ),
    ),
) -> list[dict[str, Any]]:
    """List recent daily reports (summary cards).

    Each entry contains the date, key metrics snapshot, and agent
    summaries (grok_summary, gpt_summary) — the full report text is
    accessible via Telegram; this endpoint provides the structured
    data layer for the PWA archive view.
    """
    resolved_profile: str | None = None
    if profile is not None and str(profile).strip() != "":
        try:
            from brief_profiles import get_active_profile
        except ImportError as exc:
            logger.error("brief_profiles import failed: %s", exc)
            raise HTTPException(
                status_code=500, detail="Server configuration error"
            ) from exc
        try:
            resolved_profile = get_active_profile(profile)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    base_select = f"""
            SELECT
                DATE(m.timestamp) AS report_date,
                m.timestamp,
                m.dxy,
                m.etf_flow_millions,
                m.avg_risk_score,
                m.mvrv_z_score,
                m.regime_score,
                m.sentiment_score,
                m.grok_summary,
                m.gpt_summary,
                m.news_titles
            FROM `{METRICS_TABLE}` m
    """
    try:
        client = _get_bq_client()
        if resolved_profile is None:
            rows = client.query(
                base_select
                + f"""
            ORDER BY m.timestamp DESC
            LIMIT {limit}
        """
            ).result()
        else:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("profile", "STRING", resolved_profile),
                    bigquery.ScalarQueryParameter("lim", "INT64", int(limit)),
                ]
            )
            rows = client.query(
                base_select
                + f"""
            INNER JOIN (
                SELECT DISTINCT DATE(timestamp) AS d
                FROM `{LLM_RUN_LOG_TABLE}`
                WHERE profile = @profile
            ) filt ON DATE(m.timestamp) = filt.d
            ORDER BY m.timestamp DESC
            LIMIT @lim
        """,
                job_config=job_config,
            ).result()
    except Exception as exc:
        logger.error("BigQuery reports list failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    return rows_to_dicts(rows)


@app.get("/api/reports/profile-stats")
def get_report_profile_stats(
    days: int = Query(default=30, ge=1, le=365),
) -> dict[str, Any]:
    """Aggregate daily-brief report counts grouped by profile.

    Queries ``llm_run_log`` within the past ``days`` window and returns a
    breakdown of distinct report dates per profile, so the Archive page can
    render a distribution bar chart. Profiles with zero reports in the window
    are still returned (count=0) to keep the chart axis stable.
    """
    try:
        from brief_profiles import PROFILES
    except ImportError as exc:  # pragma: no cover - defensive
        logger.error("brief_profiles import failed: %s", exc)
        raise HTTPException(status_code=500, detail="Server configuration error") from exc

    known_profiles = list(PROFILES.keys())
    try:
        client = _get_bq_client()
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("days", "INT64", int(days)),
            ]
        )
        rows = client.query(
            f"""
            SELECT
                COALESCE(profile, 'full') AS profile,
                COUNT(DISTINCT DATE(timestamp)) AS report_count,
                MAX(DATE(timestamp)) AS latest_date
            FROM `{LLM_RUN_LOG_TABLE}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
            GROUP BY profile
            """,
            job_config=job_config,
        ).result()
    except Exception as exc:
        logger.error("BigQuery profile-stats query failed: %s", exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    raw = {row["profile"]: row for row in rows_to_dicts(rows)}
    breakdown: list[dict[str, Any]] = []
    total = 0
    for name in known_profiles:
        row = raw.get(name)
        count = int(row["report_count"]) if row else 0
        breakdown.append(
            {
                "profile": name,
                "report_count": count,
                "latest_date": row.get("latest_date") if row else None,
            }
        )
        total += count
    # Include any unexpected profiles that appear in the log but aren't in PROFILES
    for name, row in raw.items():
        if name in known_profiles:
            continue
        count = int(row["report_count"])
        breakdown.append(
            {
                "profile": name,
                "report_count": count,
                "latest_date": row.get("latest_date"),
            }
        )
        total += count

    return {
        "window_days": int(days),
        "total_reports": total,
        "breakdown": breakdown,
    }


def _validate_report_date(report_date: str) -> None:
    try:
        datetime.strptime(report_date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="Invalid date format; use YYYY-MM-DD"
        ) from exc


def _load_report_legacy(report_date: str) -> dict[str, Any]:
    """Load metrics row + recommendations from BigQuery (legacy PWA shape)."""
    try:
        client = _get_bq_client()
        rows = list(
            client.query(
                f"""
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
        """
            ).result()
        )
    except Exception as exc:
        logger.error("BigQuery report/%s failed: %s", report_date, exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        raise HTTPException(status_code=404, detail=f"No report found for {report_date}")

    report = rows_to_dicts(rows)[0]

    try:
        rec_rows = client.query(
            f"""
            SELECT
                asset, direction, entry_price, target_price, stop_price,
                confidence, narrative, trigger, invalidation,
                position_pct, timeframe, category,
                status, exit_price, exit_date, pnl_pct, rr_ratio
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date = '{report_date}'
            ORDER BY confidence DESC, asset ASC
        """
        ).result()
        report["recommendations"] = rows_to_dicts(rec_rows)
    except Exception as exc:
        logger.warning("Could not attach recommendations for %s: %s", report_date, exc)
        report["recommendations"] = []

    return report


@app.get("/api/reports/{report_date}/structured")
def get_report_structured(
    report_date: str,
    profile: str = Query(
        default="full",
        description="Telegram brief profile: full, lite, crypto-only",
    ),
) -> dict[str, Any]:
    """Structured report envelope for block-based PWA (V2 visualization).

    When ``daily_brief_report`` is not persisted yet, ``legacy`` carries the same
    payload as ``GET /api/reports/{report_date}`` for UI fallback.
    """
    _validate_report_date(report_date)
    try:
        from brief_profiles import BLOCK_REGISTRY, get_active_profile, profile_block_ids
    except ImportError as exc:
        logger.error("brief_profiles import failed: %s", exc)
        raise HTTPException(
            status_code=500, detail="Server configuration error"
        ) from exc

    try:
        resolved_profile = get_active_profile(profile)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    block_ids = list(profile_block_ids(resolved_profile))
    block_registry = {
        bid: {
            "template_subpath": BLOCK_REGISTRY[bid].template_subpath,
            "macro_name": BLOCK_REGISTRY[bid].macro_name,
            "empty_behavior": BLOCK_REGISTRY[bid].empty_behavior,
        }
        for bid in block_ids
        if bid in BLOCK_REGISTRY
    }

    legacy = _load_report_legacy(report_date)

    daily_brief_report: dict[str, Any] | None = None
    structured_body_available = False
    structured_validation_result: dict[str, Any] | None = None
    structured_source: str | None = None
    parse_error: str | None = None

    raw_dict, raw_src = _try_load_daily_brief_raw_dict(report_date)
    if raw_dict:
        try:
            from schemas import DailyBriefReport, validate_structured_report

            model = DailyBriefReport.model_validate(raw_dict)
            daily_brief_report = model.model_dump(mode="json")
            structured_body_available = True
            structured_source = raw_src
            structured_validation_result = validate_structured_report(model)
        except Exception as exc:
            logger.warning(
                "DailyBriefReport validation failed for %s (source=%s): %s",
                report_date,
                raw_src,
                exc,
            )
            parse_error = str(exc)
            daily_brief_report = None
            structured_body_available = False

    gate_failure = _latest_gate_failure_summary()
    gate_summary = _compose_gate_summary_for_structured(
        structured_validation=structured_validation_result,
        gate_failure=gate_failure,
        parse_error=parse_error,
    )

    return {
        "report_date": report_date,
        "profile": resolved_profile,
        "block_ids": block_ids,
        "block_registry": block_registry,
        "daily_brief_report": daily_brief_report,
        "structured_body_available": structured_body_available,
        "structured_source": structured_source,
        "gate_summary": gate_summary,
        "legacy": legacy,
    }


@app.get("/api/reports/{report_date}/html")
def get_report_html(
    report_date: str,
    profile: str = Query(default="full"),
    download: bool = Query(default=False),
) -> Response:
    """Render a self-contained HTML export of the Daily Brief.

    Inspired by nexu-io/open-design finance-report skill:
    Masthead + KPI strip + exec summary + trades grid + news block + QSREC payload.
    """
    from fastapi.responses import HTMLResponse
    from jinja2 import Environment, FileSystemLoader
    from report_render import tg_escape
    import json as _json

    _validate_report_date(report_date)
    raw_dict, _ = _try_load_daily_brief_raw_dict(report_date)
    if not raw_dict:
        raise HTTPException(status_code=404, detail=f"No structured report found for {report_date}")

    try:
        from schemas import DailyBriefReport
        model = DailyBriefReport.model_validate(raw_dict)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Report schema error: {exc}") from exc

    templates_dir = _REPO_ROOT / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["tg_escape"] = tg_escape
    env.filters["tojson"] = lambda v, indent=None: _json.dumps(v, ensure_ascii=False, indent=indent)

    tmpl = env.get_template("html_export/brief_card.html.j2")
    html = tmpl.render(report=model, report_date=report_date, profile=profile)

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="brief_{report_date}.html"'
    return HTMLResponse(content=html, headers=headers)


@app.get("/api/brief-layouts")
def list_brief_layout_yaml_files() -> dict[str, Any]:
    """List ``*.yaml`` under ``config/brief_layouts/`` (modularization Phase 4b).

    Read-only inventory for PWA layout UX (``visualization_plan`` V3). Filenames are
    examples or operator-supplied layouts; merging still happens server-side via
    ``BRIEF_LAYOUT_FILE``.
    """
    layouts_dir = _REPO_ROOT / "config" / "brief_layouts"
    if not layouts_dir.is_dir():
        return {"layouts": []}

    layouts: list[dict[str, Any]] = []
    for path in sorted(layouts_dir.glob("*.yaml")):
        try:
            rel = path.relative_to(_REPO_ROOT)
        except ValueError:
            rel = path
        entry: dict[str, Any] = {
            "filename": path.name,
            "path": str(rel).replace("\\", "/"),
        }
        try:
            with path.open(encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except OSError as exc:
            entry["parse_error"] = f"read failed: {exc}"[:500]
            layouts.append(entry)
            continue
        except yaml.YAMLError as exc:
            entry["parse_error"] = str(exc)[:500]
            layouts.append(entry)
            continue

        if data is None:
            entry["parse_error"] = "empty or null YAML"
        elif not isinstance(data, dict):
            entry["parse_error"] = "YAML root must be a mapping"
        else:
            applies = data.get("applies_to_profile")
            if applies is not None:
                entry["applies_to_profile"] = str(applies).strip()
            blocks_raw = data.get("blocks")
            if isinstance(blocks_raw, list):
                entry["blocks"] = [str(b).strip() for b in blocks_raw if b is not None and str(b).strip()]
        layouts.append(entry)
    return {"layouts": layouts}


@app.get("/api/reports/{report_date}")
def get_report(report_date: str) -> dict[str, Any]:
    """Return the report summary for a specific date (YYYY-MM-DD)."""
    _validate_report_date(report_date)
    return _load_report_legacy(report_date)


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

    return rows_to_dicts(rows)


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
        stats["by_category"] = rows_to_dicts(cat_rows)
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
        stats["equity_curve"] = rows_to_dicts(eq_rows)
    except Exception as exc:
        logger.warning("Could not fetch equity curve: %s", exc)
        stats["equity_curve"] = []

    return stats


class WebPushSubscribeBody(BaseModel):
    """預留 Web Push 訂閱 payload（與 browser PushSubscription JSON 對齊）。"""

    endpoint: str = Field(..., max_length=4096)
    keys: dict[str, str] | None = None
    report_date: str | None = Field(default=None, max_length=32)
    block_id: str | None = Field(default=None, max_length=128)

    @field_validator("report_date")
    @classmethod
    def _validate_report_date(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        parts = s.split("-")
        if len(parts) != 3 or len(s) != 10:
            raise ValueError("report_date must be YYYY-MM-DD")
        y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
        if not (2000 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31):
            raise ValueError("report_date out of range")
        return s

    @field_validator("block_id")
    @classmethod
    def _validate_block_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        s = str(v).strip()
        return s if s else None


class WebPushTestSendBody(BaseModel):
    """管理端測試推送（須 ``WEB_PUSH_ADMIN_KEY`` 與 ``WEB_PUSH_VAPID_PRIVATE_KEY``）。"""

    title: str = Field(default="Q-Silicon", max_length=120)
    body: str = Field(default="Test notification", max_length=500)


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


class ExecutionIntentStatusBody(BaseModel):
    """Human / War Room workflow: advance intent lifecycle (no order placement)."""

    status: str = Field(..., description="One of CLIENT_PATCHABLE_STATUSES (case-insensitive).")
    note: str = Field(default="", max_length=2000)
    reference_entry_price: float | None = None
    reference_target_price: float | None = None
    reference_stop_price: float | None = None


class ExecutionIntentRow(BaseModel):
    signal_id: str
    created_at: str
    category: str
    regime: str = ""
    asset: str
    direction: str
    star_rating: int
    thesis_one_liner: str = ""
    status: str
    status_updated_at: str = ""
    status_note: str = ""
    reference_entry_price: float | None = None
    reference_target_price: float | None = None
    reference_stop_price: float | None = None
    paper_fill_price: float | None = None
    paper_exit_price: float | None = None
    gate_issue_hints: list[str] = Field(default_factory=list)


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


def _compact_yyyymmdd(report_date: str) -> str:
    """``YYYY-MM-DD`` → ``YYYYMMDD`` for matching ``logs/run_YYYYMMDD_*`` folders."""
    return report_date.replace("-", "")


def _daily_brief_explicit_json_paths(report_date: str) -> list[Path]:
    paths: list[Path] = []
    env_dir = (os.getenv("DAILY_BRIEF_JSON_DIR") or "").strip()
    if env_dir:
        paths.append(Path(env_dir).expanduser().resolve() / f"{report_date}.json")
    paths.append(_REPO_ROOT / ".qsilicon" / "daily_brief_reports" / f"{report_date}.json")
    return paths


def _load_daily_brief_json_from_logs_run_folder(report_date: str) -> tuple[dict[str, Any] | None, str | None]:
    """Match ``logs/run_YYYYMMDD_* / raw_data.json`` (same convention as ``main._persist_pipeline_raw_report``)."""
    logs_dir = _REPO_ROOT / "logs"
    if not logs_dir.is_dir():
        return None, None
    compact = _compact_yyyymmdd(report_date)
    for folder in sorted(logs_dir.glob("run_*"), reverse=True):
        m = re.match(r"run_(\d{8})_", folder.name)
        if not m or m.group(1) != compact:
            continue
        path = folder / "raw_data.json"
        data = _read_json_if_exists(path)
        if data:
            try:
                rel = path.relative_to(_REPO_ROOT)
            except ValueError:
                rel = path
            return data, str(rel).replace("\\", "/")
    return None, None


def _try_load_daily_brief_raw_dict(report_date: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return ``(json_dict, provenance_path)`` for optional ``DailyBriefReport`` JSON on disk."""
    for path in _daily_brief_explicit_json_paths(report_date):
        data = _read_json_if_exists(path)
        if data:
            try:
                rel = path.resolve().relative_to(_REPO_ROOT.resolve())
                src = str(rel).replace("\\", "/")
            except ValueError:
                src = str(path)
            return data, src
    return _load_daily_brief_json_from_logs_run_folder(report_date)


def _unique_str_preserve(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in seq:
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _classify_gate_line_to_blocks(line: str) -> list[str]:
    """Heuristic mapping of ``validate_report`` / structured issue strings to ``brief_profiles`` block ids."""
    s = line.strip()
    if not s:
        return []
    hits: list[str] = []

    def add(bid: str) -> None:
        if bid not in hits:
            hits.append(bid)

    if any(k in s for k in ("執行摘要", "【執行摘要】", "lite Pass6", "Pass6：執行摘要")):
        add("exec_summary")
    if any(k in s for k in ("市場模式", "【今日市場模式】", "制度／波動", "制度/波動")):
        add("market_mode")
    if any(k in s for k in ("總經", "【總經", "Macro", "macro_framework")):
        add("macro_framework")
    if any(k in s for k in ("預測市場", "Polymarket", "prediction_markets")):
        add("prediction_markets")
    if any(k in s for k in ("幣圈儀表", "加密儀表")):
        add("crypto_dashboard")
    if "幣圈新聞" in s or ("crypto" in s.lower() and "news" in s.lower()):
        add("crypto_news")
    if any(k in s for k in ("幣圈社群", "呢喃", "chatter")):
        add("crypto_chatter")
    if any(k in s for k in ("加密", "crypto")) and any(k in s for k in ("交易", "trade", "QSREC")):
        add("crypto_trades")
    if any(k in s for k in ("AI 儀表", "科技儀表", "ai_dashboard")):
        add("ai_dashboard")
    if "AI" in s and "新聞" in s:
        add("ai_news")
    if any(k in s for k in ("時事", "Roundtable", "roundtable", "多觀點", "current_affairs")):
        add("current_affairs_roundtable")
    if any(k in s for k in ("機構速讀", "機構", "institutional")):
        add("institutional_view")
    if any(k in s for k in ("上期", "前次建議", "previous_recs")):
        add("previous_recs")
    if any(k in s for k in ("來源健康", "source_health", "footer")):
        add("source_health")
    if any(k in s for k in ("QSREC", "交易建議")):
        add("qsrec")

    return hits


def _partition_issues_by_block(issues: list[str]) -> tuple[dict[str, list[str]], list[str]]:
    by_block: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for line in issues:
        bids = _classify_gate_line_to_blocks(line)
        if not bids:
            unmapped.append(line)
            continue
        for bid in bids:
            by_block.setdefault(bid, []).append(line)
    return by_block, unmapped


def _compose_gate_summary_for_structured(
    *,
    structured_validation: dict[str, Any] | None,
    gate_failure: dict[str, Any] | None,
    parse_error: str | None,
) -> dict[str, Any]:
    """Merge structured ``validate_structured_report`` output with optional last gate failure artifacts."""
    issues_struct: list[str] = []
    if structured_validation is not None:
        issues_struct = _unique_str_preserve(
            list(structured_validation.get("blocking_issues") or [])
            + list(structured_validation.get("issues") or [])
        )
    gf_issues: list[str] = []
    if gate_failure:
        gf_issues = [
            str(x).strip() for x in (gate_failure.get("issues") or []) if str(x).strip()
        ]
    merged = _unique_str_preserve(issues_struct + gf_issues)
    if parse_error:
        merged = _unique_str_preserve([f"[daily_brief JSON] {parse_error}"] + merged)

    by_block, unmapped = _partition_issues_by_block(merged)

    ok_struct = structured_validation.get("valid") if structured_validation else None
    ok_gate = gate_failure.get("valid") if gate_failure else None

    overall_ok: bool | None
    if structured_validation is not None and gate_failure is not None:
        overall_ok = bool(ok_struct) and (ok_gate is not False)
    elif structured_validation is not None:
        overall_ok = bool(ok_struct)
    elif gate_failure is not None:
        overall_ok = ok_gate is not False
    else:
        overall_ok = None if not parse_error else False

    if parse_error and overall_ok is None:
        overall_ok = False

    available = bool(
        structured_validation is not None
        or gate_failure is not None
        or parse_error
        or merged
    )

    return {
        "available": available,
        "ok": overall_ok,
        "issue_count": len(merged),
        "issues": merged,
        "issues_by_block": by_block,
        "issues_unmapped": unmapped,
        "structured_validation": structured_validation,
        "last_gate_artifact_dir": (gate_failure or {}).get("artifact_dir"),
        "last_gate_issues_path": (gate_failure or {}).get("issues_path"),
    }


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


def _gate_line_matches_intent(line: str, asset_u: str, signal_id: str) -> bool:
    """Avoid substring false positives (e.g. ``ASSET`` inside ``PASSSETS``) where possible."""
    if not asset_u:
        return False
    lu = line.upper()
    if len(asset_u) >= 2:
        try:
            if re.search(rf"\b{re.escape(asset_u)}\b", lu):
                return True
        except re.error:
            pass
    sid = (signal_id or "").upper()
    parts = {p for p in re.split(r"[^A-Z0-9]+", sid) if len(p) >= 2}
    if asset_u in parts and asset_u in lu:
        return True
    return asset_u in lu


def _enrich_intents_with_gate_hints(
    intents: list[dict[str, Any]],
    gate_failure: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Read-only cross-hints (T5b): match gate issue lines to ``asset`` / ``signal_id`` segments."""
    issues_raw = (gate_failure or {}).get("issues") if isinstance(gate_failure, dict) else None
    if not intents or not isinstance(issues_raw, list) or not issues_raw:
        return intents
    issues = [str(x).strip() for x in issues_raw if str(x).strip()]
    if not issues:
        return intents
    out: list[dict[str, Any]] = []
    for row in intents:
        asset = str(row.get("asset") or "").strip().upper()
        sid = str(row.get("signal_id") or "").strip()
        if not asset:
            out.append(row)
            continue
        matched = [line for line in issues if _gate_line_matches_intent(line, asset, sid)]
        if not matched:
            out.append(row)
            continue
        merged = {**row, "gate_issue_hints": matched[:8]}
        out.append(merged)
    return out


def _sse_auth_ok(request: Request) -> bool:
    key = (os.getenv("API_STREAM_AUTH_KEY") or "").strip()
    if not key:
        return True
    return request.headers.get("X-QS-Stream-Key") == key or request.query_params.get("stream_key") == key


def _paper_tick_auth_ok(request: Request) -> bool:
    key = (os.getenv("PAPER_TICK_API_KEY") or "").strip()
    if not key:
        return True
    return request.headers.get("X-Paper-Tick-Key") == key


def _web_push_admin_ok(request: Request) -> bool:
    key = (os.getenv("WEB_PUSH_ADMIN_KEY") or "").strip()
    if not key:
        return False
    return request.headers.get("X-Web-Push-Admin-Key") == key


def _validate_symbol(symbol: str) -> str:
    try:
        return validate_symbol_for_snapshot(symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/execution-intents", response_model=list[ExecutionIntentRow])
def list_execution_intents(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(
        default=None,
        description="Optional case-insensitive substring filter on intent status (e.g. PAPER).",
    ),
    category: str | None = Query(
        default=None,
        description="Optional prefix filter: CRYPTO or AI (case-insensitive).",
    ),
    sort_by: str = Query(
        default="updated_desc",
        description="Sort: updated_desc (default), created_desc, asset_asc.",
    ),
) -> list[dict[str, Any]]:
    """Latest execution intent per ``signal_id`` (append-only JSONL collapsed for Terminal blotter)."""
    sort_key = (sort_by or "updated_desc").strip().lower()
    if sort_key not in {"updated_desc", "created_desc", "asset_asc"}:
        raise HTTPException(
            status_code=400,
            detail="sort_by must be one of: updated_desc, created_desc, asset_asc",
        )
    rows = latest_execution_intents(
        limit=limit,
        dedupe=True,
        status=status,
        category=category,
        sort_by=sort_key,
    )
    gate = _latest_gate_failure_summary()
    return _enrich_intents_with_gate_hints(rows, gate)


@app.get("/api/execution-intents/allowed-statuses")
def execution_intent_allowed_statuses() -> dict[str, Any]:
    return {
        "statuses": sorted(ALLOWED_INTENT_STATUSES),
        "client_patchable": sorted(CLIENT_PATCHABLE_STATUSES),
    }


@app.patch("/api/execution-intents/{signal_id}", response_model=ExecutionIntentRow)
def patch_execution_intent_status(
    signal_id: str,
    body: ExecutionIntentStatusBody,
) -> dict[str, Any]:
    """Append-only status transition (review / paper handoff). Does **not** send orders."""
    updated = update_execution_intent_status(
        signal_id,
        body.status,
        note=body.note,
        reference_entry_price=body.reference_entry_price,
        reference_target_price=body.reference_target_price,
        reference_stop_price=body.reference_stop_price,
    )
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
def push_subscribe(request: Request, body: WebPushSubscribeBody) -> dict[str, Any]:
    """Web Push 訂閱：預設關閉；開啟後見 ``web_push_store``（Redis／程序內／log-only）。"""
    import web_push_store

    if not web_push_store.web_push_enabled():
        raise HTTPException(
            status_code=501,
            detail=(
                "Web Push 未啟用。設 WEB_PUSH_ENABLED=1 後可 POST 訂閱；"
                "可選 WEB_PUSH_STORE=1 啟用程序內暫存（非持久化）。詳見 docs/PWA_WEB_PUSH.md。"
            ),
        )
    client_ip = (request.client.host if request.client else "") or ""
    meta = web_push_store.record_subscription(body.model_dump(mode="json"), client_ip=client_ip)
    return {"ok": True, **meta}


@app.post("/api/push/test-send")
def push_test_send(request: Request, body: WebPushTestSendBody) -> dict[str, Any]:
    """對已存訂閱送一則 **測試** Web Push（``pywebpush``）。須 ``WEB_PUSH_ADMIN_KEY`` Header。"""
    import web_push_store

    if not web_push_store.web_push_enabled():
        raise HTTPException(status_code=501, detail="Web Push disabled")
    if not _web_push_admin_ok(request):
        raise HTTPException(status_code=404, detail="admin endpoint disabled or invalid key")
    return web_push_store.send_test_push(body.title, body.body)


@app.get("/api/war-room/latest")
def get_war_room_latest() -> dict[str, Any]:
    """Read-only War Room snapshot from local gate-failure artifacts and scratchpad."""
    gate = _latest_gate_failure_summary()
    intents = latest_execution_intents(limit=20)
    payload = WarRoomSnapshot(
        gate_failure=gate,
        scratchpad=_latest_scratchpad_summary(),
        execution_intents=_enrich_intents_with_gate_hints(intents, gate),
    )
    return payload.model_dump(mode="json")


def _war_room_fingerprint() -> dict[str, Any]:
    return {
        "stream_version": get_war_room_stream_version(),
        "intent_store_mtime": intent_store_mtime(),
    }


@app.get("/api/stream/war-room")
async def stream_war_room(request: Request):
    """SSE: push war-room payload when execution intents change (M4). Disabled unless ``TERMINAL_SSE_ENABLED=1``."""
    if os.getenv("TERMINAL_SSE_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="SSE disabled; set TERMINAL_SSE_ENABLED=1")
    if not _sse_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing stream auth")

    interval = float(os.getenv("TERMINAL_SSE_POLL_SEC", "2") or "2")
    interval = max(0.5, min(interval, 30.0))

    async def event_gen():
        last_fp: dict[str, Any] | None = None
        while True:
            fp = _war_room_fingerprint()
            if fp != last_fp:
                last_fp = fp
                body = get_war_room_latest()
                payload = json.dumps(body, ensure_ascii=False)
                yield f"data: {payload}\n\n"
            yield ": keepalive\n\n"
            await asyncio.sleep(interval)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/paper/execution-tick")
def post_paper_execution_tick(request: Request) -> dict[str, Any]:
    """Run one paper simulation pass (M5). Disabled unless ``PAPER_TICK_HTTP_ENABLED=1``."""
    if os.getenv("PAPER_TICK_HTTP_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="paper tick HTTP disabled")
    if not _paper_tick_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing paper tick auth")
    written = run_paper_execution_tick()
    return {"ok": True, "written": len(written), "rows": written}
