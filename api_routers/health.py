import os
from typing import Any

from fastapi import APIRouter

from config import (
    GATE_FAILURE_LOG_TABLE,
    LLM_RUN_LOG_TABLE,
    OPTIONS_GEX_HISTORY_TABLE,
    OPTIONS_UNUSUAL_TRADES_TABLE,
    RECOMMENDATIONS_TABLE,
)

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _configured(value: str | None) -> bool:
    return bool(str(value or "").strip())


def _item(id: str, label: str, ok: bool, source: str, hint: str) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "status": "ready" if ok else "pending",
        "source": source,
        "hint": "" if ok else hint,
    }


@router.get("/api/data-health")
def data_health() -> dict[str, Any]:
    options_ok = _configured(OPTIONS_GEX_HISTORY_TABLE) and _configured(
        OPTIONS_UNUSUAL_TRADES_TABLE
    )
    portfolio_backend = os.getenv("PORTFOLIO_STORE_BACKEND", "jsonl").strip().lower()
    portfolio_ok = portfolio_backend != "bigquery" or _configured(os.getenv("PORTFOLIO_HOLDINGS_TABLE"))
    portfolio_source = "BigQuery" if portfolio_backend == "bigquery" else "JSONL"
    return {
        "enabled": True,
        "items": [
            _item(
                "reports",
                "Daily Brief / Gate",
                _configured(LLM_RUN_LOG_TABLE) and _configured(GATE_FAILURE_LOG_TABLE),
                "BigQuery",
                "Set GCP_PROJECT_ID so llm_run_log and gate_failure_log resolve.",
            ),
            _item(
                "recommendations",
                "Recommendations",
                _configured(RECOMMENDATIONS_TABLE),
                "BigQuery",
                "Set GCP_PROJECT_ID so trade_recommendations resolves.",
            ),
            _item(
                "options",
                "Options Flow + GEX",
                options_ok,
                "BigQuery + Polygon",
                "Create POLYGON_API_KEY, run options DDL, and set OPTIONS_GEX_HISTORY_TABLE / OPTIONS_UNUSUAL_TRADES_TABLE.",
            ),
            _item(
                "portfolio",
                "Portfolio Holdings",
                portfolio_ok,
                portfolio_source,
                "Set PORTFOLIO_HOLDINGS_TABLE or switch PORTFOLIO_STORE_BACKEND=jsonl.",
            ),
            _item(
                "news",
                "Tech News",
                _configured(os.getenv("TECH_PULSE_FIRESTORE_COLLECTION") or "tech_pulse_items"),
                "Firestore",
                "Ensure TECH_PULSE_FIRESTORE_PROJECT/COLLECTION and ingestion job are configured.",
            ),
        ],
    }
