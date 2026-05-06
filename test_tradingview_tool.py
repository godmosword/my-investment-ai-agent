import importlib


def test_tradingview_mock_fixture(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "1")
    import tools.tradingview as tv

    importlib.reload(tv)
    out = tv.tradingview_summary("BTC")
    assert "mock_tradingview" in out
    assert "BUY" in out


def test_tradingview_disabled_without_fallback(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "0")
    monkeypatch.setenv("TRADINGVIEW_MCP_ENABLED", "0")
    monkeypatch.setenv("TRADINGVIEW_FALLBACK_YFINANCE", "0")
    import tools.tradingview as tv

    importlib.reload(tv)
    assert tv.tradingview_summary("BTC").startswith("[DATA_MISSING:tradingview_disabled]")
