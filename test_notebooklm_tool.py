"""Tests for tools/notebooklm_tool.py (Phase 0–1: off by default, cache contract)."""

import importlib

import pytest


def test_notebooklm_disabled_returns_placeholder(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "0")
    import tools.notebooklm_tool as m

    importlib.reload(m)
    with m._CACHE_LOCK:
        m._CACHE.clear()
    assert m.notebooklm_enabled() is False
    assert m.notebooklm_query("hello") == "[DATA_MISSING:notebooklm_disabled]"


def test_notebooklm_enabled_stub_uses_cache(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "1")
    import tools.notebooklm_tool as m

    importlib.reload(m)
    with m._CACHE_LOCK:
        m._CACHE.clear()
    assert m.notebooklm_enabled() is True
    a = m.notebooklm_query("same q", notebook_id="n1")
    b = m.notebooklm_query("same q", notebook_id="n1")
    assert a == b == "[DATA_MISSING:notebooklm_not_implemented]"
