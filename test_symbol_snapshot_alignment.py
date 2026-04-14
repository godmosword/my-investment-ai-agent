"""Snapshot price_alignment: OHLC tail vs fetch_symbol_quote."""

from __future__ import annotations

import pytest

import symbol_snapshot_service as sss


@pytest.mark.smoke
def test_align_snapshot_price_mismatch_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    series = [{"time": "2026-04-10", "close": 100.0}]
    monkeypatch.setattr(
        sss,
        "fetch_symbol_quote",
        lambda _s: {
            "last": 101.0,
            "error": None,
        },
    )
    a = sss._align_snapshot_price("BTC", series)
    assert a.get("aligned") is False
    assert a.get("abs_diff") == 1.0


@pytest.mark.smoke
def test_build_symbol_snapshot_includes_price_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Job:
        def __init__(self, rows):
            self._rows = rows

        def result(self):
            return self._rows

    class _Client:
        def query(self, sql: str):
            if "LIMIT 1" in sql and "grok_summary" in sql:
                return _Job(
                    [
                        {
                            "timestamp": "2026-04-12T00:00:00+00:00",
                            "dxy": 101.0,
                            "etf_flow_millions": 1.0,
                            "avg_risk_score": 2.0,
                            "mvrv_z_score": 1.0,
                            "sentiment_score": 0.1,
                            "sopr": 1.0,
                            "exchange_netflow": -1.0,
                            "regime_score": 2.0,
                            "grok_summary": "x",
                            "gpt_summary": "y",
                        }
                    ]
                )
            if "TIMESTAMP_SUB" in sql:
                return _Job([])
            if "UPPER(asset)" in sql:
                return _Job([])
            return _Job([])

    monkeypatch.setattr(
        sss,
        "fetch_symbol_ohlc",
        lambda _sym, days: [{"time": "2026-04-11", "open": 1, "high": 2, "low": 0.5, "close": 50.0}],
    )
    monkeypatch.setattr(
        sss,
        "fetch_symbol_quote",
        lambda _sym: {"last": 50.0, "error": None},
    )

    out = sss.build_symbol_snapshot(_Client(), "BTC", days=30, recommendation_limit=5)
    assert out.get("price_alignment", {}).get("aligned") is True
    prov = out.get("data_provenance") or {}
    assert "price_alignment" in prov
