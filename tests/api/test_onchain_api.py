"""Crypto on-chain dashboard fixture endpoint (queue 45 · P5-mock)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api import app
from api_routers import macro as macro_router


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.delenv("QSILICON_MASTER_KEY", raising=False)
    macro_router._onchain_reset_cache_for_tests()
    return TestClient(app)


def test_onchain_enabled_false_when_fixture_missing(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(tmp_path / "nope.json"))
    r = client.get("/api/macro/onchain")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["reason"] == "fixture_missing"


def test_onchain_enabled_false_on_invalid_json(client, monkeypatch, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    r = client.get("/api/macro/onchain")
    assert r.status_code == 200
    assert r.json()["reason"] == "fixture_invalid"


def test_onchain_returns_three_blocks_from_fixture(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(
        json.dumps(
            {
                "as_of": "2026-05-16",
                "live": False,
                "disclaimer": "test",
                "btc_valuation": {"source": "mock", "items": [{"metric": "MVRV-Z"}]},
                "exchange_flow": {"source": "mock", "items": [{"venue": "All CEX"}]},
                "funding_rate": {"source": "mock", "items": [{"asset": "BTC"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    r = client.get("/api/macro/onchain")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["live"] is False
    assert body["btc_valuation"]["items"][0]["metric"] == "MVRV-Z"
    assert body["exchange_flow"]["enabled"] is False
    assert body["exchange_flow"]["reason"] == "no_free_equivalent"
    assert body["funding_rate"]["items"][0]["asset"] == "BTC"


def test_exchange_flow_is_disabled_without_free_equivalent(client, monkeypatch, tmp_path):
    path = tmp_path / "exchange-flow.json"
    path.write_text(
        json.dumps(
            {
                "btc_valuation": {"source": "mock", "items": []},
                "exchange_flow": {
                    "source": "mock",
                    "items": [{"venue": "All CEX", "window_days": 7, "net_flow_usd": None}],
                },
                "funding_rate": {"source": "mock", "items": []},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))

    body = client.get("/api/macro/onchain").json()

    assert body["live_block_status"]["exchange_flow"] == "disabled"
    assert body["exchange_flow"]["enabled"] is False
    assert body["exchange_flow"]["reason"] == "no_free_equivalent"
    assert body["exchange_flow"]["items"] == []


def test_onchain_live_flag_requires_both_env_and_fixture(client, monkeypatch, tmp_path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps({"live": True, "btc_valuation": {}, "exchange_flow": {}, "funding_rate": {}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))

    monkeypatch.delenv("ONCHAIN_LIVE", raising=False)
    macro_router._onchain_reset_cache_for_tests()
    assert client.get("/api/macro/onchain").json()["live"] is False

    monkeypatch.setenv("ONCHAIN_LIVE", "1")
    macro_router._onchain_reset_cache_for_tests()
    assert client.get("/api/macro/onchain").json()["live"] is True


def test_onchain_caches_within_ttl(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(json.dumps({"btc_valuation": {}, "exchange_flow": {}, "funding_rate": {}}), encoding="utf-8")
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    assert client.get("/api/macro/onchain").json()["cached"] is False
    assert client.get("/api/macro/onchain").json()["cached"] is True


def test_funding_live_uses_binance_when_flag_on(client, monkeypatch, tmp_path):
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "btc_valuation": {"items": []},
                "exchange_flow": {"items": []},
                "funding_rate": {"source": "mock", "items": [{"asset": "BTC"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    monkeypatch.setenv("ONCHAIN_FUNDING_LIVE", "1")

    from tools import binance_funding_rate

    live_items = [
        {"asset": "BTC", "venue": "Binance", "funding_apr_pct": 7.83, "as_of": "2026-05-16", "source": "binance_fapi"},
        {"asset": "ETH", "venue": "Binance", "funding_apr_pct": 30.11, "as_of": "2026-05-16", "source": "binance_fapi"},
    ]
    monkeypatch.setattr(binance_funding_rate, "fetch_funding_rates", lambda: live_items)

    macro_router._onchain_reset_cache_for_tests()
    body = client.get("/api/macro/onchain").json()
    assert body["live_block_status"]["funding"] == "live"
    assert body["live_block_status"]["valuation"] == "mock"
    assert body["live_block_status"]["exchange_flow"] == "disabled"
    assert body["funding_rate"]["source"] == "binance_fapi"
    assert {row["asset"] for row in body["funding_rate"]["items"]} == {"BTC", "ETH"}


def test_funding_live_falls_back_to_fixture_when_fetch_fails(client, monkeypatch, tmp_path):
    path = tmp_path / "fb.json"
    path.write_text(
        json.dumps(
            {
                "btc_valuation": {"items": []},
                "exchange_flow": {"items": []},
                "funding_rate": {"source": "mock", "items": [{"asset": "BTC"}]},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    monkeypatch.setenv("ONCHAIN_FUNDING_LIVE", "1")

    from tools import binance_funding_rate

    monkeypatch.setattr(binance_funding_rate, "fetch_funding_rates", lambda: None)

    macro_router._onchain_reset_cache_for_tests()
    body = client.get("/api/macro/onchain").json()
    assert body["live_block_status"]["funding"] == "fallback"
    assert body["funding_rate"]["source"] == "mock"


def test_funding_live_off_keeps_mock_status(client, monkeypatch, tmp_path):
    path = tmp_path / "good.json"
    path.write_text(
        json.dumps({"btc_valuation": {}, "exchange_flow": {}, "funding_rate": {"source": "mock"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("ONCHAIN_FIXTURE_FILE", str(path))
    monkeypatch.delenv("ONCHAIN_FUNDING_LIVE", raising=False)
    macro_router._onchain_reset_cache_for_tests()
    body = client.get("/api/macro/onchain").json()
    assert body["live_block_status"]["funding"] == "mock"
