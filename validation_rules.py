import re


HAS_REGIME_RE = re.compile(r"risk[\s_\-]*on|risk[\s_\-]*off|neutral", re.IGNORECASE)
HAS_DASHBOARD_RE = re.compile(r"DXY|BTC\s*OI|資金費率|模型排名|ML.*權重|RSI|Fear.*Greed|儀表板", re.IGNORECASE)
HAS_AI_SECTION_RE = re.compile(r"AI\s*市場|AI\s*產業新聞|AI\s*數據儀表板", re.IGNORECASE)
HAS_CRYPTO_SECTION_RE = re.compile(r"加密市場|核心新聞|數據儀表板", re.IGNORECASE)
HAS_DATA_MISSING_RE = re.compile(r"\[DATA_MISSING:")
DATA_MISSING_FIELDS_RE = re.compile(r"\[DATA_MISSING:([^\]]+)\]")
# 全文是否進入「交易觀望」放寬（新聞分段、R:R 等）
TRADE_WATCH_MODE_RE = re.compile(r"觀望模式|資料不足觀望|暫不開新倉|暫不提供股票進出場價格")
# 觀望／可執行價互斥：加密精準操作段不含「股票」用語，避免誤判模板殘句
TRADE_WATCH_CRYPTO_OP_RE = re.compile(r"觀望模式|資料不足觀望|暫不開新倉")
# AI／美股段含股票專用觀望句
TRADE_WATCH_AI_OP_RE = re.compile(
    r"觀望模式|資料不足觀望|暫不開新倉|暫不提供股票進出場價格"
)
QSREC_MARKERS_RE = re.compile(r"\[QSREC_START\][\s\S]*?\[QSREC_END\]")
HAS_RR_RE = re.compile(r"R:R\s*=\s*1:\d+(?:\.\d+)?", re.IGNORECASE)
HAS_MAX_DRAWDOWN_RE = re.compile(r"最大回撤風險[：:]\s*(?:<code>)?\s*-\d+(?:\.\d+)?%(?:</code>)?")
HAS_EXPECTED_WIN_RATE_RE = re.compile(r"(?:預期勝率|勝率預期)[：:]\s*(?:<code>)?\s*\d+(?:\.\d+)?\s*%?(?:</code>)?")
HAS_SIGNAL_SCORE_RE = re.compile(
    r"Signal\s*Score[：:]\s*(?:<code>)?\s*\d+(?:\.\d+)?(?:\s*/\s*100)?(?:</code>)?",
    re.IGNORECASE,
)
HAS_SIGNAL_CONFLICT_RE = re.compile(r"[訊信]號衝突(?:摘要|分析)?[：:]")
HAS_RISK_BUDGET_RE = re.compile(r"今日風險預算[：:]")
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
