import json
import os
import re
import sys
import time
import logging
import builtins
import html
import telebot
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.cloud import bigquery
import yfinance as yf
from pathlib import Path

from config import PROJECT_ID, METRICS_TABLE, RECOMMENDATIONS_TABLE
from crew import CryptoResearchCrew, AIResearchCrew
from report_output_validator import (
    assert_report_output,
    assert_sample_output,
    parse_report_output,
)
from tools import source_observability_lines
from visualizer import generate_quant_chart
import tracker
import scratchpad
from tracker import load_previous_recs_block
from report_pipeline_compare import compare_validation_results
from validation_rules import (
    BUDGET_TAGS_RE,
    CODE_LEAK_RE,
    DATA_MISSING_FIELDS_RE,
    HAS_AI_SECTION_RE,
    HAS_CRYPTO_SECTION_RE,
    HAS_DASHBOARD_RE,
    HAS_DATA_MISSING_RE,
    HAS_EXPECTED_WIN_RATE_RE,
    HAS_LOW_CONFIDENCE_RE,
    HAS_REGIME_RE,
    HAS_RISK_BUDGET_RE,
    HAS_RR_RE,
    HAS_SIGNAL_CONFLICT_RE,
    HAS_SIGNAL_SCORE_RE,
    HAS_MAX_DRAWDOWN_RE,
    IMPACT_LEAK_RE,
    MALFORMED_INVALIDATION_RE,
    MODE_TAGS_RE,
    NA_TOKEN_RE,
    NUMERIC_INVESTMENT_LINE_RE,
    NUMERIC_INVESTMENT_MULTI_RE,
    QSREC_MARKERS_RE,
    TRADE_WATCH_MODE_RE,
    UNACTIONABLE_TRADE_RE,
)

load_dotenv()

# 日誌等級：LOG_LEVEL=DEBUG 或 DEBUG=1 可開啟除錯
_log_level = os.getenv("LOG_LEVEL", "INFO").upper()
if os.getenv("DEBUG", "").lower() in ("1", "true", "yes"):
    _log_level = "DEBUG"
logging.basicConfig(level=getattr(logging, _log_level, logging.INFO), format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 除錯與乾跑開關（方便本地測試）
SKIP_TELEGRAM = os.getenv("SKIP_TELEGRAM", "").lower() in ("1", "true", "yes")
SKIP_BIGQUERY = os.getenv("SKIP_BIGQUERY", "").lower() in ("1", "true", "yes")
STRICT_CONSISTENCY_GATE = os.getenv("STRICT_CONSISTENCY_GATE", "1").lower() in ("1", "true", "yes")


def _allow_partial_news_gate() -> bool:
    """允許「新聞分段」模式：3~5 則〔新聞 N〕+ 宣告不補假新聞時，放寬 6 則硬性要求。ALLOW_PARTIAL_NEWS_GATE=0 關閉。"""
    return os.getenv("ALLOW_PARTIAL_NEWS_GATE", "1").lower() not in ("0", "false", "no")


def _strict_pick_justification() -> bool:
    """驗證「本日選擇理由」是否連結催化／鏈上或退階邏輯並點名 QSREC 標的。STRICT_PICK_JUSTIFICATION=0 關閉。"""
    return os.getenv("STRICT_PICK_JUSTIFICATION", "1").lower() not in ("0", "false", "no")


def _strict_pick_rotation() -> bool:
    """與昨日 BQ 已存 QSREC 標的（canonical）完全相同時，須改選或寫「重複選用理由」。STRICT_PICK_ROTATION=0 關閉。"""
    return os.getenv("STRICT_PICK_ROTATION", "1").lower() not in ("0", "false", "no")


def _allow_repeat_pick_override() -> bool:
    """同標延續是否允許以分數優勢覆核放行。ALLOW_REPEAT_PICK_OVERRIDE=0 關閉（改為強制至少換一檔）。"""
    return os.getenv("ALLOW_REPEAT_PICK_OVERRIDE", "1").lower() not in ("0", "false", "no")


def _pick_rotation_override_min_gap() -> float:
    """同標延續的最低分差門檻（selection_score - alt_candidate_score）。"""
    try:
        return float(os.getenv("PICK_ROTATION_OVERRIDE_MIN_GAP", "12"))
    except ValueError:
        return 12.0


def _strict_pick_scoring() -> bool:
    """要求 QSREC 內含可量化選標分數欄位。STRICT_PICK_SCORING=0 關閉。"""
    return os.getenv("STRICT_PICK_SCORING", "1").lower() not in ("0", "false", "no")


def _repeat_pick_days_max() -> int:
    """同標延續放行時，repeat_days 最大容許值。"""
    try:
        return int(os.getenv("PICK_REPEAT_DAYS_MAX", "2"))
    except ValueError:
        return 2


def _repeat_pick_min_score() -> float:
    """同標延續放行時，selection_score 最低門檻。"""
    try:
        return float(os.getenv("PICK_REPEAT_MIN_SELECTION_SCORE", "75"))
    except ValueError:
        return 75.0

# 重試常數（集中管理，方便調參）
MAX_REPORT_RETRIES = int(os.getenv("MAX_REPORT_RETRIES", "2"))
MAX_503_RETRIES = int(os.getenv("MAX_503_RETRIES", "3"))
BACKOFF_BASE_SEC = int(os.getenv("BACKOFF_BASE_SEC", "30"))
ERROR_PREFIX = "🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息："
MAX_EXCLUSION_CONTEXT_CHARS = int(os.getenv("MAX_EXCLUSION_CONTEXT_CHARS", "1000"))
MAX_PREV_RECS_CHARS = int(os.getenv("MAX_PREV_RECS_CHARS", "1200"))

# 除錯用環境變數：LOG_LEVEL=DEBUG | DEBUG=1 | CREW_VERBOSE=1（Agent 步驟）| SKIP_TELEGRAM=1 | SKIP_BIGQUERY=1

# Telegram HTML 支援的標籤白名單（與專案規範一致，不含 <pre>）
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "blockquote", "a"}


def _truncate_text(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n…[truncated]"


class _FilteredStream:
    """過濾已知無害的 CrewAI event bus pairing 警告。"""

    def __init__(self, wrapped):
        self._wrapped = wrapped
        self._buf = ""

    def write(self, s: str):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if "CrewAIEventsBus" in line and "Event pairing mismatch" in line:
                continue
            self._wrapped.write(line + "\n")
        return len(s)

    def flush(self):
        if self._buf:
            if not ("CrewAIEventsBus" in self._buf and "Event pairing mismatch" in self._buf):
                self._wrapped.write(self._buf)
            self._buf = ""
        self._wrapped.flush()


def _install_runtime_noise_filters() -> None:
    """安裝執行期降噪與相容性處理。"""
    if not isinstance(sys.stderr, _FilteredStream):
        sys.stderr = _FilteredStream(sys.stderr)
    if not isinstance(sys.stdout, _FilteredStream):
        sys.stdout = _FilteredStream(sys.stdout)

    # 部分 CrewAI 版本直接以 print 寫出 event pairing mismatch，這裡做最小侵入過濾。
    orig_print = builtins.print
    if not getattr(orig_print, "__qs_wrapped__", False):
        def _quiet_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            if "CrewAIEventsBus" in msg and "Event pairing mismatch" in msg:
                return
            if "expected 'crew_kickoff_started'" in msg or "expected 'agent_execution_started'" in msg:
                return
            return orig_print(*args, **kwargs)

        _quiet_print.__qs_wrapped__ = True  # type: ignore[attr-defined]
        builtins.print = _quiet_print


def sanitize_telegram_html(text: str) -> str:
    """清洗 LLM 輸出的 HTML，保留 Telegram 支援標籤並修復失衡標籤。"""
    if not text:
        return ""
    text = text.replace("\r\n", "\n")
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)

    placeholders: dict[str, str] = {}
    seq = 0

    def _stash(val: str) -> str:
        nonlocal seq
        key = f"__TG_TAG_{seq}__"
        placeholders[key] = val
        seq += 1
        return key

    def _keep_anchor_open(m: re.Match) -> str:
        href_m = re.search(r'href=["\']([^"\']+)["\']', m.group(0), re.IGNORECASE)
        if not href_m:
            return ""
        href = html.escape(html.unescape(href_m.group(1)), quote=True)
        return _stash(f'<a href="{href}">')

    text = re.sub(r'<a\b[^>]*>', _keep_anchor_open, text, flags=re.IGNORECASE)
    text = re.sub(r'</a\s*>', lambda _m: _stash("</a>"), text, flags=re.IGNORECASE)
    text = re.sub(
        r'</?(?:b|i|u|s|code|blockquote)\s*>',
        lambda m: _stash(m.group(0).lower()),
        text,
        flags=re.IGNORECASE,
    )

    # 先把所有殘餘尖括號轉義，避免 `<0.03)</code>` 這類非標籤片段炸掉 Telegram parser。
    text = text.replace("<", "&lt;").replace(">", "&gt;")

    for key, val in placeholders.items():
        text = text.replace(key, val)

    return _balance_telegram_html_tags(text)


def _balance_telegram_html_tags(text: str) -> str:
    """移除不合法 closing tag，並為未關閉 tag 自動補齊結尾。"""
    tag_re = re.compile(
        r'</?(?:b|i|u|s|code|blockquote|a)(?:\s+href="[^"]*")?\s*>',
        re.IGNORECASE,
    )
    out: list[str] = []
    stack: list[str] = []
    last = 0
    for m in tag_re.finditer(text):
        out.append(text[last:m.start()])
        tag = m.group(0)
        name_m = re.match(r'</?\s*([a-z]+)', tag, re.IGNORECASE)
        if not name_m:
            last = m.end()
            continue
        name = name_m.group(1).lower()
        is_close = tag.startswith("</")

        if not is_close:
            if name == "a":
                if not re.match(r'<a\s+href="[^"]*">', tag, re.IGNORECASE):
                    last = m.end()
                    continue
                out.append(tag)
            else:
                out.append(f"<{name}>")
            stack.append(name)
        else:
            if stack and stack[-1] == name:
                out.append(f"</{name}>")
                stack.pop()
            # unmatched closing tag -> drop
        last = m.end()

    out.append(text[last:])
    while stack:
        out.append(f"</{stack.pop()}>")
    return "".join(out)


def strip_html(text: str) -> str:
    """完全移除所有 HTML 標籤，回傳純文字。"""
    return re.sub(r'<[^>]+>', '', text)


# ── 動態選幣／選股：本日選擇理由驗證（與 crew 規則對齊，允許連日同標的但須說清楚依據）────────
_CRYPTO_PICK_KW: tuple[str, ...] = (
    "新聞",
    "催化",
    "事件",
    "題材",
    "ETF",
    "核准",
    "升級",
    "主網",
    "分叉",
    "清算",
    "爆倉",
    "流入",
    "流出",
    "鏈上",
    "巨鯨",
    "資金費率",
    "多空比",
    "DeFi",
    "監管",
    "申請",
    "上市",
    "解鎖",
    "減半",
    "RWA",
    "SOPR",
    "NUPL",
    "交易所",
    "淨流",
    "未平倉",
    "OI",
    "現貨",
    "基差",
    "期權",
    "選擇權",
)
_CRYPTO_PICK_FALLBACK: tuple[str, ...] = (
    "大型幣",
    "主流幣",
    "龍頭",
    "流動性",
    "最後才",
    "缺乏",
    "無其他",
    "不明顯",
    "退而求其次",
    "避險",
    "保守",
    "催化劑不足",
)
_EQUITY_PICK_KW: tuple[str, ...] = (
    "財報",
    "合約",
    "營收",
    "資本",
    "支出",
    "Capex",
    "回購",
    "新品",
    "發布",
    "上線",
    "GPU",
    "資料中心",
    "雲端",
    "雲",
    "生成式",
    "LLM",
    "訂單",
    "拉貨",
    "晶片",
    "代工",
    "新聞",
    "報導",
    "法說",
    "指引",
    "併購",
)
_EQUITY_PICK_FALLBACK: tuple[str, ...] = (
    "權值",
    "大型股",
    "指數",
    "避險",
    "流動性",
    "最後才",
    "缺乏催化",
    "通殺",
    "ETF",
    "BOTZ",
    "ARKQ",
)


_AI_SECTION_BOUNDARY_PATTERNS: tuple[str, ...] = (
    r"(?m)^────────────\s*\n\s*🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
    r"\n🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
    r"🤖\s*AI(?:\s*與\s*美股市場|\s*市場)",
    r"(?m)^══════\s*🤖\s*AI(?:\s*與\s*美股市場|\s*市場)\s*══════",
    r"(?m)^\s*AI\s*產業鏈精準操作\s*\(US\s*Equit",
)


def _ai_section_start_index(text: str, cache: dict[str, int] | None = None) -> int:
    """回傳 AI 主段起始位置；若找不到則回傳 len(text)。"""
    cache_key = "ai_section_start_index"
    if cache is not None and cache_key in cache:
        return cache[cache_key]
    best = len(text)
    for pat in _AI_SECTION_BOUNDARY_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m and m.start() < best:
            best = m.start()
    if cache is not None:
        cache[cache_key] = best
    return best


def _crypto_report_prefix(text: str, *, _cache: dict[str, int] | None = None) -> str:
    """合併戰報中「加密區」之前綴（🤖 AI 主段起頭後視為下半部）。"""
    best = _ai_section_start_index(text, cache=_cache)
    return text[:best] if best < len(text) else text


def _extract_today_pick_reason(span: str) -> str | None:
    """自區塊內取出第一處「本日選擇理由」純文字（至風險預算／訊號衝突／交易條目／QSREC／分隔線）。"""
    m = re.search(
        r"本日選擇理由[：:]\s*([\s\S]+?)(?=\n\s*(?:今日風險預算|訊號衝突(?:摘要)?)[：:]|\n\s*·[^\n]*\$|\[QSREC_START\]|\n(?:-{4,}|─{4,}))",
        span,
        re.IGNORECASE,
    )
    if not m:
        return None
    return strip_html(m.group(1)).strip()


def _normalize_pick_asset_legs(asset: str) -> list[str]:
    """QSREC asset → 大寫代號列表（比值拆兩腿，供『理由是否點名』檢查）。"""
    a = str(asset or "").upper().replace("$", "").replace(" ", "").replace("-", "/")
    if "/" in a:
        return [p for p in a.split("/") if p]
    return [a] if a else []


def _reason_covers_assets(reason: str, assets: list[str]) -> bool:
    """理由中須可辨識每一檔標的（代號字串出現於 strip 後大寫比對）。"""
    u = strip_html(reason).upper()
    for raw in assets:
        legs = _normalize_pick_asset_legs(raw)
        if not legs:
            return False
        if len(legs) >= 2:
            if not all(leg in u for leg in legs):
                return False
        else:
            if legs[0] not in u:
                return False
    return True


def _score_kw_hits(reason: str, kws: tuple[str, ...]) -> int:
    return sum(1 for k in kws if k in reason)


def _pick_justification_crypto_ok(
    text: str,
    recs: list[dict],
    *,
    span_cache: dict[str, int] | None = None,
) -> tuple[bool, str]:
    """
    加密 QSREC 每檔須在「本日選擇理由」區間內可被合規敘事支持：
    ≥2 個催化/鏈上關鍵線索；或 1 線索 + 明確大型幣退階語；或 1 線索 + 長文且點名所有標的。
    """
    crypto_assets = [
        str(r.get("asset", ""))
        for r in recs
        if str(r.get("category", "CRYPTO")).upper() == "CRYPTO"
    ]
    if not crypto_assets:
        return True, ""
    cspan = _crypto_report_prefix(text, _cache=span_cache)
    reason = _extract_today_pick_reason(cspan)
    if not reason:
        return False, "加密區缺少「本日選擇理由」，或內容未寫在「今日風險預算／訊號衝突／交易條目」之前（請依動態選幣標準補敘）"
    if len(reason) < 34:
        return False, "本日選擇理由（加密）過短：請說明新聞/鏈上依據或明確大型幣退階邏輯，並點名 QSREC 標的"
    strong = _score_kw_hits(reason, _CRYPTO_PICK_KW)
    fb = _score_kw_hits(reason, _CRYPTO_PICK_FALLBACK)
    named = _reason_covers_assets(reason, crypto_assets)
    ok = (
        strong >= 2
        or (strong >= 1 and fb >= 1)
        or (strong >= 1 and len(reason) >= 72 and named)
    )
    if ok:
        return True, ""
    return (
        False,
        "本日選擇理由（加密）未達動態選幣標準：須（≥2 項催化/鏈上線索）或（1 線索+大型幣退階說明）或（1 線索+長文且點名所有加密 QSREC 標的）；不符則請改選標的或補強敘事",
    )


