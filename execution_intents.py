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


# All statuses that may appear in JSONL (worker + client).
ALLOWED_INTENT_STATUSES = frozenset(
    {
        "PENDING_REVIEW",
        "APPROVED_FOR_PAPER",
        "REJECTED",
        "SUPERSEDED",
        "PAPER_SUBMITTED",
        "PAPER_FILLED",
        "PAPER_CLOSED",
    }
)

# Client PATCH only — paper lifecycle rows are written by ``paper_execution`` worker.
CLIENT_PATCHABLE_STATUSES = frozenset(
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
    reference_entry_price: float | None = Field(default=None, description="Optional anchor for paper sim (M5).")
    reference_target_price: float | None = Field(default=None)
    reference_stop_price: float | None = Field(default=None)
    paper_fill_price: float | None = Field(default=None, description="Simulated fill (M5 worker).")
    paper_exit_price: float | None = Field(default=None, description="Simulated exit at stop/target (M5).")


def _normalize_int(value: Any, *, default: int = 1, minimum: int = 1, maximum: int = 2) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _normalize_float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_execution_intent_row(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce legacy / partial JSONL rows into the public blotter contract shape."""
    created_at = str(row.get("created_at") or "").strip()
    normalized = {
        "signal_id": str(row.get("signal_id") or "").strip(),
        "created_at": created_at,
        "category": str(row.get("category") or "").strip().upper(),
        "regime": str(row.get("regime") or "").strip(),
        "asset": str(row.get("asset") or "").strip().upper().lstrip("$"),
        "direction": str(row.get("direction") or "").strip().upper(),
        "star_rating": _normalize_int(row.get("star_rating")),
        "thesis_one_liner": str(row.get("thesis_one_liner") or "").strip(),
        "status": str(row.get("status") or "PENDING_REVIEW").strip().upper(),
        "status_updated_at": str(row.get("status_updated_at") or created_at or "").strip(),
        "status_note": str(row.get("status_note") or "").strip(),
        "reference_entry_price": _normalize_float_or_none(row.get("reference_entry_price")),
        "reference_target_price": _normalize_float_or_none(row.get("reference_target_price")),
        "reference_stop_price": _normalize_float_or_none(row.get("reference_stop_price")),
        "paper_fill_price": _normalize_float_or_none(row.get("paper_fill_price")),
        "paper_exit_price": _normalize_float_or_none(row.get("paper_exit_price")),
    }
    for key in ("prior_recommendation_id", "prior_signal_id", "matched_recommendation_id"):
        value = str(row.get(key) or "").strip()
        if value:
            normalized[key] = value
    return normalized


def _store_path() -> Path:
    raw = (os.getenv("EXECUTION_INTENT_STORE") or ".qsilicon/execution_intents.jsonl").strip()
    return Path(__file__).resolve().parent / raw


def intent_store_mtime() -> float:
    """mtime for SSE fingerprint (local JSONL)."""
    p = _store_path()
    try:
        return float(p.stat().st_mtime)
    except OSError:
        return 0.0


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
        try:
            from war_room_stream import bump_war_room_stream_version

            bump_war_room_stream_version()
        except Exception:
            pass
    except OSError as exc:
        logger.warning("execution intent append failed: %s", exc)
    return rows


def _intent_updated_ts(row: dict[str, Any]) -> str:
    return str(row.get("status_updated_at") or row.get("created_at") or "")


def _intent_created_ts(row: dict[str, Any]) -> str:
    return str(row.get("created_at") or "")


def _iso_ts_to_epoch(ts: str) -> float:
    if not ts:
        return 0.0
    s = ts.strip()
    if not s:
        return 0.0
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s).timestamp()
    except (TypeError, ValueError, OSError):
        return 0.0


def latest_execution_intents(
    limit: int = 20,
    *,
    dedupe: bool = True,
    status: str | None = None,
    category: str | None = None,
    sort_by: str = "updated_desc",
) -> list[dict[str, Any]]:
    """Return the last *limit* intent rows, optionally collapsing JSONL to latest row per ``signal_id``.

    Append-only updates (see ``update_execution_intent_status``) add a new line with the same
    ``signal_id``; with ``dedupe=True`` we return the **last** row per id (Terminal-style blotter).

    Optional ``status`` / ``category`` filter Terminal blotter (case-insensitive substring on status;
    category prefix match on ``CRYPTO`` / ``AI``). ``sort_by`` one of
    ``updated_desc`` (default), ``created_desc``, ``asset_asc``.
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
        tail = rows[-limit:]
        normalized_tail = [normalize_execution_intent_row(r) for r in tail]
        return _filter_and_sort_intents(normalized_tail, status=status, category=category, sort_by=sort_by)[:limit]

    # Last JSONL line per signal_id wins (append-only updates).
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        sid = str(row.get("signal_id") or "").strip()
        if sid:
            by_id[sid] = normalize_execution_intent_row(row)
    merged = list(by_id.values())
    merged = _filter_and_sort_intents(merged, status=status, category=category, sort_by=sort_by)
    return merged[:limit]


def _filter_and_sort_intents(
    rows: list[dict[str, Any]],
    *,
    status: str | None,
    category: str | None,
    sort_by: str,
) -> list[dict[str, Any]]:
    st_sub = (status or "").strip().upper()
    cat_u = (category or "").strip().upper()
    out = rows
    if st_sub:
        out = [r for r in out if st_sub in str(r.get("status") or "").upper()]
    if cat_u:
        out = [r for r in out if str(r.get("category") or "").upper().startswith(cat_u)]
    sort_u = (sort_by or "updated_desc").strip().lower()
    if sort_u == "created_desc":
        out.sort(key=lambda r: _intent_created_ts(r), reverse=True)
    elif sort_u == "asset_asc":
        out.sort(
            key=lambda r: (
                str(r.get("asset") or "").upper(),
                -_iso_ts_to_epoch(_intent_updated_ts(r)),
            ),
        )
    else:
        out.sort(key=lambda r: _intent_updated_ts(r), reverse=True)
    return out


def update_execution_intent_status(
    signal_id: str,
    new_status: str,
    *,
    note: str = "",
    reference_entry_price: float | None = None,
    reference_target_price: float | None = None,
    reference_stop_price: float | None = None,
) -> tuple[dict[str, Any], str | None] | None:
    """Append a status transition row for an existing intent. Does not place orders.

    Returns ``(row, prev_status)`` when a new append-row was written; ``prev_status`` is the
    prior status string for optional BQ audit. Returns ``(row, None)`` when the latest row
    already had the requested status (no append). Returns ``None`` if *signal_id* was not
    found or *new_status* is invalid.
    """
    sid = signal_id.strip()
    status_u = new_status.strip().upper()
    if status_u not in CLIENT_PATCHABLE_STATUSES:
        logger.warning("execution intent status rejected: not client-patchable %s", new_status)
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
        return prev, None

    def _fprev(key: str, override: float | None) -> float | None:
        if override is not None:
            return override
        v = prev.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _fprev_only(key: str) -> float | None:
        v = prev.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

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
            reference_entry_price=_fprev("reference_entry_price", reference_entry_price),
            reference_target_price=_fprev("reference_target_price", reference_target_price),
            reference_stop_price=_fprev("reference_stop_price", reference_stop_price),
            paper_fill_price=_fprev_only("paper_fill_price"),
            paper_exit_price=_fprev_only("paper_exit_price"),
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
        try:
            from war_room_stream import bump_war_room_stream_version

            bump_war_room_stream_version()
        except Exception:
            pass
    except OSError as exc:
        logger.warning("execution intent status append failed: %s", exc)
        return None
    return merged, prev_status


def append_execution_intent_row(row: dict[str, Any]) -> bool:
    """Validate and append one row (worker / paper); bumps SSE version."""
    try:
        validated = ExecutionIntent(**row).model_dump(mode="json")
    except Exception as exc:
        logger.warning("append_execution_intent_row validation failed: %s", exc)
        return False
    path = _store_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(validated, ensure_ascii=False) + "\n")
        try:
            from war_room_stream import bump_war_room_stream_version

            bump_war_room_stream_version()
        except Exception:
            pass
        return True
    except OSError as exc:
        logger.warning("append_execution_intent_row failed: %s", exc)
        return False
