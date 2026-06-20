"""Unit tests for web_push_store.broadcast (daily-brief Web Push).

pywebpush is not installed in CI, so a fake module is injected via sys.modules;
broadcast does ``from pywebpush import webpush`` at call time so the fake is used.
"""

from __future__ import annotations

import json
import sys
import types

import pytest

import web_push_store


@pytest.fixture()
def fake_pywebpush(monkeypatch):
    calls: list[dict] = []

    def fake_webpush(**kwargs):
        calls.append(kwargs)

    mod = types.ModuleType("pywebpush")
    mod.webpush = fake_webpush
    mod.WebPushException = Exception
    monkeypatch.setitem(sys.modules, "pywebpush", mod)
    monkeypatch.setenv("WEB_PUSH_VAPID_PRIVATE_KEY", "fake-pem")
    return calls


def _subs(monkeypatch, n: int):
    subs = [{"endpoint": f"https://push.example/{i}", "keys": {"p256dh": "k", "auth": "a"}} for i in range(n)]
    monkeypatch.setattr(web_push_store, "list_subscription_infos_for_send", lambda: subs)
    return subs


@pytest.mark.smoke
def test_broadcast_sends_to_all_and_includes_url(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 2)
    res = web_push_store.broadcast("t", "b", "https://portal.example/report/2026-06-20")
    assert res["ok"] is True
    assert res["sent"] == 2
    assert res["attempted"] == 2
    payload = json.loads(fake_pywebpush[0]["data"])
    assert payload["url"] == "https://portal.example/report/2026-06-20"
    assert payload["title"] == "t"


def test_broadcast_no_subscriptions_is_not_ok(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 0)
    res = web_push_store.broadcast("t", "b")
    assert res["ok"] is False
    assert res["error"] == "no_subscriptions"
    assert res["sent"] == 0


def test_broadcast_vapid_unset_is_not_ok(monkeypatch):
    monkeypatch.delenv("WEB_PUSH_VAPID_PRIVATE_KEY", raising=False)
    res = web_push_store.broadcast("t", "b")
    assert res["ok"] is False
    assert res["error"] == "vapid_unset"


def test_broadcast_all_failures_not_ok(monkeypatch):
    monkeypatch.setenv("WEB_PUSH_VAPID_PRIVATE_KEY", "fake-pem")
    mod = types.ModuleType("pywebpush")

    def boom(**kwargs):
        raise RuntimeError("push endpoint gone")

    mod.webpush = boom
    monkeypatch.setitem(sys.modules, "pywebpush", mod)
    _subs(monkeypatch, 3)
    res = web_push_store.broadcast("t", "b")
    assert res["ok"] is False  # sent == 0 despite having subscribers
    assert res["sent"] == 0
    assert len(res["errors"]) >= 1


def test_broadcast_respects_cap(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 5)
    res = web_push_store.broadcast("t", "b", cap=2)
    assert res["sent"] == 2
    assert res["attempted"] == 2


def test_broadcast_truncates_body(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 1)
    web_push_store.broadcast("t", "x" * 500)
    payload = json.loads(fake_pywebpush[0]["data"])
    assert len(payload["body"]) <= web_push_store._PUSH_BODY_MAX


def test_broadcast_drops_non_http_url(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 1)
    web_push_store.broadcast("t", "b", "javascript:alert(1)")
    payload = json.loads(fake_pywebpush[0]["data"])
    assert "url" not in payload


def test_send_test_push_delegates_to_broadcast(fake_pywebpush, monkeypatch):
    _subs(monkeypatch, 1)
    res = web_push_store.send_test_push("t", "b")
    assert res["ok"] is True
    assert res["sent"] == 1
