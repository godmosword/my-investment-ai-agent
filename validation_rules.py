import re


HAS_REGIME_RE = re.compile(r"risk[\s_\-]*on|risk[\s_\-]*off|neutral", re.IGNORECASE)
HAS_DASHBOARD_RE = re.compile(r"DXY|BTC\s*OI|資金費率|模型排名|ML.*權重|RSI|Fear.*Greed|儀表板", re.IGNORECASE)
HAS_AI_SECTION_RE = re.compile(r"AI\s*市場|AI\s*產業新聞|AI\s*數據儀表板", re.IGNORECASE)
HAS_CRYPTO_SECTION_RE = re.compile(r"加密市場|核心新聞|數據儀表板", re.IGNORECASE)
HAS_DATA_MISSING_RE = re.compile(r"\[DATA_MISSING:")
DATA_MISSING_FIELDS_RE = re.compile(r"\[DATA_MISSING:([^\]]+)\]")
# 以下字串仍保留，供 grep／文件對照；**語意判斷請用** `text_has_positive_trade_watch_mode` /
# `span_has_positive_trade_watch_declaration`，避免「非觀望模式」「除非觀望…」等子字串誤判。
_TRADE_WATCH_MODE_LITERAL = r"觀望模式|資料不足觀望|暫不開新倉|暫不提供股票進出場價格"
TRADE_WATCH_MODE_RE = re.compile(_TRADE_WATCH_MODE_LITERAL)
TRADE_WATCH_CRYPTO_OP_RE = re.compile(r"觀望模式|資料不足觀望|暫不開新倉")
TRADE_WATCH_AI_OP_RE = re.compile(_TRADE_WATCH_MODE_LITERAL)

_CRYPTO_WATCH_PHRASES = ("觀望模式", "資料不足觀望", "暫不開新倉")
_AI_WATCH_PHRASES = _CRYPTO_WATCH_PHRASES + ("暫不提供股票進出場價格",)
_MODE_WATCH_PHRASES = _AI_WATCH_PHRASES


def _watch_phrase_negated_at(text: str, start: int, phrase: str) -> bool:
    """
    該次命中是否為否定／排除語境（避免「非觀望模式」仍命中「觀望模式」子字串）。
    start 為 phrase 在 text 中的起始 index。
    """
    if phrase.startswith("觀望"):
        if start >= 1 and text[start - 1] == "非":
            # 除非觀望 → 非前為「除」時不視為否定整個「觀望模式」子串
            if start >= 2 and text[start - 2] == "除":
                return False
            return True
        if start >= 2 and text[start - 2 : start] in ("不是", "勿", "不採", "未能", "無需"):
            return True
        if start >= 3 and text[start - 3 : start] == "並非":
            return True
        return False
    if phrase.startswith("資料"):
        if start >= 1 and text[start - 1] == "非":
            return True
        if start >= 3 and text[start - 3 : start] == "並非":
            return True
        return False
    if phrase.startswith("暫"):
        win = text[max(0, start - 4) : start]
        if win.endswith(("並非", "不是", "勿", "非")):
            return True
        return False
    return False


def _span_has_any_positive_watch_phrase(span: str, phrases: tuple[str, ...]) -> bool:
    for ph in phrases:
        for m in re.finditer(re.escape(ph), span):
            if not _watch_phrase_negated_at(span, m.start(), ph):
                return True
    return False


def text_has_positive_trade_watch_mode(text: str) -> bool:
    """全文是否宣告「交易觀望」以放寬 R:R 等（排除否定句）。"""
    return _span_has_any_positive_watch_phrase(text, _MODE_WATCH_PHRASES)


def span_has_positive_trade_watch_declaration(span: str, *, is_ai: bool) -> bool:
    """單一操作段內是否有**肯定**觀望宣告（供與可執行價位互斥檢查）。"""
    phrases = _AI_WATCH_PHRASES if is_ai else _CRYPTO_WATCH_PHRASES
    return _span_has_any_positive_watch_phrase(span, phrases)