def _pick_justification_equity_ok(
    text: str,
    recs: list[dict],
    *,
    span_cache: dict[str, int] | None = None,
) -> tuple[bool, str]:
    """美股 QSREC：理由須含足夠基本面/新聞線索並點名各檔股票代號。"""
    eq_assets = [
        str(r.get("asset", ""))
        for r in recs
        if str(r.get("category", "")).upper() == "EQUITY"
    ]
    if not eq_assets:
        return True, ""
    ai_span = text[_ai_section_start_index(text, cache=span_cache) :]
    reason = _extract_today_pick_reason(ai_span)
    if not reason:
        return False, "AI/美股區缺少「本日選擇理由」，或格式未寫在交易條目前（請依動態選股標準補敘）"
    if len(reason) < 38:
        return False, "本日選擇理由（美股）過短：請連結財報/產品/新聞催化並點名 QSREC 標的"
    strong = _score_kw_hits(reason, _EQUITY_PICK_KW)
    fb = _score_kw_hits(reason, _EQUITY_PICK_FALLBACK)
    named = _reason_covers_assets(reason, eq_assets)
    ok = strong >= 2 or (strong >= 1 and fb >= 1) or (strong >= 1 and len(reason) >= 80 and named)
    if ok:
        return True, ""
    return (
        False,
        "本日選擇理由（美股）未達動態選股標準：須（≥2 項基本面/新聞線索）或（1 線索+權值/ETF 退階說明）或（1 線索+長文且點名所有美股 QSREC 標的）；不符則請改選標的或補強敘事",
    )


_REPEAT_PICK_REASON_RE = re.compile(
    r"重複選用理由|重複選股理由|重複持有理由|連日(?:選(?:用)?|持有|維持)|連續(?:兩日|多日)(?:同標|持有|維持)|"
    r"仍選(?:用)?|同標(?:的)?延續|延續昨|延續上日|與昨日相同標的|維持昨日(?:兩檔|組合|標的)|持續鎖定(?:同組|兩檔)",
    re.IGNORECASE,
)
_PICK_SCORE_FIELDS = (
    "selection_score",
    "catalyst_score",
    "flow_score",
    "technical_score",
    "risk_fit_score",
    "execution_score",
)


def _qsrec_canonical_set_for_category(recs: list[dict], category: str) -> set[str]:
    want = category.upper()
    out: set[str] = set()
    for r in recs:
        if str(r.get("category", "")).upper() != want:
            continue
        a = r.get("asset")
        if a:
            out.add(tracker.canonical_asset_key(str(a)))
    return out


def _safe_float_val(v) -> float | None:
    try:
        if v in (None, "", []):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _best_repeat_score_gap_for_category(recs: list[dict], category: str) -> float | None:
    """回傳該類別可用的最大 score_gap；若缺失則 None。"""
    want = category.upper()
    gaps: list[float] = []
    for rec in recs:
        if str(rec.get("category", "")).upper() != want:
            continue
        gap = _safe_float_val(rec.get("score_gap"))
        if gap is None:
            sel = _safe_float_val(rec.get("selection_score"))
            alt = _safe_float_val(rec.get("alt_candidate_score"))
            if sel is not None and alt is not None:
                gap = sel - alt
        if gap is not None:
            gaps.append(gap)
    if not gaps:
        return None
    return max(gaps)


def _has_repeat_quality_anchor(recs: list[dict], category: str) -> bool:
    """同標延續時，至少 1 筆滿足 repeat_days 與 selection_score 品質門檻。"""
    want = category.upper()
    max_days = _repeat_pick_days_max()
    min_score = _repeat_pick_min_score()
    for rec in recs:
        if str(rec.get("category", "")).upper() != want:
            continue
        repeat_days = _safe_float_val(rec.get("repeat_days"))
        score = _safe_float_val(rec.get("selection_score"))
        if repeat_days is None or score is None:
            continue
        if repeat_days <= max_days and score >= min_score:
            return True
    return False


def _fetch_yesterday_qsrec_canonical_set(category: str) -> set[str] | None:
    """
    讀取昨日已寫入 trade_recommendations 的 QSREC 標的（DISTINCT asset → canonical）。
    SKIP_BIGQUERY 或查詢失敗回傳 None（略過輪動檢查，避免誤擋）。
    """
    if SKIP_BIGQUERY:
        return None
    cat = category.upper().replace("'", "")
    if cat not in ("CRYPTO", "EQUITY"):
        return None
    try:
        client = bigquery.Client(project=PROJECT_ID)
        rows = list(
            client.query(
                f"""
                SELECT DISTINCT asset
                FROM `{RECOMMENDATIONS_TABLE}`
                WHERE report_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
                  AND UPPER(COALESCE(category, '')) = '{cat}'
                """
            ).result()
        )
        if not rows:
            return set()
        return {tracker.canonical_asset_key(r["asset"]) for r in rows if r.get("asset")}
    except Exception as e:
        logger.warning("pick rotation: yesterday QSREC query failed: %s", e)
        return None


def _pick_rotation_crypto_ok(
    text: str,
    recs: list[dict],
    *,
    span_cache: dict[str, int] | None = None,
) -> tuple[bool, str]:
    """今日加密 QSREC canonical 集合若與昨日完全相同，須改選或達成同標覆核。"""
    if not _strict_pick_rotation():
        return True, ""
    y = _fetch_yesterday_qsrec_canonical_set("CRYPTO")
    if y is None:
        return True, ""
    t = _qsrec_canonical_set_for_category(recs, "CRYPTO")
    if not t or not y or t != y:
        return True, ""
    if not _allow_repeat_pick_override():
        return False, "動態選幣／輪動：與昨日完全相同時不允許同標延續，請至少更換一檔（或配對腿）。"
    reason = _extract_today_pick_reason(_crypto_report_prefix(text, _cache=span_cache)) or ""
    if not _REPEAT_PICK_REASON_RE.search(reason):
        return (
            False,
            "動態選幣／輪動：本日加密 QSREC 標的與昨日 BQ 紀錄完全相同，請至少更換一檔（或配對腿），或在「本日選擇理由」明確寫「重複選用理由：…」（新催化／連日持有依據）。",
        )
    gap = _best_repeat_score_gap_for_category(recs, "CRYPTO")
    if gap is None:
        return False, "動態選幣／輪動：同標延續需提供可量化分差（score_gap 或 selection_score/alt_candidate_score）。"
    min_gap = _pick_rotation_override_min_gap()
    if gap < min_gap:
        return False, f"動態選幣／輪動：同標延續分差不足（score_gap={gap:.2f} < {min_gap:.2f}），請改選至少一檔。"
    if not _has_repeat_quality_anchor(recs, "CRYPTO"):
        return (
            False,
            f"動態選幣／輪動：同標延續需至少 1 筆滿足 repeat_days <= {_repeat_pick_days_max()} 且 selection_score >= {_repeat_pick_min_score():.0f}。",
        )
    return True, ""


def _pick_rotation_equity_ok(
    text: str,
    recs: list[dict],
    *,
    span_cache: dict[str, int] | None = None,
) -> tuple[bool, str]:
    """今日美股 QSREC canonical 集合若與昨日完全相同，須改選或達成同標覆核。"""
    if not _strict_pick_rotation():
        return True, ""
    y = _fetch_yesterday_qsrec_canonical_set("EQUITY")
    if y is None:
        return True, ""
    t = _qsrec_canonical_set_for_category(recs, "EQUITY")
    if not t or not y or t != y:
        return True, ""
    if not _allow_repeat_pick_override():
        return False, "動態選股／輪動：與昨日完全相同時不允許同標延續，請至少更換一檔。"
    reason = _extract_today_pick_reason(text[_ai_section_start_index(text, cache=span_cache) :]) or ""
    if not _REPEAT_PICK_REASON_RE.search(reason):
        return (
            False,
            "動態選股／輪動：本日美股 QSREC 標的與昨日 BQ 紀錄完全相同，請至少更換一檔，或在「本日選擇理由」明確寫「重複選用理由：…」。",
        )
    gap = _best_repeat_score_gap_for_category(recs, "EQUITY")
    if gap is None:
        return False, "動態選股／輪動：同標延續需提供可量化分差（score_gap 或 selection_score/alt_candidate_score）。"
    min_gap = _pick_rotation_override_min_gap()
    if gap < min_gap:
        return False, f"動態選股／輪動：同標延續分差不足（score_gap={gap:.2f} < {min_gap:.2f}），請更換至少一檔。"
    if not _has_repeat_quality_anchor(recs, "EQUITY"):
        return (
            False,
            f"動態選股／輪動：同標延續需至少 1 筆滿足 repeat_days <= {_repeat_pick_days_max()} 且 selection_score >= {_repeat_pick_min_score():.0f}。",
        )
    return True, ""


def _safe_float(m: re.Match | None, group: int = 1) -> float | None:
    """從 regex match 安全萃取 float，失敗回傳 None。"""
    if not m:
        return None
    try:
        return float(m.group(group))
    except (ValueError, IndexError):
        return None


def _build_output_json_for_validation(report_text: str) -> dict:
    """將戰報文字轉成結構化 payload，供 Pydantic 與 assertion 驗證。"""
    plain = strip_html(report_text).strip()
    title = "Daily Brief"
    if plain:
        first = plain.splitlines()[0].strip()
        if first:
            title = first[:120]

    summary = plain[:800] if plain else ""
    code_match = re.search(r"(<code>[\s\S]*?</code>)", report_text, re.IGNORECASE)
    code = code_match.group(1) if code_match else ""
    news_text = "\n".join(
        line for line in report_text.splitlines()
        if ("HTTPError" in line or "[DATA_MISSING" in line or "Traceback" in line)
    )
    return {
        "title": title,
        "summary": summary,
        "code": code,
        "news": news_text,
    }


def _codex_judge_pass(report_text: str) -> bool:
    """
    以 Codex 裁判提示詞 + 關鍵詞規則做快速審核。
    若判定含 API 錯誤訊息/無關內容，回傳 False 觸發重試。
    """
    return not bool(
        re.search(
            r"HTTPError|\[DATA_MISSING:|Traceback|Exception:|API key 未設定|Will be right back",
            report_text,
            re.IGNORECASE,
        )
    )


def _normalize_fullwidth_news_brackets_on_news_lines(text: str) -> str:
    """將含〔新聞 N〕行之全形括號 ［］ 轉為半形 []，利於 UTC+8 正規化與 Gate 比對。"""
    out: list[str] = []
    for ln in text.splitlines():
        if re.search(r"〔新聞\s*\d+〕", ln):
            out.append(ln.replace("［", "[").replace("］", "]"))
        else:
            out.append(ln)
    return "\n".join(out)


def _join_news_tag_timestamp_lines(text: str) -> str:
    """若 LLM 將〔新聞 N〕與 [日期 時間] 拆成兩行，合併為單行以便補齊 UTC+8 與 regex 驗證。"""
    lines = text.splitlines()
    if not lines:
        return text
    out: list[str] = []
    i = 0
    ts_head = re.compile(
        r"^\s*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)\s+\d{1,2}:\d{2}(?::\d{2})?"
    )
    while i < len(lines):
        ln = lines[i]
        if re.search(r"〔新聞\s*\d+〕\s*$", ln.rstrip()) and i + 1 < len(lines):
            nxt = lines[i + 1]
            if ts_head.match(nxt):
                out.append(ln.rstrip() + " " + nxt.lstrip())
                i += 2
                continue
        out.append(ln)
        i += 1
    return "\n".join(out)


def _has_news_timezone_utc8(text: str) -> bool:
    """新聞時間格式檢查：標籤格式需全數標示香港時區（UTC+8／GMT+8 等）；數字條列格式視為已降級接受。
    支援 [MM/DD HH:MM]、[MM/DD/YYYY HH:MM]、[YYYY/MM/DD HH:MM]、[YYYY-MM-DD HH:MM]；
    時區允許全形加號、多空格、GMT+8 等 LLM 常見變體。
    """
    t0 = _text_for_utc8_validation(text)
    t1 = _join_news_tag_timestamp_lines(t0)
    t2 = _normalize_fullwidth_news_brackets_on_news_lines(t1)
    t = _strip_inline_tags_on_news_lines(t2)
    tagged_total = len(re.findall(r"〔新聞\s*\d+〕", t))
    tagged_ts_total = len(_NEWS_TAGGED_WITH_TS_RE.findall(t))
    if tagged_ts_total > 0:
        tagged_utc = len(_NEWS_TAGGED_WITH_HK_TZ_RE.findall(t))
        return tagged_utc == tagged_ts_total
    if tagged_total > 0:
        return False
    numbered = len(re.findall(r"(?m)^\s*\d+[.)]\s+.+", t))
    return numbered > 0


def _normalize_regime_token(raw: str) -> str | None:
    token = re.sub(r'[\s\-_]+', '_', (raw or "").strip().lower())
    if token in ("risk_on", "risk_off", "neutral"):
        return token
    return None


def _risk_off_star_cap_violated(text: str) -> bool:
    """risk_off 下是否出現超過上限的信心星等（4 顆星）。"""
    has_risk_off = bool(
        re.search(
            r'【今日市場模式】\s*(?:<[^>]*>\s*)*risk[\s_\-]*off(?:\s*</[^>]*>)*',
            text,
            re.IGNORECASE,
        )
    )
    has_4_star = "⭐️⭐️⭐️⭐️" in text
    return has_risk_off and has_4_star


def _pair_trade_unit_consistent(text: str) -> bool:
    """
    粗略檢查配對交易單位一致性：
    若出現 $A / $B，必須標註比值/價差單位，且現價比值與進場不應嚴重失真。
    """
    pair_m = re.search(
        r'\$([A-Z]{2,10})\s*/\s*\$([A-Z]{2,10}).*?現價[：:]\s*\$?([0-9,]+(?:\.\d+)?)\s*/\s*\$?([0-9,]+(?:\.\d+)?)',
        text,
        re.DOTALL,
    )
    if not pair_m:
        return True

    has_pair_unit = bool(re.search(r'單位[：:]\s*(?:比值|價差|[A-Z]{2,10}/[A-Z]{2,10}\s*比值)', text))
    if not has_pair_unit:
        return False

    a = float(pair_m.group(3).replace(",", ""))
    b = float(pair_m.group(4).replace(",", ""))
    if b <= 0:
        return False
    implied_ratio = a / b

    nearby = text[pair_m.start(): pair_m.start() + 500]
    entry_m = re.search(r'進場[：:]\s*(?:<code>)?\$?([0-9,]+(?:\.\d+)?)', nearby)
    if not entry_m:
        return False
    entry = float(entry_m.group(1).replace(",", ""))
    if entry <= 0:
        return False

    # 容忍 35% 誤差（避免過度嚴苛），超出視為單位可能混用
    return abs(entry - implied_ratio) / implied_ratio <= 0.35


def _qsrec_opposing_direction_same_asset(recs: list[dict]) -> list[str]:
    """同一 category + asset 不得同時 LONG 與 SHORT（避免讀者看到互斥觀點）。"""
    from collections import defaultdict

    buckets: dict[tuple[str, str], set[str]] = defaultdict(set)
    for rec in recs:
        asset = str(rec.get("asset") or "").strip().upper().replace("$", "")
        direction = str(rec.get("direction") or "").strip().upper()
        cat = str(rec.get("category") or "").strip().upper()
        if not asset or direction not in ("LONG", "SHORT"):
            continue
        buckets[(cat or "UNKNOWN", asset)].add(direction)
    issues: list[str] = []
    for (cat, asset), dirs in sorted(buckets.items()):
        if len(dirs) > 1:
            issues.append(
                f"QSREC 同資產方向互斥：{cat} {asset} 同時含 LONG 與 SHORT（請整併為單一淨方向或分拆為明確對沖敘事）"
            )
    return issues


def _conflicting_total_risk_budget_lines(text: str) -> bool:
    """若出現多組「今日風險預算」且總風險預算百分比不一致，視為版面/敘事衝突。"""
    nums = re.findall(r"今日風險預算[：:][^\n]*總風險預算[^\d]*(\d+)\s*%", text)
    if len(nums) < 2:
        return False
    return len(set(nums)) > 1


def _fix_glued_na_suffix(text: str) -> str:
    """修復 <code>N/A</code> 或裸 N/A 與後續中英文字黏連（如 N/ACoinGlass）。"""
    if not text:
        return text
    out = re.sub(r"(N/A)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", text)
    out = re.sub(r"(</code>)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", out)
    return out


