"""LangGraph node implementations for Phase 3 research pipeline.

State machine flow (USE_LANGGRAPH_ENGINE=1):

    ┌─────────────┐
    │  GatherNode │  fetch raw data via RESEARCH_TOOLS
    └──────┬──────┘
           │ ResearchGraphState.raw_data
     ┌─────┴──────┐
     │            │  parallel fan-out
  ┌──▼──┐      ┌──▼──┐
  │ Bull│      │ Bear│  independent LLM analysis
  └──┬──┘      └──┬──┘
     └─────┬───────┘
           │ bull_analysis + bear_analysis
    ┌──────▼──────┐
    │ ArbiterNode │  decide if deep-dive needed
    └──────┬──────┘
           │
     ┌─────┴─────────────────┐
     │                       │
  [skip]               ┌─────▼────┐
     │                 │ DeepNode │  additional tool calls
     │                 └─────┬────┘
     └─────────┬─────────────┘
               │
       ┌───────▼────────┐
       │ FormatterNode  │  assemble → DailyBriefReport schema
       └───────┬────────┘
               │
           graph output
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from collections.abc import Sequence
from typing import Any, Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from graph.graph_formatter_schemas import (
    AIFormatterNarrative,
    CryptoFormatterNarrative,
    FormatterInputPacket,
    FormatterNewsInput,
    FormatterTradeIntentInput,
)
from graph.graph_state import ResearchGraphState
from graph.graph_tools import RESEARCH_TOOLS
from execution_intents import append_execution_intents
from war_room_stream import emit_graph_node_event
from schemas import (
    AgencyDeliverable,
    AgencyResearchOutput,
    AISection,
    Citation,
    CryptoSection,
    DeepFilingAnalysis,
    ExecutableTradeLeg,
    MarketRegimeBlock,
    MetricLine,
    NewsItem,
    TradeRecommendation,
    normalize_optional_agency_research_output,
)
from validation_rules import ensure_news_timestamp_line_utc8

logger = logging.getLogger(__name__)

# 與 crew.py「工具真值／因果」對齊：LangGraph 路徑亦禁止為用滿 context 而硬湊無關宏觀讀數。
_GRAPH_CONTEXT_PRUNING_RULE = (
    "【上下文刪減】你可省略與當前標的、新聞或 trade thesis 無直接、可驗證關聯的工具讀數（如 DXY、HF 下載量、"
    "與主線無關的利率細節）；禁止為了「用滿資料」而牽強單一主因或宏觀跳接。寧可簡短，也不要硬湊。"
)


def _hkt_now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _emit_node_event(
    node_name: str,
    data: dict,
    *,
    phase: str = "end",
    summary: str | None = None,
    run_id: str | None = None,
    category: str | None = None,
) -> None:
    try:
        emit_graph_node_event(
            node_name,
            data,
            phase=phase,
            summary=summary,
            run_id=run_id,
            category=category,
        )
    except Exception:  # never let SSE plumbing crash the graph
        pass


def _graph_run_id(state: ResearchGraphState) -> str | None:
    rid = state.get("graph_run_id")
    return str(rid).strip() or None if rid is not None else None


def _graph_category(state: ResearchGraphState) -> str | None:
    c = state.get("category")
    return str(c).strip() or None if c is not None else None


def _blocked_assets_preview(assets: list[str], *, max_items: int = 3) -> str:
    xs = [str(a).strip() for a in assets if str(a).strip()][:max_items]
    if not xs:
        return ""
    if len(assets) > max_items:
        return "、".join(xs) + f"…（共 {len(assets)} 檔）"
    return "、".join(xs)


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


_FILING_TRIGGER_KEYWORDS = (
    "10-k",
    "10-q",
    "8-k",
    "s-1",
    "filing",
    "sec",
    "earnings",
    "financial statement",
    "財報",
    "申報",
    "年報",
    "季報",
)
_AGENCY_TRIGGER_KEYWORDS = _FILING_TRIGGER_KEYWORDS + (
    "equity",
    "company",
    "stock",
    "valuation",
    "ai",
    "nvda",
    "msft",
    "股票",
    "估值",
)


def _state_text_for_feature_triggers(state: ResearchGraphState, *, max_chars: int = 6000) -> str:
    chunks: list[str] = [
        str(state.get("category", "")),
        str(state.get("price_context", "")),
        str(state.get("exclude_context", "")),
        str(state.get("arbiter_summary", "")),
        str(state.get("deep_dive_query", "")),
    ]
    chunks.extend(str(x) for x in state.get("bull_arguments", [])[:4])
    chunks.extend(str(x) for x in state.get("bear_arguments", [])[:4])
    for item in state.get("raw_news", [])[:6]:
        if isinstance(item, dict):
            chunks.append(str(item.get("title", "")))
            chunks.append(str(item.get("description", "")))
    try:
        chunks.append(json.dumps(state.get("raw_data", {}), ensure_ascii=False)[:max_chars])
    except Exception:
        chunks.append(str(state.get("raw_data", ""))[:max_chars])
    return "\n".join(chunks).lower()[:max_chars]


def _state_hits_keywords(state: ResearchGraphState, keywords: tuple[str, ...]) -> bool:
    blob = _state_text_for_feature_triggers(state)
    return any(kw.lower() in blob for kw in keywords)


def _extract_equity_ticker(state: ResearchGraphState) -> str:
    for row in state.get("proposed_trades", []) or []:
        if isinstance(row, dict):
            asset = str(row.get("asset", "")).strip().upper()
            if re.fullmatch(r"[A-Z]{2,5}", asset):
                return asset
    text = "\n".join(
        [
            str(state.get("price_context", "")),
            str(state.get("deep_dive_query", "")),
            str(state.get("arbiter_summary", "")),
        ]
    )
    ignore = {"AI", "SEC", "ETF", "USD", "BTC", "ETH", "SOL", "LONG", "SHORT"}
    for token in re.findall(r"\b[A-Z]{2,5}\b", text):
        if token not in ignore:
            return token
    return "AI"


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


class TradeIntent(BaseModel):
    """Structured intent returned by trade picker LLM (no numeric prices)."""

    asset: str = Field(..., description="Ticker without $, uppercase preferred.")
    direction: Literal["LONG", "SHORT"] = Field(...)
    star_rating: int = Field(..., ge=1, le=2, description="Conviction 1-2 only.")
    thesis_one_liner: str = Field(..., description="One-line external narrative seed.")


class TradePickerOutput(BaseModel):
    intents: list[TradeIntent] = Field(default_factory=list)


# ==========================================
# Hard Python Gate — market boundaries (pre-reviewer)
# ==========================================

# Four-to-six digit numeric strings are Taiwan local codes (e.g. "2330", "00878").
_TW_LOCAL_CODE_RE = re.compile(r"^\d{4,6}$")

# Non-US yfinance-style exchange suffixes (longest matched first).
_NON_US_REGIONAL_SUFFIXES: frozenset[str] = frozenset(
    {
        ".TW",
        ".TWO",
        ".TWSE",
        ".TPEX",
        ".HK",
        ".SS",
        ".SZ",
        ".T",
        ".TO",
        ".L",
        ".PA",
        ".DE",
        ".AS",
        ".MI",
        ".SW",
        ".MC",
        ".LS",
        ".NS",
        ".BO",
        ".AX",
        ".SA",
        ".MX",
        ".ST",
        ".OL",
        ".CO",
        ".VI",
        ".BR",
        ".IS",
        ".KS",
    }
)

_SORTED_NON_US_SUFFIXES: tuple[str, ...] = tuple(
    sorted(_NON_US_REGIONAL_SUFFIXES, key=len, reverse=True)
)


def _coerce_intent_dict(row: Any) -> dict[str, Any] | None:
    if isinstance(row, dict):
        return row
    if isinstance(row, TradeIntent):
        return row.model_dump(mode="json")
    if isinstance(row, BaseModel):
        return row.model_dump(mode="json")
    return None


def _raw_asset_upper(row: dict[str, Any]) -> str:
    return str(row.get("asset", "")).strip().upper().lstrip("$")


def _has_non_us_regional_suffix(asset_upper: str) -> bool:
    au = asset_upper
    for sfx in _SORTED_NON_US_SUFFIXES:
        if au.endswith(sfx.upper()):
            return True
    return False


def _is_taiwan_local_numeric(asset_upper: str) -> bool:
    return bool(_TW_LOCAL_CODE_RE.match(asset_upper)) and "." not in asset_upper


def _crypto_allowlist_base(asset_upper: str) -> str | None:
    """Map spot/perp-style symbols to BTC or ETH; strict two-asset policy."""
    raw = asset_upper.strip().upper().lstrip("$")
    t = raw.split("-", 1)[0] if "-" in raw else raw
    for noise in (".P", ".PT"):
        if t.upper().endswith(noise.upper()):
            t = t[: -len(noise)]
    for suf in ("USDT", "USD", "PERP"):
        u = t.upper()
        su = suf.upper()
        if u.endswith(su) and len(u) > len(su):
            t = t[: -len(suf)]
            break
    t = t.upper()
    if t in ("BTC", "ETH"):
        return t
    return None


def _ai_equity_symbol_for_allowlist(asset_upper: str) -> str:
    """Strip optional .US suffix for membership in equity_universe_merged."""
    au = asset_upper.strip().upper().lstrip("$")
    if au.endswith(".US"):
        return au[:-3]
    return au


@lru_cache(maxsize=1)
def _equity_universe_upper() -> frozenset[str]:
    # Mirrors ``assets_universe`` defaults when config cannot be read or returns empty.
    _fallback = frozenset(
        {
            "NVDA",
            "MSFT",
            "AAPL",
            "TSLA",
            "GOOGL",
            "GOOG",
            "AMZN",
            "META",
            "AVGO",
            "TSM",
        }
    )
    try:
        from assets_universe import equity_universe_merged

        merged = frozenset(s.upper() for s in equity_universe_merged())
        return merged if merged else _fallback
    except Exception:
        return _fallback


def gate_exclude_unwanted_markets(
    intents: Sequence[Any],
    *,
    category: str = "CRYPTO",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deterministically drop non-target-market and out-of-allowlist assets.

    - **Regional / TW**: suffix on non-US exchanges, Taiwan local numeric codes.
    - **CRYPTO** track: only ``BTC`` and ``ETH`` (after normalizing e.g. ``BTCUSDT``).
    - **AI** track: only symbols in ``equity_universe_merged()`` (after optional ``.US`` strip).

    Returns (allowed, blocked) dict rows. Never raises.
    """
    cat = str(category or "CRYPTO").strip().upper()
    if cat not in ("CRYPTO", "AI"):
        cat = "CRYPTO"

    allowed: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    eq_allow = _equity_universe_upper()

    for raw in intents:
        row = _coerce_intent_dict(raw)
        if row is None:
            continue
        asset_raw = _raw_asset_upper(row)
        display = str(row.get("asset", "")).strip() or asset_raw

        if not asset_raw:
            logger.warning("[GATE] Dropped %s: empty asset", display)
            blocked.append(row)
            continue

        if _has_non_us_regional_suffix(asset_raw) or _is_taiwan_local_numeric(asset_raw):
            logger.warning("[GATE] Dropped %s: Non-target market", display)
            blocked.append(row)
            continue

        if cat == "CRYPTO":
            base = _crypto_allowlist_base(asset_raw)
            if base is None:
                logger.warning("[GATE] Dropped %s: Not-in-allowlist", display)
                blocked.append(row)
                continue
            out = dict(row)
            out["asset"] = base
            allowed.append(out)
            continue

        # AI — equities universe only (no crypto legs on the AI track)
        sym = _ai_equity_symbol_for_allowlist(asset_raw)
        if _crypto_allowlist_base(asset_raw) is not None or sym in ("BTC", "ETH"):
            logger.warning("[GATE] Dropped %s: Not-in-allowlist", display)
            blocked.append(row)
            continue
        if sym not in eq_allow:
            logger.warning("[GATE] Dropped %s: Not-in-allowlist", display)
            blocked.append(row)
            continue
        out = dict(row)
        out["asset"] = sym
        allowed.append(out)

    return allowed, blocked


