import os
import re
import time
import logging
import telebot
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE
from crew import CryptoResearchCrew, AIResearchCrew

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

# 重試常數（集中管理，方便調參）
MAX_REPORT_RETRIES = int(os.getenv("MAX_REPORT_RETRIES", "2"))
MAX_503_RETRIES = int(os.getenv("MAX_503_RETRIES", "3"))
BACKOFF_BASE_SEC = int(os.getenv("BACKOFF_BASE_SEC", "30"))
ERROR_PREFIX = "🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息："

# 除錯用環境變數：LOG_LEVEL=DEBUG | DEBUG=1 | CREW_VERBOSE=1（Agent 步驟）| SKIP_TELEGRAM=1 | SKIP_BIGQUERY=1

# Telegram HTML 支援的標籤白名單
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "blockquote"}


def sanitize_telegram_html(text: str) -> str:
    """清洗 LLM 輸出的 HTML，確保只保留 Telegram 支援的標籤。"""
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)

    def _fix_tag(m: re.Match) -> str:
        inner = m.group(1)
        tag_name = inner.lstrip('/').split()[0].lower()
        return m.group(0) if tag_name in _ALLOWED_TAGS else ''

    return re.sub(r'<(/?\w+(?:\s[^>]*)?)>', _fix_tag, text)


def strip_html(text: str) -> str:
    """完全移除所有 HTML 標籤，回傳純文字。"""
    return re.sub(r'<[^>]+>', '', text)


def _safe_float(m: re.Match | None, group: int = 1) -> float | None:
    """從 regex match 安全萃取 float，失敗回傳 None。"""
    if not m:
        return None
    try:
        return float(m.group(group))
    except (ValueError, IndexError):
        return None


def validate_report(text: str) -> dict:
    """驗證戰報是否包含足夠的新聞與推文，回傳驗證結果與詳細計數。"""
    news_count  = len(re.findall(r'〔新聞', text))
    tweet_count = len(re.findall(r'〔推文', text))
    has_regime  = bool(re.search(r'risk_on|risk_off|neutral', text, re.IGNORECASE))
    has_dashboard = bool(re.search(r'ICE\s*DXY|BTC\s*OI|OpenRouter|模型排名|模型熱度', text, re.IGNORECASE))

    issues = []
    if news_count < 12:
        issues.append(f"新聞數不足（{news_count}/12）")
    if tweet_count < 10:
        issues.append(f"推文數不足（{tweet_count}/10，每區塊各 5 則）")
    if not has_regime:
        issues.append("缺少 market_regime 標籤")
    if not has_dashboard:
        issues.append("缺少數據儀表板內容")

    return {
        "valid":       not issues,
        "issues":      issues,
        "news_count":  news_count,
        "tweet_count": tweet_count,
    }


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


def _safe_chunks(text: str, max_len: int = 4000) -> list[str]:
    """切分訊息且保證每塊不超過 max_len，盡量避免切斷 HTML 標籤。"""
    if not text:
        return [""]
    chunks: list[str] = []
    remaining = text
    while len(remaining) > max_len:
        cut = remaining.rfind("\n", 0, max_len + 1)
        if cut == -1:
            cut = remaining.rfind(" ", 0, max_len + 1)
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
        remaining = remaining[cut:]
    if remaining:
        chunks.append(remaining)
    return chunks


