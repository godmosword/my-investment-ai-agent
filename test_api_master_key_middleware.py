"""Optional ``QSILICON_MASTER_KEY`` guard on ``/api/*`` (SSE path exempt)."""

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.mark.smoke
class TestQsSiliconMasterKeyMiddleware:
    def test_healthz_unaffected_when_master_set(self, monkeypatch):
        monkeypatch.setenv("QSILICON_MASTER_KEY", "only-for-api")
        client = TestClient(app)
        r = client.get("/healthz")
        assert r.status_code == 200

    def test_api_protected_401_without_header_when_master_set(self, monkeypatch):
        monkeypatch.setenv("QSILICON_MASTER_KEY", "secret-k")
        client = TestClient(app)
        r = client.get("/api/execution-intents/allowed-statuses")
        assert r.status_code == 401
        assert "Unauthorized" in (r.text or "")

    def test_api_with_valid_header_reaches_route(self, monkeypatch):
        monkeypatch.setenv("QSILICON_MASTER_KEY", "ok-key")
        client = TestClient(app)
        r = client.get(
            "/api/execution-intents/allowed-statuses",
            headers={"X-Q-Silicon-Key": "ok-key"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "statuses" in body

    def test_sse_path_not_blocked_by_master_key(self, monkeypatch):
        """SSE 專線豁免 master middleware；SSE disabled 時應為 404 而非 401。"""
        monkeypatch.setenv("QSILICON_MASTER_KEY", "block-others")
        monkeypatch.setenv("TERMINAL_SSE_ENABLED", "0")
        client = TestClient(app)
        r = client.get("/api/stream/war-room")
        assert r.status_code == 404
