"""Binance funding-rate fetcher (queue 45 · P5-live PR-C)."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from tools import binance_funding_rate


@pytest.fixture(autouse=True)
def _reset_cache():
    binance_funding_rate.reset_cache_for_tests()
    yield
    binance_funding_rate.reset_cache_for_tests()


def _fake_response(payload: dict[str, Any]) -> Any:
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def _premium_payload(symbol: str, rate: float) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "markPrice": "1.0",
        "indexPrice": "1.0",
        "lastFundingRate": str(rate),
        "nextFundingTime": 0,
        "time": 0,
    }


def test_fetch_returns_both_assets_on_success(monkeypatch):
    """0.0001/8h × 3 × 365 × 100 = 10.95% APR."""
    payloads = {
        "BTCUSDT": _premium_payload("BTCUSDT", 0.00007152),
        "ETHUSDT": _premium_payload("ETHUSDT", 0.00027500),
    }
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        for sym, body in payloads.items():
            if sym in req.full_url:
                return _fake_response(body)
        raise AssertionError(f"unexpected URL {req.full_url}")

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", fake_urlopen)

    items = binance_funding_rate.fetch_funding_rates()
    assert items is not None
    by_asset = {row["asset"]: row for row in items}
    assert set(by_asset) == {"BTC", "ETH"}
    # 0.00007152 * 3 * 365 * 100 = 7.8314
    assert by_asset["BTC"]["funding_apr_pct"] == pytest.approx(7.8314, abs=1e-3)
    assert by_asset["ETH"]["funding_apr_pct"] == pytest.approx(30.1125, abs=1e-3)
    assert all(row["source"] == "binance_fapi" for row in items)
    assert len(calls) == 2


def test_negative_funding_rate_handled(monkeypatch):
    monkeypatch.setattr(
        binance_funding_rate.urllib.request,
        "urlopen",
        lambda *_a, **_k: _fake_response(_premium_payload("ANY", -0.0001)),
    )
    items = binance_funding_rate.fetch_funding_rates()
    assert items is not None
    assert all(row["funding_apr_pct"] < 0 for row in items)


@pytest.mark.parametrize("code", [429, 451, 503])
def test_fetch_returns_none_on_http_error(monkeypatch, code):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(b""))

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", boom)
    assert binance_funding_rate.fetch_funding_rates() is None


def test_fetch_returns_none_on_url_error(monkeypatch):
    def boom(req, timeout=None):
        raise urllib.error.URLError("DNS")

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", boom)
    assert binance_funding_rate.fetch_funding_rates() is None


def test_fetch_returns_none_on_invalid_json(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{not-json"

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", lambda *_a, **_k: _Resp())
    assert binance_funding_rate.fetch_funding_rates() is None


def test_fetch_returns_none_when_lastfundingrate_missing(monkeypatch):
    bad = {"symbol": "BTCUSDT"}  # no lastFundingRate
    monkeypatch.setattr(
        binance_funding_rate.urllib.request, "urlopen", lambda *_a, **_k: _fake_response(bad)
    )
    assert binance_funding_rate.fetch_funding_rates() is None


def test_fetch_all_or_nothing(monkeypatch):
    """One symbol failing collapses the whole batch."""
    state = {"n": 0}

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        if state["n"] == 2:
            raise urllib.error.URLError("flake")
        return _fake_response(_premium_payload("BTCUSDT", 0.0001))

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", fake_urlopen)
    assert binance_funding_rate.fetch_funding_rates() is None


def test_cache_skips_network_within_ttl(monkeypatch):
    state = {"n": 0}

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        return _fake_response(_premium_payload("X", 0.0001))

    monkeypatch.setattr(binance_funding_rate.urllib.request, "urlopen", fake_urlopen)
    binance_funding_rate.fetch_funding_rates()
    binance_funding_rate.fetch_funding_rates()
    assert state["n"] == 2  # 2 symbols on first call; cached on second
