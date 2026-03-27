"""FastAPI Web Push stub contract."""

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
