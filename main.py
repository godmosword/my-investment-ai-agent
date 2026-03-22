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
from telegram_sender import (
    sanitize_telegram_html,
    _balance_telegram_html_tags,
    strip_html,
    _safe_chunks,
    _send_telegram_report,
    _send_telegram_gate_alert,
    _format_gate_issues_followup_messages,
    _gate_alert_severity_and_code,
    GATE_CODE_CRITICAL_SOURCE,
    GATE_CODE_LLM_DISCONNECT,
    GATE_CODE_EXECUTION_FAILED,
    GATE_CODE_VALIDATION,
    GATE_CODE_UNKNOWN,
)
from bigquery_writer import (
    extract_and_save_metrics,
    fetch_exclusion_context,
    _get_last_success_report_time_utc,
    _extract_section,
    _extract_news_titles,
    _semantic_dedup_titles,
)
from report_validator import (
    validate_report,
    _crypto_report_prefix,
    _count_effective_news_items,
    _fallback_news_count,
    _normalize_regime_token,
    _has_news_timezone_utc8,
    _has_macro_outlier_values,
    _has_macro_conflicts,
    _risk_off_star_cap_violated,
    _pair_trade_unit_consistent,
    _has_crypto_trade_section,
    _has_ai_trade_section,
    _partial_news_ok,
    _pick_rotation_crypto_ok,
    _pick_rotation_equity_ok,
    _has_rumor_grade_marker,
    _conflicting_total_risk_budget_lines,
    _qsrec_opposing_direction_same_asset,
    _fetch_yesterday_qsrec_canonical_set,
    _pick_justification_crypto_ok,
    _pick_justification_equity_ok,
    _pick_rotation_override_min_gap,
    _has_repeat_quality_anchor,
    _normalize_pick_asset_legs,
    _reason_covers_assets,
    _score_kw_hits,
    _extract_today_pick_reason,
    _persist_gate_validation_failure,
    _is_conditional_regime_line,
    _has_source_observability_conflicts,
    _allow_partial_news_gate,
    _strict_pick_justification,
    _strict_pick_rotation,
    _allow_repeat_pick_override,
    _strict_pick_scoring,
    _repeat_pick_days_max,
    _repeat_pick_min_score,
    _count_news_tags_only,
    _join_news_tag_timestamp_lines,
    _normalize_fullwidth_news_brackets_on_news_lines,
    _NEWS_HK_TZ_TOKEN,
    _NEWS_LINE_INLINE_HTML_RE,
    _MISSING_REASON_PROXY_RE,
    _REPEAT_PICK_REASON_RE,
    _PICK_SCORE_FIELDS,
    _CRYPTO_PICK_KW,
    _CRYPTO_PICK_FALLBACK,
    _EQUITY_PICK_KW,
    _EQUITY_PICK_FALLBACK,
    _MISSING_REASON_PROXY_RE,  # noqa: F811
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
    UNACTIONABLE_TRADE_RE,
    span_has_positive_trade_watch_declaration,
    text_has_positive_trade_watch_mode,
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

# 重試常數（集中管理，方便調參）
MAX_REPORT_RETRIES = int(os.getenv("MAX_REPORT_RETRIES", "2"))
MAX_503_RETRIES = int(os.getenv("MAX_503_RETRIES", "3"))
BACKOFF_BASE_SEC = int(os.getenv("BACKOFF_BASE_SEC", "30"))
ERROR_PREFIX = "🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息："
MAX_EXCLUSION_CONTEXT_CHARS = int(os.getenv("MAX_EXCLUSION_CONTEXT_CHARS", "1000"))
MAX_PREV_RECS_CHARS = int(os.getenv("MAX_PREV_RECS_CHARS", "1200"))

# 除錯用環境變數：LOG_LEVEL=DEBUG | DEBUG=1 | CREW_VERBOSE=1（Agent 步驟）| SKIP_TELEGRAM=1 | SKIP_BIGQUERY=1


def _truncate_text(text: str | None, limit: int) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n…[truncated]"


def _fix_glued_na_suffix(text: str) -> str:
    """修復 <code>N/A</code> 或裸 N/A 與後續中英文字黏連（如 N/ACoinGlass）。"""
    if not text:
        return text
    out = re.sub(r"(N/A)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", text)
    out = re.sub(r"(</code>)([A-Za-z\u4e00-\u9fff])", r"\1\n\2", out)
    return out


def _sanitize_macro_outlier_values(text: str) -> str:
    """宏觀數值異常修正：10Y/2Y/SOFR 超出合理區間時改為 N/A。"""
    patched = text

    def _pct_or_none(raw: str) -> float | None:
        try:
            return float(raw.replace(",", ""))
        except ValueError:
            return None

    def _repl_ust(m: re.Match) -> str:
        y10, y2 = _pct_or_none(m.group(1)), _pct_or_none(m.group(2))
        if y10 is None or y2 is None:
            return m.group(0)
        if not (0.0 <= y10 <= 20.0 and 0.0 <= y2 <= 20.0):
            return "美債 10Y: N/A（數據異常待確認） | 2Y: N/A（數據異常待確認） | 利差: N/A"
        return m.group(0)

    patched = re.sub(
        r"美債\s*10Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y[：:]\s*([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust, patched,
    )
    patched = re.sub(
        r"美債\s*10Y\D{0,18}([0-9,]+(?:\.[0-9]+)?)\s*%\s*[|｜]\s*2Y\D{0,12}([0-9,]+(?:\.[0-9]+)?)\s*%",
        _repl_ust, patched,
    )
    def _repl_2y(m: re.Match) -> str:
        val = _pct_or_none(m.group(2))
        if val is None or 0.0 <= val <= 20.0:
            return m.group(0)
        return f"{m.group(1)}N/A（數據異常待確認）"
    patched = re.sub(r"(2Y[^0-9%\n]{0,16})([0-9,]+(?:\.[0-9]+)?)%", _repl_2y, patched)

    def _repl_sofr(m: re.Match) -> str:
        val = _pct_or_none(m.group(1))
        if val is None or 0.0 <= val <= 20.0:
            return m.group(0)
        return "Fed SOFR 期貨隱含利率: N/A（數據異常待確認）"
    patched = re.sub(r"Fed SOFR 期貨隱含利率[：:]\s*([0-9,]+(?:\.[0-9]+)?)%", _repl_sofr, patched)
    patched = re.sub(
        r"(利差[：:]?\s*)[+\-−]?([0-9,]{4,}(?:\.[0-9]+)?)\s*bp",
        r"\1N/A", patched, flags=re.IGNORECASE,
    )
    return patched


def _inject_canonical_prev_recs_block(report_text: str, canonical_html: str) -> str:
    """以 BigQuery 載入之上期追蹤覆寫 LLM 輸出，避免模型自行膨脹多筆同標的進場價。"""
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
    return f"{head_clean}{sep}{canonical_html}\n\n{tail}"


def _auto_prefix_missing_news_tags(text: str) -> str:
    """LLM 漏寫〔新聞 N〕時自動補標籤。"""
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
            elif st.startswith(("投資解讀", "💎", "·", "•", "- ", "—", "低置信度", "資料缺失",
                                 "HuggingFace", "OpenRouter", "AI Momentum")):
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
    """將新聞時間標籤統一補上 UTC+8。"""
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


def _unify_regime_mentions(text: str) -> str:
    """統一全篇 regime：以第一個【今日市場模式】為準，覆寫後續風險預算中的 regime。"""
    regime_token_re = r'(risk[\s_\-]*on|risk[\s_\-]*off|neutral)'
    m = re.search(
        rf'【今日市場模式】\s*(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*',
        text, re.IGNORECASE,
    )
    if not m:
        return text
    regime = _normalize_regime_token(m.group(1))
    if not regime:
        return text
    patched = re.sub(
        rf'(【今日市場模式】\s*(?:<[^>]*>\s*)*){regime_token_re}(?:\s*</[^>]*>)*',
        rf"\1{regime}", text, flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:][^\n]*?regime\s*=\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*",
        rf"\1regime={regime}", patched, flags=re.IGNORECASE,
    )
    patched = re.sub(
        rf"(今日風險預算[：:]\s*)(?:<[^>]*>\s*)*{regime_token_re}(?:\s*</[^>]*>)*(\s*[｜|])",
        rf"\1{regime}\3", patched, flags=re.IGNORECASE,
    )
    patched = re.sub(
        r'("regime"\s*:\s*")(risk_on|risk_off|neutral)(")',
        rf'\1{regime}\3', patched, flags=re.IGNORECASE,
    )

    def _risk_budget_line_repl(m: re.Match) -> str:
        line = m.group(0)
        if _is_conditional_regime_line(line):
            return line
        line = re.sub(r'\brisk[\s_-]*on\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\brisk[\s_-]*off\b', regime, line, flags=re.IGNORECASE)
        line = re.sub(r'\bneutral\b', regime, line, flags=re.IGNORECASE)
        return line

    patched = re.sub(r'(?im)^.*今日風險預算[^\n]*$', _risk_budget_line_repl, patched)
    return patched


