"""Tests for GET /api/quant/signals and GET /api/quant/backtest (Q33)."""

import json

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture()
def client():
    return TestClient(app)


# ── /api/quant/signals ──────────────────────────────────────────────────────

def test_quant_signals_structure(client):
    r = client.get("/api/quant/signals")
    assert r.status_code == 200
    body = r.json()
    assert "signals" in body
    assert "disclaimer" in body


def test_quant_signals_list_not_empty(client):
    r = client.get("/api/quant/signals")
    assert r.status_code == 200
    signals = r.json()["signals"]
    assert isinstance(signals, list)
    assert len(signals) >= 1


def test_quant_signals_schema(client):
    r = client.get("/api/quant/signals")
    for sig in r.json()["signals"]:
        assert "id" in sig
        assert "direction" in sig
        assert "confidence" in sig


def test_quant_signals_derive_active_rows_from_execution_intents(client, tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    rows = [
        {
            "signal_id": "ai-nvda-long-1",
            "created_at": "2026-05-20T01:00:00Z",
            "category": "AI",
            "asset": "NVDA",
            "direction": "LONG",
            "star_rating": 2,
            "thesis_one_liner": "AI capex momentum",
            "status": "PAPER_FILLED",
            "status_updated_at": "2026-05-20T02:00:00Z",
            "reference_entry_price": 900,
            "reference_target_price": 960,
            "reference_stop_price": 870,
        },
        {
            "signal_id": "crypto-btc-long-1",
            "created_at": "2026-05-19T01:00:00Z",
            "category": "CRYPTO",
            "asset": "BTC",
            "direction": "LONG",
            "star_rating": 1,
            "thesis_one_liner": "closed row should not show",
            "status": "PAPER_CLOSED",
            "status_updated_at": "2026-05-19T02:00:00Z",
        },
    ]
    store.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(store))

    r = client.get("/api/quant/signals")

    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "execution_intents.jsonl"
    assert body["count"] == 1
    signal = body["signals"][0]
    assert signal["id"] == "ai-nvda-long-1"
    assert signal["symbol"] == "NVDA"
    assert signal["status"] == "PAPER_FILLED"
    assert signal["confidence"] == 1.0
    assert signal["reference_entry_price"] == 900


# ── /api/quant/backtest ─────────────────────────────────────────────────────

def test_quant_backtest_disabled_by_default(client):
    r = client.get("/api/quant/backtest?symbol=BTC")
    assert r.status_code == 404
    assert "QUANT_BACKTEST_ENABLED" in r.json()["detail"]


def test_quant_backtest_structure_when_enabled(client, monkeypatch):
    monkeypatch.setenv("QUANT_BACKTEST_ENABLED", "1")
    r = client.get("/api/quant/backtest?symbol=BTC")
    assert r.status_code == 200
    body = r.json()
    assert "symbol" in body
    assert "equity_curve" in body
    assert "sharpe" in body
    assert "max_drawdown" in body
    assert "total_return" in body


def test_quant_backtest_invalid_symbol(client, monkeypatch):
    monkeypatch.setenv("QUANT_BACKTEST_ENABLED", "1")
    r = client.get("/api/quant/backtest?symbol=!!!BAD!!!")
    assert r.status_code == 400


def test_quant_backtest_equity_curve_is_list(client, monkeypatch):
    monkeypatch.setenv("QUANT_BACKTEST_ENABLED", "1")
    r = client.get("/api/quant/backtest?symbol=SPY")
    assert r.status_code == 200
    assert isinstance(r.json()["equity_curve"], list)
