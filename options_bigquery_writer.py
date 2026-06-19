"""BigQuery writers for the Polygon options pipeline (snapshots / unusual / GEX).

Mirrors the conventions in :mod:`bigquery_writer`: ``SKIP_BIGQUERY`` short-circuits,
empty table names skip silently, and writes use ``insert_rows_json`` with a
deterministic ``insert_id`` so a re-run of the same trade_date does not duplicate
rows (R5). All three tables are optional — unset env → no-op.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import date, datetime, timezone

from config import (
    OPTIONS_GEX_HISTORY_TABLE,
    OPTIONS_SNAPSHOTS_TABLE,
    OPTIONS_UNUSUAL_TRADES_TABLE,
    PROJECT_ID,
)

from tools.options.models import GEXResult, OptionSnapshot, UnusualFlowSignal

logger = logging.getLogger(__name__)

SKIP_BIGQUERY = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")


def _insert_id(*parts: object) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def _client(table_id: str):
    """Lazy BigQuery client; project inferred from the table id when possible."""
    from google.cloud import bigquery

    project = table_id.split(".", 1)[0] if "." in table_id else PROJECT_ID
    return bigquery.Client(project=project)


def _insert(table_id: str, rows: list[tuple[str, dict]]) -> bool:
    """Insert ``(insert_id, row)`` pairs. Returns False on skip/empty/error."""
    if SKIP_BIGQUERY or not table_id or not rows:
        if SKIP_BIGQUERY:
            logger.info("SKIP_BIGQUERY set; skipping write to %s", table_id or "(unset)")
        return False
    try:
        client = _client(table_id)
        errors = client.insert_rows_json(
            table_id,
            [r for _, r in rows],
            row_ids=[rid for rid, _ in rows],
        )
        if errors:
            logger.error("options BQ insert errors for %s: %s", table_id, errors)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 — never let telemetry crash the pipeline
        logger.warning("options BQ insert failed for %s: %s", table_id, exc)
        return False


def write_snapshots(underlying: str, trade_date: date, snapshots: list[OptionSnapshot]) -> bool:
    rows: list[tuple[str, dict]] = []
    td = trade_date.isoformat()
    for s in snapshots:
        c = s.contract
        rows.append(
            (
                _insert_id("snap", td, c.ticker),
                {
                    "trade_date": td,
                    "underlying": underlying,
                    "option_ticker": c.ticker,
                    "expiration": c.expiration.isoformat(),
                    "strike": c.strike,
                    "contract_type": c.contract_type.value,
                    "open_interest": s.open_interest,
                    "implied_volatility": s.implied_volatility,
                    "day_volume": s.day_volume,
                    "last_price": s.last_price,
                    "gamma": s.greeks.gamma,
                    "delta": s.greeks.delta,
                    "as_of": s.provenance.as_of.isoformat(),
                    "source": s.provenance.source,
                },
            )
        )
    return _insert(OPTIONS_SNAPSHOTS_TABLE, rows)


def write_unusual(underlying: str, trade_date: date, signals: list[UnusualFlowSignal]) -> bool:
    rows: list[tuple[str, dict]] = []
    td = trade_date.isoformat()
    for sig in signals:
        c = sig.contract
        rows.append(
            (
                _insert_id("unusual", td, c.ticker, sig.signal_type.value, sig.rationale),
                {
                    "trade_date": td,
                    "underlying": underlying,
                    "option_ticker": c.ticker,
                    "signal_type": sig.signal_type.value,
                    "score": sig.score,
                    "premium": sig.premium,
                    "volume": sig.volume,
                    "open_interest": sig.open_interest,
                    "rationale": sig.rationale,
                    "as_of": sig.provenance.as_of.isoformat(),
                    "source": sig.provenance.source,
                },
            )
        )
    return _insert(OPTIONS_UNUSUAL_TRADES_TABLE, rows)


def write_gex(trade_date: date, gex: GEXResult) -> bool:
    td = trade_date.isoformat()
    row = {
        "trade_date": td,
        "underlying": gex.underlying,
        "spot_price": gex.spot_price,
        "total_gex": gex.total_gex,
        "call_gex": gex.call_gex,
        "put_gex": gex.put_gex,
        "contracts_used": gex.contracts_used,
        "as_of": gex.provenance.as_of.isoformat(),
        "method": gex.provenance.method,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
    return _insert(OPTIONS_GEX_HISTORY_TABLE, [(_insert_id("gex", td, gex.underlying), row)])