QSREC_MARKERS_RE = re.compile(r"\[QSREC_START\][\s\S]*?\[QSREC_END\]")
HAS_RR_RE = re.compile(r"R:R\s*=\s*1:\d+(?:\.\d+)?", re.IGNORECASE)
HAS_MAX_DRAWDOWN_RE = re.compile(r"最大回撤風險[：:]\s*(?:<code>)?\s*-\d+(?:\.\d+)?%(?:</code>)?")
HAS_EXPECTED_WIN_RATE_RE = re.compile(r"(?:預期勝率|勝率預期)[：:]\s*(?:<code>)?\s*\d+(?:\.\d+)?\s*%?(?:</code>)?")
HAS_SIGNAL_SCORE_RE = re.compile(
    r"Signal\s*Score[：:]\s*(?:<code>)?\s*\d+(?:\.\d+)?(?:\s*/\s*100)?(?:</code>)?",
    re.IGNORECASE,
)
# 允許 <b>訊號衝突摘要</b>：等 HTML 包裝
HAS_SIGNAL_CONFLICT_RE = re.compile(
    r"[訊信]號衝突(?:摘要|分析)?(?:\s*</b>)?\s*[：:]|[訊信]號衝突(?:摘要|分析)?\s*(?:<[^>]+>)?\s*[：:]",
    re.IGNORECASE,
)
HAS_RISK_BUDGET_RE = re.compile(
    r"今日風險預算(?:\s*</b>)?\s*[：:]|今日風險預算\s*(?:<[^>]+>)?\s*[：:]",
    re.IGNORECASE,
)
NA_TOKEN_RE = re.compile(r"\bN/A\b")
HAS_LOW_CONFIDENCE_RE = re.compile(r"低置信度|低信心")


def plain_text_for_investment_numeric_gate(html: str) -> str:
    """Strip Telegram HTML tags so 投資解讀 Gate sees digits inside <i>/<b>/<code> wrappers."""
    if not html:
        return ""
    return re.sub(r"<[^>]+>", " ", html)


# 允許負號（資金費率 -0.0008% 等）；Gate 於 strip HTML 後套用
_NUMERIC_INVESTMENT_TOKEN = r"(?:\-?\d+(?:\.\d+)?%?|\$[0-9,]+(?:\.\d+)?)"
# Telegram 模板為 <i>投資解讀</i>：…；strip HTML 後「投資解讀」與冒號間可能有空格，須允許 \s*。
NUMERIC_INVESTMENT_LINE_RE = re.compile(rf"投資解讀\s*[：:][^\n]*({_NUMERIC_INVESTMENT_TOKEN})")
NUMERIC_INVESTMENT_MULTI_RE = re.compile(
    rf"投資解讀\s*[：:][^\n]*(?:\n[^\n]*){{0,5}}({_NUMERIC_INVESTMENT_TOKEN})"
)
MODE_TAGS_RE = re.compile(
    r"【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*",
    re.IGNORECASE,
)
BUDGET_TAGS_RE = re.compile(r"今日風險預算[：:][^\n]*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)", re.IGNORECASE)
MALFORMED_INVALIDATION_RE = re.compile(r"失效條件[：:]\s*(?:<code>)?\s*(?:</code>)?\s*(?:\n|$)")
# Match 現價：<code>$N/A</code>、進場 N/A、全形｜分隔；$ 可選（模板常輸出 $N/A）
UNACTIONABLE_TRADE_RE = re.compile(
    r"·\s*\$[A-Z0-9/]+[\s\S]*?(?:現價|進場|目標|停損)[：:｜]\s*(?:<code>)?\s*\$?\s*N\s*/\s*A\b(?:</code>)?",
    re.IGNORECASE,
)
CODE_LEAK_RE = re.compile(r"multi_timeframe_tool\s*\(")
IMPACT_LEAK_RE = re.compile(r"\[IMPACT:|🎯\s*IMPACT|📍\s*受影響資產|📈\s*做多機會|📉\s*做空風險")

