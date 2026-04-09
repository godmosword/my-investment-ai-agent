"""Shared LangGraph state and reducers for research workflow."""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict


def merge_raw_data(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Merge raw_data without mutating existing state objects."""
    if not left:
        return dict(right or {})
    if not right:
        return dict(left)
    return {**left, **right}


class ResearchGraphState(TypedDict):
    """Global state shared by all LangGraph nodes."""

    category: Literal["CRYPTO", "AI"]
    exclude_context: str
    price_context: str
    prev_recs_block: str
    agreed_regime: str | None
    recent_lessons: str
    use_fallback_llm: bool
    raw_data: Annotated[dict[str, Any], merge_raw_data]
    raw_news: list[dict[str, Any]]
    proposed_trades: list[dict[str, Any]]
    bull_arguments: list[str]
    bear_arguments: list[str]
    arbiter_summary: str
    research_depth: int
    max_research_depth: int
    needs_deep_dive: bool
    deep_dive_query: str
    final_report: dict[str, Any] | None
