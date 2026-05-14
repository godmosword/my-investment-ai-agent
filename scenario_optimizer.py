"""Queue 28d: deterministic scenario presets and target hints (paper + portfolio only).

All numbers come from ``execution_intents`` JSONL and ``portfolio_holdings`` cost basis
rows — no LLM-derived prices and no live market fetches. Suggestions require human review.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from execution_intents import intent_store_mtime, latest_execution_intents
from paper_lifecycle import ACTIVE_STATUSES
from portfolio_holdings import load_holdings
from track_record import build_track_record_payload, load_closed_records


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


def _portfolio_weights(holdings: list[dict[str, Any]]) -> dict[str, float]:
    notionals: dict[str, float] = {}
    for row in holdings:
        sym = _upper(row.get("symbol"))
        if not sym:
            continue
        shares = _float_or_none(row.get("shares")) or 0.0
        cost = _float_or_none(row.get("cost_basis")) or 0.0
        notionals[sym] = notionals.get(sym, 0.0) + max(shares * cost, 0.0)
    total = sum(notionals.values())
    if total <= 0:
        return {}
    return {sym: val / total for sym, val in notionals.items()}


def _concentration_hhi(weights: dict[str, float]) -> float:
    return sum(w * w for w in weights.values()) if weights else 0.0


def _as_of_iso(mtime: float) -> str:
    if not mtime:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return (
        datetime.fromtimestamp(mtime, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_scenario_suggestions(*, limit: int = 500) -> dict[str, Any]:
    rows = latest_execution_intents(limit=limit, dedupe=True, sort_by="updated_desc")
    holdings = load_holdings()
    weights = _portfolio_weights(holdings)
    hhi = _concentration_hhi(weights)
    top_syms = sorted(weights.keys(), key=lambda s: weights[s], reverse=True)[:5]

    closed = load_closed_records(limit=min(limit, 2000))
    tr = build_track_record_payload(closed)
    summary = tr.get("summary") or {}

    active_rows = [r for r in rows if _upper(r.get("status")) in ACTIVE_STATUSES]
    by_asset_active: dict[str, int] = {}
    for r in active_rows:
        sym = _upper(r.get("asset"))
        if sym:
            by_asset_active[sym] = by_asset_active.get(sym, 0) + 1

    overlap = [s for s in by_asset_active if s in weights]

    # Scenario presets: notional % shift suggestions (deterministic bounds).
    reduce_pct = min(15.0, max(0.0, round((hhi - 0.2) * 45.0, 1))) if hhi > 0.2 else 0.0
    add_diversify = min(10.0, max(0.0, round(len(overlap) * 2.5, 1))) if overlap else 0.0

    scenarios = [
        {
            "id": "defensive",
            "label": "Defensive tilt",
            "notional_shift_pct": -reduce_pct,
            "rationale_codes": ["HIGH_HHI"] if hhi > 0.2 else ["BASELINE"],
            "notes": (
                f"Largest book weights: {', '.join(f'{s} {weights[s]*100:.1f}%' for s in top_syms[:3]) or 'n/a'}; "
                f"HHI concentration index {hhi:.3f}."
            ),
        },
        {
            "id": "base",
            "label": "Hold structure",
            "notional_shift_pct": 0.0,
            "rationale_codes": ["NEUTRAL"],
            "notes": "No automatic rebalance; review overlap between portfolio cost basis and active paper legs.",
        },
        {
            "id": "opportunistic",
            "label": "Opportunistic trim",
            "notional_shift_pct": -add_diversify,
            "rationale_codes": ["ACTIVE_OVERLAP"] if overlap else ["NEUTRAL"],
            "notes": (
                f"Active paper legs overlapping portfolio symbols: {', '.join(overlap) or 'none'} "
                f"({sum(by_asset_active[s] for s in overlap)} open rows)."
            ),
        },
    ]

    target_hints: list[dict[str, Any]] = []
    for r in active_rows:
        sym = _upper(r.get("asset"))
        if not sym:
            continue
        entry = _float_or_none(r.get("paper_fill_price")) or _float_or_none(r.get("reference_entry_price"))
        tgt = _float_or_none(r.get("reference_target_price"))
        stp = _float_or_none(r.get("reference_stop_price"))
        direction = _upper(r.get("direction"))
        hint: dict[str, Any] = {
            "signal_id": str(r.get("signal_id") or ""),
            "asset": sym,
            "direction": direction,
            "reference_entry_price": entry,
            "reference_target_price": tgt,
            "reference_stop_price": stp,
            "in_portfolio": sym in weights,
            "suggestions": [],
        }
        if entry and tgt and entry > 0:
            dist_pct = abs(tgt - entry) / entry * 100.0
            hint["suggestions"].append(
                {
                    "kind": "target_distance",
                    "value_pct": round(dist_pct, 2),
                    "text": f"Row target is {dist_pct:.1f}% from entry anchor (from intent fields only).",
                }
            )
        if entry and stp and entry > 0:
            risk_pct = abs(entry - stp) / entry * 100.0
            hint["suggestions"].append(
                {
                    "kind": "stop_distance",
                    "value_pct": round(risk_pct, 2),
                    "text": f"Row stop is {risk_pct:.1f}% from entry anchor (from intent fields only).",
                }
            )
        if hint["suggestions"]:
            target_hints.append(hint)

    mtime = intent_store_mtime()
    return {
        "enabled": True,
        "as_of": _as_of_iso(mtime),
        "sources": {
            "execution_intents": "EXECUTION_INTENT_STORE",
            "portfolio_holdings": "PORTFOLIO_HOLDINGS_FILE",
        },
        "disclaimer": (
            "Internal planning only. Uses cost-basis notionals (not mark-to-market). "
            "Does not place orders and does not promise returns. Human confirmation required."
        ),
        "portfolio": {
            "positions": len(holdings),
            "concentration_hhi": round(hhi, 4),
            "top_symbols": [{"symbol": s, "weight_pct": round(weights[s] * 100.0, 2)} for s in top_syms],
        },
        "paper": {
            "active_open_count": len(active_rows),
            "active_by_asset": dict(sorted(by_asset_active.items(), key=lambda kv: (-kv[1], kv[0]))),
            "overlap_with_portfolio": overlap,
        },
        "track_record_summary": {
            "closed_count": summary.get("total_closed"),
            "win_rate_pct": summary.get("hit_rate_pct"),
            "avg_return_pct": summary.get("avg_return_pct"),
        },
        "scenarios": scenarios,
        "target_hints": target_hints[:50],
    }