def market_gate_node(state: ResearchGraphState) -> dict[str, Any]:
    """Pure-Python interceptor: enforce market boundaries before review loop."""
    proposed = list(state.get("proposed_trades") or [])
    rid = _graph_run_id(state)
    gcat = _graph_category(state) or str(state.get("category") or "CRYPTO")
    if not proposed:
        _emit_node_event(
            "market_gate",
            {"allowed": 0, "blocked": 0},
            summary="Gate：無待審 intent",
            run_id=rid,
            category=gcat,
        )
        return {}

    category = str(state.get("category") or "CRYPTO")
    _emit_node_event(
        "market_gate",
        {"incoming_count": len(proposed)},
        phase="begin",
        summary=f"Gate 審核 {len(proposed)} 筆 intent（{category}）",
        run_id=rid,
        category=category,
    )
    allowed, blocked = gate_exclude_unwanted_markets(proposed, category=category)

    if blocked:
        logger.warning(
            "[GATE] Summary: stripped %d intent(s); remaining=%d (category=%s)",
            len(blocked),
            len(allowed),
            category,
        )

    blocked_assets = [str(b.get("asset", "?")) for b in blocked]
    if blocked:
        prev = _blocked_assets_preview(blocked_assets)
        gate_summary = f"Gate 攔截 {len(blocked)} 檔（放行 {len(allowed)}）"
        if prev:
            gate_summary = f"{gate_summary}：{prev}"
    else:
        gate_summary = f"Gate 通過 {len(allowed)} 檔、攔截 0 檔"
    _emit_node_event(
        "market_gate",
        {
            "allowed": len(allowed),
            "blocked": len(blocked),
            "blocked_assets": blocked_assets,
        },
        summary=gate_summary,
        run_id=rid,
        category=category,
    )
    return {"proposed_trades": allowed}


class ReviewerIssue(BaseModel):
    """Single issue found by reviewer (slim schema — field + one-line reason)."""

    field: str = Field(..., description="The trade field or dimension that failed, e.g. 'asset', 'direction'.")
    reason: str = Field(..., description="One-line explanation of the failure.")


