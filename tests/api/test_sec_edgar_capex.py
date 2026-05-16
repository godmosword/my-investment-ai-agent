"""SEC EDGAR hyperscaler capex fetcher (queue 45 · P2-live PR-A)."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from tools import sec_edgar_capex


@pytest.fixture(autouse=True)
def _reset_cache_and_env(monkeypatch):
    sec_edgar_capex.reset_cache_for_tests()
    monkeypatch.setenv("SEC_EDGAR_CONTACT_EMAIL", "test@example.com")
    yield
    sec_edgar_capex.reset_cache_for_tests()


def _fake_response(payload: dict[str, Any]) -> Any:
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def test_fetch_latest_capex_returns_record_on_success(monkeypatch):
    payload = {
        "units": {
            "USD": [
                {"end": "2025-09-30", "val": 23_000_000_000, "fy": 2026, "fp": "Q1", "form": "10-Q", "accn": "0001-23"},
                {"end": "2025-06-30", "val": 19_000_000_000, "fy": 2025, "fp": "Q4", "form": "10-K", "accn": "0001-22"},
            ]
        }
    }

    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        assert "MSFT" not in req.full_url  # URL uses CIK, not ticker
        assert "0000789019" in req.full_url
        assert req.headers["User-agent"].startswith("q-silicon-research/1.0")
        return _fake_response(payload)

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", fake_urlopen)

    rec = sec_edgar_capex.fetch_latest_capex("MSFT")
    assert rec is not None
    assert rec["ticker"] == "MSFT"
    assert rec["capex_b_usd"] == 23.0
    assert rec["as_of"] == "2025-09-30"
    assert rec["source"] == "sec_edgar"
    assert rec["form"] == "10-Q"
    assert len(calls) == 1


def test_fetch_returns_none_when_contact_email_unset(monkeypatch):
    monkeypatch.delenv("SEC_EDGAR_CONTACT_EMAIL", raising=False)

    def boom(*_args, **_kw):
        raise AssertionError("should not hit network without User-Agent email")

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", boom)
    assert sec_edgar_capex.fetch_latest_capex("MSFT") is None


@pytest.mark.parametrize("code", [429, 503])
def test_fetch_returns_none_on_http_error(monkeypatch, code):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(b""))

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", fake_urlopen)
    assert sec_edgar_capex.fetch_latest_capex("MSFT") is None


def test_fetch_returns_none_on_url_error(monkeypatch):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("DNS")

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", fake_urlopen)
    assert sec_edgar_capex.fetch_latest_capex("GOOG") is None


def test_fetch_returns_none_on_invalid_json(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{not-json"

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", lambda *_a, **_k: _Resp())
    assert sec_edgar_capex.fetch_latest_capex("META") is None


def test_fetch_returns_none_on_missing_units(monkeypatch):
    monkeypatch.setattr(
        sec_edgar_capex.urllib.request,
        "urlopen",
        lambda *_a, **_k: _fake_response({"units": {}}),
    )
    assert sec_edgar_capex.fetch_latest_capex("AMZN") is None


def test_unknown_ticker_returns_none():
    assert sec_edgar_capex.fetch_latest_capex("NVDA") is None


def test_cache_skips_network_within_ttl(monkeypatch):
    payload = {"units": {"USD": [{"end": "2025-09-30", "val": 1e9, "fy": 2026, "fp": "Q1", "form": "10-Q", "accn": "x"}]}}
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        return _fake_response(payload)

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", fake_urlopen)

    sec_edgar_capex.fetch_latest_capex("ORCL")
    sec_edgar_capex.fetch_latest_capex("ORCL")
    assert calls["n"] == 1


def test_fetch_all_returns_none_if_any_ticker_fails(monkeypatch):
    """All-or-nothing: any single failure collapses the batch to None."""
    payload = {"units": {"USD": [{"end": "2025-09-30", "val": 1e9, "fy": 2026, "fp": "Q1", "form": "10-Q", "accn": "x"}]}}
    state = {"n": 0}

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        if state["n"] == 3:
            raise urllib.error.URLError("flake")
        return _fake_response(payload)

    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", fake_urlopen)
    assert sec_edgar_capex.fetch_all_hyperscaler_capex() is None


def test_fetch_all_returns_five_items_on_success(monkeypatch):
    payload = {"units": {"USD": [{"end": "2025-09-30", "val": 1e9, "fy": 2026, "fp": "Q1", "form": "10-Q", "accn": "x"}]}}
    monkeypatch.setattr(sec_edgar_capex.urllib.request, "urlopen", lambda *_a, **_k: _fake_response(payload))

    items = sec_edgar_capex.fetch_all_hyperscaler_capex()
    assert items is not None
    assert {row["ticker"] for row in items} == {"MSFT", "GOOG", "META", "AMZN", "ORCL"}
    assert all(row["source"] == "sec_edgar" for row in items)
