"""Phase 1: ``tools`` package + ``tools_legacy`` shim (Alt B scaffolding)."""

import pytest


@pytest.mark.smoke
def test_tools_package_reexports_legacy_tools():
    import tools

    assert callable(getattr(tools, "fear_greed_tool", None))
    assert callable(getattr(tools, "newsapi_tool", None))


@pytest.mark.smoke
def test_tools_exposes_submodules():
    import tools

    assert hasattr(tools, "base")
    assert hasattr(tools, "market")


@pytest.mark.smoke
def test_market_fixture_empty_when_mock_off(monkeypatch):
    monkeypatch.delenv("MOCK_APIS", raising=False)
    from tools.market import market_fixture_dict

    assert market_fixture_dict() == {}


@pytest.mark.smoke
def test_market_fixture_loads_when_mock_on(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "1")
    from tools.market import market_fixture_dict

    d = market_fixture_dict()
    assert d.get("btc_spot_usd") == 66544.59
    assert d.get("fixture_version") == 1


@pytest.mark.smoke
def test_mock_apis_enabled_truthy(monkeypatch):
    monkeypatch.setenv("MOCK_APIS", "1")
    from tools.base import mock_apis_enabled

    assert mock_apis_enabled() is True
