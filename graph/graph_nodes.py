"""LangGraph node implementations for Phase 3 research pipeline."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from graph.graph_state import ResearchGraphState


def _hkt_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _tool_calls_enabled() -> bool:
    return os.getenv("GRAPH_ENABLE_TOOL_CALLS", "1").lower() in ("1", "true", "yes")


def _formatter_uses_legacy_crews() -> bool:
    return os.getenv("LANGGRAPH_SKIP_FORMATTER_CREW", "0").lower() not in ("1", "true", "yes")


def _safe_tool_run(tool_obj: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        runner = getattr(tool_obj, "run", None)
        if callable(runner):
            return runner(*args, **kwargs)
        if callable(tool_obj):
            return tool_obj(*args, **kwargs)
        return "[DATA_MISSING:tool_not_callable]"
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return f"[DATA_MISSING:{exc}]"


def _extract_numeric_lines(raw_data: dict[str, Any], limit: int = 4) -> list[str]:
    lines: list[str] = []
    for key, value in raw_data.items():
        text = str(value)
        if any(ch.isdigit() for ch in text):
            lines.append(f"{key}: {text[:180]}")
        if len(lines) >= limit:
            break
    if not lines:
        lines.append("尚無可引用的客觀讀數，需補抓工具輸出。")
    return lines


def data_gatherer_node(state: ResearchGraphState) -> dict[str, Any]:
    """Collect objective market/macro/tool data into raw_data."""
    category = state["category"]
    raw_data: dict[str, Any] = {
        "timestamp_hkt": _hkt_now(),
        "category": category,
        "price_context": state.get("price_context", ""),
    }

    if not _tool_calls_enabled():
        raw_data["tool_mode"] = "disabled_by_GRAPH_ENABLE_TOOL_CALLS"
        return {"raw_data": raw_data}

    # Lazy import to avoid module-load side effects during tests.
    from tools import (
        ai_momentum_tool,
        ai_sector_market_tool,
        etf_flow_tool,
        fear_greed_tool,
        financial_datasets_tool,
        macro_context_tool,
        onchain_metrics_tool,
        regime_scorecard_tool,
    )

    raw_data["regime_scorecard"] = _safe_tool_run(regime_scorecard_tool)
    raw_data["macro_context"] = _safe_tool_run(macro_context_tool)

    if category == "CRYPTO":
        raw_data["fear_greed"] = _safe_tool_run(fear_greed_tool)
        raw_data["etf_flow"] = _safe_tool_run(etf_flow_tool)
        raw_data["onchain_metrics"] = _safe_tool_run(onchain_metrics_tool)
    else:
        raw_data["ai_sector_market"] = _safe_tool_run(ai_sector_market_tool)
        raw_data["ai_momentum"] = _safe_tool_run(ai_momentum_tool, "openrouter_rankings")
        raw_data["ai_fundamentals"] = _safe_tool_run(financial_datasets_tool, "watchlist")

    return {"raw_data": raw_data}


def bull_agent_node(state: ResearchGraphState) -> dict[str, Any]:
    """Bull prompt stance: focus on liquidity expansion and upside catalysts."""
    lines = _extract_numeric_lines(state.get("raw_data", {}))
    arguments = [
        "多方觀點：流動性/資金風險偏好改善時，風險資產具上修空間。",
        f"多方數據錨點：{lines[0]}",
        f"多方次要佐證：{lines[1] if len(lines) > 1 else lines[0]}",
    ]
    return {"bull_arguments": arguments}


def bear_agent_node(state: ResearchGraphState) -> dict[str, Any]:
    """Bear prompt stance: focus on valuation fragility and macro headwinds."""
    lines = _extract_numeric_lines(state.get("raw_data", {}))
    arguments = [
        "空方觀點：估值與宏觀阻力未解除前，反彈可能是風險再定價前奏。",
        f"空方數據錨點：{lines[-1]}",
        f"空方次要佐證：{lines[0]}",
    ]
    return {"bear_arguments": arguments}


def arbiter_node(state: ResearchGraphState) -> dict[str, Any]:
    """Arbiter decides if deep research is required."""
    raw_data = state.get("raw_data", {})
    bull_args = state.get("bull_arguments", [])
    bear_args = state.get("bear_arguments", [])
    depth = int(state.get("research_depth", 0))
    max_depth = int(state.get("max_research_depth", 2))

    data_missing_keys = [
        key for key, value in raw_data.items() if "[DATA_MISSING" in str(value)
    ]
    def _has_numeric_anchor(arguments: list[str]) -> bool:
        # Require at least one explicit numeric anchor line per side.
        return any(("錨點" in arg or "佐證" in arg) and any(ch.isdigit() for ch in arg) for arg in arguments)

    weak_argument = not (_has_numeric_anchor(bull_args) and _has_numeric_anchor(bear_args))

    needs_deep_dive = bool(data_missing_keys or weak_argument)
    if depth >= max_depth:
        needs_deep_dive = False

    if data_missing_keys:
        deep_dive_query = "補齊缺失讀數：" + ", ".join(data_missing_keys[:3])
    elif weak_argument:
        deep_dive_query = "補齊可量化佐證（價格、流量、估值）"
    else:
        deep_dive_query = ""

    summary = (
        f"Arbiter：depth={depth}/{max_depth}，"
        f"missing={len(data_missing_keys)}，needs_deep_dive={needs_deep_dive}"
    )
    return {
        "arbiter_summary": summary,
        "needs_deep_dive": needs_deep_dive,
        "deep_dive_query": deep_dive_query,
    }


def deep_research_node(state: ResearchGraphState) -> dict[str, Any]:
    """Fetch narrow, missing evidence requested by Arbiter."""
    if not state.get("needs_deep_dive"):
        return {}

    category = state["category"]
    query = state.get("deep_dive_query", "")
    patch: dict[str, Any] = {"deep_dive_query": query}

    if not _tool_calls_enabled():
        patch["deep_research"] = "[DATA_MISSING:tool_calls_disabled]"
        return {"raw_data": patch, "research_depth": int(state.get("research_depth", 0)) + 1}

    from tools import financial_datasets_tool, onchain_metrics_tool

    if category == "CRYPTO":
        patch["deep_onchain_probe"] = _safe_tool_run(onchain_metrics_tool)
    else:
        probe = query if query else "watchlist"
        patch["deep_fundamentals_probe"] = _safe_tool_run(financial_datasets_tool, probe)

    return {"raw_data": patch, "research_depth": int(state.get("research_depth", 0)) + 1}


def final_formatter_node(state: ResearchGraphState) -> dict[str, Any]:
    """Format final output aligned with existing schemas via legacy crews."""
    if not _formatter_uses_legacy_crews():
        return {
            "final_report": {
                "category": state["category"],
                "arbiter_summary": state.get("arbiter_summary", ""),
                "bull_arguments": state.get("bull_arguments", []),
                "bear_arguments": state.get("bear_arguments", []),
            },
            "needs_deep_dive": False,
        }

    from crew import AIResearchCrew, CryptoResearchCrew

    category = state["category"]
    use_fallback_llm = bool(state.get("use_fallback_llm", False))
    if category == "CRYPTO":
        section = CryptoResearchCrew(use_fallback_llm=use_fallback_llm).run(
            exclude_context=state.get("exclude_context", ""),
            price_context=state.get("price_context", ""),
            prev_recs_block=state.get("prev_recs_block", ""),
            agreed_regime=state.get("agreed_regime"),
            recent_lessons=state.get("recent_lessons", ""),
        )
    else:
        section = AIResearchCrew(use_fallback_llm=use_fallback_llm).run(
            exclude_context=state.get("exclude_context", ""),
            price_context=state.get("price_context", ""),
            agreed_regime=state.get("agreed_regime"),
            recent_lessons=state.get("recent_lessons", ""),
        )

    return {"final_report": section.model_dump(mode="json"), "needs_deep_dive": False}