class ReviewerVerdict(BaseModel):
    """Slim reviewer verdict — only verdict + issues list, never a full rewrite."""

    passed: bool = Field(..., description="True if no logical contradictions found.")
    issues: list[ReviewerIssue] = Field(
        default_factory=list,
        description="Empty when passed=True; otherwise list of specific issues.",
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


@lru_cache(maxsize=1)
def _get_trade_picker_llm() -> Any:
    """Low-temperature LLM for compact trade intent extraction (singleton per process)."""
    from langchain_openai import ChatOpenAI
    from config import MODEL_GPT

    return ChatOpenAI(
        model=_strip_provider_prefix(MODEL_GPT),
        temperature=0.2,
        max_retries=3,
    )


def _trade_picker_enabled() -> bool:
    return os.getenv("GRAPH_LLM_TRADE_PICKER", "0").lower() in ("1", "true", "yes")


def _fetch_live_ground_truth(assets: list[str], category: str) -> str:
    """Build reviewer Ground Truth from ``symbol_snapshot_service`` (quote + OHLC).

    Single source of truth with Terminal yfinance paths; does not use
    ``tracker._current_prices_for_assets``. Never raises — on failure returns a
    labelled DATA_MISSING marker.
    """
    if not assets:
        return "[GROUND_TRUTH: no assets to fetch]"
    try:
        from symbol_snapshot_service import build_reviewer_ground_truth_block

        return build_reviewer_ground_truth_block(
            assets,
            category=category,
            bypass_quote_cache=True,
        )
    except Exception as exc:
        logger.warning("_fetch_live_ground_truth failed: %s", exc)
        return f"[GROUND_TRUTH: DATA_MISSING — {exc}]"


def _reviewer_enabled() -> bool:
    """When enabled, trade_picker output is reviewed before formatter.

    GRAPH_LLM_REVIEWER is the original flag; GRAPH_LLM_TRADE_REVIEWER is kept as
    the explicit alias used in the architecture plan.
    """
    return (
        os.getenv("GRAPH_LLM_REVIEWER", "0").lower() in ("1", "true", "yes")
        or os.getenv("GRAPH_LLM_TRADE_REVIEWER", "0").lower() in ("1", "true", "yes")
    )


def _reviewer_fail_open() -> bool:
    """Dev-only escape hatch; production default is fail-closed on reviewer errors."""
    return os.getenv("GRAPH_LLM_REVIEWER_FAIL_OPEN", "0").lower() in ("1", "true", "yes")


def _persist_reviewed_execution_intents(state: ResearchGraphState) -> None:
    """Write execution intents once, after review loop completes (not at market_gate)."""
    if state.get("degraded"):
        return
    trades = list(state.get("trade_watch_final") or [])
    if not trades:
        return
    try:
        append_execution_intents(
            category=str(state.get("category") or ""),
            regime=state.get("agreed_regime"),
            proposed_trades=[t for t in trades if isinstance(t, dict)],
        )
    except Exception as exc:
        logger.warning("[FORMATTER] execution intent append failed: %s", exc)


@lru_cache(maxsize=1)
def _get_reviewer_llm() -> Any:
    """Low-temperature LLM for strict reviewer verdict (singleton per process)."""
    from langchain_openai import ChatOpenAI
    from config import MODEL_GPT

    return ChatOpenAI(
        model=_strip_provider_prefix(MODEL_GPT),
        temperature=0.1,
        max_retries=2,
    )


def _is_known_ticker(asset: str, *, category: str | None = None) -> bool:
    """Same allowlist semantics as ``gate_exclude_unwanted_markets`` (regional rules omitted).

    Mirrors graph ``state["category"]``: ``CRYPTO`` (BTC/ETH only, after normalization)
    or ``AI`` (``equity_universe_merged`` only). Unknown category defaults to ``CRYPTO``.
    """
    cat = str(category or "CRYPTO").strip().upper()
    if cat not in ("CRYPTO", "AI"):
        cat = "CRYPTO"
    raw = str(asset).strip().upper().lstrip("$")
    if not raw:
        return False
    if cat == "CRYPTO":
        return _crypto_allowlist_base(raw) is not None
    sym = _ai_equity_symbol_for_allowlist(raw)
    if _crypto_allowlist_base(raw) is not None or sym in ("BTC", "ETH"):
        return False
    return sym in _equity_universe_upper()


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


def _tool_registry():
    from tools import market  # noqa: PLC0415
    import tools as tools_pkg  # noqa: PLC0415

    return market.build_tool_registry(tools_pkg)


def _fetch_parsed_news_source(
    name: str, tool_key: str, kwargs: dict[str, Any]
) -> tuple[str, list[dict[str, Any]]]:
    """Run one news tool and return (source_name, parsed items). Thread-safe for parallel fetch."""
    try:
        result = _tool_registry().get_news_payload(tool_key, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        result = f"[DATA_MISSING:{exc}]"
    text = str(result)
    if not text or text.startswith("[DATA_MISSING"):
        return name, []
    parsed = (
        _parse_cryptopanic_blocks(text)
        if name == "cryptopanic"
        else _parse_news_lines(text, name)
    )
    return name, parsed


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


def _build_formatter_input_packet(state: ResearchGraphState) -> FormatterInputPacket:
    raw_data = state.get("raw_data", {})
    raw_data_digest: dict[str, str] = {}
    for key, value in raw_data.items():
        text = str(value).strip()
        if len(text) > 280:
            text = f"{text[:280]}... [TRUNCATED]"
        raw_data_digest[str(key)] = text

    news_rows: list[FormatterNewsInput] = []
    for item in state.get("raw_news", [])[:6]:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        news_rows.append(
            FormatterNewsInput(
                title=title[:220],
                source=str(item.get("source", "")).strip() or str(item.get("feed", "unknown")).strip() or "unknown",
                published_at=str(item.get("published_at", "")).strip(),
            )
        )

    intents: list[FormatterTradeIntentInput] = []
    for item in state.get("proposed_trades", [])[:2]:
        try:
            intent = TradeIntent.model_validate(item)
        except Exception:
            continue
        intents.append(
            FormatterTradeIntentInput(
                asset=intent.asset.upper().lstrip("$"),
                direction=intent.direction,
                star_rating=intent.star_rating,
                thesis_one_liner=intent.thesis_one_liner.strip(),
            )
        )

    return FormatterInputPacket(
        category=str(state.get("category", "")),
        agreed_regime=str(state.get("agreed_regime") or ""),
        arbiter_summary=str(state.get("arbiter_summary", "")),
        bull_arguments=[str(x).strip() for x in state.get("bull_arguments", []) if str(x).strip()],
        bear_arguments=[str(x).strip() for x in state.get("bear_arguments", []) if str(x).strip()],
        price_context=str(state.get("price_context", "")),
        recent_lessons=str(state.get("recent_lessons", "")),
        raw_data_digest=raw_data_digest,
        raw_news=news_rows,
        proposed_trades=intents,
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


def _extract_first_number(text: str) -> str:
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?%?", text or "")
    if not match:
        return ""
    return match.group(0)


def _dashboard_numeric_anchor(dashboard: list[MetricLine] | list[dict[str, Any]]) -> str:
    for row in dashboard:
        if isinstance(row, MetricLine):
            token = _extract_first_number(row.value)
        else:
            token = _extract_first_number(str(row.get("value", "")))
        if token:
            return token
    return "0"


def _parse_cryptopanic_blocks(raw: str) -> list[dict[str, Any]]:
    blocks = re.split(r"\n\s*\n", raw.strip())
    parsed: list[dict[str, Any]] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue
        meta = lines[0]
        title = lines[1]
        url = ""
        published_at = ""
        source = "unknown"
        if len(lines) >= 3:
            url = lines[2].replace("URL:", "").strip()
        ts_match = re.search(r"時間：([^｜]+)", meta)
        src_match = re.search(r"來源：([^｜]+)", meta)
        if ts_match:
            published_at = ts_match.group(1).strip()
        if src_match:
            source = src_match.group(1).strip()
        if not title:
            continue
        parsed.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "published_at": published_at,
                "raw_body": block,
                "feed": "cryptopanic",
            }
        )
    return parsed


def _parse_news_lines(raw: str, feed: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    parsed: list[dict[str, Any]] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.startswith("【"):
            continue
        meta = re.match(r"^〔([^｜]+)｜([^〕]+)〕(.*)$", line)
        if not meta:
            continue
        published_at = meta.group(1).strip()
        source = meta.group(2).strip()
        title = meta.group(3).strip()
        url = ""
        if i < len(lines):
            nxt = lines[i]
            if nxt.startswith("http"):
                url = nxt
                i += 1
        if not title:
            continue
        parsed.append(
            {
                "title": title,
                "url": url,
                "source": source,
                "published_at": published_at,
                "raw_body": line,
                "feed": feed,
            }
        )
    return parsed


def _to_timestamp_line(published_at: str) -> str:
    ts = (published_at or "").strip()
    hkt = timezone(timedelta(hours=8))
    dt: datetime | None = None
    if ts:
        iso = ts.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            mdhm = re.search(r"(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})", ts)
            if mdhm:
                now = datetime.now(hkt)
                dt = datetime(
                    year=now.year,
                    month=int(mdhm.group(1)),
                    day=int(mdhm.group(2)),
                    hour=int(mdhm.group(3)),
                    minute=int(mdhm.group(4)),
                    tzinfo=hkt,
                )
    if dt is None:
        dt = datetime.now(hkt)
    ts_line = f"[{dt.astimezone(hkt).strftime('%m/%d %H:%M')} UTC+8]"
    return ensure_news_timestamp_line_utc8(ts_line)


def _resolve_spot_price(asset: str, price_context: str, category: str) -> float | None:
    symbol = (asset or "").strip().upper().lstrip("$")
    if not symbol:
        return None
    probe = symbol.split("/")[0]
    ctx = price_context or ""
    patterns = (
        rf"\b{re.escape(probe)}\b\s*[:=]?\s*\$?\s*([0-9][0-9,]*(?:\.\d+)?)",
        rf"\${re.escape(probe)}\s*[:=]?\s*([0-9][0-9,]*(?:\.\d+)?)",
    )
    for pattern in patterns:
        m = re.search(pattern, ctx, flags=re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", ""))

    fallback_symbol = probe
    if category == "AI":
        fallback_symbol = probe.upper()
    try:
        from tracker import _current_price_for_asset  # noqa: PLC0415

        val = _current_price_for_asset(fallback_symbol)
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        token = _extract_first_number(str(val)).replace(",", "")
        return float(token) if token else None
    except Exception:  # pragma: no cover - graceful degradation
        return None


def _proposed_trades_to_legs_and_qsrec(
    category: Literal["CRYPTO", "AI"],
    proposed_trades: list[dict[str, Any]],
    price_context: str,
    agreed_regime: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if "risk_off" in (agreed_regime or "").lower().replace("-", "_"):
        return [], []

    legs: list[dict[str, Any]] = []
    qsrec: list[dict[str, Any]] = []
    for item in proposed_trades:
        try:
            intent = TradeIntent.model_validate(item)
        except Exception:
            continue
        spot = _resolve_spot_price(intent.asset, price_context, category)
        if spot is None or spot <= 0:
            continue

        direction = intent.direction
        if direction == "LONG":
            entry = spot
            target = spot * 1.03
            stop = spot * 0.98
            tgt_pct = 3.0
            stop_pct = -2.0
        else:
            entry = spot
            target = spot * 0.97
            stop = spot * 1.02
            tgt_pct = -3.0
            stop_pct = 2.0

        rr_value = abs((target - entry) / (entry - stop)) if entry != stop else 1.0
        confidence = max(1, min(2, int(intent.star_rating)))
        asset_market = "CRYPTO" if category == "CRYPTO" else "US"
        tr_category = "CRYPTO" if category == "CRYPTO" else "EQUITY"

        rec = TradeRecommendation.model_validate(
            {
                "asset": intent.asset.upper().lstrip("$"),
                "direction": direction,
                "current_price": round(spot, 6),
                "entry": round(entry, 6),
                "target": round(target, 6),
                "stop": round(stop, 6),
                "confidence": confidence,
                "category": tr_category,
                "asset_market": asset_market,
                "narrative": intent.thesis_one_liner.strip() or "—",
                "trigger": f"若價格觸及 {entry:.2f} 附近進場。",
                "invalidation": f"若價格觸及 {stop:.2f} 視為失效。",
                "position_pct": 0.05 if confidence == 2 else 0.03,
                "rr_ratio": round(rr_value, 2),
                "max_drawdown_pct": round(-abs((stop - entry) / entry) * 100, 2),
                "expected_win_rate": 52.0,
                "signal_score": 58.0,
            }
        )
        leg = ExecutableTradeLeg.model_validate(
            {
                "asset_market": asset_market,
                "asset": intent.asset.upper().lstrip("$"),
                "direction": direction,
                "current_price": f"{spot:.2f}",
                "star_rating": confidence,
                "entry": f"{entry:.2f}",
                "target": f"{target:.2f} ({tgt_pct:+.1f}%)",
                "stop": f"{stop:.2f} ({stop_pct:+.1f}%)",
                "rr": f"1:{rr_value:.2f}",
                "max_drawdown_pct": f"{-abs((stop - entry) / entry) * 100:.1f}%",
                "expected_win_rate": "52%",
                "signal_score": "58/100",
                "trigger": f"價格觸及 {entry:.2f} 進場。",
                "sizing_logic": "先小倉位測試，確認後再加碼。",
                "invalidation": f"跌破/突破 {stop:.2f} 立即退出。",
                "position_pct": "3-5%",
                "liquidity_execution_note": "以限價單分批成交，避免滑價擴大。",
                "narrative": intent.thesis_one_liner.strip() or "—",
                "bull_scenario": f"站穩 {target:.2f} 延續趨勢",
                "base_scenario": f"{entry:.2f}-{target:.2f} 區間整理",
                "bear_scenario": f"觸及 {stop:.2f} 失效",
            }
        )
        qsrec.append(rec.model_dump(mode="json"))
        legs.append(leg.model_dump(mode="json"))
    return legs, qsrec


def _raw_news_to_news_items(
    category: Literal["CRYPTO", "AI"],
    raw_news: list[dict[str, Any]],
    dashboard: list[MetricLine],
    start_index: int,
) -> list[dict[str, Any]]:
    anchor = _dashboard_numeric_anchor(dashboard)
    out: list[dict[str, Any]] = []
    for index, item in enumerate(raw_news[:3], start=start_index):
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        source = str(item.get("source", "unknown")).strip() or "unknown"
        source_and_nature = f"{source}｜confirmed"
        news_asset = "BTC" if category == "CRYPTO" else "NVDA"
        try:
            news = NewsItem.model_validate(
                {
                    "index": index,
                    "timestamp_line": _to_timestamp_line(str(item.get("published_at", ""))),
                    "title": title[:220],
                    "source_and_nature": source_and_nature,
                    "summary": title[:90],
                    "investment_takeaway": f"{anchor} 為當前關鍵讀數；事件延續現有交易主軸。",
                    "editor_consensus": f"{news_asset} 以紀律倉位應對。",
                    "pricing_note": "大致已定價",
                }
            )
        except Exception as exc:
            logger.warning("Skip invalid news item: %s", exc)
            continue
        out.append(news.model_dump(mode="json"))
    return out


def _assemble_crypto_section(
    state: ResearchGraphState, slim: CryptoFormatterNarrative
) -> CryptoSection:
    dashboard = _build_dashboard(state.get("raw_data", {}), limit=8)
    news_rows = _raw_news_to_news_items(
        "CRYPTO",
        state.get("raw_news", []),
        dashboard,
        start_index=1,
    )
    trade_legs, qsrec = _proposed_trades_to_legs_and_qsrec(
        "CRYPTO",
        state.get("proposed_trades", []),
        state.get("price_context", ""),
        state.get("agreed_regime"),
    )
    payload: dict[str, Any] = {
        "report_title_date": _hkt_now().split(" ")[0],
        "market": _infer_regime(state).model_dump(mode="json"),
        "narrative_of_day": slim.narrative_of_day,
        "macro_framework_lines": slim.macro_framework_lines[:4],
        "dashboard": [row.model_dump(mode="json") for row in dashboard],
        "news": news_rows,
        "x_highlights": [],
        "chatter": [],
        "pick_reason": slim.pick_reason,
        "risk_budget_summary": slim.risk_budget_summary,
        "signal_conflict_summary": slim.signal_conflict_summary,
        "trade_legs": trade_legs,
        "qsrec": qsrec,
    }
    return CryptoSection.model_validate(payload)


def _assemble_ai_section(
    state: ResearchGraphState, slim: AIFormatterNarrative
) -> AISection:
    dashboard = _build_dashboard(state.get("raw_data", {}), limit=8)
    news_rows = _raw_news_to_news_items(
        "AI",
        state.get("raw_news", []),
        dashboard,
        start_index=4,
    )
    trade_legs, qsrec = _proposed_trades_to_legs_and_qsrec(
        "AI",
        state.get("proposed_trades", []),
        state.get("price_context", ""),
        state.get("agreed_regime"),
    )
    payload: dict[str, Any] = {
        "macro_bridge_lines": slim.macro_bridge_lines[:2],
        "dashboard": [row.model_dump(mode="json") for row in dashboard],
        "news": news_rows,
        "x_highlights": [],
        "chatter": [],
        "pick_reason": slim.pick_reason,
        "signal_conflict_summary": slim.signal_conflict_summary,
        "trade_legs": trade_legs,
        "qsrec": qsrec,
    }
    if state.get("deep_filing_analysis"):
        payload["deep_filing_analysis"] = state.get("deep_filing_analysis")
    agency_payload = normalize_optional_agency_research_output(
        state.get("agency_research_output")
    )
    if agency_payload is not None:
        payload["agency_research_output"] = agency_payload
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

    registry = _tool_registry()

    raw_data["regime_scorecard"] = registry.get_snapshot("regime_scorecard_tool")
    raw_data["macro_context"] = registry.get_snapshot("macro_context_tool")
    raw_data["prediction_markets"] = registry.get_snapshot("prediction_markets_tool")

    if category == "CRYPTO":
        raw_data["fear_greed"] = registry.get_snapshot("fear_greed_tool")
        raw_data["etf_flow"] = registry.get_snapshot("etf_flow_tool")
        raw_data["onchain_metrics"] = registry.get_snapshot("onchain_metrics_tool")
    else:
        raw_data["ai_sector_market"] = registry.get_snapshot("ai_sector_market_tool")
        raw_data["ai_momentum"] = registry.get_snapshot("ai_momentum_tool", "openrouter_rankings")
        raw_data["ai_fundamentals"] = registry.get_snapshot("financial_datasets_tool", "watchlist")

    return {"raw_data": raw_data}


def news_scraper_node(state: ResearchGraphState) -> dict[str, Any]:
    """Deterministically collect news from existing tools and normalize into raw_news."""
    if not _tool_calls_enabled():
        return {"raw_news": []}

    category = state.get("category", "CRYPTO")
    raw_news: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    def _append(items: list[dict[str, Any]]) -> None:
        for item in items:
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            dedupe_key = (url or title).lower()
            if not title or not dedupe_key or dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            raw_news.append(item)
            if len(raw_news) >= 6:
                return

    if category == "CRYPTO":
        sources = [
            ("cryptopanic", "cryptopanic_tool", {"topic": "bitcoin"}),
            ("newsapi", "newsapi_tool", {"query": "bitcoin OR ethereum crypto market"}),
            ("gnews", "gnews_tool", {"query": "bitcoin OR ethereum crypto market"}),
            ("rss", "rss_feed_tool", {"category": "crypto"}),
        ]
    else:
        sources = [
            ("newsapi", "newsapi_tool", {"query": "artificial intelligence stocks NVDA MSFT"}),
            ("gnews", "gnews_tool", {"query": "artificial intelligence stocks NVDA MSFT"}),
            ("rss", "rss_feed_tool", {"category": "ai"}),
        ]

    # Parallel HTTP/tool calls; merge in configured source order for stable priority / dedupe.
    max_workers = min(4, len(sources))
    by_name: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_fetch_parsed_news_source, name, tool_key, dict(kwargs))
            for name, tool_key, kwargs in sources
        ]
        for fut in as_completed(futures):
            name, items = fut.result()
            by_name[name] = items

    for name, _tool_key, _kwargs in sources:
        if len(raw_news) >= 6:
            break
        _append(by_name.get(name, []))

    freshness_whitelist = {
        token.strip().upper()
        for token in (os.getenv("NEWS_FRESHNESS_SOURCE_WHITELIST", "").split(","))
        if token.strip()
    }
    normalized: list[dict[str, Any]] = []
    for item in raw_news[:6]:
        source = str(item.get("source", "")).strip() or str(item.get("feed", "")).strip() or "unknown"
        item = {
            **item,
            "source": source,
            "source_whitelisted_for_freshness": source.upper() in freshness_whitelist,
        }
        normalized.append(item)

    return {"raw_news": normalized}


def trade_picker_node(state: ResearchGraphState) -> dict[str, Any]:
    """Use structured LLM output for trade intents; prices are materialized later.

    When called as a retry (review_issues non-empty), injects reviewer feedback
    into the prompt so the LLM can self-correct.
    """
    category = state.get("category", "CRYPTO")
    rid = _graph_run_id(state)
    gcat = _graph_category(state) or str(category)
    if not _trade_picker_enabled():
        _emit_node_event(
            "trade_picker",
            {"intent_count": 0, "category": category, "reason": "disabled"},
            summary="Trade picker：功能關閉",
            run_id=rid,
            category=gcat,
        )
        return {"proposed_trades": [], "review_issues": []}

    agreed_regime = str(state.get("agreed_regime") or "")
    arbiter_summary = str(state.get("arbiter_summary") or "")
    regime_hint = f"{agreed_regime}\n{arbiter_summary}".lower().replace("-", "_")
    if "risk_off" in regime_hint:
        _emit_node_event(
            "trade_picker",
            {"intent_count": 0, "category": category, "reason": "risk_off"},
            summary="Trade picker：risk-off 模式，略過產出",
            run_id=rid,
            category=gcat,
        )
        return {"proposed_trades": [], "review_issues": []}

    price_context = state.get("price_context", "")
    raw_news = state.get("raw_news", []) or []
    news_titles = [str(item.get("title", "")).strip() for item in raw_news[:5] if str(item.get("title", "")).strip()]
    news_blob = "\n".join(f"- {title}" for title in news_titles) or "（無）"

    # Inject reviewer feedback when retrying after validation failure.
    prior_issues: list[dict[str, Any]] = list(state.get("review_issues") or [])
    feedback_block = ""
    if prior_issues:
        lines = [f"  - [{i.get('field', '?')}] {i.get('reason', '?')}" for i in prior_issues[:5]]
        feedback_block = "\n審查員反饋（請修正後重新輸出）：\n" + "\n".join(lines) + "\n"
        logger.info(
            "trade_picker_node: retry revision_count=%d with feedback",
            int(state.get("revision_count") or 0),
        )

    revision_count = int(state.get("revision_count") or 0)
    llm = _get_trade_picker_llm()
    structured_llm = llm.with_structured_output(TradePickerOutput)
    human_template = (
        "板塊：{category}\n"
        "主編共識：{arbiter_summary}\n"
        "市場模式：{agreed_regime}\n"
        "系統報價上下文（僅供參考，禁止輸出價格）：\n{price_context}\n"
        "新聞標題：\n{news_blob}\n"
        "{feedback_block}"
    )
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "你是交易篩選編輯。僅輸出 0-2 筆 trade intents。"
                "嚴禁輸出任何價格數字，僅可輸出 asset/direction/star_rating/thesis_one_liner。"
                "star_rating 只能是 1 或 2。若訊號不足，回傳空陣列。"
                + _GRAPH_CONTEXT_PRUNING_RULE,
            ),
            ("human", human_template),
        ]
    )
    _emit_node_event(
        "trade_picker",
        {"category": category, "revision_count": revision_count},
        phase="begin",
        summary=f"Trade picker 呼叫 LLM（{category}，rev={revision_count}）",
        run_id=rid,
        category=gcat,
    )
    try:
        out: TradePickerOutput = (prompt | structured_llm).invoke(
            {
                "category": category,
                "arbiter_summary": arbiter_summary,
                "agreed_regime": agreed_regime or "neutral",
                "price_context": price_context or "（無）",
                "news_blob": news_blob,
                "feedback_block": feedback_block,
            }
        )
    except Exception as exc:
        logger.warning("trade_picker_node failed, fallback to empty: %s", exc)
        _emit_node_event(
            "trade_picker",
            {"intent_count": 0, "category": category, "reason": "error"},
            summary=f"Trade picker 失敗：{exc!s}"[:200],
            run_id=rid,
            category=gcat,
        )
        return {"proposed_trades": [], "review_issues": []}

    intents = [intent.model_dump(mode="json") for intent in out.intents]
    n = len(intents)
    _emit_node_event(
        "trade_picker",
        {"intent_count": n, "category": category},
        summary=f"Trade picker 完成：產出 {n} 筆 intent（{category}）",
        run_id=rid,
        category=gcat,
    )
    # Clear prior review_issues so routing starts fresh for this new picker output.
    return {"proposed_trades": intents, "review_issues": []}


