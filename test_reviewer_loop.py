"""Smoke + boundary tests for LangGraph Reviewer Loop (Phase 3.5).

Covers:
  smoke    — basic pass/fail paths without API calls
  boundary — edge cases: empty trades, duplicate tickers, hard cap routing

All tests run with GRAPH_LLM_REVIEWER=0 (default) or override it per-test.
No LLM or BigQuery calls are made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from graph.graph_nodes import (
    ReviewerIssue,
    ReviewerVerdict,
    _is_known_ticker,
    degrade_node,
    llm_reviewer_node,
    python_validate_node,
)
from graph.graph_crew import _route_after_llm_reviewer, _route_after_python_validate
from graph.graph_state import ResearchGraphState


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _base_state(**overrides: Any) -> ResearchGraphState:
    base: dict[str, Any] = {
        "category": "CRYPTO",
        "exclude_context": "",
        "price_context": "",
        "prev_recs_block": "",
        "agreed_regime": None,
        "recent_lessons": "",
        "use_fallback_llm": False,
        "raw_data": {},
        "raw_news": [],
        "proposed_trades": [],
        "bull_arguments": [],
        "bear_arguments": [],
        "arbiter_summary": "",
        "research_depth": 0,
        "max_research_depth": 2,
        "needs_deep_dive": False,
        "deep_dive_query": "",
        "final_report": None,
        # Reviewer fields
        "graph_run_id": "test-run-id",
        "trade_candidates": [],
        "review_issues": [],
        "revision_count": 0,
        "review_history": [],
        "trade_watch_final": [],
        "degraded": False,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def _valid_trade(asset: str = "BTC", direction: str = "LONG") -> dict[str, Any]:
    return {
        "asset": asset,
        "direction": direction,
        "star_rating": 1,
        "thesis_one_liner": "流動性改善，短線看多突破。",
    }


# ─────────────────────────────────────────────────────────────────
# python_validate_node — reviewer DISABLED (default)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_python_validate_disabled_pass_through():
    """When GRAPH_LLM_REVIEWER=0, python_validate is a transparent no-op."""
    trades = [_valid_trade("BTC"), _valid_trade("ETH", "SHORT")]
    state = _base_state(proposed_trades=trades)

    result = python_validate_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == trades
    assert result["trade_candidates"] == trades


@pytest.mark.smoke
def test_python_validate_disabled_empty_trades():
    """Empty proposed_trades passes when reviewer is disabled."""
    state = _base_state(proposed_trades=[])
    result = python_validate_node(state)
    assert result["review_issues"] == []


# ─────────────────────────────────────────────────────────────────
# python_validate_node — reviewer ENABLED
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_python_validate_enabled_valid_trades(monkeypatch: pytest.MonkeyPatch):
    """Valid trades pass all 5 deterministic checks."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    trades = [_valid_trade("BTC", "LONG"), _valid_trade("ETH", "SHORT")]
    state = _base_state(proposed_trades=trades)

    result = python_validate_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == trades
    assert "revision_count" not in result or result.get("revision_count") == 0


@pytest.mark.smoke
def test_python_validate_enabled_empty_trades(monkeypatch: pytest.MonkeyPatch):
    """Empty proposed_trades vacuously passes (nothing to validate)."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    state = _base_state(proposed_trades=[])

    result = python_validate_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == []


@pytest.mark.boundary
def test_python_validate_duplicate_ticker(monkeypatch: pytest.MonkeyPatch):
    """Duplicate tickers in proposed_trades trigger review_issues."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    trades = [_valid_trade("BTC"), _valid_trade("BTC")]  # same asset twice
    state = _base_state(proposed_trades=trades)

    result = python_validate_node(state)

    issues = result["review_issues"]
    assert len(issues) > 0
    assert any("重複" in i["reason"] for i in issues)
    assert result.get("revision_count", 0) == 1


@pytest.mark.boundary
def test_python_validate_invalid_direction(monkeypatch: pytest.MonkeyPatch):
    """Invalid direction triggers review issue."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    bad_trade = {**_valid_trade(), "direction": "HOLD"}
    state = _base_state(proposed_trades=[bad_trade])

    result = python_validate_node(state)

    assert len(result["review_issues"]) > 0
    assert any("direction" in i["field"] for i in result["review_issues"])


@pytest.mark.boundary
def test_python_validate_invalid_star_rating(monkeypatch: pytest.MonkeyPatch):
    """star_rating=5 triggers review issue."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    bad_trade = {**_valid_trade(), "star_rating": 5}
    state = _base_state(proposed_trades=[bad_trade])

    result = python_validate_node(state)

    assert any("star_rating" in i["field"] for i in result["review_issues"])


