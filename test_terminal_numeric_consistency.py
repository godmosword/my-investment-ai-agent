"""Bloomberg alignment §4 item 6: quote last vs OHLC last close (same yfinance stub)."""

from __future__ import annotations

import sys
import types
import pandas as pd
import pytest

import symbol_snapshot_service as sss


@pytest.mark.smoke
def test_quote_last_matches_last_ohlc_close_same_yfinance_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """When yfinance returns the same daily frame, last close from quote matches OHLC tail."""
    idx = pd.date_range("2026-01-01", periods=6, freq="D", tz="UTC")
    hist = pd.DataFrame(
        {
            "Open": [1.0] * 6,
            "High": [1.1] * 6,
            "Low": [0.9] * 6,
            "Close": [10.0, 10.5, 11.0, 11.2, 11.4, 112.34],
        },
        index=idx,
    )

    class _FakeTicker:
        def history(self, period=None, interval=None):
            return hist

    def _fake_ticker(_sym):
        return _FakeTicker()

    yf_stub = types.ModuleType("yfinance")
    yf_stub.Ticker = _fake_ticker
    monkeypatch.setitem(sys.modules, "yfinance", yf_stub)

    monkeypatch.setattr(sss, "_quote_cache", {})
    monkeypatch.setattr(sss, "_ohlc_cache", {})

    q = sss.fetch_symbol_quote("BTC")
    ohlc = sss.fetch_symbol_ohlc("BTC", 10)

    assert ohlc, "expected non-empty OHLC"
    assert q.get("last") is not None
    assert abs(float(q["last"]) - float(ohlc[-1]["close"])) < 1e-6
    prev = float(ohlc[-2]["close"])
    expected_pct = round((float(ohlc[-1]["close"]) - prev) / prev * 100.0, 4)
    assert q.get("change_pct_1d") is not None
    assert abs(float(q["change_pct_1d"]) - expected_pct) < 1e-6
