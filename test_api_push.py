"""FastAPI Web Push stub contract."""

import json

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("WEB_PUSH_ENABLED", raising=False)
    return TestClient(app)


def test_push_subscribe_returns_501_when_disabled(client):
    r = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://example.com/push/abc", "keys": {"p256dh": "x", "auth": "y"}},
    )
    assert r.status_code == 501


def test_push_subscribe_accepts_when_enabled(client, monkeypatch):
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    r = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://example.com/push/abc", "keys": {"p256dh": "x", "auth": "y"}},
    )
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_war_room_latest_reads_local_artifacts(client, tmp_path, monkeypatch):
    gate_dir = tmp_path / ".qsilicon" / "last_gate_failure"
    gate_dir.mkdir(parents=True)
    (gate_dir / "validation_summary.json").write_text(
        json.dumps({"valid": False, "issue_count": 2, "issues": ["foo", "bar"]}),
        encoding="utf-8",
    )
    (gate_dir / "issues.txt").write_text("1. foo\n2. bar\n", encoding="utf-8")

    scratchpad_dir = tmp_path / ".qsilicon" / "scratchpad"
    scratchpad_dir.mkdir(parents=True)
    (scratchpad_dir / "20260410_test.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"type": "init", "runId": "run-1", "meta": {"category": "CRYPTO"}}),
                json.dumps({"type": "gate_result", "runId": "run-1", "valid": False, "issues_count": 2}),
                json.dumps({"type": "run_end", "runId": "run-1", "status": "failed"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    intents_path = tmp_path / ".qsilicon" / "execution_intents.jsonl"
    intents_path.write_text(
        json.dumps(
            {
                "signal_id": "crypto-btc-long-1",
                "created_at": "2026-04-10T00:00:00Z",
                "category": "CRYPTO",
                "regime": "neutral",
                "asset": "BTC",
                "direction": "LONG",
                "star_rating": 2,
                "status": "PENDING_REVIEW",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("api._repo_root", lambda: tmp_path)
    monkeypatch.setattr("execution_intents._store_path", lambda: intents_path)

    r = client.get("/api/war-room/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["gate_failure"]["issue_count"] == 2
    assert body["scratchpad"]["run_id"] == "run-1"
    assert body["scratchpad"]["final_status"] == "failed"
    assert body["execution_intents"][0]["signal_id"] == "crypto-btc-long-1"
