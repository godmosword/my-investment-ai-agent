from __future__ import annotations

from fastapi.testclient import TestClient

from api import app
from api_routers import price_alerts as router


def test_price_alert_create_list_delete(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    client = TestClient(app)

    created = client.post(
        "/api/push/price-alerts",
        json={"symbol": "nvda", "direction": "above", "target_price": 900, "note": "breakout"},
    )
    assert created.status_code == 200
    alert = created.json()["alert"]
    assert alert["symbol"] == "NVDA"
    assert alert["direction"] == "above"
    assert alert["id"]

    listed = client.get("/api/push/price-alerts")
    assert listed.status_code == 200
    assert listed.json()["alerts"][0]["symbol"] == "NVDA"

    deleted = client.delete(f"/api/push/price-alerts/{alert['id']}")
    assert deleted.status_code == 200
    assert deleted.json() == {"ok": True}
    assert client.get("/api/push/price-alerts").json()["alerts"] == []


def test_price_alert_digest_empty_store(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    client = TestClient(app)
    r = client.get("/api/push/price-alerts/digest")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == "qsi_price_alert_digest_v1"
    assert body["total"] == 0
    assert body["symbols"] == []


def test_price_alert_check_triggers_with_mocked_quote(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setattr(
        router,
        "fetch_symbol_quote",
        lambda symbol: {"symbol": symbol, "last": 950.0, "error": None},
    )
    client = TestClient(app)

    alert = client.post(
        "/api/push/price-alerts",
        json={"symbol": "NVDA", "direction": "above", "target_price": 900},
    ).json()["alert"]

    checked = client.post("/api/push/price-alerts/check?send_push=false")
    assert checked.status_code == 200
    body = checked.json()
    assert body["triggered"] == 1
    updated = body["alerts"][0]
    assert updated["id"] == alert["id"]
    assert updated["last_price"] == 950.0
    assert updated["triggered_at"]


def test_price_alert_check_telegram_send(tmp_path, monkeypatch):
    """Triggered alert with PRICE_ALERTS_TELEGRAM_ENABLED=1 sends Telegram once."""
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.setenv("PRICE_ALERTS_TELEGRAM_ENABLED", "1")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "fake-chat")
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setattr(
        router,
        "fetch_symbol_quote",
        lambda symbol: {"symbol": symbol, "last": 950.0, "error": None},
    )
    sent: list[dict] = []

    def fake_send(alert, last_price):
        sent.append({"alert_id": alert["id"], "last_price": last_price})
        return {"ok": True}

    monkeypatch.setattr(router, "_send_telegram", fake_send)
    client = TestClient(app)

    alert = client.post(
        "/api/push/price-alerts",
        json={"symbol": "NVDA", "direction": "above", "target_price": 900},
    ).json()["alert"]

    body = client.post("/api/push/price-alerts/check?send_push=false").json()
    assert body["triggered"] == 1
    assert len(sent) == 1
    assert sent[0]["alert_id"] == alert["id"]
    assert body["telegram_results"][0]["ok"] is True

    # Second tick: alert already triggered, no Telegram resend (natural dedupe).
    # ``triggered`` is cumulative (includes prior-tick hits), but telegram is not re-sent.
    body2 = client.post("/api/push/price-alerts/check?send_push=false").json()
    assert body2["telegram_results"] == []
    assert len(sent) == 1


def test_price_alert_telegram_disabled_skips_send(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.delenv("PRICE_ALERTS_TELEGRAM_ENABLED", raising=False)
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setattr(
        router,
        "fetch_symbol_quote",
        lambda symbol: {"symbol": symbol, "last": 950.0, "error": None},
    )
    sent: list[dict] = []
    monkeypatch.setattr(
        router,
        "_send_telegram",
        lambda alert, last_price: sent.append(alert) or {"ok": True},
    )
    client = TestClient(app)
    client.post(
        "/api/push/price-alerts",
        json={"symbol": "NVDA", "direction": "above", "target_price": 900},
    )
    body = client.post("/api/push/price-alerts/check?send_push=false").json()
    assert body["triggered"] == 1
    assert body["telegram_results"] == []
    assert sent == []


def test_price_alert_check_quote_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("PRICE_ALERTS_FILE", str(tmp_path / "alerts.jsonl"))
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setattr(
        router,
        "fetch_symbol_quote",
        lambda symbol: {"symbol": symbol, "last": None, "error": "boom"},
    )
    client = TestClient(app)

    client.post(
        "/api/push/price-alerts",
        json={"symbol": "NVDA", "direction": "below", "target_price": 800},
    )
    checked = client.post("/api/push/price-alerts/check?send_push=false")
    assert checked.status_code == 200
    body = checked.json()
    assert body["triggered"] == 0
    assert body["alerts"][0]["error"] == "quote_unavailable"