def _send_telegram_report(text: str, token: str, chat_id: str) -> None:
    """發送戰報至 Telegram，含重試與 fallback。"""
    from telebot import apihelper

    apihelper.SESSION_TIME_TO_LIVE = 5 * 60
    bot = telebot.TeleBot(token)
    cleaned = sanitize_telegram_html(text)
    for chunk in _safe_chunks(cleaned):
        for attempt in range(3):
            try:
                bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                break
            except Exception as e:
                logger.warning("Telegram send failed (attempt %d): %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(5)
                else:
                    try:
                        bot.send_message(chat_id, strip_html(chunk), timeout=60)
                    except Exception as final_e:
                        logger.error("Fallback failed: %s", final_e)


def extract_and_save_metrics(report_text: str, project_id: str = PROJECT_ID) -> None:
    """從戰報文字萃取關鍵指標並寫入 BigQuery daily_metrics 資料表。"""
    metrics_table = f"{project_id}.market_data.daily_metrics"
    # 先剝除 HTML 標籤，避免 <code>97.65</code> 等結構干擾 regex 萃取
    clean_text = strip_html(report_text)

    # ── 1. 萃取 DXY：匹配 "ICE DXY → 97.65" 格式 ──────────────────
    dxy_match = re.search(r'ICE\s+DXY\s*[→\->\s→]+\s*(\d{2,3}\.\d{1,4})', clean_text, re.IGNORECASE)
    dxy = _safe_float(dxy_match)

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

    # ── 5. 萃取 MVRV Z-Score：匹配 "MVRV Z-Score → 2.34" 格式 ───────
    mvrv_match = re.search(r'MVRV\s*Z[-\s]?Score\s*[→\->]+\s*(-?\d+(?:\.\d+)?)', clean_text, re.IGNORECASE)
    mvrv_z = _safe_float(mvrv_match)

    # ── 6. 萃取 Agent 情報摘要（幣圈 / AI 區塊各取第一段重點）──────
    grok_summary = _extract_section(clean_text, "【幣圈新聞】")
    gpt_summary  = _extract_section(clean_text, "【AI 基建現況】")

    logger.info(
        "Extracted metrics — DXY: %s, ETF Flow: %s億, Avg Risk: %s, MVRV Z: %s",
        dxy, etf_flow, avg_risk, mvrv_z,
    )

    # ── 7. 寫入 BigQuery ──────────────────────────────────────────
    try:
        client = bigquery.Client(project=project_id)  # noqa: 每次戰報執行一次，不需全域 client

        schema = [
            bigquery.SchemaField("timestamp",          "TIMESTAMP"),
            bigquery.SchemaField("dxy",                "FLOAT"),
            bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
            bigquery.SchemaField("avg_risk_score",     "FLOAT"),
            bigquery.SchemaField("gpu_b200_price",     "FLOAT"),
            bigquery.SchemaField("grok_summary",       "STRING"),
            bigquery.SchemaField("gpt_summary",        "STRING"),
            bigquery.SchemaField("mvrv_z_score",       "FLOAT"),
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
        }
        errors = client.insert_rows_json(metrics_table, [row])
        if errors:
            logger.error("BigQuery insert errors: %s", errors)
        else:
            logger.info("Daily metrics written to BigQuery successfully.")
    except Exception as e:
        logger.error("Failed to write metrics to BigQuery: %s", e)


def fetch_exclusion_context(project_id: str = PROJECT_ID, metrics_table: str = METRICS_TABLE) -> str | None:
    """從 BigQuery 讀取前一日的 grok_summary 與 gpt_summary，供研究流程排除重複新聞。"""
    try:
        client = bigquery.Client(project=project_id)
        query = f"""
            SELECT grok_summary, gpt_summary
            FROM `{metrics_table}`
            WHERE grok_summary IS NOT NULL OR gpt_summary IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = list(client.query(query).result())
        if not rows:
            return None
        row = rows[0]
        parts = [p for p in (row.get("grok_summary"), row.get("gpt_summary")) if p]
        s = "\n\n".join(parts) if parts else None
        if s and len(s) > 1200:
            s = s[:1200] + "\n…[truncated]"
        return s
    except Exception as e:
        logger.warning("Could not fetch exclusion context from BigQuery: %s", e)
        return None


def _is_503(e: Exception) -> bool:
    """是否為 503 / 暫時不可用類錯誤（可重試）。"""
    msg = str(e).lower()
    return "503" in msg or "unavailable" in msg or "high demand" in msg


def _run_pipeline_once(exclude_context: str | None) -> tuple[str, Exception | None]:
    """使用 ThreadPoolExecutor 讓兩個 Crew 同時執行，回傳合併戰報。"""
    try:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(lambda: str(CryptoResearchCrew().run(exclude_context=exclude_context)))
            future_ai = executor.submit(lambda: str(AIResearchCrew().run(exclude_context=exclude_context)))

            crypto_report = future_crypto.result()
            ai_report = future_ai.result()

        combined_report = f"{crypto_report}\n\n{ai_report}"
        return combined_report, None
    except Exception as e:
        return "", e


def run_pipeline_with_retries(exclude_context: str | None) -> tuple[str, bool]:
    """
    帶 503 退避與驗證重試的產報流程。回傳 (final_report, report_valid)。
    """
    final_report = ""
    report_valid = False
    for attempt in range(MAX_REPORT_RETRIES + 1):
        last_err: Exception | None = None
        for step in range(MAX_503_RETRIES + 1):
            report, err = _run_pipeline_once(exclude_context)
            if err is None:
                final_report = report
                last_err = None
                break
            last_err = err
            if _is_503(err) and step < MAX_503_RETRIES:
                wait = BACKOFF_BASE_SEC * (2**step)
                logger.warning("503/暫時不可用，%ds 後重試 (%d/%d)：%s", wait, step + 1, MAX_503_RETRIES + 1, err)
                time.sleep(wait)
            else:
                logger.error("Execution failed: %s", err)
                final_report = f"{ERROR_PREFIX}{err}"
                break
        if last_err is not None:
            break

        result = validate_report(final_report)
        report_valid = result["valid"]
        logger.info(
            "[Attempt %d] Validation — news=%d, tweets=%d, valid=%s",
            attempt + 1, result["news_count"], result["tweet_count"], report_valid,
        )
        if report_valid:
            logger.info("Report generation successful.")
            return final_report, True
        logger.warning("Report incomplete: %s", result["issues"])
        if logger.isEnabledFor(logging.DEBUG) and final_report:
            logger.debug("Report snippet (first 500 chars): %s", final_report[:500].replace("\n", " "))
        if attempt < MAX_REPORT_RETRIES:
            logger.info("Retrying report generation (%d/%d)...", attempt + 2, MAX_REPORT_RETRIES + 1)

    if final_report and not final_report.startswith("🚨"):
        logger.warning("Sending report despite validation issues (retries exhausted).")
    return final_report, report_valid


if __name__ == "__main__":
    logger.info("Initializing Q-Silicon Ultimate Agent...")
    exclusion = fetch_exclusion_context()
    if exclusion:
        logger.info("Loaded exclusion context from previous report (to avoid duplicate news).")

    final_report, report_valid = run_pipeline_with_retries(exclusion)

    if not SKIP_TELEGRAM:
        token, chat_id = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
        if token and chat_id:
            _send_telegram_report(final_report, token, chat_id)
        else:
            logger.warning("Telegram configuration missing. Skipping push.")
    else:
        logger.info("SKIP_TELEGRAM=1: skipping Telegram push.")

    if not SKIP_BIGQUERY and final_report and not final_report.startswith("🚨"):
        extract_and_save_metrics(final_report)
    elif SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1: skipping metrics write.")
    elif not final_report or final_report.startswith("🚨"):
        logger.warning("Skipping BigQuery metrics write — report is an error or empty.")
