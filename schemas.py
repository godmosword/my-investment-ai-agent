"""
Structured daily-brief contract (Pydantic v2).

Field descriptions are consumed by CrewAI output_pydantic as JSON Schema hints for the LLM.
Use Optional / defaults for sparse tool data so one missing field does not fail the whole parse.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class TradeRecommendation(BaseModel):
    """Single QSREC row; must stay JSON-serializable for tracker / BigQuery."""

    asset: str = Field(
        ...,
        description="Ticker without $, uppercase (e.g. BTC, NVDA, or BTC/SOL for pair).",
    )
    direction: Literal["LONG", "SHORT"] = Field(
        ...,
        description="Net direction for this leg or pair.",
    )
    current_price: float = Field(
        ...,
        description="Last price or reference mark used for the thesis.",
    )
    entry: float = Field(..., description="Planned entry price (number only).")
    target: float = Field(..., description="Target price (number only).")
    stop: float = Field(..., description="Stop loss price (number only).")
    confidence: int = Field(
        ...,
        ge=1,
        le=4,
        description="Star level 1–4 (maps to conviction / position sizing).",
    )
    category: Literal["CRYPTO", "EQUITY"] = Field(
        ...,
        description="CRYPTO for digital assets; EQUITY for US stocks.",
    )
    narrative: str = Field(
        default="",
        description="One tight sentence: fundamental or technical root cause; avoid bullet lists.",
    )
    trigger: str = Field(
        default="",
        description="Activation / trigger condition, concrete and testable.",
    )
    invalidation: str = Field(
        default="",
        description="Invalidation condition; must be non-empty for actionable trades.",
    )
    position_pct: float = Field(
        default=0.0,
        description="Suggested % of total capital for this idea (align with regime caps).",
    )
    timeframe: str = Field(
        default="",
        description="Holding horizon text e.g. 3-5天.",
    )
    selection_score: float | None = Field(
        default=None,
        description="Final 0–100 selection score; required when gate strict scoring is on.",
    )
    catalyst_score: float | None = Field(default=None, description="0–100 catalyst dimension.")
    flow_score: float | None = Field(default=None, description="0–100 flow dimension.")
    technical_score: float | None = Field(default=None, description="0–100 technical dimension.")
    risk_fit_score: float | None = Field(default=None, description="0–100 risk-fit dimension.")
    execution_score: float | None = Field(default=None, description="0–100 execution dimension.")
    alt_candidate_score: float | None = Field(
        default=None,
        description="Score of next-best same-category alternative.",
    )
    score_gap: float | None = Field(
        default=None,
        description="selection_score − alt_candidate_score; do not fabricate.",
    )
    repeat_days: int = Field(
        default=0,
        ge=0,
        description="Consecutive days the same pick is held; 0 if first day.",
    )
    rr_ratio: float | None = Field(default=None, description="Reward:risk ratio number if computed.")
    max_drawdown_pct: float | None = Field(default=None, description="Negative percent drawdown risk.")
    expected_win_rate: float | None = Field(default=None, description="Expected win rate percent.")
    signal_score: float | None = Field(default=None, description="0–100 composite signal score.")
    regime: str | None = Field(
        default=None,
        description="Optional regime tag echo risk_on/risk_off/neutral for this leg.",
    )


class NewsItem(BaseModel):
    """One core news row; plain text only — templates add Telegram HTML."""

    index: int = Field(..., ge=1, le=6, description="Global index 1–6 across crypto+AI sections.")
    timestamp_line: str = Field(
        ...,
        description="Bracketed time e.g. [03/22 09:30 UTC+8] without 〔新聞〕 prefix.",
    )
    title: str = Field(..., description="Headline plain text.")
    source_and_nature: str = Field(
        ...,
        description="Source name and nature: confirmed / likely / unverified rumor.",
    )
    summary: str = Field(
        ...,
        description="One factual sentence ≤40 chars ideal; no editorial opinion.",
    )
    investment_takeaway: str = Field(
        ...,
        description="1–2 sentences ≤90 chars total ideally; must embed at least one numeric datum from dashboard.",
    )
    editor_consensus: str = Field(
        ...,
        description="One sentence ≤28 chars naming a concrete ticker.",
    )


class MetricLine(BaseModel):
    """Single dashboard row."""

    label: str = Field(..., description="Indicator display name.")
    value: str = Field(
        ...,
        description="Reading or N/A; plain text, templates wrap in <code>.",
    )
    status_emoji: str | None = Field(
        default=None,
        description="Optional ✅ ❌ ⬜ prefix for regime scorecard style lines.",
    )


_CHATTER_CRED_INLINE_RE = re.compile(
    r'可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b'
    r'|來源[：:]\s*[ABC](?:級|等級)?'
    r'|可信度\s*[ABC](?:級|等)?'
    r'|(?:Grade|Credibility)\s*[：:]\s*(?:A|B|C|\d{1,3})\b',
    re.IGNORECASE,
)


class ChatterItem(BaseModel):
    """Rumor / whisper line; must carry credibility for gate."""

    text: str = Field(
        ...,
        description=(
            "Single line ending （未確認） with source tier A/B/C or 0–100 and MSM re-verify yes/no. "
            "Must contain credibility marker e.g. 可信度：B or Credibility：72/100."
        ),
    )
    credibility: str | None = Field(
        default=None,
        description="Credibility grade A/B/C or 0–100. Auto-injected into text if marker is absent.",
    )

    @model_validator(mode="after")
    def _inject_credibility_into_text(self) -> "ChatterItem":
        """Ensure text contains a credibility marker; fall back to credibility field or C grade."""
        if not _CHATTER_CRED_INLINE_RE.search(self.text):
            grade = self.credibility or "C"
            self.text = self.text.rstrip() + f"｜可信度：{grade}（自動補填）"
        return self


_LABEL_PREFIX_RE = re.compile(
    r'^(?:本日選擇理由|今日風險預算|訊號衝突摘要)[：:]\s*',
    re.IGNORECASE,
)


class ExecutableTradeLeg(BaseModel):
    """One rendered trade bullet group in block ④ (before QSREC)."""

    asset: str = Field(..., description="Ticker symbol WITHOUT leading $, uppercase (e.g. BTC, BTC/SOL, NVDA). The template prepends $ automatically.")

    @field_validator("asset", mode="before")
    @classmethod
    def _strip_dollar_prefix(cls, v: object) -> object:
        """Strip accidental leading $ so template doesn't emit $$TICKER."""
        if isinstance(v, str):
            return v.lstrip("$")
        return v
    direction: Literal["LONG", "SHORT"] = Field(...)
    current_price: str = Field(..., description="Display string for spot mark.")
    star_rating: int = Field(..., ge=1, le=4, description="Confidence stars count 1–4.")
    entry: str = Field(..., description="Numeric string for entry.")
    target: str = Field(..., description="Numeric string for target plus optional (+x%) in same cell.")
    stop: str = Field(..., description="Numeric string for stop plus optional (-x%) in same cell.")
    rr: str = Field(..., description="e.g. 1:2.5 inside R:R line.")
    max_drawdown_pct: str = Field(..., description="e.g. -3.2%")
    expected_win_rate: str = Field(..., description="e.g. 56%")
    signal_score: str = Field(..., description="e.g. 62/100")
    trigger: str = Field(default="", description="Trigger mode one line.")
    sizing_logic: str = Field(default="", description="Position scaling logic one line.")
    invalidation: str = Field(default="", description="Invalidation one line non-empty when actionable.")
    position_pct: str = Field(default="", description="Portfolio % guidance line.")
    narrative: str = Field(default="", description="Short catalyst tie-in.")


