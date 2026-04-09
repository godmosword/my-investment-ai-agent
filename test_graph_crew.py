from __future__ import annotations

import pytest

import graph.graph_nodes as graph_nodes
from graph.graph_crew import build_research_graph
from graph.graph_nodes import arbiter_node
from graph.graph_state import merge_raw_data


def _initial_state(category: str = "CRYPTO", max_depth: int = 2) -> dict:
    return {
        "category": category,
        "exclude_context": "",
        "price_context": "",
        "prev_recs_block": "",
        "agreed_regime": None,
        "recent_lessons": "test",
        "use_fallback_llm": False,
        "raw_data": {},
        "bull_arguments": [],
        "bear_arguments": [],
        "arbiter_summary": "",
        "research_depth": 0,
        "max_research_depth": max_depth,
        "needs_deep_dive": False,
        "deep_dive_query": "",
        "final_report": None,
    }


def test_merge_raw_data_is_non_mutating() -> None:
    left = {"a": 1, "nested": {"x": 1}}
    right = {"b": 2}
    merged = merge_raw_data(left, right)

    assert merged == {"a": 1, "nested": {"x": 1}, "b": 2}
    assert left == {"a": 1, "nested": {"x": 1}}
    assert right == {"b": 2}


def test_arbiter_skips_deep_dive_when_both_sides_have_numeric_anchors() -> None:
    state = _initial_state("CRYPTO", max_depth=2)
    state["raw_data"] = {"price": "BTC=100000"}
    state["bull_arguments"] = ["多方數據錨點：BTC 100000", "多方次要佐證：ETF 320"]
    state["bear_arguments"] = ["空方數據錨點：VIX 22", "空方次要佐證：Funding 0.01"]
    result = arbiter_node(state)
    assert result["needs_deep_dive"] is False


@pytest.mark.smoke
def test_graph_compile_and_invoke_smoke(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "0")
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")

    graph = build_research_graph()
    result = graph.invoke(_initial_state("CRYPTO", max_depth=1), config={"recursion_limit": 30})

    assert result["final_report"] is not None
    assert result["final_report"]["category"] == "CRYPTO"
    assert "arbiter_summary" in result["final_report"]


@pytest.mark.smoke
def test_graph_depth_guard_stops_infinite_loop(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "0")
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(
        graph_nodes,
        "_extract_numeric_lines",
        lambda *_args, **_kwargs: ["尚無可引用的客觀讀數，需補抓工具輸出。"],
    )

    graph = build_research_graph()
    result = graph.invoke(_initial_state("AI", max_depth=1), config={"recursion_limit": 30})

    assert result["research_depth"] == 1
    assert result["needs_deep_dive"] is False
    assert result["final_report"]["category"] == "AI"
    assert "deep_dive_round_1" in result.get("raw_data", {})
