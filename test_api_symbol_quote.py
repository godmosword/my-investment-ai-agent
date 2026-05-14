"""Tests for GET /api/symbols/{symbol}/quote (M3 lightweight quote)."""

from fastapi.testclient import TestClient

from api import app


def test_symbol_quote_success(monkeypatch):
    monkeypatch.setattr(
        "api_routers.symbols.fetch_symbol_quote",
        lambda _sym: {
            "symbol": "BTC",
            "as_of": "2026-04-12T00:00:00Z",
            "source": "yfinance",
            "underlying_symbol": "BTC-USD",
            "last": 95000.5,
            "currency": "USD",
            "change_pct_1d": 1.25,
            "error": None,
            "cached": False,
        },
    )
    client = TestClient(app)
    r = client.get("/api/symbols/BTC/quote")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "BTC"
    assert body["last"] == 95000.5
    assert body["change_pct_1d"] == 1.25
    assert body["data_provenance"]["price"]["source"] == "yfinance"
    assert body["data_provenance"]["price"]["ttl_seconds"] == 45


def test_symbol_quote_503_when_unavailable(monkeypatch):
    monkeypatch.setattr(
        "api_routers.symbols.fetch_symbol_quote",
        lambda _sym: {
            "symbol": "ZZZ",
            "as_of": "2026-04-12T00:00:00Z",
            "source": "yfinance",
            "underlying_symbol": "ZZZ",
            "last": None,
            "currency": None,
            "change_pct_1d": None,
            "error": "no_price_data",
            "cached": False,
        },
    )
    client = TestClient(app)
    r = client.get("/api/symbols/ZZZ/quote")
    assert r.status_code == 503


def test_symbol_quote_rejects_bad_symbol():
    client = TestClient(app)
    r = client.get("/api/symbols/BAD%20SYM/quote")
    assert r.status_code == 400
