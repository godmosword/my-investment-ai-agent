from __future__ import annotations

import threading

import pytest

import graph.graph_nodes as graph_nodes
from graph.graph_crew import build_research_graph, get_compiled_research_graph, run_langgraph_category
from graph.graph_nodes import (
    arbiter_node,
    deep_research_node,
    final_formatter_node,
    news_scraper_node,
    trade_picker_node,
)
from graph.graph_state import ResearchGraphState
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
        "raw_news": [],
        "proposed_trades": [],
        "review_issues": [],
        "review_history": [],
        "revision_count": 0,
        "review_passed": True,
        "degraded": False,
        "review_warnings": [],
        "bull_arguments": [],
        "bear_arguments": [],
        "arbiter_summary": "",
        "research_depth": 0,
        "max_research_depth": max_depth,
        "needs_deep_dive": False,
        "deep_dive_query": "",
        "final_report": None,
    }


class _FakeFormatterLLM:
    last_inputs = None

    def with_structured_output(self, model_cls):
        def _runner(_inputs):
            _FakeFormatterLLM.last_inputs = _inputs
            if model_cls.__name__ == "CryptoFormatterNarrative":
                return model_cls(
                    narrative_of_day="主敘事：風險偏好回升但保留防守。",
                    signal_conflict_summary="空方：宏觀壓力未退｜多方：資金面改善延續。",
                    pick_reason="以風險回報比優先，偏向等待確認後分批。",
                    risk_budget_summary="中性偏保守，先小倉位測試。",
                    macro_framework_lines=["美債利率回落，壓力暫緩。"],
                )
            return model_cls(
                signal_conflict_summary="空方：估值高｜多方：基本面撐住。",
                pick_reason="選擇高流動性標的，控制回撤。",
                macro_bridge_lines=["利率路徑仍是 AI 權值核心變數。"],
            )

        return _runner


def test_get_compiled_research_graph_is_per_thread() -> None:
    """main.py 雙 category ThreadPool 並行時，各 thread 應有獨立 compiled graph。"""
    results: dict[str, int] = {}

    def _worker(key: str) -> None:
        results[key] = id(get_compiled_research_graph())

    t1 = threading.Thread(target=_worker, args=("a",))
    t2 = threading.Thread(target=_worker, args=("b",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    assert results["a"] != results["b"]


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
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())

    graph = build_research_graph()
    result = graph.invoke(_initial_state("CRYPTO", max_depth=1), config={"recursion_limit": 30})

    assert result["final_report"] is not None
    assert result["final_report"]["narrative_of_day"]
    assert result["final_report"]["signal_conflict_summary"]
    assert result["final_report"]["dashboard"]
    assert result["final_report"]["market"]["regime"] in {"risk_on", "risk_off", "neutral"}


@pytest.mark.smoke
def test_graph_depth_guard_stops_infinite_loop(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "0")
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())
    monkeypatch.setattr(
        graph_nodes,
        "_extract_numeric_lines",
        lambda *_args, **_kwargs: ["尚無可引用的客觀讀數，需補抓工具輸出。"],
    )

    graph = build_research_graph()
    result = graph.invoke(_initial_state("AI", max_depth=1), config={"recursion_limit": 30})

    assert result["research_depth"] == 1
    assert result["needs_deep_dive"] is False
    assert result["final_report"]["pick_reason"]
    assert result["final_report"]["signal_conflict_summary"]
    assert "deep_dive_round_1" in result.get("raw_data", {})


@pytest.mark.smoke
def test_deep_research_deterministic_includes_prediction_probe(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "1")
    monkeypatch.setenv("GRAPH_DEEP_RESEARCH_TOOL_LLM", "0")

    class _FakeReg:
        def get_snapshot(self, key: str, *args, **kwargs):
            return f"stub:{key}"

    monkeypatch.setattr(graph_nodes, "_tool_registry", lambda: _FakeReg())

    state = _initial_state("CRYPTO", max_depth=2)
    state["needs_deep_dive"] = True
    state["deep_dive_query"] = "probe"
    state["research_depth"] = 0

    out = deep_research_node(state)
    blob = out["raw_data"]["deep_dive_round_1"]
    assert "deep_prediction_probe" in blob
    assert "stub:prediction_markets_tool" in blob


