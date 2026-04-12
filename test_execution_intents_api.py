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
