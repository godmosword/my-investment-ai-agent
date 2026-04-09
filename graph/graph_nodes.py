"""LangGraph node implementations for Phase 3 research pipeline."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from graph.graph_formatter_schemas import AIFormatterNarrative, CryptoFormatterNarrative
from graph.graph_state import ResearchGraphState
from graph.graph_tools import RESEARCH_TOOLS
from schemas import AISection, CryptoSection, MarketRegimeBlock, MetricLine

logger = logging.getLogger(__name__)


def _hkt_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _tool_calls_enabled() -> bool:
    return os.getenv("GRAPH_ENABLE_TOOL_CALLS", "1").lower() in ("1", "true", "yes")


def _deep_research_tool_llm_enabled() -> bool:
    """When True, deep_research_node uses bind_tools + real tool execution (needs API keys)."""
    return os.getenv("GRAPH_DEEP_RESEARCH_TOOL_LLM", "0").lower() in ("1", "true", "yes")


def _llm_debate_enabled() -> bool:
    """When GRAPH_LLM_DEBATE=1, Bull/Bear/Arbiter nodes use live LLM calls.

    Default OFF so existing smoke tests remain cost-free and deterministic.
    """
    return os.getenv("GRAPH_LLM_DEBATE", "0").lower() in ("1", "true", "yes")


def _formatter_uses_legacy_crews() -> bool:
    return os.getenv("LANGGRAPH_SKIP_FORMATTER_CREW", "0").lower() not in ("1", "true", "yes")


# ==========================================
# Pydantic schema for structured Arbiter output
# ==========================================

class ArbiterDecision(BaseModel):
    needs_deep_dive: bool = Field(
        description=(
            "如果多空雙方的論點缺乏『具體的客觀數據』支撐"
            "（例如只說下跌但沒給具體均線價位，或只說資金流出但沒給金額），設為 True。"
        )
    )
    deep_dive_query: str = Field(
        description=(
            "如果 needs_deep_dive 為 True，請寫出指示 Deep Research Agent 去查證的具體問題。"
            "若為 False，請留空字串。"
        )
    )
    arbiter_summary: str = Field(
        description="用一句話總結目前的辯論共識（供最終報告的 signal_conflict_summary 使用）。"
    )


# ==========================================
# LLM factory helpers (lazy import to avoid module-load side effects)
# ==========================================

def _strip_provider_prefix(model_str: str) -> str:
    """Convert LiteLLM model strings (e.g. 'openai/gpt-4o-mini') to bare model names."""
    return model_str.split("/", 1)[-1]


def _get_debate_llm() -> Any:
    """High-temperature LLM for opinionated Bull/Bear debate arguments."""
    from langchain_openai import ChatOpenAI
    from config import MODEL_GPT

    return ChatOpenAI(
        model=_strip_provider_prefix(MODEL_GPT),
        temperature=0.8,
        max_retries=3,
    )


def _get_arbiter_llm() -> Any:
    """Low-temperature LLM for precise, structured Arbiter decisions."""
    from langchain_openai import ChatOpenAI
    from config import MODEL_GPT

    return ChatOpenAI(
        model=_strip_provider_prefix(MODEL_GPT),
        temperature=0.1,
        max_retries=3,
    )


def _get_formatter_llm() -> Any:
    """Low-temperature LLM for strict formatter schema adherence."""
    from langchain_openai import ChatOpenAI
    from config import MODEL_GPT

    return ChatOpenAI(
        model=_strip_provider_prefix(MODEL_GPT),
        temperature=0.1,
        max_retries=3,
    )


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


def _build_debate_context(state: ResearchGraphState) -> str:
    bull_args = state.get("bull_arguments", [])
    bear_args = state.get("bear_arguments", [])
    arbiter_summary = state.get("arbiter_summary", "")
    numeric_lines = _extract_numeric_lines(state.get("raw_data", {}), limit=4)
    return (
        f"主編共識：{arbiter_summary or '（無）'}\n"
        f"多方論點：{' | '.join(bull_args) if bull_args else '（無）'}\n"
        f"空方論點：{' | '.join(bear_args) if bear_args else '（無）'}\n"
        f"客觀讀數：{' | '.join(numeric_lines)}"
    )


def _build_formatter_context(state: ResearchGraphState) -> str:
    raw_data = state.get("raw_data", {})
    raw_lines = []
    for key, value in raw_data.items():
        text = str(value)
        if len(text) > 500:
            text = f"{text[:500]}... [TRUNCATED]"
        raw_lines.append(f"{key}: {text}")
    return (
        f"【主編共識】\n{state.get('arbiter_summary', '無主編共識')}\n\n"
        f"【多方視角】\n{chr(10).join(state.get('bull_arguments', [])) or '（無）'}\n\n"
        f"【空方視角】\n{chr(10).join(state.get('bear_arguments', [])) or '（無）'}\n\n"
        f"【Regime 鎖定】\n{state.get('agreed_regime') or '未鎖定'}\n\n"
        f"【系統即時報價】\n{state.get('price_context', '') or '（無）'}\n\n"
        f"【客觀數據】\n{chr(10).join(raw_lines) or '（無）'}\n\n"
        f"【系統反思】\n{state.get('recent_lessons', '') or '（無）'}\n"
    )


def _infer_regime(state: ResearchGraphState) -> MarketRegimeBlock:
    raw_scorecard = str(state.get("raw_data", {}).get("regime_scorecard", ""))
    agreed = str(state.get("agreed_regime") or "").strip().lower().replace("-", "_")
    source_token = agreed
    if not source_token and raw_scorecard:
        scorecard_norm = raw_scorecard.lower().replace("-", "_")
        if "risk_on" in scorecard_norm:
            source_token = "risk_on"
        elif "risk_off" in scorecard_norm:
            source_token = "risk_off"
        elif "neutral" in scorecard_norm:
            source_token = "neutral"

    if "risk_on" in source_token:
        regime = "risk_on"
    elif "risk_off" in source_token:
        regime = "risk_off"
    elif source_token in {"on", "bull", "bullish"}:
        regime = "risk_on"
    elif source_token in {"off", "bear", "bearish"}:
        regime = "risk_off"
    else:
        regime = "neutral"

    score_suffix = ""
    score_lines: list[str] = []
    if raw_scorecard:
        match = re.search(r"[\(（][+-]?\d+/\d+[\)）]", raw_scorecard)
        if match:
            score_suffix = match.group(0)
        for line in raw_scorecard.splitlines():
            line = line.strip()
            if line.startswith("✅") or line.startswith("❌"):
                score_lines.append(line)
            if len(score_lines) >= 4:
                break

    return MarketRegimeBlock(
        regime=regime,
        score_suffix=score_suffix,
        scorecard_lines=score_lines,
    )


def _build_dashboard(raw_data: dict[str, Any], limit: int = 8) -> list[MetricLine]:
    rows: list[MetricLine] = []
    for line in _extract_numeric_lines(raw_data, limit=limit):
        if ":" in line:
            label, value = line.split(":", 1)
            rows.append(MetricLine(label=label.strip(), value=value.strip()))
        else:
            rows.append(MetricLine(label="指標", value=line.strip()))
    if not rows:
        rows.append(MetricLine(label="資料狀態", value="N/A"))
    return rows


def _assemble_crypto_section(
    state: ResearchGraphState, slim: CryptoFormatterNarrative
) -> CryptoSection:
    payload: dict[str, Any] = {
        "report_title_date": _hkt_now().split(" ")[0],
        "market": _infer_regime(state).model_dump(mode="json"),
        "narrative_of_day": slim.narrative_of_day,
        "macro_framework_lines": slim.macro_framework_lines[:4],
        "dashboard": [row.model_dump(mode="json") for row in _build_dashboard(state.get("raw_data", {}), limit=8)],
        "news": [],
        "x_highlights": [],
        "chatter": [],
        "pick_reason": slim.pick_reason,
        "risk_budget_summary": slim.risk_budget_summary,
        "signal_conflict_summary": slim.signal_conflict_summary,
        "trade_legs": [],
        "qsrec": [],
    }
    return CryptoSection.model_validate(payload)


def _assemble_ai_section(
    state: ResearchGraphState, slim: AIFormatterNarrative
) -> AISection:
    payload: dict[str, Any] = {
        "macro_bridge_lines": slim.macro_bridge_lines[:2],
        "dashboard": [row.model_dump(mode="json") for row in _build_dashboard(state.get("raw_data", {}), limit=8)],
        "news": [],
        "x_highlights": [],
        "chatter": [],
        "pick_reason": slim.pick_reason,
        "signal_conflict_summary": slim.signal_conflict_summary,
        "trade_legs": [],
        "qsrec": [],
    }
    return AISection.model_validate(payload)


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
    """Bull prompt stance: focus on liquidity expansion and upside catalysts.

    When GRAPH_LLM_DEBATE=1, invokes a live ChatOpenAI call with a dedicated
    opinionated system prompt. Falls back to deterministic rule-based output otherwise.
    """
    category = state.get("category", "CRYPTO")
    lines = _extract_numeric_lines(state.get("raw_data", {}))

    if not _llm_debate_enabled():
        # Rule-based fallback (deterministic, cost-free, CI-safe)
        arguments = [
            "多方觀點：流動性/資金風險偏好改善時，風險資產具上修空間。",
            f"多方數據錨點：{lines[0]}",
            f"多方次要佐證：{lines[1] if len(lines) > 1 else lines[0]}",
        ]
        return {"bull_arguments": arguments}

    logger.info("--- [Node] Bull Agent (LLM) 啟動 ---")
    from langchain_core.prompts import ChatPromptTemplate

    llm = _get_debate_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "你是一個極度樂觀的避險基金做多經理人（Bull Agent）。"
            "你的目標是從給定的市場數據中，找出所有支持『做多』或『市場即將上漲』的蛛絲馬跡。"
            "請專注於：流動性釋放、技術面支撐確認、超賣反彈機會、以及利多催化劑。"
            "語氣必須是華爾街機構級的洗鍊，不要用問候語，"
            "直接給出 3 句具備數字佐證（價格、金額、百分比）的看多論點。",
        ),
        ("human", "板塊：{category}\n客觀讀數：\n{data_lines}"),
    ])
    chain = prompt | llm
    response = chain.invoke({
        "category": category,
        "data_lines": "\n".join(lines),
    })
    logger.debug("[Bull] %s", response.content)
    return {"bull_arguments": [response.content]}


def bear_agent_node(state: ResearchGraphState) -> dict[str, Any]:
    """Bear prompt stance: focus on valuation fragility and macro headwinds.

    When GRAPH_LLM_DEBATE=1, invokes a live ChatOpenAI call with a dedicated
    opinionated system prompt. Falls back to deterministic rule-based output otherwise.
    """
    category = state.get("category", "CRYPTO")
    lines = _extract_numeric_lines(state.get("raw_data", {}))

    if not _llm_debate_enabled():
        # Rule-based fallback (deterministic, cost-free, CI-safe)
        arguments = [
            "空方觀點：估值與宏觀阻力未解除前，反彈可能是風險再定價前奏。",
            f"空方數據錨點：{lines[-1]}",
            f"空方次要佐證：{lines[0]}",
        ]
        return {"bear_arguments": arguments}

    logger.info("--- [Node] Bear Agent (LLM) 啟動 ---")
    from langchain_core.prompts import ChatPromptTemplate

    llm = _get_debate_llm()
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "你是一個極度悲觀的避險基金放空經理人（Bear Agent）。"
            "你的目標是從給定的市場數據中，找出所有支持『做空』或『市場即將崩盤』的危險訊號。"
            "請專注於：宏觀阻力（如 VIX 攀升、DXY 走強）、估值泡沫、技術面破位、以及流動性枯竭。"
            "語氣必須是華爾街機構級的洗鍊，不要用問候語，"
            "直接給出 3 句具備數字佐證（價格、金額、百分比）的看空論點。",
        ),
        ("human", "板塊：{category}\n客觀讀數：\n{data_lines}"),
    ])
    chain = prompt | llm
    response = chain.invoke({
        "category": category,
        "data_lines": "\n".join(lines),
    })
    logger.debug("[Bear] %s", response.content)
    return {"bear_arguments": [response.content]}


def arbiter_node(state: ResearchGraphState) -> dict[str, Any]:
    """Arbiter decides if deep research is required.

    Rule-based mode (default): checks for DATA_MISSING keys and numeric anchors.
    LLM mode (GRAPH_LLM_DEBATE=1): uses with_structured_output(ArbiterDecision)
    for precise JSON-enforced decisions, with hard depth cap as safety net.
    """
    raw_data = state.get("raw_data", {})
    bull_args = state.get("bull_arguments", [])
    bear_args = state.get("bear_arguments", [])
    depth = int(state.get("research_depth", 0))
    max_depth = int(state.get("max_research_depth", 2))

    # Hard cap: never allow infinite loops regardless of LLM output.
    force_stop = depth >= max_depth

    if not _llm_debate_enabled():
        # ── Rule-based fallback ──────────────────────────────────────────────
        data_missing_keys = [
            key for key, value in raw_data.items() if "[DATA_MISSING" in str(value)
        ]

        def _has_numeric_anchor(arguments: list[str]) -> bool:
            return any(
                ("錨點" in arg or "佐證" in arg) and any(ch.isdigit() for ch in arg)
                for arg in arguments
            )

        weak_argument = not (_has_numeric_anchor(bull_args) and _has_numeric_anchor(bear_args))
        needs_deep_dive = bool((data_missing_keys or weak_argument) and not force_stop)

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

    # ── LLM-powered Arbiter ──────────────────────────────────────────────────
    logger.info("--- [Node] Arbiter (LLM 仲裁) 啟動 depth=%d/%d ---", depth, max_depth)
    from langchain_core.prompts import ChatPromptTemplate

    bull_latest = bull_args[-1] if bull_args else "（無多方論點）"
    bear_latest = bear_args[-1] if bear_args else "（無空方論點）"

    llm = _get_arbiter_llm()
    structured_llm = llm.with_structured_output(ArbiterDecision)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "你是 Q-Silicon 的首席仲裁主編。你需要審閱多空雙方的辯論。\n"
            "規則 1：如果雙方論點有明顯矛盾，但卻『缺乏具體數字佐證』"
            "（例如只說 ETF 流出卻沒給金額，或只說跌破均線卻沒給具體均線價位），"
            "你必須將 needs_deep_dive 設為 true，並給出『非常明確的 API 查詢關鍵字或指令』"
            "（例如：請查詢 'liquidations' 或 NVDA 的財報數據）。\n"
            "規則 2：如果論點已經很紮實，或這是第二次以上的審查，"
            "請將 needs_deep_dive 設為 false，並寫下一句精準的共識總結。",
        ),
        (
            "human",
            "當前查證深度：{depth}/{max_depth}\n\n多方論點：{bull}\n\n空方論點：{bear}\n\n請給出你的仲裁決策：",
        ),
    ])
    chain = prompt | structured_llm
    decision: ArbiterDecision = chain.invoke({
        "depth": depth,
        "max_depth": max_depth,
        "bull": bull_latest,
        "bear": bear_latest,
    })

    # Hard safety net: override LLM if depth cap reached.
    if force_stop and decision.needs_deep_dive:
        logger.warning("已達最大查證深度 (%d)，強制放行進入排版階段。", max_depth)
        decision = ArbiterDecision(
            needs_deep_dive=False,
            deep_dive_query="",
            arbiter_summary=decision.arbiter_summary or f"強制放行（depth={depth}/{max_depth}）",
        )

    if decision.needs_deep_dive:
        logger.warning("🚨 主編打回票，要求深挖查證: %s", decision.deep_dive_query)
    else:
        logger.info("✅ 主編放行。共識: %s", decision.arbiter_summary)

    return {
        "arbiter_summary": decision.arbiter_summary,
        "needs_deep_dive": decision.needs_deep_dive,
        "deep_dive_query": decision.deep_dive_query,
    }


def _tool_call_id(tc: Any) -> str:
    if isinstance(tc, dict):
        return str(tc.get("id") or "")
    return str(getattr(tc, "id", "") or "")


def _tool_call_name(tc: Any) -> str:
    if isinstance(tc, dict):
        return str(tc.get("name") or "")
    return str(getattr(tc, "name", "") or "")


def _tool_call_args(tc: Any) -> dict[str, Any]:
    if isinstance(tc, dict):
        raw = tc.get("args")
        return dict(raw) if isinstance(raw, dict) else {}
    raw = getattr(tc, "args", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _deep_research_with_bound_tools(query: str) -> str:
    """Run ChatOpenAI with bind_tools; execute tool_calls until model returns text."""
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    logger.info("--- [Node] Deep Research (Tool Calling LLM) 啟動 ---")
    llm = _get_debate_llm()
    llm_with_tools = llm.bind_tools(RESEARCH_TOOLS)
    tool_map = {t.name: t for t in RESEARCH_TOOLS}

    system_text = (
        "你是一位頂級的量化數據研究員。主編給了你一個具體的查核任務。"
        "你『必須』使用提供的工具 (Tools) 去撈取真實數據來回答。"
        "取得數據後，請用精準的數字（例如確切的百分比、金額、均線）回報給主編，嚴禁給出模糊的猜測。"
    )
    messages: list[Any] = [
        SystemMessage(content=system_text),
        HumanMessage(content=f"查核任務：{query}"),
    ]

    max_rounds = 6
    tool_excerpts: list[str] = []
    last_ai: AIMessage | None = None

    for _ in range(max_rounds):
        response = llm_with_tools.invoke(messages)
        if not isinstance(response, AIMessage):
            messages.append(response)
            continue
        last_ai = response
        messages.append(response)

        if not response.tool_calls:
            break

        logger.info(
            "Deep Research tool_calls: %s",
            [_tool_call_name(tc) for tc in response.tool_calls],
        )
        for tc in response.tool_calls:
            name = _tool_call_name(tc)
            selected = tool_map.get(name)
            if not selected:
                err = f"[DATA_MISSING:unknown_tool:{name}]"
                tool_excerpts.append(f"【來自 {name}】\n{err}")
                messages.append(
                    ToolMessage(content=err, tool_call_id=_tool_call_id(tc) or name)
                )
                continue
            try:
                out = selected.invoke(_tool_call_args(tc))
                out_s = out if isinstance(out, str) else str(out)
            except Exception as exc:  # pragma: no cover - defensive
                out_s = f"工具執行失敗: {exc}"
            tool_excerpts.append(f"【來自 {name} 的真實數據】\n{out_s}")
            messages.append(
                ToolMessage(content=out_s, tool_call_id=_tool_call_id(tc) or name)
            )

    synthesis = (last_ai.content or "").strip() if last_ai else ""
    if tool_excerpts and synthesis:
        return "\n\n".join(tool_excerpts) + "\n\n【綜合】\n" + synthesis
    if synthesis:
        return synthesis
    if tool_excerpts:
        return "\n\n".join(tool_excerpts)
    return "查證未完成：模型未回傳可讀摘要。"


def deep_research_node(state: ResearchGraphState) -> dict[str, Any]:
    """Fetch narrow, missing evidence requested by Arbiter.

    When GRAPH_DEEP_RESEARCH_TOOL_LLM=1 and GRAPH_ENABLE_TOOL_CALLS is on, uses
    bind_tools + real tool execution. Otherwise uses deterministic probes
    (onchain / financial_datasets) for CI and no-LLM runs.
    """
    if not state.get("needs_deep_dive"):
        return {}

    category = state["category"]
    query = state.get("deep_dive_query", "")
    depth = int(state.get("research_depth", 0))
    new_data_key = f"deep_dive_round_{depth + 1}"
    patch: dict[str, Any] = {"deep_dive_query": query}

    if not _tool_calls_enabled():
        patch["deep_research"] = "[DATA_MISSING:tool_calls_disabled]"
        return {"raw_data": {new_data_key: f"針對【{query}】查核結果：\n{patch['deep_research']}"}, "research_depth": depth + 1}

    if _deep_research_tool_llm_enabled():
        try:
            investigation = _deep_research_with_bound_tools(query or "依主編指令補齊客觀數據")
        except Exception as exc:
            logger.exception("Deep research tool LLM failed: %s", exc)
            investigation = f"[DATA_MISSING:deep_research_llm] {exc}"
        payload = f"針對【{query}】查核結果：\n{investigation}"
        logger.info("查核完成（Tool LLM），%d 字元", len(payload))
        return {"raw_data": {new_data_key: payload}, "research_depth": depth + 1}

    from tools import financial_datasets_tool, onchain_metrics_tool

    if category == "CRYPTO":
        patch["deep_onchain_probe"] = _safe_tool_run(onchain_metrics_tool)
    else:
        probe = query if query else "watchlist"
        patch["deep_fundamentals_probe"] = _safe_tool_run(financial_datasets_tool, probe)

    investigation = "\n".join(f"{k}: {v}" for k, v in patch.items() if k != "deep_dive_query")
    return {
        "raw_data": {new_data_key: f"針對【{query}】查核結果：\n{investigation}"},
        "research_depth": depth + 1,
    }


def final_formatter_node(state: ResearchGraphState) -> dict[str, Any]:
    """Final formatter with legacy fallback and native structured mode."""
    category = state["category"]
    if _formatter_uses_legacy_crews():
        logger.info("--- [Node] Final Formatter (Legacy Crew) 啟動 ---")
        from crew import AIResearchCrew, CryptoResearchCrew

        use_fallback_llm = bool(state.get("use_fallback_llm", False))
        debate_context = _build_debate_context(state)
        if category == "CRYPTO":
            section = CryptoResearchCrew(use_fallback_llm=use_fallback_llm).run(
                exclude_context=state.get("exclude_context", ""),
                price_context=state.get("price_context", ""),
                prev_recs_block=state.get("prev_recs_block", ""),
                agreed_regime=state.get("agreed_regime"),
                langgraph_debate_context=debate_context,
                recent_lessons=state.get("recent_lessons", ""),
            )
        else:
            section = AIResearchCrew(use_fallback_llm=use_fallback_llm).run(
                exclude_context=state.get("exclude_context", ""),
                price_context=state.get("price_context", ""),
                agreed_regime=state.get("agreed_regime"),
                langgraph_debate_context=debate_context,
                recent_lessons=state.get("recent_lessons", ""),
            )
        return {"final_report": section.model_dump(mode="json"), "needs_deep_dive": False}

    logger.info("--- [Node] Final Formatter (Native Structured Output) 啟動 ---")
    llm = _get_formatter_llm()
    context_text = _build_formatter_context(state)

    if category == "CRYPTO":
        structured_llm = llm.with_structured_output(CryptoFormatterNarrative)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是 Q-Silicon 最終排版總編。"
                "你只能根據提供的內部簡報生成內容，禁止捏造新聞、價格、代碼、交易腿。"
                "輸出需精簡、機構語氣、可直接寫入 JSON 欄位。",
            ),
            ("human", "板塊：CRYPTO\n\n內部簡報：\n{context_text}"),
        ])
        chain = prompt | structured_llm
        try:
            slim = chain.invoke({"context_text": context_text})
            section = _assemble_crypto_section(state, slim)
        except Exception as exc:
            logger.error("Native formatter (CRYPTO) failed: %s", exc)
            raise RuntimeError(f"Native formatter failed for CRYPTO: {exc}") from exc
    else:
        structured_llm = llm.with_structured_output(AIFormatterNarrative)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是 Q-Silicon 最終排版總編。"
                "你只能根據提供的內部簡報生成內容，禁止捏造新聞、價格、代碼、交易腿。"
                "輸出需精簡、機構語氣、可直接寫入 JSON 欄位。",
            ),
            ("human", "板塊：AI\n\n內部簡報：\n{context_text}"),
        ])
        chain = prompt | structured_llm
        try:
            slim = chain.invoke({"context_text": context_text})
            section = _assemble_ai_section(state, slim)
        except Exception as exc:
            logger.error("Native formatter (AI) failed: %s", exc)
            raise RuntimeError(f"Native formatter failed for AI: {exc}") from exc

    return {"final_report": section.model_dump(mode="json"), "needs_deep_dive": False}
