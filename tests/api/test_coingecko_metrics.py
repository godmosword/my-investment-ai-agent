"""CoinGecko / Alternative.me valuation fetcher (queue 53 · FA-1)."""

from __future__ import annotations

import io
import json
import urllib.error
from typing import Any

import pytest

from tools import coingecko_metrics


@pytest.fixture(autouse=True)
def _reset_cache():
    coingecko_metrics.reset_cache_for_tests()
    yield
    coingecko_metrics.reset_cache_for_tests()


def _fake_response(payload: dict[str, Any]) -> Any:
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode("utf-8")

    return _Resp()


def _global_payload() -> dict[str, Any]:
    return {
        "data": {
            "market_cap_percentage": {"btc": 51.23},
            "total_market_cap": {"usd": 2_450_000_000_000},
            "total_volume": {"usd": 86_000_000_000},
        }
    }


def _fng_payload() -> dict[str, Any]:
    return {"data": [{"value": "72", "value_classification": "Greed", "timestamp": "1779321600"}]}


def test_fetch_returns_free_valuation_items(monkeypatch):
    calls: list[str] = []

    def fake_urlopen(req, timeout=None):
        calls.append(req.full_url)
        if "coingecko" in req.full_url:
            return _fake_response(_global_payload())
        if "alternative.me" in req.full_url:
            return _fake_response(_fng_payload())
        raise AssertionError(f"unexpected URL {req.full_url}")

    monkeypatch.setattr(coingecko_metrics.urllib.request, "urlopen", fake_urlopen)

    block = coingecko_metrics.fetch_valuation_snapshot()

    assert block is not None
    assert block["source"] == "coingecko_altme"
    by_metric = {row["metric"]: row for row in block["items"]}
    assert by_metric["BTC Dominance"]["value"] == pytest.approx(51.23)
    assert by_metric["Total Crypto Market Cap"]["value"] == pytest.approx(2_450_000_000_000)
    assert by_metric["Fear & Greed"]["value"] == 72
    assert by_metric["Fear & Greed"]["regime"] == "Greed"
    assert len(calls) == 2


@pytest.mark.parametrize("code", [429, 451, 503])
def test_fetch_returns_none_on_http_error(monkeypatch, code):
    def boom(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, code, "err", {}, io.BytesIO(b""))

    monkeypatch.setattr(coingecko_metrics.urllib.request, "urlopen", boom)
    assert coingecko_metrics.fetch_valuation_snapshot() is None


def test_fetch_returns_none_on_invalid_json(monkeypatch):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return b"{not-json"

    monkeypatch.setattr(coingecko_metrics.urllib.request, "urlopen", lambda *_a, **_k: _Resp())
    assert coingecko_metrics.fetch_valuation_snapshot() is None


def test_fetch_returns_none_on_missing_required_fields(monkeypatch):
    def fake_urlopen(req, timeout=None):
        if "coingecko" in req.full_url:
            return _fake_response({"data": {}})
        return _fake_response(_fng_payload())

    monkeypatch.setattr(coingecko_metrics.urllib.request, "urlopen", fake_urlopen)
    assert coingecko_metrics.fetch_valuation_snapshot() is None


def test_cache_skips_network_within_ttl(monkeypatch):
    state = {"n": 0}

    def fake_urlopen(req, timeout=None):
        state["n"] += 1
        if "coingecko" in req.full_url:
            return _fake_response(_global_payload())
        return _fake_response(_fng_payload())

    monkeypatch.setattr(coingecko_metrics.urllib.request, "urlopen", fake_urlopen)
    coingecko_metrics.fetch_valuation_snapshot()
    coingecko_metrics.fetch_valuation_snapshot()
    assert state["n"] == 2