def python_validate_node(state: ResearchGraphState) -> dict[str, Any]:
    """Layer-1 deterministic validator for trade_picker output (no LLM, no token cost).

    Five checks:
      1. Required fields non-empty (asset, direction, star_rating, thesis_one_liner)
      2. direction in {LONG, SHORT}
      3. star_rating in {1, 2}
      4. No duplicate tickers within the same trade_watch
      5. Ticker allowlist: CRYPTO → BTC/ETH only; AI → equity_universe_merged only

    When GRAPH_LLM_REVIEWER=0 (default), this node is a transparent pass-through.
    """
    proposed = list(state.get("proposed_trades") or [])
    revision_count = int(state.get("revision_count") or 0)
    rid = _graph_run_id(state)
    gcat = _graph_category(state)

    if not _reviewer_enabled():
        _emit_node_event(
            "python_validate",
            {
                "passed": True,
                "revision_count": revision_count,
                "trade_count": len(proposed),
                "reason": "reviewer_disabled",
            },
            summary="Python 驗證：審查迴路關閉，略過",
            run_id=rid,
            category=gcat,
        )
        return {
            "trade_candidates": proposed,
            "review_issues": [],
            "trade_watch_final": proposed,
        }

    if not proposed:
        _emit_node_event(
            "python_validate",
            {"passed": True, "revision_count": revision_count, "trade_count": 0},
            summary="Python 驗證：無 trade 可驗",
            run_id=rid,
            category=gcat,
        )
        return {"trade_candidates": [], "review_issues": [], "trade_watch_final": []}

    _emit_node_event(
        "python_validate",
        {"trade_count": len(proposed), "revision_count": revision_count},
        phase="begin",
        summary=f"Python 驗證 {len(proposed)} 筆 trade（rev={revision_count}）",
        run_id=rid,
        category=gcat,
    )

    category = str(state.get("category") or "CRYPTO")
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    for trade in proposed:
        asset = str(trade.get("asset", "")).upper().strip().lstrip("$")
        direction = str(trade.get("direction", ""))
        star_rating = trade.get("star_rating")
        thesis = str(trade.get("thesis_one_liner", "")).strip()

        if not asset:
            issues.append({"field": "asset", "reason": "asset 欄位為空"})
        if not thesis:
            issues.append({"field": "thesis_one_liner", "reason": "thesis_one_liner 為空"})
        if direction not in ("LONG", "SHORT"):
            issues.append({"field": "direction", "reason": f"direction 無效：{direction!r}（須為 LONG 或 SHORT）"})
        if not isinstance(star_rating, int) or star_rating not in (1, 2):
            issues.append({"field": "star_rating", "reason": f"star_rating 須為 1 或 2，得到 {star_rating!r}"})
        if asset:
            if asset in seen:
                issues.append({"field": "asset", "reason": f"重複標的 {asset!r}（trade_watch 不允許重複）"})
            seen.add(asset)
            if not _is_known_ticker(asset, category=category):
                issues.append({"field": "asset", "reason": f"ticker {asset!r} 不在允許清單中（疑似幻覺）"})

    if issues:
        logger.warning(
            "python_validate_node: %d issue(s) at revision_count=%d — %s",
            len(issues),
            revision_count,
            issues[:3],
        )
        _emit_node_event(
            "python_validate",
            {
                "passed": False,
                "revision_count": revision_count,
                "trade_count": len(proposed),
                "issue_count": len(issues),
            },
            summary=f"Python 驗證未過：{len(issues)} 項問題（rev={revision_count}）",
            run_id=rid,
            category=gcat,
        )
        return {
            "trade_candidates": proposed,
            "review_issues": issues,
            "revision_count": revision_count + 1,
        }

    logger.info("python_validate_node: all checks passed (revision_count=%d)", revision_count)
    _emit_node_event(
        "python_validate",
        {"passed": True, "revision_count": revision_count, "trade_count": len(proposed)},
        summary=f"Python 驗證通過：{len(proposed)} 筆（rev={revision_count}）",
        run_id=rid,
        category=gcat,
    )
    return {"trade_candidates": proposed, "review_issues": [], "trade_watch_final": proposed}


