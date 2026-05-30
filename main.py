import os
import re
import sys
import time
import json
import logging
import builtins
from datetime import datetime, timezone
from dotenv import load_dotenv
import yfinance as yf
from pathlib import Path

from crew import AIResearchCrew, CryptoResearchCrew
from brief_profiles import get_active_profile
from report_html_postprocess import post_process_html_for_gate
from report_render import assemble_daily_brief_report, render_telegram_daily_brief
from schemas import (
    DailyBriefReport,
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
    write_daily_brief_json,
    write_gate_failure_log,
    write_llm_run_log,
)
from report_judge import (
    hard_pattern_judge_pass,
    hard_pattern_judge_reason,
    llm_judge_should_block,
    llm_quality_judge,
    domain_quality_check,
)
from report_quality_agent import (
    maybe_run_report_quality_agent_after_success,
    quality_agent_summary_for_scratchpad,
)
from report_html_gates import (
    validate_report,
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
    format_gate_feedback_for_llm,
)
from crew import _parse_regime_from_scorecard
from tools import source_observability_lines
from visualizer import generate_quant_chart
import tracker
import scratchpad
from tracker import get_recent_lessons, load_previous_recs_block
from report_pipeline_compare import compare_validation_results
from config import USE_LANGGRAPH_ENGINE

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
BACKOFF_BASE_SEC = int(os.getenv("BACKOFF_BASE_SEC", "25"))
ERROR_PREFIX = "🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息："
MAX_EXCLUSION_CONTEXT_CHARS = int(os.getenv("MAX_EXCLUSION_CONTEXT_CHARS", "1000"))
MAX_PREV_RECS_CHARS = int(os.getenv("MAX_PREV_RECS_CHARS", "1200"))
# 雙 Crew 並行時，單軌 wall-clock 上限（較慢的軌決定總等待）。預設 40min：避免慢 LLM／多工具日誤觸發 TimeoutError。
# Cloud Run Job 已預設 4h task timeout；此值應小於 (PIPELINE_HARD_DEADLINE / 預期嘗試次數)。
CREW_FUTURE_TIMEOUT_SEC = int(os.getenv("CREW_FUTURE_TIMEOUT_SEC", "2400"))
# 整段產報（含 validate 重試、503 退避）的牆鐘預算；達上限後不再開新一趟 kickoff。預設對齊 4h Cloud Run 留 ~20min 緩衝。
PIPELINE_HARD_DEADLINE_SEC = int(os.getenv("PIPELINE_HARD_DEADLINE_SEC", "13200"))
SHADOW_BENCHMARK_LOG = os.getenv("SHADOW_BENCHMARK_LOG", "").lower() in ("1", "true", "yes")
SHADOW_BENCHMARK_PATH = os.getenv(
    "SHADOW_BENCHMARK_PATH",
    ".qsilicon/crew_shadow_benchmark.jsonl",
)

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
    # Reader-facing typo scrubs (LLM duplicates)
    text = text.replace("美國政府政府", "美國政府")
    return sanitize_telegram_html(text)


def _daily_brief_report_date(report: DailyBriefReport) -> str:
    raw = str(getattr(report.crypto, "report_title_date", "") or "").strip()
    m = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    if m:
        return m.group(0)
    from datetime import timedelta

    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d")


def _persist_pipeline_raw_report(report: DailyBriefReport | None) -> None:
    """Persist the assembled DailyBriefReport JSON for API/PWA parity and debugging."""
    if report is None:
        return
    try:
        from datetime import datetime, timedelta, timezone

        tz = timezone(timedelta(hours=8))
        run_id = datetime.now(tz).strftime("run_%Y%m%d_%H%M%S")
        payload_json = report.model_dump_json(indent=2)
        d = Path("logs") / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "raw_data.json").write_text(
            payload_json,
            encoding="utf-8",
        )
        logger.info("Wrote structured raw report to %s", d / "raw_data.json")

        report_date = _daily_brief_report_date(report)
        json_dir = Path(os.getenv("DAILY_BRIEF_JSON_DIR") or ".qsilicon/daily_brief_reports")
        json_dir.mkdir(parents=True, exist_ok=True)
        daily_path = json_dir / f"{report_date}.json"
        daily_path.write_text(payload_json, encoding="utf-8")
        logger.info("Wrote DailyBriefReport JSON to %s", daily_path)

        write_daily_brief_json(
            report_date=report_date,
            profile=get_active_profile(),
            payload_json=payload_json,
            run_id=run_id,
            source="pipeline",
        )
    except OSError as e:
        logger.warning("DailyBriefReport JSON write failed: %s", e)


