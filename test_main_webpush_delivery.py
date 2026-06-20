"""Boundary tests for main._deliver_daily_brief_webpush (daily-brief delivery branch).

Asserts the flag/report_ok/preflight gating and that the helper never raises into
the main pipeline. broadcast is mocked so no real Web Push is attempted.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.boundary


def _patch_store(monkeypatch, *, enabled=True, redis="redis://x", subs=1):
    import main
    import web_push_store

    monkeypatch.setattr(web_push_store, "web_push_enabled", lambda: enabled)
    monkeypatch.setattr(web_push_store, "subscription_count", lambda: subs)
    if redis:
        monkeypatch.setenv("WEB_PUSH_REDIS_URL", redis)
    else:
        monkeypatch.delenv("WEB_PUSH_REDIS_URL", raising=False)
    calls: list = []
    monkeypatch.setattr(web_push_store, "broadcast", lambda *a, **k: calls.append((a, k)) or {"ok": True, "sent": 1, "attempted": 1})
    return main, calls


def test_no_send_when_flag_off(monkeypatch):
    main, calls = _patch_store(monkeypatch)
    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", False)
    main._deliver_daily_brief_webpush("2026-06-20", True)
    assert calls == []


def test_no_send_when_report_not_ok(monkeypatch):
    main, calls = _patch_store(monkeypatch)
    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", True)
    main._deliver_daily_brief_webpush("2026-06-20", False)
    assert calls == []


def test_no_send_when_redis_unconfigured(monkeypatch):
    main, calls = _patch_store(monkeypatch, redis="")
    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", True)
    main._deliver_daily_brief_webpush("2026-06-20", True)
    assert calls == []  # preflight blocks (no shared Redis → no recipients)


def test_no_send_when_zero_subscriptions(monkeypatch):
    main, calls = _patch_store(monkeypatch, subs=0)
    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", True)
    main._deliver_daily_brief_webpush("2026-06-20", True)
    assert calls == []


def test_sends_when_enabled_and_ok(monkeypatch):
    main, calls = _patch_store(monkeypatch)
    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", True)
    monkeypatch.setenv("WEB_PUSH_PORTAL_URL", "https://portal.example")
    main._deliver_daily_brief_webpush("2026-06-20", True)
    assert len(calls) == 1
    args, _kwargs = calls[0]
    body, url = args[1], args[2]
    assert "2026-06-20" in body
    assert url == "https://portal.example/report/2026-06-20"


def test_helper_never_raises(monkeypatch):
    import main
    import web_push_store

    monkeypatch.setattr(main, "WEB_PUSH_DAILY_BRIEF", True)
    monkeypatch.setattr(web_push_store, "web_push_enabled", lambda: True)
    monkeypatch.setenv("WEB_PUSH_REDIS_URL", "redis://x")
    monkeypatch.setattr(web_push_store, "subscription_count", lambda: 1)

    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(web_push_store, "broadcast", boom)
    # Must swallow the exception (pipeline safety), not propagate.
    main._deliver_daily_brief_webpush("2026-06-20", True)
