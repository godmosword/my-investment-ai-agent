"""Tests for execution intent list + status PATCH (Terminal mid-tier handoff)."""

import json

from fastapi.testclient import TestClient

from api import app


def test_execution_intent_allowed_statuses():
    client = TestClient(app)
    r = client.get("/api/execution-intents/allowed-statuses")
    assert r.status_code == 200
    body = r.json()
    assert "APPROVED_FOR_PAPER" in body["statuses"]
    assert "PENDING_REVIEW" in body["statuses"]
    assert "PAPER_FILLED" in body["statuses"]
    assert "PAPER_FILLED" not in body["client_patchable"]


def test_execution_intents_list_dedupes_by_signal_id(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "signal_id": "crypto-btc-long-1",
                        "created_at": "2026-04-10T00:00:00Z",
                        "category": "CRYPTO",
                        "regime": "x",
                        "asset": "BTC",
                        "direction": "LONG",
                        "star_rating": 2,
                        "status": "PENDING_REVIEW",
                        "status_updated_at": "2026-04-10T00:00:00Z",
                    }
                ),
                json.dumps(
                    {
                        "signal_id": "crypto-btc-long-1",
                        "created_at": "2026-04-10T00:00:00Z",
                        "category": "CRYPTO",
                        "regime": "x",
                        "asset": "BTC",
                        "direction": "LONG",
                        "star_rating": 2,
                        "status": "APPROVED_FOR_PAPER",
                        "status_updated_at": "2026-04-11T12:00:00Z",
                        "status_note": "ok for paper",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)

    client = TestClient(app)
    r = client.get("/api/execution-intents?limit=10")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["status"] == "APPROVED_FOR_PAPER"
    assert rows[0]["status_note"] == "ok for paper"


def test_patch_execution_intent_status(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "crypto-eth-long-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "regime": "neutral",
                "asset": "ETH",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)

    client = TestClient(app)
    r = client.patch(
        "/api/execution-intents/crypto-eth-long-1",
        json={"status": "approved_for_paper", "note": "reviewed"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "APPROVED_FOR_PAPER"
    assert r.json()["status_note"] == "reviewed"

    lines = store.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    last = json.loads(lines[-1])
    assert last["status"] == "APPROVED_FOR_PAPER"
    assert last["status_updated_at"]


def test_patch_execution_intent_with_reference_prices(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "crypto-sol-long-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "asset": "SOL",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    client = TestClient(app)
    r = client.patch(
        "/api/execution-intents/crypto-sol-long-1",
        json={
            "status": "APPROVED_FOR_PAPER",
            "note": "with refs",
            "reference_entry_price": 150.0,
            "reference_target_price": 180.0,
            "reference_stop_price": 130.0,
        },
    )
    assert r.status_code == 200
    assert r.json()["reference_entry_price"] == 150.0
    assert r.json()["reference_target_price"] == 180.0
    assert r.json()["reference_stop_price"] == 130.0


def test_patch_execution_intent_unknown_returns_404(tmp_path, monkeypatch):
    store = tmp_path / "empty.jsonl"
    store.write_text("", encoding="utf-8")
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    client = TestClient(app)
    r = client.patch(
        "/api/execution-intents/missing-id",
        json={"status": "APPROVED_FOR_PAPER"},
    )
    assert r.status_code == 404


def test_patch_execution_intent_bad_status_returns_404(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "x",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    client = TestClient(app)
    r = client.patch("/api/execution-intents/x", json={"status": "FILLED"})
    assert r.status_code == 404


def test_execution_intents_filter_sort(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    rows = [
        {
            "signal_id": "a-btc",
            "created_at": "2026-04-09T00:00:00Z",
            "category": "CRYPTO",
            "asset": "BTC",
            "direction": "LONG",
            "star_rating": 1,
            "status": "PENDING_REVIEW",
            "status_updated_at": "2026-04-09T12:00:00Z",
        },
        {
            "signal_id": "b-spy",
            "created_at": "2026-04-10T00:00:00Z",
            "category": "AI",
            "asset": "SPY",
            "direction": "LONG",
            "star_rating": 1,
            "status": "APPROVED_FOR_PAPER",
            "status_updated_at": "2026-04-11T00:00:00Z",
        },
    ]
    store.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr("api._latest_gate_failure_summary", lambda: None)
    client = TestClient(app)
    r = client.get("/api/execution-intents?limit=10&status=PENDING")
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["asset"] == "BTC"

    r2 = client.get("/api/execution-intents?limit=10&category=AI&sort_by=asset_asc")
    assert r2.status_code == 200
    assert r2.json()[0]["asset"] == "SPY"

    r3 = client.get("/api/execution-intents?sort_by=bad")
    assert r3.status_code == 400


def test_execution_intents_gate_issue_hints(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "spy-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "AI",
                "asset": "SPY",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
                "status_updated_at": "2026-04-10T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "api._latest_gate_failure_summary",
        lambda: {"issues": ["check SPY spread", "unrelated line"]},
    )
    client = TestClient(app)
    r = client.get("/api/execution-intents?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body[0].get("gate_issue_hints") == ["check SPY spread"]


def test_gate_issue_hints_no_false_positive_substring(tmp_path, monkeypatch):
    """``ASSET`` must not match inside unrelated tokens like ``PASSSETS``."""
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "x-asset-long-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "asset": "ASSET",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
                "status_updated_at": "2026-04-10T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "api._latest_gate_failure_summary",
        lambda: {"issues": ["PASSSETS validation ok"]},
    )
    client = TestClient(app)
    r = client.get("/api/execution-intents?limit=10")
    assert r.status_code == 200
    row = r.json()[0]
    assert "gate_issue_hints" not in row


def test_war_room_enriches_intents_with_gate_hints(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "spy-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "AI",
                "asset": "SPY",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
                "status_updated_at": "2026-04-10T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    monkeypatch.setattr(
        "api._latest_gate_failure_summary",
        lambda: {"issues": ["SPY gate block"]},
    )
    client = TestClient(app)
    r = client.get("/api/war-room/latest")
    assert r.status_code == 200
    intents = r.json().get("execution_intents") or []
    assert intents[0].get("gate_issue_hints") == ["SPY gate block"]


def test_patch_execution_intent_paper_status_not_allowed(tmp_path, monkeypatch):
    store = tmp_path / "intents.jsonl"
    store.write_text(
        json.dumps(
            {
                "signal_id": "p1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 1,
                "status": "PENDING_REVIEW",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("execution_intents._store_path", lambda: store)
    client = TestClient(app)
    r = client.patch("/api/execution-intents/p1", json={"status": "PAPER_FILLED"})
    assert r.status_code == 404
