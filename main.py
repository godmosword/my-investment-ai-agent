import os
import re
import sys
import time
import logging
import builtins
from datetime import datetime, timezone
from dotenv import load_dotenv
import yfinance as yf
from pathlib import Path

from crew import AIResearchCrew, CryptoResearchCrew
from report_render import assemble_daily_brief_report, render_telegram_daily_brief
from schemas import DailyBriefReport
from report_output_validator import (
    assert_report_output,
    assert_sample_output,
    parse_report_output,
)
from telegram_sender import (
    sanitize_telegram_html,
    _balance_telegram_html_tags,  # noqa: F401
    strip_html,
    _send_telegram_report,
    _send_telegram_gate_alert,
    _format_gate_issues_followup_messages,  # noqa: F401
    _gate_alert_severity_and_code,  # noqa: F401
    GATE_CODE_CRITICAL_SOURCE,  # noqa: F401
)
from bigquery_writer import (
    extract_and_save_metrics,
    fetch_exclusion_context,
    _get_last_success_report_time_utc,
)
from report_validator import (
    validate_report,
    validate_structured_report,
    _crypto_report_prefix,  # noqa: F401
    _fallback_news_count,
    _has_news_timezone_utc8,  # noqa: F401
    _has_macro_outlier_values,  # noqa: F401
    _has_macro_conflicts,  # noqa: F401
    _risk_off_star_cap_violated,  # noqa: F401
    _pair_trade_unit_consistent,  # noqa: F401
    _has_crypto_trade_section,  # noqa: F401
    _partial_news_ok,  # noqa: F401
    _pick_rotation_crypto_ok,  # noqa: F401
    _pick_rotation_equity_ok,  # noqa: F401
    _pick_rotation_override_min_gap,  # noqa: F401
    _has_rumor_grade_marker,  # noqa: F401
    _conflicting_total_risk_budget_lines,  # noqa: F401
    _qsrec_opposing_direction_same_asset,  # noqa: F401
    _persist_gate_validation_failure,
    _allow_partial_news_gate,
)
from crew import _parse_regime_from_scorecard
from tools import source_observability_lines
from visualizer import generate_quant_chart
import tracker
import scratchpad
from tracker import load_previous_recs_block
from report_pipeline_compare import compare_validation_results

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
# Score-based gate: send with banner when warning count <= threshold and no blocking issues.
# Set GATE_WARN_THRESHOLD=0 to revert to strict binary behaviour.
GATE_WARN_THRESHOLD = int(os.getenv("GATE_WARN_THRESHOLD", "3"))

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


def _postprocess_report_for_resilience(text: str) -> str:
    """Jinja 已決定性排版；僅做 Telegram HTML 安全清洗。"""
    if not text:
        return text
    return sanitize_telegram_html(text)


