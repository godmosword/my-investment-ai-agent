"""RESEARCH_TOOLS surface checks (no live LLM)."""

from __future__ import annotations

import pytest

import graph.graph_tools as graph_tools_mod
from graph.graph_tools import RESEARCH_TOOLS, fetch_onchain_metrics_btc


@pytest.mark.smoke
def test_research_tools_includes_onchain() -> None:
    names = {t.name for t in RESEARCH_TOOLS}
    assert "fetch_onchain_metrics_btc" in names


@pytest.mark.smoke
def test_fetch_onchain_metrics_delegates_to_legacy(monkeypatch) -> None:
    calls: list[str] = []

    def fake_run(*_a, **_k):
        calls.append("run")
        return "stub-onchain"

    monkeypatch.setattr(
        graph_tools_mod,
        "onchain_metrics_tool",
        type("T", (), {"run": staticmethod(fake_run)})(),
    )
    out = fetch_onchain_metrics_btc.invoke({})
    assert out == "stub-onchain"
    assert calls == ["run"]