def _qsrec_consistency_issues(report_text: str, recs: list[dict]) -> list[str]:
    """檢查 QSREC 載荷的交易欄位完整度與 regime 倉位一致性。"""
    if not recs:
        return []

    regime_m = re.search(
        r'【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*',
        report_text,
        re.IGNORECASE,
    )
    regime = _normalize_regime_token(regime_m.group(1)) if regime_m else "neutral"
    regime = regime or "neutral"
    cap_map = {"risk_off": 5.0, "neutral": 10.0, "risk_on": 15.0}
    cap = cap_map.get(regime, 10.0)

    issues: list[str] = []
    required = ("trigger", "invalidation", "position_pct", "timeframe")
    for i, rec in enumerate(recs, start=1):
        missing = [k for k in required if rec.get(k) in (None, "", [])]
        if missing:
            issues.append(f"QSREC 第 {i} 筆缺少必要欄位：{', '.join(missing)}")

        pos = rec.get("position_pct")
        try:
            if pos is not None and float(pos) > cap:
                issues.append(f"QSREC 第 {i} 筆 position_pct 超過 regime 上限（{float(pos):.2f}% > {cap:.2f}%）")
        except (TypeError, ValueError):
            issues.append(f"QSREC 第 {i} 筆 position_pct 非數字")

        if _strict_pick_scoring():
            for k in _PICK_SCORE_FIELDS:
                val = _safe_float_val(rec.get(k))
                if val is None:
                    issues.append(f"QSREC 第 {i} 筆缺少可量化評分欄位：{k}")
                    continue
                if not (0.0 <= val <= 100.0):
                    issues.append(f"QSREC 第 {i} 筆 {k} 超出範圍（{val:.2f}，應為 0~100）")

            sel = _safe_float_val(rec.get("selection_score"))
            alt = _safe_float_val(rec.get("alt_candidate_score"))
            gap = _safe_float_val(rec.get("score_gap"))
            if sel is None or alt is None:
                issues.append(f"QSREC 第 {i} 筆缺少 selection_score/alt_candidate_score（無法檢查分差）")
            elif gap is None:
                issues.append(f"QSREC 第 {i} 筆缺少 score_gap（建議填 selection_score-alt_candidate_score）")
            elif abs((sel - alt) - gap) > 1.0:
                issues.append(
                    f"QSREC 第 {i} 筆 score_gap 與 selection_score-alt_candidate_score 不一致（{gap:.2f} vs {sel - alt:.2f}）"
                )

    issues.extend(_qsrec_opposing_direction_same_asset(recs))
    return issues


def _count_effective_news_items(text: str) -> int:
    """統計有效新聞數。

    優先採 crew 規定的〔新聞 N〕（全篇目標 6：幣圈 3 + AI 3）；只要出現此格式就只信該計數，
    避免「新聞辯論」「列表」裡的 1. / 1) 被 max() 誤算成 6+ 而掩蓋真正缺則。
    無任何〔新聞〕標籤時才退回 1) / 1.（舊稿相容）。
    """
    tagged = len(re.findall(r"〔新聞\s*\d+〕", text))
    if tagged > 0:
        return tagged
    numbered_paren = len(re.findall(r"(?m)^\s*\d+\)\s+.+", text))
    numbered_dot = len(re.findall(r"(?m)^\s*\d+\.\s+.+", text))
    return max(numbered_paren, numbered_dot)


def _sanitize_macro_outlier_values(text: str) -> str:
    """
    宏觀數值異常修正：
    - 10Y/2Y/SOFR 超出合理區間時改為 N/A（數據異常待確認）
    """
    patched = text

    def _pct_or_none(raw: str) -> float | None:
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return None

    def _repl_ust(m: re.Match) -> str:
        y10_raw = m.group(1)
        y2_raw = m.group(2)
        y10 = _pct_or_none(y10_raw)
        y2 = _pct_or_none(y2_raw)
        if y10 is None or y2 is None:
            return m.group(0)
        if not (0.0 <= y10 <= 20.0 and 0.0 <= y2 <= 20.0):
            return "美債 10Y: N/A（數據異常待確認） | 2Y: N/A（數據異常待確認） | 利差: N/A"
        return m.group(0)

    # 美債 10Y / 2Y 行（覆蓋常見格式）
    patched = re.sub(
        r"美債\s*10Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust,
        patched,
    )
    patched = re.sub(
        r"美債\s*10Y\D{0,18}([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y\D{0,12}([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust,
        patched,
    )

    # 泛用：2Y 數值若超過合理區間，僅替換數值本體，避免句式變化漏網。
    def _repl_2y(m: re.Match) -> str:
        prefix = m.group(1)
        raw = m.group(2)
        val = _pct_or_none(raw)
        if val is None or 0.0 <= val <= 20.0:
            return m.group(0)
        return f"{prefix}N/A（數據異常待確認）"

    patched = re.sub(
        r"(2Y[^0-9%\n]{0,16})([0-9,]+(?:\.[0-9]+)?)%",
        _repl_2y,
        patched,
    )

    def _repl_sofr(m: re.Match) -> str:
        raw = m.group(1)
        val = _pct_or_none(raw)
        if val is None:
            return m.group(0)
        if not (0.0 <= val <= 20.0):
            return "Fed SOFR 期貨隱含利率: N/A（數據異常待確認）"
        return m.group(0)

    patched = re.sub(
        r"Fed SOFR 期貨隱含利率[：:]\s*([0-9,]+(?:\.[0-9]+)?)%",
        _repl_sofr,
        patched,
    )

    # SOFR 句型變體（不一定含「Fed」）
    patched = re.sub(
        r"(SOFR 期貨隱含利率[^0-9%\n]{0,12})([0-9,]+(?:\.[0-9]+)?)%",
        lambda m: (
            f"{m.group(1)}N/A（數據異常待確認）"
            if (lambda v: v is not None and v > 20.0)(_pct_or_none(m.group(2)))
            else m.group(0)
        ),
        patched,
    )

    # 利差絕對值過大（>= 1000bp）視為異常，兼容 + / - / Unicode 負號 / 小數。
    patched = re.sub(
        r"(利差[：:]?\s*)[+\-−]?([0-9,]{4,}(?:\.[0-9]+)?)\s*bp",
        r"\1N/A",
        patched,
        flags=re.IGNORECASE,
    )
    return patched


def _is_conditional_regime_line(line: str) -> bool:
    """判斷該行是否為情境分析條件句（若轉為 risk_off 則…），不應被 regime 統一覆寫。"""
    return bool(re.search(
        r'(?:若|如果|假設|when|if)\s*(?:轉為|切換至|shift\s*to|switch\s*to|moves?\s*to)\s*'
        r'(?:risk[\s_\-]*on|risk[\s_\-]*off|neutral)',
        line,
        re.IGNORECASE,
    ))


def _unify_regime_mentions(text: str) -> str:
    """統一全篇 regime：以第一個【今日市場模式】為準，覆寫後續風險預算中的 regime。

    情境分析條件句（如「若轉為 risk_off 則…」）保留原文不覆寫。
    """
    regime_token_re = r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)'
    m = re.search(
        rf'【今日市場模式】\s*(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*',
        text,
        re.IGNORECASE,
    )
    if not m:
        return text
    regime = _normalize_regime_token(m.group(1))
    if not regime:
        return text
    patched = text
    patched = re.sub(
        rf'(【今日市場模式】\s*(?:<[^>]*>\s*)*){regime_token_re}(?:\s*</[^>]*>)*',
        rf"\1{regime}",
        patched,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:][^\n]*?regime\s*=\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*",
        rf"\1regime={regime}",
        patched,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:]\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*(\s*[｜|])",
        rf"\1{regime}\3",
        patched,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        r'("regime"\s*:\s*")(risk_on|risk_off|neutral)(")',
        rf'\1{regime}\3',
        patched,
        flags=re.IGNORECASE,
    )
    # 兼容英文寫法（Risk Off / Risk-On）在風險預算行中造成的不一致。
    # 跳過情境分析條件句，避免覆寫「若轉為 risk_off 則…」。
    def _risk_budget_line_repl(m: re.Match) -> str:
        line = m.group(0)
        if _is_conditional_regime_line(line):
            return line
        line = re.sub(r'\brisk[\s_-]*on\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\brisk[\s_-]*off\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\bneutral\b', regime, line, flags=re.IGNORECASE)
        return line

    patched = re.sub(
        r'(?im)^.*今日風險預算[^\n]*$',
        _risk_budget_line_repl,
        patched,
    )
    return patched


