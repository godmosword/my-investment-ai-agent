"""Local JSONL-backed price alert storage for Web Push trigger checks."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


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


def build_alert_digest() -> dict[str, Any]:
    """Read-only aggregate for workspace / digest UIs (queue 34)."""
    rows = load_alerts()
    triggered = [r for r in rows if str(r.get("triggered_at") or "").strip()]
    pending = [r for r in rows if not str(r.get("triggered_at") or "").strip()]
    symbols = sorted({str(r.get("symbol") or "").upper() for r in rows if str(r.get("symbol") or "").strip()})
    last_triggered: str | None = None
    if triggered:
        last_triggered = max(
            (str(r.get("triggered_at") or "") for r in triggered),
            default="",
        ) or None
    return {
        "schema_version": "qsi_price_alert_digest_v1",
        "as_of": _now_iso(),
        "total": len(rows),
        "pending": len(pending),
        "triggered": len(triggered),
        "symbols": symbols,
        "last_triggered_at": last_triggered,
    }


def triggered(alert: dict[str, Any], last_price: float) -> bool:
    direction = str(alert.get("direction") or "").lower()
    target = float(alert.get("target_price") or 0)
    if direction == "above":
        return last_price >= target
    if direction == "below":
        return last_price <= target
    return False


def telegram_enabled() -> bool:
    return os.getenv("PRICE_ALERTS_TELEGRAM_ENABLED", "").strip() in {"1", "true", "TRUE"}


def send_telegram(alert: dict[str, Any], last_price: float) -> dict[str, Any]:
    """Send single triggered alert as plain-text Telegram message.

    Natural 24h dedupe: callers skip rows where ``triggered_at`` is set,
    so each alert sends to Telegram at most once over its lifetime.
    """
    if not telegram_enabled():
        return {"ok": False, "skipped": "telegram_disabled"}
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        return {"ok": False, "skipped": "telegram_credentials_missing"}
    try:
        import telebot

        bot = telebot.TeleBot(token)
        symbol = str(alert.get("symbol") or "").upper()
        direction = str(alert.get("direction") or "").lower()
        target = float(alert.get("target_price") or 0)
        note_raw = str(alert.get("note") or "").strip()
        note_suffix = f"\n\U0001f4dd {note_raw}" if note_raw else ""
        text = (
            f"\U0001f514 Price Alert: {symbol}\n"
            f"{direction.upper()} {target:.2f} \u2014 last {last_price:.2f}"
            f"{note_suffix}"
        )
        bot.send_message(chat_id, text, timeout=30)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_alert telegram send failed: %s", exc)
        return {"ok": False, "error": str(exc)}


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
