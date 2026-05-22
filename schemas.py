"""
Structured daily-brief contract (Pydantic v2).

Field descriptions are consumed by CrewAI output_pydantic as JSON Schema hints for the LLM.
Use Optional / defaults for sparse tool data so one missing field does not fail the whole parse.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from validation_rules import (
    ensure_news_timestamp_line_utc8,
    sanitize_us_treasury_yield_tokens_in_line,
)

logger = logging.getLogger(__name__)

# Stripped from Telegram [QSREC_START]…[QSREC_END] JSON (internal CoT only).
QSREC_JSON_EXCLUDE_FIELDS: frozenset[str] = frozenset({"internal_reasoning"})

# NewsItem.pricing_note — must match rendered prefix for Gate (Phase B).
_PRICING_NOTE_CANONICAL: tuple[str, ...] = ("未定價／增量資訊", "大致已定價", "已高度反應")
_PRICING_NOTE_ALIASES: dict[str, str] = {
    "未定價": "未定價／增量資訊",
    "增量資訊": "未定價／增量資訊",
    "未定價/增量資訊": "未定價／增量資訊",
    "priced in": "大致已定價",
    "priced-in": "大致已定價",
    "已定價": "大致已定價",
    "高度反應": "已高度反應",
    "已反應": "已高度反應",
}

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


def _norm_qsrec_asset(a: object) -> str:
    """Canonical asset key for leg↔qsrec alignment (same rule as structured gate checks)."""
    return str(a or "").upper().replace("$", "").replace("-", "/").replace(" ", "")


def _infer_trade_direction_from_prices(
    entry: object, target: object, stop: object
) -> Literal["LONG", "SHORT"] | None:
    """When LLM omits direction, infer LONG/SHORT from entry/target/stop geometry (no fabrication of prices)."""
    try:
        e = float(entry)  # type: ignore[arg-type]
        t = float(target)
        s = float(stop)
    except (TypeError, ValueError):
        return None
    if t > e and s < e:
        return "LONG"
    if t < e and s > e:
        return "SHORT"
    if t > e and s <= e:
        return "LONG"
    if t < e and s >= e:
        return "SHORT"
    return None


def _backfill_missing_qsrec_directions_from_sections_raw(
    data: dict[str, Any], *, label: str
) -> dict[str, Any]:
    """Patch raw qsrec dicts missing direction using same-section trade_legs (Crew drift guard)."""
    qsrec = data.get("qsrec")
    legs = data.get("trade_legs")
    if not isinstance(qsrec, list) or not isinstance(legs, list):
        return data
    leg_dirs: dict[str, str] = {}
    for leg in legs:
        if not isinstance(leg, dict):
            continue
        asset_key = _norm_qsrec_asset(leg.get("asset"))
        dv = leg.get("direction")
        if not asset_key or not isinstance(dv, str) or not dv.strip():
            continue
        u = dv.strip().upper()
        if u in ("LONG", "BUY"):
            leg_dirs[asset_key] = "LONG"
        elif u in ("SHORT", "SELL"):
            leg_dirs[asset_key] = "SHORT"
    if not leg_dirs:
        return data
    new_qs: list[Any] = []
    changed = False
    for item in qsrec:
        if not isinstance(item, dict):
            new_qs.append(item)
            continue
        row = dict(item)
        cur = row.get("direction")
        missing = cur is None or (isinstance(cur, str) and not cur.strip())
        if missing:
            ak = _norm_qsrec_asset(row.get("asset"))
            fill = leg_dirs.get(ak)
            if fill:
                row["direction"] = fill
                changed = True
                logger.warning(
                    "%s: qsrec 資產 %r 缺 direction，已由 trade_legs 補為 %s",
                    label,
                    row.get("asset"),
                    fill,
                )
        new_qs.append(row)
    if not changed:
        return data
    out = dict(data)
    out["qsrec"] = new_qs
    return out


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
    def _coerce_trade_recommendation_raw(cls, data: object) -> object:
        """解析前容錯：補 direction（別名欄位／價位幾何）、補 score_gap（selection−alt）。"""
        if not isinstance(data, dict):
            return data
        merged: dict[str, Any] = dict(data)

        raw_dir = merged.get("direction")
        if isinstance(raw_dir, str) and raw_dir.strip():
            u = raw_dir.strip().upper()
            if u in ("LONG", "BUY"):
                merged["direction"] = "LONG"
            elif u in ("SHORT", "SELL"):
                merged["direction"] = "SHORT"

        if merged.get("direction") not in ("LONG", "SHORT"):
            for alt_key in ("side", "position", "bias", "net_direction", "trade_direction"):
                alt = merged.get(alt_key)
                if not isinstance(alt, str) or not alt.strip():
                    continue
                u = alt.strip().upper()
                if u in ("LONG", "BUY"):
                    merged["direction"] = "LONG"
                    logger.warning(
                        "TradeRecommendation: direction 已由別名欄位 %r 補上（資產=%r）",
                        alt_key,
                        merged.get("asset"),
                    )
                    break
                if u in ("SHORT", "SELL"):
                    merged["direction"] = "SHORT"
                    logger.warning(
                        "TradeRecommendation: direction 已由別名欄位 %r 補上（資產=%r）",
                        alt_key,
                        merged.get("asset"),
                    )
                    break

        if merged.get("direction") not in ("LONG", "SHORT"):
            inferred = _infer_trade_direction_from_prices(
                merged.get("entry"), merged.get("target"), merged.get("stop")
            )
            if inferred:
                merged["direction"] = inferred
                logger.warning(
                    "TradeRecommendation: direction 依 entry/target/stop 推斷為 %s（資產=%r）",
                    inferred,
                    merged.get("asset"),
                )

        if merged.get("score_gap") is None:
            sel, alt = merged.get("selection_score"), merged.get("alt_candidate_score")
            if sel is not None and alt is not None:
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
    pricing_note: str = Field(
        default="",
        description=(
            "市場定價註記（三擇一，須與模板「市場定價：」後文字完全一致）："
            "「未定價／增量資訊」「大致已定價」「已高度反應」。"
            "說明該則事件相對盤面是否已 priced-in。"
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

    @field_validator("pricing_note", mode="before")
    @classmethod
    def _scrub_pricing_note(cls, v: object) -> object:
        if v is None:
            return ""
        if not isinstance(v, str):
            s = str(v).strip()
        else:
            s = _strip_prompt_instruction_echoes(v).strip()
        if not s:
            return ""
        if s in _PRICING_NOTE_CANONICAL:
            return s
        low = s.lower()
        for alias, canon in _PRICING_NOTE_ALIASES.items():
            if alias.lower() in low:
                return canon
        logger.warning("NewsItem.pricing_note unrecognized %r; clearing for Gate to catch", s)
        return ""


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
    is_section_header: bool = Field(
        default=False,
        description=(
            "When True, template renders only a grouping subhead (投行式儀表板分區)；"
            "value may be a single space — omit <code> value line."
        ),
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
        elif "主流媒體二次驗證" not in self.text:
            # Inline 可信度已存在（例如「可信度：B」）但漏 MSM 欄位時補齊，對齊 _CHATTER_FMT 與 STRICT_CHATTER_MSM_VERIFY_GATE。
            self.text = self.text.rstrip() + "｜主流媒體二次驗證：否"

        # 每條須含「（未確認）」；常見漏寫為直接「傳…可信度：」—在可信度前補標記。
        if "（未確認）" not in self.text and "(未確認)" not in self.text:
            if re.search(r"可信度[：:]", self.text):
                self.text = re.sub(
                    r"(可信度[：:])",
                    r"（未確認）｜\1",
                    self.text,
                    count=1,
                )
            else:
                self.text = self.text.rstrip() + "（未確認）"
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
    liquidity_execution_note: str = Field(
        default="",
        description=(
            "【流動性／執行】一句 ≤100 字：ADV/價差/大額可行性或建議限價區間（定性即可）；"
            "加密可寫主要所深度；禁內部標籤。"
        ),
    )
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

    @field_validator("trigger", "sizing_logic", "invalidation", "liquidity_execution_note", mode="before")
    @classmethod
    def _strip_aux_instruction_echo(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("rr", "max_drawdown_pct", "expected_win_rate", "signal_score", mode="before")
    @classmethod
    def _strip_dollar_from_metric_strings(cls, v: object) -> object:
        """Avoid $$ in Telegram when template prepends $ to adjacent fields."""
        if isinstance(v, str):
            return v.lstrip("$").strip()
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
        description="支持論點 2–3 條（投行速讀），每條 ≤72 字；須可對照儀表板或新聞，禁止空泛形容詞。",
    )
    thesis_contrary_points: list[str] = Field(
        default_factory=list,
        description="反駁／風險論點 2–3 條，每條 ≤72 字；與主命題對稱，禁止只寫「波動大」。",
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
    portfolio_framing_summary: str = Field(
        default="",
        description=(
            "【組合與曝險框架】2–4 句 ≤280 字：加密／美股合計總曝險意圖、淨方向、"
            "與 SPY／BTC 相關性直覺、是否對沖；禁內部標籤。"
        ),
    )
    scenario_probability_notes: str = Field(
        default="",
        description=(
            "【三情境機率】恰好三行（換行分隔），每行 ≤72 字，格式："
            "· 樂觀：…（機率 xx%）／· 基準：…（xx%）／· 悲觀：…（xx%）；"
            "三機率須為整數百分比且合計 100%。"
        ),
    )
    crypto_cycle_valuation_notes: str = Field(
        default="",
        description=(
            "【加密週期與估值錨】1–3 句 ≤220 字：BTC 週期位置、鏈上估值錨（NVT/MVRV 等）"
            "與價格關係一句；禁內部標籤；數字須與儀表板一致。"
        ),
    )
    equity_valuation_framing: str = Field(
        default="",
        description=(
            "【美股估值與修正框架】2–4 句 ≤320 字：AI 權值相對大盤、盈利修正方向、"
            "利率對估值倍數壓力；可點名 NVDA/MSFT 等但勿發明未列於儀表之精確本益比。"
        ),
    )
    event_calendar_lines: list[str] = Field(
        default_factory=list,
        description=(
            "【近端事件日曆】3–6 條，每條 ≤96 字；須含可解析日期（MM/DD 或 YYYY-MM-DD）"
            "與事件類型（財報/Fed/期權到期/解鎖等）；禁止虛構未公告日期。"
        ),
    )
    prediction_market_highlight_lines: list[str] = Field(
        default_factory=list,
        description=(
            "【預測市場熱門】3–6 條獨立掃讀行；管線由 Polymarket Gamma API 注入即時隱含機率／成交量，"
            "LLM 勿捏造；正文僅複述本欄與工具回傳。"
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

    @model_validator(mode="before")
    @classmethod
    def _backfill_qsrec_direction_from_legs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        return _backfill_missing_qsrec_directions_from_sections_raw(
            data, label="CryptoSection"
        )

    @field_validator("qsrec", mode="before")
    @classmethod
    def _coerce_qsrec_category_to_crypto(cls, v: object) -> object:
        """LLM occasionally assigns category=EQUITY inside the crypto section.

        Auto-correct to CRYPTO and emit a warning so the gate never hard-blocks
        due to this cross-section contamination. The correction is logged so
        operators can identify prompt drift.
        Handles both raw dicts (from JSON/LLM) and already-constructed TradeRecommendation objects.
        """
        if not isinstance(v, list):
            return v
        out: list[object] = []
        for i, item in enumerate(v, start=1):
            if isinstance(item, dict):
                cat = str(item.get("category", "CRYPTO")).upper()
                if cat != "CRYPTO":
                    logger.warning(
                        "CryptoSection.qsrec 第 %d 筆 category=%r 已自動修正為 CRYPTO",
                        i,
                        item.get("category"),
                    )
                    item = {**item, "category": "CRYPTO"}
            elif hasattr(item, "model_dump"):
                # Already a TradeRecommendation (or similar Pydantic model)
                raw = item.model_dump()  # type: ignore[union-attr]
                cat = str(raw.get("category", "CRYPTO")).upper()
                if cat != "CRYPTO":
                    logger.warning(
                        "CryptoSection.qsrec 第 %d 筆 category=%r 已自動修正為 CRYPTO",
                        i,
                        raw.get("category"),
                    )
                    raw["category"] = "CRYPTO"
                    item = raw
            out.append(item)
        return out

    crypto_block4_recommendation_line: str = Field(
        default="",
        description=(
            "管線注入：區塊④開頭一行「部位摘要」（含 whitelist HTML）；"
            "非 LLM 輸出，由 assemble 填入。"
        ),
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
        "portfolio_framing_summary",
        "scenario_probability_notes",
        "crypto_cycle_valuation_notes",
        "equity_valuation_framing",
        mode="before",
    )
    @classmethod
    def _scrub_thesis_strings(cls, v: object) -> object:
        if isinstance(v, str):
            return _strip_prompt_instruction_echoes(v)
        return v

    @field_validator("event_calendar_lines", mode="before")
    @classmethod
    def _scrub_event_calendar(cls, v: object) -> object:
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


class Citation(BaseModel):
    """Supplemental research citation used by optional deep-dive blocks."""

    page: int | str | None = Field(
        default=None,
        description="Source page or locator when available.",
    )
    section: str | None = Field(
        default=None,
        description="Filing / template section label when available.",
    )
    excerpt: str = Field(
        ...,
        description="Short source excerpt or citation anchor; must not be empty.",
    )

    @field_validator("excerpt", mode="before")
    @classmethod
    def _require_excerpt(cls, v: object) -> object:
        if isinstance(v, str) and v.strip():
            return v.strip()
        raise ValueError("Citation.excerpt cannot be empty")


def _coerce_question_key(key: object) -> int | str:
    """Normalize question-index keys to int. Handles '1', 'Q1', 'q2', etc."""
    if isinstance(key, int):
        return key
    s = str(key).strip()
    try:
        return int(s)
    except ValueError:
        stripped = s.lstrip("Qq")
        try:
            return int(stripped)
        except ValueError:
            return s


class DeepFilingAnalysis(BaseModel):
    """Optional NotebookLM filing analysis; omitted from renders when absent."""

    ticker: str = Field(default="", description="Ticker or company symbol.")
    filing_type: str = Field(default="", description="10-K / 10-Q / S-1 / other filing label.")
    answers: dict[int, str] = Field(
        default_factory=dict,
        description="Question index to answer text.",
    )
    citations: dict[int, list[Citation]] = Field(
        default_factory=dict,
        description="Question index to source citations.",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="Concise filing red flags, if any.",
    )

    @field_validator("answers", mode="before")
    @classmethod
    def _drop_empty_answers(cls, v: object) -> object:
        if isinstance(v, dict):
            out: dict[int | str, str] = {}
            for k, val in v.items():
                text = str(val).strip()
                if not text:
                    continue
                out[_coerce_question_key(k)] = text
            return out
        return v

    @field_validator("citations", mode="before")
    @classmethod
    def _normalize_citations_shape(cls, v: object) -> object:
        """Coerce API / legacy shapes so Gate AISection parse does not fail.

        Live NotebookLM or upstream JSON may send a section label string per question,
        a bare string instead of a list, or string elements inside the list.
        """
        if not isinstance(v, dict):
            return v
        out: dict[int | str, object] = {}
        for key, val in v.items():
            nk: int | str = _coerce_question_key(key)
            if isinstance(val, str):
                s = val.strip()
                val = [{"excerpt": s}] if s else []
            elif isinstance(val, dict):
                val = [val]
            elif isinstance(val, list):
                fixed: list[object] = []
                for item in val:
                    if isinstance(item, str):
                        s = item.strip()
                        if s:
                            fixed.append({"excerpt": s})
                    else:
                        fixed.append(item)
                val = fixed
            else:
                val = []
            out[nk] = val
        return out

    @model_validator(mode="after")
    def _require_citations_for_answers(self) -> "DeepFilingAnalysis":
        for key in self.answers:
            if not self.citations.get(key):
                raise ValueError(f"DeepFilingAnalysis answer {key!r} missing citation")
        return self


class AgencyDeliverable(BaseModel):
    """One structured deliverable from the optional Agency research template."""

    name: str = Field(..., min_length=1, description="Deliverable title.")
    content: str = Field(..., min_length=1, description="Deliverable body.")
    confidence: Literal["high", "medium", "low"] = Field(default="low")
    citations: list[Citation] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_citations(self) -> "AgencyDeliverable":
        if not self.citations:
            raise ValueError("AgencyDeliverable requires at least one citation")
        return self


class AgencyResearchOutput(BaseModel):
    """Optional Agency-style supplemental finance research."""

    agent_type: str = Field(default="investment_researcher")
    ticker: str | None = Field(default=None)
    deliverables: list[AgencyDeliverable] = Field(default_factory=list)
    risk_register: list[str] = Field(default_factory=list)
    success_metrics: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _require_deliverables(self) -> "AgencyResearchOutput":
        if not self.deliverables:
            raise ValueError("AgencyResearchOutput requires at least one deliverable")
        return self


def normalize_optional_agency_research_output(value: object) -> dict[str, Any] | None:
    """Return a validated agency payload dict, or None if absent/invalid.

    Prevents GATE_EXECUTION_FAILED when LangGraph state carries a partial
    agency_research_output (e.g. empty deliverables) into AISection parsing.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return None
    if not isinstance(value, dict):
        return None
    if not value:
        return None
    try:
        return AgencyResearchOutput.model_validate(value).model_dump(mode="json")
    except Exception as exc:
        logger.warning(
            "Dropping invalid agency_research_output before AISection parse: %s",
            exc,
        )
        return None