def _log_shadow_benchmark(stage: str, payload: dict) -> None:
    """Append lightweight shadow/runtime metrics for optional benchmark analysis."""
    if not SHADOW_BENCHMARK_LOG:
        return
    try:
        rec = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "stage": stage,
            **payload,
        }
        path = Path(SHADOW_BENCHMARK_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.warning("shadow benchmark write failed: %s", e)


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
    硬規則快速審核（原 Codex 關鍵詞 gate）；詳見 report_judge.hard_pattern_judge_pass。
    """
    return hard_pattern_judge_pass(report_text)


def _validate_pipeline_output(
    report_html: str,
    report_model: DailyBriefReport,
) -> tuple[str, Exception | None]:
    """Post-process rendered HTML and run structural + codex validation.

    Extracted to deduplicate the identical check in both the primary-LLM path
    and the fallback-LLM path inside run_pipeline_with_retries.

    Returns:
        (final_report, structural_validation_err)
        structural_validation_err is None when all checks pass.
    """
    final_report = _postprocess_report_for_resilience(report_html)
    output_json = _build_output_json_for_validation(final_report, report_model)
    structural_validation_err: Exception | None = None
    try:
        parsed = parse_report_output(output_json)
        assert_report_output(parsed)
        assert_sample_output(output_json)
        if not hard_pattern_judge_pass(final_report):
            hint = hard_pattern_judge_reason(final_report) or "pattern_match"
            raise AssertionError(f"Hard pattern judge 未通過（{hint}）")
        if os.getenv("REPORT_LLM_JUDGE", "").lower() in ("1", "true", "yes"):
            jres = llm_quality_judge(final_report)
            scratchpad.append_judge_result(jres)
            if llm_judge_should_block(jres):
                raise AssertionError(
                    f"LLM judge 阻擋：score={jres.get('overall_score')} "
                    f"reasons={jres.get('reasons')}"
                )
    except Exception as v_err:  # noqa: BLE001
        structural_validation_err = v_err
    return final_report, structural_validation_err


def _report_compare_mode() -> bool:
    """Phase 3：雙軌驗證比對（僅 log，不切 Telegram / BQ 決策）。"""
    return os.getenv("REPORT_COMPARE_MODE", "").lower() in ("1", "true", "yes")


def _validate_report_candidate(text: str) -> dict:
    """
    Phase 3 候選驗證路徑。

    實作：延遲 import `report_html_gates.validate_report`，避免載入循環。
    目前與 `validate_report` 等價；日後可改為獨立實作並以 REPORT_COMPARE_MODE 觀測差異。
    """
    from report_html_gates import validate_report as _vr

    return _vr(text, profile=get_active_profile())


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
        financial_datasets_tool,
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
        "financial_datasets":     lambda: financial_datasets_tool.run("watchlist"),
    }
    if os.getenv("PREDICTION_MARKETS_IN_BRIEF", "").strip().lower() in ("1", "true", "yes"):
        from tools import prediction_markets_tool  # noqa: PLC0415

        tasks["prediction_markets"] = lambda: prediction_markets_tool.run()

    logger.info("Pre-warming %d tool caches in parallel...", len(tasks))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
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


def _run_pipeline_once(
    exclude_context: str | None,
    use_fallback_llm: bool = False,
) -> tuple[str, Exception | None, DailyBriefReport | None]:
    """並行執行雙 Crew → 組裝 DailyBriefReport → Jinja 渲染 Telegram HTML。"""
    try:
        _prewarm_tool_caches()
        price_context = get_realtime_quotes()
        trimmed_exclusion = _truncate_text(exclude_context, MAX_EXCLUSION_CONTEXT_CHARS)
        _pipe_rd = os.getenv("PIPELINE_REPORT_DATE", "").strip()
        if _pipe_rd:
            trimmed_exclusion = (
                f"【錨定報告日】{_pipe_rd}（新聞回溯與 STRICT_NEWS_FRESHNESS 機檢以此日 23:59 HKT 為參考；"
                "非實時時鐘。）\n\n" + (trimmed_exclusion or "")
            ).strip()

        try:
            from earnings_focus import maybe_prepend_earnings_focus_exclusion

            trimmed_exclusion = maybe_prepend_earnings_focus_exclusion(trimmed_exclusion) or ""
            trimmed_exclusion = _truncate_text(trimmed_exclusion, MAX_EXCLUSION_CONTEXT_CHARS)
        except Exception as _ef_err:
            logger.warning("Earnings focus injection skipped: %s", _ef_err)

        try:
            from tools import tech_pulse_tool as _tpt  # noqa: PLC0415

            tp_block = _tpt.fetch_tech_pulse_exclusion_snippet()
            if (tp_block or "").strip():
                trimmed_exclusion = (
                    (trimmed_exclusion or "").strip()
                    + "\n\n【Tech pulse（external）】\n"
                    + tp_block.strip()
                ).strip()
                trimmed_exclusion = _truncate_text(trimmed_exclusion, MAX_EXCLUSION_CONTEXT_CHARS)
        except Exception as _tp_err:
            logger.warning("Tech pulse exclusion injection skipped: %s", _tp_err)

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

        try:
            _reflect_days = int(os.getenv("REFLECTION_LOOKBACK_DAYS", "3") or "3")
        except ValueError:
            _reflect_days = 3
        _reflect_days = max(1, min(_reflect_days, 90))
        lessons_str = get_recent_lessons(_reflect_days)
        if not (lessons_str or "").strip():
            lessons_str = (
                "[系統反思記憶] 近期無停損紀錄，請維持客觀的風險控管。"
            )
        logger.info(
            "Injected recent_lessons for crew (%d chars, days=%d, json_payload=%s).",
            len(lessons_str),
            _reflect_days,
            str(lessons_str).lstrip().startswith("{"),
        )

        from concurrent.futures import ThreadPoolExecutor

        if USE_LANGGRAPH_ENGINE:
            logger.info("USE_LANGGRAPH_ENGINE=1, running LangGraph shadow engine.")
            from graph.graph_crew import run_langgraph_category  # noqa: PLC0415

            _engine_t0 = time.monotonic()
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_crypto = executor.submit(
                    lambda: run_langgraph_category(
                        category="CRYPTO",
                        exclude_context=trimmed_exclusion or "",
                        price_context=price_context,
                        prev_recs_block=prev_recs,
                        agreed_regime=agreed_regime,
                        recent_lessons=lessons_str,
                        use_fallback_llm=use_fallback_llm,
                    )
                )
                future_ai = executor.submit(
                    lambda: run_langgraph_category(
                        category="AI",
                        exclude_context=trimmed_exclusion or "",
                        price_context=price_context,
                        prev_recs_block=prev_recs,
                        agreed_regime=agreed_regime,
                        recent_lessons=lessons_str,
                        use_fallback_llm=use_fallback_llm,
                    )
                )
                crypto_section = future_crypto.result(timeout=CREW_FUTURE_TIMEOUT_SEC)
                ai_section = future_ai.result(timeout=CREW_FUTURE_TIMEOUT_SEC)
            _log_shadow_benchmark(
                "langgraph_dual_crew",
                {
                    "elapsed_sec": round(time.monotonic() - _engine_t0, 3),
                    "timeout_sec": CREW_FUTURE_TIMEOUT_SEC,
                    "news_count_total": len(crypto_section.news) + len(ai_section.news),
                },
            )
        else:
            _engine_t0 = time.monotonic()
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_crypto = executor.submit(
                    lambda: CryptoResearchCrew(use_fallback_llm=use_fallback_llm).run(
                        exclude_context=trimmed_exclusion,
                        price_context=price_context,
                        prev_recs_block=prev_recs,
                        agreed_regime=agreed_regime,
                        recent_lessons=lessons_str,
                    )
                )
                future_ai = executor.submit(
                    lambda: AIResearchCrew(use_fallback_llm=use_fallback_llm).run(
                        exclude_context=trimmed_exclusion,
                        price_context=price_context,
                        prev_recs_block=prev_recs,
                        agreed_regime=agreed_regime,
                        recent_lessons=lessons_str,
                    )
                )
                crypto_section = future_crypto.result(timeout=CREW_FUTURE_TIMEOUT_SEC)
                ai_section = future_ai.result(timeout=CREW_FUTURE_TIMEOUT_SEC)
            _log_shadow_benchmark(
                "crewai_dual_crew",
                {
                    "elapsed_sec": round(time.monotonic() - _engine_t0, 3),
                    "timeout_sec": CREW_FUTURE_TIMEOUT_SEC,
                    "news_count_total": len(crypto_section.news) + len(ai_section.news),
                },
            )

        try:
            _min_tc = int(os.getenv("MIN_TOOL_CALLS_PER_PIPELINE", "0") or "0")
        except ValueError:
            _min_tc = 0
        if _min_tc > 0:
            _n_tools = scratchpad.raw_tool_invocation_count()
            if _n_tools < _min_tc:
                raise RuntimeError(
                    f"MIN_TOOL_CALLS_PER_PIPELINE={_min_tc} 但本輪僅 {_n_tools} 次工具呼叫"
                    "（經 traced_tool_execution 計數）。"
                )

        try:
            _min_crew = int(os.getenv("MIN_TOOL_CALLS_PER_CREW", "0") or "0")
        except ValueError:
            _min_crew = 0
        if _min_crew > 0:
            _nc = scratchpad.raw_tool_invocation_count_crypto()
            _na = scratchpad.raw_tool_invocation_count_ai()
            if _nc < _min_crew or _na < _min_crew:
                raise RuntimeError(
                    f"MIN_TOOL_CALLS_PER_CREW={_min_crew} 但本輪 crypto={_nc}、ai={_na} "
                    "（僅統計 crew.kickoff 階段、scratchpad.set_tool_invocation_lane 標記之 traced 呼叫）。"
                )

        tagged = len(crypto_section.news) + len(ai_section.news)
        partial_tier = tagged < 6 and _allow_partial_news_gate() and 3 <= tagged
        _rt = None
        _so = ""
        if os.getenv("BRIEF_CURRENT_AFFAIRS", "").strip().lower() in ("1", "true", "yes"):
            from current_affairs_crew import run_current_affairs_roundtable_task

            with ThreadPoolExecutor(max_workers=2) as _pool2:
                fut_so = _pool2.submit(source_observability_lines)
                fut_ca = _pool2.submit(
                    run_current_affairs_roundtable_task,
                    crypto=crypto_section,
                    ai=ai_section,
                )
                try:
                    _raw_so = fut_so.result(timeout=120)
                    _so = (_raw_so or "").strip()
                except Exception as _soe:
                    logger.warning("source_observability_lines failed: %s", _soe)
                    _so = ""
                try:
                    _rt = fut_ca.result(timeout=CREW_FUTURE_TIMEOUT_SEC)
                except Exception as _cae:
                    logger.warning("current_affairs_roundtable optional crew failed: %s", _cae)
                    _rt = None
        else:
            _so = (source_observability_lines() or "").strip()
        if _so:
            logger.info("Source observability (not in Telegram body):\n%s", _so)
        if _rt is None and os.getenv("BRIEF_CURRENT_AFFAIRS_JSON", "").strip():
            try:
                from schemas import CurrentAffairsRoundtable as _CAR

                _rt = _CAR.model_validate_json(os.environ["BRIEF_CURRENT_AFFAIRS_JSON"])
            except Exception as _je:
                logger.warning("BRIEF_CURRENT_AFFAIRS_JSON parse failed: %s", _je)
                _rt = None
        report_model = assemble_daily_brief_report(
            crypto_section,
            ai_section,
            previous_recs_html=prev_recs or "",
            source_observability_block=_so,
            report_tier_partial_news=partial_tier,
            agreed_regime=agreed_regime,
            current_affairs_roundtable=_rt,
            inject_earnings_radar=True,
        )
        html = render_telegram_daily_brief(report_model, profile=get_active_profile())
        html = post_process_html_for_gate(html, agreed_regime=agreed_regime)
        return html, None, report_model
    except Exception as e:
        return "", e, None


def _pipeline_config_snapshot_for_scratchpad() -> dict:
    """非機密啟動組態摘要（供 scratchpad init／LG-1 觀測）；失敗時降級為空欄位。"""
    snap: dict = {
        "PIPELINE_STRICT_ENV": (os.getenv("PIPELINE_STRICT_ENV") or "").strip()[:16],
        "STRICT_PICK_ROTATION": (os.getenv("STRICT_PICK_ROTATION") or "").strip()[:16],
        "ADAPTIVE_GATE_THRESHOLDS": (os.getenv("ADAPTIVE_GATE_THRESHOLDS") or "").strip()[:16],
        "ADAPTIVE_GATE_BQ_READ": (os.getenv("ADAPTIVE_GATE_BQ_READ") or "").strip()[:16],
        "GRAPH_DEEP_RESEARCH_TOOL_LLM": (os.getenv("GRAPH_DEEP_RESEARCH_TOOL_LLM") or "").strip()[:16],
        "GRAPH_ENABLE_TOOL_CALLS": (os.getenv("GRAPH_ENABLE_TOOL_CALLS") or "").strip()[:16],
        "USE_LANGGRAPH_ENGINE": (os.getenv("USE_LANGGRAPH_ENGINE") or "").strip()[:16],
        "WEB_PUSH_ENABLED": (os.getenv("WEB_PUSH_ENABLED") or "").strip()[:16],
        "WEB_PUSH_STORE": (os.getenv("WEB_PUSH_STORE") or "").strip()[:16],
        "BRIEF_CURRENT_AFFAIRS": (os.getenv("BRIEF_CURRENT_AFFAIRS") or "").strip()[:8],
        "BRIEF_DYNAMIC_RENDER": (os.getenv("BRIEF_DYNAMIC_RENDER") or "").strip()[:8],
    }
    try:
        from adaptive_gate_thresholds import effective_pick_rotation_override_min_gap

        snap["effective_pick_rotation_override_min_gap"] = float(
            effective_pick_rotation_override_min_gap()
        )
    except Exception:
        snap["effective_pick_rotation_override_min_gap"] = None
    return snap


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
            "pipeline_config": _pipeline_config_snapshot_for_scratchpad(),
        }
    )
    final_report = ""
    report_valid = False
    last_validation: dict | None = None
    # LLM run tracking — populated as the pipeline runs, written to BQ at the end.
    _used_fallback = False
    _total_retries = 0
    _pipeline_start = time.monotonic()
    # Gate feedback accumulated across retries — injected into exclude_context so the
    # crew knows exactly what to fix without re-reading raw gate issues.
    _gate_feedback: str = ""

    def _budget_ok() -> bool:
        """True 當剩餘時間足夠再跑一次完整的 crew kickoff（加 2 分鐘緩衝）。"""
        elapsed = time.monotonic() - _pipeline_start
        remaining = PIPELINE_HARD_DEADLINE_SEC - elapsed
        return remaining >= CREW_FUTURE_TIMEOUT_SEC + 120

    try:
        for attempt in range(MAX_REPORT_RETRIES + 1):
            if not _budget_ok():
                logger.error(
                    "Pipeline wall-clock budget exhausted (elapsed=%.0fs / %ds) — aborting retries",
                    time.monotonic() - _pipeline_start, PIPELINE_HARD_DEADLINE_SEC,
                )
                break
            last_err: Exception | None = None
            structural_validation_err: Exception | None = None
            report_model: DailyBriefReport | None = None
            for step in range(MAX_503_RETRIES + 1):
                if not _budget_ok():
                    logger.error(
                        "Pipeline wall-clock budget exhausted mid-attempt (elapsed=%.0fs) — stopping 503 retries",
                        time.monotonic() - _pipeline_start,
                    )
                    break
                _context_with_feedback = (
                    f"{_gate_feedback}\n\n{exclude_context}".strip()
                    if _gate_feedback
                    else exclude_context
                )
                report_html, err, report_model = _run_pipeline_once(_context_with_feedback, use_fallback_llm=False)
                if err is None:
                    if report_model is None:
                        raise RuntimeError("pipeline OK but DailyBriefReport missing")
                    _persist_pipeline_raw_report(report_model)
                    final_report, structural_validation_err = _validate_pipeline_output(
                        report_html, report_model
                    )
                    if structural_validation_err:
                        logger.warning(
                            "輸出結構/內容驗證未通過（不佔 503 重試配額，交由報告驗證重試機制處理）：%s",
                            structural_validation_err,
                        )
                    break
                last_err = err
                if _is_retriable(err) and step < MAX_503_RETRIES:
                    _total_retries += 1
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
            if last_err is not None and _is_retriable(last_err) and _budget_ok():
                logger.warning("Primary LLM 失敗，改用 fallback LLM（全 GPT）重試一次：%s", last_err)
                _used_fallback = True
                _total_retries += 1
                report_html, err, report_model = _run_pipeline_once(_context_with_feedback, use_fallback_llm=True)
                if err is None:
                    if report_model is None:
                        raise RuntimeError("pipeline OK but DailyBriefReport missing")
                    _persist_pipeline_raw_report(report_model)
                    final_report, structural_validation_err = _validate_pipeline_output(
                        report_html, report_model
                    )
                    last_err = None
            if last_err is not None:
                break
            if structural_validation_err is not None:
                logger.info(
                    "[Attempt %d] 結構驗證未過，保留可讀報告交由 validate_report 決定是否重試：%s",
                    attempt + 1,
                    structural_validation_err,
                )

            result = validate_report(
                final_report,
                profile=get_active_profile(),
                structured_report=report_model,
            )
            # Structured business rules enforced at DailyBriefReport construction (schemas).
            _log_validation_dual_run(final_report, result)
            last_validation = result

            blocking = result.get("blocking_issues") or []
            warnings = result.get("warning_issues") or []
            warn_count = len(warnings)
            report_valid = result["valid"]  # True only when issues == 0

            scratchpad.append_gate_result(attempt + 1, result)
            if result.get("issues"):
                write_gate_failure_log(
                    attempt=attempt + 1,
                    validation=result,
                    report_chars=len(final_report or ""),
                    used_fallback=_used_fallback,
                    profile=result.get("profile"),
                )
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
                _qa = maybe_run_report_quality_agent_after_success(
                    final_report, gate_passed=True, validation_result=result
                )
                if _qa:
                    scratchpad.append_quality_agent_result(_qa)
                scratchpad.finalize_run(
                    "success",
                    {
                        "finalAttempt": attempt + 1,
                        "valid": True,
                        "quality_agent": quality_agent_summary_for_scratchpad(_qa),
                    },
                )
                return final_report, True, result

            # Warn pass: no blocking issues and warnings within threshold.
            if not blocking and warn_count <= GATE_WARN_THRESHOLD:
                logger.warning(
                    "Score-based gate: warn-pass (blocking=0, warnings=%d <= threshold=%d). "
                    "Delivering with banner.",
                    warn_count, GATE_WARN_THRESHOLD,
                )
                final_report = _inject_gate_warning_banner(final_report, warnings)
                _qa = maybe_run_report_quality_agent_after_success(
                    final_report, gate_passed=True, validation_result=result
                )
                if _qa:
                    scratchpad.append_quality_agent_result(_qa)
                scratchpad.finalize_run(
                    "success_warn_pass",
                    {
                        "finalAttempt": attempt + 1,
                        "warnings": warn_count,
                        "threshold": GATE_WARN_THRESHOLD,
                        "quality_agent": quality_agent_summary_for_scratchpad(_qa),
                    },
                )
                return final_report, True, result

            logger.warning(
                "Report gate not passed (blocking=%d, warnings=%d): %s",
                len(blocking), warn_count, result["issues"],
            )
            if logger.isEnabledFor(logging.DEBUG) and final_report:
                logger.debug("Report snippet (first 500 chars): %s", final_report[:500].replace("\n", " "))
            _gate_feedback = format_gate_feedback_for_llm(result)
            if _gate_feedback:
                logger.info("Gate feedback prepared for next retry (%d chars).", len(_gate_feedback))
            if attempt < MAX_REPORT_RETRIES:
                _total_retries += 1
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
                _qa = maybe_run_report_quality_agent_after_success(
                    final_report, gate_passed=True, validation_result=last_validation
                )
                if _qa:
                    scratchpad.append_quality_agent_result(_qa)
                scratchpad.finalize_run(
                    "success_warn_pass_exhausted",
                    {
                        "warnings": len(warnings_final),
                        "threshold": GATE_WARN_THRESHOLD,
                        "quality_agent": quality_agent_summary_for_scratchpad(_qa),
                    },
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
        # Write LLM run metadata to BigQuery for cost and reliability tracking.
        try:
            from config import MODEL_GROK, MODEL_GPT  # noqa: PLC0415
            _model = MODEL_GPT if _used_fallback else MODEL_GROK
            _gate_issues = list((last_validation or {}).get("issues") or [])
            write_llm_run_log(
                model_name=_model,
                used_fallback=_used_fallback,
                retry_count=_total_retries,
                gate_passed=report_valid,
                gate_issues=_gate_issues,
                profile=(last_validation or {}).get("profile"),
            )
        except Exception as _llm_log_err:
            logger.warning("LLM run log write failed (non-fatal): %s", _llm_log_err)


def _validate_report_profile_env() -> None:
    """Phase 4d: fail fast on invalid REPORT_PROFILE (avoid late ValueError after long crew run)."""
    try:
        get_active_profile()
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc


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
        # GCP credentials: either a service account key JSON path or ADC via workload identity.
        has_sa_key = bool(
            (os.getenv("GCP_SA_KEY") or "").strip()
            or (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or "").strip()
        )
        if not has_sa_key:
            logger.warning(
                "Neither GCP_SA_KEY nor GOOGLE_APPLICATION_CREDENTIALS is set; "
                "BigQuery writes will fail unless Application Default Credentials are configured. "
                "Set SKIP_BIGQUERY=1 to suppress this warning.",
            )


def _validate_critical_env_strict() -> None:
    """可選硬擋：PIPELINE_STRICT_ENV=1 時，未 SKIP 的路徑必須具備最小金鑰／設定（排程／生產建議）。"""
    if os.getenv("PIPELINE_STRICT_ENV", "").lower() not in ("1", "true", "yes"):
        return
    if not os.getenv("SKIP_TELEGRAM", "").strip():
        if not (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip() or not (
            os.getenv("TELEGRAM_CHAT_ID") or ""
        ).strip():
            raise RuntimeError(
                "PIPELINE_STRICT_ENV=1 且未設 SKIP_TELEGRAM：必須設定 TELEGRAM_BOT_TOKEN 與 TELEGRAM_CHAT_ID。"
            )
    if not os.getenv("SKIP_BIGQUERY", "").strip():
        if not (os.getenv("GCP_PROJECT_ID") or "").strip():
            raise RuntimeError(
                "PIPELINE_STRICT_ENV=1 且未設 SKIP_BIGQUERY：必須設定 GCP_PROJECT_ID。"
            )
        if not (os.getenv("GCP_SA_KEY") or "").strip() and not (
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or ""
        ).strip():
            raise RuntimeError(
                "PIPELINE_STRICT_ENV=1 且未設 SKIP_BIGQUERY：必須設定 GCP_SA_KEY 或 GOOGLE_APPLICATION_CREDENTIALS。"
            )


def _validate_env_types() -> None:
    """Validate numeric environment variables at startup to fail fast on typos."""
    numeric_vars = {
        "MAX_REPORT_RETRIES": "2",
        "MAX_503_RETRIES": "3",
        "BACKOFF_BASE_SEC": "25",
        "NEWSAPI_DAILY_CALL_LIMIT": "120",
        "GNEWS_DAILY_CALL_LIMIT": "120",
        "APIFY_DAILY_CALL_LIMIT": "30",
        "PICK_ROTATION_OVERRIDE_MIN_GAP": "12",
        "PICK_REPEAT_DAYS_MAX": "2",
        "PICK_REPEAT_MIN_SELECTION_SCORE": "75",
        "MAX_EXCLUSION_CONTEXT_CHARS": "1000",
        "MAX_PREV_RECS_CHARS": "1200",
        "NEWS_FRESHNESS_WINDOW_HOURS": "48",
        "CREW_FUTURE_TIMEOUT_SEC": "2400",
        "PIPELINE_HARD_DEADLINE_SEC": "13200",
        "ADAPTIVE_GATE_BQ_LOOKBACK_DAYS": "14",
        "ADAPTIVE_BQ_MIN_FAILURE_ROWS": "5",
        "ADAPTIVE_ROTATION_PREVIEW_FRACTION": "0.35",
        "ADAPTIVE_GATE_GAP_BUMP": "2",
        "ADAPTIVE_GATE_GAP_CEILING": "24",
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
                ("OPENROUTER_API_KEY", "OpenRouter"),
                ("FMP_API_KEY", "FMP"),
                ("FINANCIAL_DATASETS_API_KEY", "Financial Datasets"),
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
    _main_start = time.monotonic()
    _install_runtime_noise_filters()
    logger.info("Initializing Q-Silicon Ultimate Agent...")
    _validate_required_keys()
    _validate_report_profile_env()
    _validate_critical_env_strict()
    _validate_env_types()
    _log_api_key_inventory()
    _verify_optional_api_keys_light()
    generate_quant_chart("daily_chart.png")
    exclusion = fetch_exclusion_context()
    if exclusion:
        logger.info("Loaded exclusion context from previous report (to avoid duplicate news).")
    if os.getenv("COMPANY_CREW_ENABLED", "").lower() in ("1", "true", "yes"):
        try:
            from crew_company import run_growth_narrative_for_context

            _company_t0 = time.monotonic()
            growth_ctx = run_growth_narrative_for_context()
            _log_shadow_benchmark(
                "company_growth_context",
                {
                    "elapsed_sec": round(time.monotonic() - _company_t0, 3),
                    "enabled": True,
                    "chars": len(growth_ctx or ""),
                },
            )
            if growth_ctx:
                exclusion = f"{growth_ctx}\n\n{exclusion}" if exclusion else growth_ctx
                logger.info("Prepended Company Growth narrative to exclusion context.")
        except Exception as _co_err:
            logger.warning("Company crew block skipped: %s", _co_err)

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
            inv = (
                validation_result
                if validation_result is not None
                else validate_report(final_report, profile=get_active_profile())
            )
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
    _validation_clean = bool(validation_result and validation_result.get("valid") is True)
    _tracker_ok = bool(final_report and not final_report.startswith("🚨") and _validation_clean)
    if not SKIP_BIGQUERY and _tracker_ok:
        _saved = tracker.save_recommendations(final_report)
        if _saved:
            logger.info("Tracker: saved %d trade recommendations.", _saved)
        _closed = tracker.check_and_update_positions()
        if _closed:
            logger.info("Tracker: %d positions updated today: %s", len(_closed), _closed)
    elif not SKIP_BIGQUERY:
        # 即使報告未達 clean pass（含 warn-pass），仍每日回查已有的未平倉建議
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
            try:
                _dqc = domain_quality_check(clean_report)
                _elapsed = time.monotonic() - _main_start
                logger.info(
                    "Report quality (not sent to Telegram): Q-Score=%s elapsed=%.1fs detail=%s",
                    _dqc.get("overall"),
                    _elapsed,
                    _dqc,
                )
            except Exception as _qe:
                logger.warning("Quality check logging failed: %s", _qe)
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