def _remove_duplicate_source_observability(text: str) -> str:
    """移除報告內重複/過時的 SourceHealth/SourceErrors/SourceQuota 行。"""
    lines = text.splitlines()
    cleaned = [
        ln for ln in lines
        if not re.search(r"\bSource(?:Health|Errors|Quota)\b", ln)
        and not re.match(r"^\s*【Source(?:Health|Errors|Quota)】", ln)
    ]
    return "\n".join(cleaned).strip()


def _drop_unactionable_trade_blocks(text: str) -> str:
    """移除不可執行交易段（現價/進場/目標/停損為 N/A）。"""
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


def _ensure_signal_conflict_section(text: str) -> str:
    """若報告缺少訊號衝突摘要，自動注入預設值，避免 gate 阻擋。"""
    if re.search(r'[訊信]號衝突(?:摘要|分析)?[：:]', text):
        return text
    fallback_line = "訊號衝突摘要：各指標方向基本一致，暫無顯著多空衝突訊號。"
    risk_budget_m = re.search(r'(今日風險預算[：:][^\n]*\n)', text)
    if risk_budget_m:
        pos = risk_budget_m.end()
        return text[:pos] + fallback_line + "\n" + text[pos:]
    trade_section_m = re.search(r'(區塊④【)', text)
    if trade_section_m:
        pos = trade_section_m.start()
        return text[:pos] + fallback_line + "\n" + text[pos:]
    marker = "[QSREC_START]"
    pos = text.find(marker)
    if pos != -1:
        return text[:pos].rstrip() + "\n" + fallback_line + "\n\n" + text[pos:]
    return text


