from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api import app


def _write_rows(path, rows):
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(tmp_path / "execution_intents.jsonl"))
    return TestClient(app)


def test_quant_backtest_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("QUANT_BACKTEST_ENABLED", raising=False)
    response = client.get("/api/quant/backtest?symbol=NVDA")
    assert response.status_code == 404


def test_quant_backtest_uses_closed_execution_intents(client, tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(store))
    monkeypatch.setenv("QUANT_BACKTEST_ENABLED", "1")
    _write_rows(
        store,
        [
            {
                "signal_id": "nvda-win",
                "created_at": "2026-05-01T00:00:00Z",
                "status_updated_at": "2026-05-02T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "paper_exit_price": 110,
            },
            {
                "signal_id": "nvda-loss",
                "created_at": "2026-05-03T00:00:00Z",
                "status_updated_at": "2026-05-04T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "paper_exit_price": 95,
            },
            {
                "signal_id": "msft-win",
                "created_at": "2026-05-03T00:00:00Z",
                "status_updated_at": "2026-05-04T00:00:00Z",
                "category": "AI",
                "asset": "MSFT",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "paper_exit_price": 150,
            },
        ],
    )

    response = client.get("/api/quant/backtest?symbol=NVDA")
    assert response.status_code == 200
    body = response.json()
    assert body["symbol"] == "NVDA"
    assert body["trade_count"] == 2
    assert body["source"] == "execution_intents.jsonl"
    assert body["equity_curve"][-1]["value"] == pytest.approx(10450)
    assert body["total_return"] == pytest.approx(0.045)


def test_quant_backtest_rejects_invalid_symbol(client, monkeypatch):
    monkeypatch.setenv("QUANT_BACKTEST_ENABLED", "1")
    response = client.get("/api/quant/backtest?symbol=***")
    assert response.status_code == 400