class AISection(BaseModel):
    """AI / US equities crew structured output."""

    macro_bridge_lines: list[str] = Field(
        default_factory=list,
        description=(
            "1–2 lines ≤60 chars each connecting macro context to AI equities impact. "
            "Do NOT repeat UST/SOFR/VIX values already shown in 加密宏觀框架. "
            "Focus on the specific implication for AI growth stocks (e.g. valuation compression, capex outlook)."
        ),
    )

    @field_validator("macro_bridge_lines", mode="before")
    @classmethod
    def _cap_macro_bridge_line_length(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        result = []
        for line in v:
            if isinstance(line, str) and len(line) > 60:
                logger.warning("macro_bridge_lines: line truncated %d→60 chars", len(line))
                result.append(line[:60])
            else:
                result.append(line)
        return result[:2]  # enforce 1–2 lines max

    dashboard: list[MetricLine] = Field(
        ...,
        description=(
            "AI block ① metrics. Investor-facing order: 可交易市場, 基本面／財報錨點, "
            "需求代理; model momentum is optional narrative support, not a price signal."
        ),
    )
    earnings_event_lines: list[str] = Field(
        default_factory=list,
        description=(
            "Pipeline-filled deterministic 【財報雷達｜未來 7 天】 lines. "
            "Use yfinance earnings calendar only; no EPS/revenue consensus forecast unless separately sourced."
        ),
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
    ai_block4_recommendation_line: str = Field(
        default="",
        description="管線注入：AI 區塊④開頭一行部位摘要（whitelist HTML）；非 LLM。",
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

    @model_validator(mode="before")
    @classmethod
    def _backfill_qsrec_direction_from_legs(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        return _backfill_missing_qsrec_directions_from_sections_raw(data, label="AISection")

    deep_filing_analysis: DeepFilingAnalysis | None = Field(
        default=None,
        description="Optional NotebookLM filing deep dive; empty values are omitted from renders.",
    )
    agency_research_output: AgencyResearchOutput | None = Field(
        default=None,
        description="Optional Agency supplemental finance research; empty values are omitted from renders.",
    )

    @field_validator("agency_research_output", mode="before")
    @classmethod
    def _coerce_agency_research_output(cls, v: object) -> object:
        return normalize_optional_agency_research_output(v)

    @field_validator("qsrec", mode="before")
    @classmethod
    def _coerce_qsrec_category_to_equity(cls, v: object) -> object:
        """LLM occasionally assigns category=CRYPTO inside the AI/equity section.

        Auto-correct to EQUITY and emit a warning so the gate never hard-blocks
        due to this cross-section contamination.
        Handles both raw dicts (from JSON/LLM) and already-constructed TradeRecommendation objects.
        """
        if not isinstance(v, list):
            return v
        out: list[object] = []
        for i, item in enumerate(v, start=1):
            if isinstance(item, dict):
                cat = str(item.get("category", "EQUITY")).upper()
                if cat != "EQUITY":
                    logger.warning(
                        "AISection.qsrec 第 %d 筆 category=%r 已自動修正為 EQUITY",
                        i,
                        item.get("category"),
                    )
                    item = {**item, "category": "EQUITY"}
            elif hasattr(item, "model_dump"):
                # Already a TradeRecommendation (or similar Pydantic model)
                raw = item.model_dump()  # type: ignore[union-attr]
                cat = str(raw.get("category", "EQUITY")).upper()
                if cat != "EQUITY":
                    logger.warning(
                        "AISection.qsrec 第 %d 筆 category=%r 已自動修正為 EQUITY",
                        i,
                        raw.get("category"),
                    )
                    raw["category"] = "EQUITY"
                    item = raw
            out.append(item)
        return out

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


def _current_affairs_min_voices() -> int:
    raw = os.getenv("CURRENT_AFFAIRS_MIN_VOICES", "2").strip()
    try:
        v = int(raw)
    except ValueError:
        return 2
    return max(2, min(v, 4))


def _current_affairs_max_voices() -> int:
    raw = os.getenv("CURRENT_AFFAIRS_MAX_VOICES", "4").strip()
    try:
        v = int(raw)
    except ValueError:
        return 4
    return max(_current_affairs_min_voices(), min(v, 8))


class RoundtableVoice(BaseModel):
    """Phase 5 optional 〔時事多觀點〕 — 單一發言；數值敘述須對齊 tools／儀表板（由 crew 提示詞約束）。"""

    role: Literal["宏觀", "加密", "股票策略", "風險"]
    viewpoint: str = Field(min_length=1, max_length=4000)
    evidence_anchor: str | None = Field(default=None, max_length=500)
    disagreement: str | None = Field(default=None, max_length=2000)


def dashboard_semantic_keys_for_roundtable(
    crypto: "CryptoSection",
    ai: "AISection",
    *,
    max_keys: int = 24,
) -> str:
    """Human-readable keys from MetricLine labels (for crew whitelist hints)."""
    keys: list[str] = []
    for sec in (crypto, ai):
        for row in sec.dashboard:
            if row.is_section_header:
                continue
            lab = (row.label or "").strip()
            if lab and lab not in keys:
                keys.append(lab)
    return "、".join(keys[:max_keys])


class CurrentAffairsRoundtable(BaseModel):
    """Optional multi-voice block; rendered only when ``BRIEF_CURRENT_AFFAIRS=1`` and field is set."""

    topic: str = Field(min_length=1, max_length=500)
    voices: list[RoundtableVoice] = Field(default_factory=list)
    consensus: str | None = Field(default=None, max_length=4000)
    unresolved: list[str] = Field(default_factory=list)
    dashboard_anchors: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _voice_and_summary_rules(self) -> "CurrentAffairsRoundtable":
        mn, mx = _current_affairs_min_voices(), _current_affairs_max_voices()
        n = len(self.voices)
        if not (mn <= n <= mx):
            raise ValueError(f"時事多觀點 voices 須 {mn}–{mx} 條（當前 {n}）")
        if not any((v.disagreement or "").strip() for v in self.voices):
            raise ValueError("時事多觀點：至少一則 voice 須填 disagreement（非空）")
        has_consensus = bool((self.consensus or "").strip())
        has_unresolved = any((u or "").strip() for u in self.unresolved)
        if not has_consensus and not has_unresolved:
            raise ValueError("時事多觀點：consensus 與 unresolved 須至少一項非空")
        allowed = {str(x).strip() for x in self.dashboard_anchors if str(x).strip()}
        for i, v in enumerate(self.voices, start=1):
            ea = (v.evidence_anchor or "").strip()
            if ea and allowed and ea not in allowed:
                raise ValueError(
                    f"時事多觀點 voice {i}：evidence_anchor 不在 dashboard_anchors 白名單內：{ea!r}"
                )
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

            # Score-field completeness (catalyst_score, flow_score, …) is a
            # business-quality check handled by report_html_gates._strict_pick_scoring().
            # Do NOT duplicate it here: these fields are Optional in the schema,
            # and blocking DailyBriefReport construction when the LLM omits one
            # crashes the entire pipeline before the gate layer can even report it.

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
    if os.getenv("STRICT_INSTITUTIONAL_PHASE_B_GATE", "0").lower() in ("1", "true", "yes"):
        issues.extend(_institutional_phase_b_structured_issues(cr, ai_sec))
    if os.getenv("STRICT_INSTITUTIONAL_PHASE_C_GATE", "0").lower() in ("1", "true", "yes"):
        issues.extend(_institutional_phase_c_structured_issues(cr, ai_sec))
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
    if not (2 <= len(sup) <= 3):
        out.append(f"支持論點須 2–3 條（當前 {len(sup)}）")
    if not (2 <= len(con) <= 3):
        out.append(f"反駁論點須 2–3 條（當前 {len(con)}）")
    ass = [str(x).strip() for x in cr.key_assumptions_lines if str(x).strip()]
    if not (2 <= len(ass) <= 4):
        out.append(f"關鍵假設須 2–4 條（當前 {len(ass)}）")
    if not (cr.narrative_invalidation_summary or "").strip():
        out.append("結構化缺少敘事失效（narrative_invalidation_summary）")
    return out


def _institutional_phase_b_structured_issues(cr: CryptoSection, ai_sec: AISection) -> list[str]:
    """When STRICT_INSTITUTIONAL_PHASE_B_GATE=1, require Phase B blocks."""
    out: list[str] = []
    if not (cr.portfolio_framing_summary or "").strip():
        out.append("結構化缺少組合與曝險框架（portfolio_framing_summary）")
    probs, perr = _parse_scenario_probability_notes(cr.scenario_probability_notes or "")
    if perr:
        out.extend(perr)
    elif probs is not None and sum(probs) != 100:
        out.append(f"三情境機率合計須為 100%（當前合計 {sum(probs)}）")
    for label, items in (("加密", cr.news), ("AI", ai_sec.news)):
        for n in items:
            pn = (n.pricing_note or "").strip()
            if pn not in _PRICING_NOTE_CANONICAL:
                out.append(
                    f"{label}新聞〔{n.index}〕pricing_note 須為「未定價／增量資訊」「大致已定價」「已高度反應」之一"
                )
    return out


_EVENT_CALENDAR_DATE_RE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?"
)


def _institutional_phase_c_structured_issues(cr: CryptoSection, ai_sec: AISection) -> list[str]:
    """When STRICT_INSTITUTIONAL_PHASE_C_GATE=1, require Phase C valuation, calendar, liquidity."""
    out: list[str] = []
    if not (cr.crypto_cycle_valuation_notes or "").strip():
        out.append("結構化缺少加密週期與估值錨（crypto_cycle_valuation_notes）")
    if not (cr.equity_valuation_framing or "").strip():
        out.append("結構化缺少美股估值框架（equity_valuation_framing）")
    cal = [str(x).strip() for x in cr.event_calendar_lines if str(x).strip()]
    if not (3 <= len(cal) <= 6):
        out.append(f"近端事件日曆須 3–6 條（當前 {len(cal)}）")
    for i, ln in enumerate(cal, start=1):
        if not _EVENT_CALENDAR_DATE_RE.search(ln):
            out.append(f"事件日曆第 {i} 條須含可解析日期（MM/DD 或 YYYY-MM-DD）")
    for label, legs in (("加密", cr.trade_legs), ("AI", ai_sec.trade_legs)):
        for j, leg in enumerate(legs, start=1):
            if not (leg.liquidity_execution_note or "").strip():
                out.append(f"{label}交易腿 {leg.asset} 缺少流動性／執行註記（liquidity_execution_note）")
    return out


def _parse_scenario_probability_notes(raw: str) -> tuple[list[int] | None, list[str]]:
    """Parse bull/base/bear percentages from scenario_probability_notes; return (percents, error messages)."""
    err: list[str] = []
    text = (raw or "").strip()
    if not text:
        return None, ["結構化缺少三情境機率（scenario_probability_notes）"]
    lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
    if len(lines) < 3:
        return None, [f"三情境機率須恰好 3 行（當前 {len(lines)}）"]
    lines = lines[:3]
    pct_re = re.compile(r"(?:機率|概率)[：:\s]*(\d{1,3})\s*%|（\s*(\d{1,3})\s*%）|\(\s*(\d{1,3})\s*%\s*\)")
    found: list[int] = []
    for i, ln in enumerate(lines, start=1):
        m = pct_re.search(ln)
        if not m:
            err.append(f"三情境機率第 {i} 行須含「機率 xx%」或「（xx%）」")
            continue
        g = m.groups()
        p = int(next(x for x in g if x is not None))
        if not (0 <= p <= 100):
            err.append(f"三情境機率第 {i} 行百分比須 0–100")
            continue
        found.append(p)
    if err:
        return None, err
    if len(found) != 3:
        return None, ["三情境機率須每行可解析一個百分比"]
    return found, []


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
    current_affairs_roundtable: CurrentAffairsRoundtable | None = Field(
        default=None,
        description="Phase 5 optional 〔時事多觀點〕；預設 None。僅在 BRIEF_CURRENT_AFFAIRS=1 時渲染。",
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
