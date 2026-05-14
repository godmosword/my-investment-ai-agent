"""Price alert endpoints for Web Push trigger checks."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

import price_alerts
from symbol_snapshot_service import fetch_symbol_quote, validate_symbol_for_snapshot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/push/price-alerts", tags=["push"])


class PriceAlertBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=24)
    direction: str = Field(pattern="^(above|below)$")
    target_price: float = Field(gt=0)
    note: str = ""

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        try:
            return validate_symbol_for_snapshot(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("direction")
    @classmethod
    def normalize_direction(cls, value: str) -> str:
        return value.lower()


def _triggered(alert: dict[str, Any], last_price: float) -> bool:
    direction = str(alert.get("direction") or "").lower()
    target = float(alert.get("target_price") or 0)
    if direction == "above":
        return last_price >= target
    if direction == "below":
        return last_price <= target
    return False


def _send_push(alert: dict[str, Any], last_price: float) -> dict[str, Any]:
    try:
        import web_push_store

        if not web_push_store.web_push_enabled():
            return {"ok": False, "skipped": "web_push_disabled"}
        title = f"{alert['symbol']} price alert"
        body = f"{alert['symbol']} crossed {alert['direction']} ${alert['target_price']:.2f}; last ${last_price:.2f}"
        return web_push_store.send_test_push(title, body)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _telegram_enabled() -> bool:
    return os.getenv("PRICE_ALERTS_TELEGRAM_ENABLED", "").strip() in {"1", "true", "TRUE"}


def _sse_alert_enabled() -> bool:
    return os.getenv("SSE_PRICE_ALERT_ENABLED", "").strip() in {"1", "true", "TRUE"}


def _publish_sse_alert(alert: dict[str, Any], last_price: float) -> None:
    """Enqueue triggered alert to in-process SSE queue (best-effort, never raises)."""
    if not _sse_alert_enabled():
        return
    try:
        from war_room_stream import emit_price_alert_event

        emit_price_alert_event(
            alert_id=str(alert.get("id") or ""),
            symbol=str(alert.get("symbol") or "").upper(),
            direction=str(alert.get("direction") or "").lower(),
            target_price=float(alert.get("target_price") or 0),
            last_price=last_price,
            note=str(alert.get("note") or ""),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_alert SSE publish failed: %s", exc)


def _send_telegram(alert: dict[str, Any], last_price: float) -> dict[str, Any]:
    """Send single triggered alert as plain-text Telegram message.

    Natural 24h dedupe: ``check_price_alerts`` skips rows where ``triggered_at`` is set,
    so each alert sends to Telegram at most once over its lifetime.
    """
    if not _telegram_enabled():
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
        note_suffix = f"\n📝 {note_raw}" if note_raw else ""
        text = (
            f"🔔 Price Alert: {symbol}\n"
            f"{direction.upper()} {target:.2f} — last {last_price:.2f}"
            f"{note_suffix}"
        )
        bot.send_message(chat_id, text, timeout=30)
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        logger.warning("price_alert telegram send failed: %s", exc)
        return {"ok": False, "error": str(exc)}


@router.get("")
def list_price_alerts() -> dict[str, Any]:
    return {"alerts": price_alerts.load_alerts()}


@router.get("/digest")
def get_price_alerts_digest() -> dict[str, Any]:
    """Read-only summary for Terminal workspace digest (no quote fetches)."""
    return price_alerts.build_alert_digest()


@router.post("")
def create_price_alert(body: PriceAlertBody) -> dict[str, Any]:
    alert = price_alerts.add_alert(body.model_dump())
    return {"alert": alert}


@router.delete("/{alert_id}")
def delete_price_alert(alert_id: str) -> dict[str, Any]:
    if not price_alerts.delete_alert(alert_id):
        raise HTTPException(status_code=404, detail="price alert not found")
    return {"ok": True}


@router.post("/check")
def check_price_alerts(
    send_push: bool = Query(default=True),
    send_telegram: bool = Query(default=True),
) -> dict[str, Any]:
    alerts = price_alerts.load_alerts()
    checked: list[dict[str, Any]] = []
    push_results: list[dict[str, Any]] = []
    telegram_results: list[dict[str, Any]] = []
    for alert in alerts:
        if alert.get("triggered_at"):
            checked.append(alert)
            continue
        symbol = str(alert.get("symbol") or "").upper()
        quote = fetch_symbol_quote(symbol)
        if quote.get("error") or quote.get("last") is None:
            updated = price_alerts.mark_checked(
                str(alert.get("id")),
                last_price=None,
                triggered=False,
                error="quote_unavailable",
            )
            if updated:
                checked.append(updated)
            continue
        last_price = float(quote["last"])
        hit = _triggered(alert, last_price)
        updated = price_alerts.mark_checked(
            str(alert.get("id")),
            last_price=last_price,
            triggered=hit,
            error="",
        )
        if updated:
            checked.append(updated)
            if hit and send_push:
                push_results.append({"alert_id": updated["id"], **_send_push(updated, last_price)})
            if hit and send_telegram and _telegram_enabled():
                telegram_results.append(
                    {"alert_id": updated["id"], **_send_telegram(updated, last_price)}
                )
            if hit:
                _publish_sse_alert(updated, last_price)
    return {
        "checked": len(checked),
        "triggered": sum(1 for row in checked if row.get("triggered_at")),
        "alerts": checked,
        "push_results": push_results,
        "telegram_results": telegram_results,
    }
