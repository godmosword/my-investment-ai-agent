"""Paper signal lifecycle read models built from execution_intents.jsonl."""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from execution_intents import latest_execution_intents
from signal_quality import evaluate_signal_quality


ACTIVE_STATUSES = {"APPROVED_FOR_PAPER", "PAPER_SUBMITTED", "PAPER_FILLED"}
CLOSED_STATUSES = {"PAPER_CLOSED", "CLOSED", "EXITED"}
INACTIVE_STATUSES = {"REJECTED", "SUPERSEDED"}


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _entry(row: dict[str, Any]) -> float | None:
    for key in ("paper_fill_price", "reference_entry_price", "entry_price"):
        value = _float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _exit(row: dict[str, Any]) -> float | None:
    for key in ("paper_exit_price", "paper_exit", "exit_price"):
        value = _float_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _return_pct(direction: str, entry: float, mark: float) -> float | None:
    if entry <= 0:
        return None
    if direction == "LONG":
        return (mark - entry) / entry * 100.0
    if direction == "SHORT":
        return (entry - mark) / entry * 100.0
    return None


def _risk_metrics(row: dict[str, Any], entry: float | None) -> dict[str, Any]:
    target = _float_or_none(row.get("reference_target_price"))
    stop = _float_or_none(row.get("reference_stop_price"))
    if entry is None or entry <= 0:
        return {
            "target_distance_pct": None,
            "stop_distance_pct": None,
            "r_multiple": None,
        }
    target_distance = abs(target - entry) / entry * 100.0 if target is not None else None
    stop_distance = abs(entry - stop) / entry * 100.0 if stop is not None else None
    r_multiple = None
    if target is not None and stop is not None and abs(entry - stop) > 0:
        r_multiple = abs(target - entry) / abs(entry - stop)
    return {
        "target_distance_pct": target_distance,
        "stop_distance_pct": stop_distance,
        "r_multiple": r_multiple,
    }


def _enrich_row(
    row: dict[str, Any],
    quote_fn: Callable[[str], dict[str, Any]] | None,
    *,
    include_quotes: bool,
) -> dict[str, Any]:
    status = _upper(row.get("status"))
    direction = _upper(row.get("direction"))
    asset = _upper(row.get("asset")).lstrip("$")
    entry = _entry(row)
    exit_price = _exit(row)
    mark_price = exit_price
    quote_error = None
    quote_as_of = None
    quote_change_pct_1d = None

    if mark_price is None and include_quotes and status in ACTIVE_STATUSES and quote_fn and asset:
        try:
            quote = quote_fn(asset)
        except Exception:
            quote = {"error": "quote_unavailable"}
        if quote.get("error") or quote.get("last") is None:
            quote_error = "quote_unavailable"
        else:
            mark_price = _float_or_none(quote.get("last"))
            quote_as_of = quote.get("as_of")
            quote_change_pct_1d = _float_or_none(quote.get("change_pct_1d"))

    ret = _return_pct(direction, entry, mark_price) if entry is not None and mark_price is not None else None
    risk = _risk_metrics(row, entry)
    quality = evaluate_signal_quality({**row, **risk})

    return {
        **row,
        "asset": asset,
        "direction": direction,
        "status": status,
        "entry_price": entry,
        "mark_price": mark_price,
        "exit_price": exit_price,
        "return_pct": ret,
        "outcome": "win" if ret is not None and ret > 0 else "loss" if ret is not None and ret < 0 else "flat" if ret == 0 else None,
        "quote_error": quote_error,
        "quote_as_of": quote_as_of,
        "quote_change_pct_1d": quote_change_pct_1d,
        **risk,
        **quality,
    }


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(_upper(row.get("status")) for row in rows)
    closed = [row for row in rows if _upper(row.get("status")) in CLOSED_STATUSES]
    active = [row for row in rows if _upper(row.get("status")) in ACTIVE_STATUSES]
    realized = [
        float(row["return_pct"])
        for row in closed
        if row.get("return_pct") is not None
    ]
    unrealized = [
        float(row["return_pct"])
        for row in active
        if row.get("return_pct") is not None
    ]
    wins = sum(1 for value in realized if value > 0)
    losses = sum(1 for value in realized if value < 0)
    quote_error_count = sum(1 for row in rows if row.get("quote_error"))
    all_returns = realized + unrealized
    quality_scores = [
        float(row["quality_score"])
        for row in rows
        if row.get("quality_score") is not None
    ]
    quality_counts = Counter(str(row.get("quality_grade") or "—") for row in rows)
    quality_return_rows = [
        row
        for row in rows
        if row.get("quality_grade") and row.get("return_pct") is not None
    ]
    returns_by_quality = {}
    for grade in sorted({str(row.get("quality_grade")) for row in quality_return_rows}):
        vals = [float(row["return_pct"]) for row in quality_return_rows if str(row.get("quality_grade")) == grade]
        returns_by_quality[grade] = _avg(vals)
    return {
        "total": len(rows),
        "active_count": len(active),
        "closed_count": len(closed),
        "status_counts": dict(status_counts),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": wins / len(realized) * 100.0 if realized else 0.0,
        "avg_realized_return_pct": _avg(realized),
        "avg_unrealized_return_pct": _avg(unrealized),
        "best_return_pct": max(all_returns) if all_returns else 0.0,
        "worst_return_pct": min(all_returns) if all_returns else 0.0,
        "quote_error_count": quote_error_count,
        "avg_quality_score": _avg(quality_scores),
        "quality_counts": dict(quality_counts),
        "avg_return_by_quality": returns_by_quality,
    }


def build_paper_lifecycle_payload(
    *,
    limit: int = 200,
    status: str | None = None,
    category: str | None = None,
    quote_fn: Callable[[str], dict[str, Any]] | None = None,
    include_quotes: bool = False,
) -> dict[str, Any]:
    rows = latest_execution_intents(
        limit=limit,
        dedupe=True,
        status=status,
        category=category,
        sort_by="updated_desc",
    )
    enriched = [
        _enrich_row(row, quote_fn, include_quotes=include_quotes)
        for row in rows
        if _upper(row.get("status")) not in INACTIVE_STATUSES
    ]
    return {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "summary": _summarize(enriched),
        "rows": enriched,
        "source": "execution_intents.jsonl",
    }
