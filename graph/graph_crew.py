"""Graph compiler and runtime wrapper for LangGraph research engine."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from graph.graph_nodes import (
    arbiter_node,
    bear_agent_node,
    bull_agent_node,
    data_gatherer_node,
    deep_research_node,
    final_formatter_node,
    news_scraper_node,
    trade_picker_node,
)
from graph.graph_state import ResearchGraphState
from schemas import AISection, CryptoSection


RouteKey = Literal["deep_research", "news_scraper"]


def _route_after_arbiter(state: ResearchGraphState) -> RouteKey:
    if state.get("needs_deep_dive", False):
        return "deep_research"
    return "news_scraper"


def build_research_graph() -> Any:
    """Build and compile the LangGraph state machine."""
    builder = StateGraph(ResearchGraphState)
    builder.add_node("data_gatherer", data_gatherer_node)
    builder.add_node("bull_agent", bull_agent_node)
    builder.add_node("bear_agent", bear_agent_node)
    builder.add_node("arbiter", arbiter_node)
    builder.add_node("deep_research", deep_research_node)
    builder.add_node("news_scraper", news_scraper_node)
    builder.add_node("trade_picker", trade_picker_node)
    builder.add_node("final_formatter", final_formatter_node)

    builder.add_edge(START, "data_gatherer")
    builder.add_edge("data_gatherer", "bull_agent")
    builder.add_edge("data_gatherer", "bear_agent")
    builder.add_edge("bull_agent", "arbiter")
    builder.add_edge("bear_agent", "arbiter")

    builder.add_conditional_edges(
        "arbiter",
        _route_after_arbiter,
        {
            "deep_research": "deep_research",
            "news_scraper": "news_scraper",
        },
    )
    builder.add_edge("deep_research", "bull_agent")
    builder.add_edge("deep_research", "bear_agent")
    builder.add_edge("news_scraper", "trade_picker")
    builder.add_edge("trade_picker", "final_formatter")
    builder.add_edge("final_formatter", END)

    return builder.compile()


@lru_cache(maxsize=1)
def get_compiled_research_graph() -> Any:
    """Singleton graph to reduce compile overhead in production pipeline."""
    return build_research_graph()


def run_langgraph_category(
    *,
    category: Literal["CRYPTO", "AI"],
    exclude_context: str,
    price_context: str,
    prev_recs_block: str,
    agreed_regime: str | None,
    recent_lessons: str,
    use_fallback_llm: bool = False,
    max_research_depth: int = 2,
) -> CryptoSection | AISection:
    """Run graph for a single category and validate output with Pydantic schema."""
    graph = get_compiled_research_graph()
    initial_state: ResearchGraphState = {
        "category": category,
        "exclude_context": exclude_context,
        "price_context": price_context,
        "prev_recs_block": prev_recs_block,
        "agreed_regime": agreed_regime,
        "recent_lessons": recent_lessons,
        "use_fallback_llm": use_fallback_llm,
        "raw_data": {},
        "raw_news": [],
        "proposed_trades": [],
        "bull_arguments": [],
        "bear_arguments": [],
        "arbiter_summary": "",
        "research_depth": 0,
        "max_research_depth": max(1, int(max_research_depth)),
        "needs_deep_dive": False,
        "deep_dive_query": "",
        "final_report": None,
    }

    result = graph.invoke(initial_state, config={"recursion_limit": 40})
    payload = result.get("final_report")
    if payload is None:
        raise RuntimeError("LangGraph final_report is missing")

    if category == "CRYPTO":
        return CryptoSection.model_validate(payload)
    return AISection.model_validate(payload)
