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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from google.cloud import bigquery
from pydantic import BaseModel, Field, field_validator

from config import (
    METRICS_TABLE,
    RECOMMENDATIONS_TABLE,
    LLM_RUN_LOG_TABLE,
    REVIEWER_LOG_TABLE,
    GATE_FAILURE_LOG_TABLE,
)
from execution_intents import (
    intent_store_mtime,
    latest_execution_intents,
)
from paper_lifecycle import build_paper_lifecycle_payload
from transparency_letter import build_transparency_letter
from track_record import normalize_closed_intent
from paper_execution import run_paper_execution_tick
import sse_token
from war_room_stream import (
    drain_graph_node_events,
    drain_price_alert_events,
    get_war_room_stream_version,
)
from symbol_snapshot_service import (
    build_symbol_snapshot,
    fetch_symbol_quote,
    validate_symbol_for_snapshot,
)

from api_deps import get_bq_client as _bq_singleton, rows_to_dicts
from api_routers import health as health_router
from api_routers import macro as macro_router
from api_routers import metrics as metrics_router
from api_routers import news as news_router
from api_routers import portfolio as portfolio_router
from api_routers import price_alerts as price_alerts_router
from api_routers import run_crew as run_crew_router
from api_routers import scenario as scenario_router
from api_routers import symbols as symbols_router
from api_routers import track_record as track_record_router
from api_routers import industries as industries_router
from api_routers import earnings as earnings_router
from api_routers.execution_intents import (
    _enrich_intents_with_gate_hints,
    _latest_gate_failure_summary,
)
from api_routers import execution_intents as execution_intents_router

logger = logging.getLogger(__name__)


def _get_bq_client() -> bigquery.Client:
    """BQ client accessor; tests monkeypatch ``api._get_bq_client``."""
    return _bq_singleton()

_REPO_ROOT = Path(__file__).resolve().parent

# Prevent duplicate PAPER_* rows when two execution-tick requests arrive simultaneously
_paper_tick_lock = asyncio.Lock()