# ── Pre-render / post-render coercions (align with report_html_gates macro outlier band) ──
MACRO_YIELD_MIN_PCT, MACRO_YIELD_MAX_PCT = 0.1, 9.0
MACRO_YIELD_SUB_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(10Y\s*[:：]\s*)([0-9,]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE),
    re.compile(r"(10Y\D{0,22}?)([0-9,]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE),
    re.compile(r"(2Y\s*[:：]\s*)([0-9,]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE),
    re.compile(r"(2Y\D{0,22}?)([0-9,]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE),
)

_NEWS_TIMESTAMP_LINE_MISSING_TZ_RE = re.compile(
    r"^(\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\d{1,2}:\d{2}(?::\d{2})?)"
    r"(?!\s*(?:UTC|GMT)\s*[+＋]\s*0?8|\s*HKT\b|\s*(?:香港|北京|台北)時間)"
    r"(\])$",
    re.IGNORECASE,
)


def sanitize_us_treasury_yield_tokens_in_line(line: str) -> str:
    """Replace out-of-range 10Y/2Y percentage tokens with N/A (matches tools_legacy sane band)."""

    def _fix_yield_match(m: re.Match[str]) -> str:
        try:
            val = float(m.group(2).replace(",", ""))
        except ValueError:
            return m.group(0)
        if not (MACRO_YIELD_MIN_PCT <= val <= MACRO_YIELD_MAX_PCT):
            g2_start = m.start(2) - m.start(0)
            return m.group(0)[:g2_start] + "N/A"
        return m.group(0)

    out = line
    for pat in MACRO_YIELD_SUB_PATTERNS:
        out = pat.sub(_fix_yield_match, out)
    return out


def sanitize_lines_with_us_treasury_keyword(lines: list[str]) -> list[str]:
    """Only touch lines mentioning 美債 to avoid accidental edits elsewhere."""
    return [
        sanitize_us_treasury_yield_tokens_in_line(line) if "美債" in line else line for line in lines
    ]


def ensure_news_timestamp_line_utc8(timestamp_line: str) -> str:
    """If bracketed time lacks HK-style tz, append `` UTC+8`` before closing bracket (Gate 新聞時區)."""
    if not isinstance(timestamp_line, str):
        return timestamp_line
    s = timestamp_line.strip()
    m = _NEWS_TIMESTAMP_LINE_MISSING_TZ_RE.match(s)
    if m:
        return m.group(1) + " UTC+8" + m.group(2)
    return timestamp_line


# Align with ``report_html_postprocess`` / Gate: skip conditional regime sentences.
_CONDITIONAL_REGIME_IN_LINE_RE = re.compile(
    r"(?:若|如果|假設|when|if)\s*.{0,80}(?:risk_on|risk_off|neutral)",
    re.IGNORECASE,
)
_REGIME_TOKEN_BOUNDARY_RE = re.compile(r"\b(risk_on|risk_off|neutral)\b", re.IGNORECASE)


def normalize_authoritative_regime_tokens_multiline(text: str, regime: str) -> str:
    """Replace standalone risk_on/risk_off/neutral tokens with ``regime``; keep conditional lines."""
    if not isinstance(text, str) or not text.strip() or not (regime or "").strip():
        return text
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        if _CONDITIONAL_REGIME_IN_LINE_RE.search(line):
            out.append(line)
        else:
            out.append(_REGIME_TOKEN_BOUNDARY_RE.sub(regime, line))
    return "\n".join(out)


def crypto_risk_budget_has_regime_token(regime: str, summary: str | None) -> bool:
    """True if summary already mentions ``regime`` with flexible underscore/space/hyphen (schema/Gate)."""
    if not isinstance(regime, str) or not regime.strip():
        return True
    s = summary if isinstance(summary, str) else ""
    pat = re.escape(regime.strip()).replace(r"_", r"[\s_\-]+")
    return bool(re.search(pat, s, re.IGNORECASE))


def ensure_crypto_risk_budget_regime_token(summary: str, regime: str) -> str:
    """If summary lacks the canonical regime substring, prepend ``regime｜`` (pipeline safety net).

    Avoids DailyBriefReport validation error「加密今日風險預算未包含主 regime token」when the model
    writes Chinese-only risk budget lines without risk_on/risk_off/neutral.
    """
    if not isinstance(regime, str) or not regime.strip():
        return summary if isinstance(summary, str) else ""
    r = regime.strip()
    s = summary if isinstance(summary, str) else ""
    if crypto_risk_budget_has_regime_token(r, s):
        return s
    if not s.strip():
        return r
    return f"{r}｜{s.lstrip()}"


_REPEAT_PICK_LEADING_RE = re.compile(
    r"^\s*(重複選用理由|重複選股理由|重複持有理由)\s*[：:]\s*",
    re.UNICODE,
)

# Reader-facing: avoids Jinja 「本日選擇理由：」+ body 「重複選用理由：」double headers.
# Wording must still match ``_REPEAT_PICK_REASON_RE`` (e.g. 連日維持); omit internal BQ/pipeline jargon.
_REPEAT_SAME_YESTERDAY_PREFIX = "連日維持與昨日相同建議標的；"


def normalize_leading_repeat_pick_phrase(reason: str, *, same_as_yesterday: bool) -> str:
    """Rewrite or strip a leading 重複選用理由：… label (template already prints 本日選擇理由：).

    When ``same_as_yesterday`` is True (QSREC canonical set matches BQ yesterday), replace the label with
    ``連日維持與昨日相同建議標的；`` + remainder so ``_REPEAT_PICK_REASON_RE`` still matches.

    When False, strip the redundant leading label only so the narrative is not mislabeled as a repeat pick.
    """
    if not isinstance(reason, str) or not reason.strip():
        return reason if isinstance(reason, str) else ""
    m = _REPEAT_PICK_LEADING_RE.match(reason)
    if not m:
        return reason
    rest = reason[m.end() :].lstrip()
    if same_as_yesterday:
        return f"{_REPEAT_SAME_YESTERDAY_PREFIX}{rest}" if rest else "連日維持與昨日相同建議標的。"
    return rest
