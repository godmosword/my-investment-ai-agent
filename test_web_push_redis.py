"""Web Push Redis backend (fakeredis)."""

import json

import pytest
from fastapi.testclient import TestClient

from api import app


@pytest.fixture
def redis_client(monkeypatch):
    import fakeredis

    import web_push_store

    web_push_store.clear_subscriptions_for_tests()
    r = fakeredis.FakeStrictRedis(decode_responses=True)

    def _from_url(url, **_kwargs):  # noqa: ARG001
        return r

    monkeypatch.setattr("redis.from_url", _from_url)
    web_push_store.reset_redis_client_for_tests()
    monkeypatch.setenv("WEB_PUSH_REDIS_URL", "redis://localhost:6379/0")
    yield r
    web_push_store.clear_subscriptions_for_tests()
    monkeypatch.delenv("WEB_PUSH_REDIS_URL", raising=False)


def test_push_subscribe_stores_full_json_in_redis(redis_client, monkeypatch):
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    monkeypatch.delenv("WEB_PUSH_STORE", raising=False)

    client = TestClient(app)
    body = {"endpoint": "https://push.example.com/ep1", "keys": {"p256dh": "x", "auth": "y"}}
    r = client.post("/api/push/subscribe", json=body)
    assert r.status_code == 200
    js = r.json()
    assert js.get("backend") == "redis"
    assert js.get("stored") is True
    fp = js["endpoint_fp"]
    raw = redis_client.hget("webpush:subscriptions", fp)
    assert raw
    data = json.loads(raw)
    assert data["endpoint"] == body["endpoint"]
    assert data["keys"] == body["keys"]


def test_push_test_send_404_without_admin_key(redis_client, monkeypatch):
    monkeypatch.setenv("WEB_PUSH_ENABLED", "1")
    monkeypatch.setenv("WEB_PUSH_ADMIN_KEY", "admin-secret")

    client = TestClient(app)
    r = client.post("/api/push/test-send", json={"title": "t", "body": "b"})
    assert r.status_code == 404