def _ensure_trade_sections(text: str) -> str:
    """當 LLM 漏寫交易段時，注入「觀望模式」區塊（不捏造價格）。"""
    has_crypto_trade = _has_crypto_trade_section(text)
    has_ai_trade = _has_ai_trade_section(text)
    if has_crypto_trade and has_ai_trade:
        return text
    regime_m = re.search(
        r'【今日市場模式】\s*(?:<[^>]*>\s*)*(risk[\s_\-]*on|risk[\s_\-]*off|neutral)(?:\s*</[^>]*>)*',
        text, re.IGNORECASE,
    )
    regime = (_normalize_regime_token(regime_m.group(1)) if regime_m else None) or "neutral"
    blocks: list[str] = []
    if not has_crypto_trade:
        blocks.append("\n".join([
            "區塊④【資金流向與精準操作 (Crypto)】：",
            "· <b>觀望模式</b>：資料不足觀望，暫不開新倉（避免捏造現價/進場/目標/停損）。",
            f"· 風險預算：依 <code>{regime}</code> 模式降低風險，僅保留既有倉位管理。",
            "· 重新進場條件：待下一輪有效新聞、即時報價與多時框訊號齊備後再提供交易參數。",
        ]))
    if not has_ai_trade:
        blocks.append("\n".join([
            "區塊④【AI 產業鏈精準操作 (US Equities)】：",
            "· <b>觀望模式</b>：資料不足觀望，暫不提供股票進出場價格。",
            f"· 風險預算：依 <code>{regime}</code> 模式執行防守配置，避免情緒性追價。",
            "· 重新進場條件：需補齊產業催化、成交量與多時框確認後再發布可執行建議。",
        ]))
    if not blocks:
        return text
    marker = "[QSREC_START]"
    pos = text.find(marker)
    block = "\n\n".join(blocks)
    if pos != -1:
        return text[:pos].rstrip() + "\n\n" + block + "\n\n" + text[pos:]
    return text.rstrip() + "\n\n" + block


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
        f"{tier_line}【新聞資料狀態】\n"
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


