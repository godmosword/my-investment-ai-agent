from __future__ import annotations

import pytest

from api_routers import macro
from tests.api.helpers import make_api_client


@pytest.fixture()
def client(monkeypatch):
    macro._macro_cache = None
    return make_api_client(monkeypatch)


def test_macro_snapshot_returns_eight_indicators(client, monkeypatch):
    fixtures = {
        "^TNX": [4.0, 4.1, 4.2, 4.25, 4.3, 4.4, 4.6],
        "2YY=F": [4.5, 4.45, 4.4, 4.4, 4.45, 4.5, 4.5],
        "DX-Y.NYB": [100, 101, 102, 103, 104, 105, 106],
        "^VIX": [22, 21, 20, 19, 18.5, 18, 17.5],
        "BTC-USD": [50000, 50500, 51000, 51500, 52000, 52500, 53000],
        "SOXX": [200, 202, 204, 206, 208, 210, 212],
        "SPY": [500, 501, 502, 503, 504, 505, 506],
        "NVDA": [100, 102, 104, 106, 108, 110, 112],
        "AMD": [80, 81, 82, 83, 84, 85, 86],
        "AVGO": [900, 905, 910, 915, 920, 925, 930],
        "MSFT": [400, 402, 404, 406, 408, 410, 412],
        "AAPL": [200, 199, 201, 202, 203, 204, 205],
        "SMH": [250, 252, 254, 256, 258, 260, 262],
    }
    monkeypatch.setattr(macro, "_download_close_series", lambda symbol, period="14d": fixtures[symbol])
    monkeypatch.setattr(
        macro,
        "_fetch_catalysts",
        lambda _now: [
            {
                "date": "2026-05-15",
                "name": "US CPI",
                "importance": "high",
                "estimate": "0.3%",
                "previous": "0.2%",
                "source": "test",
            }
        ],
    )

    response = client.get("/api/macro/snapshot")

    assert response.status_code == 200
    body = response.json()
    assert body["indicator_order"] == macro.INDICATOR_ORDER
    assert set(body["indicators"]) == set(macro.INDICATOR_ORDER)
    assert body["indicators"]["spread_2s10s"]["value"] == pytest.approx(10.0)
    assert len(body["indicators"]["btc"]["spark"]) == 7
    assert body["indicators"]["next_fed_cpi"]["display"] == "2026-05-15 · US CPI"
    assert body["regime"]["label"] in {"risk_on", "neutral", "risk_off"}


def test_macro_snapshot_cache_avoids_repeated_downloads(client, monkeypatch):
    calls: list[str] = []

    def fake_series(symbol, period="14d"):
        calls.append(symbol)
        return [10, 11, 12, 13, 14, 15, 16]

    monkeypatch.setattr(macro, "_download_close_series", fake_series)
    monkeypatch.setattr(macro, "_fetch_catalysts", lambda _now: [])

    first = client.get("/api/macro/snapshot")
    second = client.get("/api/macro/snapshot")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cached"] is False
    assert second.json()["cached"] is True
    assert calls
    assert len(calls) < 20