def llm_reviewer_node(state: ResearchGraphState) -> dict[str, Any]:
    """Layer-2 LLM reviewer: catches narrative/logic contradictions Python cannot detect.

    Checks:
      1. thesis_one_liner direction vs trade direction consistency
         (e.g. 「看空」thesis with LONG direction is a contradiction)
      2. asset anti-hallucination: ticker should appear in news or raw_data context
         (titles/keys only prove *presence in context*, not prices)
      3. Price / % change / level claims: **only** the Ground Truth block (from
         ``symbol_snapshot_service``) counts as factual market data. News titles and
         raw_data keys must **not** be used as quote evidence. If thesis contains an
         explicit numeric price claim that clearly conflicts with Ground Truth ``last``
         or the latest OHLC close, set passed=false; if there is no explicit price in
         thesis, do **not** infer or sanity-check prices (no invented numbers).

    When GRAPH_LLM_REVIEWER=0, passes through transparently.
    When reviewer is enabled, missing API key or LLM errors fail closed (empty trades)
    unless ``GRAPH_LLM_REVIEWER_FAIL_OPEN=1`` (dev only).
    Uses slim ReviewerVerdict schema — only verdict + issues, never a full rewrite.
    """
    proposed = list(state.get("proposed_trades") or [])
    revision_count = int(state.get("revision_count") or 0)
    rid = _graph_run_id(state)
    gcat = _graph_category(state)

    if not _reviewer_enabled():
        _emit_node_event(
            "llm_reviewer",
            {
                "passed": True,
                "revision_count": revision_count,
                "issues": [],
                "reason": "reviewer_disabled",
            },
            summary="LLM 審查：審查迴路關閉",
            run_id=rid,
            category=gcat,
        )
        return {"review_issues": [], "trade_watch_final": proposed}

    if not proposed:
        _emit_node_event(
            "llm_reviewer",
            {"passed": True, "revision_count": revision_count, "issues": []},
            summary="LLM 審查：無 trade 可審",
            run_id=rid,
            category=gcat,
        )
        return {"review_issues": [], "trade_watch_final": []}

    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        if _reviewer_fail_open():
            logger.info("llm_reviewer_node: OPENAI_API_KEY not set — fail-open pass-through")
            _emit_node_event(
                "llm_reviewer",
                {
                    "passed": True,
                    "revision_count": revision_count,
                    "issues": [],
                    "reason": "missing_api_key",
                },
                summary="LLM 審查：未設定 API key，fail-open 略過",
                run_id=rid,
                category=gcat,
            )
            return {"review_issues": [], "trade_watch_final": proposed}
        logger.warning("llm_reviewer_node: OPENAI_API_KEY not set — fail-closed")
        issues = [{"field": "llm_reviewer", "reason": "OPENAI_API_KEY missing while reviewer enabled"}]
        _emit_node_event(
            "llm_reviewer",
            {
                "passed": False,
                "revision_count": revision_count,
                "issues": issues,
                "reason": "missing_api_key",
            },
            summary="LLM 審查：未設定 API key，fail-closed",
            run_id=rid,
            category=gcat,
        )
        return {"review_issues": issues, "trade_watch_final": [], "revision_count": revision_count + 1}

    raw_news = state.get("raw_news") or []
    news_titles = [
        str(item.get("title", "")).strip()
        for item in raw_news[:8]
        if str(item.get("title", "")).strip()
    ]
    raw_data_keys = list((state.get("raw_data") or {}).keys())[:10]
    trade_lines = "\n".join(
        f"- {t.get('asset')} ({t.get('direction')}) "
        f"star={t.get('star_rating')} thesis={t.get('thesis_one_liner')}"
        for t in proposed
    )

    # Task 1: Fetch live price snapshot BEFORE the LLM call.
    # The reviewer cross-checks Picker logic against this Ground Truth.
    category = str(state.get("category") or "CRYPTO")
    assets_to_fetch = [
        str(t.get("asset", "")).strip().upper().lstrip("$")
        for t in proposed
        if str(t.get("asset", "")).strip()
    ]
    ground_truth_block = _fetch_live_ground_truth(assets_to_fetch, category)
    logger.info("llm_reviewer_node ground_truth: %s", ground_truth_block[:200])

    _emit_node_event(
        "llm_reviewer",
        {"trade_count": len(proposed), "revision_count": revision_count},
        phase="begin",
        summary=f"LLM 審查 {len(proposed)} 筆 trade（rev={revision_count}）",
        run_id=rid,
        category=gcat or category,
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "你是交易意圖審查員。只檢查下列事項，不做其他判斷：\n"
            "1. thesis_one_liner 的敘述方向是否與 direction 一致"
            "（含「看空」「空頭」「下跌」卻是 LONG，或含「看多」「做多」「上漲」卻是 SHORT，則為矛盾）。\n"
            "2. asset 是否出現在新聞標題或資料鍵中（僅用於標的是否曾在脈絡出現，不得當作報價依據）。\n"
            "3. 價格、漲跌幅、價位／技術敘述：**只能**以下方 Ground Truth 區塊內的數字為事實；"
            "新聞標題與 raw_data 鍵名**不得**當作價格或漲跌依據。\n"
            "4. 價格矛盾：僅當 thesis_one_liner 內含**可辨識的具體價格數字**（例如「9 萬」「90000」「$90k」），"
            "且該宣稱與 Ground Truth 的 last 或 ohlc_last 收盤**明顯衝突**時，才列 issue（passed=false）；"
            "若 thesis 無具體價格，**不要**自行推算或臆測價格合理性。\n"
            "若無矛盾：passed=true, issues=[]。\n"
            "若有矛盾：passed=false 並列出具體 issues（field + reason，各一行）。\n"
            "Slim schema only: passed (bool), issues (list of {field, reason}).",
        ),
        (
            "human",
            "Trade intents:\n{trade_lines}\n\n"
            "News titles（僅供標的是否曾出現在脈絡，非報價依據）:\n{news_titles}\n\n"
            "Raw data keys（僅供脈絡鍵名，非報價依據）:\n{raw_data_keys}\n\n"
            "Ground Truth（唯一價格與簡易 OHLC 事實來源）:\n{ground_truth_block}\n",
        ),
    ])

    try:
        llm = _get_reviewer_llm()
        structured_llm = llm.with_structured_output(ReviewerVerdict)
        verdict: ReviewerVerdict = (prompt | structured_llm).invoke({
            "trade_lines": trade_lines or "（無）",
            "news_titles": "\n".join(f"- {t}" for t in news_titles) or "（無）",
            "raw_data_keys": ", ".join(raw_data_keys) or "（無）",
            "ground_truth_block": ground_truth_block,
        })
    except Exception as exc:
        if _reviewer_fail_open():
            logger.warning("llm_reviewer_node error — fail-open pass-through: %s", exc)
            _emit_node_event(
                "llm_reviewer",
                {
                    "passed": True,
                    "revision_count": revision_count,
                    "issues": [],
                    "reason": "fail_open",
                },
                summary=f"LLM 審查例外，fail-open：{exc!s}"[:200],
                run_id=rid,
                category=gcat or category,
            )
            return {"review_issues": [], "trade_watch_final": proposed}
        logger.warning("llm_reviewer_node error — fail-closed: %s", exc)
        issues = [{"field": "llm_reviewer", "reason": f"reviewer_error: {exc}"}]
        _emit_node_event(
            "llm_reviewer",
            {
                "passed": False,
                "revision_count": revision_count,
                "issues": issues,
                "reason": "fail_closed",
            },
            summary=f"LLM 審查例外，fail-closed：{exc!s}"[:200],
            run_id=rid,
            category=gcat or category,
        )
        return {"review_issues": issues, "trade_watch_final": [], "revision_count": revision_count + 1}

    if verdict.passed:
        logger.info("llm_reviewer_node: passed (revision_count=%d)", revision_count)
        _emit_node_event(
            "llm_reviewer",
            {"passed": True, "revision_count": revision_count, "issues": []},
            summary=f"LLM 審查通過（rev={revision_count}）",
            run_id=rid,
            category=gcat or category,
        )
        return {"review_issues": [], "trade_watch_final": proposed}

    issues = [{"field": i.field, "reason": i.reason} for i in verdict.issues]
    logger.warning(
        "llm_reviewer_node: %d issue(s) at revision_count=%d — %s",
        len(issues),
        revision_count,
        issues[:3],
    )
    _emit_node_event(
        "llm_reviewer",
        {"passed": False, "revision_count": revision_count, "issues": issues[:5]},
        summary=f"LLM 審查未過：{len(issues)} 項（rev={revision_count}）",
        run_id=rid,
        category=gcat or category,
    )
    return {"review_issues": issues, "revision_count": revision_count + 1}


