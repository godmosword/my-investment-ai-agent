from __future__ import annotations

import pytest

from tests.api.helpers import write_jsonl_rows


@pytest.fixture()
def client(client_intents):
    return client_intents

def test_manual_execution_intent_create_list_patch(client):
    created = client.post(
        "/api/execution-intents",
        json={
            "category": "ai",
            "asset": "nvda",
            "direction": "long",
            "star_rating": 2,
            "thesis_one_liner": "AI capex impulse",
            "reference_entry_price": 100,
            "reference_target_price": 120,
            "reference_stop_price": 90,
        },
    )
    assert created.status_code == 200
    row = created.json()
    assert row["signal_id"].startswith("manual-nvda-long-")
    assert row["asset"] == "NVDA"
    assert row["direction"] == "LONG"
    assert row["status"] == "PENDING_REVIEW"

    listed = client.get("/api/execution-intents").json()
    assert [r["signal_id"] for r in listed] == [row["signal_id"]]
    assert listed[0]["quality_grade"] == "A"
    assert listed[0]["quality_score"] >= 80

    patched = client.patch(
        f"/api/execution-intents/{row['signal_id']}",
        json={"status": "APPROVED_FOR_PAPER", "note": "paper run"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "APPROVED_FOR_PAPER"


def test_paper_lifecycle_summary_and_risk_metrics(client, tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(store))
    write_jsonl_rows(
        store,
        [
            {
                "signal_id": "nvda-long-open",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-10T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 100,
                "reference_target_price": 130,
                "reference_stop_price": 90,
            },
            {
                "signal_id": "btc-short-closed",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-11T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "SHORT",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 50,
                "paper_exit_price": 45,
            },
        ],
    )

    response = client.get("/api/paper/lifecycle")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["active_count"] == 1
    assert body["summary"]["closed_count"] == 1
    assert body["summary"]["avg_realized_return_pct"] == pytest.approx(10)
    open_row = next(r for r in body["rows"] if r["signal_id"] == "nvda-long-open")
    assert open_row["target_distance_pct"] == pytest.approx(30)
    assert open_row["stop_distance_pct"] == pytest.approx(10)
    assert open_row["r_multiple"] == pytest.approx(3)
    assert open_row["quality_grade"] == "A"
    assert body["summary"]["avg_quality_score"] > 0
    assert body["summary"]["quality_counts"]["A"] == 1


def test_paper_pnl_marks_active_rows_and_keeps_quote_errors(client, tmp_path, monkeypatch):
    store = tmp_path / "execution_intents.jsonl"
    monkeypatch.setenv("EXECUTION_INTENT_STORE", str(store))
    write_jsonl_rows(
        store,
        [
            {
                "signal_id": "nvda-long-open",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-10T00:00:00Z",
                "category": "AI",
                "asset": "NVDA",
                "direction": "LONG",
                "star_rating": 2,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 100,
            },
            {
                "signal_id": "bad-long-open",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-10T00:00:00Z",
                "category": "AI",
                "asset": "BAD",
                "direction": "LONG",
                "star_rating": 1,
                "status": "APPROVED_FOR_PAPER",
                "reference_entry_price": 20,
            },
            {
                "signal_id": "msft-long-closed",
                "created_at": "2026-05-10T00:00:00Z",
                "status_updated_at": "2026-05-11T00:00:00Z",
                "category": "AI",
                "asset": "MSFT",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PAPER_CLOSED",
                "reference_entry_price": 200,
                "paper_exit_price": 180,
            },
        ],
    )

    def fake_quote(symbol):
        if symbol == "BAD":
            raise RuntimeError("offline")
        return {"symbol": symbol, "last": 112, "as_of": "2026-05-13T00:00:00Z", "change_pct_1d": 1.5}

    monkeypatch.setattr("api.fetch_symbol_quote", fake_quote)
    response = client.get("/api/paper/pnl")
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["active_count"] == 2
    assert body["summary"]["quote_error_count"] == 1
    assert body["summary"]["avg_unrealized_return_pct"] == pytest.approx(12)
    assert body["summary"]["avg_realized_return_pct"] == pytest.approx(-10)
    nvda = next(r for r in body["rows"] if r["signal_id"] == "nvda-long-open")
    bad = next(r for r in body["rows"] if r["signal_id"] == "bad-long-open")
    assert nvda["mark_price"] == 112
    assert nvda["return_pct"] == pytest.approx(12)
    assert bad["quote_error"] == "quote_unavailable"
