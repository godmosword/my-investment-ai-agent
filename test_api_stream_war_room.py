"""Tests for GET /api/stream/war-room (M4 SSE)."""

from fastapi.testclient import TestClient

from api import _parse_sse_watch_symbols_param, app


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


def test_parse_sse_watch_symbols_empty():
    assert _parse_sse_watch_symbols_param(None) == []
    assert _parse_sse_watch_symbols_param("") == []
    assert _parse_sse_watch_symbols_param("  , , ") == []


def test_parse_sse_watch_symbols_csv():
    assert _parse_sse_watch_symbols_param("BTC, NVDA") == ["BTC", "NVDA"]


def test_parse_sse_watch_symbols_skips_invalid_tokens():
    assert _parse_sse_watch_symbols_param("NVDA, BAD SYM, MSFT") == ["NVDA", "MSFT"]


def test_parse_sse_watch_symbols_respects_max_n():
    raw = ",".join(f"S{i}" for i in range(12))
    out = _parse_sse_watch_symbols_param(raw, max_n=8)
    assert len(out) == 8
    assert out[0] == "S0"
    assert out[-1] == "S7"