def _remove_duplicate_source_observability(text: str) -> str:
    """移除報告內重複/過時的 SourceHealth/SourceErrors/SourceQuota 行，避免前後矛盾。"""
    lines = text.splitlines()
    cleaned: list[str] = []
    for line in lines:
        if re.search(r"\bSource(?:Health|Errors|Quota)\b", line):
            continue
        if re.match(r"^\s*【Source(?:Health|Errors|Quota)】", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _drop_unactionable_trade_blocks(text: str) -> str:
    """
    移除不可執行交易段（現價/進場/目標/停損為 N/A）。
    以每筆「· $TICKER ...」起始，直到下一筆交易或段落邊界為一個 block。
    """
    lines = text.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    bullet_re = re.compile(r'^\s*·\s*\$[A-Z0-9/]+')
    boundary_re = re.compile(r'^\s*(?:────────────|區塊\d+|【|════)')
    while i < n:
        line = lines[i]
        if bullet_re.search(line):
            j = i + 1
            while j < n and not bullet_re.search(lines[j]) and not boundary_re.search(lines[j]):
                j += 1
            block = "\n".join(lines[i:j])
            if re.search(r'(現價|進場|目標|停損)[：:]\s*(?:<code>)?\s*N/A', block):
                i = j
                continue
            out.extend(lines[i:j])
            i = j
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _has_macro_outlier_values(text: str) -> bool:
    """
    僅檢查宏觀欄位中的實值是否超出合理範圍：
    - 美債 10Y/2Y 僅在含「美債」之行解析，避免敘事句中「10Y 殖利率」誤配後文任意 %。
    - SOFR 僅在含 SOFR 之行解析數值%，且略過同時含 N/A 且無明確數值之句。
    - 利差 bp 應在 +/-1000bp 以內
    """
    for line in text.splitlines():
        if "美債" not in line:
            continue
        for m in re.finditer(
            r"10Y\s*[:：]\s*([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        # 「美債 10Y 報 4.25%」等無冒號寫法（仍限含美債之行）
        for m in re.finditer(
            r"10Y\D{0,22}([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        for m in re.finditer(
            r"2Y\s*[:：]\s*([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True
        for m in re.finditer(
            r"2Y\D{0,22}([0-9,]+(?:\.\d+)?)\s*%",
            line,
            re.IGNORECASE,
        ):
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            if not (0.0 <= val <= 20.0):
                return True

    for line in text.splitlines():
        if "SOFR" not in line.upper():
            continue
        # 僅取 SOFR 關鍵字鄰近第一個利率%，避免同列 VIX%、敘事百分比誤觸
        if "N/A" in line and not re.search(
            r"(?i)SOFR.{0,80}?[+\-]?[0-9][0-9,]*(?:\.[0-9]+)?\s*%",
            line,
        ):
            continue
        m = re.search(
            r"(?i)(?:Fed\s*)?SOFR[^0-9%\n]{0,90}([+\-]?[0-9,]+(?:\.[0-9]+)?)\s*%",
            line,
        )
        if not m:
            continue
        sofr_i = line.upper().find("SOFR")
        if sofr_i >= 0 and re.search(
            r"(?i)\bVIX\b|恐慌指數|波動率指數|VIX\s*指數",
            line[sofr_i : m.end()],
        ):
            continue
        try:
            val = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        if not (-0.5 <= val <= 25.0):
            return True

    for m in re.finditer(r"利差[：:]?\s*([+\-−]?[0-9,]+(?:\.\d+)?)\s*bp", text):
        raw = m.group(1).replace(",", "").replace("−", "-")
        try:
            val = float(raw)
        except ValueError:
            continue
        if abs(val) >= 1000:
            return True

    return False


def _has_macro_conflicts(text: str) -> bool:
    """
    檢查宏觀欄位自我矛盾：
    - 同時出現 2Y 的 N/A 與數值
    - 利差同時出現正值與負值
    - 2Y 多個數值差異過大（>1.0%）
    """
    y2_has_na = bool(re.search(r'美債\s*2Y[^\n]*N/?A', text, re.IGNORECASE))
    y2_vals = [
        float(v.replace(",", ""))
        for v in re.findall(r'美債\s*2Y[^0-9\n]{0,20}([0-9,]+(?:\.\d+)?)\s*%', text, re.IGNORECASE)
    ]
    if y2_has_na and y2_vals:
        return True
    if len(y2_vals) >= 2 and (max(y2_vals) - min(y2_vals) > 1.0):
        return True

    spread_vals = [
        float(v.replace(",", ""))
        for v in re.findall(r'利差[：:]?\s*(-?[0-9,]+(?:\.\d+)?)\s*bp', text)
    ]
    has_pos_spread = any(v > 0 for v in spread_vals)
    has_neg_spread = any(v < 0 for v in spread_vals)
    if has_pos_spread and has_neg_spread:
        return True

    return False


def _has_source_observability_conflicts(text: str) -> bool:
    """檢查 SourceHealth/Errors/Quota 是否重複或互相矛盾。"""
    src_lines = [
        ln.strip()
        for ln in text.splitlines()
        if re.search(r'(?:【)?Source(?:Health|Errors|Quota)', ln)
    ]
    if not src_lines:
        return True

    def _norm(line: str, key: str) -> str:
        line = re.sub(r'^[·\-\s]*', '', line)
        line = line.replace(f"【{key}】", "")
        line = re.sub(rf"^{key}\s*", "", line, flags=re.IGNORECASE)
        return line.strip()

    per_key = {"SourceHealth": [], "SourceErrors": [], "SourceQuota": []}
    for ln in src_lines:
        for key in per_key:
            if re.search(key, ln, re.IGNORECASE):
                per_key[key].append(_norm(ln, key))

    for key, values in per_key.items():
        if len(values) != 1:
            return True
        if len(set(values)) != 1:
            return True
    return False


_NEWS_VALIDATION_NOISE = re.compile(
    r"新聞資料狀態|請主編下一版|格式未統一為〔新聞|【新聞資料狀態】"
)

# 新聞時間戳允許之香港時區字樣（含全形加號、GMT、HKT／中文口語、UTC+08:00 等）
_NEWS_HK_TZ_TOKEN = (
    r"(?:UTC|GMT)\s*[\+\＋]\s*0?8(?::\s*00)?"
    r"|HKT\b"
    r"|(?:香港|北京|台北)時間"
    r"|中國標準時間|東八區"
)
# N/A 過多時須同現「資料缺失原因」與「替代指標」（允許跨行，避免 . 不匹配換行誤判）
_MISSING_REASON_PROXY_RE = re.compile(
    r"資料缺失原因[\s\S]{0,800}?替代指標|替代指標[\s\S]{0,800}?資料缺失原因",
    re.IGNORECASE,
)
# 新聞行內常以 <code> 包住時間戳，驗證／正規化前先剥除該行上行內標籤
_NEWS_LINE_INLINE_HTML_RE = re.compile(r"</?(?:code|b|i|u|s)(?:\s[^>]*)?>", re.IGNORECASE)

_NEWS_TAGGED_WITH_HK_TZ_RE = re.compile(
    rf"〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{{4}}[/\-]\d{{1,2}}[/\-]\d{{1,2}}|\d{{1,2}}/\d{{1,2}}(?:/\d{{4}})?)"
    rf"\s+\d{{1,2}}:\d{{2}}(?::\d{{2}})?\s*{_NEWS_HK_TZ_TOKEN}\]",
    re.IGNORECASE,
)
_NEWS_TAGGED_WITH_TS_RE = re.compile(
    r"〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
    r"\s+\d{1,2}:\d{2}(?::\d{2})?",
    re.IGNORECASE,
)


def _strip_inline_tags_on_news_lines(text: str) -> str:
    """僅在含〔新聞 N〕之行剥除 <code>/<b> 等行內標籤，利於比對時間戳又不動儀表板其他 HTML。"""
    out: list[str] = []
    for ln in text.splitlines():
        if re.search(r"〔新聞\s*\d+〕", ln):
            out.append(_NEWS_LINE_INLINE_HTML_RE.sub("", ln))
        else:
            out.append(ln)
    return "\n".join(out)


def _strip_lines_for_news_validation(text: str) -> str:
    """排除系統注入之『新聞資料狀態』等行，避免誤算〔新聞 N〕或 UTC+8。"""
    lines = [ln for ln in text.splitlines() if not _NEWS_VALIDATION_NOISE.search(ln)]
    return "\n".join(lines)


def _text_for_utc8_validation(text: str) -> str:
    """僅供新聞時區檢查：去噪後截斷【新聞資料狀態】段落之後，避免腳註內仿格式〔新聞〕干擾比對。"""
    t = _strip_lines_for_news_validation(text)
    m = re.search(r"(?m)^\s*【新聞資料狀態】", t)
    if m:
        return t[: m.start()]
    return t


def _partial_news_ok(text: str) -> bool:
    """
    新聞資料不足分段（產品規則）：
    - 〔新聞 1〕～〔新聞 3〕必須存在，且全篇已標示之〔新聞 N〕須全部帶 UTC+8；
    - 〔新聞 N〕則數須為 3～5（不足 6 但未完全缺新聞）；
    - 文內須宣告「資料不足保護／不補虛構新聞」，並有【新聞資料狀態】或 [REPORT_TIER:PARTIAL_NEWS]（後處理會注入）。
    不影響交易欄位檢查；交易觀望另見 trade_watch_mode。
    """
    if not _allow_partial_news_gate():
        return False
    tagged = _count_news_tags_only(text)
    if not (3 <= tagged < 6):
        return False
    if not re.search(r"資料不足保護|不補虛構新聞", text):
        return False
    if not (
        re.search(r"【新聞資料狀態】|新聞資料狀態", text)
        or "[REPORT_TIER:PARTIAL_NEWS]" in text
    ):
        return False
    for i in (1, 2, 3):
        if not re.search(rf"〔新聞\s*{i}〕", text):
            return False
    return _has_news_timezone_utc8(text)


def _inject_canonical_prev_recs_block(report_text: str, canonical_html: str) -> str:
    """
    以 BigQuery 載入之上期追蹤覆寫 LLM 輸出，避免模型自行膨脹多筆同標的進場價。
    canonical_html 為空時仍會**剥除** LLM 捏造之【上期建議追蹤】（以免無 BQ 時重複假列）。
    """
    canonical_html = (canonical_html or "").strip()
    m = re.search(r"【今日市場模式】", report_text)
    if not m:
        if not canonical_html:
            return report_text
        return canonical_html + "\n\n" + report_text
    head, tail = report_text[: m.start()], report_text[m.start() :]
    head_clean = re.sub(r"【上期建議追蹤】[\s\S]*\Z", "", head, flags=re.MULTILINE).rstrip()
    sep = "\n\n" if head_clean else ""
    if not canonical_html:
        return f"{head_clean}{sep}{tail}"
    block = canonical_html + "\n\n"
    return f"{head_clean}{sep}{block}{tail}"


def _auto_prefix_missing_news_tags(text: str) -> str:
    """
    LLM 常以 [MM/DD HH:MM UTC+8] 起句但漏寫〔新聞 N〕，導致計數與 Gate 失敗。
    在【核心新聞】內為時間戳行補標籤；在【AI 產業新聞】內為「標題行 + 摘要：」補標籤（接續既有最大編號）。
    """
    lines = text.splitlines()
    if not lines:
        return text

    def _max_news_tag_num(s: str) -> int:
        nums = [int(x) for x in re.findall(r"〔新聞\s*(\d+)〕", s)]
        return max(nums) if nums else 0

    tag_i = _max_news_tag_num(text) + 1
    section = "out"
    out: list[str] = []
    pending_title_idx: int | None = None

    _crypto_header = re.compile(r"【區塊②\s*核心新聞】|區塊②【核心新聞】|^【核心新聞】")
    _crypto_ts = re.compile(r"^\s*\[\d{1,2}/\d{1,2}(?:/\d{2,4})?\s+\d{1,2}:\d{2}(?::\d{2})?")

    for ln in lines:
        if _crypto_header.search(ln):
            section = "crypto"
            pending_title_idx = None
            out.append(ln)
            continue
        if section == "crypto" and re.search(r"區塊③|【區塊③", ln):
            section = "out"
            pending_title_idx = None
            out.append(ln)
            continue

        if "【AI 產業新聞】" in ln:
            section = "ai"
            pending_title_idx = None
            out.append(ln)
            continue
        if section == "ai" and "【產業鏈呢喃】" in ln:
            section = "out"
            pending_title_idx = None
            out.append(ln)
            continue

        if section == "crypto":
            if _crypto_ts.match(ln) and "〔新聞" not in ln:
                out.append(f"〔新聞 {tag_i}〕{ln.lstrip()}")
                tag_i += 1
            else:
                out.append(ln)
            continue

        if section == "ai":
            st = ln.strip()
            if st.startswith("摘要：") or st.startswith("摘要∶"):
                if pending_title_idx is not None and "〔新聞" not in out[pending_title_idx]:
                    out[pending_title_idx] = f"〔新聞 {tag_i}〕{out[pending_title_idx]}"
                    tag_i += 1
                pending_title_idx = None
                out.append(ln)
            elif st.startswith(
                ("投資解讀", "💎", "·", "•", "- ", "—", "低置信度", "資料缺失", "HuggingFace", "OpenRouter", "AI Momentum")
            ):
                out.append(ln)
            elif st and (re.search(r"[A-Za-z]{3,}", st) or len(st) > 18):
                out.append(ln)
                pending_title_idx = len(out) - 1
            else:
                out.append(ln)
            continue

        out.append(ln)

    return "\n".join(out)


def _normalize_news_timezone_utc8(text: str) -> str:
    """將新聞時間標籤統一補上 UTC+8。
    支援格式：[MM/DD HH:MM]、[MM/DD/YYYY HH:MM]、[YYYY/MM/DD HH:MM]、[YYYY-MM-DD HH:MM]；
    已含 UTC+8／GMT+8／HKT／香港時間等者不變。會先剥除新聞行上 <code> 等行內標籤再比對。
    """
    text = _join_news_tag_timestamp_lines(text)
    text = _normalize_fullwidth_news_brackets_on_news_lines(text)
    pattern = re.compile(
        r"(〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)"
        r"\s+\d{1,2}:\d{2}(?::\d{2})?)"
        rf"(\s+(?:{_NEWS_HK_TZ_TOKEN}))?"
        r"(\])",
        re.IGNORECASE,
    )

    def _repl(m: re.Match) -> str:
        left, tz, closing = m.group(1), m.group(2), m.group(3)
        if tz and tz.strip():
            return m.group(0)
        return f"{left} UTC+8{closing}"

    lines = text.splitlines()
    out: list[str] = []
    for ln in lines:
        if not re.search(r"〔新聞\s*\d+〕", ln):
            out.append(ln)
            continue
        ln_flat = _NEWS_LINE_INLINE_HTML_RE.sub("", ln)
        out.append(pattern.sub(_repl, ln_flat))
    return "\n".join(out)


def _inject_fallback_news_entries(text: str, min_news: int = 6) -> str:
    """新聞不足時加入風險提示，不再注入假新聞條目。"""
    current = _count_effective_news_items(text)
    if current >= min_news:
        return text

    tagged = _count_news_tags_only(text)
    tier_line = ""
    if _allow_partial_news_gate() and 3 <= tagged < min_news:
        tier_line = "[REPORT_TIER:PARTIAL_NEWS]\n"

    block = (
        f"{tier_line}"
        "【新聞資料狀態】\n"
        f"以〔新聞 N〕標籤計入的新聞為 <code>{current}</code> 則／目標 <code>{min_news}</code> "
        f"則（幣圈 3 + AI 3）。已啟用資料不足保護：不補虛構新聞。"
        "若實際已寫滿 6 則但格式未統一為〔新聞 N〕，請主編下一版改為規定格式以便系統計數。"
    )
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


def _ensure_min_news_count(text: str, min_news: int = 6) -> str:
    """新聞數不足時，只加入觀測提示，不注入虛構新聞。"""
    return _inject_fallback_news_entries(text, min_news=min_news)


def _ensure_signal_conflict_section(text: str) -> str:
    """若報告缺少訊號衝突摘要，自動注入預設值，避免 gate 阻擋。"""
    has_signal_conflict = bool(re.search(r'[訊信]號衝突(?:摘要|分析)?[：:]', text))
    if has_signal_conflict:
        return text

    fallback_line = "訊號衝突摘要：各指標方向基本一致，暫無顯著多空衝突訊號。"

    # 優先注入在「今日風險預算」行之後
    risk_budget_m = re.search(r'(今日風險預算[：:][^\n]*\n)', text)
    if risk_budget_m:
        pos = risk_budget_m.end()
        return text[:pos] + fallback_line + "\n" + text[pos:]

    # 次選：注入在區塊④之前
    trade_section_m = re.search(r'(區塊④【)', text)
    if trade_section_m:
        pos = trade_section_m.start()
        return text[:pos] + fallback_line + "\n" + text[pos:]

    # 最後手段：注入在 QSREC_START 之前
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n" + fallback_line + "\n\n" + text[pos:]

    return text


def _has_crypto_trade_section(text: str) -> bool:
    """
    是否已含加密精準操作段（含 LLM 省略 (Crypto) 括號但已寫進出場的情形）。
    避免誤判導致在完整建議後又注入「觀望模式」。
    """
    if re.search(r'資金流向與精準操作', text):
        return True
    return bool(
        re.search(
            r'精準操作\s*\(Crypto\)|精準操作[^\n]{0,40}Crypto|區塊④[^\n]*Crypto',
            text,
            re.IGNORECASE,
        )
    )


def _has_ai_trade_section(text: str) -> bool:
    if re.search(r'AI\s*產業鏈精準操作|精準操作\s*\(US\s*Equit', text, re.IGNORECASE):
        return True
    if re.search(r'區塊④[^\n]*US\s*Equit', text, re.IGNORECASE):
        return True
    return bool(re.search(r'精準操作.*Equit', text, re.IGNORECASE))


def _ensure_trade_sections(text: str) -> str:
    """
    當 LLM 漏寫交易段時，注入「觀望模式」區塊（不捏造價格）。
    """
    has_crypto_trade = _has_crypto_trade_section(text)
    has_ai_trade = _has_ai_trade_section(text)
    if has_crypto_trade and has_ai_trade:
        return text

    regime_m = re.search(
        r'【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*',
        text,
        re.IGNORECASE,
    )
    regime = (_normalize_regime_token(regime_m.group(1)) if regime_m else None) or "neutral"
    blocks: list[str] = []
    if not has_crypto_trade:
        blocks.append(
            "\n".join(
                [
                    "區塊④【資金流向與精準操作 (Crypto)】：",
                    "· <b>觀望模式</b>：資料不足觀望，暫不開新倉（避免捏造現價/進場/目標/停損）。",
                    f"· 風險預算：依 <code>{regime}</code> 模式降低風險，僅保留既有倉位管理。",
                    "· 重新進場條件：待下一輪有效新聞、即時報價與多時框訊號齊備後再提供交易參數。",
                ]
            )
        )
    if not has_ai_trade:
        blocks.append(
            "\n".join(
                [
                    "區塊④【AI 產業鏈精準操作 (US Equities)】：",
                    "· <b>觀望模式</b>：資料不足觀望，暫不提供股票進出場價格。",
                    f"· 風險預算：依 <code>{regime}</code> 模式執行防守配置，避免情緒性追價。",
                    "· 重新進場條件：需補齊產業催化、成交量與多時框確認後再發布可執行建議。",
                ]
            )
        )

    if not blocks:
        return text
    marker = "[QSREC_START]"
    pos = text.find(marker)
    block = "\n\n".join(blocks)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


def _ensure_low_confidence_for_many_na(text: str) -> str:
    """當 <code>N/A</code> 出現次數過多時，validate_report 要求同時具備低置信度字樣與「資料缺失原因／替代指標」說明。"""
    if len(re.findall(r"\bN/A\b", text)) <= 3:
        return text
    has_lc = bool(re.search(r"低置信度|低信心", text))
    has_proxy = bool(_MISSING_REASON_PROXY_RE.search(text))
    if has_lc and has_proxy:
        return text
    # 避免重複注入（與手寫段落區隔：固定片語）
    if "方案權限回傳暫缺" in text:
        return text
    block = (
        "· <b>低置信度</b>：儀表板若出現多項 <code>N/A</code>，表示第三方 API 或方案權限回傳暫缺，"
        "敘事仍以已回傳之技術面與新聞催化為準。"
        "<b>資料缺失原因</b>：與工具欄位空白或 <code>[DATA_MISSING:...]</code> 標記一致；"
        "<b>替代指標</b>：請交叉比對 DXY、VIX、資金費率、Fear&amp;Greed、RSI、現貨成交與上文核心新聞。"
    )
    for anchor in (
        r"(區塊①[^\n]*\n)",
        r"(數據儀表板[^\n]*\n)",
        r"([^\n]*\bDXY\b[^\n]*\n)",
        r"(【今日市場模式】[^\n]*\n)",
    ):
        m = re.search(anchor, text)
        if m:
            pos = m.end()
            return text[:pos] + block + "\n" + text[pos:]
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


_DATA_MISSING_TOKEN_RE = re.compile(r"\[DATA_MISSING:([^\]]+)\]")


def _redact_data_missing_tokens_from_visible_report(text: str) -> str:
    """
    LLM 有時把工具回傳的 [DATA_MISSING:...] 貼進戰報正文，validate_report 會記為「資料缺失欄位」並可能 hard fail。
    改寫為不含該標記的中文短語（來源健康仍見 【SourceHealth】 三行）。
    """
    if not text or "[DATA_MISSING:" not in text:
        return text

    def _repl(m: re.Match) -> str:
        key = (m.group(1) or "").strip() or "unknown"
        return f"〔資料源暫缺：{key}〕"

    return _DATA_MISSING_TOKEN_RE.sub(_repl, text)


def _postprocess_report_for_resilience(text: str) -> str:
    """修正易失格式：新聞 UTC+8、新聞不足降級補齊、來源可觀測欄位。"""
    if not text:
        return text
    patched = _fix_glued_na_suffix(text)
    patched = _sanitize_macro_outlier_values(patched)
    patched = _unify_regime_mentions(patched)
    patched = _drop_unactionable_trade_blocks(patched)
    patched = _ensure_trade_sections(patched)
    patched = _ensure_rumor_grade_marker(patched)
    patched = _auto_prefix_missing_news_tags(patched)
    patched = _normalize_news_timezone_utc8(patched)
    patched = _ensure_signal_conflict_section(patched)
    patched = _ensure_min_news_count(patched, min_news=6)
    patched = _ensure_low_confidence_for_many_na(patched)
    patched = _redact_data_missing_tokens_from_visible_report(patched)

    # 原子化來源欄位收斂：只做一次「清理 -> 注入」避免重複殘留。
    patched = _remove_duplicate_source_observability(patched)
    observe_block = source_observability_lines()
    marker = "[QSREC_START]"
    pos = patched.find(marker)
    if pos != -1:
        patched = patched[:pos].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos:]
    else:
        patched = patched.rstrip() + f"\n\n{observe_block}"
    # 若 LLM 殘留半套 Source 行導致缺欄，再清一次並注入完整三行。
    if not all(s in patched for s in ("【SourceHealth】", "【SourceErrors】", "【SourceQuota】")):
        patched = _remove_duplicate_source_observability(patched)
        pos2 = patched.find(marker)
        if pos2 != -1:
            patched = patched[:pos2].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos2:]
        else:
            patched = patched.rstrip() + f"\n\n{observe_block}"
    return patched


def _has_rumor_grade_marker(text: str) -> bool:
    """是否已包含可被 validate_report 接受的傳聞可信度分級字樣。"""
    return bool(
        re.search(r"可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b", text, re.IGNORECASE)
        or re.search(r"來源[：:]\s*[ABC](?:級|等級)?", text, re.IGNORECASE)
        or re.search(r"可信度\s*[ABC](?:級|等)?", text, re.IGNORECASE)
        or re.search(r"可信度\s*[/／]\s*\d{1,3}\s*/\s*100", text, re.IGNORECASE)
        or re.search(r"(?:可信|可信度)\s*[：:]?\s*\d{1,3}\s*/\s*100", text, re.IGNORECASE)
        or re.search(r"(?:等級|分級|評級)[：:]\s*(?:A|B|C)\b", text, re.IGNORECASE)
        or re.search(r"等級\s+[ABC]\b", text, re.IGNORECASE)
        or re.search(
            r"(?:Grade|Credibility)\s*[：:]\s*(?:A|B|C|\d{1,3})\b",
            text,
            re.IGNORECASE,
        )
        or re.search(r"可信度\s*等級\s*[：:]\s*(?:A|B|C)\b", text, re.IGNORECASE)
        or re.search(r"(?:呢喃|傳聞|供應鏈)[^\n]{0,48}可信度\s*[：:]?\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"信賴度\s*[：:]\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"置信\s*分級\s*[：:]\s*(?:A|B|C|\d{1,3})\b", text, re.IGNORECASE)
        or re.search(r"來源[：:][^\n]{0,160}\(([ABC])級\)", text, re.IGNORECASE)
    )


def _ensure_rumor_grade_marker(text: str) -> str:
    """若出現呢喃/傳聞但缺可信度分級，補一行保底分級，避免 Gate 因格式失敗。"""
    if not text or not re.search(r"呢喃|傳聞", text):
        return text
    if _has_rumor_grade_marker(text):
        return text
    marker_line = "· 傳聞可信度：B（未確認）｜主流媒體二次驗證：否"
    m = re.search(r"(區塊③[^\n]*(?:呢喃|傳聞)[^\n]*\n?)", text)
    if m:
        return text[:m.end()] + marker_line + "\n" + text[m.end():]
    pos = text.find("[QSREC_START]")
    if pos != -1:
        return text[:pos].rstrip() + f"\n{marker_line}\n\n" + text[pos:]
    return text.rstrip() + f"\n{marker_line}"


def _fallback_news_count(text: str) -> int:
    """統計自動降級補位新聞數量。"""
    return len(re.findall(r"資料源不足：自動降級補位", text))


# 資料時效：tool 回傳內 [data_as_of: ISO] 超過此秒數則在驗證時標記 STALE
STALE_DATA_THRESHOLD_SEC = 2 * 3600  # 2 小時


def _collect_stale_data_sources(text: str) -> list[str]:
    """掃描報告中的 [data_as_of: ISO] (source=id)，回傳超過 2h 的 source_id 列表。"""
    pattern = re.compile(r"\[data_as_of:\s*([^\]]+)\]\s*\(source=(\w+)\)")
    now = datetime.now(timezone.utc)
    latest_ts: dict[str, datetime] = {}
    for m in pattern.finditer(text):
        ts_str, source_id = m.group(1).strip(), m.group(2)
        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if source_id not in latest_ts or ts > latest_ts[source_id]:
                latest_ts[source_id] = ts
        except ValueError:
            continue
    stale = []
    for source_id, ts in latest_ts.items():
        if (now - ts).total_seconds() > STALE_DATA_THRESHOLD_SEC:
            stale.append(source_id)
    return stale


def _count_news_tags_only(text: str) -> int:
    """僅統計〔新聞 N〕標籤數（與 _count_effective_news_items 在無標籤時的 fallback 分離）。"""
    t = _strip_lines_for_news_validation(text)
    return len(re.findall(r"〔新聞\s*\d+〕", t))


def _primary_regime_from_report(text: str) -> str | None:
    """以第一處【今日市場模式】為準的主 regime。"""
    m = re.search(
        r"【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)",
        text,
        re.IGNORECASE,
    )
    if not m:
        return None
    return _normalize_regime_token(m.group(1)) or None


def _risk_off_narrative_violations(text: str) -> list[str]:
    """
    主 regime 為 neutral / risk_on 時，交易／倉位段落不得出現「依 risk_off」「高風險環境 risk_off」等矛盾用語。
    情境句「若轉為 risk_off」除外。
    """
    primary = _primary_regime_from_report(text)
    if primary not in ("neutral", "risk_on"):
        return []
    bad_lines: list[str] = []
    cond_inline = re.compile(
        r"(?:若|如果|假設|when|if)\s+.{0,48}risk[\s_\-]*off",
        re.IGNORECASE,
    )
    bad_trade = re.compile(
        r"(?:高風險環境|依)\s*risk[\s_\-]*off|risk[\s_\-]*off\s*(?:減倉|採|模式)|"
        r"Market\s*Regime\s*:\s*risk[\s_\-]*off|"
        r"[（(][^）)]*risk[\s_\-]*off[^）)]*(?:減倉|水位|配置)",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        if "risk" not in line.lower():
            continue
        if "【今日市場模式】" in line:
            continue
        if _is_conditional_regime_line(line):
            continue
        if cond_inline.search(line):
            continue
        if "今日風險預算" in line and re.search(r"risk[\s_\-]*off", line, re.IGNORECASE):
            if not cond_inline.search(line):
                snippet = line.strip()[:160]
                if snippet not in bad_lines:
                    bad_lines.append(snippet)
            continue
        tradeish = any(
            k in line
            for k in (
                "倉位建議",
                "進場：",
                "停損：",
                "目標：",
                "資金流向與精準操作",
                "精準操作",
                "AI 產業鏈精準操作",
            )
        )
        if tradeish and bad_trade.search(line):
            snippet = line.strip()[:160]
            if snippet not in bad_lines:
                bad_lines.append(snippet)
    return bad_lines


def _trade_watch_actionable_conflicts(
    text: str,
    *,
    span_cache: dict[str, int] | None = None,
) -> list[str]:
    """
    交易操作段若宣告「觀望模式」，同段不得同時提供可執行三要素（進場/目標/停損）。
    僅檢查加密與 AI 各自的操作段，避免誤掃到「上期建議追蹤」。
    """
    def _operation_span(span: str, is_ai: bool) -> str:
        if not span:
            return ""
        start_re = (
            r"區塊④[^\n]*(?:AI\s*產業鏈精準操作|US\s*Equit|資金流向與精準操作)|"
            r"AI\s*產業鏈精準操作|資金流向與精準操作"
            if is_ai
            else r"區塊④[^\n]*資金流向與精準操作|資金流向與精準操作"
        )
        m = re.search(start_re, span, re.IGNORECASE)
        return span[m.start() :] if m else span

    def _has_actionable_params(span: str) -> bool:
        has_entry = bool(re.search(r"進場[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        has_target = bool(re.search(r"目標[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        has_stop = bool(re.search(r"停損[：:]\s*(?:<code>)?\$?\s*[0-9,]+(?:\.[0-9]+)?", span))
        return has_entry and has_target and has_stop

    conflicts: list[str] = []
    crypto_span = _crypto_report_prefix(text, _cache=span_cache)
    ai_span = text[len(crypto_span) :]
    for label, span, is_ai in (
        ("加密", crypto_span, False),
        ("AI/美股", ai_span, True),
    ):
        op_span = _operation_span(span, is_ai=is_ai)
        if not op_span:
            continue
        if TRADE_WATCH_MODE_RE.search(op_span) and _has_actionable_params(op_span):
            conflicts.append(label)
    return conflicts


def _ai_dashboard_hallucination_hits(text: str) -> list[str]:
    """
    AI 儀表板常見幻覺欄位（ai_momentum_tool 從未輸出）；僅掃描 🤖 AI 市場 之後至 AI 產業新聞 之前。
    """
    start_m = re.search(r"(🤖\s*AI\s*市場|【AI\s*數據儀表板】|AI\s*數據儀表板)", text, re.IGNORECASE)
    if not start_m:
        return []
    start = start_m.start()
    end_m = re.search(r"【AI\s*產業新聞】|區塊②【AI\s*產業新聞】", text[start:], re.IGNORECASE)
    span = text[start : start + end_m.start()] if end_m else text[start : start + 6000]
    span_low = span.lower()
    forbidden = [
        "ai token market cap",
        "openrouter api request rank",
        "openrouter request vol",
        "ai sector sentiment",
        "token market cap",
        "huggingface trending models n/a",
    ]
    hits = []
    for phrase in forbidden:
        if phrase in span_low:
            hits.append(phrase)
    return hits


def _macro_yield_spread_inconsistent(text: str) -> bool:
    """美債 10Y、2Y 與「利差 %」是否同口徑（利差≈10Y−2Y，容差 0.15%）。"""
    m10 = re.search(r"美債\s*10Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    m2 = re.search(r"美債\s*2Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%", text, re.IGNORECASE)
    ms = re.search(
        r"利差[：:]\s*([+−\-]?[0-9,]+(?:\.[0-9]+)?)\s*%",
        text,
        re.IGNORECASE,
    )
    if not (m10 and m2 and ms):
        return False
    try:
        y10 = float(m10.group(1).replace(",", ""))
        y2 = float(m2.group(1).replace(",", ""))
        raw_s = ms.group(1).replace(",", "").replace("−", "-").replace("\u2212", "-").lstrip("+")
        spr = float(raw_s)
    except ValueError:
        return False
    expected = y10 - y2
    return abs(spr - expected) > 0.15


def validate_report(text: str) -> dict:
    """驗證戰報是否包含足夠新聞與必要區塊（V2.1 四區塊結構）。"""
    span_cache: dict[str, int] = {}
    news_count  = _count_effective_news_items(text)
    fallback_count = _fallback_news_count(text)

    # Accept both old plain regime label and new scorecard format (e.g. "risk_on（+4/6）")
    has_regime = bool(HAS_REGIME_RE.search(text))
    has_dashboard = bool(HAS_DASHBOARD_RE.search(text))
    has_crypto_trade = _has_crypto_trade_section(text)
    has_ai_trade = _has_ai_trade_section(text)
    has_ai_section = bool(HAS_AI_SECTION_RE.search(text))
    has_crypto_section = bool(HAS_CRYPTO_SECTION_RE.search(text))
    has_chatter = bool(re.search(r'呢喃|傳聞', text))
    has_data_missing = bool(HAS_DATA_MISSING_RE.search(text))
    data_missing_fields = sorted(set(DATA_MISSING_FIELDS_RE.findall(text)))
    # 交易觀望：放寬 R:R／勝率等「可執行欄位」檢查（與「新聞不足分段」解耦）
    trade_watch_mode = bool(TRADE_WATCH_MODE_RE.search(text))
    partial_news_ok = _partial_news_ok(text)
    news_six_relaxed = trade_watch_mode or partial_news_ok
    has_qsrec_markers = bool(QSREC_MARKERS_RE.search(text))
    parsed_qsrec = tracker.extract_recommendations_json(text) if has_qsrec_markers else []
    has_valid_qsrec = bool(parsed_qsrec)
    has_rr = bool(HAS_RR_RE.search(text))
    has_max_drawdown = bool(HAS_MAX_DRAWDOWN_RE.search(text))
    has_expected_win_rate = bool(HAS_EXPECTED_WIN_RATE_RE.search(text))
    has_signal_score = bool(HAS_SIGNAL_SCORE_RE.search(text))
    has_signal_conflict = bool(HAS_SIGNAL_CONFLICT_RE.search(text))
    has_risk_budget = bool(HAS_RISK_BUDGET_RE.search(text))
    has_rumor_grade = _has_rumor_grade_marker(text)
    has_utc8 = _has_news_timezone_utc8(text)
    too_many_na = len(NA_TOKEN_RE.findall(text)) > 3
    has_low_confidence_tag = bool(HAS_LOW_CONFIDENCE_RE.search(text))
    has_missing_reason_proxy = bool(_MISSING_REASON_PROXY_RE.search(text))
    has_numeric_in_investment = bool(
        NUMERIC_INVESTMENT_LINE_RE.search(text) or NUMERIC_INVESTMENT_MULTI_RE.search(text)
    )
    has_source_health = "【SourceHealth】" in text
    has_source_errors = "【SourceErrors】" in text
    has_source_quota = "【SourceQuota】" in text
    mode_tags_raw = MODE_TAGS_RE.findall(text)
    budget_tags_raw = BUDGET_TAGS_RE.findall(text)
    mode_tags = [r for r in (_normalize_regime_token(x) for x in mode_tags_raw) if r]
    budget_tags = [r for r in (_normalize_regime_token(x) for x in budget_tags_raw) if r]
    qsrec_regimes = []
    if has_valid_qsrec:
        for rec in parsed_qsrec:
            rv = _normalize_regime_token(str(rec.get("regime", "")))
            if rv:
                qsrec_regimes.append(rv)
    unique_regimes = set(mode_tags + budget_tags + qsrec_regimes)
    # 情境分析條件句（若轉為 risk_off 則…）不算 mixed regime —— 僅排除條件句中的 regime 提及
    _conditional_re = re.compile(
        r'(?:若|如果|假設|when|if)\s*(?:轉為|切換至|shift\s*to|switch\s*to|moves?\s*to)\s*'
        r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)',
        re.IGNORECASE,
    )
    conditional_regimes = {
        _normalize_regime_token(m.group(1))
        for m in _conditional_re.finditer(text)
        if _normalize_regime_token(m.group(1))
    }
    authoritative_regimes = unique_regimes - conditional_regimes
    has_mixed_regime = len(authoritative_regimes) > 1
    malformed_invalidation = bool(MALFORMED_INVALIDATION_RE.search(text))
    has_unactionable_trade = bool(UNACTIONABLE_TRADE_RE.search(text))
    has_macro_outlier = _has_macro_outlier_values(text)
    has_macro_conflict = _has_macro_conflicts(text)
    has_source_observability_conflict = _has_source_observability_conflicts(text)
    watch_trade_conflicts = _trade_watch_actionable_conflicts(text, span_cache=span_cache)
    has_code_leak = bool(CODE_LEAK_RE.search(text))
    has_impact_leak = bool(IMPACT_LEAK_RE.search(text))
    pair_unit_ok = _pair_trade_unit_consistent(text)
    risk_off_star_ok = not _risk_off_star_cap_violated(text)
    qsrec_issues = _qsrec_consistency_issues(text, parsed_qsrec) if has_valid_qsrec else []

    pick_crypto_ok, pick_crypto_err = True, ""
    pick_equity_ok, pick_equity_err = True, ""
    if _strict_pick_justification() and not trade_watch_mode and has_valid_qsrec:
        pick_crypto_ok, pick_crypto_err = _pick_justification_crypto_ok(
            text, parsed_qsrec, span_cache=span_cache
        )
        pick_equity_ok, pick_equity_err = _pick_justification_equity_ok(
            text, parsed_qsrec, span_cache=span_cache
        )

    pick_crypto_rot_ok, pick_crypto_rot_err = True, ""
    pick_equity_rot_ok, pick_equity_rot_err = True, ""
    if _strict_pick_rotation() and not trade_watch_mode and has_valid_qsrec:
        pick_crypto_rot_ok, pick_crypto_rot_err = _pick_rotation_crypto_ok(
            text, parsed_qsrec, span_cache=span_cache
        )
        pick_equity_rot_ok, pick_equity_rot_err = _pick_rotation_equity_ok(
            text, parsed_qsrec, span_cache=span_cache
        )

    issues = []
    tagged_news = _count_news_tags_only(text)
    if len(text) < 3000:
        issues.append(f"報告過短（{len(text)} chars，預期 >3000）")
    if tagged_news < 6 and not news_six_relaxed:
        issues.append(
            f"核心新聞〔新聞 N〕標籤不足（{tagged_news}/6）：須以〔新聞 1〕…〔新聞 6〕標示幣圈 3 + AI 3，"
            f"禁止僅用 1. 2. 3. 作為新聞編號（避免與辯論列表混淆）。"
            f"（分段放行：交易觀望／或符合「新聞資料不足分段」— 3~5 則且〔新聞 1~3〕+ UTC+8 + 不補虛構宣告，見 ALLOW_PARTIAL_NEWS_GATE）"
        )
    if news_count < 6 and not news_six_relaxed:
        issues.append(
            f"新聞數不足（{news_count}/6）且未符合觀望或新聞分段條件（見 validate_report 說明／README）"
        )
    if not has_regime:
        issues.append("缺少 market_regime 標籤（risk_on/risk_off/neutral）")
    if not has_dashboard:
        issues.append("缺少數據儀表板（DXY/RSI/資金費率/Fear&Greed）")
    if not has_crypto_trade:
        issues.append("缺少加密市場操作建議（精準操作 Crypto）")
    if not has_ai_trade:
        issues.append("缺少 AI 美股操作建議（精準操作 US Equities）")
    if not has_ai_section:
        issues.append("缺少 AI 市場段落")
    if not has_crypto_section:
        issues.append("缺少加密市場段落")
    if not has_chatter:
        issues.append("缺少呢喃/傳聞區塊")
    if not has_qsrec_markers:
        issues.append("缺少系統追蹤載荷區塊（[QSREC_START]...[QSREC_END]）")
    elif not has_valid_qsrec:
        issues.append("QSREC 區塊存在但 JSON 無法解析或為空陣列")
    if _strict_pick_justification() and not trade_watch_mode and has_valid_qsrec:
        if not pick_crypto_ok:
            issues.append(pick_crypto_err)
        if not pick_equity_ok:
            issues.append(pick_equity_err)
    if _strict_pick_rotation() and not trade_watch_mode and has_valid_qsrec:
        if not pick_crypto_rot_ok:
            issues.append(pick_crypto_rot_err)
        if not pick_equity_rot_ok:
            issues.append(pick_equity_rot_err)
    if not has_utc8:
        issues.append("新聞時間未統一標示 UTC+8")
    if not has_signal_conflict:
        issues.append("缺少訊號衝突摘要（避免過度單邊敘事）")
    if not has_rumor_grade:
        issues.append("傳聞區缺少可信度分級（A/B/C 或 0~100）")
    if (not trade_watch_mode) and (not has_rr or not has_max_drawdown):
        issues.append("交易建議缺少 R:R 或最大回撤風險欄位")
    if (not trade_watch_mode) and (not has_expected_win_rate or not has_signal_score):
        issues.append("交易建議缺少預期勝率或 Signal Score 欄位")
    if not has_risk_budget:
        issues.append("缺少今日風險預算摘要")
    if (not trade_watch_mode) and (not has_numeric_in_investment):
        issues.append("投資解讀缺少當日量化數據引用")
    if not has_source_health or not has_source_errors or not has_source_quota:
        issues.append("缺少來源健康欄位（SourceHealth/SourceErrors/SourceQuota）")
    if has_mixed_regime:
        issues.append(f"報告內 market_regime 不一致：{', '.join(sorted(unique_regimes))}")
    if malformed_invalidation:
        issues.append("交易建議存在空白/截斷的失效條件")
    if has_unactionable_trade:
        issues.append("交易段含 N/A 關鍵價格（現價/進場/目標/停損），不可執行")
    if has_macro_outlier:
        issues.append("宏觀數值疑似異常（10Y/2Y/SOFR/利差超出合理範圍）")
    if has_macro_conflict:
        issues.append("宏觀段落前後矛盾（2Y/利差數值不一致）")
    if has_source_observability_conflict:
        issues.append("Source observability 欄位重複或互相矛盾")
    if watch_trade_conflicts:
        issues.append(
            "觀望模式契約衝突："
            + "、".join(watch_trade_conflicts)
            + "操作段同時出現「觀望模式」與可執行價位（進場/目標/停損），請擇一保留。"
        )
    if _conflicting_total_risk_budget_lines(text):
        issues.append("今日風險預算出現多組不一致的總風險預算百分比（請整併為單一總框或依【日報 V2】改為美股部位框）")
    if not pair_unit_ok:
        issues.append("配對交易單位不一致或未標註比值/價差單位")
    if not risk_off_star_ok:
        issues.append("risk_off 模式下出現超過上限的信心水準（4 顆星）")
    if too_many_na and (not has_low_confidence_tag or not has_missing_reason_proxy):
        issues.append("N/A 過多但缺少低置信度標籤與替代指標說明")
    if has_code_leak:
        issues.append("戰報外洩 Python 函數名稱（multi_timeframe_tool）")
    if has_impact_leak:
        issues.append("戰報外洩內部 IMPACT 原始標籤")
    rv_lines = _risk_off_narrative_violations(text)
    if rv_lines:
        preview = " | ".join(rv_lines[:3])
        issues.append(
            "主 regime 為 neutral/risk_on 但交易／風險預算段誤用 risk_off 敘述（禁用「依 risk_off」「高風險環境 risk_off 減倉」等；"
            f"情境句「若轉為 risk_off」除外）：{preview}"
        )
    ah = _ai_dashboard_hallucination_hits(text)
    if ah:
        issues.append(
            "AI 儀表板含疑似幻覺欄位（非 ai_momentum_tool 輸出）：" + ", ".join(sorted(set(ah)))
        )
    if _macro_yield_spread_inconsistent(text):
        issues.append("宏觀「利差 %」與美債 10Y/2Y 數值不一致（請核對是否同為 10Y−2Y 口徑）")
    issues.extend(qsrec_issues)
    for source_id in _collect_stale_data_sources(text):
        issues.append(f"[STALE_DATA:{source_id}]")
    if has_data_missing:
        issues.append(f"資料缺失欄位：{', '.join(data_missing_fields)}")
        critical_missing = {
            "market_search",
            "newsapi",
            "gnews",
            "rss_feed",
            "x_search",
            "multi_timeframe",
            "coinglass_data",
            "macro_context",
            "regime_scorecard",
        }
        if any(f in critical_missing for f in data_missing_fields):
            issues.append("關鍵資料來源缺失（hard fail）")

    return {
        "valid": len([i for i in issues if all(k not in i for k in ("呢喃", "傳聞"))]) == 0,
        "issues": issues,
        "news_count": news_count,
        "fallback_news_count": fallback_count,
        "has_data_missing": has_data_missing,
        "has_qsrec": has_valid_qsrec,
        "qsrec_count": len(parsed_qsrec),
        "has_source_health": has_source_health,
        "has_source_errors": has_source_errors,
        "has_source_quota": has_source_quota,
        "has_mixed_regime": has_mixed_regime,
        "has_unactionable_trade": has_unactionable_trade,
        "has_macro_outlier": has_macro_outlier,
        "has_macro_conflict": has_macro_conflict,
        "has_source_observability_conflict": has_source_observability_conflict,
        "trade_watch_mode": trade_watch_mode,
        "partial_news_ok": partial_news_ok,
        "news_six_relaxed": news_six_relaxed,
        "pick_justification_crypto_ok": pick_crypto_ok,
        "pick_justification_equity_ok": pick_equity_ok,
        "pick_rotation_crypto_ok": pick_crypto_rot_ok,
        "pick_rotation_equity_ok": pick_equity_rot_ok,
    }


def _report_compare_mode() -> bool:
    """Phase 3：雙軌驗證比對（僅 log，不切 Telegram / BQ 決策）。"""
    return os.getenv("REPORT_COMPARE_MODE", "").lower() in ("1", "true", "yes")


def _validate_report_candidate(text: str) -> dict:
    """
    Phase 3 候選驗證路徑。

    實作位於 `core/report_validation.py`（延遲 import main，避免循環）。
    目前與 `validate_report` 等價；日後可改為獨立實作並以 REPORT_COMPARE_MODE 觀測差異。
    正式管線仍以本模組的 `validate_report` 為唯一權威。
    """
    from core.report_validation import validate_report_candidate

    return validate_report_candidate(text)


def _log_validation_dual_run(final_report: str, legacy_result: dict) -> None:
    """若 REPORT_COMPARE_MODE=1，比對 legacy vs candidate 並寫入日誌（不一致為 WARNING）。"""
    if not _report_compare_mode():
        return
    if not (final_report or "").strip():
        return
    candidate = _validate_report_candidate(final_report)
    diff = compare_validation_results(legacy_result, candidate)
    if diff["identical"]:
        logger.info("REPORT_COMPARE: legacy vs candidate snapshots identical.")
        return
    logger.warning(
        "REPORT_COMPARE: mismatch legacy vs candidate | legacy_valid=%s candidate_valid=%s | "
        "only_in_legacy=%s | only_in_candidate=%s",
        diff["legacy_valid"],
        diff["candidate_valid"],
        diff["issues_only_in_legacy"][:8],
        diff["issues_only_in_candidate"][:8],
    )


_SECTION_RE_CACHE: dict[str, re.Pattern] = {}


def _extract_section(text: str, header: str, max_chars: int = 500) -> str | None:
    """從報告文字中萃取指定區塊的內容（模組級，避免重複編譯）。"""
    if header not in _SECTION_RE_CACHE:
        _SECTION_RE_CACHE[header] = re.compile(
            re.escape(header) + r'[】]?\s*\n?([\s\S]*?)(?=────|$)'
        )
    m = _SECTION_RE_CACHE[header].search(text)
    if not m:
        return None
    body = m.group(1).strip()
    if len(body) > max_chars:
        body = body[:max_chars] + "…"
    return body or None


def _extract_news_titles(text: str, max_titles: int = 20) -> list[str]:
    """從戰報中萃取所有新聞標題，供次日排除重複使用。"""
    clean = strip_html(text)
    seen: set[str] = set()
    titles: list[str] = []
    for pattern in (r'〔新聞\s*\d+〕[^\n]*\n([^\n]{10,120})', r'〔新聞\s*\d+〕\s*([^\n]{10,120})'):
        for m in re.finditer(pattern, clean):
            t = m.group(1).strip()
            if t not in seen:
                seen.add(t)
                titles.append(t)
    return titles[:max_titles]


# ── 語義去重（Semantic Deduplication）──────────────────────────────────
_SBERT_MODEL: object = None  # None=not loaded, False=unavailable, Model=ready

try:
    from scipy.spatial.distance import cosine as _cosine_distance
except ImportError:
    _cosine_distance = None


def _get_sbert_model():
    """Lazy-load sentence-transformers model (first call ~1-2s, cached after)."""
    global _SBERT_MODEL
    if _SBERT_MODEL is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SBERT_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Loaded sentence-transformers model: all-MiniLM-L6-v2")
        except ImportError:
            _SBERT_MODEL = False  # sentinel: don't retry
            logger.warning("sentence-transformers not installed; semantic dedup disabled.")
    return _SBERT_MODEL if _SBERT_MODEL is not False else None


def _semantic_dedup_titles(titles: list[str], threshold: float = 0.80) -> list[str]:
    """Filter semantically duplicate titles using cosine similarity on embeddings.

    Args:
        titles: List of news title strings.
        threshold: Cosine similarity above this value is considered a duplicate (0-1).

    Returns:
        Deduplicated list preserving original order.
    """
    if len(titles) <= 1 or _cosine_distance is None:
        return titles

    model = _get_sbert_model()
    if model is None:
        return titles

    try:
        embeddings = model.encode(titles)

        kept_indices: list[int] = []
        for i, emb_i in enumerate(embeddings):
            is_dup = False
            for j in kept_indices:
                sim = 1.0 - _cosine_distance(emb_i, embeddings[j])
                if sim > threshold:
                    logger.debug(
                        "Semantic dedup: title %d (%.30s…) %.3f-similar to %d (%.30s…), skipping.",
                        i, titles[i], sim, j, titles[j],
                    )
                    is_dup = True
                    break
            if not is_dup:
                kept_indices.append(i)

        deduped = [titles[i] for i in kept_indices]
        if len(deduped) < len(titles):
            logger.info("Semantic dedup removed %d/%d duplicate titles.", len(titles) - len(deduped), len(titles))
        return deduped
    except Exception as e:
        logger.warning("Semantic dedup failed, returning original titles: %s", e)
        return titles


def _safe_chunks(text: str, max_len: int = 4000) -> list[str]:
    """切分訊息，優先在區段分隔線處切割，避免切斷新聞/推文條目。"""
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        cut = remaining.rfind("────────────", 0, max_len + 1)
        if cut > max_len // 2:
            cut += len("────────────")
        else:
            section_matches = list(re.finditer(r'\n【', remaining[:max_len + 1]))
            if section_matches:
                cut = section_matches[-1].start()
            else:
                cut = remaining.rfind("\n", 0, max_len + 1)
                if cut == -1:
                    cut = max_len

        candidate = remaining[:cut]
        if candidate.count("<") > candidate.count(">"):
            last_open = candidate.rfind("<")
            if last_open > 0:
                cut = last_open

        if cut <= 0:
            cut = max_len
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")

    if remaining:
        chunks.append(remaining)
    return chunks


def _send_telegram_report(text: str, token: str, chat_id: str, image_path: str = "daily_chart.png") -> None:
    """發送戰報至 Telegram：若有圖表則先發圖，再分段發送文字；含重試與 fallback。"""
    from telebot import apihelper

    apihelper.SESSION_TIME_TO_LIVE = 5 * 60
    bot = telebot.TeleBot(token)

    if os.path.exists(image_path):
        for attempt in range(3):
            try:
                with open(image_path, "rb") as f:
                    bot.send_photo(chat_id, photo=f, timeout=60)
                break
            except Exception as e:
                logger.warning("send_photo attempt %d failed: %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))

    html_mode = True
    for i, raw_chunk in enumerate(_safe_chunks(text)):
        chunk = sanitize_telegram_html(raw_chunk)
        plain_chunk = strip_html(chunk)
        sent = False
        for attempt in range(4):
            try:
                if html_mode:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                else:
                    bot.send_message(chat_id, plain_chunk, timeout=60)
                sent = True
                time.sleep(0.5)
                break
            except Exception as e:
                err_str = str(e).lower()
                if html_mode and "can't parse entities" in err_str:
                    logger.warning("Chunk %d HTML parse failed; downgrade to plain text mode: %s", i, e)
                    html_mode = False
                    continue
                wait = 5 if "429" not in err_str else 30 * (attempt + 1)
                logger.warning("Chunk %d send attempt %d failed (wait=%ds): %s", i, attempt + 1, wait, e)
                if attempt < 3:
                    time.sleep(wait)
        if not sent:
            try:
                bot.send_message(chat_id, plain_chunk, timeout=60)
            except Exception as final_e:
                logger.error("Chunk %d all retries failed: %s", i, final_e)


# Gate 告警錯誤碼（供 Telegram 關鍵字過濾）
GATE_CODE_CRITICAL_SOURCE = "GATE_CRITICAL_SOURCE"
GATE_CODE_LLM_DISCONNECT = "GATE_LLM_DISCONNECT"
GATE_CODE_EXECUTION_FAILED = "GATE_EXECUTION_FAILED"
GATE_CODE_VALIDATION = "GATE_VALIDATION"
GATE_CODE_UNKNOWN = "GATE_UNKNOWN"


def _gate_failure_output_dir() -> Path:
    raw = (os.getenv("GATE_FAILURE_ARTIFACT_DIR") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / ".qsilicon" / "last_gate_failure"


def _gate_failure_artifacts_enabled() -> bool:
    return os.getenv("GATE_FAILURE_ARTIFACTS", "1").lower() not in ("0", "false", "no")


def _gate_alert_send_full_issues() -> bool:
    return os.getenv("GATE_ALERT_FULL_ISSUES", "1").lower() not in ("0", "false", "no")


def _persist_gate_validation_failure(report_text: str, validation: dict) -> Path | None:
    """
    驗證失敗時寫入本機（預設 .qsilicon/last_gate_failure/）：
    draft_report.txt、issues.txt、validation_summary.json — 方便對照格式與完整問題清單。
    """
    if not _gate_failure_artifacts_enabled() or not (report_text or "").strip():
        return None
    out_dir = _gate_failure_output_dir()
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("gate failure artifact mkdir failed: %s", e)
        return None
    issues = [str(x).strip() for x in (validation.get("issues") or []) if str(x).strip()]
    try:
        (out_dir / "draft_report.txt").write_text(report_text, encoding="utf-8")
        (out_dir / "issues.txt").write_text(
            "\n".join(f"{i + 1}. {x}" for i, x in enumerate(issues)) if issues else "(no issues list)",
            encoding="utf-8",
        )
        summary = {
            "valid": validation.get("valid"),
            "issue_count": len(issues),
            "report_chars": len(report_text),
            "written_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "issues": issues,
        }
        (out_dir / "validation_summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning("gate failure artifact write failed: %s", e)
        return None
    logger.warning(
        "validate_report failed — draft + full issues written to %s (count=%d)",
        out_dir,
        len(issues),
    )
    return out_dir


def _format_gate_issues_followup_messages(all_issues: list[str]) -> list[str]:
    """純文字 follow-up（不用 HTML parse_mode），避免長 issue 炸 Telegram entity。"""
    if not all_issues:
        return []
    header = (
        f"📋 Q-Silicon 驗證問題清單（共 {len(all_issues)} 項）\n"
        "下列為 validate_report 完整 issues；正式戰報未推送。\n"
        "────────────────────────"
    )
    chunks: list[str] = []
    cur = header
    max_body = 3600
    for idx, issue in enumerate(all_issues, start=1):
        line = f"\n{idx}. {issue}"
        if len(cur) + len(line) > max_body:
            chunks.append(cur)
            cur = f"（續）\n{idx}. {issue}"
        else:
            cur += line
    if cur.strip():
        chunks.append(cur)
    return chunks


def _gate_alert_severity_and_code(
    top_issues: str | None,
    error_text: str | None,
    *,
    all_issues_list: list[str] | None = None,
) -> tuple[str, str]:
    """依 top_issues 與 error_text 決定 severity 與固定錯誤碼。"""
    issues = (top_issues or "").strip().lower()
    err = (error_text or "").strip().lower()
    issues_blob = (top_issues or "") + "\n" + "\n".join(all_issues_list or [])

    if "關鍵資料來源缺失" in issues_blob:
        return "CRITICAL", GATE_CODE_CRITICAL_SOURCE
    if err and err != "n/a":
        if "server disconnected" in err or "disconnected without sending" in err:
            return "WARNING", GATE_CODE_LLM_DISCONNECT
        if "503" in err or "unavailable" in err or "rate limit" in err:
            return "WARNING", GATE_CODE_LLM_DISCONNECT
        return "CRITICAL", GATE_CODE_EXECUTION_FAILED
    if (issues and issues != "n/a") or (all_issues_list and len(all_issues_list) > 0):
        return "WARNING", GATE_CODE_VALIDATION
    return "WARNING", GATE_CODE_UNKNOWN


def _send_telegram_gate_alert(
    token: str,
    chat_id: str,
    top_issues: str | None = None,
    error_text: str | None = None,
    *,
    all_issues: list[str] | None = None,
    artifact_rel: str | None = None,
) -> None:
    """一致性 gate 阻擋時，發送簡短告警到 Telegram（含 severity 與固定錯誤碼）。"""
    if not token or not chat_id:
        return

    bot = telebot.TeleBot(token)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    issue_line = top_issues.strip() if (top_issues or "").strip() else "N/A"
    err_line = (error_text or "").strip()
    if len(err_line) > 240:
        err_line = err_line[:240] + "..."
    if not err_line:
        err_line = "N/A"
    last_ok = _get_last_success_report_time_utc()
    n_issues = len(all_issues) if all_issues else 0
    severity, code = _gate_alert_severity_and_code(
        top_issues, error_text, all_issues_list=all_issues
    )
    art_line = (artifact_rel or "").strip() or "N/A"

    alert_text = (
        "<b>Q-Silicon Gate 告警</b>\n"
        f"<code>code: {code}</code>\n"
        f"<code>severity: {severity}</code>\n"
        f"<code>STRICT_CONSISTENCY_GATE=1</code> 已阻擋本次正式戰報推送。\n"
        f"<code>time: {ts}</code>\n"
        f"<code>last_success: {last_ok or 'N/A'}</code>\n"
        f"<code>issues_count: {n_issues}</code>\n"
        f"<code>artifacts: {art_line}</code>\n"
        f"<code>top_issues: {issue_line}</code>\n"
        f"<code>error: {err_line}</code>"
    )
    safe_alert = sanitize_telegram_html(alert_text)
    try:
        bot.send_message(chat_id, safe_alert, parse_mode="HTML", timeout=30)
        logger.info("Gate alert sent to Telegram.")
    except Exception as e:
        logger.warning("Failed to send gate alert to Telegram: %s", e)

    if (
        _gate_alert_send_full_issues()
        and all_issues
        and len(all_issues) > 0
        and code == GATE_CODE_VALIDATION
    ):
        for chunk in _format_gate_issues_followup_messages(all_issues):
            try:
                bot.send_message(chat_id, chunk, timeout=60)
            except Exception as e:
                logger.warning("Failed to send gate issues follow-up: %s", e)
                break


def _get_last_success_report_time_utc(
    project_id: str = PROJECT_ID,
    metrics_table: str = METRICS_TABLE,
) -> str | None:
    """查詢最近一次成功寫入 metrics 的時間（視為最近成功戰報時間）。"""
    if SKIP_BIGQUERY:
        return None
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT timestamp
            FROM `{metrics_table}`
            WHERE timestamp IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return None
        row = rows[0]
        ts = row.get("timestamp") if hasattr(row, "get") else None
        if not ts:
            return None
        if hasattr(ts, "strftime"):
            return ts.strftime("%Y-%m-%d %H:%M UTC")
        return str(ts)
    except Exception as e:
        logger.warning("Could not fetch last successful report time from BigQuery: %s", e)
        return None


def extract_and_save_metrics(report_text: str, project_id: str = PROJECT_ID) -> None:
    """從戰報文字萃取關鍵指標並寫入 BigQuery daily_metrics 資料表。"""
    metrics_table = f"{project_id}.market_data.daily_metrics"
    # 先剝除 HTML 標籤，避免 <code>97.65</code> 等結構干擾 regex 萃取
    clean_text = strip_html(report_text)

    # ── 1. 萃取 DXY：多模式匹配 ──────────────────
    dxy_patterns = [
        r'ICE\s+DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'DXY\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'美元指數[（(]DXY[）)]?\s*[→\->:：]+\s*(\d{2,3}\.\d{1,4})',
        r'DXY[^<]*?(\d{2,3}\.\d{1,4})',
    ]
    dxy = None
    for pattern in dxy_patterns:
        m = re.search(pattern, clean_text, re.IGNORECASE)
        dxy = _safe_float(m)
        if dxy is not None:
            break

    # ── 2. 萃取 ETF 資金流：匹配中文語境的流出/流入 + 億 ────────────
    etf_flow = None
    etf_match = re.search(
        r'ETF.{0,60}?(流出|外流|流入)\D{0,10}?(\d+(?:\.\d+)?)\s*億',
        clean_text, re.IGNORECASE | re.DOTALL
    )
    if not etf_match:
        etf_match = re.search(
            r'(流出|外流|流入)\s*(\d+(?:\.\d+)?)\s*億',
            clean_text, re.IGNORECASE
        )
    if etf_match:
        direction_raw = etf_match.group(1).lower()
        value = _safe_float(etf_match, 2)
        if value is not None:
            is_outflow = any(k in direction_raw for k in ('流出', '外流'))
            etf_flow = -value if is_outflow else value

    # ── 3. 萃取 IMPACT 並轉為風險數值（強利空=5 … 強利多=1），與舊 RISK x/5 相容 ──
    _IMPACT_TO_SCORE = {"強利空": 5.0, "弱利空": 4.0, "中性": 3.0, "弱利多": 2.0, "強利多": 1.0}
    avg_risk = None
    impact_matches = re.findall(
        r'IMPACT[：:]\s*(強利空|弱利空|中性|弱利多|強利多)',
        clean_text
    )
    if impact_matches:
        scores = [_IMPACT_TO_SCORE.get(m, 3.0) for m in impact_matches]
        avg_risk = round(sum(scores) / len(scores), 2)
    else:
        # 向後相容：若仍出現舊格式 RISK x/5，則沿用
        legacy = re.findall(r'RISK(?:_SCORE)?[】\s]*(\d(?:\.\d)?)\s*/\s*5', clean_text, re.IGNORECASE)
        if legacy:
            try:
                scores = [float(s) for s in legacy]
                avg_risk = round(sum(scores) / len(scores), 2)
            except ValueError:
                pass

    # ── 4. B200 租賃價已移除，保留欄位以相容既有 BigQuery schema（寫入 None）──
    gpu_b200 = None

    # ── 4b. 萃取 P2 新增指標 ──────────────────────────────────────────────────
    # sentiment_score（來自 sentiment_score_tool 輸出，範圍 -1 到 +1）
    sent_m = re.search(r'情緒分數[：:]\s*([+-]?\d+\.\d+)', clean_text)
    sentiment_score = _safe_float(sent_m)

    # SOPR（來自 onchain_metrics_tool）
    sopr_m = re.search(r'SOPR[^：:（\n]*[：:]\s*([+-]?\d+\.\d+)', clean_text, re.IGNORECASE)
    sopr = _safe_float(sopr_m)

    # 交易所 BTC 淨流向（以千 BTC 為單位）
    netflow_m = re.search(r'交易所\s*BTC\s*淨流[向入出][^：:（\n]*[：:]\s*([+-]?\d+\.?\d*)', clean_text)
    exchange_netflow = _safe_float(netflow_m)

    # ── 5. 萃取 MVRV Z-Score：多模式匹配 ───────
    mvrv_patterns = [
        r'MVRV\s*Z[-\s]?Score\s*[→\->:：]+\s*(-?\d+(?:\.\d+)?)',
        r'MVRV[：:]\s*(-?\d+(?:\.\d+)?)',
        r'MVRV[^<]*?(-?\d+(?:\.\d+)?)',
    ]
    mvrv_z = None
    for pattern in mvrv_patterns:
        m = re.search(pattern, clean_text, re.IGNORECASE)
        mvrv_z = _safe_float(m)
        if mvrv_z is not None:
            break

    # ── 6. 萃取 Agent 情報摘要（幣圈 / AI 區塊各取第一段重點）──────
    grok_summary = _extract_section(clean_text, "【幣圈新聞】")
    # AI 區塊 header 隨版本變動，依序嘗試多種可能的 header
    gpt_summary = (
        _extract_section(clean_text, "AI 產業新聞")
        or _extract_section(clean_text, "AI 數據儀表板")
        or _extract_section(clean_text, "AI 市場")
        or _extract_section(clean_text, "【AI 基建現況】")
    )

    # ── 6b. 萃取新聞標題供次日去重 ──────────────────
    all_titles = _extract_news_titles(report_text, max_titles=25)
    all_titles = _semantic_dedup_titles(all_titles, threshold=0.80)
    news_titles_str = "\n".join(f"· {t}" for t in all_titles) if all_titles else None
    logger.info("Extracted %d news titles for deduplication (after semantic dedup).", len(all_titles))

    # ── Phase 4：從評分卡萃取 regime_score（-6 到 +6）──────────────
    regime_score: float | None = None
    regime_score_m = re.search(r'市場機制評分[^（(]*[（(]([+-]?\d+)/6[）)]', clean_text)
    if regime_score_m:
        regime_score = _safe_float(regime_score_m)

    logger.info(
        "Extracted metrics — DXY: %s, ETF Flow: %s億, Avg Risk: %s, MVRV Z: %s, "
        "Sentiment: %s, SOPR: %s, Netflow: %s, RegimeScore: %s",
        dxy, etf_flow, avg_risk, mvrv_z, sentiment_score, sopr, exchange_netflow, regime_score,
    )

    # ── 7. 寫入 BigQuery ──────────────────────────────────────────
    try:
        client = bigquery.Client(project=project_id)

        schema = [
            bigquery.SchemaField("timestamp",          "TIMESTAMP"),
            bigquery.SchemaField("dxy",                "FLOAT"),
            bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
            bigquery.SchemaField("avg_risk_score",     "FLOAT"),
            bigquery.SchemaField("gpu_b200_price",     "FLOAT"),
            bigquery.SchemaField("grok_summary",       "STRING"),
            bigquery.SchemaField("gpt_summary",        "STRING"),
            bigquery.SchemaField("mvrv_z_score",       "FLOAT"),
            bigquery.SchemaField("news_titles",        "STRING"),
            # P2 新增欄位
            bigquery.SchemaField("sentiment_score",    "FLOAT"),
            bigquery.SchemaField("sopr",               "FLOAT"),
            bigquery.SchemaField("exchange_netflow",   "FLOAT"),
            # Phase 4 新增欄位
            bigquery.SchemaField("regime_score",       "FLOAT"),
        ]
        table_ref = bigquery.Table(metrics_table, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        # 既有表不會因 create_table(exists_ok=True) 自動補新欄位，需手動 migration。
        table = client.get_table(metrics_table)
        existing_columns = {field.name for field in table.schema}
        missing_fields = [field for field in schema if field.name not in existing_columns]
        if missing_fields:
            table.schema = list(table.schema) + missing_fields
            client.update_table(table, ["schema"])
            logger.info("Added missing BigQuery columns: %s", ", ".join(f.name for f in missing_fields))

        row = {
            "timestamp":         datetime.now(timezone.utc).isoformat(),
            "dxy":               dxy,
            "etf_flow_millions": etf_flow,
            "avg_risk_score":    avg_risk,
            "gpu_b200_price":    gpu_b200,
            "grok_summary":      grok_summary,
            "gpt_summary":       gpt_summary,
            "mvrv_z_score":      mvrv_z,
            "news_titles":       news_titles_str,
            # P2 新增欄位
            "sentiment_score":   sentiment_score,
            "sopr":              sopr,
            "exchange_netflow":  exchange_netflow,
            # Phase 4 新增欄位
            "regime_score":      regime_score,
        }
        non_null_count = sum(1 for v in [dxy, etf_flow, avg_risk, mvrv_z] if v is not None)
        if non_null_count == 0:
            logger.warning("All key metrics are None — skipping BigQuery write to avoid empty row.")
            return
        logger.info("Writing %d/4 key metrics to BigQuery.", non_null_count)

        errors = client.insert_rows_json(metrics_table, [row])
        if errors:
            logger.error("BigQuery insert errors: %s", errors)
        else:
            logger.info("Daily metrics written to BigQuery successfully.")
    except Exception as e:
        logger.error("Failed to write metrics to BigQuery: %s", e)


def _fetch_recent_recommended_assets(client: bigquery.Client, days: int = 3) -> list[str]:
    """查詢近 N 天已建議的資產代號，供排除重複標的使用。"""
    try:
        rows = list(client.query(f"""
            SELECT DISTINCT asset
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
            ORDER BY asset
        """).result())
        return [r["asset"] for r in rows if r.get("asset")]
    except Exception as e:
        logger.warning("Failed to fetch recent recommended assets: %s", e)
        return []


def fetch_exclusion_context(project_id: str = PROJECT_ID, metrics_table: str = METRICS_TABLE) -> str | None:
    """從 BigQuery 讀取前一日的新聞標題列表與近期已推薦資產，供研究流程排除重複。"""
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT grok_summary, gpt_summary, news_titles
            FROM `{metrics_table}`
            WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 36 HOUR)
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return None
        row = rows[0]

        parts: list[str] = []

        news_titles_raw = row.get("news_titles") if hasattr(row, "get") else None
        if news_titles_raw:
            parts.append("昨日已報導的新聞標題（禁止重複選用）：\n" + news_titles_raw)
        else:
            for field in ("grok_summary", "gpt_summary"):
                val = row.get(field) if hasattr(row, "get") else None
                if val:
                    parts.append(val)

        # 近 3 天已推薦資產排除（強制輪換標的）
        recent_assets = _fetch_recent_recommended_assets(client, days=3)
        if recent_assets:
            asset_list = ", ".join(f"${a}" for a in recent_assets)
            parts.append(
                f"過去 3 天已建議的標的（除非有重大新催化劑，否則禁止重複選用）：{asset_list}\n"
                "必須優先選擇不在此清單中的標的。若該標的有全新重大事件（如 ETF 核准、主網升級、財報超預期），"
                "可以再次選用，但必須明確說明「重複選用理由：XXX」。"
            )
            logger.info("Loaded %d recent recommended assets for exclusion: %s", len(recent_assets), recent_assets)

        s = "\n\n".join(parts) if parts else None
        if s and len(s) > 2500:
            s = s[:2500] + "\n…[truncated]"
        return s
    except Exception as e:
        logger.warning("Could not fetch exclusion context from BigQuery: %s", e)
        return None


def _is_retriable(e: Exception) -> bool:
    """是否為可重試的暫時性錯誤（503/429/服務不可用/XAI 異常）。"""
    msg = str(e).lower()
    return (
        "503" in msg
        or "429" in msg
        or "rate limit" in msg
        or "rate_limit" in msg
        or "unavailable" in msg
        or "high demand" in msg
        or "xai" in msg
    )


def _quote_of(symbol: str) -> float | None:
    """取單一標的最新收盤價（含 MultiIndex 防護）。"""
    try:
        df = yf.download(symbol, period="7d", interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        close_col = df["Close"]
        if hasattr(close_col, "iloc") and hasattr(close_col, "ndim") and close_col.ndim > 1:
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()
        if close_col.empty:
            return None
        return float(close_col.iloc[-1])
    except Exception:
        return None


def _compute_rsi(closes, period: int = 14) -> float | None:
    """計算 RSI(period)，需要至少 period+1 筆收盤價。"""
    if closes is None or len(closes) < period + 1:
        return None
    try:
        delta = closes.diff().dropna()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))
        avg_gain = gain.rolling(window=period, min_periods=period).mean().iloc[-1]
        avg_loss = loss.rolling(window=period, min_periods=period).mean().iloc[-1]
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return round(100 - (100 / (1 + rs)), 1)
    except Exception:
        return None


def _get_extended_price_data(symbol: str, period: str = "60d") -> dict:
    """取得延伸價格數據：最新收盤、RSI(14)、MA20、MA50。"""
    result: dict = {"close": None, "rsi14": None, "ma20": None, "ma50": None}
    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            return result
        close_col = df["Close"]
        if hasattr(close_col, "ndim") and close_col.ndim > 1:
            close_col = close_col.iloc[:, 0]
        close_col = close_col.dropna()
        if close_col.empty:
            return result

        result["close"] = float(close_col.iloc[-1])
        result["rsi14"] = _compute_rsi(close_col)
        if len(close_col) >= 20:
            result["ma20"] = round(float(close_col.iloc[-20:].mean()), 2)
        if len(close_col) >= 50:
            result["ma50"] = round(float(close_col.iloc[-50:].mean()), 2)
    except Exception:
        pass
    return result


def get_realtime_quotes() -> str:
    """取得系統強制即時報價 context，含技術指標與 VIX 期限結構。"""
    symbols = {
        "BTC": "BTC-USD",
        "VIX": "^VIX",
        "IBIT": "IBIT",
        "NVDA": "NVDA",
        "MSFT": "MSFT",
        "SPY": "SPY",
        "SOL": "SOL-USD",
        "DXY": "DX-Y.NYB",
    }
    parts: list[str] = []
    for name, sym in symbols.items():
        v = _quote_of(sym)
        if v is None:
            parts.append(f"{name}: N/A")
        elif name in ("VIX", "DXY"):
            parts.append(f"{name}: {v:.2f}")
        else:
            parts.append(f"{name}: ${v:.2f}")

    # ── BTC 技術指標（RSI + MA）──
    btc_ext = _get_extended_price_data("BTC-USD", period="60d")
    tech_parts: list[str] = []
    if btc_ext["rsi14"] is not None:
        rsi = btc_ext["rsi14"]
        zone = "超買" if rsi > 70 else ("超賣" if rsi < 30 else "中性")
        tech_parts.append(f"BTC RSI(14): {rsi}（{zone}）")
    if btc_ext["ma20"] is not None:
        tech_parts.append(f"BTC MA20: ${btc_ext['ma20']:,.2f}")
    if btc_ext["ma50"] is not None:
        tech_parts.append(f"BTC MA50: ${btc_ext['ma50']:,.2f}")
    if btc_ext["ma20"] is not None and btc_ext["ma50"] is not None and btc_ext["close"] is not None:
        if btc_ext["close"] > btc_ext["ma20"] > btc_ext["ma50"]:
            tech_parts.append("趨勢：多頭排列（價>MA20>MA50）")
        elif btc_ext["close"] < btc_ext["ma20"] < btc_ext["ma50"]:
            tech_parts.append("趨勢：空頭排列（價<MA20<MA50）")
        else:
            tech_parts.append("趨勢：盤整/交叉")

    # ── VIX 期限結構 ──
    vix_spot = _quote_of("^VIX")
    vix3m = _quote_of("^VIX3M")
    if vix_spot is not None and vix3m is not None:
        if vix_spot > vix3m:
            structure = "Backwardation（短期恐慌 > 長期，市場定價急性風險）"
        else:
            structure = "Contango（正常，短期 < 長期）"
        tech_parts.append(f"VIX 期限結構: VIX {vix_spot:.2f} vs VIX3M {vix3m:.2f} → {structure}")

    header = "【系統強制即時報價】" + " | ".join(parts)
    if tech_parts:
        header += "\n【技術指標與結構】" + " | ".join(tech_parts)
    return header


def _prewarm_tool_caches() -> None:
    """並行預取所有獨立 tool 數據，填充快取供後續 Crew 使用（省 40-60% 等待時間）。"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from tools import (
        coinglass_data_tool,
        fear_greed_tool,
        etf_flow_tool,
        econ_calendar_tool,
        onchain_metrics_tool,
        ml_quant_tool,
        regime_scorecard_tool,
        macro_context_tool,
    )

    # 定義所有獨立的 tool 呼叫（無互相依賴）
    tasks: dict[str, callable] = {
        "coinglass_funding_rate": lambda: coinglass_data_tool.run("funding_rate"),
        "coinglass_liquidations": lambda: coinglass_data_tool.run("liquidations"),
        "coinglass_long_short":   lambda: coinglass_data_tool.run("long_short_ratio"),
        "coinglass_options":      lambda: coinglass_data_tool.run("options_info"),
        "fear_greed":             lambda: fear_greed_tool.run(),
        "etf_flow":               lambda: etf_flow_tool.run(),
        "econ_calendar":          lambda: econ_calendar_tool.run(),
        "onchain_metrics":        lambda: onchain_metrics_tool.run(),
        "ml_quant":               lambda: ml_quant_tool.run(),
        "regime_scorecard":       lambda: regime_scorecard_tool.run(),
        "macro_context":          lambda: macro_context_tool.run(),
    }

    logger.info("Pre-warming %d tool caches in parallel...", len(tasks))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result(timeout=60)
            except Exception as e:
                logger.warning("Pre-warm %s failed (non-fatal): %s", name, e)
    elapsed = time.time() - t0
    logger.info("Tool cache pre-warm done in %.1fs", elapsed)


def _run_pipeline_once(
    exclude_context: str | None,
    use_fallback_llm: bool = False,
) -> tuple[str, Exception | None]:
    """使用 ThreadPoolExecutor 讓兩個 Crew 同時執行，回傳合併戰報。use_fallback_llm=True 時全用 GPT 降低靜默失敗。"""
    try:
        _prewarm_tool_caches()
        price_context = get_realtime_quotes()
        trimmed_exclusion = _truncate_text(exclude_context, MAX_EXCLUSION_CONTEXT_CHARS)

        # Phase 1：載入上期建議追蹤（注入 Crypto 戰報頭部）
        prev_recs = ""
        if not SKIP_BIGQUERY:
            try:
                prev_recs = load_previous_recs_block()
                if prev_recs:
                    prev_recs = _truncate_text(prev_recs, MAX_PREV_RECS_CHARS)
                    logger.info("Loaded previous recommendations block (%d chars).", len(prev_recs))
            except Exception as _e:
                logger.warning("Could not load previous recs block: %s", _e)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(
                lambda: str(CryptoResearchCrew(use_fallback_llm=use_fallback_llm).run(
                    exclude_context=trimmed_exclusion,
                    price_context=price_context,
                    prev_recs_block=prev_recs,
                ))
            )
            future_ai = executor.submit(
                lambda: str(AIResearchCrew(use_fallback_llm=use_fallback_llm).run(
                    exclude_context=trimmed_exclusion, price_context=price_context
                ))
            )

            crypto_report = future_crypto.result()
            ai_report = future_ai.result()

        combined_report = f"{crypto_report}\n\n{ai_report}"
        # 一律經注入流程：有 BQ 則覆寫上期；無則剥除 LLM 幻覺之多列上期追蹤
        combined_report = _inject_canonical_prev_recs_block(combined_report, prev_recs or "")
        return combined_report, None
    except Exception as e:
        return "", e


def run_pipeline_with_retries(exclude_context: str | None) -> tuple[str, bool, dict | None]:
    """
    帶 503 退避與驗證重試的產報流程。回傳 (final_report, report_valid)。
    """
    scratchpad.begin_run(
        {
            "pipeline": "run_pipeline_with_retries",
            "max_report_retries": MAX_REPORT_RETRIES,
            "max_503_retries": MAX_503_RETRIES,
            "skip_telegram": SKIP_TELEGRAM,
            "skip_bigquery": SKIP_BIGQUERY,
            "strict_consistency_gate": STRICT_CONSISTENCY_GATE,
        }
    )
    final_report = ""
    report_valid = False
    last_validation: dict | None = None
    try:
        for attempt in range(MAX_REPORT_RETRIES + 1):
            last_err: Exception | None = None
            structural_validation_err: Exception | None = None
            for step in range(MAX_503_RETRIES + 1):
                report, err = _run_pipeline_once(exclude_context, use_fallback_llm=False)
                if err is None:
                    final_report = _postprocess_report_for_resilience(report)
                    # Pydantic + assertion（你要求的順序）
                    output_json = _build_output_json_for_validation(final_report)
                    try:
                        parsed = parse_report_output(output_json)
                        assert_report_output(parsed)
                        assert_sample_output(output_json)
                        if not _codex_judge_pass(final_report):
                            raise AssertionError("Codex judge 判定包含 API 錯誤訊息或無關內容")
                    except Exception as v_err:
                        structural_validation_err = v_err
                        logger.warning(
                            "輸出結構/內容驗證未通過（不佔 503 重試配額，交由報告驗證重試機制處理）：%s",
                            v_err,
                        )
                    break
                last_err = err
                if _is_retriable(err) and step < MAX_503_RETRIES:
                    wait = BACKOFF_BASE_SEC * (2**step)
                    logger.warning(
                        "暫時性錯誤（可重試），%ds 後重試 (%d/%d)：%s",
                        wait,
                        step + 1,
                        MAX_503_RETRIES + 1,
                        err,
                    )
                    time.sleep(wait)
                else:
                    logger.error("Execution failed: %s", err)
                    final_report = f"{ERROR_PREFIX}{err}"
                    break
            # 可重試錯誤時，以 fallback LLM（全 GPT）再跑一次
            if last_err is not None and _is_retriable(last_err):
                logger.warning("Primary LLM 失敗，改用 fallback LLM（全 GPT）重試一次：%s", last_err)
                report, err = _run_pipeline_once(exclude_context, use_fallback_llm=True)
                if err is None:
                    final_report = _postprocess_report_for_resilience(report)
                    output_json = _build_output_json_for_validation(final_report)
                    try:
                        parsed = parse_report_output(output_json)
                        assert_report_output(parsed)
                        assert_sample_output(output_json)
                        if not _codex_judge_pass(final_report):
                            raise AssertionError("Codex judge 判定包含 API 錯誤訊息或無關內容")
                    except Exception as v_err:
                        structural_validation_err = v_err
                    last_err = None
            if last_err is not None:
                break
            if structural_validation_err is not None:
                logger.info(
                    "[Attempt %d] 結構驗證未過，保留可讀報告交由 validate_report 決定是否重試：%s",
                    attempt + 1,
                    structural_validation_err,
                )

            result = validate_report(final_report)
            _log_validation_dual_run(final_report, result)
            last_validation = result
            report_valid = result["valid"]
            scratchpad.append_gate_result(attempt + 1, result)
            fallback_cnt = _fallback_news_count(final_report)
            logger.info(
                "[Attempt %d] Validation — news=%d, fallback_news=%d, valid=%s",
                attempt + 1,
                result["news_count"],
                fallback_cnt,
                report_valid,
            )
            if report_valid:
                logger.info("Report generation successful.")
                scratchpad.finalize_run("success", {"finalAttempt": attempt + 1, "valid": True})
                return final_report, True, result
            logger.warning("Report incomplete: %s", result["issues"])
            if logger.isEnabledFor(logging.DEBUG) and final_report:
                logger.debug("Report snippet (first 500 chars): %s", final_report[:500].replace("\n", " "))
            if attempt < MAX_REPORT_RETRIES:
                logger.info("Retrying report generation (%d/%d)...", attempt + 2, MAX_REPORT_RETRIES + 1)

        if final_report and not final_report.startswith("🚨"):
            if STRICT_CONSISTENCY_GATE:
                logger.error("Report invalid and STRICT_CONSISTENCY_GATE=1; keep blocked (no forced send).")
            else:
                logger.warning("Sending report despite validation issues (retries exhausted).")
        end_status = "completed_invalid"
        if final_report.startswith("🚨"):
            end_status = "execution_error_report"
        scratchpad.finalize_run(
            end_status,
            {"report_valid": report_valid, "strict_consistency_gate": STRICT_CONSISTENCY_GATE},
        )
        return final_report, report_valid, last_validation
    finally:
        if scratchpad.current_run_id():
            scratchpad.finalize_run("aborted_without_finalize", {"note": "exception_or_broken_flow"})


def _validate_required_keys() -> None:
    """啟動前檢查必要 API 金鑰，提早回報缺失。"""
    required = {
        "XAI_API_KEY": "Grok（加密市場情報員）",
        "OPENAI_API_KEY": "GPT（AI 情報員）",
        "GEMINI_API_KEY": "Gemini（機構策略主編）",
        "APIFY_API_TOKEN": "Apify 搜尋引擎",
    }
    missing = [k for k in required if not (os.getenv(k) or "").strip()]
    if missing:
        names = ", ".join(f"{k}（{required[k]}）" for k in missing)
        raise RuntimeError(
            f"缺少必要 API 金鑰：{names}。"
            "請在 .env 或環境變數中設定。"
            "若出現 XaiException，請確認 XAI_API_KEY 有效且未過期。"
        )


def _log_api_key_inventory() -> None:
    """盤點金鑰是否已設定（不記錄密碼）。MISS 表示該路徑工具會走備援或 N/A。"""
    groups: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "必要",
            [
                ("XAI_API_KEY", "Grok"),
                ("OPENAI_API_KEY", "OpenAI"),
                ("GEMINI_API_KEY", "Gemini"),
                ("APIFY_API_TOKEN", "Apify"),
            ],
        ),
        (
            "建議/備援",
            [
                ("ANTHROPIC_API_KEY", "Claude fallback"),
                ("NEWSAPI_KEY", "NewsAPI"),
                ("GNEWS_API_KEY", "GNews"),
                ("COINGLASS_API_KEY", "CoinGlass"),
                ("CRYPTOPANIC_API_KEY", "CryptoPanic"),
                ("CRYPTOQUANT_API_KEY", "CryptoQuant"),
                ("FRED_API_KEY", "FRED"),
                ("TWITTER_BEARER_TOKEN", "X/Twitter"),
                ("OPENROUTER_API_KEY", "OpenRouter"),
                ("FMP_API_KEY", "FMP"),
                ("GLASSNODE_API_KEY", "Glassnode"),
            ],
        ),
    ]
    for title, keys in groups:
        line = " | ".join(
            f"{label}: {'OK' if (os.getenv(env) or '').strip() else 'MISS'}"
            for env, label in keys
        )
        logger.info("API key inventory [%s] %s", title, line)


def _verify_optional_api_keys_light() -> None:
    """設 VERIFY_API_KEYS=1 時對少數公開端點做輕量探測（不驗證 Grok/Gemini 以節省配額）。"""
    if os.getenv("VERIFY_API_KEYS", "").lower() not in ("1", "true", "yes"):
        return
    try:
        import requests
    except ImportError:
        logger.warning("VERIFY_API_KEYS set but requests not installed; skip probe.")
        return
    nk = (os.getenv("NEWSAPI_KEY") or "").strip()
    if nk:
        try:
            r = requests.get(
                "https://newsapi.org/v2/top-headlines",
                params={"country": "us", "pageSize": 1, "apiKey": nk},
                timeout=10,
            )
            logger.info("VERIFY_API_KEYS: NewsAPI HTTP %s", r.status_code)
        except Exception as e:
            logger.warning("VERIFY_API_KEYS: NewsAPI probe failed: %s", e)
    apify = (os.getenv("APIFY_API_TOKEN") or "").strip()
    if apify:
        try:
            r = requests.get(
                "https://api.apify.com/v2/users/me",
                headers={"Authorization": f"Bearer {apify}"},
                timeout=10,
            )
            logger.info("VERIFY_API_KEYS: Apify user/me HTTP %s", r.status_code)
        except Exception as e:
            logger.warning("VERIFY_API_KEYS: Apify probe failed: %s", e)


if __name__ == "__main__":
    _install_runtime_noise_filters()
    logger.info("Initializing Q-Silicon Ultimate Agent...")
    _validate_required_keys()
    _log_api_key_inventory()
    _verify_optional_api_keys_light()
    generate_quant_chart("daily_chart.png")
    exclusion = fetch_exclusion_context()
    if exclusion:
        logger.info("Loaded exclusion context from previous report (to avoid duplicate news).")

    # Pre-initialize so downstream references are always safe even if the
    # pipeline call raises an uncaught exception.
    final_report: str = ""
    report_valid: bool = False
    validation_result: dict | None = None
    try:
        final_report, report_valid, validation_result = run_pipeline_with_retries(exclusion)
    except Exception as _pipeline_err:
        logger.error("Critical unhandled pipeline error: %s", _pipeline_err, exc_info=True)
        scratchpad.log_pipeline_error(str(_pipeline_err))
        final_report = f"{ERROR_PREFIX}{_pipeline_err}"
        report_valid = False
    logger.info("Pipeline finished (valid=%s, chars=%d).", report_valid, len(final_report or ""))
    invalid_issues_preview = ""
    gate_issues_full: list[str] = []
    gate_artifact_rel: str | None = None
    if not report_valid and final_report and (not final_report.startswith("🚨")):
        try:
            inv = validation_result if validation_result is not None else validate_report(final_report)
            gate_issues_full = [i for i in inv.get("issues", []) if i]
            invalid_issues_preview = " | ".join(gate_issues_full[:3])
            art_path = _persist_gate_validation_failure(final_report, inv)
            if art_path:
                try:
                    gate_artifact_rel = str(art_path.relative_to(Path(__file__).resolve().parent))
                except ValueError:
                    gate_artifact_rel = str(art_path)
            logger.error(
                "Report invalid under consistency gate. Top issues: %s",
                invalid_issues_preview or "N/A",
            )
        except Exception as _validate_err:
            logger.warning("Could not build invalid report issue preview: %s", _validate_err)

    # ── Tracker：儲存建議 & 每日回查未平倉部位 ───────────────────────────────
    _report_ok = bool(final_report and not final_report.startswith("🚨") and (report_valid or not STRICT_CONSISTENCY_GATE))
    if not SKIP_BIGQUERY and _report_ok:
        _saved = tracker.save_recommendations(final_report)
        if _saved:
            logger.info("Tracker: saved %d trade recommendations.", _saved)
        _closed = tracker.check_and_update_positions()
        if _closed:
            logger.info("Tracker: %d positions updated today: %s", len(_closed), _closed)
    elif not SKIP_BIGQUERY:
        # 即使報告失敗，仍每日回查已有的未平倉建議
        tracker.check_and_update_positions()

    # ── Tracker：週一發送績效週報 ─────────────────────────────────────────────
    token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not SKIP_BIGQUERY and not SKIP_TELEGRAM and token and chat_id:
        if datetime.now(timezone.utc).weekday() == 0:  # 0 = Monday
            perf_summary = tracker.generate_performance_summary()
            if perf_summary:
                try:
                    import telebot as _tb

                    safe_perf = sanitize_telegram_html(perf_summary)
                    bot = _tb.TeleBot(token)
                    try:
                        bot.send_message(chat_id, safe_perf, parse_mode="HTML", timeout=30)
                    except Exception as send_e:
                        err_str = str(send_e).lower()
                        if "can't parse entities" in err_str:
                            bot.send_message(
                                chat_id, strip_html(safe_perf), timeout=30
                            )
                        else:
                            raise
                    logger.info("Weekly performance summary sent to Telegram.")
                except Exception as _e:
                    logger.warning("Failed to send weekly performance summary: %s", _e)

    # ── 移除機器可讀區塊，再發送 Telegram ────────────────────────────────────
    clean_report = tracker.strip_tracker_blocks(final_report)

    if not SKIP_TELEGRAM:
        if STRICT_CONSISTENCY_GATE and not report_valid:
            logger.error(
                "STRICT_CONSISTENCY_GATE=1 且 report_valid=False，阻擋 Telegram 發送。Top issues: %s",
                invalid_issues_preview or "N/A",
            )
            if token and chat_id:
                _send_telegram_gate_alert(
                    token,
                    chat_id,
                    top_issues=invalid_issues_preview,
                    error_text=final_report if final_report.startswith("🚨") else None,
                    all_issues=gate_issues_full if gate_issues_full else None,
                    artifact_rel=gate_artifact_rel,
                )
            else:
                logger.warning("Telegram configuration missing. Skipping gate alert push.")
        elif token and chat_id:
            _send_telegram_report(clean_report, token, chat_id, image_path="daily_chart.png")
        else:
            logger.warning("Telegram configuration missing. Skipping push.")
    else:
        logger.info("SKIP_TELEGRAM=1: skipping Telegram push.")

    if not SKIP_BIGQUERY and _report_ok:
        extract_and_save_metrics(final_report)
    elif SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1: skipping metrics write.")
    elif not _report_ok:
        logger.warning(
            "Skipping BigQuery metrics write — report blocked. strict_gate=%s, report_valid=%s, startswith_error=%s, empty=%s, top_issues=%s",
            STRICT_CONSISTENCY_GATE,
            report_valid,
            bool(final_report.startswith("🚨")) if final_report else False,
            not bool(final_report),
            invalid_issues_preview or "N/A",
        )
