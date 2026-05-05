"""Shared BigQuery helpers for FastAPI routers (incremental split from ``api.py``)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from google.cloud import bigquery

from config import PROJECT_ID

logger = logging.getLogger(__name__)

_bq_client: bigquery.Client | None = None


def get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
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
