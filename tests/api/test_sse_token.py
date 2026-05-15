"""SSE short-lived token mint + verify (Phase 3 backlog closure)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sse_token
from api import app


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    sse_token.reset_for_tests()
    return TestClient(app)


def test_stream_token_404_without_key(client, monkeypatch):
    monkeypatch.delenv("API_STREAM_AUTH_KEY", raising=False)
    r = client.post("/api/stream/token")
    assert r.status_code == 404


def test_stream_token_requires_long_lived_key(client, monkeypatch):
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "secret-key")
    r = client.post("/api/stream/token")
    assert r.status_code == 403


def test_stream_token_mint_shape_and_ttl(client, monkeypatch):
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "secret-key")
    monkeypatch.setenv("SSE_TOKEN_TTL_SECONDS", "45")
    r = client.post("/api/stream/token", headers={"X-QS-Stream-Key": "secret-key"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body.get("token"), str) and len(body["token"]) >= 16
    assert body.get("ttl_seconds") == 45
    assert isinstance(body.get("expires_at"), (int, float))
    assert sse_token.verify(body["token"]) is True


def test_stream_token_ttl_clamped(client, monkeypatch):
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "k")
    monkeypatch.setenv("SSE_TOKEN_TTL_SECONDS", "9999")
    r = client.post("/api/stream/token", headers={"X-QS-Stream-Key": "k"})
    assert r.status_code == 200
    assert r.json()["ttl_seconds"] == sse_token.MAX_TTL_SECONDS


def test_sse_token_verify_rejects_unknown_or_empty():
    sse_token.reset_for_tests()
    assert sse_token.verify(None) is False
    assert sse_token.verify("") is False
    assert sse_token.verify("not-a-real-token") is False


def test_sse_token_verify_expires(monkeypatch):
    sse_token.reset_for_tests()
    monkeypatch.setenv("SSE_TOKEN_TTL_SECONDS", "10")
    minted = sse_token.mint()
    assert sse_token.verify(minted.token) is True
    # Fast-forward by patching the clock past expiry.
    monkeypatch.setattr(sse_token, "_now", lambda: minted.expires_at + 1)
    assert sse_token.verify(minted.token) is False


def test_sse_stream_rejects_invalid_token(client, monkeypatch):
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "k")
    monkeypatch.setenv("TERMINAL_SSE_ENABLED", "1")
    r = client.get("/api/stream/war-room?stream_token=bogus")
    assert r.status_code == 403


def test_sse_stream_rejects_without_any_auth(client, monkeypatch):
    monkeypatch.setenv("API_STREAM_AUTH_KEY", "k")
    monkeypatch.setenv("TERMINAL_SSE_ENABLED", "1")
    r = client.get("/api/stream/war-room")
    assert r.status_code == 403