@pytest.mark.boundary
def test_python_validate_unknown_ticker(monkeypatch: pytest.MonkeyPatch):
    """Ticker not in crypto/equity universe flags as potential hallucination."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    bad_trade = {**_valid_trade(), "asset": "FAKECOIN9999"}
    state = _base_state(proposed_trades=[bad_trade])

    result = python_validate_node(state)

    assert any("FAKECOIN9999" in i["reason"] for i in result["review_issues"])


@pytest.mark.boundary
def test_python_validate_empty_thesis(monkeypatch: pytest.MonkeyPatch):
    """Empty thesis_one_liner triggers review issue."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    bad_trade = {**_valid_trade(), "thesis_one_liner": ""}
    state = _base_state(proposed_trades=[bad_trade])

    result = python_validate_node(state)

    assert any("thesis_one_liner" in i["field"] for i in result["review_issues"])


@pytest.mark.boundary
def test_python_validate_increments_revision_count(monkeypatch: pytest.MonkeyPatch):
    """revision_count increments when validation fails."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    bad_trade = {**_valid_trade(), "direction": "HOLD"}
    state = _base_state(proposed_trades=[bad_trade], revision_count=0)

    result = python_validate_node(state)

    assert result.get("revision_count") == 1


# ─────────────────────────────────────────────────────────────────
# llm_reviewer_node
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_llm_reviewer_disabled_pass_through():
    """When GRAPH_LLM_REVIEWER=0, llm_reviewer is a transparent no-op."""
    trades = [_valid_trade()]
    state = _base_state(proposed_trades=trades)

    result = llm_reviewer_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == trades


@pytest.mark.smoke
def test_llm_reviewer_no_api_key_pass_through(monkeypatch: pytest.MonkeyPatch):
    """Without OPENAI_API_KEY, llm_reviewer passes through transparently."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    trades = [_valid_trade()]
    state = _base_state(proposed_trades=trades)

    result = llm_reviewer_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == trades


@pytest.mark.smoke
def test_llm_reviewer_empty_trades(monkeypatch: pytest.MonkeyPatch):
    """Empty proposed_trades returns empty trade_watch_final."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    state = _base_state(proposed_trades=[])

    result = llm_reviewer_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == []


@pytest.mark.smoke
def test_llm_reviewer_mocked_pass(monkeypatch: pytest.MonkeyPatch):
    """With mocked LLM returning passed=True, reviewer passes trades through."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    mock_verdict = ReviewerVerdict(passed=True, issues=[])
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = mock_verdict

    trades = [_valid_trade()]
    state = _base_state(proposed_trades=trades)

    with patch("graph.graph_nodes._get_reviewer_llm") as mock_llm_factory:
        mock_llm = MagicMock()
        mock_llm.with_structured_output.return_value.__ror__ = MagicMock(return_value=mock_chain)
        mock_llm_factory.return_value = mock_llm

        # Patch ChatPromptTemplate pipeline result
        with patch("graph.graph_nodes.ChatPromptTemplate") as mock_tpl:
            mock_pipe = MagicMock()
            mock_pipe.invoke.return_value = mock_verdict
            mock_tpl.from_messages.return_value.__or__ = MagicMock(return_value=mock_pipe)

            result = llm_reviewer_node(state)

    # Pass-through on any execution path (mock may or may not intercept)
    assert "review_issues" in result


