"""Deterministic quality scoring for paper execution intents."""

from __future__ import annotations

import math
from typing import Any


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _grade(score: int) -> str:
    if score >= 80:
        return "A"
    if score >= 65:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def _reference_r_multiple(row: dict[str, Any]) -> float | None:
    entry = _float_or_none(row.get("reference_entry_price"))
    target = _float_or_none(row.get("reference_target_price"))
    stop = _float_or_none(row.get("reference_stop_price"))
    if entry is None or target is None or stop is None:
        return None
    risk = abs(entry - stop)
    if entry <= 0 or risk <= 0:
        return None
    return abs(target - entry) / risk


def evaluate_signal_quality(row: dict[str, Any]) -> dict[str, Any]:
    """Return quality fields for one intent row.

    The score only uses information known at review time. It intentionally does
    not reward or punish later paper P&L, so downstream UI can compare quality
    versus outcome without hindsight leakage.
    """
    score = 50
    reasons: list[str] = []

    try:
        stars = int(row.get("star_rating") or 1)
    except (TypeError, ValueError):
        stars = 1
    if stars >= 2:
        score += 15
        reasons.append("high_conviction")
    else:
        score += 5
        reasons.append("base_conviction")

    thesis = str(row.get("thesis_one_liner") or "").strip()
    if len(thesis) >= 24:
        score += 10
        reasons.append("clear_thesis")
    elif thesis:
        score += 5
        reasons.append("has_thesis")
    else:
        score -= 5
        reasons.append("missing_thesis")

    entry = _float_or_none(row.get("reference_entry_price"))
    target = _float_or_none(row.get("reference_target_price"))
    stop = _float_or_none(row.get("reference_stop_price"))
    if entry is not None and target is not None and stop is not None:
        score += 15
        reasons.append("has_entry_target_stop")
    elif entry is not None:
        score += 5
        reasons.append("has_entry")
    else:
        score -= 10
        reasons.append("missing_entry")

    r_multiple = _reference_r_multiple(row)
    if r_multiple is not None:
        if 1.5 <= r_multiple <= 5:
            score += 10
            reasons.append("balanced_r_multiple")
        elif r_multiple > 0:
            score += 3
            reasons.append("unbalanced_r_multiple")

    if str(row.get("regime") or "").strip():
        score += 5
        reasons.append("has_regime")

    gate_hints = row.get("gate_issue_hints")
    if isinstance(gate_hints, list) and gate_hints:
        penalty = min(30, 15 * len(gate_hints))
        score -= penalty
        reasons.append("gate_warning")

    status = str(row.get("status") or "").strip().upper()
    if status in {"REJECTED", "SUPERSEDED"}:
        score -= 25
        reasons.append("inactive_status")
    elif status in {"APPROVED_FOR_PAPER", "PAPER_SUBMITTED", "PAPER_FILLED"}:
        score += 5
        reasons.append("approved_for_paper")

    score = max(0, min(100, int(round(score))))
    return {
        "quality_score": score,
        "quality_grade": _grade(score),
        "quality_reasons": reasons,
        "quality_model": "qsi_signal_quality_v1",
    }


def enrich_signal_quality(row: dict[str, Any]) -> dict[str, Any]:
    return {**row, **evaluate_signal_quality(row)}
