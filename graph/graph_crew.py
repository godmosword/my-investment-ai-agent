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
    degrade_node,
    final_formatter_node,
    llm_reviewer_node,
    news_scraper_node,
    python_validate_node,
    trade_picker_node,
)
from graph.graph_state import ResearchGraphState
from schemas import AISection, CryptoSection


RouteKey = Literal["deep_research", "news_scraper"]


def _route_after_arbiter(state: ResearchGraphState) -> RouteKey:
    if state.get("needs_deep_dive", False):
        return "deep_research"
    return "news_scraper"


def _route_after_python_validate(
    state: ResearchGraphState,
) -> Literal["llm_reviewer", "trade_picker", "degrade"]:
    """Pass → llm_reviewer; fail+retries_left → trade_picker; hard cap → degrade."""
    if not state.get("review_issues"):
        return "llm_reviewer"
    if int(state.get("revision_count") or 0) < 2:
        return "trade_picker"
    return "degrade"


def _route_after_llm_reviewer(
    state: ResearchGraphState,
) -> Literal["final_formatter", "trade_picker", "degrade"]:
    """Pass → final_formatter; fail+retries_left → trade_picker; hard cap → degrade."""
    if not state.get("review_issues"):
        return "final_formatter"
    if int(state.get("revision_count") or 0) < 2:
        return "trade_picker"
    return "degrade"


def build_research_graph() -> Any:
    """Build and compile the LangGraph state machine.

    Reviewer loop (GRAPH_LLM_REVIEWER=1):
        trade_picker → python_validate → llm_reviewer → final_formatter
                              ↓ fail               ↓ fail
                           trade_picker ← retry (revision_count < 2)
                           degrade_node ← hard cap (revision_count >= 2)
    When reviewer is disabled, python_validate and llm_reviewer are transparent
    pass-throughs so the graph topology stays constant regardless of the env flag.
    """
    builder = StateGraph(ResearchGraphState)
    builder.add_node("data_gatherer", data_gatherer_node)
    builder.add_node("bull_agent", bull_agent_node)
    builder.add_node("bear_agent", bear_agent_node)
    builder.add_node("arbiter", arbiter_node)
    builder.add_node("deep_research", deep_research_node)
    builder.add_node("news_scraper", news_scraper_node)
    builder.add_node("trade_picker", trade_picker_node)
    builder.add_node("python_validate", python_validate_node)
    builder.add_node("llm_reviewer", llm_reviewer_node)
    builder.add_node("degrade", degrade_node)
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

    # Reviewer loop replaces the former direct trade_picker → final_formatter edge.
    builder.add_edge("trade_picker", "python_validate")
    builder.add_conditional_edges(
        "python_validate",
        _route_after_python_validate,
        {
            "llm_reviewer": "llm_reviewer",
            "trade_picker": "trade_picker",
            "degrade": "degrade",
        },
    )
    builder.add_conditional_edges(
        "llm_reviewer",
        _route_after_llm_reviewer,
        {
            "final_formatter": "final_formatter",
            "trade_picker": "trade_picker",
            "degrade": "degrade",
        },
    )
    builder.add_edge("degrade", "final_formatter")
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
    import uuid

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
        # Reviewer loop initial values
        "graph_run_id": str(uuid.uuid4()),
        "trade_candidates": [],
        "review_issues": [],
        "revision_count": 0,
        "review_history": [],
        "trade_watch_final": [],
        "degraded": False,
    }

    result = graph.invoke(initial_state, config={"recursion_limit": 40})
    payload = result.get("final_report")
    if payload is None:
        raise RuntimeError("LangGraph final_report is missing")

    if category == "CRYPTO":
        return CryptoSection.model_validate(payload)
    return AISection.model_validate(payload)
