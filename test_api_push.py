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
    monkeypatch.delenv("WEB_PUSH_STORE", raising=False)
    r = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://example.com/push/abc", "keys": {"p256dh": "x", "auth": "y"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("stored") is False


@pytest.mark.smoke
def test_push_subscribe_stores_in_memory_when_store_flag(client, monkeypatch):
    import web_push_store

    web_push_store.clear_subscriptions_for_tests()
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    monkeypatch.setenv("WEB_PUSH_STORE", "1")
    r = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://example.com/push/stored-1", "keys": {"p256dh": "x", "auth": "y"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("stored") is True
    assert body.get("count", 0) >= 1


def test_push_subscribe_dedupes_same_endpoint(client, monkeypatch):
    import web_push_store

    web_push_store.clear_subscriptions_for_tests()
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    monkeypatch.setenv("WEB_PUSH_STORE", "1")
    body_json = {"endpoint": "https://example.com/push/dedup-me", "keys": {"p256dh": "a", "auth": "b"}}
    r1 = client.post("/api/push/subscribe", json=body_json)
    r2 = client.post("/api/push/subscribe", json=body_json)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("deduped") is True
    assert r2.json().get("count") == 1


def test_push_subscribe_rate_limit_per_ip(client, monkeypatch):
    import web_push_store

    web_push_store.clear_subscriptions_for_tests()
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    monkeypatch.setenv("WEB_PUSH_STORE", "1")
    monkeypatch.setenv("WEB_PUSH_SUBSCRIBE_RATE_PER_MIN", "2")
    for i in range(2):
        r = client.post(
            "/api/push/subscribe",
            json={"endpoint": f"https://example.com/push/rate-{i}", "keys": {"p256dh": "x", "auth": "y"}},
        )
        assert r.status_code == 200
        assert r.json().get("rate_limited") is not True
    r3 = client.post(
        "/api/push/subscribe",
        json={"endpoint": "https://example.com/push/rate-blocked", "keys": {"p256dh": "x", "auth": "y"}},
    )
    assert r3.status_code == 200
    assert r3.json().get("rate_limited") is True


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