class MarketRegimeBlock(BaseModel):
    """Regime header + optional scorecard lines (plain text)."""

    regime: Literal["risk_on", "risk_off", "neutral"] = Field(
        ...,
        description="Single authoritative regime for the full brief.",
    )
    score_suffix: str = Field(
        default="",
        description="Parenthetical after regime e.g. （+4/6） on the first regime line.",
    )
    scorecard_lines: list[str] = Field(
        default_factory=list,
        description="Extra ✅/❌ lines with readings; plain text, template wraps each value in <code> where needed.",
    )


class CryptoSection(BaseModel):
    """Crypto crew final structured output."""

    report_title_date: str = Field(
        ...,
        description="YYYY-MM-DD for Daily Brief subtitle (UTC+8 run day).",
    )
    market: MarketRegimeBlock
    narrative_of_day: str = Field(
        ...,
        description="今日主敘事 one line ≤45 chars; must not contradict regime.",
    )
    macro_framework_lines: list[str] = Field(
        default_factory=list,
        description="≤4 lines ≤60 chars each for 美債/Fed/財報等 macro bullets.",
    )
    dashboard: list[MetricLine] = Field(
        ...,
        description="Crypto block ① metrics; one MetricLine per row.",
    )
    news: list[NewsItem] = Field(
        default_factory=list,
        description="Target 3 items with index 1–3; pipeline may pad tier if short.",
    )
    x_highlights: list[str] = Field(
        default_factory=list,
        description="Optional X/Twitter picks; omit if no data.",
    )
    chatter: list[ChatterItem] = Field(
        default_factory=list,
        description="2–3 rumor lines with credibility markers.",
    )
    pick_reason: str = Field(
        ...,
        description="本日選擇理由 body text ONLY — do NOT include the label '本日選擇理由：' as prefix.",
    )
    risk_budget_summary: str = Field(
        ...,
        description="今日風險預算 body text ONLY — do NOT include the label '今日風險預算：' as prefix.",
    )
    signal_conflict_summary: str = Field(
        ...,
        description="訊號衝突摘要 body text ONLY — do NOT include the label '訊號衝突摘要：' as prefix. ≤75 chars.",
    )
    trade_legs: list[ExecutableTradeLeg] = Field(
        default_factory=list,
        description="Executable legs; if empty, pipeline may inject watch-mode via assembly.",
    )
    qsrec: list[TradeRecommendation] = Field(
        default_factory=list,
        description="CRYPTO category recommendations for QSREC JSON block.",
    )

    @field_validator("pick_reason", "risk_budget_summary", "signal_conflict_summary", mode="before")
    @classmethod
    def _strip_label_prefix(cls, v: object) -> object:
        """Strip accidental label prefix so template doesn't emit '本日選擇理由：本日選擇理由：...'."""
        if isinstance(v, str):
            return _LABEL_PREFIX_RE.sub("", v)
        return v