def _ensure_low_confidence_for_many_na(text: str) -> str:
    """當 N/A 過多時，注入低置信度說明段落。"""
    if len(re.findall(r"\bN/A\b", text)) <= 3:
        return text
    has_lc = bool(re.search(r"低置信度|低信心", text))
    has_proxy = bool(_MISSING_REASON_PROXY_RE.search(text))
    if has_lc and has_proxy:
        return text
    if "方案權限回傳暫缺" in text:
        return text
    block = (
        "· <b>低置信度</b>：儀表板若出現多項 <code>N/A</code>，表示第三方 API 或方案權限回傳暫缺，"
        "敘事仍以已回傳之技術面與新聞催化為準。"
        "<b>資料缺失原因</b>：與工具欄位空白或 <code>[DATA_MISSING:...]</code> 標記一致；"
        "<b>替代指標</b>：請交叉比對 DXY、VIX、資金費率、Fear&amp;Greed、RSI、現貨成交與上文核心新聞。"
    )
    for anchor in (r"(區塊①[^\n]*\n)", r"(數據儀表板[^\n]*\n)", r"([^\n]*\bDXY\b[^\n]*\n)", r"(【今日市場模式】[^\n]*\n)"):
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
    """改寫 [DATA_MISSING:...] 標記為中文短語，避免 Gate 誤判。"""
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
    patched = _remove_duplicate_source_observability(patched)
    observe_block = source_observability_lines()
    marker = "[QSREC_START]"
    pos = patched.find(marker)
    if pos != -1:
        patched = patched[:pos].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos:]
    else:
        patched = patched.rstrip() + f"\n\n{observe_block}"
    if not all(s in patched for s in ("【SourceHealth】", "【SourceErrors】", "【SourceQuota】")):
        patched = _remove_duplicate_source_observability(patched)
        pos2 = patched.find(marker)
        if pos2 != -1:
            patched = patched[:pos2].rstrip() + f"\n\n{observe_block}\n\n" + patched[pos2:]
        else:
            patched = patched.rstrip() + f"\n\n{observe_block}"
    return patched


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
    cat = category.upper()
    if cat not in ("CRYPTO", "EQUITY"):
        return None
    try:
        client = bigquery.Client(project=PROJECT_ID)
        job_cfg = bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("cat", "STRING", cat)]
        )
        rows = list(
            client.query(
                f"""
                SELECT DISTINCT asset
                FROM `{RECOMMENDATIONS_TABLE}`
                WHERE report_date = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
                  AND UPPER(COALESCE(category, '')) = @cat
                """,
                job_config=job_cfg,
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
    except Exception as e:
        logger.warning("_quote_of %s failed: %s", symbol, e)
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
    except Exception as e:
        logger.warning("_compute_rsi failed: %s", e)
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
    except Exception as e:
        logger.warning("_get_extended_price_data %s failed: %s", symbol, e)
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

    # -- Conditionally-required keys: warn instead of hard-fail --
    if not os.getenv("SKIP_TELEGRAM", "").strip():
        tg_missing = [
            k
            for k in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")
            if not (os.getenv(k) or "").strip()
        ]
        if tg_missing:
            logger.warning(
                "Telegram keys missing (%s); Telegram push will be skipped. "
                "Set SKIP_TELEGRAM=1 to suppress this warning.",
                ", ".join(tg_missing),
            )

    if not os.getenv("SKIP_BIGQUERY", "").strip():
        if not (os.getenv("GCP_PROJECT_ID") or "").strip():
            logger.warning(
                "GCP_PROJECT_ID is not set; BigQuery metrics will be skipped. "
                "Set SKIP_BIGQUERY=1 to suppress this warning.",
            )


def _validate_env_types() -> None:
    """Validate numeric environment variables at startup to fail fast on typos."""
    numeric_vars = {
        "MAX_REPORT_RETRIES": "2",
        "MAX_503_RETRIES": "3",
        "BACKOFF_BASE_SEC": "30",
        "NEWSAPI_DAILY_CALL_LIMIT": "120",
        "GNEWS_DAILY_CALL_LIMIT": "120",
        "APIFY_DAILY_CALL_LIMIT": "30",
        "PICK_ROTATION_OVERRIDE_MIN_GAP": "12",
        "PICK_REPEAT_DAYS_MAX": "2",
        "PICK_REPEAT_MIN_SELECTION_SCORE": "75",
        "MAX_EXCLUSION_CONTEXT_CHARS": "1000",
        "MAX_PREV_RECS_CHARS": "1200",
    }
    for var, default in numeric_vars.items():
        raw = os.getenv(var)
        if raw is not None:
            try:
                float(raw)
            except ValueError:
                raise RuntimeError(
                    f"Environment variable {var}={raw!r} is not a valid number (default: {default})"
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
    _validate_env_types()
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
                    last_success_time_utc=_get_last_success_report_time_utc(),
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
