import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from config import (
    GATE_FAILURE_LOG_TABLE,
    LLM_RUN_LOG_TABLE,
    OPTIONS_GEX_BY_STRIKE_TABLE,
    OPTIONS_GEX_HISTORY_TABLE,
    OPTIONS_SNAPSHOTS_TABLE,
    OPTIONS_UNUSUAL_TRADES_TABLE,
    RECOMMENDATION_OUTCOMES_TABLE,
    RECOMMENDATIONS_TABLE,
)
from execution_intents import latest_execution_intents
from portfolio_holdings import load_holdings
from track_record import load_track_record_records

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _configured(value: str | None) -> bool:
    return bool(str(value or "").strip())


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _item(
    id: str,
    label: str,
    status: str,
    source: str,
    hint: str = "",
    *,
    row_count: int | None = None,
    latest_as_of: str | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "status": status,
        "source": source,
        "hint": hint if status != "ready" else "",
        "row_count": row_count,
        "latest_as_of": latest_as_of,
    }


def _status_from_configured(ok: bool, row_count: int | None = None) -> str:
    if not ok:
        return "pending"
    if row_count == 0:
        return "empty"
    return "ready"


def _parse_as_of(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _status_from_stats(
    configured: bool,
    row_count: int | None,
    latest_as_of: str | None,
    *,
    error: bool = False,
    stale_after_days: int | None = None,
) -> str:
    if not configured:
        return "pending"
    if error:
        return "error"
    if row_count == 0:
        return "empty"
    parsed = _parse_as_of(latest_as_of)
    if stale_after_days is not None and parsed is not None:
        age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
        if age_seconds > stale_after_days * 86400:
            return "stale"
    return "ready"


def _latest_from_rows(rows: list[dict[str, Any]]) -> str | None:
    candidates: list[str] = []
    for row in rows:
        for key in ("updated_at", "created_at", "closed_at", "as_of", "status_updated_at"):
            value = str(row.get(key) or "").strip()
            if value:
                candidates.append(value)
                break
    return sorted(candidates)[-1] if candidates else None


def _safe_portfolio_count() -> tuple[int | None, str | None]:
    try:
        rows = load_holdings()
    except Exception:
        return None, None
    return len(rows), _latest_from_rows(rows)


def _safe_paper_count() -> tuple[int | None, str | None]:
    try:
        rows = latest_execution_intents(limit=1000, dedupe=True, sort_by="updated_desc")
    except Exception:
        return None, None
    return len(rows), _latest_from_rows(rows)


def _safe_track_record_count() -> tuple[int | None, str | None, str]:
    try:
        records, source = load_track_record_records(limit=1000)
    except Exception:
        return None, None, "execution_intents.jsonl"
    return len(records), _latest_from_rows(records), source


def _safe_jsonl_file_count(env_key: str) -> tuple[int | None, str | None]:
    raw = os.getenv(env_key, "").strip()
    if not raw:
        return None, None
    path = Path(raw).expanduser()
    if not path.is_file():
        return 0, None
    try:
        rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except Exception:
        return None, None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0)
    return len(rows), mtime.isoformat().replace("+00:00", "Z")


def _safe_bq_table_stats(
    table: str,
    latest_expr: str = "as_of",
) -> tuple[int | None, str | None, bool]:
    if not _configured(table):
        return None, None, False
    try:
        from google.cloud import bigquery

        project = table.split(".", 1)[0]
        client = bigquery.Client(project=project)
        sql = f"""
            SELECT COUNT(1) AS row_count, CAST(MAX({latest_expr}) AS STRING) AS latest_as_of
            FROM `{table}`
        """
        rows = list(client.query(sql).result())
        if not rows:
            return 0, None, False
        row = dict(rows[0])
        latest_as_of = str(row.get("latest_as_of") or "") or None
        return int(row.get("row_count") or 0), latest_as_of, False
    except Exception:
        return None, None, True


def _safe_bq_tables_stats(tables: list[str]) -> tuple[int | None, str | None, bool]:
    total = 0
    latest_values: list[str] = []
    for table in tables:
        row_count, latest_as_of, errored = _safe_bq_table_stats(table)
        if errored:
            return None, None, True
        if row_count is None:
            return None, None, False
        total += row_count
        if latest_as_of:
            latest_values.append(latest_as_of)
    return total, sorted(latest_values)[-1] if latest_values else None, False


