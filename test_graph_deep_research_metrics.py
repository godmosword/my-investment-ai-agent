"""LG-3 / LG-1: deep_research bind_tools path records scratchpad metrics (mocked LLM)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

import graph.graph_nodes as graph_nodes
from graph.graph_nodes import _deep_research_with_bound_tools


class _FakeTool:
    name = "fake_metrics_tool"

    def invoke(self, _args):
        return "stub-tool-output"


@pytest.mark.smoke
def test_deep_research_tool_llm_emits_scratchpad_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[dict] = []

    def _capture(payload: dict) -> None:
        captured.append(dict(payload))

    ft = _FakeTool()
    monkeypatch.setattr(graph_nodes, "RESEARCH_TOOLS", [ft])

    rounds: list[AIMessage] = [
        AIMessage(
            content="",
            tool_calls=[{"name": ft.name, "id": "tc1", "args": {"x": 1}}],
        ),
        AIMessage(content="綜合結論：測試通過。"),
    ]

    def _fake_invoke(_messages):
        return rounds.pop(0) if rounds else AIMessage(content="fallback")

    fake_llm = MagicMock()
    fake_bound = MagicMock()
    fake_bound.invoke.side_effect = _fake_invoke
    fake_llm.bind_tools.return_value = fake_bound

    monkeypatch.setattr(graph_nodes, "_get_debate_llm", lambda: fake_llm)

    with patch("scratchpad.append_graph_deep_research_metrics", _capture):
        out = _deep_research_with_bound_tools("unit probe")

    assert "stub-tool-output" in out
    assert "測試通過" in out
    assert len(captured) == 1
    assert captured[0].get("tool_calls_total", 0) >= 1
    assert captured[0].get("elapsed_ms", 0) >= 0
    assert captured[0].get("finish_kind") == "tools_and_synthesis"
    assert captured[0].get("unknown_tool_hits", -1) == 0
