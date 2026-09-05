"""Track Record calculations for paper-only recommendation outcomes."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from typing import Any, Callable

from execution_intents import latest_execution_intents


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _upper(value: Any) -> str:
    return str(value or "").strip().upper()


def _paper_entry(row: dict[str, Any]) -> float | None:
    for key in ("paper_fill_price", "reference_entry_price", "entry_price"):
        if row.get(key) is not None:
            return _float_or_none(row.get(key))
    return None


def _paper_exit(row: dict[str, Any]) -> float | None:
    for key in ("paper_exit_price", "paper_exit", "exit_price"):
        if row.get(key) is not None:
            return _float_or_none(row.get(key))
    return None


def _return_pct(direction: str, entry: float, exit_price: float) -> float | None:
    if entry <= 0:
        return None
    if direction == "LONG":
        return (exit_price - entry) / entry * 100.0
    if direction == "SHORT":
        return (entry - exit_price) / entry * 100.0
    return None


def normalize_closed_intent(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a latest execution-intent row into a closed Track Record record."""
    status = _upper(row.get("status"))
    if status not in {"PAPER_CLOSED", "CLOSED", "EXITED"}:
        return None
    signal_id = str(row.get("signal_id") or "").strip()
    asset = _upper(row.get("asset")).lstrip("$")
    direction = _upper(row.get("direction"))
    entry = _paper_entry(row)
    exit_price = _paper_exit(row)
    if not signal_id or not asset or direction not in {"LONG", "SHORT"} or entry is None or exit_price is None:
        return None
    ret = _return_pct(direction, entry, exit_price)
    if ret is None:
        return None
    closed_at = str(row.get("status_updated_at") or row.get("closed_at") or row.get("created_at") or "")
    category = _upper(row.get("category"))
    outcome = "win" if ret > 0 else "loss" if ret < 0 else "flat"
    record = {
        "signal_id": signal_id,
        "asset": asset,
        "direction": direction,
        "category": category,
        "status": status,
        "opened_at": str(row.get("created_at") or ""),
        "closed_at": closed_at,
        "entry_price": entry,
        "exit_price": exit_price,
        "return_pct": ret,
        "outcome": outcome,
        "thesis_one_liner": str(row.get("thesis_one_liner") or ""),
        "source": "execution_intents.jsonl",
        "source_id": signal_id,
        "tags": [tag for tag in (category, asset, direction, outcome.upper()) if tag],
    }
    record.update(_prior_link_fields(row))
    return record