def test_final_formatter_native_assembles_schema(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())
    state: ResearchGraphState = _initial_state("CRYPTO", max_depth=1)
    state["agreed_regime"] = None
    state["arbiter_summary"] = "多空分歧收斂，等待確認。"
    state["bull_arguments"] = ["多方數據錨點：ETF 淨流入 320M"]
    state["bear_arguments"] = ["空方數據錨點：VIX 仍在高檔"]
    state["raw_data"] = {"regime_scorecard": "【今日市場模式】risk_on（+4/6）", "price": "BTC=102000"}

    result = final_formatter_node(state)
    payload = result["final_report"]

    assert payload["market"]["regime"] == "risk_on"
    assert payload["market"]["score_suffix"] == "（+4/6）"
    assert isinstance(payload["dashboard"], list) and payload["dashboard"]
    assert payload["news"] == []
    assert payload["trade_legs"] == []


def test_final_formatter_maps_raw_news_and_proposed_trades(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())
    state: ResearchGraphState = _initial_state("CRYPTO", max_depth=1)
    state["agreed_regime"] = "neutral"
    state["price_context"] = "BTC=100000"
    state["raw_data"] = {"regime_scorecard": "【今日市場模式】neutral（+0/6）", "price": "BTC=100000"}
    state["raw_news"] = [
        {
            "title": "ETF flows stabilize after volatility spike",
            "url": "https://example.com/news-1",
            "source": "Reuters",
            "published_at": "2026-04-09T01:00:00Z",
            "feed": "newsapi",
        }
    ]
    state["proposed_trades"] = [
        {
            "asset": "BTC",
            "direction": "LONG",
            "star_rating": 2,
            "thesis_one_liner": "資金流穩定，等待突破延續。",
        }
    ]

    payload = final_formatter_node(state)["final_report"]
    assert len(payload["news"]) == 1
    assert len(payload["trade_legs"]) == 1
    assert len(payload["qsrec"]) == 1


def test_final_formatter_passes_structured_packet_to_prompt(monkeypatch) -> None:
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())
    state: ResearchGraphState = _initial_state("AI", max_depth=1)
    state["agreed_regime"] = "neutral"
    state["arbiter_summary"] = "主編等待更強催化。"
    state["raw_data"] = {"regime_scorecard": "【今日市場模式】neutral（+0/6）", "ai_sector_market": "NVDA 120.5"}
    state["raw_news"] = [
        {
            "title": "AI capex outlook remains firm",
            "source": "Reuters",
            "published_at": "2026-04-09T01:00:00Z",
        }
    ]
    state["proposed_trades"] = [
        {
            "asset": "NVDA",
            "direction": "LONG",
            "star_rating": 2,
            "thesis_one_liner": "資本支出預期支撐高流動性龍頭。",
        }
    ]

    final_formatter_node(state)

    prompt_text = _FakeFormatterLLM.last_inputs.messages[-1].content
    assert '"raw_news"' in prompt_text
    assert '"proposed_trades"' in prompt_text
    assert "AI capex outlook remains firm" in prompt_text
    assert "NVDA" in prompt_text


def test_news_scraper_returns_empty_when_tools_disabled(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "0")
    result = news_scraper_node(_initial_state("CRYPTO", max_depth=1))
    assert result["raw_news"] == []


def test_news_scraper_marks_freshness_whitelist(monkeypatch) -> None:
    monkeypatch.setenv("NEWS_FRESHNESS_SOURCE_WHITELIST", "REUTERS")
    monkeypatch.setattr(
        graph_nodes,
        "_fetch_parsed_news_source",
        lambda name, _tool_key, _kwargs: (
            name,
            [
                {
                    "title": "ETF flows stabilize after volatility spike",
                    "url": "https://example.com/news-1",
                    "source": "Reuters",
                    "published_at": "2026-04-09T01:00:00Z",
                }
            ],
        ),
    )
    result = news_scraper_node(_initial_state("CRYPTO", max_depth=1))
    assert result["raw_news"][0]["source"] == "Reuters"
    assert result["raw_news"][0]["source_whitelisted_for_freshness"] is True


def test_trade_picker_respects_env_off(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_LLM_TRADE_PICKER", "0")
    state = _initial_state("AI", max_depth=1)
    state["arbiter_summary"] = "test"
    state["agreed_regime"] = "neutral"
    result = trade_picker_node(state)
    assert result["proposed_trades"] == []


def test_run_langgraph_category_smoke_with_mocked_formatter(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_ENABLE_TOOL_CALLS", "0")
    monkeypatch.setenv("LANGGRAPH_SKIP_FORMATTER_CREW", "1")
    monkeypatch.setattr(graph_nodes, "_get_formatter_llm", lambda: _FakeFormatterLLM())

    section = run_langgraph_category(
        category="AI",
        exclude_context="",
        price_context="",
        prev_recs_block="",
        agreed_regime="neutral",
        recent_lessons="test",
        use_fallback_llm=False,
        max_research_depth=1,
    )
    assert section.pick_reason
    assert section.signal_conflict_summary
    assert section.dashboard
