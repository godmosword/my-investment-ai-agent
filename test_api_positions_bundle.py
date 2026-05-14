"""Contract tests for Portal M4–M7 aggregate endpoints (mock BQ / intents)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import app


def test_positions_m4_defaults_to_open(monkeypatch):
    rows = [
        {
            "report_date": "2026-01-01",
            "asset": "NVDA",
            "direction": "LONG",
            "status": "OPEN",
            "entry_price": 100.0,
        }
    ]
    monkeypatch.setattr("api._fetch_trades", lambda **kwargs: rows)
    client = TestClient(app)
    r = client.get("/api/positions")
    assert r.status_code == 200
    assert r.json() == rows


def test_industries_themes_m5(monkeypatch):
    monkeypatch.setattr(
        "api_routers.industries.latest_execution_intents",
        lambda **kwargs: [{"regime": "risk_on"}, {"regime": "risk_off"}],
    )
    client = TestClient(app)
    r = client.get("/api/industries/themes")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("themes"), list)
    assert body["intent_sample_regime"] == "risk_on"
    assert body["intent_count"] == 2


def test_analysis_bundle_m6_quote_and_snapshot(monkeypatch):
    monkeypatch.setattr(
        "api.fetch_symbol_quote",
        lambda sym: {"symbol": sym, "last": 12.5, "error": None},
    )

    def fake_build(_client, sym, days=30, recommendation_limit=12):
        return {"symbol": sym, "source": "unit_test"}

    monkeypatch.setattr("api._get_bq_client", lambda: object())
    monkeypatch.setattr("api.build_symbol_snapshot", fake_build)
    client = TestClient(app)
    r = client.get("/api/analysis/NVDA")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "NVDA"
    assert body["quote"]["last"] == 12.5
    assert body["snapshot"]["source"] == "unit_test"
    assert body["snapshot_error"] is None


def test_analysis_bundle_m6_snapshot_error_surfaces(monkeypatch):
    monkeypatch.setattr(
        "api.fetch_symbol_quote",
        lambda sym: {"symbol": sym, "last": 1.0, "error": None},
    )
    monkeypatch.setattr("api._get_bq_client", lambda: object())
    monkeypatch.setattr(
        "api.build_symbol_snapshot",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("simulated bq failure")),
    )
    client = TestClient(app)
    r = client.get("/api/analysis/MSFT")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "MSFT"
    assert body["snapshot"] is None
    assert body["snapshot_error"] == "simulated bq failure"


def test_quant_signals_m7():
    client = TestClient(app)
    r = client.get("/api/quant/signals")
    assert r.status_code == 200
    body = r.json()
    assert "disclaimer" in body
    assert isinstance(body.get("signals"), list)
    assert body["signals"]
