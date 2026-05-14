"""Contract tests for /api/run-crew trigger + status router."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api import app


def test_run_crew_status_always_available(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.delenv("CREW_HTTP_ENABLED", raising=False)
    client = TestClient(app)

    response = client.get("/api/run-crew/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"idle", "running", "done", "error"}
    assert isinstance(body["age_seconds"], int)
    assert body["stale_after_seconds"] == 1800
    assert body["is_stale"] is False


def test_run_crew_trigger_disabled_by_default(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    monkeypatch.delenv("CREW_HTTP_ENABLED", raising=False)
    client = TestClient(app)

    response = client.post("/api/run-crew")

    assert response.status_code == 404
    assert "CREW_HTTP_ENABLED=1" in response.text
