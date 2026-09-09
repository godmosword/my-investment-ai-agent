"""Shared helpers for FastAPI routers (incremental split from ``api.py``)."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any

from config import PROJECT_ID

logger = logging.getLogger(__name__)

_bq_client: Any = None


def skip_bigquery() -> bool:
    """True when the HTTP API must not open a BigQuery client."""
    return os.getenv("SKIP_BIGQUERY", "").strip().lower() in ("1", "true", "yes")


def get_bq_client() -> Any:
    """Lazy BigQuery client. Raises when ``SKIP_BIGQUERY`` is set."""
    global _bq_client
    if skip_bigquery():
        raise RuntimeError("SKIP_BIGQUERY is set")
    if _bq_client is None:
        from google.cloud import bigquery  # noqa: PLC0415

        _bq_client = bigquery.Client(project=PROJECT_ID)
    return _bq_client


def rows_to_dicts(rows) -> list[dict[str, Any]]:
    """Convert BigQuery RowIterator rows to JSON-serialisable dicts."""
    result = []
    for row in rows:
        result.append(
            {k: v.isoformat() if isinstance(v, (datetime, date)) else v for k, v in row.items()}
        )
    return result
