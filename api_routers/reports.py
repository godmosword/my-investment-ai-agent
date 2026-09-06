"""``/api/reports*`` and report-gate routes, split out of ``api.py``.

Moved verbatim from ``api.py`` (route paths, query bounds, payload keys and
error codes unchanged). Declaration order is load-bearing: ``/api/reports/
profile-stats`` and ``/api/reports/qsrec-stats`` must stay ahead of
``/api/reports/{report_date}`` or the literal paths get swallowed by the
path-parameter route.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from google.cloud import bigquery

from api_deps import get_bq_client as _bq_singleton
from api_deps import rows_to_dicts
from api_routers.execution_intents import _latest_gate_failure_summary
from config import (
    GATE_FAILURE_LOG_TABLE,
    LLM_RUN_LOG_TABLE,
    METRICS_TABLE,
    RECOMMENDATIONS_TABLE,
    REVIEWER_LOG_TABLE,
)

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from jinja2 import Environment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _get_bq_client() -> bigquery.Client:
    """BQ client accessor; tests monkeypatch ``api_routers.reports._get_bq_client``."""
    return _bq_singleton()


# Module-level Jinja2 env (bytecode-cached, autoescape enabled for XSS safety)
def _build_jinja2_env() -> Environment:  # lazy import avoids a hard Jinja2 dep at startup
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


_JINJA2_ENV: Environment | None = None


def _get_jinja2_env() -> Environment:
    global _JINJA2_ENV
    if _JINJA2_ENV is None:
        _JINJA2_ENV = _build_jinja2_env()
    return _JINJA2_ENV


# ── /api/reports ─────────────────────────────────────────────────────────────

@router.get("/api/reports")
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


@router.get("/api/reports/profile-stats")
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


@router.get("/api/reports/{report_date}/structured")
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


@router.get("/api/reports/{report_date}/gate-status")
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


@router.get("/api/reports/{report_date}/html")
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


@router.get("/api/brief-layouts")
def list_brief_layout_yaml_files() -> dict[str, Any]:
    """List ``*.yaml`` under ``config/brief_layouts/`` (modularization Phase 4b).

    Read-only inventory for PWA layout UX (``visualization_plan`` V3). Filenames are
    examples or operator-supplied layouts; merging still happens server-side via
    ``BRIEF_LAYOUT_FILE``. Response includes ``runtime_hints`` (server env snapshot;
    no secrets).
    """
    import yaml

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


@router.get("/api/reports/qsrec-stats")
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


@router.get("/api/gate-failures")
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


@router.get("/api/reports/{report_date}")
def get_report(report_date: str) -> dict[str, Any]:
    """Return the report summary for a specific date (YYYY-MM-DD)."""
    _validate_report_date(report_date)
    return _load_report_legacy(report_date)



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