def degrade_node(state: ResearchGraphState) -> dict[str, Any]:
    """Hard-cap fallback: mark degraded and clear trade_watch_final for downstream safety.

    Review issues remain in state for logging; trades are not promoted to the report
    or execution-intent store when the reviewer loop exhausts retries.
    Writes a reviewer_log entry to BigQuery (best-effort, non-blocking).
    """
    review_issues = list(state.get("review_issues") or [])
    revision_count = int(state.get("revision_count") or 0)

    logger.warning(
        "degrade_node: hard cap hit (revision_count=%d). "
        "Clearing trade_watch_final (degraded=True). Unresolved issues: %s",
        revision_count,
        review_issues[:3],
    )
    _write_reviewer_log_safe(state, degraded=True)
    return {"degraded": True, "trade_watch_final": []}


def _write_reviewer_log_safe(state: ResearchGraphState, *, degraded: bool) -> None:
    """Best-effort BQ reviewer_log write; never raises (non-blocking)."""
    try:
        from bigquery_writer import write_reviewer_log  # lazy import avoids circular deps

        review_issues = list(state.get("review_issues") or [])
        run_id = str(state.get("graph_run_id") or "")
        category = str(state.get("category") or "CRYPTO")
        revision_count = int(state.get("revision_count") or 0)
        trade_watch_final = list(state.get("trade_watch_final") or state.get("proposed_trades") or [])

        write_reviewer_log(
            run_id=run_id,
            profile=None,
            track=category.lower(),
            revision_count=revision_count,
            python_fail_reasons=[i.get("reason", "") for i in review_issues][:10],
            llm_fail_reasons=[],
            degraded=degraded,
            final_trade_count=len(trade_watch_final),
            total_latency_ms=0,
        )
    except Exception as exc:
        logger.debug("_write_reviewer_log_safe skipped (non-blocking): %s", exc)


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

    import scratchpad

    _t0 = time.perf_counter()
    _rounds_used = 0
    _tool_names_flat: list[str] = []
    _unknown_tool_hits = 0
    _tool_invoke_errors = 0

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
        _rounds_used += 1

        if not response.tool_calls:
            break

        _names = [_tool_call_name(tc) for tc in response.tool_calls]
        _tool_names_flat.extend(n for n in _names if n)
        logger.info(
            "Deep Research tool_calls: %s",
            _names,
        )
        for tc in response.tool_calls:
            name = _tool_call_name(tc)
            selected = tool_map.get(name)
            if not selected:
                _unknown_tool_hits += 1
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
                _tool_invoke_errors += 1
                out_s = f"工具執行失敗: {exc}"
            tool_excerpts.append(f"【來自 {name} 的真實數據】\n{out_s}")
            messages.append(
                ToolMessage(content=out_s, tool_call_id=_tool_call_id(tc) or name)
            )

    synthesis = (last_ai.content or "").strip() if last_ai else ""
    _elapsed_ms = round((time.perf_counter() - _t0) * 1000.0, 2)
    _finish = "incomplete"
    if tool_excerpts and synthesis:
        _finish = "tools_and_synthesis"
    elif synthesis:
        _finish = "synthesis_only"
    elif tool_excerpts:
        _finish = "tools_only"
    try:
        scratchpad.append_graph_deep_research_metrics(
            {
                "rounds_used": _rounds_used,
                "tool_calls_total": len(_tool_names_flat),
                "tool_names_sample": _tool_names_flat[:12],
                "elapsed_ms": _elapsed_ms,
                "chars_out": len(synthesis) + sum(len(x) for x in tool_excerpts),
                "unknown_tool_hits": _unknown_tool_hits,
                "tool_invoke_errors": _tool_invoke_errors,
                "finish_kind": _finish,
            }
        )
    except Exception:
        logger.debug("graph_deep_research_metrics scratchpad append skipped", exc_info=True)

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

    registry = _tool_registry()

    if category == "CRYPTO":
        patch["deep_onchain_probe"] = registry.get_snapshot("onchain_metrics_tool")
        patch["deep_prediction_probe"] = registry.get_snapshot("prediction_markets_tool")
    else:
        probe = query if query else "watchlist"
        patch["deep_fundamentals_probe"] = registry.get_snapshot("financial_datasets_tool", probe)
        patch["deep_prediction_probe"] = registry.get_snapshot("prediction_markets_tool")

    investigation = "\n".join(f"{k}: {v}" for k, v in patch.items() if k != "deep_dive_query")
    return {
        "raw_data": {new_data_key: f"針對【{query}】查核結果：\n{investigation}"},
        "research_depth": depth + 1,
    }


