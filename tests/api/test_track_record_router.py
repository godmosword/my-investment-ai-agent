from __future__ import annotations

import pytest

from tests.api.helpers import make_api_client, write_jsonl_rows

from track_record import build_mark_to_market_rows




@pytest.fixture()
def client(tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    write_jsonl_rows(
        store,
        [
            {
                "signal_id": "ai-nvda-long-1",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-11T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 100,
                "paper_exit_price": 110,
                "thesis_one_liner": "AI demand",
            },
            {
                "signal_id": "crypto-btc-short-1",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-12T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "SHORT",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 50,
                "paper_exit_price": 45,
            },
            {
                "signal_id": "ai-msft-long-1",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-13T00:00:00Z",
                "category": "AI",
                "asset": "MSFT",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 200,
                "paper_exit_price": 180,
            },
            {
                "signal_id": "ai-aapl-long-open",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-13T00:00:00Z",
                "category": "AI",
                "asset": "AAPL",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 100,
            },
        ],
    )
    return make_api_client(monkeypatch, EXECUTION_INTENT_STORE=str(store))

def test_track_record_summary_from_closed_intents(client):
    response = client.get("/api/track-record/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_closed"] == 3
    assert body["wins"] == 2
    assert body["losses"] == 1
    assert body["hit_rate_pct"] == pytest.approx(66.666, rel=1e-3)
    assert body["avg_return_pct"] == pytest.approx(3.333, rel=1e-3)
    assert body["max_drawdown_pct"] == pytest.approx(-10.0)
    assert body["source_row_count"] == 3
    assert len(body["equity_curve"]) == 3


def test_track_record_closed_endpoint_paginates_and_exposes_source(client):
    response = client.get("/api/track-record/closed?limit=2&offset=0")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["records"]) == 2
    assert body["records"][0]["signal_id"] == "ai-msft-long-1"
    assert body["records"][0]["source"] == "execution_intents.jsonl"
    assert body["records"][0]["source_id"] == "ai-msft-long-1"


def test_track_record_by_tag_filters_category(client):
    response = client.get("/api/track-record/by-tag?tag=AI")
    assert response.status_code == 200
    body = response.json()
    assert body["tag"] == "AI"
    assert body["summary"]["total_closed"] == 2
    assert {row["asset"] for row in body["records"]} == {"NVDA", "MSFT"}


def test_track_record_uses_bigquery_outcomes_when_available(client, monkeypatch):
    monkeypatch.setattr(
        "api_routers.track_record.load_track_record_records",
        lambda limit=500: (
            [
                {
                    "signal_id": "bq-nvda-1",
                    "asset": "NVDA",
                    "direction": "LONG",
                    "category": "AI",
                    "status": "PAPER_CLOSED",
                    "opened_at": "",
                    "closed_at": "2026-05-14T00:00:00Z",
                    "entry_price": 100,
                    "exit_price": 112,
                    "return_pct": 12,
                    "outcome": "win",
                    "source": "bigquery",
                    "source_id": "bq-nvda-1",
                    "tags": ["AI", "NVDA", "LONG", "WIN"],
                }
            ],
            "bigquery",
        ),
    )

    summary = client.get("/api/track-record/summary").json()
    assert summary["source"] == "bigquery"
    assert summary["source_row_count"] == 1

    closed = client.get("/api/track-record/closed").json()
    assert closed["source"] == "bigquery"
    assert closed["records"][0]["signal_id"] == "bq-nvda-1"


def test_mark_to_market_rows_for_active_intents():
    rows = [
        {
            "signal_id": "active-long",
            "category": "AI",
            "asset": "NVDA",
            "direction": "LONG",
            "status": "APPROVED_FOR_PAPER",
            "reference_entry_price": 100,
        }
    ]

    marked = build_mark_to_market_rows(
        rows,
        lambda symbol: {"symbol": symbol, "last": 112, "as_of": "2026-05-13T00:00:00Z", "error": None},
        as_of="2026-05-13T01:00:00Z",
    )

    assert len(marked) == 1
    assert marked[0]["signal_id"] == "active-long"
    assert marked[0]["return_pct"] == pytest.approx(12)
    assert marked[0]["outcome"] == "win"
