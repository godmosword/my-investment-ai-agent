from __future__ import annotations

import json

import pytest

from tests.api.helpers import write_jsonl_rows


@pytest.fixture()
def client(client_intents_portfolio):
    return client_intents_portfolio



def test_scenario_optimizer_disabled_by_default(client, monkeypatch):
    monkeypatch.delenv("SCENARIO_OPTIMIZER_ENABLED", raising=False)
    response = client.get("/api/scenario/suggestions")
    assert response.status_code == 404


def test_scenario_optimizer_returns_payload(client, tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(store))
    monkeypatch.setenv("SCENARIO_OPTIMIZER_ENABLED", "1")
    ph = tmp_path / "portfolio_holdings.jsonl"
    ph.write_text(
        json.dumps(
            {
                "symbol": "NVDA",
                "shares": 10,
                "cost_basis": 100,
                "opened_at": "2026-01-01",
                "notes": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("PORTFOLIO_HOLDINGS_FILE", str(ph))
    write_jsonl_rows(
        store,
        [
            {
                "signal_id": "nvda-1",
                "created_at": "2026-05-01T00:00:00Z",
                "status_updated_at": "2026-05-02T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "status": "PAPER_FILLED",
                "reference_entry_price": 100,
                "reference_target_price": 110,
                "reference_stop_price": 95,
                "paper_fill_price": 100,
            },
        ],
    )

    response = client.get("/api/scenario/suggestions")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert "disclaimer" in body
    assert body["portfolio"]["positions"] == 1
    assert any(s["id"] == "defensive" for s in body["scenarios"])
    hints = body["target_hints"]
    assert len(hints) == 1
    assert hints[0]["asset"] == "NVDA"
    assert hints[0]["in_portfolio"] is True
    kinds = {s["kind"] for s in hints[0]["suggestions"]}
    assert "target_distance" in kinds
    assert "stop_distance" in kinds