def deep_filing_analysis_node(state: ResearchGraphState) -> dict[str, Any]:
    """Optional NotebookLM filing analysis; disabled/no-data paths are no-ops."""
    if state.get("category") != "AI":
        return {}
    if not _state_hits_keywords(state, _FILING_TRIGGER_KEYWORDS):
        return {}

    from tools.notebooklm_tool import notebooklm_enabled, notebooklm_query_many

    if not notebooklm_enabled():
        return {}

    ticker = _extract_equity_ticker(state)
    notebook_id = os.getenv("NOTEBOOKLM_NOTEBOOK_ID", "").strip()
    questions = [
        f"{ticker} 最新 filing 的營收／毛利率變化是什麼？請附頁碼引用。",
        f"{ticker} filing 中有哪些風險因子或管理層語氣變化？請附頁碼引用。",
        f"{ticker} 的現金流、capex 或客戶集中度有何值得追蹤之處？請附頁碼引用。",
    ]
    start = time.perf_counter()
    status = "degraded"
    try:
        rows = notebooklm_query_many(questions, notebook_id=notebook_id)
        answers: dict[int, str] = {}
        citations: dict[int, list[dict[str, Any]]] = {}
        for idx, row in rows.items():
            answer = str((row or {}).get("answer", "")).strip()
            if not answer or "[DATA_MISSING:" in answer:
                continue
            raw_citations = (row or {}).get("citations")
            if isinstance(raw_citations, str):
                raw_citations = [raw_citations] if raw_citations.strip() else []
            elif not raw_citations:
                raw_citations = []
            valid_citations: list[dict[str, Any]] = []
            for raw in raw_citations:
                if isinstance(raw, str):
                    s = raw.strip()
                    if not s:
                        continue
                    raw = {"excerpt": s}
                try:
                    valid_citations.append(Citation.model_validate(raw).model_dump(mode="json"))
                except Exception:
                    continue
            if not valid_citations:
                continue
            from schemas import _coerce_question_key
            ikey = _coerce_question_key(idx)
            answers[ikey] = answer
            citations[ikey] = valid_citations

        if not answers:
            return {"raw_data": {"deep_filing_analysis": "[DATA_MISSING:notebooklm_no_cited_answers]"}}

        analysis = DeepFilingAnalysis.model_validate(
            {
                "ticker": ticker,
                "filing_type": "filing",
                "answers": answers,
                "citations": citations,
                "red_flags": [],
            }
        )
        status = "success"
        payload = analysis.model_dump(mode="json")
        return {
            "deep_filing_analysis": payload,
            "raw_data": {"deep_filing_analysis": payload},
        }
    except Exception as exc:
        logger.warning("deep_filing_analysis_node skipped: %s", exc)
        return {"raw_data": {"deep_filing_analysis": f"[DATA_MISSING:notebooklm_error] {exc}"}}
    finally:
        try:
            from bigquery_writer import write_notebooklm_cost_log

            write_notebooklm_cost_log(
                run_id=str(state.get("graph_run_id", "")),
                notebook_id=notebook_id,
                ticker=ticker,
                question_count=len(questions),
                status=status,
                latency_ms=int((time.perf_counter() - start) * 1000),
                metadata={"node": "deep_filing_analysis_node"},
            )
        except Exception:
            logger.debug("NotebookLM cost log skipped", exc_info=True)


