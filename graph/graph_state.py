"""Shared LangGraph state and reducers for research workflow."""

from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict


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

    # ── Reviewer Loop (Phase 3.5) ─────────────────────────────────────────
    # All fields are NotRequired for backward compatibility with existing tests.
    graph_run_id: NotRequired[str]            # UUID per graph invocation; used in reviewer_log BQ
    trade_candidates: NotRequired[list[dict[str, Any]]]   # snapshot of picker output pre-review
    review_issues: NotRequired[list[dict[str, Any]]]      # current round failure reasons
    revision_count: NotRequired[int]          # how many times picker was retried with feedback
    review_history: NotRequired[list[dict[str, Any]]]     # per-round audit trail for BQ
    trade_watch_final: NotRequired[list[dict[str, Any]]]  # approved trade list after review
    degraded: NotRequired[bool]               # True if hard cap hit; trades retained with warning
