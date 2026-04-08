"""
Structured daily-brief contract (Pydantic v2).

Field descriptions are consumed by CrewAI output_pydantic as JSON Schema hints for the LLM.
Use Optional / defaults for sparse tool data so one missing field does not fail the whole parse.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from validation_rules import (
    ensure_news_timestamp_line_utc8,
    sanitize_us_treasury_yield_tokens_in_line,
)

logger = logging.getLogger(__name__)

# Stripped from Telegram [QSREC_START]…[QSREC_END] JSON (internal CoT only).
QSREC_JSON_EXCLUDE_FIELDS: frozenset[str] = frozenset({"internal_reasoning"})

_NARRATIVE_FEW_SHOT = (
    "【風格】主詞或數據開頭，結論收束；冷靜俐落。"
    "❌「因為今天 VIX 飆升到 29.39 且期限倒掛，市場很恐慌，所以我們建議做空微軟避險，倉位約 1.5%。」"
    "✅「VIX 29.39 期限結構倒掛，急性避險升溫；高利率壓軟體估值，MSFT 防禦性空頭配置。」"
)

# Trade card / QSREC 對外 narrative：過短易被截斷難讀；過長影響 Telegram 密度。
_NARRATIVE_DISPLAY_MAX_CHARS = 85


def _cap_internal_field(v: object, *, max_len: int = 4000) -> object:
    if isinstance(v, str) and len(v) > max_len:
        logger.warning("internal_reasoning truncated %d→%d chars", len(v), max_len)
        return v[:max_len]
    return v


class ReportOutput(BaseModel):
    """Post-render JSON slice for pipeline structural checks (title / summary / code / news)."""

    title: str
    summary: str
    code: str  # <code> 區塊
    news: str = ""


def parse_report_output(output_json: dict) -> ReportOutput:
    """Pydantic 結構驗證：若欄位缺失/型別錯誤會直接拋出例外。"""
    return ReportOutput(**output_json)


def assert_report_output(result: ReportOutput) -> None:
    """自訂 assertion：檢查摘要乾淨度、<code> 標籤與最小長度。"""
    assert "Error" not in result.summary, "摘要含有錯誤訊息"
    assert "<code>" in result.code, "缺少 <code> 標籤"
    assert len(result.summary) > 50, "摘要太短，可能是空回應"


def assert_sample_output(sample_output: dict) -> None:
    """對原始 dict 的快速防呆檢查（與 parse_report_output 互補）。"""
    assert sample_output.get("title"), "title 不能為空"
    assert "<code>" in sample_output.get("code", ""), "code block 缺失"
    assert "HTTPError" not in sample_output.get("news", ""), "news 含有 API error"


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
    asset_market: Literal["US", "TW", "CRYPTO"] | None = Field(
        default=None,
        description="Optional venue for symbol formatting (TW 台股等)；None 時由 category 推斷展示規則。",
    )
    internal_reasoning: str = Field(
        default="",
        description=(
            "【思考區｜不對外】多空權衡、數據衝突、選點依據、與研究員／風險意見的分歧；可較長。"
            "此欄不會出現在 Telegram 正文，也不會寫入對外 QSREC JSON；僅供你理清思路。"
            "寫完後將精華壓縮進 narrative，禁止把本欄內容複製到 narrative。"
        ),
    )
    narrative: str = Field(
        default="—",
        description=(
            f"【展示區】對外敘事：依 internal_reasoning 榨乾後 1～2 句（系統截斷至 {_NARRATIVE_DISPLAY_MAX_CHARS} 字）。"
            + _NARRATIVE_FEW_SHOT
            + "禁止因為／所以／值得注意的是／總結來說／我們認為等填充；禁止條列與算式；"
            "禁止字面【≤N字】等 prompt；禁止辯論框架標籤。"
        ),
    )
    trigger: str = Field(
        default="",
        description=(
            "【極簡短句】用一句話說明觸發的具體價格與條件。禁止冗長解釋、禁止條列、"
            "禁止「辯論摘要」「最強空方論點」「多方反駁」等內部標籤。"
        ),
    )
    invalidation: str = Field(
        default="",
        description=(
            "【極簡短句】用一句話說明失效的具體價格與條件。禁止冗長解釋、禁止條列、"
            "禁止內部思考標籤。可執行單時須非空。"
        ),
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
    bull_scenario: str | None = Field(
        default=None,
        description=(
            "Bull scenario one line ≤40 chars: target price + trigger. "
            "禁止內部思考標籤與辯論框架用語；只寫可讀結論句。confidence≥3 時必填。"
        ),
    )
    base_scenario: str | None = Field(
        default=None,
        description=(
            "Base scenario one line ≤40 chars: expected path + probability %. "
            "禁止內部思考標籤；只寫可讀結論句。confidence≥3 時必填。"
        ),
    )
    bear_scenario: str | None = Field(
        default=None,
        description=(
            "Bear scenario one line ≤40 chars: invalidation + trigger. "
            "禁止內部思考標籤；只寫可讀結論句。confidence≥3 時必填。"
        ),
    )

    @field_validator("internal_reasoning", mode="before")
    @classmethod
    def _cap_internal_reasoning_tr(cls, v: object) -> object:
        if v is None:
            return ""
        return _cap_internal_field(v)

    @field_validator("narrative", mode="before")
    @classmethod
    def _truncate_narrative(cls, v: object) -> object:
        """Coerce empty narrative; strip prompt echo; auto-truncate to _NARRATIVE_DISPLAY_MAX_CHARS."""
        cap = _NARRATIVE_DISPLAY_MAX_CHARS
        if v is None or (isinstance(v, str) and not str(v).strip()):
            v = "—"
        if isinstance(v, str):
            v = _strip_prompt_instruction_echoes(v)
        if isinstance(v, str) and len(v) > cap:
            logger.warning("TradeRecommendation.narrative truncated %d→%d chars", len(v), cap)
            return v[:cap]
        return v

    @model_validator(mode="before")
    @classmethod
    def _derive_score_gap_before(cls, data: object) -> object:
        """Crew 契約：score_gap = selection_score − alt_candidate_score。LLM 常漏填 gap；有兩分數時於解析前補上。"""
        if not isinstance(data, dict):
            return data
        if data.get("score_gap") is not None:
            return data
        sel, alt = data.get("selection_score"), data.get("alt_candidate_score")
        if sel is None or alt is None:
            return data
        merged = dict(data)
        merged["score_gap"] = float(sel) - float(alt)
        return merged

    @model_validator(mode="after")
    def _require_scenarios_and_narrative_when_high_confidence(self) -> "TradeRecommendation":
        """confidence≥3：三情境與對外 narrative 必填（對齊 QSREC／HTML Gate）。"""
        if self.confidence < 3:
            return self
        for fld in ("bull_scenario", "base_scenario", "bear_scenario"):
            val = getattr(self, fld, None)
            if val is None or (isinstance(val, str) and not str(val).strip()):
                raise ValueError(
                    f"TradeRecommendation.{fld} 在 confidence>=3 時須為非空字串"
                )
        nar = (self.narrative or "").strip()
        if not nar or nar == "—":
            raise ValueError(
                "TradeRecommendation.narrative 在 confidence>=3 時須為有效展示句（不可為空或「—」）"
            )
        return self


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
        description=(
            "【展示】一句客觀事實短句（理想 ≤40 字）；禁止評論腔與條列。"
            "絕對禁止「辯論摘要」「最強空方論點」「多方反駁」「╌辯論摘要╌」等內部思考或流程標籤；"
            "禁止輸出算式、評分步驟或模型自述（如 VIX>25→-1）。"
            "推演請寫入 internal_reasoning，勿塞進本欄。"
        ),
    )
    investment_takeaway: str = Field(
        ...,
        description=(
            "【展示】1–2 句極簡投資含義（理想總長 ≤90 字）；須含至少一個與儀表板一致的數字讀數。"
            "主詞／數據開頭，分號銜接因果；禁因為／所以／值得注意的是／我們認為。"
            "禁止條列、內部標籤與冗長推理；Bloomberg 式冷靜結論。"
        ),
    )
    editor_consensus: str = Field(
        ...,
        description=(
            "一句話（≤28 字）點名具體 ticker；語氣專業簡潔。"
            "須與該段交易方向一致（SHORT 時不得單邊看漲該標的等）。"
            "禁止「辯論摘要」「最強空方論點」「多方反駁」等內部標籤與廢話。"
        ),
    )
    internal_reasoning: str = Field(
        default="",
        description=(
            "【思考區｜不對外】本則新聞的簡短研判草稿、不確定性與與儀表板對照備註；"
            "Jinja 不會渲染此欄。summary／investment_takeaway／editor_consensus 僅寫展示用洗練句。"
        ),
    )

    @field_validator("internal_reasoning", mode="before")
    @classmethod
    def _cap_internal_reasoning_news(cls, v: object) -> object:
        if v is None:
            return ""
        return _cap_internal_field(v, max_len=2000)

    @field_validator("timestamp_line", mode="after")
    @classmethod
    def _ensure_timestamp_line_has_utc8(cls, v: object) -> object:
        if isinstance(v, str):
            return ensure_news_timestamp_line_utc8(v)
        return v


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

    @model_validator(mode="after")
    def _sanitize_treasury_yield_in_value(self) -> "MetricLine":
        """Gate macro outlier：儀表板美債／10Y／2Y 列之 value 異常百分比改 N/A。"""
        label = self.label or ""
        label_u = label.upper()
        if not (
            "美債" in label
            or "10Y" in label_u
            or "2Y" in label_u
            or "UST" in label_u
        ):
            return self
        val = self.value or ""
        nv = sanitize_us_treasury_yield_tokens_in_line(val)
        if nv != val:
            self.value = nv
        return self


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

        if ("（未確認）" in self.text or "(未確認)" in self.text) and re.search(
            r"可信度[：:]\s*A\b", self.text
        ):
            self.text = re.sub(r"(可信度[：:]\s*)A\b", r"\1B", self.text, count=1)

        if not _CHATTER_CRED_INLINE_RE.search(self.text):
            grade = self.credibility or "C"
            self.text = self.text.rstrip() + f"｜可信度：{grade}｜主流媒體二次驗證：否"
        return self


_ECHO_LABEL_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(?:本日選擇理由|今日風險預算|訊號衝突摘要)[：:]\s*", re.IGNORECASE),
    re.compile(r"^(?:·\s*)?美股部位框[：:]\s*", re.IGNORECASE),
)


def _strip_echoed_field_labels(value: object) -> object:
    """Remove repeated section headers the LLM pasted into body (Jinja adds the label once)."""
    if not isinstance(value, str):
        return value
    s = value.strip()
    while True:
        changed = False
        for rx in _ECHO_LABEL_RES:
            m = rx.match(s)
            if m:
                s = s[m.end() :].lstrip()
                changed = True
        if not changed:
            break
    return s


_INSTRUCTION_BRACKET_RE = re.compile(r"[【\[]\s*(?:≤|＜|<=)?\s*\d+\s*字[^】\]]*[】\]]")
_INSTRUCTION_STRICT_INLINE_RE = re.compile(
    r"[【\[]\s*嚴格限制\s*\d+\s*字以內\s*[】\]]",
    re.IGNORECASE,
)


def _strip_prompt_instruction_echoes(text: str) -> str:
    """Strip literal prompt fragments models copy into output (e.g. 【≤80字】)."""
    s = _INSTRUCTION_STRICT_INLINE_RE.sub("", text)
    while True:
        t2 = _INSTRUCTION_BRACKET_RE.sub("", s)
        if t2 == s:
            return t2.strip()
        s = t2


def _strip_debate_decorators(text: str) -> str:
    return re.sub(r"╌\s*辯論摘要\s*╌\s*", "", text, flags=re.IGNORECASE).strip()


def _dedupe_repeated_bear_lead(text: str) -> str:
    """If the model pasted the same 「最強空方論點」 block twice, keep the first."""
    needle = "最強空方論點："
    if text.count(needle) <= 1:
        return text
    first = text.find(needle)
    second = text.find(needle, first + len(needle))
    if second >= 0:
        return text[:second].strip()
    return text


class ExecutableTradeLeg(BaseModel):
    """One rendered trade bullet group in block ④ (before QSREC)."""

    asset_market: Literal["US", "TW", "CRYPTO"] | None = Field(
        default=None,
        description="Optional venue hint for `$`/幣符模板與 Gate（None=沿用區塊慣例：加密段 CRYPTO、AI 段 US）。",
    )
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
    trigger: str = Field(
        default="",
        description=(
            "【極簡短句】一句話：觸發的具體價位／條件。禁止冗長解釋、禁止條列、禁止內部思考標籤。"
        ),
    )
    sizing_logic: str = Field(
        default="",
        description="一句話部位邏輯；禁止內部思考標籤與辯論用語。",
    )
    invalidation: str = Field(
        default="",
        description=(
            "【極簡短句】一句話：失效的具體價位／條件。可執行時須非空。"
            "禁止冗長解釋、禁止內部思考標籤。"
        ),
    )
    position_pct: str = Field(default="", description="Portfolio % guidance line.")
    internal_reasoning: str = Field(
        default="",
        description=(
            "【思考區｜不對外】本筆交易的多空權衡、價位選取依據、與工具讀數對照；可較長。"
            "Telegram 交易卡與對外 QSREC JSON 均不顯示此欄；寫完後將精華壓入 narrative。"
        ),
    )
    narrative: str = Field(
        default="—",
        description=(
            f"【展示區】對外一句（系統截斷至 {_NARRATIVE_DISPLAY_MAX_CHARS} 字）。"
            + _NARRATIVE_FEW_SHOT
            + "禁止條列、內部標籤與【≤N字】等 prompt 字面；禁止因為／所以／值得注意的是等填充。"
        ),
    )
    bull_scenario: str | None = Field(
        default=None,
        description="🐂 Bull scenario ≤40 chars: target + trigger (e.g. breaks 74k, ETF inflow >$500M).",
    )
    base_scenario: str | None = Field(
        default=None,
        description="⚖️ Base scenario ≤40 chars: expected path + probability % (e.g. range 68-74k, prob 55%).",
    )
    bear_scenario: str | None = Field(
        default=None,
        description="🐻 Bear scenario ≤40 chars: invalidation level + trigger (e.g. breaks 65k, funding turns negative).",
    )

    @field_validator("internal_reasoning", mode="before")
    @classmethod
    def _cap_internal_reasoning_leg(cls, v: object) -> object:
        if v is None:
            return ""
        return _cap_internal_field(v)

    @field_validator("trigger", "sizing_logic", "invalidation", mode="before")
    @classmethod
    def _strip_aux_instruction_echo(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("narrative", mode="before")
    @classmethod
    def _truncate_narrative(cls, v: object) -> object:
        """Coerce empty narrative; strip prompt echo; auto-truncate to _NARRATIVE_DISPLAY_MAX_CHARS."""
        cap = _NARRATIVE_DISPLAY_MAX_CHARS
        if v is None or (isinstance(v, str) and not str(v).strip()):
            v = "—"
        if isinstance(v, str):
            v = _strip_prompt_instruction_echoes(v)
        if isinstance(v, str) and len(v) > cap:
            logger.warning("ExecutableTradeLeg.narrative truncated %d→%d chars", len(v), cap)
            return v[:cap]
        return v

    @model_validator(mode="after")
    def _require_scenarios_when_high_conviction(self) -> "ExecutableTradeLeg":
        """P4：信心 ≥2 星須有三情境欄位（與結構化 Gate / HTML QSREC 情境一致）。"""
        if self.star_rating >= 2:
            for fld in ("bull_scenario", "base_scenario", "bear_scenario"):
                val = getattr(self, fld, None)
                if val is None or (isinstance(val, str) and not val.strip()):
                    raise ValueError(
                        f"ExecutableTradeLeg.{fld} 在 star_rating>={self.star_rating} 時須為非空字串"
                    )
        return self

    @model_validator(mode="after")
    def _default_invalidation_when_actionable_star(self) -> "ExecutableTradeLeg":
        if self.star_rating >= 2 and not (self.invalidation or "").strip():
            self.invalidation = "跌破關鍵支撐位或重大利空事件出現"
        return self


class MarketRegimeBlock(BaseModel):
    """Regime header + optional scorecard lines (plain text)."""

    regime: Literal["risk_on", "risk_off", "neutral"] = Field(
        ...,
        description="Single authoritative regime for the full brief.",
    )
    score_suffix: str = Field(
        default="",
        description=(
            "括號內結論片段，如 （+4/6）。僅輸出最終讀數／符號，禁止寫算式或逐步評分過程（如 VIX>25→-1）。"
        ),
    )
    scorecard_lines: list[str] = Field(
        default_factory=list,
        description=(
            "額外 ✅/❌ 行：每行一句定性＋讀數；plain text。禁止條列推理、禁止內部思考標籤；"
            "模板會將數值包在 <code>。"
        ),
    )


class CryptoSection(BaseModel):
    """Crypto crew final structured output."""

    report_title_date: str = Field(
        ...,
        description="YYYY-MM-DD for Daily Brief subtitle (UTC+8 run day).",
    )
    exec_summary: list[str] = Field(
        default_factory=list,
        description=(
            "【執行摘要】3–5 bullet lines, each ≤50 chars. "
            "One-glance conclusions for a CIO: today's dominant thesis, key trade, main risk, macro stance. "
            "Goes at the very top of the report before market mode."
        ),
    )
    investment_thesis_one_liner: str = Field(
        default="",
        description=(
            "【投資命題】一句可檢驗主命題（≤90 字），須涵蓋加密與美股主軸或明確寫出跨資產邏輯；"
            "禁止內部標籤與【≤N字】提示詞。"
        ),
    )
    thesis_supporting_points: list[str] = Field(
        default_factory=list,
        description="支持論點恰好 3 條，每條 ≤72 字；須可對照儀表板或新聞，禁止空泛形容詞。",
    )
    thesis_contrary_points: list[str] = Field(
        default_factory=list,
        description="反駁／風險論點恰好 3 條，每條 ≤72 字；與主命題對稱，禁止只寫「波動大」。",
    )
    key_assumptions_lines: list[str] = Field(
        default_factory=list,
        description="關鍵假設 2–4 條，每條 ≤80 字（例：利率路徑、盈利共識、流動性條件）。",
    )
    narrative_invalidation_summary: str = Field(
        default="",
        description=(
            "【敘事失效】宏觀或敘事級觸發（非單筆價格停損）：1–2 句 ≤160 字；"
            "說明何種證據若出現則本日主命題需重估。"
        ),
    )
    market: MarketRegimeBlock
    narrative_of_day: str = Field(
        ...,
        description=(
            "【今日主敘事】一句話總結市場核心氛圍（理想 ≤45 字），須與 regime 不矛盾。"
            "禁止算式或評分過程；禁止內部標籤與冗言；禁止字面輸出【≤N字】等提示詞。"
        ),
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
            "兩句內說完：空方主線一句、多方主線一句（可用全形｜分隔於同一行）。"
            "嚴禁以「訊號衝突摘要：」開頭；嚴禁「╌辯論摘要╌」；"
            "嚴禁重複貼上兩遍相同論點；嚴禁字面【≤N字】等 prompt。"
            "勿再用「最強空方論點：」「多方反駁核心：」小標（模板已印訊號衝突摘要）。"
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

    @field_validator("narrative_of_day", mode="before")
    @classmethod
    def _scrub_narrative_of_day(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_prompt_instruction_echoes(v)
        return v

    @field_validator(
        "investment_thesis_one_liner",
        "narrative_invalidation_summary",
        mode="before",
    )
    @classmethod
    def _scrub_thesis_strings(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("thesis_supporting_points", "thesis_contrary_points", "key_assumptions_lines", mode="before")
    @classmethod
    def _scrub_thesis_lists(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        out: list[str] = []
        for item in v:
            if isinstance(item, str):
                s = _strip_prompt_instruction_echoes(item).strip()
                if s:
                    out.append(s)
            elif item is not None:
                out.append(str(item).strip())
        return out

    @field_validator("pick_reason", "risk_budget_summary", "signal_conflict_summary", mode="before")
    @classmethod
    def _strip_label_prefix(cls, v: object) -> object:
        """Strip echoed section headers and prompt fragments (Jinja prints labels once)."""
        v = _strip_echoed_field_labels(v)
        if isinstance(v, str):
            v = _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("signal_conflict_summary", mode="before")
    @classmethod
    def _clean_signal_conflict(cls, v: object) -> object:
        """Dedupe debate paste, normalise newlines, cap length."""
        if isinstance(v, str):
            v = _strip_debate_decorators(v)
            v = _dedupe_repeated_bear_lead(v)
            v = v.replace("\\n", "\n")
            if len(v) > 160:
                logger.warning(
                    "CryptoSection.signal_conflict_summary truncated %d→160 chars", len(v)
                )
                v = v[:160]
        return v

    @field_validator("signal_conflict_summary", mode="after")
    @classmethod
    def _default_empty_signal_conflict(cls, v: object) -> object:
        if isinstance(v, str) and v.strip():
            return v
        return "暫無重大訊號衝突，多空數據基本一致。"

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
            "訊號衝突 body ONLY — 勿含「訊號衝突摘要：」前綴。"
            "兩句內：空方主線｜多方主線；禁止「╌辯論摘要╌」與重複貼上；禁止【≤N字】；"
            "勿用小標「最強空方論點：」「多方反駁核心：」（讀者版由模板統一呈現）。"
        ),
    )

    @field_validator("pick_reason", "signal_conflict_summary", mode="before")
    @classmethod
    def _strip_label_prefix(cls, v: object) -> object:
        v = _strip_echoed_field_labels(v)
        if isinstance(v, str):
            v = _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("signal_conflict_summary", mode="before")
    @classmethod
    def _clean_signal_conflict(cls, v: object) -> object:
        if isinstance(v, str):
            v = _strip_debate_decorators(v)
            v = _dedupe_repeated_bear_lead(v)
            v = v.replace("\\n", "\n")
            if len(v) > 160:
                logger.warning(
                    "AISection.signal_conflict_summary truncated %d→160 chars", len(v)
                )
                v = v[:160]
        return v

    @field_validator("signal_conflict_summary", mode="after")
    @classmethod
    def _default_empty_signal_conflict(cls, v: object) -> object:
        if isinstance(v, str) and v.strip():
            return v
        return "暫無重大訊號衝突，多空數據基本一致。"

    us_equity_allocation_note: str | None = Field(
        default=None,
        description="美股部位框內文 ONLY — 勿含「美股部位框」或「·」前綴（模板已加粗標題）。",
    )

    @field_validator("us_equity_allocation_note", mode="before")
    @classmethod
    def _strip_us_equity_note(cls, v: object) -> object:
        if v is None:
            return v
        if isinstance(v, str) and not v.strip():
            return None
        v2 = _strip_echoed_field_labels(v)
        return v2 if isinstance(v2, str) else v
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

    @model_validator(mode="after")
    def _warn_watch_mode_vs_equity_qsrec(self) -> "AISection":
        """HTML 模板在 trade_legs 為空時走觀望文案；若 QSREC 仍帶完整 EQUITY 價位則記 warning（不擋解析）。"""
        if self.trade_legs:
            return self
        for rec in self.qsrec:
            if str(rec.category or "").upper() != "EQUITY":
                continue
            try:
                if rec.entry > 0 and rec.target > 0 and rec.stop > 0:
                    logger.warning(
                        "AISection：trade_legs 為空但 EQUITY QSREC 仍含可解析價位（%s）；"
                        "讀者 HTML 為觀望模式，請對齊 crew 輸出或 assemble",
                        rec.asset,
                    )
            except Exception:
                continue
        return self


def _structured_business_issues(report: "DailyBriefReport") -> list[str]:
    """Cross-field business rules formerly in report_validator.validate_structured_report."""
    issues: list[str] = []
    cr, ai_sec = report.crypto, report.ai
    if len(cr.news) < 3:
        issues.append(f"結構化加密新聞不足（{len(cr.news)}/3）")
    if len(ai_sec.news) < 3:
        issues.append(f"結構化 AI 新聞不足（{len(ai_sec.news)}/3）")
    tagged = len(cr.news) + len(ai_sec.news)
    if tagged < 6 and not report.report_tier_partial_news:
        issues.append(f"結構化新聞總數 {tagged}/6 且未標記 partial tier")
    if report.report_tier_partial_news and not (3 <= tagged <= 5):
        issues.append(f"partial tier 僅允許 3~5 則新聞，當前為 {tagged}")
    if not report.all_qsrec():
        issues.append("結構化 qsrec 為空")
    if not (cr.pick_reason or "").strip():
        issues.append("加密本日選擇理由為空")
    if not (ai_sec.pick_reason or "").strip():
        issues.append("AI 本日選擇理由為空")

    if len((cr.pick_reason or "").strip()) < 34:
        issues.append("加密本日選擇理由過短（<34）")
    if len((ai_sec.pick_reason or "").strip()) < 38:
        issues.append("AI 本日選擇理由過短（<38）")
    _regime_pattern = re.escape(cr.market.regime).replace(r"_", r"[\s_\-]+")
    if not re.search(_regime_pattern, cr.risk_budget_summary or "", re.IGNORECASE):
        issues.append("加密今日風險預算未包含主 regime token")

    def _norm_asset(a: str) -> str:
        return str(a or "").upper().replace("$", "").replace("-", "/").replace(" ", "")

    def _check_section_alignment(section: CryptoSection | AISection, category: str, label: str) -> None:
        leg_map: dict[str, str] = {}
        for leg in section.trade_legs:
            leg_map[_norm_asset(leg.asset)] = str(leg.direction or "").upper()

        seen: dict[str, str] = {}
        for idx, rec in enumerate(section.qsrec, start=1):
            cat = str(rec.category or "").upper()
            if cat != category:
                issues.append(f"{label} qsrec 第 {idx} 筆 category={cat} 應為 {category}")
            asset = _norm_asset(rec.asset)
            direction = str(rec.direction or "").upper()
            prev = seen.get(asset)
            if prev and prev != direction:
                issues.append(f"{label} qsrec 同資產 {asset} 出現相反方向 {prev}/{direction}")
            seen[asset] = direction
            if asset in leg_map and leg_map[asset] != direction:
                issues.append(
                    f"{label} 交易條目與 qsrec 方向不一致：{asset} leg={leg_map[asset]} qsrec={direction}"
                )

            for f in (
                "selection_score",
                "catalyst_score",
                "flow_score",
                "technical_score",
                "risk_fit_score",
                "execution_score",
                "alt_candidate_score",
                "score_gap",
            ):
                if getattr(rec, f) is None:
                    issues.append(f"{label} qsrec 第 {idx} 筆缺少可量化評分欄位：{f}")

    for section_label, section in (("加密", cr), ("AI", ai_sec)):
        for leg in section.trade_legs:
            if leg.star_rating >= 2 and not all(
                [leg.bull_scenario, leg.base_scenario, leg.bear_scenario]
            ):
                issues.append(
                    f"{section_label}交易腿 {leg.asset} star_rating={leg.star_rating}≥2"
                    f" 但缺少三情境分析（bull/base/bear）"
                )

    _check_section_alignment(cr, "CRYPTO", "加密")
    _check_section_alignment(ai_sec, "EQUITY", "AI")
    if os.getenv("STRICT_INSTITUTIONAL_PHASE_A_GATE", "0").lower() in ("1", "true", "yes"):
        issues.extend(_institutional_phase_a_structured_issues(cr))
    return issues


def _institutional_phase_a_structured_issues(cr: CryptoSection) -> list[str]:
    """When STRICT_INSTITUTIONAL_PHASE_A_GATE=1, require Phase A institutional blocks in CryptoSection."""
    out: list[str] = []
    thesis = (cr.investment_thesis_one_liner or "").strip()
    if not thesis:
        out.append("結構化缺少投資命題（investment_thesis_one_liner）")
    elif len(thesis) > 95:
        out.append("投資命題過長（>90 字建議上限）")
    sup = [str(x).strip() for x in cr.thesis_supporting_points if str(x).strip()]
    con = [str(x).strip() for x in cr.thesis_contrary_points if str(x).strip()]
    if len(sup) != 3:
        out.append(f"支持論點須恰好 3 條（當前 {len(sup)}）")
    if len(con) != 3:
        out.append(f"反駁論點須恰好 3 條（當前 {len(con)}）")
    ass = [str(x).strip() for x in cr.key_assumptions_lines if str(x).strip()]
    if not (2 <= len(ass) <= 4):
        out.append(f"關鍵假設須 2–4 條（當前 {len(ass)}）")
    if not (cr.narrative_invalidation_summary or "").strip():
        out.append("結構化缺少敘事失效（narrative_invalidation_summary）")
    return out


class DailyBriefReport(BaseModel):
    """Assembled root object: crypto + AI crews + pipeline-injected fields."""

    crypto: CryptoSection
    ai: AISection
    institutional_disclaimer_html: str = Field(
        default="",
        description="Fixed institutional disclaimer HTML (whitelist tags only); injected at assemble, not from LLM.",
    )
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
    low_confidence_disclaimer: str = Field(
        default="",
        description=(
            "Plain-text block (escaped in Jinja) inserted before QSREC when N/A density exceeds Gate "
            "threshold; filled by assemble_daily_brief_report, not LLM."
        ),
    )

    @model_validator(mode="after")
    def _structured_business_rules(self) -> "DailyBriefReport":
        issues = _structured_business_issues(self)
        if issues:
            raise ValueError("; ".join(issues))
        return self

    def all_qsrec(self) -> list[TradeRecommendation]:
        return list(self.crypto.qsrec) + list(self.ai.qsrec)

    def tagged_news_count(self) -> int:
        return len(self.crypto.news) + len(self.ai.news)


def validate_structured_report(report: object) -> dict:
    """Attribute-level checks on assembled DailyBriefReport (dict API for tests / tooling).

    Valid constructed models always pass; use with model_construct() to inspect invalid tuples.
    """
    if not isinstance(report, DailyBriefReport):
        return {
            "valid": False,
            "issues": ["report 非 DailyBriefReport"],
            "blocking_issues": ["report 非 DailyBriefReport"],
            "warning_issues": [],
        }
    issues = _structured_business_issues(report)
    return {
        "valid": len(issues) == 0,
        "blocking_issues": issues,
        "warning_issues": [],
        "issues": issues,
    }
