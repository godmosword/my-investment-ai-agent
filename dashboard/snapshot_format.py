"""Shared text formatting for Streamlit/API snapshot parity."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def format_price_alignment_status(alignment: dict[str, Any] | None) -> str:
    if not alignment:
        return "對齊狀態：N/A。請以資料溯源與後端欄位為準。"
    if alignment.get("aligned") is True:
        return "對齊狀態：一致。請以資料溯源與後端欄位為準。"
    if alignment.get("aligned") is False:
        rel = alignment.get("rel_diff")
        suffix = ""
        if rel is not None:
            try:
                suffix = f"（相對差 {float(rel) * 100:.3f}%）"
            except (TypeError, ValueError):
                suffix = ""
        return f"對齊警告：OHLC 與 quote 不一致{suffix}。請以資料溯源與後端欄位為準。"
    if alignment.get("quote_error"):
        return f"對齊狀態：N/A（{alignment.get('quote_error')}）。請以資料溯源與後端欄位為準。"
    return "對齊狀態：N/A（後端未確認）。請以資料溯源與後端欄位為準。"


def _format_as_of(value: Any) -> str:
    if not value:
        return "—"
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


def format_provenance_summary(provenance: dict[str, Any] | None) -> str:
    if not isinstance(provenance, dict) or not provenance:
        return "資料溯源：N/A"
    labels = (
        ("ohlc", "OHLC"),
        ("daily_metrics", "daily_metrics"),
        ("recommendations", "recommendations"),
    )
    parts: list[str] = []
    for key, label in labels:
        row = provenance.get(key)
        if not isinstance(row, dict):
            continue
        source = row.get("source") or "—"
        as_of = _format_as_of(row.get("as_of"))
        table_id = row.get("table_id")
        tail = f" · {table_id}" if table_id else ""
        parts.append(f"{label}: {source} · {as_of}{tail}")
    return "資料溯源：" + " | ".join(parts) if parts else "資料溯源：N/A"
