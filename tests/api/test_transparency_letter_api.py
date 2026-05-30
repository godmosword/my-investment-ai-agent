from __future__ import annotations

import pytest

from tests.api.helpers import write_jsonl_rows


@pytest.fixture()
def client(client_intents_portfolio):
    return client_intents_portfolio

def test_transparency_letter_summarizes_closed_month_and_alignment(client, tmp_path):
    write_jsonl_rows(
        tmp_path / "execution_intents.jsonl",
        [
            {
                "signal_id": "nvda-win",
                "created_at": "2026-05-01T00:00:00Z",
                "status_updated_at": "2026-05-12T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "thesis_one_liner": "AI capex remains strong enough to support estimates.",
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "reference_target_price": 130,
                "reference_stop_price": 90,
                "paper_exit_price": 120,
            },
            {
                "signal_id": "btc-loss",
                "created_at": "2026-05-02T00:00:00Z",
                "status_updated_at": "2026-05-13T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "SHORT",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 50,
                "paper_exit_price": 55,
            },
            {
                "signal_id": "old-msft",
                "created_at": "2026-04-01T00:00:00Z",
                "status_updated_at": "2026-04-12T00:00:00Z",
                "category": "AI",
                "asset": "MSFT",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "paper_exit_price": 110,
            },
        ],
    )
    write_jsonl_rows(
        tmp_path / "portfolio_holdings.jsonl",
        [
            {"id": "1", "symbol": "NVDA", "shares": 1, "cost_basis": 100, "opened_at": "2026-01-01"},
            {"id": "2", "symbol": "AAPL", "shares": 1, "cost_basis": 100, "opened_at": "2026-01-01"},
        ],
    )

    response = client.get("/api/paper/transparency-letter?month=2026-05")
    assert response.status_code == 200
    body = response.json()
    assert body["month"] == "2026-05"
    assert body["summary"]["closed_count"] == 2
    assert body["summary"]["wins"] == 1
    assert body["summary"]["losses"] == 1
    assert body["summary"]["avg_return_pct"] == pytest.approx(5)
    assert body["summary"]["publishable"] is False
    assert body["alignment"]["matched_symbols"] == ["NVDA"]
    assert body["alignment"]["paper_only_symbols"] == ["BTC"]
    assert body["alignment"]["portfolio_only_symbols"] == ["AAPL"]
    assert "Paper Transparency Letter" in body["letter_markdown"]


def test_transparency_letter_rejects_invalid_month(client):
    response = client.get("/api/paper/transparency-letter?month=202605")
    assert response.status_code == 400
