"""Monthly internal transparency letter read model for paper-tracked signals."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from execution_intents import latest_execution_intents
from paper_lifecycle import CLOSED_STATUSES
from portfolio_holdings import load_holdings
from signal_quality import enrich_signal_quality


MIN_PUBLISHABLE_SAMPLE = 5


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


def _return_pct(row: dict[str, Any]) -> float | None:
    entry = _entry(row)
    exit_price = _exit(row)
    direction = _upper(row.get("direction"))
    if entry is None or exit_price is None or entry <= 0:
        return None
    if direction == "LONG":
        return (exit_price - entry) / entry * 100.0
    if direction == "SHORT":
        return (entry - exit_price) / entry * 100.0
    return None


def _month_from_row(row: dict[str, Any]) -> str:
    ts = str(row.get("status_updated_at") or row.get("created_at") or "").strip()
    return ts[:7] if re.fullmatch(r"\d{4}-\d{2}.*", ts) else ""


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _validate_month(month: str | None) -> str:
    raw = str(month or _current_month()).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", raw):
        raise ValueError("month must be YYYY-MM")
    return raw


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _letter_markdown(month: str, summary: dict[str, Any], alignment: dict[str, Any]) -> str:
    sample = int(summary["closed_count"])
    publishable = bool(summary["publishable"])
    status_line = (
        "Internal review only: sample size is below the public disclosure threshold."
        if not publishable
        else "Sample threshold met for internal review; public use still requires human approval."
    )
    return "\n".join(
        [
            f"# Paper Transparency Letter — {month}",
            "",
            status_line,
            "",
            f"- Closed paper signals: {sample}",
            f"- Win rate: {summary['win_rate_pct']:.1f}%",
            f"- Average return: {summary['avg_return_pct']:.1f}%",
            f"- Best / worst: {summary['best_return_pct']:.1f}% / {summary['worst_return_pct']:.1f}%",
            f"- Average quality score: {summary['avg_quality_score']:.1f}",
            f"- Portfolio-aligned symbols: {', '.join(alignment['matched_symbols']) or 'none'}",
        ]
    )


def build_transparency_letter(month: str | None = None, *, limit: int = 500) -> dict[str, Any]:
    """Build an internal monthly transparency letter from closed paper signals.

    This is deliberately read-only and uses only paper-tracked rows plus the local
    portfolio JSONL symbols for alignment. It does not publish externally.
    """
    normalized_month = _validate_month(month)
    rows = latest_execution_intents(limit=limit, dedupe=True, sort_by="updated_desc")
    closed_rows = [
        row
        for row in rows
        if _upper(row.get("status")) in CLOSED_STATUSES and _month_from_row(row) == normalized_month
    ]

    enriched_rows: list[dict[str, Any]] = []
    for raw_row in closed_rows:
        row = enrich_signal_quality(raw_row)
        ret = _return_pct(row)
        enriched_rows.append(
            {
                "signal_id": row.get("signal_id"),
                "asset": _upper(row.get("asset")),
                "direction": _upper(row.get("direction")),
                "category": _upper(row.get("category")),
                "status_updated_at": row.get("status_updated_at"),
                "entry_price": _entry(row),
                "exit_price": _exit(row),
                "return_pct": ret,
                "quality_score": row.get("quality_score"),
                "quality_grade": row.get("quality_grade"),
                "thesis_one_liner": row.get("thesis_one_liner") or "",
            }
        )

    returns = [float(row["return_pct"]) for row in enriched_rows if row.get("return_pct") is not None]
    wins = sum(1 for value in returns if value > 0)
    losses = sum(1 for value in returns if value < 0)
    quality_scores = [
        float(row["quality_score"])
        for row in enriched_rows
        if row.get("quality_score") is not None
    ]
    grade_counts = Counter(str(row.get("quality_grade") or "ungraded") for row in enriched_rows)

    paper_symbols = sorted({str(row.get("asset") or "").upper() for row in enriched_rows if row.get("asset")})
    portfolio_symbols = sorted(
        {
            str(row.get("symbol") or "").strip().upper()
            for row in load_holdings()
            if str(row.get("symbol") or "").strip()
        }
    )
    paper_set = set(paper_symbols)
    portfolio_set = set(portfolio_symbols)
    alignment = {
        "portfolio_symbols": portfolio_symbols,
        "paper_symbols": paper_symbols,
        "matched_symbols": sorted(paper_set & portfolio_set),
        "paper_only_symbols": sorted(paper_set - portfolio_set),
        "portfolio_only_symbols": sorted(portfolio_set - paper_set),
    }

    summary = {
        "closed_count": len(enriched_rows),
        "wins": wins,
        "losses": losses,
        "win_rate_pct": wins / len(returns) * 100.0 if returns else 0.0,
        "avg_return_pct": _avg(returns),
        "best_return_pct": max(returns) if returns else 0.0,
        "worst_return_pct": min(returns) if returns else 0.0,
        "avg_quality_score": _avg(quality_scores),
        "quality_counts": dict(grade_counts),
        "min_publishable_sample": MIN_PUBLISHABLE_SAMPLE,
        "publishable": len(enriched_rows) >= MIN_PUBLISHABLE_SAMPLE,
    }

    return {
        "as_of": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "month": normalized_month,
        "source": "execution_intents.jsonl+portfolio_holdings.jsonl",
        "summary": summary,
        "alignment": alignment,
        "rows": enriched_rows,
        "letter_markdown": _letter_markdown(normalized_month, summary, alignment),
    }