def agency_researcher_node(state: ResearchGraphState) -> dict[str, Any]:
    """Optional Agency-style structured finance research; no-op unless enabled."""
    if state.get("category") != "AI":
        return {}

    from agents.agency import agency_research_enabled, load_agency_template

    if not agency_research_enabled():
        return {}
    if not state.get("deep_filing_analysis") and not _state_hits_keywords(state, _AGENCY_TRIGGER_KEYWORDS):
        return {}

    template = load_agency_template("investment_researcher.md")
    if not (template.core_mission or template.deliverables):
        return {}

    ticker = _extract_equity_ticker(state)
    deep = state.get("deep_filing_analysis") if isinstance(state.get("deep_filing_analysis"), dict) else {}
    first_answer = ""
    first_citation: dict[str, Any] | None = None
    if deep:
        answers = deep.get("answers") if isinstance(deep.get("answers"), dict) else {}
        citations = deep.get("citations") if isinstance(deep.get("citations"), dict) else {}
        for key, answer in answers.items():
            cite_raw = citations.get(key)
            if cite_raw is None:
                cite_raw = citations.get(str(key))
            if isinstance(cite_raw, str):
                cite_rows: list[Any] = [{"excerpt": cite_raw.strip()}] if cite_raw.strip() else []
            elif isinstance(cite_raw, dict):
                cite_rows = [cite_raw]
            elif isinstance(cite_raw, list):
                cite_rows = cite_raw
            else:
                cite_rows = []
            if answer and cite_rows:
                first_answer = str(answer).strip()
                fc = cite_rows[0]
                first_citation = fc if isinstance(fc, dict) else {"excerpt": str(fc).strip()}
                break

    if not first_citation:
        first_citation = {
            "section": "Agency template",
            "excerpt": template.core_mission or "Agency fallback template",
        }
    content = first_answer or (template.deliverables[0] if template.deliverables else template.core_mission)
    try:
        output = AgencyResearchOutput(
            agent_type="investment_researcher",
            ticker=ticker,
            deliverables=[
                AgencyDeliverable(
                    name="可驗證研究補充",
                    content=content,
                    confidence="low",
                    citations=[Citation.model_validate(first_citation)],
                )
            ],
            risk_register=list(template.critical_rules[:3]),
            success_metrics={"fallback_template": str(bool(template.fallback)).lower()},
        )
        agency_payload = output.model_dump(mode="json")
        return {
            "agency_research_output": agency_payload,
            "raw_data": {"agency_research_output": output.model_dump(mode="json")},
        }
    except Exception as exc:
        logger.warning("agency_researcher_node skipped: %s", exc)
        return {"raw_data": {"agency_research_output": f"[DATA_MISSING:agency_research_error] {exc}"}}


def final_formatter_node(state: ResearchGraphState) -> dict[str, Any]:
    """Final formatter with legacy fallback and native structured mode."""
    category = state["category"]
    rid = _graph_run_id(state)
    fmt_cat = _graph_category(state) or str(category)
    if _formatter_uses_legacy_crews():
        logger.info("--- [Node] Final Formatter (Legacy Crew) 啟動 ---")
        _emit_node_event(
            "final_formatter",
            {"category": category, "degraded": bool(state.get("degraded"))},
            phase="begin",
            summary=f"最終排版（Legacy，{category}）",
            run_id=rid,
            category=fmt_cat,
        )
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
            updates: dict[str, Any] = {}
            if state.get("deep_filing_analysis"):
                updates["deep_filing_analysis"] = state.get("deep_filing_analysis")
            agency_payload = normalize_optional_agency_research_output(
                state.get("agency_research_output")
            )
            if agency_payload is not None:
                updates["agency_research_output"] = agency_payload
            if updates:
                section = section.model_copy(update=updates)
        degraded = bool(state.get("degraded"))
        _emit_node_event(
            "final_formatter",
            {"category": category, "degraded": degraded},
            summary="Legacy 排版完成" + ("（degraded）" if degraded else ""),
            run_id=rid,
            category=fmt_cat,
        )
        _persist_reviewed_execution_intents(state)
        return {"final_report": section.model_dump(mode="json"), "needs_deep_dive": False}

    _emit_node_event(
        "final_formatter",
        {"category": category, "degraded": bool(state.get("degraded"))},
        phase="begin",
        summary=f"最終排版（Native，{category}）",
        run_id=rid,
        category=fmt_cat,
    )
    logger.info("--- [Node] Final Formatter (Native Structured Output) 啟動 ---")
    llm = _get_formatter_llm()
    packet = _build_formatter_input_packet(state)
    packet_json = json.dumps(packet.model_dump(mode="json"), ensure_ascii=False, indent=2)

    if category == "CRYPTO":
        structured_llm = llm.with_structured_output(CryptoFormatterNarrative)
        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "你是 Q-Silicon 最終排版總編。"
                "你只能根據提供的內部簡報生成內容，禁止捏造新聞、價格、代碼、交易腿。"
                "輸出需精簡、機構語氣、可直接寫入 JSON 欄位。"
                + _GRAPH_CONTEXT_PRUNING_RULE,
            ),
            (
                "human",
                "板塊：CRYPTO\n\n"
                "內部簡報（唯一資料來源，結構化封包 JSON）：\n{packet_json}",
            ),
        ])
        chain = prompt | structured_llm
        try:
            slim = chain.invoke(
                {
                    "packet_json": packet_json,
                }
            )
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
                "輸出需精簡、機構語氣、可直接寫入 JSON 欄位。"
                + _GRAPH_CONTEXT_PRUNING_RULE,
            ),
            (
                "human",
                "板塊：AI\n\n"
                "內部簡報（唯一資料來源，結構化封包 JSON）：\n{packet_json}",
            ),
        ])
        chain = prompt | structured_llm
        try:
            slim = chain.invoke(
                {
                    "packet_json": packet_json,
                }
            )
            section = _assemble_ai_section(state, slim)
        except Exception as exc:
            logger.error("Native formatter (AI) failed: %s", exc)
            raise RuntimeError(f"Native formatter failed for AI: {exc}") from exc

    if not state.get("degraded"):
        _write_reviewer_log_safe(state, degraded=False)
    degraded_end = bool(state.get("degraded"))
    _emit_node_event(
        "final_formatter",
        {"category": category, "degraded": degraded_end},
        summary="最終排版完成" + ("（degraded）" if degraded_end else ""),
        run_id=rid,
        category=fmt_cat,
    )
    _persist_reviewed_execution_intents(state)
    return {"final_report": section.model_dump(mode="json"), "needs_deep_dive": False}