@router.get("/api/data-health")
def data_health() -> dict[str, Any]:
    options_tables = [
        OPTIONS_SNAPSHOTS_TABLE,
        OPTIONS_UNUSUAL_TRADES_TABLE,
        OPTIONS_GEX_HISTORY_TABLE,
        OPTIONS_GEX_BY_STRIKE_TABLE,
    ]
    options_ok = all(_configured(table) for table in options_tables)
    portfolio_backend = os.getenv("PORTFOLIO_STORE_BACKEND", "jsonl").strip().lower()
    portfolio_table = os.getenv("PORTFOLIO_HOLDINGS_TABLE", "").strip()
    portfolio_ok = portfolio_backend != "bigquery" or _configured(portfolio_table)
    portfolio_source = "BigQuery" if portfolio_backend == "bigquery" else "JSONL"
    portfolio_error = False
    if portfolio_backend == "bigquery" and portfolio_ok:
        portfolio_count, portfolio_as_of, portfolio_error = _safe_bq_table_stats(
            portfolio_table,
            "COALESCE(updated_at, created_at)",
        )
    elif portfolio_backend == "bigquery":
        portfolio_count, portfolio_as_of = None, None
    else:
        portfolio_count, portfolio_as_of = _safe_portfolio_count()
    paper_count, paper_as_of = _safe_paper_count()
    track_count, track_as_of, track_source = _safe_track_record_count()
    options_count, options_as_of, options_error = (
        _safe_bq_tables_stats(options_tables) if options_ok else (None, None, False)
    )
    news_count, news_as_of = _safe_jsonl_file_count("TECH_PULSE_JSONL_FILE")
    scenario_enabled = os.getenv("SCENARIO_OPTIMIZER_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }
    return {
        "enabled": True,
        "as_of": _now_iso(),
        "items": [
            _item(
                "reports",
                "Daily Brief / Gate",
                _status_from_configured(
                    _configured(LLM_RUN_LOG_TABLE) and _configured(GATE_FAILURE_LOG_TABLE)
                ),
                "BigQuery",
                "Set GCP_PROJECT_ID so llm_run_log and gate_failure_log resolve.",
            ),
            _item(
                "recommendations",
                "Recommendations",
                _status_from_configured(_configured(RECOMMENDATIONS_TABLE)),
                "BigQuery",
                "Set GCP_PROJECT_ID so trade_recommendations resolves.",
            ),
            _item(
                "paper",
                "Paper Lifecycle",
                _status_from_configured(True, paper_count),
                "execution_intents.jsonl",
                "Create or approve at least one paper intent so lifecycle panels have rows.",
                row_count=paper_count,
                latest_as_of=paper_as_of,
            ),
            _item(
                "track-record",
                "Track Record",
                _status_from_configured(
                    _configured(RECOMMENDATION_OUTCOMES_TABLE)
                    or track_source == "execution_intents.jsonl",
                    track_count,
                ),
                track_source,
                "Run scripts/mark_recommendations.py or close paper signals so outcomes can be measured.",
                row_count=track_count,
                latest_as_of=track_as_of,
            ),
            _item(
                "options",
                "Options Flow + GEX",
                _status_from_stats(
                    options_ok,
                    options_count,
                    options_as_of,
                    error=options_error,
                    stale_after_days=7,
                ),
                "BigQuery + Polygon",
                (
                    "Create POLYGON_API_KEY, run options DDL, and set OPTIONS_SNAPSHOTS_TABLE / "
                    "OPTIONS_UNUSUAL_TRADES_TABLE / OPTIONS_GEX_HISTORY_TABLE / "
                    "OPTIONS_GEX_BY_STRIKE_TABLE."
                ),
                row_count=options_count,
                latest_as_of=options_as_of,
            ),
            _item(
                "portfolio",
                "Portfolio Holdings",
                _status_from_stats(
                    portfolio_ok,
                    portfolio_count,
                    portfolio_as_of,
                    error=portfolio_error,
                ),
                portfolio_source,
                "Set PORTFOLIO_HOLDINGS_TABLE or switch PORTFOLIO_STORE_BACKEND=jsonl.",
                row_count=portfolio_count,
                latest_as_of=portfolio_as_of,
            ),
            _item(
                "news",
                "Tech News",
                _status_from_configured(_configured(os.getenv("TECH_PULSE_FIRESTORE_COLLECTION") or "tech_pulse_items"), news_count),
                "Firestore",
                "Ensure TECH_PULSE_FIRESTORE_PROJECT/COLLECTION and ingestion job are configured.",
                row_count=news_count,
                latest_as_of=news_as_of,
            ),
            _item(
                "scenario",
                "Scenario Planner",
                "ready" if scenario_enabled else "pending",
                "execution_intents.jsonl + portfolio_holdings",
                "Set SCENARIO_OPTIMIZER_ENABLED=1 when the scenario engine is ready for this environment.",
            ),
        ],
    }