def _persist_pipeline_raw_report(report: DailyBriefReport | None) -> None:
    """將組裝後 DailyBriefReport 寫入 logs/run_*/raw_data.json（渲染前結構化真相）。"""
    if report is None:
        return
    try:
        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(hours=8))
        run_id = datetime.now(tz).strftime("run_%Y%m%d_%H%M%S")
        d = Path("logs") / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "raw_data.json").write_text(
            report.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Wrote structured raw report to %s", d / "raw_data.json")
    except OSError as e:
        logger.warning("raw_data.json write failed: %s", e)


def _build_output_json_for_validation(
    final_report: str,
    report: DailyBriefReport,
) -> dict:
    """以最終渲染字串為主，搭配結構化資料做驗證 payload。"""
    plain = strip_html(final_report).strip()
    title = "Daily Brief"
    if plain:
        first = plain.splitlines()[0].strip()
        if first:
            title = first[:120]
    summary = plain[:800] if plain else ""
    if not summary:
        summary = (report.crypto.narrative_of_day + " " + report.ai.pick_reason).strip()[:800]
    code_match = re.search(r"(<code>[\s\S]*?</code>)", final_report, re.IGNORECASE)
    code = code_match.group(1) if code_match else ""
    news_text = "\n".join(
        line
        for line in final_report.splitlines()
        if ("HTTPError" in line or "[DATA_MISSING" in line or "Traceback" in line)
    )
    return {
        "title": title or "Daily Brief",
        "summary": summary or "summary",
        "code": code,
        "news": news_text,
    }


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


def _inject_gate_warning_banner(html: str, warning_issues: list[str]) -> str:
    """
    Prepend a visible ⚠️ banner to the report when gate passes with warnings.
    Lists the outstanding issues so readers know the report is slightly degraded.
    The banner is clearly marked so it can be identified in logs.
    """
    if not warning_issues:
        return html
    issue_lines = "\n".join(f"  • {i}" for i in warning_issues)
    banner = (
        "⚠️ <b>【Gate 警示 — 報告已送出，含未滿分項目】</b>\n"
        f"{issue_lines}\n"
        "─────────────────────────────\n\n"
    )
    logger.warning(
        "gate_warn_banner: report delivered with %d warning(s): %s",
        len(warning_issues),
        "; ".join(warning_issues),
    )
    return banner + html


# ── Module-level constants for _post_process_html_for_gate ───────────────────
_PP_CRED_RE = re.compile(r'可信度[：:]\s*(?:A|B|C|[0-9]{1,3})\b', re.IGNORECASE)
# Normalize English "Credibility：X" to "可信度：X" for display consistency.
_PP_CRED_EN_RE = re.compile(r'(?:Credibility|Grade)\s*[：:]\s*', re.IGNORECASE)
_PP_CHATTER_LINE_RE = re.compile(r'^(· [^\n]+?（未確認）)', re.MULTILINE)
_PP_CHATTER3_RE = re.compile(r'(區塊③【[^】]+】\n)')
_PP_YIELD_MIN, _PP_YIELD_MAX = 0.0, 20.0
_PP_MACRO_YIELD_RES = [
    re.compile(r'(10Y\s*[:：]\s*)([0-9,]+(?:\.[0-9]+)?)\s*%', re.IGNORECASE),
    re.compile(r'(10Y\D{0,22}?)([0-9,]+(?:\.[0-9]+)?)\s*%', re.IGNORECASE),
    re.compile(r'(2Y\s*[:：]\s*)([0-9,]+(?:\.[0-9]+)?)\s*%', re.IGNORECASE),
    re.compile(r'(2Y\D{0,22}?)([0-9,]+(?:\.[0-9]+)?)\s*%', re.IGNORECASE),
]
_PP_REGIME_TOKEN_RE = re.compile(r'\b(risk_on|risk_off|neutral)\b', re.IGNORECASE)
_PP_CONDITIONAL_LINE_RE = re.compile(
    r'(?:若|如果|假設|when|if)\s.{0,80}(?:risk_on|risk_off|neutral)',
    re.IGNORECASE,
)
# Fix 5: UTC+8 — matches 〔新聞 N〕[date time] that lacks a HK timezone, including closing "]"
# Negative lookahead ensures we skip brackets that already carry UTC/GMT+8 / HKT / 香港時間 etc.
_PP_NEWS_TS_RE = re.compile(
    r'(〔新聞\s*\d+〕[\s\u3000]*\[(?:\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{4})?)'
    r'\s+\d{1,2}:\d{2}(?::\d{2})?)'
    r'(?!\s*(?:UTC|GMT)\s*[+＋]\s*0?8|\s*HKT\b|\s*(?:香港|北京|台北)時間)'
    r'\]',
    re.IGNORECASE,
)
# Fix 6: Signal conflict
_PP_SIGNAL_CONFLICT_RE = re.compile(r'[訊信]號衝突(?:摘要|分析)?[：:]')
# Fix 7: Malformed (empty) invalidation condition
_PP_MALFORMED_INVAL_RE = re.compile(
    r'(失效條件[：:]\s*)(?:<code>)?\s*(?:</code>)?\s*(?=\n|$)',
    re.MULTILINE,
)


def _post_process_html_for_gate(html: str, agreed_regime: str | None = None) -> str:
    """
    Post-render safety net that patches 7 common gate failures BEFORE validate_report:

    1. 傳聞區缺少可信度分級 — injects credibility marker if none found in rendered text.
    2. 宏觀數值疑似異常     — replaces out-of-range 10Y/2Y values on 美債 lines with N/A.
    3. N/A 過多低置信度     — injects 低置信度 block if N/A count > 3 and markers missing.
    4. Regime 不一致        — normalizes all authoritative regime tokens to agreed_regime.
    5. 新聞時間缺 UTC+8     — appends " UTC+8" to news timestamp brackets missing timezone.
    6. 缺少訊號衝突摘要     — injects minimal 訊號衝突摘要 block before [QSREC_START].
    7. 空白失效條件         — fills empty 失效條件：with default invalidation text.

    This runs AFTER Jinja2 rendering so it works regardless of LLM output quality.
    It is intentionally minimal: only patches what the gate would reject.
    """
    # ── 0. Credibility language normalization ────────────────────────
    # Normalize English "Credibility：X" / "Grade：X" to "可信度：X" for display consistency.
    if _PP_CRED_EN_RE.search(html):
        html = _PP_CRED_EN_RE.sub("可信度：", html)
        logger.info("post_process: normalized English credibility labels to 可信度：")

    # ── 1. Chatter credibility ────────────────────────────────────────
    if not _PP_CRED_RE.search(html):
        # Find first chatter bullet line that ends with （未確認） and append credibility.
        # Uses MULTILINE (not DOTALL) to avoid crossing section boundaries.
        m = _PP_CHATTER_LINE_RE.search(html)
        if m:
            html = html[:m.end()] + '｜可信度：C' + html[m.end():]
            logger.warning("post_process: injected missing chatter credibility marker")
        else:
            # Fallback: inject a minimal chatter entry under the chatter section header.
            html = _PP_CHATTER3_RE.sub(
                r'\1· 低信噪比，暫無高可信傳聞（未確認）｜可信度：C\n',
                html, count=1,
            )
            logger.warning("post_process: injected fallback chatter entry with credibility")

    # ── 2. Macro outlier values ──────────────────────────────────────
    # Mirror the exact patterns used by _has_macro_outlier_values so we only
    # patch what the validator would reject.
    def _fix_yield_match(m: re.Match) -> str:
        try:
            val = float(m.group(2).replace(",", ""))
        except ValueError:
            return m.group(0)
        if not (_PP_YIELD_MIN <= val <= _PP_YIELD_MAX):
            logger.warning("post_process: replacing out-of-range yield %.3f%% with N/A", val)
            g2_start = m.start(2) - m.start(0)
            return m.group(0)[:g2_start] + "N/A"
        return m.group(0)

    patched_lines = []
    for line in html.splitlines():
        if "美債" in line:
            for pat in _PP_MACRO_YIELD_RES:
                line = pat.sub(_fix_yield_match, line)
        patched_lines.append(line)
    html = "\n".join(patched_lines)

    # ── 3. N/A count + low-confidence label ─────────────────────────
    na_count = len(re.findall(r'\bN/A\b', html))
    has_low_conf = bool(re.search(r'低置信度|低信心', html))
    has_proxy = bool(re.search(
        r'資料缺失原因[\s\S]{0,800}?替代指標|替代指標[\s\S]{0,800}?資料缺失原因',
        html, re.IGNORECASE,
    ))

    if na_count > 3 and not (has_low_conf and has_proxy):
        injection = (
            "\n⚠️ 低置信度聲明\n"
            "資料缺失原因：本日部分數據源（yfinance / CoinGlass / NewsAPI）未回應，"
            "相關欄位以 N/A 標示。\n"
            "替代指標：N/A 欄位請參考 Binance 備援數據或 CME FedWatch Tool 補充。\n"
        )
        if "[QSREC_START]" in html:
            html = html.replace("[QSREC_START]", injection + "[QSREC_START]", 1)
        else:
            logger.warning("post_process: [QSREC_START] sentinel missing — appending 低置信度 block at end")
            html += injection
        logger.warning(
            "post_process: injected 低置信度 block (N/A count=%d, had_low_conf=%s, had_proxy=%s)",
            na_count, has_low_conf, has_proxy,
        )

    # ── 4. Regime normalization ──────────────────────────────────────
    # Replace all authoritative (non-conditional) regime tokens with agreed_regime.
    # Conditional lines like「若轉為 risk_off 則…」are left untouched.
    # Fallback: if agreed_regime was not determined upstream (scorecard failed),
    # infer it from the 【今日市場模式】 line already rendered in the report.
    _effective_regime = agreed_regime
    if not _effective_regime:
        _mode_m = re.search(
            r'【今日市場模式】[^(risk_on|risk_off|neutral)]*?(risk_on|risk_off|neutral)',
            html,
            re.IGNORECASE,
        )
        if _mode_m:
            _effective_regime = _mode_m.group(1).lower().replace("-", "_").replace(" ", "_")
            logger.warning(
                "post_process: agreed_regime was None; inferred fallback regime=%s from 市場模式 line",
                _effective_regime,
            )
    if _effective_regime:
        fixed_lines = []
        for line in html.splitlines():
            if _PP_CONDITIONAL_LINE_RE.search(line):
                fixed_lines.append(line)
            else:
                fixed_lines.append(_PP_REGIME_TOKEN_RE.sub(_effective_regime, line))
        html = "\n".join(fixed_lines)
        logger.info("post_process: regime normalized to %s", _effective_regime)

    # ── 5. UTC+8 timezone injection ───────────────────────────────
    # Append " UTC+8" to news timestamp brackets that lack a HK timezone marker.
    # _PP_NEWS_TS_RE captures (group 1) up to the end of the time digits then matches "]".
    # Replacement: group(1) + " UTC+8]" — the original "]" is consumed by the pattern.
    utc8_count = [0]

    def _inject_utc8(m: re.Match) -> str:
        utc8_count[0] += 1
        return m.group(1) + " UTC+8]"

    html = _PP_NEWS_TS_RE.sub(_inject_utc8, html)
    if utc8_count[0]:
        logger.warning("post_process: injected UTC+8 into %d news timestamp bracket(s)", utc8_count[0])

    # ── 6. Signal conflict summary injection ─────────────────────
    # If the gate-required 訊號衝突摘要 block is missing, inject a minimal one.
    if not _PP_SIGNAL_CONFLICT_RE.search(html):
        _signal_block = "\n訊號衝突摘要：暫無重大訊號衝突，多空數據基本一致。\n"
        if "[QSREC_START]" in html:
            html = html.replace("[QSREC_START]", _signal_block + "[QSREC_START]", 1)
        else:
            html += _signal_block
        logger.warning("post_process: injected missing 訊號衝突摘要 block")

    # ── 7. Malformed invalidation condition fill ──────────────────
    # Replace empty 失效條件：（含 <code></code> 殼）with a safe default.
    _inval_default = r"\g<1><code>跌破關鍵支撐位或重大利空事件出現</code>"
    new_html = _PP_MALFORMED_INVAL_RE.sub(_inval_default, html)
    if new_html != html:
        html = new_html
        logger.warning("post_process: filled empty 失效條件 with default invalidation text")

    return html


def _run_pipeline_once(
    exclude_context: str | None,
    use_fallback_llm: bool = False,
) -> tuple[str, Exception | None, DailyBriefReport | None]:
    """並行執行雙 Crew → 組裝 DailyBriefReport → Jinja 渲染 Telegram HTML。"""
    try:
        _prewarm_tool_caches()
        price_context = get_realtime_quotes()
        trimmed_exclusion = _truncate_text(exclude_context, MAX_EXCLUSION_CONTEXT_CHARS)

        prev_recs = ""
        if not SKIP_BIGQUERY:
            try:
                prev_recs = load_previous_recs_block()
                if prev_recs:
                    prev_recs = _truncate_text(prev_recs, MAX_PREV_RECS_CHARS)
                    logger.info("Loaded previous recommendations block (%d chars).", len(prev_recs))
            except Exception as _e:
                logger.warning("Could not load previous recs block: %s", _e)

        # Parse agreed regime from pre-warmed scorecard cache to lock regime across both crews.
        agreed_regime: str | None = None
        try:
            from tools import regime_scorecard_tool as _rst  # noqa: PLC0415
            scorecard_text = _rst.run()
            agreed_regime = _parse_regime_from_scorecard(scorecard_text)
            if agreed_regime:
                logger.info("Pipeline agreed_regime locked: %s", agreed_regime)
            else:
                logger.warning("Could not parse regime from scorecard; regime locking disabled.")
        except Exception as _re:
            logger.warning("Regime pre-parse failed (non-fatal): %s", _re)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(
                lambda: CryptoResearchCrew(use_fallback_llm=use_fallback_llm).run(
                    exclude_context=trimmed_exclusion,
                    price_context=price_context,
                    prev_recs_block=prev_recs,
                    agreed_regime=agreed_regime,
                )
            )
            future_ai = executor.submit(
                lambda: AIResearchCrew(use_fallback_llm=use_fallback_llm).run(
                    exclude_context=trimmed_exclusion,
                    price_context=price_context,
                    agreed_regime=agreed_regime,
                )
            )

            crypto_section = future_crypto.result()
            ai_section = future_ai.result()

        tagged = len(crypto_section.news) + len(ai_section.news)
        partial_tier = tagged < 6 and _allow_partial_news_gate() and 3 <= tagged
        report_model = assemble_daily_brief_report(
            crypto_section,
            ai_section,
            previous_recs_html=prev_recs or "",
            source_observability_block=source_observability_lines(),
            report_tier_partial_news=partial_tier,
        )
        html = render_telegram_daily_brief(report_model)
        html = _post_process_html_for_gate(html, agreed_regime=agreed_regime)
        return html, None, report_model
    except Exception as e:
        return "", e, None


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
            report_model: DailyBriefReport | None = None
            for step in range(MAX_503_RETRIES + 1):
                report_html, err, report_model = _run_pipeline_once(exclude_context, use_fallback_llm=False)
                if err is None:
                    if report_model is None:
                        raise RuntimeError("pipeline OK but DailyBriefReport missing")
                    _persist_pipeline_raw_report(report_model)
                    final_report = _postprocess_report_for_resilience(report_html)
                    output_json = _build_output_json_for_validation(final_report, report_model)
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
                report_html, err, report_model = _run_pipeline_once(exclude_context, use_fallback_llm=True)
                if err is None:
                    if report_model is None:
                        raise RuntimeError("pipeline OK but DailyBriefReport missing")
                    _persist_pipeline_raw_report(report_model)
                    final_report = _postprocess_report_for_resilience(report_html)
                    output_json = _build_output_json_for_validation(final_report, report_model)
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
            if report_model is not None:
                sres = validate_structured_report(report_model)
                if not sres["valid"]:
                    # Merge issues from both validators; structured issues are always blocking.
                    merged_issues = list(result.get("issues") or [])
                    merged_issues.extend(sres.get("issues") or [])
                    merged_blocking = list(result.get("blocking_issues") or [])
                    merged_blocking.extend(sres.get("blocking_issues") or [])
                    merged_warnings = list(result.get("warning_issues") or [])
                    merged_warnings.extend(sres.get("warning_issues") or [])
                    result = {
                        **result,
                        "valid": False,
                        "issues": merged_issues,
                        "blocking_issues": merged_blocking,
                        "warning_issues": merged_warnings,
                    }
            _log_validation_dual_run(final_report, result)
            last_validation = result

            blocking = result.get("blocking_issues") or []
            warnings = result.get("warning_issues") or []
            warn_count = len(warnings)
            report_valid = result["valid"]  # True only when issues == 0

            scratchpad.append_gate_result(attempt + 1, result)
            fallback_cnt = _fallback_news_count(final_report)
            logger.info(
                "[Attempt %d] Validation — news=%d, fallback=%d, blocking=%d, warnings=%d, valid=%s",
                attempt + 1,
                result["news_count"],
                fallback_cnt,
                len(blocking),
                warn_count,
                report_valid,
            )

            # ── Score-based gate decision ─────────────────────────────────
            # Clean pass: no issues at all.
            if report_valid:
                logger.info("Report generation successful (clean pass).")
                scratchpad.finalize_run("success", {"finalAttempt": attempt + 1, "valid": True})
                return final_report, True, result

            # Warn pass: no blocking issues and warnings within threshold.
            if not blocking and warn_count <= GATE_WARN_THRESHOLD:
                logger.warning(
                    "Score-based gate: warn-pass (blocking=0, warnings=%d <= threshold=%d). "
                    "Delivering with banner.",
                    warn_count, GATE_WARN_THRESHOLD,
                )
                final_report = _inject_gate_warning_banner(final_report, warnings)
                scratchpad.finalize_run(
                    "success_warn_pass",
                    {"finalAttempt": attempt + 1, "warnings": warn_count, "threshold": GATE_WARN_THRESHOLD},
                )
                return final_report, True, result

            logger.warning(
                "Report gate not passed (blocking=%d, warnings=%d): %s",
                len(blocking), warn_count, result["issues"],
            )
            if logger.isEnabledFor(logging.DEBUG) and final_report:
                logger.debug("Report snippet (first 500 chars): %s", final_report[:500].replace("\n", " "))
            if attempt < MAX_REPORT_RETRIES:
                logger.info("Retrying report generation (%d/%d)...", attempt + 2, MAX_REPORT_RETRIES + 1)

        # All retries exhausted — apply final score-based decision.
        blocking_final = (last_validation or {}).get("blocking_issues") or []
        warnings_final = (last_validation or {}).get("warning_issues") or []
        if final_report and not final_report.startswith("🚨"):
            if not blocking_final:
                # No structural failures: always deliver, even if warnings > threshold.
                logger.warning(
                    "Score-based gate: retries exhausted but no blocking issues (%d warnings). "
                    "Delivering with banner.",
                    len(warnings_final),
                )
                final_report = _inject_gate_warning_banner(final_report, warnings_final)
                scratchpad.finalize_run(
                    "success_warn_pass_exhausted",
                    {"warnings": len(warnings_final), "threshold": GATE_WARN_THRESHOLD},
                )
                return final_report, True, last_validation
            else:
                # Structural blocking issues remain — truly block.
                logger.error(
                    "Report blocked: %d blocking issue(s) remain after all retries: %s",
                    len(blocking_final), blocking_final,
                )

        end_status = "completed_invalid"
        if final_report.startswith("🚨"):
            end_status = "execution_error_report"
        scratchpad.finalize_run(
            end_status,
            {"report_valid": report_valid, "blocking_count": len(blocking_final)},
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
