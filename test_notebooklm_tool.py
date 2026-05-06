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


def test_notebooklm_missing_notebook_id(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "1")
    monkeypatch.delenv("NOTEBOOKLM_NOTEBOOK_ID", raising=False)
    import tools.notebooklm_tool as m

    importlib.reload(m)
    assert m.notebooklm_query("same q") == "[DATA_MISSING:notebooklm_notebook_id_missing]"


def test_parse_notebooklm_citations_and_query_many(monkeypatch):
    monkeypatch.setenv("NOTEBOOKLM_ENABLED", "1")
    import tools.notebooklm_tool as m

    importlib.reload(m)
    cites = m.parse_notebooklm_citations("Capex rose [p.12: capex note] and risks [page 44: risk note]")
    assert cites == [
        {"page": 12, "excerpt": "capex note"},
        {"page": 44, "excerpt": "risk note"},
    ]
    rows = m.notebooklm_query_many(["q1"], notebook_id="n1")
    assert rows[1]["answer"] == "[DATA_MISSING:notebooklm_not_implemented]"
    assert rows[1]["citations"] == []
