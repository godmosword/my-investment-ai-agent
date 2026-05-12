"""Tests for GET /api/analysis/{symbol} — M6 analysis bundle (Q32)."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from api import app


@pytest.fixture()
def client():
    return TestClient(app)


def _mock_quote(symbol):
    return {"symbol": symbol, "last": 100.5, "as_of": "2026-04-14", "change_pct_1d": 1.2, "currency": "USD", "error": None, "cached": False}


def _mock_snapshot(symbol):
    return {
        "symbol": symbol,
        "source": "bigquery",
        "as_of": "2026-04-14T00:00:00+00:00",
        "price_series": [],
        "recommendations": [],
        "latest_metrics": {},
    }


def test_analysis_bundle_structure(client):
    with (
        patch("api.fetch_symbol_quote", return_value=_mock_quote("AAPL")),
        patch("api.build_symbol_snapshot", return_value=_mock_snapshot("AAPL")),
        patch("api._get_bq_client", return_value=MagicMock()),
    ):
        r = client.get("/api/analysis/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAPL"
    assert "quote" in body
    assert "snapshot" in body
    assert "snapshot_error" in body


def test_analysis_bundle_quote_fields(client):
    with (
        patch("api.fetch_symbol_quote", return_value=_mock_quote("NVDA")),
        patch("api.build_symbol_snapshot", return_value=_mock_snapshot("NVDA")),
        patch("api._get_bq_client", return_value=MagicMock()),
    ):
        r = client.get("/api/analysis/NVDA")
    assert r.status_code == 200
    body = r.json()
    assert body["quote"]["symbol"] == "NVDA"
    assert body["quote"]["last"] == 100.5


def test_analysis_bundle_invalid_symbol(client):
    """Non-alphanumeric symbols must return 400."""
    r = client.get("/api/analysis/INVALID!!!")
    assert r.status_code == 400


def test_analysis_bundle_bq_failure_degrades_gracefully(client):
    """If BigQuery fails, snapshot_error is populated but response is still 200."""
    with (
        patch("api.fetch_symbol_quote", return_value=_mock_quote("BTC")),
        patch("api._get_bq_client", side_effect=Exception("BQ unavailable")),
    ):
        r = client.get("/api/analysis/BTC")
    assert r.status_code == 200
    body = r.json()
    assert body["snapshot"] is None
    assert body["snapshot_error"] is not None
    assert "BQ unavailable" in body["snapshot_error"]


def test_analysis_bundle_skip_bigquery(client, monkeypatch):
    """SKIP_BIGQUERY=1 must not crash the endpoint."""
    monkeypatch.setenv("SKIP_BIGQUERY", "1")
    with patch("api.fetch_symbol_quote", return_value=_mock_quote("SPY")):
        r = client.get("/api/analysis/SPY")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "SPY"