def normalize_bigquery_outcome(row: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a recommendation_outcomes row into a Track Record record."""
    signal_id = str(row.get("signal_id") or "").strip()
    asset = _upper(row.get("asset")).lstrip("$")
    direction = _upper(row.get("direction"))
    entry = _float_or_none(row.get("entry_price"))
    exit_price = _float_or_none(row.get("exit_price"))
    mark_price = _float_or_none(row.get("mark_price"))
    ret = _float_or_none(row.get("return_pct"))
    if not signal_id or not asset or direction not in {"LONG", "SHORT"} or entry is None:
        return None
    if exit_price is None and mark_price is None:
        return None
    resolved_exit = exit_price if exit_price is not None else mark_price
    if ret is None and resolved_exit is not None:
        ret = _return_pct(direction, entry, resolved_exit)
    if ret is None:
        return None
    category = _upper(row.get("category"))
    outcome = _upper(row.get("outcome")).lower() or ("win" if ret > 0 else "loss" if ret < 0 else "flat")
    closed_at = str(row.get("as_of") or row.get("created_at") or "")
    record = {
        "signal_id": signal_id,
        "asset": asset,
        "direction": direction,
        "category": category,
        "status": _upper(row.get("status")) or "PAPER_CLOSED",
        "opened_at": "",
        "closed_at": closed_at,
        "entry_price": entry,
        "exit_price": resolved_exit,
        "return_pct": ret,
        "outcome": outcome,
        "thesis_one_liner": "",
        "source": "bigquery",
        "source_id": signal_id,
        "tags": [tag for tag in (category, asset, direction, outcome.upper()) if tag],
    }
    record.update(_prior_link_fields(row))
    return record


def _sort_closed(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda row: str(row.get("closed_at") or row.get("opened_at") or ""), reverse=True)


def load_closed_records(limit: int = 500) -> list[dict[str, Any]]:
    rows = latest_execution_intents(limit=limit, dedupe=True, sort_by="updated_desc")
    records = [record for row in rows if (record := normalize_closed_intent(row)) is not None]
    return _sort_closed(records)


def load_closed_records_from_bigquery(limit: int = 500) -> list[dict[str, Any]]:
    table = os.getenv("RECOMMENDATION_OUTCOMES_TABLE", "").strip()
    if not table:
        return []
    try:
        from google.cloud import bigquery

        project = table.split(".", 1)[0]
        client = bigquery.Client(project=project)
        sql = f"""
            SELECT signal_id, as_of, quote_as_of, asset, direction, category, status,
                   entry_price, mark_price, exit_price, return_pct, outcome, source, created_at
            FROM `{table}`
            WHERE return_pct IS NOT NULL
            ORDER BY as_of DESC
            LIMIT @limit
        """
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(
                query_parameters=[bigquery.ScalarQueryParameter("limit", "INT64", int(limit))]
            ),
        )
        records = [record for row in job.result() if (record := normalize_bigquery_outcome(dict(row))) is not None]
        return _sort_closed(records)
    except Exception:
        return []


def load_track_record_records(limit: int = 500) -> tuple[list[dict[str, Any]], str]:
    bq_records = load_closed_records_from_bigquery(limit=limit)
    if bq_records:
        return bq_records, "bigquery"
    return load_closed_records(limit=limit), "execution_intents.jsonl"


def filter_records_by_tag(records: list[dict[str, Any]], tag: str) -> list[dict[str, Any]]:
    needle = _upper(tag)
    if not needle:
        return records
    out = []
    for row in records:
        tags = {_upper(tag_value) for tag_value in row.get("tags") or []}
        if needle in tags or needle in {_upper(row.get("category")), _upper(row.get("asset")), _upper(row.get("outcome"))}:
            out.append(row)
    return out


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    returns = [_float_or_none(row.get("return_pct")) for row in records]
    returns = [value for value in returns if value is not None]
    total = len(returns)
    wins = sum(1 for value in returns if value > 0)
    losses = sum(1 for value in returns if value < 0)
    flats = total - wins - losses
    hit_rate = wins / total * 100.0 if total else 0.0
    avg_return = sum(returns) / total if total else 0.0

    decimal_returns = [value / 100.0 for value in returns]
    if len(decimal_returns) > 1:
        mean = sum(decimal_returns) / len(decimal_returns)
        variance = sum((value - mean) ** 2 for value in decimal_returns) / (len(decimal_returns) - 1)
        std = math.sqrt(variance)
        sharpe = mean / std * math.sqrt(len(decimal_returns)) if std > 0 else 0.0
    else:
        sharpe = 0.0

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    equity_curve: list[dict[str, Any]] = []
    for row in sorted(records, key=lambda record: str(record.get("closed_at") or record.get("opened_at") or "")):
        ret = _float_or_none(row.get("return_pct"))
        if ret is None:
            continue
        equity *= 1.0 + ret / 100.0
        peak = max(peak, equity)
        drawdown = (equity / peak - 1.0) * 100.0 if peak else 0.0
        max_drawdown = min(max_drawdown, drawdown)
        equity_curve.append(
            {
                "signal_id": row.get("signal_id"),
                "closed_at": row.get("closed_at"),
                "value": equity,
                "return_pct": ret,
                "drawdown_pct": drawdown,
            }
        )

    return {
        "total_closed": total,
        "wins": wins,
        "losses": losses,
        "flats": flats,
        "hit_rate_pct": hit_rate,
        "avg_return_pct": avg_return,
        "sharpe": sharpe,
        "max_drawdown_pct": max_drawdown,
        "cumulative_return_pct": (equity - 1.0) * 100.0 if total else 0.0,
        "equity_curve": equity_curve,
    }


_PRIOR_LINK_KEYS = ("prior_recommendation_id", "prior_signal_id", "matched_recommendation_id")


def _prior_link_fields(row: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in _PRIOR_LINK_KEYS:
        value = str(row.get(key) or "").strip()
        if value:
            out[key] = value
    return out


def _closed_at_sort_key(value: Any) -> str:
    return str(value or "").strip()


def build_inclusion_rules(source: str = "execution_intents.jsonl") -> dict[str, Any]:
    """Source-specific inclusion rules. Quality is not applied. Does not change KPI universe."""
    if source == "bigquery":
        return {
            "source": source,
            "universe": "recommendation_outcomes_with_return",
            "included_statuses": [],
            "required_fields": ["signal_id", "asset", "direction", "entry_price", "return_pct"],
            "accepts_mark_price": True,
            "quality_weighted": False,
            "quality_filter_applied": False,
            "notes": [
                "來源 BigQuery recommendation_outcomes：WHERE return_pct IS NOT NULL。",
                "不限 PAPER_CLOSED／CLOSED／EXITED；出場可用 exit_price 或 mark_price，故可能含市價結算列（含未結 APPROVED_FOR_PAPER 快照）。",
                "本頁未套用 quality 權重。",
            ],
        }
    return {
        "source": source,
        "universe": "paper_tracked_closed_only",
        "included_statuses": ["PAPER_CLOSED", "CLOSED", "EXITED"],
        "required_fields": ["signal_id", "asset", "direction", "entry_price", "exit_price", "return_pct"],
        "accepts_mark_price": False,
        "quality_weighted": False,
        "quality_filter_applied": False,
        "notes": [
            "來源 execution_intents.jsonl：僅 PAPER_CLOSED／CLOSED／EXITED，且須有進場／出場價與可計算報酬。",
            "本頁未套用 quality 權重。",
        ],
    }


def build_prior_alignment(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return linkage evidence only. Never invent a match rate."""
    evidence_field = ""
    linked = 0
    for row in records:
        for key in _PRIOR_LINK_KEYS:
            if str(row.get(key) or "").strip():
                linked += 1
                if not evidence_field:
                    evidence_field = key
                break
    if linked == 0:
        return None
    return {
        "available": True,
        "evidence_field": evidence_field,
        "linked_count": linked,
        "sample_size": len(records),
    }


def build_audit_fields(
    records: list[dict[str, Any]],
    *,
    source: str = "execution_intents.jsonl",
) -> dict[str, Any]:
    """Additive audit meta. Does not change KPI meanings in summarize_records."""
    dated = sorted(
        (_closed_at_sort_key(row.get("closed_at")) for row in records),
        key=lambda value: value,
    )
    dated = [value for value in dated if value]
    returns = [_float_or_none(row.get("return_pct")) for row in records]
    sample_size = sum(1 for value in returns if value is not None)
    as_of = dated[-1] if dated else None
    return {
        "as_of": as_of,
        "period_start": dated[0] if dated else None,
        "period_end": as_of,
        "sample_size": sample_size,
        "inclusion_rules": build_inclusion_rules(source),
        "prior_alignment": build_prior_alignment(records),
    }


def build_track_record_payload(
    records: list[dict[str, Any]],
    *,
    limit: int | None = None,
    offset: int = 0,
    source: str = "execution_intents.jsonl",
) -> dict[str, Any]:
    summary = summarize_records(records)
    summary = {**summary, **build_audit_fields(records, source=source)}
    sliced = records[offset : offset + limit] if limit is not None else records[offset:]
    return {
        "summary": summary,
        "records": sliced,
        "total": len(records),
        "limit": limit,
        "offset": offset,
        "source": source,
    }


def build_mark_to_market_rows(
    rows: list[dict[str, Any]],
    quote_fn: Callable[[str], dict[str, Any]],
    *,
    as_of: str | None = None,
) -> list[dict[str, Any]]:
    """Build rows suitable for optional BigQuery recommendation_outcomes writes."""
    now = as_of or datetime.now(timezone.utc).isoformat()
    out: list[dict[str, Any]] = []
    for row in rows:
        status = _upper(row.get("status"))
        if status in {"REJECTED", "SUPERSEDED", "PENDING_REVIEW"}:
            continue
        asset = _upper(row.get("asset")).lstrip("$")
        direction = _upper(row.get("direction"))
        entry = _paper_entry(row)
        if not asset or direction not in {"LONG", "SHORT"} or entry is None:
            continue
        exit_price = _paper_exit(row)
        mark_price = exit_price
        quote_as_of = ""
        if mark_price is None:
            try:
                quote = quote_fn(asset)
            except Exception:
                quote = {"error": "quote_unavailable"}
            if quote.get("error") or quote.get("last") is None:
                continue
            mark_price = _float_or_none(quote.get("last"))
            quote_as_of = str(quote.get("as_of") or "")
        if mark_price is None:
            continue
        ret = _return_pct(direction, entry, mark_price)
        if ret is None:
            continue
        out.append(
            {
                "signal_id": str(row.get("signal_id") or ""),
                "as_of": now,
                "quote_as_of": quote_as_of,
                "asset": asset,
                "direction": direction,
                "category": _upper(row.get("category")),
                "status": status,
                "entry_price": entry,
                "mark_price": mark_price,
                "exit_price": exit_price,
                "return_pct": ret,
                "outcome": "win" if ret > 0 else "loss" if ret < 0 else "flat",
                "source": "execution_intents.jsonl",
            }
        )
    return out