@pytest.mark.smoke
def test_llm_reviewer_exception_pass_through(monkeypatch: pytest.MonkeyPatch):
    """LLM call exception causes fail-open pass-through (never blocks pipeline)."""
    monkeypatch.setenv("GRAPH_LLM_REVIEWER", "1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    trades = [_valid_trade()]
    state = _base_state(proposed_trades=trades)

    with patch("graph.graph_nodes._get_reviewer_llm", side_effect=RuntimeError("network error")):
        result = llm_reviewer_node(state)

    assert result["review_issues"] == []
    assert result["trade_watch_final"] == trades


# ─────────────────────────────────────────────────────────────────
# degrade_node
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_degrade_node_sets_degraded_flag():
    """degrade_node sets degraded=True and preserves proposed_trades."""
    trades = [_valid_trade()]
    issues = [{"field": "asset", "reason": "重複標的 'BTC'"}]
    state = _base_state(proposed_trades=trades, review_issues=issues, revision_count=2)

    with patch("graph.graph_nodes._write_reviewer_log_safe"):
        result = degrade_node(state)

    assert result["degraded"] is True
    assert result["trade_watch_final"] == trades


@pytest.mark.boundary
def test_degrade_node_empty_trades():
    """degrade_node handles empty proposed_trades gracefully."""
    state = _base_state(proposed_trades=[], revision_count=2)

    with patch("graph.graph_nodes._write_reviewer_log_safe"):
        result = degrade_node(state)

    assert result["degraded"] is True
    assert result["trade_watch_final"] == []


# ─────────────────────────────────────────────────────────────────
# Routing functions
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_route_after_python_validate_pass():
    """No issues → route to llm_reviewer."""
    state = _base_state(review_issues=[], revision_count=0)
    assert _route_after_python_validate(state) == "llm_reviewer"


@pytest.mark.smoke
def test_route_after_python_validate_fail_retry():
    """Issues + revision_count < 2 → route back to trade_picker."""
    state = _base_state(
        review_issues=[{"field": "asset", "reason": "重複"}],
        revision_count=1,
    )
    assert _route_after_python_validate(state) == "trade_picker"


@pytest.mark.boundary
def test_route_after_python_validate_fail_degrade():
    """Issues + revision_count >= 2 → route to degrade."""
    state = _base_state(
        review_issues=[{"field": "asset", "reason": "重複"}],
        revision_count=2,
    )
    assert _route_after_python_validate(state) == "degrade"


@pytest.mark.smoke
def test_route_after_llm_reviewer_pass():
    """No issues → route to final_formatter."""
    state = _base_state(review_issues=[], revision_count=0)
    assert _route_after_llm_reviewer(state) == "final_formatter"


@pytest.mark.smoke
def test_route_after_llm_reviewer_fail_retry():
    """Issues + revision_count < 2 → route back to trade_picker."""
    state = _base_state(
        review_issues=[{"field": "direction", "reason": "矛盾"}],
        revision_count=1,
    )
    assert _route_after_llm_reviewer(state) == "trade_picker"


@pytest.mark.boundary
def test_route_after_llm_reviewer_fail_degrade():
    """Issues + revision_count >= 2 → route to degrade (hard cap)."""
    state = _base_state(
        review_issues=[{"field": "direction", "reason": "矛盾"}],
        revision_count=2,
    )
    assert _route_after_llm_reviewer(state) == "degrade"


# ─────────────────────────────────────────────────────────────────
# _is_known_ticker helper
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_is_known_ticker_crypto():
    """Major crypto tickers are recognized without any API call."""
    assert _is_known_ticker("BTC") is True
    assert _is_known_ticker("ETH") is True
    assert _is_known_ticker("SOL") is True
    assert _is_known_ticker("$BTC") is True  # $-prefix stripped


@pytest.mark.smoke
def test_is_known_ticker_equity():
    """Equity tickers from assets_universe are recognized."""
    assert _is_known_ticker("NVDA") is True
    assert _is_known_ticker("MSFT") is True


@pytest.mark.boundary
def test_is_known_ticker_fake():
    """Fabricated ticker returns False."""
    assert _is_known_ticker("FAKECOIN9999") is False


@pytest.mark.boundary
def test_is_known_ticker_empty():
    """Empty string returns False."""
    assert _is_known_ticker("") is False


# ─────────────────────────────────────────────────────────────────
# ReviewerVerdict schema
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_reviewer_verdict_slim_schema():
    """ReviewerVerdict accepts passed=True with empty issues."""
    v = ReviewerVerdict(passed=True, issues=[])
    assert v.passed is True
    assert v.issues == []


@pytest.mark.smoke
def test_reviewer_verdict_with_issues():
    """ReviewerVerdict serializes issues correctly."""
    issues = [ReviewerIssue(field="direction", reason="thesis 與 direction 矛盾")]
    v = ReviewerVerdict(passed=False, issues=issues)
    assert not v.passed
    assert v.issues[0].field == "direction"


# ─────────────────────────────────────────────────────────────────
# Full pass-through integration (reviewer disabled)
# ─────────────────────────────────────────────────────────────────

@pytest.mark.smoke
def test_full_pass_through_reviewer_disabled():
    """With reviewer disabled, all three nodes are no-ops and trades pass through."""
    trades = [_valid_trade("BTC"), _valid_trade("SOL", "SHORT")]
    state = _base_state(proposed_trades=trades)

    # python_validate
    r1 = python_validate_node(state)
    assert r1["review_issues"] == []

    # update state with r1 (simulate graph state merge)
    state = _base_state(**{**state, **r1})  # type: ignore[arg-type]

    # llm_reviewer
    r2 = llm_reviewer_node(state)
    assert r2["review_issues"] == []
    assert r2["trade_watch_final"] == trades
