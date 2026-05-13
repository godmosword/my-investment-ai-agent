"""Local JSONL-backed price alert storage for Web Push trigger checks."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _store_path() -> Path:
    return Path(os.getenv("PRICE_ALERTS_FILE") or "price_alerts.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_alerts() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            rows.append(data)
    return rows


def save_alerts(alerts: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in alerts)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def add_alert(data: dict[str, Any]) -> dict[str, Any]:
    alert = {
        "id": str(uuid.uuid4()),
        "symbol": str(data["symbol"]).upper(),
        "direction": str(data["direction"]).lower(),
        "target_price": float(data["target_price"]),
        "note": str(data.get("note") or ""),
        "created_at": _now_iso(),
        "last_checked_at": "",
        "last_price": None,
        "triggered_at": "",
    }
    rows = load_alerts()
    rows.append(alert)
    save_alerts(rows)
    return alert


def delete_alert(alert_id: str) -> bool:
    rows = load_alerts()
    next_rows = [row for row in rows if str(row.get("id")) != alert_id]
    if len(next_rows) == len(rows):
        return False
    save_alerts(next_rows)
    return True


def mark_checked(
    alert_id: str,
    *,
    last_price: float | None,
    triggered: bool,
    error: str = "",
) -> dict[str, Any] | None:
    rows = load_alerts()
    updated: dict[str, Any] | None = None
    now = _now_iso()
    for idx, row in enumerate(rows):
        if str(row.get("id")) != alert_id:
            continue
        next_row = {**row, "last_checked_at": now, "last_price": last_price, "error": error}
        if triggered and not next_row.get("triggered_at"):
            next_row["triggered_at"] = now
        rows[idx] = next_row
        updated = next_row
        break
    if updated is not None:
        save_alerts(rows)
    return updated