class AISection(BaseModel):
    """AI / US equities crew structured output."""

    macro_bridge_lines: list[str] = Field(
        default_factory=list,
        description=(
            "1–2 lines connecting macro context to AI equities impact. "
            "Do NOT repeat UST/SOFR/VIX values already shown in 加密宏觀框架. "
            "Focus on the specific implication for AI growth stocks (e.g. valuation compression, capex outlook)."
        ),
    )
    dashboard: list[MetricLine] = Field(
        ...,
        description="AI block ① metrics (model momentum etc.).",
    )
    news: list[NewsItem] = Field(
        default_factory=list,
        description="Target 3 items with index 4–6; pipeline may pad tier if short.",
    )
    x_highlights: list[str] = Field(
        default_factory=list,
        description="Optional X picks.",
    )
    chatter: list[ChatterItem] = Field(
        default_factory=list,
        description="2–3 AI supply-chain chatter lines with credibility.",
    )
    pick_reason: str = Field(
        ...,
        description="本日選擇理由 body text ONLY — do NOT include the label '本日選擇理由：' as prefix.",
    )
    signal_conflict_summary: str = Field(
        ...,
        description="訊號衝突摘要 body text ONLY — do NOT include the label '訊號衝突摘要：' as prefix.",
    )

    @field_validator("pick_reason", "signal_conflict_summary", mode="before")
    @classmethod
    def _strip_label_prefix(cls, v: object) -> object:
        """Strip accidental label prefix so template doesn't emit duplicate label."""
        if isinstance(v, str):
            return _LABEL_PREFIX_RE.sub("", v)
        return v
    us_equity_allocation_note: str | None = Field(
        default=None,
        description="Optional 美股部位框 line body text.",
    )
    trade_legs: list[ExecutableTradeLeg] = Field(
        default_factory=list,
        description="Two US equity legs typically.",
    )
    qsrec: list[TradeRecommendation] = Field(
        default_factory=list,
        description="EQUITY category rows for QSREC.",
    )


class DailyBriefReport(BaseModel):
    """Assembled root object: crypto + AI crews + pipeline-injected fields."""

    crypto: CryptoSection
    ai: AISection
    source_observability_block: str = Field(
        default="",
        description="Injected by main.py before render; not from LLM.",
    )
    previous_recs_html: str = Field(
        default="",
        description="Canonical 上期建議追蹤 HTML from BigQuery; injected by main.",
    )
    report_tier_partial_news: bool = Field(
        default=False,
        description="When True, template emits [REPORT_TIER:PARTIAL_NEWS] and 新聞資料狀態 block.",
    )

    def all_qsrec(self) -> list[TradeRecommendation]:
        return list(self.crypto.qsrec) + list(self.ai.qsrec)

    def tagged_news_count(self) -> int:
        return len(self.crypto.news) + len(self.ai.news)
