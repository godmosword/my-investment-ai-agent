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


def latest_execution_intents(limit: int = 20) -> list[dict[str, Any]]:
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
    return rows[-limit:]