# Module-level Jinja2 env (bytecode-cached, autoescape enabled for XSS safety)
def _build_jinja2_env() -> "Environment":  # noqa: F821 — lazy import avoids hard dep at startup
    from jinja2 import Environment, FileSystemLoader, Markup
    from report_render import tg_escape
    import json as _json

    _env = Environment(
        loader=FileSystemLoader(str(_REPO_ROOT / "templates")),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    # tg_escape output is already HTML-entity-encoded — wrap as Markup so
    # autoescape doesn't double-encode & → &amp;amp; etc.
    _env.filters["tg_escape"] = lambda v: Markup(tg_escape(v))
    # tojson renders into <pre> — autoescape will encode < > keeping the pre safe
    _env.filters["tojson"] = lambda v, indent=None: _json.dumps(v, ensure_ascii=False, indent=indent)
    return _env


_JINJA2_ENV: "Environment | None" = None  # noqa: F821


def _get_jinja2_env() -> "Environment":  # noqa: F821
    global _JINJA2_ENV
    if _JINJA2_ENV is None:
        _JINJA2_ENV = _build_jinja2_env()
    return _JINJA2_ENV


app = FastAPI(
    title="Q-Silicon Investment API",
    description="Daily crypto/AI investment report data API",
    version="1.0.0",
)

# Allow local dev (Vite), explicit production origins, and Vercel preview (*.vercel.app).
_CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://localhost:3000",
    ).split(",")
    if o.strip()
]
_CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", r"https://.*\.vercel\.app").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router.router)
app.include_router(macro_router.router)
app.include_router(metrics_router.router)
app.include_router(news_router.router)
app.include_router(portfolio_router.router)
app.include_router(price_alerts_router.router)
app.include_router(run_crew_router.router)
app.include_router(scenario_router.router)
app.include_router(symbols_router.router)
app.include_router(track_record_router.router)
app.include_router(industries_router.router)
app.include_router(earnings_router.router)
app.include_router(execution_intents_router.router)


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
        job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("report_date", "DATE", report_date)]
        )
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
            WHERE DATE(timestamp) = @report_date
            ORDER BY timestamp DESC
            LIMIT 1
        """,
                job_config=job_config,
            ).result()
        )
    except Exception as exc:
        logger.error("BigQuery report/%s failed: %s", report_date, exc)
        raise HTTPException(status_code=503, detail="BigQuery unavailable") from exc

    if not rows:
        raise HTTPException(status_code=404, detail=f"No report found for {report_date}")

    report = rows_to_dicts(rows)[0]

    try:
        rec_job_config = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("report_date", "DATE", report_date)]
        )
        rec_rows = client.query(
            f"""
            SELECT
                asset, direction, entry_price, target_price, stop_price,
                confidence, narrative, trigger, invalidation,
                position_pct, timeframe, category,
                status, exit_price, exit_date, pnl_pct, rr_ratio
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date = @report_date
            ORDER BY confidence DESC, asset ASC
        """,
            job_config=rec_job_config,
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


def _gate_status_from_row(row: dict[str, Any]) -> str:
    if row.get("degraded"):
        return "degraded"
    if int(row.get("revision_count", 0)) >= 2:
        return "fail"
    return "pass"


@app.get("/api/reports/{report_date}/gate-status")
def get_report_gate_status(report_date: str) -> dict[str, Any]:
    """Reviewer loop outcome for the given date.

    Returns gate_status = pass | fail | degraded | 未審.
    Falls back to fixtures/reviewer_log_fixture.json when SKIP_BIGQUERY=1.
    """
    _validate_report_date(report_date)

    skip_bq = os.getenv("SKIP_BIGQUERY", "0") == "1"

    if not skip_bq:
        try:
            client = _get_bq_client()
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("dt", "DATE", report_date),
                ]
            )
            rows = list(
                client.query(
                    f"""
                    SELECT
                      MAX(run_id) AS run_id,
                      LOGICAL_OR(degraded) AS degraded,
                      MAX(revision_count) AS revision_count,
                      SUM(final_trade_count) AS final_trade_count
                    FROM `{REVIEWER_LOG_TABLE}`
                    WHERE COALESCE(report_date, DATE(created_at)) = @dt
                    """,
                    job_config=job_config,
                ).result()
            )
            if rows:
                row = dict(rows[0])
                if row.get("run_id") is None:
                    return {"gate_status": "未審"}
                return {
                    "gate_status": _gate_status_from_row(row),
                    "run_id": row.get("run_id"),
                    "degraded": bool(row.get("degraded")),
                    "revision_count": int(row.get("revision_count", 0)),
                    "final_trade_count": int(row.get("final_trade_count", 0)),
                }
            return {"gate_status": "未審"}
        except Exception as exc:
            logger.warning("gate-status BQ query failed for %s: %s", report_date, exc)

    # Fixture fallback (SKIP_BIGQUERY=1 or BQ unavailable)
    fixture_path = _REPO_ROOT / "fixtures" / "reviewer_log_fixture.json"
    if fixture_path.exists():
        try:
            entries: list[dict[str, Any]] = json.loads(fixture_path.read_text())
            for entry in entries:
                if entry.get("date") == report_date:
                    return {
                        "gate_status": _gate_status_from_row(entry),
                        "run_id": entry.get("run_id"),
                        "degraded": bool(entry.get("degraded")),
                        "revision_count": int(entry.get("revision_count", 0)),
                        "final_trade_count": int(entry.get("final_trade_count", 0)),
                    }
        except Exception as exc:
            logger.warning("gate-status fixture read failed: %s", exc)

    return {"gate_status": "未審"}


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
    _validate_report_date(report_date)
    raw_dict, _ = _try_load_daily_brief_raw_dict(report_date)
    if not raw_dict:
        raise HTTPException(status_code=404, detail=f"No structured report found for {report_date}")

    try:
        from schemas import DailyBriefReport
        model = DailyBriefReport.model_validate(raw_dict)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Report schema error: {exc}") from exc

    env = _get_jinja2_env()
    tmpl = env.get_template("html_export/brief_card.html.j2")
    # profile is a user-supplied query param — pass through Jinja2's autoescaping
    # by NOT marking it safe; autoescape=True handles it at render time.
    html = tmpl.render(report=model, report_date=report_date, profile=profile)

    headers = {}
    if download:
        headers["Content-Disposition"] = f'attachment; filename="brief_{report_date}.html"'
    return HTMLResponse(content=html, headers=headers)


def _env_truthy(var_name: str) -> bool:
    return os.getenv(var_name, "").strip().lower() in ("1", "true", "yes")


def _brief_layouts_runtime_hints() -> dict[str, Any]:
    """Read-only server env for layout/dynamic-render UX (no pipeline side effects)."""
    layout_file = (os.getenv("BRIEF_LAYOUT_FILE") or "").strip()
    return {
        "brief_layout_file": layout_file or None,
        "brief_dynamic_render": _env_truthy("BRIEF_DYNAMIC_RENDER"),
        "report_profile": ((os.getenv("REPORT_PROFILE") or "").strip() or None),
    }


@app.get("/api/brief-layouts")
def list_brief_layout_yaml_files() -> dict[str, Any]:
    """List ``*.yaml`` under ``config/brief_layouts/`` (modularization Phase 4b).

    Read-only inventory for PWA layout UX (``visualization_plan`` V3). Filenames are
    examples or operator-supplied layouts; merging still happens server-side via
    ``BRIEF_LAYOUT_FILE``. Response includes ``runtime_hints`` (server env snapshot;
    no secrets).
    """
    layouts_dir = _REPO_ROOT / "config" / "brief_layouts"
    if not layouts_dir.is_dir():
        return {"layouts": [], "runtime_hints": _brief_layouts_runtime_hints()}

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
    return {"layouts": layouts, "runtime_hints": _brief_layouts_runtime_hints()}


@app.get("/api/reports/qsrec-stats")
def get_qsrec_stats(days: int = Query(default=7, ge=1, le=90)) -> dict[str, Any]:
    """Aggregate QSREC reviewer_log stats for the last N days.

    Returns pass_rate_pct, avg_trade_count, degraded_count, fail_count, pass_count.
    Uses worst-of-two aggregation: if ANY track (CRYPTO/AI) degraded on a given day,
    that day is counted as degraded.
    Empty state when no reviewer_log entries exist: all zeros.
    """
    skip_bq = os.getenv("SKIP_BIGQUERY", "0") == "1"

    if not skip_bq:
        try:
            client = _get_bq_client()
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("days", "INT64", days),
                ]
            )
            rows = list(
                client.query(
                    f"""
                    WITH daily_agg AS (
                      SELECT
                        COALESCE(report_date, DATE(created_at)) AS rd,
                        LOGICAL_OR(degraded) AS degraded,
                        MAX(revision_count) AS revision_count,
                        SUM(final_trade_count) AS final_trade_count
                      FROM `{REVIEWER_LOG_TABLE}`
                      WHERE DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL @days DAY)
                      GROUP BY rd
                    )
                    SELECT
                      COUNT(*) AS total_days,
                      COUNTIF(NOT degraded AND revision_count < 2) AS pass_count,
                      COUNTIF(degraded) AS degraded_count,
                      COUNTIF(NOT degraded AND revision_count >= 2) AS fail_count,
                      IFNULL(AVG(final_trade_count), 0) AS avg_trade_count
                    FROM daily_agg
                    """,
                    job_config=job_config,
                ).result()
            )
            if rows:
                r = dict(rows[0])
                total = int(r.get("total_days", 0))
                pass_count = int(r.get("pass_count", 0))
                return {
                    "days": days,
                    "total_days": total,
                    "pass_count": pass_count,
                    "degraded_count": int(r.get("degraded_count", 0)),
                    "fail_count": int(r.get("fail_count", 0)),
                    "pass_rate_pct": round(pass_count / total * 100, 1) if total else 0.0,
                    "avg_trade_count": round(float(r.get("avg_trade_count", 0)), 1),
                }
        except Exception as exc:
            logger.warning("qsrec-stats BQ query failed: %s", exc)

    # Fixture fallback (SKIP_BIGQUERY=1 or BQ unavailable)
    fixture_path = _REPO_ROOT / "fixtures" / "reviewer_log_fixture.json"
    if fixture_path.exists():
        try:
            entries: list[dict[str, Any]] = json.loads(fixture_path.read_text())
            from datetime import date as _date, timedelta as _timedelta
            cutoff = (_date.today() - _timedelta(days=days)).isoformat()
            recent = [e for e in entries if e.get("date", "") >= cutoff]
            total = len(recent)
            pass_count = sum(
                1 for e in recent
                if not e.get("degraded") and int(e.get("revision_count", 0)) < 2
            )
            degraded_count = sum(1 for e in recent if e.get("degraded"))
            fail_count = sum(
                1 for e in recent
                if not e.get("degraded") and int(e.get("revision_count", 0)) >= 2
            )
            avg_tc = (
                sum(int(e.get("final_trade_count", 0)) for e in recent) / total
                if total else 0.0
            )
            return {
                "days": days,
                "total_days": total,
                "pass_count": pass_count,
                "degraded_count": degraded_count,
                "fail_count": fail_count,
                "pass_rate_pct": round(pass_count / total * 100, 1) if total else 0.0,
                "avg_trade_count": round(avg_tc, 1),
            }
        except Exception as exc:
            logger.warning("qsrec-stats fixture read failed: %s", exc)

    return {
        "days": days,
        "total_days": 0,
        "pass_count": 0,
        "degraded_count": 0,
        "fail_count": 0,
        "pass_rate_pct": 0.0,
        "avg_trade_count": 0.0,
    }


@app.get("/api/gate-failures")
def get_gate_failures(days: int = Query(default=7, ge=1, le=30)) -> dict[str, Any]:
    """Recent ``gate_failure_log`` rows for the Settings hub (FE-4, queue 49).

    Read-only summary view. Returns up to 20 rows ordered by timestamp DESC,
    each with ``timestamp``, ``attempt``, ``blocking_count``, ``warning_count``,
    ``issue_count``, ``profile``, ``used_fallback``, ``issues_preview``.
    Falls back to ``fixtures/gate_failure_log_fixture.json`` when BQ is unavailable.
    """
    skip_bq = os.getenv("SKIP_BIGQUERY", "0") == "1"

    if not skip_bq:
        try:
            client = _get_bq_client()
            job_config = bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("days", "INT64", days)],
            )
            rows = list(
                client.query(
                    f"""
                    SELECT
                      timestamp,
                      attempt,
                      blocking_count,
                      warning_count,
                      issue_count,
                      profile,
                      used_fallback,
                      issues_preview
                    FROM `{GATE_FAILURE_LOG_TABLE}`
                    WHERE TIMESTAMP_TRUNC(timestamp, DAY) >= TIMESTAMP_SUB(
                      CURRENT_TIMESTAMP(), INTERVAL @days DAY
                    )
                    ORDER BY timestamp DESC
                    LIMIT 20
                    """,
                    job_config=job_config,
                ).result()
            )
            entries = [
                {
                    "timestamp": str(r.get("timestamp")) if r.get("timestamp") is not None else None,
                    "attempt": int(r.get("attempt") or 0),
                    "blocking_count": int(r.get("blocking_count") or 0),
                    "warning_count": int(r.get("warning_count") or 0),
                    "issue_count": int(r.get("issue_count") or 0),
                    "profile": r.get("profile"),
                    "used_fallback": bool(r.get("used_fallback")),
                    "issues_preview": r.get("issues_preview") or "",
                }
                for r in rows
            ]
            return {"days": days, "count": len(entries), "entries": entries, "source": "bq"}
        except Exception as exc:
            logger.warning("gate-failures BQ query failed: %s", exc)

    fixture_path = _REPO_ROOT / "fixtures" / "gate_failure_log_fixture.json"
    if fixture_path.exists():
        try:
            entries: list[dict[str, Any]] = json.loads(fixture_path.read_text())
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            recent = [e for e in entries if str(e.get("timestamp", "")) >= cutoff][:20]
            return {"days": days, "count": len(recent), "entries": recent, "source": "fixture"}
        except Exception as exc:
            logger.warning("gate-failures fixture read failed: %s", exc)

    return {"days": days, "count": 0, "entries": [], "source": "empty"}


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


@app.get("/api/positions")
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


@app.get("/api/analysis/{symbol}")
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


@app.get("/api/quant/signals")
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


@app.get("/api/quant/backtest")
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


def _sse_auth_ok(request: Request) -> bool:
    key = (os.getenv("API_STREAM_AUTH_KEY") or "").strip()
    if not key:
        return True
    if request.headers.get("X-QS-Stream-Key") == key or request.query_params.get("stream_key") == key:
        return True
    token = request.headers.get("X-QS-Stream-Token") or request.query_params.get("stream_token")
    return sse_token.verify(token)


def _sse_mint_auth_ok(request: Request) -> bool:
    """Minting a short-lived SSE token requires the long-lived key (header or query)."""
    key = (os.getenv("API_STREAM_AUTH_KEY") or "").strip()
    if not key:
        return False
    return (
        request.headers.get("X-QS-Stream-Key") == key
        or request.query_params.get("stream_key") == key
    )


@app.post("/api/stream/token")
def post_stream_token(request: Request) -> dict[str, Any]:
    """Mint a short-lived token for SSE auth (Phase 3 backlog closure).

    404 unless ``API_STREAM_AUTH_KEY`` is set; the caller must present that key
    via ``X-QS-Stream-Key`` header (preferred) or ``stream_key`` query parameter.
    TTL is bounded by ``SSE_TOKEN_TTL_SECONDS`` (default 60s, clamped 10–600s).
    """
    if not (os.getenv("API_STREAM_AUTH_KEY") or "").strip():
        raise HTTPException(status_code=404, detail="stream tokens disabled; set API_STREAM_AUTH_KEY")
    if not _sse_mint_auth_ok(request):
        raise HTTPException(status_code=403, detail="invalid or missing stream auth key")
    minted = sse_token.mint()
    return {
        "token": minted.token,
        "expires_at": minted.expires_at,
        "ttl_seconds": minted.ttl_seconds,
    }


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


def _parse_sse_watch_symbols_param(raw: str | None, max_n: int = 8) -> list[str]:
    """Parse ``watch_symbols=BTC,NVDA`` for war-room SSE ``symbol_quote`` events."""
    if not raw or not str(raw).strip():
        return []
    out: list[str] = []
    for part in str(raw).split(","):
        if len(out) >= max_n:
            break
        piece = part.strip()
        if not piece:
            continue
        try:
            out.append(validate_symbol_for_snapshot(piece))
        except ValueError:
            continue
    return out


@app.get("/api/paper/lifecycle")
def get_paper_lifecycle(
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    """Paper lifecycle summary from execution_intents.jsonl; read-only, no quote calls."""
    return build_paper_lifecycle_payload(limit=limit, status=status, category=category)


@app.get("/api/paper/pnl")
def get_paper_pnl(
    limit: int = Query(default=200, ge=1, le=500),
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
) -> dict[str, Any]:
    """Paper realized/unrealized P&L with best-effort quotes for active rows."""
    return build_paper_lifecycle_payload(
        limit=limit,
        status=status,
        category=category,
        quote_fn=fetch_symbol_quote,
        include_quotes=True,
    )


@app.get("/api/paper/transparency-letter")
def get_paper_transparency_letter(
    month: str | None = Query(default=None, description="Optional month in YYYY-MM format."),
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, Any]:
    """Internal monthly paper transparency letter; never publishes externally."""
    try:
        return build_transparency_letter(month=month, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
async def stream_war_room(
    request: Request,
    watch_symbols: str | None = Query(
        default=None,
        description="Comma-separated symbols (max 8) for ``symbol_quote`` SSE events.",
    ),
):
    """SSE: war-room snapshot + optional per-symbol quotes (queue 29). Disabled unless ``TERMINAL_SSE_ENABLED=1``."""
    if os.getenv("TERMINAL_SSE_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="SSE disabled; set TERMINAL_SSE_ENABLED=1")
    if not _sse_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing stream auth")

    interval = float(os.getenv("TERMINAL_SSE_POLL_SEC", "2") or "2")
    interval = max(0.5, min(interval, 30.0))

    # Explicit per-connection event-rate cap (Phase 3 backlog closure).
    # 0 / unset = disabled. Counted across node_complete / price_alert /
    # war_room_update / symbol_quote yields; keepalive comments are exempt.
    try:
        max_eps = float(os.getenv("SSE_MAX_EVENTS_PER_SEC", "0") or "0")
    except (TypeError, ValueError):
        max_eps = 0.0
    max_eps = max(0.0, min(max_eps, 100.0))

    async def event_gen():
        last_fp: dict[str, Any] | None = None
        last_quote_sigs: dict[str, str] = {}
        window_start = time.time()
        window_count = 0
        throttled_in_window = False

        def _allow_event() -> bool:
            nonlocal window_start, window_count, throttled_in_window
            if max_eps <= 0:
                return True
            now = time.time()
            if now - window_start >= 1.0:
                window_start = now
                window_count = 0
                throttled_in_window = False
            if window_count < max_eps:
                window_count += 1
                return True
            return False

        while True:
            if await request.is_disconnected():
                break

            # Drain per-node events first — these are granular state transitions.
            node_events = drain_graph_node_events()
            for event in node_events:
                if not _allow_event():
                    if not throttled_in_window:
                        throttled_in_window = True
                        warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                        yield f"event: throttled\ndata: {warn}\n\n"
                    break
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: node_complete\ndata: {payload}\n\n"

            # Drain price-alert events (M4 slice 3): triggered alerts → PWA toast.
            alert_events = drain_price_alert_events()
            for event in alert_events:
                if not _allow_event():
                    if not throttled_in_window:
                        throttled_in_window = True
                        warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                        yield f"event: throttled\ndata: {warn}\n\n"
                    break
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: price_alert\ndata: {payload}\n\n"

            # Full war-room snapshot when fingerprint changes.
            fp = _war_room_fingerprint()
            if fp != last_fp and _allow_event():
                last_fp = fp
                body = get_war_room_latest()
                payload = json.dumps(body, ensure_ascii=False)
                yield f"event: war_room_update\ndata: {payload}\n\n"

            watch_list = _parse_sse_watch_symbols_param(watch_symbols or request.query_params.get("watch_symbols"))
            for sym in watch_list:
                raw = fetch_symbol_quote(sym)
                quote_obj = {
                    "symbol": raw.get("symbol"),
                    "last": raw.get("last"),
                    "as_of": str(raw.get("as_of") or ""),
                    "change_pct_1d": raw.get("change_pct_1d"),
                    "currency": raw.get("currency"),
                    "error": raw.get("error"),
                    "cached": raw.get("cached"),
                }
                sig = json.dumps(quote_obj, ensure_ascii=False, sort_keys=True)
                if last_quote_sigs.get(sym) != sig:
                    if not _allow_event():
                        if not throttled_in_window:
                            throttled_in_window = True
                            warn = json.dumps({"reason": "rate_limit", "max_eps": max_eps}, ensure_ascii=False)
                            yield f"event: throttled\ndata: {warn}\n\n"
                        break
                    last_quote_sigs[sym] = sig
                    envelope = {"type": "symbol_quote", "symbol": sym, "quote": quote_obj}
                    yield f"event: symbol_quote\ndata: {json.dumps(envelope, ensure_ascii=False)}\n\n"

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
async def post_paper_execution_tick(request: Request) -> dict[str, Any]:
    """Run one paper simulation pass (M5). Disabled unless ``PAPER_TICK_HTTP_ENABLED=1``."""
    if os.getenv("PAPER_TICK_HTTP_ENABLED", "0").lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=404, detail="paper tick HTTP disabled")
    if not _paper_tick_auth_ok(request):
        raise HTTPException(status_code=403, detail="Invalid or missing paper tick auth")
    if _paper_tick_lock.locked():
        raise HTTPException(status_code=409, detail="paper tick already in progress")
    async with _paper_tick_lock:
        written = run_paper_execution_tick()
    return {"ok": True, "written": len(written), "rows": written}
