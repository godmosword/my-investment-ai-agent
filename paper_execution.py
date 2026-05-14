"""Paper execution tick (M5): append-only transitions for APPROVED_FOR_PAPER — no broker orders.

Uses ``fetch_symbol_quote`` vs optional ``reference_*`` prices on the latest intent row.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import bigquery_writer
import execution_intents as execution_intents_mod

from execution_intents import (
    ALLOWED_INTENT_STATUSES,
    ExecutionIntent,
    append_execution_intent_row,
    _utc_now_iso,
)
from symbol_snapshot_service import fetch_symbol_quote

logger = logging.getLogger(__name__)


def _read_all_rows() -> list[dict[str, Any]]:
    path = execution_intents_mod._store_path()
    if not path.is_file():
        return []
    try:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("paper tick read failed: %s", exc)
        return []


def _decide_paper_transition(
    *,
    direction: str,
    last: float,
    entry: float | None,
    target: float | None,
    stop: float | None,
) -> tuple[str, float | None, str] | None:
    """Return (new_status, exit_or_fill_price, reason) or None to skip."""
    d = direction.upper()
    if entry is None or target is None or stop is None:
        return None

    if d == "LONG":
        if last <= stop:
            return "PAPER_CLOSED", float(stop), "stop_hit"
        if last >= target:
            return "PAPER_CLOSED", float(target), "target_hit"
        if last >= entry:
            return "PAPER_FILLED", float(last), "filled_at_market"
        return None

    if d == "SHORT":
        if last >= stop:
            return "PAPER_CLOSED", float(stop), "stop_hit"
        if last <= target:
            return "PAPER_CLOSED", float(target), "target_hit"
        if last <= entry:
            return "PAPER_FILLED", float(last), "filled_at_market"
        return None

    return None


def run_paper_execution_tick() -> list[dict[str, Any]]:
    """Scan latest ``APPROVED_FOR_PAPER`` intents with reference prices; append PAPER_* rows.

    Returns list of rows that were written.
    """
    rows = _read_all_rows()
    if not rows:
        return []

    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("signal_id") or "").strip()
        if sid:
            by_id[sid] = row

    written: list[dict[str, Any]] = []
    now = _utc_now_iso()

    for sid, prev in by_id.items():
        status = str(prev.get("status", "")).strip().upper()
        if status != "APPROVED_FOR_PAPER":
            continue

        asset = str(prev.get("asset") or "").strip().upper().lstrip("$")
        direction = str(prev.get("direction") or "").strip().upper()
        if not asset or direction not in {"LONG", "SHORT"}:
            continue

        def _f(key: str) -> float | None:
            v = prev.get(key)
            if v is None:
                return None
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        entry = _f("reference_entry_price")
        target = _f("reference_target_price")
        stop = _f("reference_stop_price")

        q = fetch_symbol_quote(asset)
        if q.get("error") or q.get("last") is None:
            logger.debug("paper tick skip %s: no quote (%s)", sid, q.get("error"))
            continue

        last = float(q["last"])
        decision = _decide_paper_transition(
            direction=direction,
            last=last,
            entry=entry,
            target=target,
            stop=stop,
        )
        if decision is None:
            continue

        new_status, px, reason = decision
        if new_status not in ALLOWED_INTENT_STATUSES:
            continue

        paper_fill = float(px) if new_status == "PAPER_FILLED" else None
        paper_exit = float(px) if new_status == "PAPER_CLOSED" else None

        try:
            merged = ExecutionIntent(
                signal_id=sid,
                created_at=str(prev.get("created_at") or now),
                category=str(prev.get("category") or "CRYPTO"),
                regime=str(prev.get("regime") or ""),
                asset=asset,
                direction=direction,
                star_rating=max(1, min(2, int(prev.get("star_rating", 1) or 1))),
                thesis_one_liner=str(prev.get("thesis_one_liner", "")).strip(),
                status=new_status,
                status_updated_at=now,
                status_note=f"paper:{reason};quote_as_of={q.get('as_of')}",
                reference_entry_price=entry,
                reference_target_price=target,
                reference_stop_price=stop,
                paper_fill_price=paper_fill,
                paper_exit_price=paper_exit,
            ).model_dump(mode="json")
        except Exception as exc:
            logger.warning("paper tick merge failed for %s: %s", sid, exc)
            continue

        if append_execution_intent_row(merged):
            written.append(merged)
            logger.info("paper tick wrote %s -> %s (%s)", sid, new_status, reason)
            as_of = str(q.get("as_of") or "")
            bigquery_writer.write_paper_execution_audit_row(
                signal_id=sid,
                new_status=new_status,
                reason=reason,
                quote_as_of=as_of,
                asset=asset,
                direction=direction,
                source="paper_tick",
            )

    return written
