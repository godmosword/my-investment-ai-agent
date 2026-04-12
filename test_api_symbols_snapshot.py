"""Tests for /api/symbols/{symbol}/snapshot endpoint."""

from fastapi.testclient import TestClient

from api import app


class _FakeQueryJob:
    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class _FakeBQClient:
    def query(self, sql: str):
        if "LIMIT 1" in sql and "ORDER BY timestamp DESC" in sql and "grok_summary" in sql:
            return _FakeQueryJob(
                [
                    {
                        "timestamp": "2026-04-12T00:00:00+00:00",
                        "dxy": 101.2,
                        "etf_flow_millions": 3.2,
                        "avg_risk_score": 2.8,
                        "mvrv_z_score": 1.4,
                        "sentiment_score": 0.12,
                        "sopr": 1.01,
                        "exchange_netflow": -220.0,
                        "regime_score": 2.7,
                        "grok_summary": "grok",
                        "gpt_summary": "gpt",
                    }
                ]
            )
        if "TIMESTAMP_SUB" in sql:
            return _FakeQueryJob(
                [
                    {
                        "timestamp": "2026-04-10T00:00:00+00:00",
                        "dxy": 100.9,
                        "etf_flow_millions": 2.0,
                        "avg_risk_score": 2.6,
                        "mvrv_z_score": 1.3,
                        "sentiment_score": 0.11,
                        "sopr": 1.0,
                        "exchange_netflow": -180.0,
                        "regime_score": 2.5,
                    },
                    {
                        "timestamp": "2026-04-11T00:00:00+00:00",
                        "dxy": 101.1,
                        "etf_flow_millions": 2.7,
                        "avg_risk_score": 2.7,
                        "mvrv_z_score": 1.35,
                        "sentiment_score": 0.115,
                        "sopr": 1.005,
                        "exchange_netflow": -200.0,
                        "regime_score": 2.6,
                    },
                ]
            )
        if "UPPER(asset) = 'BTC'" in sql:
            return _FakeQueryJob(
                [
                    {
                        "report_date": "2026-04-11",
                        "asset": "BTC",
                        "category": "CRYPTO",
                        "direction": "LONG",
                        "confidence": 88,
                        "narrative": "n1",
                        "trigger": "t1",
                        "invalidation": "i1",
                        "status": "OPEN",
                        "entry_price": 76000,
                        "target_price": 82000,
                        "stop_price": 72000,
                        "rr_ratio": 2.0,
                    },
                    {
                        "report_date": "2026-04-10",
                        "asset": "BTC",
                        "category": "CRYPTO",
                        "direction": "LONG",
                        "confidence": 82,
                        "narrative": "n2",
                        "trigger": "t2",
                        "invalidation": "i2",
                        "status": "OPEN",
                        "entry_price": 75000,
                        "target_price": 80000,
                        "stop_price": 71000,
                        "rr_ratio": 1.8,
                    },
                ]
            )
        return _FakeQueryJob([])


def test_symbol_snapshot_success(monkeypatch):
    monkeypatch.setattr("api._get_bq_client", lambda: _FakeBQClient())
    monkeypatch.setattr(
        "api._fetch_symbol_ohlc",
        lambda _symbol, days: [
            {"time": "2026-04-10", "open": 74000.0, "high": 76500.0, "low": 73000.0, "close": 75800.0}
        ],
    )
    client = TestClient(app)
    response = client.get("/api/symbols/btc/snapshot?days=30&recommendation_limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "BTC"
    assert payload["as_of"] == "2026-04-12T00:00:00+00:00"
    assert len(payload["history"]) == 2
    assert len(payload["recommendations"]) == 2
    assert payload["price_series"][0]["close"] == 75800.0
    assert payload["event_markers"][0]["time"] == "2026-04-10"
    assert payload["report_links"][0]["href"] == "/report/2026-04-11"
    assert payload["report_links"][0]["api_href"] == "/api/reports/2026-04-11"


def test_symbol_snapshot_rejects_bad_symbol():
    client = TestClient(app)
    response = client.get("/api/symbols/BTC$%^/snapshot")
    assert response.status_code == 400
    assert "Invalid symbol format" in response.text


def test_symbol_snapshot_bigquery_failure(monkeypatch):
    class _BoomClient:
        def query(self, _sql: str):
            raise RuntimeError("boom")

    monkeypatch.setattr("api._get_bq_client", lambda: _BoomClient())
    client = TestClient(app)
    response = client.get("/api/symbols/BTC/snapshot")
    assert response.status_code == 503
