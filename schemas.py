"""
Structured daily-brief contract (Pydantic v2).

Field descriptions are consumed by CrewAI output_pydantic as JSON Schema hints for the LLM.
Use Optional / defaults for sparse tool data so one missing field does not fail the whole parse.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# Keywords that signal a bullish or bearish stance in editor_consensus free text.
# Used by _warn_consensus_direction_mismatch to detect direction conflicts.
_BULLISH_KW: frozenset[str] = frozenset({
    "領頭羊", "增強", "增長", "看漲", "買入", "支撐", "反彈", "上漲",
    "bullish", "long", "upside", "rally", "surge", "growth", "買", "多",
})
_BEARISH_KW: frozenset[str] = frozenset({
    "看跌", "做空", "拋售", "賣出", "承壓", "疑慮", "下行", "削減",
    "bearish", "short", "downside", "压力", "空", "賣",
})


def _check_consensus_direction(
    news_items: "list[NewsItem]",
    trade_legs: "list[ExecutableTradeLeg]",
) -> None:
    """Warn when an editor_consensus mentions a traded ticker with a conflicting stance.

    This is a non-blocking heuristic check. It logs warnings that will surface in CI
    logs and Telegram gate alerts to help identify LLM self-contradiction before the
    report reaches users.
    """
    if not trade_legs or not news_items:
        return
    trade_dir: dict[str, str] = {leg.asset.upper(): leg.direction for leg in trade_legs}
    for item in news_items:
        consensus_lower = item.editor_consensus.lower()
        for asset, direction in trade_dir.items():
            # Match the ticker or its first 4 chars (e.g. "NVDA" in "NVIDIA")
            if asset.lower() not in consensus_lower and asset[:4].lower() not in consensus_lower:
                continue
            has_bullish = any(kw in consensus_lower for kw in _BULLISH_KW)
            has_bearish = any(kw in consensus_lower for kw in _BEARISH_KW)
            if direction == "SHORT" and has_bullish and not has_bearish:
                logger.warning(
                    "主編共識方向衝突：%s 倉位 SHORT，但 News %d editor_consensus 含看漲語氣：%r",
                    asset, item.index, item.editor_consensus,
                )
            elif direction == "LONG" and has_bearish and not has_bullish:
                logger.warning(
                    "主編共識方向衝突：%s 倉位 LONG，但 News %d editor_consensus 含看跌語氣：%r",
                    asset, item.index, item.editor_consensus,
                )


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
    # ── P4：三情境分析（選填；信心 ≥ 3 星時強制填入）─────────────────────
    bull_scenario: str | None = Field(
        default=None,
        description=(
            "Bull scenario one line ≤40 chars: target price + trigger condition. "
            "Required when confidence ≥ 3."
        ),
    )
    base_scenario: str | None = Field(
        default=None,
        description=(
            "Base scenario one line ≤40 chars: expected outcome + estimated probability %. "
            "Required when confidence ≥ 3."
        ),
    )
    bear_scenario: str | None = Field(
        default=None,
        description=(
            "Bear scenario one line ≤40 chars: invalidation level + trigger. "
            "Required when confidence ≥ 3."
        ),
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
        description=(
            "One sentence ≤28 chars naming a concrete ticker. "
            "MUST align with the section's trade direction: if the section trades a ticker SHORT, "
            "this line must NOT express a bullish stance on that ticker, and vice versa."
        ),
    )


class MetricLine(BaseModel):
    """Single dashboard row."""

    label: str = Field(..., description="Indicator display name.")
    value: str = Field(
        ...,
        description="Reading or N/A; plain text, templates wrap in <code>. Must be single-line.",
    )
    status_emoji: str | None = Field(
        default=None,
        description="Optional ✅ ❌ ⬜ prefix for regime scorecard style lines.",
    )

    @field_validator("value", mode="before")
    @classmethod
    def _normalize_value_newlines(cls, v: object) -> object:
        """Replace literal \\n escape sequences and real newlines with a space.

        LLMs occasionally emit value fields containing literal backslash-n (e.g.
        "N/A\\n第三方資料源未回傳"), which renders as visible \\n in Telegram output.
        Collapse all variants to a single space so the value stays on one line.
        """
        if isinstance(v, str):
            # Replace literal two-char sequence backslash+n, then real newlines
            return v.replace("\\n", " ").replace("\n", " ").replace("\r", " ").strip()
        return v


_CHATTER_CRED_INLINE_RE = re.compile(
    r'可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b'
    r'|來源[：:]\s*[ABC](?:級|等級)?'
    r'|可信度\s*[ABC](?:級|等)?'
    r'|(?:Grade|Credibility)\s*[：:]\s*(?:A|B|C|\d{1,3})\b',
    re.IGNORECASE,
)


_CREDIBILITY_NUMERIC_RE = re.compile(r'^(\d{1,3})(?:/100)?$')


def _normalize_credibility_grade(raw: str) -> str:
    """Convert numeric credibility (e.g. '65' or '65/100') to A/B/C letter grade.

    Score mapping: ≥75 → A, ≥50 → B, <50 → C.
    Already-letter values pass through unchanged.
    """
    m = _CREDIBILITY_NUMERIC_RE.match(raw.strip())
    if m:
        score = int(m.group(1))
        if score >= 75:
            return "A"
        if score >= 50:
            return "B"
        return "C"
    return raw  # already a letter grade or unknown


class ChatterItem(BaseModel):
    """Rumor / whisper line; must carry credibility for gate."""

    text: str = Field(
        ...,
        description=(
            "Single line ending （未確認） with source tier A/B/C and MSM re-verify yes/no. "
            "Must contain credibility marker e.g. 可信度：B. Use ONLY letter grades A/B/C, "
            "not numeric scores — the pipeline normalizes numeric inputs but letter grades "
            "are the canonical format."
        ),
    )
    credibility: str | None = Field(
        default=None,
        description=(
            "Credibility grade A/B/C (canonical) or 0–100 numeric (auto-converted to letter). "
            "A: high confidence (≥75/100); B: moderate (50–74/100); C: low (<50/100)."
        ),
    )

    @field_validator("credibility", mode="before")
    @classmethod
    def _normalize_credibility(cls, v: object) -> object:
        """Normalize numeric credibility scores to A/B/C letter grades."""
        if isinstance(v, str) and v.strip():
            return _normalize_credibility_grade(v)
        return v

    @model_validator(mode="after")
    def _inject_credibility_into_text(self) -> "ChatterItem":
        """Ensure text contains a credibility marker; fall back to credibility field or C grade.

        Also normalizes any inline numeric marker (e.g. 可信度：65/100) to letter grade.
        """
        # Normalize numeric inline markers already present in text
        def _replace_numeric_cred(m: re.Match) -> str:
            full = m.group(0)
            # Extract numeric portion if present
            num_m = re.search(r'(\d{1,3})(?:/100)?', full)
            if num_m:
                grade = _normalize_credibility_grade(num_m.group(0))
                return re.sub(r'\d{1,3}(?:/100)?', grade, full, count=1)
            return full

        self.text = re.sub(
            r'(?:可信度[：:]\s*)(\d{1,3})(?:/100)?',
            lambda m: m.group(0).split(m.group(1))[0] + _normalize_credibility_grade(m.group(1)),
            self.text,
        )

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
        description=(
            "訊號衝突摘要 body text ONLY — do NOT include the label '訊號衝突摘要：' as prefix. ≤75 chars. "
            "P4: include the two-line ╌辯論摘要╌ from Risk Critic verbatim if available "
            "(最強空方論點 + 多方反駁核心), keeping total ≤120 chars."
        ),
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

    @model_validator(mode="after")
    def _warn_consensus_direction_mismatch(self) -> "CryptoSection":
        _check_consensus_direction(self.news, self.trade_legs)
        return self


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
        description=(
            "訊號衝突摘要 body text ONLY — do NOT include the label '訊號衝突摘要：' as prefix. "
            "P4: include ╌辯論摘要╌ two-line block from Risk Critic when available."
        ),
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

    @model_validator(mode="after")
    def _warn_consensus_direction_mismatch(self) -> "AISection":
        _check_consensus_direction(self.news, self.trade_legs)
        return self


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
