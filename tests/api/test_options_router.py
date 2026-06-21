"""Contract tests for the options flow + GEX read API.

Covers the degraded (Polygon pending) envelope and the BQ-backed data path
(reader monkeypatched so no real BigQuery is hit).
"""

from __future__ import annotations

import pytest

from api_routers import options
from tests.api.helpers import make_api_client


@pytest.fixture()
def client(monkeypatch):
    return make_api_client(monkeypatch)


def test_summary_pending_when_tables_unconfigured(client, monkeypatch):
    monkeypatch.setattr(options.reader, "tables_configured", lambda: False)
    resp = client.get("/api/options/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["reason"] == "polygon_options_pending"
    assert "MU" in body["watchlist"]
    assert body["items"] == []


def test_gex_pending_envelope_is_stable(client, monkeypatch):
    monkeypatch.setattr(options.reader, "tables_configured", lambda: False)
    body = client.get("/api/options/gex/mu").json()
    assert body["enabled"] is False
    assert body["underlying"] == "MU"
    assert body["reason"] == "polygon_options_pending"


def test_summary_data_path_reads_bq(client, monkeypatch):
    monkeypatch.setattr(options.reader, "tables_configured", lambda: True)
    monkeypatch.setattr(options, "_watchlist", lambda: ["MU"])
    monkeypatch.setattr(
        options.reader,
        "read_latest_gex",
        lambda syms: {"MU": {"underlying": "MU", "total_gex": 300000.0, "call_gex": 500000.0, "put_gex": -200000.0, "spot_price": 100.0, "trade_date": "2026-06-19"}},
    )
    monkeypatch.setattr(options.reader, "read_recent_unusual", lambda sym, limit=50: [{"signal_type": "volume_oi"}])

    body = client.get("/api/options/summary").json()
    assert body["enabled"] is True
    item = body["items"][0]
    assert item["underlying"] == "MU"
    assert item["gex"]["total_gex"] == 300000.0
    assert item["gex"]["regime"] == "positive"
    assert item["unusual_count"] == 1


def test_flow_data_path_returns_signals(client, monkeypatch):
    monkeypatch.setattr(options.reader, "tables_configured", lambda: True)
    monkeypatch.setattr(
        options.reader,
        "read_recent_unusual",
        lambda sym, limit=50: [
            {"option_ticker": "O:MU260116C00100000", "signal_type": "volume_oi", "score": 0.5, "rationale": "5x OI"}
        ],
    )
    body = client.get("/api/options/flow/MU").json()
    assert body["enabled"] is True
    assert body["signals"][0]["signal_type"] == "volume_oi"
    assert body["signals"][0]["option_ticker"] == "O:MU260116C00100000"


def test_gex_per_strike_additive_when_present(client, monkeypatch):
    monkeypatch.setattr(options.reader, "tables_configured", lambda: True)
    monkeypatch.setattr(options.reader, "read_latest_gex", lambda syms: {"MU": {"underlying": "MU", "total_gex": 300000.0}})
    monkeypatch.setattr(options.reader, "read_gex_history", lambda sym, days=60: [])
    monkeypatch.setattr(
        options.reader,
        "read_latest_by_strike",
        lambda sym: [
            {"strike": 95.0, "call_gex": 0.0, "put_gex": -200000.0, "net_gex": -200000.0},
            {"strike": 100.0, "call_gex": 500000.0, "put_gex": 0.0, "net_gex": 500000.0},
        ],
    )
    body = client.get("/api/options/gex/MU").json()
    assert body["enabled"] is True
    assert len(body["per_strike"]) == 2
    assert body["per_strike"][1]["strike"] == 100.0
    assert body["per_strike"][1]["net_gex"] == 500000.0


def test_gex_per_strike_empty_when_table_unset(client, monkeypatch):
    """by-strike 表未設/無資料 → enabled 且 per_strike: []（不 pending、不示意）。"""
    monkeypatch.setattr(options.reader, "tables_configured", lambda: True)
    monkeypatch.setattr(options.reader, "read_latest_gex", lambda syms: {})
    monkeypatch.setattr(options.reader, "read_gex_history", lambda sym, days=60: [])
    monkeypatch.setattr(options.reader, "read_latest_by_strike", lambda sym: [])
    body = client.get("/api/options/gex/MU").json()
    assert body["enabled"] is True
    assert body["reason"] == "no_data_yet"
    assert body["per_strike"] == []
