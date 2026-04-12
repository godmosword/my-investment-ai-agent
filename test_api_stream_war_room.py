"""Tests for GET /api/stream/war-room (M4 SSE)."""

from fastapi.testclient import TestClient

from api import app


def test_sse_disabled_by_default():
    client = TestClient(app)
    r = client.get("/api/stream/war-room")
    assert r.status_code == 404


def test_sse_forbidden_when_auth_required(monkeypatch):
    monkeypatch.setenv("TERMINAL_SSE_ENABLED", "1")
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "secret")
    client = TestClient(app)
    r = client.get("/api/stream/war-room")
    assert r.status_code == 403
    # 成功訂閱為長連線；Starlette TestClient 對 ``StreamingResponse`` 易阻塞，改以手動驗證（見 roadmap §3d）。


def test_paper_tick_http_disabled_by_default():
    client = TestClient(app)
    r = client.post("/api/paper/execution-tick")
    assert r.status_code == 404


def test_paper_tick_http_when_enabled(monkeypatch):
    monkeypatch.setenv("PAPER_TICK_HTTP_ENABLED", "1")
    monkeypatch.setattr("api.run_paper_execution_tick", lambda: [])
    client = TestClient(app)
    r = client.post("/api/paper/execution-tick")
    assert r.status_code == 200
    body = r.json()
    assert body.get("ok") is True
    assert body.get("written") == 0
