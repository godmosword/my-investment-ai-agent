"""Tests for POST /api/run-crew and GET /api/run-crew/status (Q29)."""

import pytest
from fastapi.testclient import TestClient

from api import app
from api_routers.run_crew import _crew_run_state, _crew_run_lock


@pytest.fixture(autouse=True)
def reset_crew_state():
    """Reset shared crew state and lock between tests."""
    _crew_run_state.update({"status": "idle", "job_id": None, "started_at": None, "finished_at": None, "error": None})
    if _crew_run_lock.locked():
        _crew_run_lock.release()
    yield
    _crew_run_state.update({"status": "idle", "job_id": None, "started_at": None, "finished_at": None, "error": None})
    if _crew_run_lock.locked():
        _crew_run_lock.release()


def test_run_crew_disabled_by_default():
    client = TestClient(app)
    r = client.post("/api/run-crew")
    assert r.status_code == 404
    assert "CREW_HTTP_ENABLED" in r.json()["detail"]


def test_run_crew_forbidden_with_wrong_key(monkeypatch):
    monkeypatch.setenv("CREW_HTTP_ENABLED", "1")
    monkeypatch.setenv("CREW_HTTP_API_KEY", "secret")
    client = TestClient(app)
    r = client.post("/api/run-crew", headers={"X-Crew-Api-Key": "wrong"})
    assert r.status_code == 403


def test_run_crew_no_auth_when_key_unset(monkeypatch):
    """When CREW_HTTP_API_KEY is not set, any request is allowed."""
    monkeypatch.setenv("CREW_HTTP_ENABLED", "1")
    monkeypatch.delenv("CREW_HTTP_API_KEY", raising=False)
    client = TestClient(app)
    # We don't want a real subprocess; patch asyncio.create_task to be a no-op.
    import api as _api
    import asyncio

    created = []

    def fake_create_task(coro):
        # Prevent real subprocess from spawning; store coro for cleanup.
        coro.close()
        created.append(True)
        fut = asyncio.get_event_loop().create_future()
        fut.set_result(None)
        return fut

    monkeypatch.setattr(_api.asyncio, "create_task", fake_create_task)
    r = client.post("/api/run-crew")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "started"
    assert body["job_id"]


def test_run_crew_409_when_already_running(monkeypatch):
    monkeypatch.setenv("CREW_HTTP_ENABLED", "1")
    monkeypatch.delenv("CREW_HTTP_API_KEY", raising=False)
    # Simulate a running job by acquiring the lock and setting state.
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(_crew_run_lock.acquire())
    _crew_run_state.update({"status": "running", "job_id": "abc123"})
    try:
        client = TestClient(app)
        r = client.post("/api/run-crew")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        assert body["status"] == "running"
        assert body["job_id"] == "abc123"
    finally:
        if _crew_run_lock.locked():
            _crew_run_lock.release()
        loop.close()


def test_get_run_crew_status_always_available():
    """Status endpoint works regardless of CREW_HTTP_ENABLED."""
    client = TestClient(app)
    r = client.get("/api/run-crew/status")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert body["status"] == "idle"
