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
NUMERIC_INVESTMENT_LINE_RE = re.compile(r"投資解讀[：:][^\n]*(\d+(?:\.\d+)?%?|\$[0-9,]+(?:\.\d+)?)")
NUMERIC_INVESTMENT_MULTI_RE = re.compile(
    r"投資解讀[：:][^\n]*(?:\n[^\n]*){0,5}(\d+(?:\.\d+)?%?|\$[0-9,]+(?:\.\d+)?)"
)
MODE_TAGS_RE = re.compile(
    r"【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*",
    re.IGNORECASE,
)
BUDGET_TAGS_RE = re.compile(r"今日風險預算[：:][^\n]*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)", re.IGNORECASE)
MALFORMED_INVALIDATION_RE = re.compile(r"失效條件[：:]\s*(?:<code>)?\s*(?:</code>)?\s*(?:\n|$)")
UNACTIONABLE_TRADE_RE = re.compile(r"·\s*\$[A-Z0-9/]+[\s\S]*?(?:現價|進場|目標|停損)[：:]\s*(?:<code>)?\s*N/A")
CODE_LEAK_RE = re.compile(r"multi_timeframe_tool\s*\(")
IMPACT_LEAK_RE = re.compile(r"\[IMPACT:|🎯\s*IMPACT|📍\s*受影響資產|📈\s*做多機會|📉\s*做空風險")
