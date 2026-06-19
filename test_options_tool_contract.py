"""Tool 快取紅線 contract: agent tools must use the shared tools_cache_http cache.

Asserts (a) the agent_tools module imports the shared cache and defines no private
cache of its own, and (b) calling the tool actually exercises _get_cache/_set_cache.
"""

from __future__ import annotations

import pytest

import tools_cache_http
from tools.options import agent_tools


@pytest.fixture()
def _offline(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "1")
    monkeypatch.setenv("SKIP_BIGQUERY", "1")


def test_agent_tools_has_no_private_cache():
    # No module-level cache dict shadowing the shared one.
    assert not hasattr(agent_tools, "_CACHE")
    src = __import__("inspect").getsource(agent_tools)
    assert "from tools_cache_http import _get_cache, _set_cache" in src


def test_gex_tool_uses_shared_cache(monkeypatch, _offline):
    calls = {"get": 0, "set": 0}
    real_set = tools_cache_http._set_cache

    def spy_get(key):
        calls["get"] += 1
        return None  # force a miss so _set_cache runs

    def spy_set(key, value):
        calls["set"] += 1
        return real_set(key, value)

    monkeypatch.setattr(agent_tools, "_get_cache", spy_get)
    monkeypatch.setattr(agent_tools, "_set_cache", spy_set)

    out = agent_tools._gex_payload("MU")
    assert "total_gex" in out
    assert calls["get"] == 1
    assert calls["set"] == 1


def test_flow_tool_returns_json_and_caches(monkeypatch, _offline):
    seen = {}
    monkeypatch.setattr(agent_tools, "_get_cache", lambda k: None)
    monkeypatch.setattr(agent_tools, "_set_cache", lambda k, v: seen.update({k: v}))

    out = agent_tools._flow_payload("MU")
    assert out.startswith("[")  # JSON array
    assert ("options_flow", "MU") in seen


def test_tool_missing_data_returns_marker_not_fabrication(_offline):
    # No fixture for ZZZZ → snapshots empty → DATA_MISSING, never a guessed number.
    out = agent_tools._flow_payload("ZZZZ")
    assert out == "[DATA_MISSING:polygon_options_snapshot_greeks]"
