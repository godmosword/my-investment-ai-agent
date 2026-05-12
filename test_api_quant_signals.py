"""Tests for GET /api/quant/signals and GET /api/quant/backtest (Q33)."""

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
