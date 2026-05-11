"""Unit tests for ``tools.tech_pulse_tool`` (MOCK_APIS / TECH_PULSE_URL paths)."""

from __future__ import annotations

import json
from unittest import mock

import pytest

from tools import tech_pulse_tool as tpt


@pytest.fixture(autouse=True)
def _clear_tech_pulse_cache():
    with tpt._CACHE_LOCK:
        tpt._CACHE.clear()
    yield
    with tpt._CACHE_LOCK:
        tpt._CACHE.clear()


def test_disabled_returns_empty(monkeypatch):
    monkeypatch.delenv("TECH_PULSE_IN_BRIEF", raising=False)
    assert tpt.fetch_tech_pulse_exclusion_snippet() == ""


def test_mock_apis_returns_cached_stub(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_IN_BRIEF", "1")
    monkeypatch.setenv("MOCK_APIS", "1")
    a = tpt.fetch_tech_pulse_exclusion_snippet()
    b = tpt.fetch_tech_pulse_exclusion_snippet()
    assert a == b
    assert "MOCK_APIS=1" in a
    assert "[DATA_MISSING:tech_pulse_mock]" in a


def test_no_url_data_missing(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_IN_BRIEF", "1")
    monkeypatch.delenv("MOCK_APIS", raising=False)
    monkeypatch.delenv("TECH_PULSE_URL", raising=False)
    out = tpt.fetch_tech_pulse_exclusion_snippet()
    assert "[DATA_MISSING:tech_pulse_no_url]" in out


def test_http_json_summary(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_IN_BRIEF", "1")
    monkeypatch.delenv("MOCK_APIS", raising=False)
    monkeypatch.setenv("TECH_PULSE_URL", "https://example.invalid/tech-pulse.json")
    payload = json.dumps({"summary": "  hello world  "}).encode()

    class _Resp:
        def read(self):
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

    with mock.patch("tools.tech_pulse_tool.urllib.request.urlopen", return_value=_Resp()):
        out = tpt.fetch_tech_pulse_exclusion_snippet()
    assert out == "hello world"


def test_http_error_sets_data_missing(monkeypatch):
    monkeypatch.setenv("TECH_PULSE_IN_BRIEF", "1")
    monkeypatch.delenv("MOCK_APIS", raising=False)
    monkeypatch.setenv("TECH_PULSE_URL", "https://example.invalid/bad")
    with mock.patch(
        "tools.tech_pulse_tool.urllib.request.urlopen",
        side_effect=OSError("network down"),
    ):
        out = tpt.fetch_tech_pulse_exclusion_snippet()
    assert "tech_pulse_http_error" in out
