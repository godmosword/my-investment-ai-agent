"""Local execution-intent store for War Room / future OMS handoff.

This module deliberately does not place orders. It only persists deterministic
trade intents so a future execution worker or human reviewer can consume them.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


ALLOWED_INTENT_STATUSES = frozenset(
    {
        "PENDING_REVIEW",
        "APPROVED_FOR_PAPER",
        "REJECTED",
        "SUPERSEDED",
    }
)


class ExecutionIntent(BaseModel):
    signal_id: str = Field(..., description="Deterministic-ish unique id for this signal.")
    created_at: str = Field(..., description="UTC ISO timestamp.")
    category: str = Field(..., description="CRYPTO or AI.")
    regime: str = Field(default="", description="Agreed regime at signal generation time.")
    asset: str = Field(..., description="Ticker without $.")
    direction: str = Field(..., description="LONG or SHORT.")
    star_rating: int = Field(..., ge=1, le=2)
    thesis_one_liner: str = Field(default="")
    status: str = Field(default="PENDING_REVIEW", description="Review/execution lifecycle status.")
    status_updated_at: str | None = Field(
        default=None,
        description="UTC ISO when status last changed (append-only log).",
    )
    status_note: str = Field(default="", description="Optional human note on status transition.")


def _store_path() -> Path:
    raw = (os.getenv("EXECUTION_INTENT_STORE") or ".qsilicon/execution_intents.jsonl").strip()
    return Path(__file__).resolve().parent / raw


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_execution_intents(
    *,
    category: str,
    regime: str | None,
    proposed_trades: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Persist current trade intents for downstream review.

    Returns the normalized intent rows that were written (or would be written if
    the store is unavailable).
    """
    rows: list[dict[str, Any]] = []
    now = _utc_now_iso()
    for idx, item in enumerate(proposed_trades, start=1):
        asset = str(item.get("asset", "")).strip().upper().lstrip("$")
        direction = str(item.get("direction", "")).strip().upper()
        if not asset or direction not in {"LONG", "SHORT"}:
            continue
        signal_id = f"{category.lower()}-{asset.lower()}-{direction.lower()}-{idx}"
        row = ExecutionIntent(
            signal_id=signal_id,
            created_at=now,
            category=category,
            regime=str(regime or ""),
            asset=asset,
            direction=direction,
            star_rating=max(1, min(2, int(item.get("star_rating", 1) or 1))),
            thesis_one_liner=str(item.get("thesis_one_liner", "")).strip(),
            status_updated_at=now,
        ).model_dump(mode="json")
        rows.append(row)

    if not rows:
        return []

    path = _store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("execution intent append failed: %s", exc)
    return rows


def latest_execution_intents(limit: int = 20, *, dedupe: bool = True) -> list[dict[str, Any]]:
    """Return the last *limit* intent rows, optionally collapsing JSONL to latest row per ``signal_id``.

    Append-only updates (see ``update_execution_intent_status``) add a new line with the same
    ``signal_id``; with ``dedupe=True`` we return the **last** row per id (Terminal-style blotter).
    """
    path = _store_path()
    if not path.is_file():
        return []
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("execution intent read failed: %s", exc)
        return []
    if not dedupe:
        return rows[-limit:]

    def _ts(row: dict[str, Any]) -> str:
        return str(row.get("status_updated_at") or row.get("created_at") or "")

    # Last JSONL line per signal_id wins (append-only updates).
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("signal_id") or "").strip()
        if sid:
            by_id[sid] = row
    merged = list(by_id.values())
    merged.sort(key=_ts, reverse=True)
    return merged[:limit]


def update_execution_intent_status(
    signal_id: str,
    new_status: str,
    *,
    note: str = "",
) -> dict[str, Any] | None:
    """Append a status transition row for an existing intent. Does not place orders.

    Returns the new row dict, or ``None`` if *signal_id* was not found or *new_status* is invalid.
    """
    sid = signal_id.strip()
    status_u = new_status.strip().upper()
    if status_u not in ALLOWED_INTENT_STATUSES:
        logger.warning("execution intent status rejected: unknown status %s", new_status)
        return None

    path = _store_path()
    if not path.is_file():
        return None
    try:
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning("execution intent update read failed: %s", exc)
        return None

    prev: dict[str, Any] | None = None
    for row in rows:
        if str(row.get("signal_id", "")).strip() == sid:
            prev = row
    if prev is None:
        return None

    prev_status = str(prev.get("status", "")).strip().upper()
    if prev_status == status_u:
        return prev

    now = _utc_now_iso()
    try:
        merged = ExecutionIntent(
            signal_id=sid,
            created_at=str(prev.get("created_at") or now),
            category=str(prev.get("category") or "CRYPTO"),
            regime=str(prev.get("regime") or ""),
            asset=str(prev.get("asset") or "").strip().upper().lstrip("$"),
            direction=str(prev.get("direction") or "").strip().upper(),
            star_rating=max(1, min(2, int(prev.get("star_rating", 1) or 1))),
            thesis_one_liner=str(prev.get("thesis_one_liner", "")).strip(),
            status=status_u,
            status_updated_at=now,
            status_note=(note or "").strip()[:2000],
        ).model_dump(mode="json")
    except Exception as exc:  # pragma: no cover - pydantic guards bad legacy rows
        logger.warning("execution intent merge failed: %s", exc)
        return None

    if merged["direction"] not in {"LONG", "SHORT"} or not merged["asset"]:
        return None

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(merged, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("execution intent status append failed: %s", exc)
        return None
    return merged
