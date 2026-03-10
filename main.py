import os
import re
import time
import logging
import telebot
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.cloud import bigquery
import yfinance as yf

from config import PROJECT_ID, METRICS_TABLE
from crew import CryptoResearchCrew, AIResearchCrew
from tracker import parse_trade_signals, log_signals_to_bigquery, settle_open_trades
from visualizer import generate_quant_chart
import tracker

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
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "blockquote", "a"}


def sanitize_telegram_html(text: str) -> str:
    """清洗 LLM 輸出的 HTML，保留 Telegram 支援的標籤。"""
    text = re.sub(r'&(?!(?:amp|lt|gt|quot|apos);)', '&amp;', text)

    def _fix_tag(m: re.Match) -> str:
        inner = m.group(1)
        tag_name = inner.lstrip('/').split()[0].lower()
        if tag_name == 'a':
            if inner.startswith('/'):
                return '</a>'
            href_m = re.search(r'href=["\']([^"\']+)["\']', inner)
            if href_m:
                return f'<a href="{href_m.group(1)}">'
            return ''
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
    """驗證戰報是否包含足夠新聞與必要區塊（V2.1 四區塊結構）。"""
    news_count  = len(re.findall(r'〔新聞', text))

    has_regime    = bool(re.search(r'risk_on|risk_off|neutral', text, re.IGNORECASE))
    has_dashboard = bool(re.search(r'DXY|BTC\s*OI|資金費率|模型排名|ML.*權重|RSI|Fear.*Greed|儀表板', text, re.IGNORECASE))
    has_crypto_trade = bool(re.search(r'資金流向與精準操作\s*\(Crypto\)|精準操作.*Crypto', text, re.IGNORECASE))
    has_ai_trade  = bool(re.search(r'AI\s*產業鏈精準操作|精準操作.*Equit', text, re.IGNORECASE))
    has_ai_section = bool(re.search(r'AI\s*市場|AI\s*產業新聞|AI\s*數據儀表板', text, re.IGNORECASE))
    has_crypto_section = bool(re.search(r'加密市場|核心新聞|數據儀表板', text, re.IGNORECASE))
    has_chatter = bool(re.search(r'呢喃|傳聞', text))
    has_data_missing = bool(re.search(r'\[DATA_MISSING:', text))

    issues = []
    if len(text) < 3000:
        issues.append(f"報告過短（{len(text)} chars，預期 >3000）")
    if news_count < 6:
        issues.append(f"新聞數不足（{news_count}/6）")
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
    if has_data_missing:
        missing_fields = re.findall(r'\[DATA_MISSING:([^\]]+)\]', text)
        issues.append(f"資料缺失欄位：{', '.join(set(missing_fields))}")

    return {
        "valid": len([i for i in issues if "資料缺失" not in i and "呢喃" not in i]) == 0,
        "issues": issues,
        "news_count": news_count,
        "has_data_missing": has_data_missing,
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


def _extract_news_titles(text: str, max_titles: int = 20) -> list[str]:
    """從戰報中萃取所有新聞標題，供次日排除重複使用。"""
    clean = strip_html(text)
    titles: list[str] = []
    for m in re.finditer(r'〔新聞\s*\d+〕[^\n]*\n([^\n]{10,120})', clean):
        titles.append(m.group(1).strip())
    for m in re.finditer(r'〔新聞\s*\d+〕\s*([^\n]{10,120})', clean):
        candidate = m.group(1).strip()
        if candidate not in titles:
            titles.append(candidate)
    return titles[:max_titles]


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

    cleaned = sanitize_telegram_html(text)
    for i, chunk in enumerate(_safe_chunks(cleaned)):
        sent = False
        for attempt in range(4):
            try:
                bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                sent = True
                time.sleep(0.5)
                break
            except Exception as e:
                err_str = str(e).lower()
                wait = 5 if "429" not in err_str else 30 * (attempt + 1)
                logger.warning("Chunk %d send attempt %d failed (wait=%ds): %s", i, attempt + 1, wait, e)
                if attempt < 3:
                    time.sleep(wait)
        if not sent:
            try:
                bot.send_message(chat_id, strip_html(chunk), timeout=60)
            except Exception as final_e:
                logger.error("Chunk %d all retries failed: %s", i, final_e)


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
    gpt_summary  = _extract_section(clean_text, "【AI 基建現況】")

    # ── 6b. 萃取新聞標題供次日去重 ──────────────────
    all_titles = _extract_news_titles(report_text, max_titles=25)
    news_titles_str = "\n".join(f"· {t}" for t in all_titles) if all_titles else None
    logger.info("Extracted %d news titles for deduplication.", len(all_titles))

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
            bigquery.SchemaField("news_titles",        "STRING"),
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


def fetch_exclusion_context(project_id: str = PROJECT_ID, metrics_table: str = METRICS_TABLE) -> str | None:
    """從 BigQuery 讀取前一日的新聞標題列表，供研究流程排除重複新聞。"""
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

        s = "\n\n".join(parts) if parts else None
        if s and len(s) > 2000:
            s = s[:2000] + "\n…[truncated]"
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
    import pandas as pd  # noqa: F811 — 模組頂層已有，此處為防呼叫端缺失
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


def _run_pipeline_once(exclude_context: str | None) -> tuple[str, Exception | None]:
    """使用 ThreadPoolExecutor 讓兩個 Crew 同時執行，回傳合併戰報。"""
    try:
        price_context = get_realtime_quotes()
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_crypto = executor.submit(
                lambda: str(CryptoResearchCrew().run(exclude_context=exclude_context, price_context=price_context))
            )
            future_ai = executor.submit(
                lambda: str(AIResearchCrew().run(exclude_context=exclude_context, price_context=price_context))
            )

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
            if _is_retriable(err) and step < MAX_503_RETRIES:
                wait = BACKOFF_BASE_SEC * (2**step)
                logger.warning("暫時性錯誤（可重試），%ds 後重試 (%d/%d)：%s", wait, step + 1, MAX_503_RETRIES + 1, err)
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
            "[Attempt %d] Validation — news=%d, valid=%s",
            attempt + 1, result["news_count"], report_valid,
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


def _validate_required_keys() -> None:
    """啟動前檢查必要 API 金鑰，提早回報缺失。"""
    required = {
        "XAI_API_KEY": "Grok（加密市場情報員）",
        "OPENROUTER_API_KEY": "Claude（幣圈/AI 辯論員）",
        "GEMINI_API_KEY": "Gemini（戰報主編）",
        "OPENAI_API_KEY": "GPT（AI 情報員）",
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


if __name__ == "__main__":
    logger.info("Initializing Q-Silicon Ultimate Agent...")
    _validate_required_keys()
    generate_quant_chart("daily_chart.png")
    exclusion = fetch_exclusion_context()
    if exclusion:
        logger.info("Loaded exclusion context from previous report (to avoid duplicate news).")

    if not SKIP_BIGQUERY:
        settle_open_trades(PROJECT_ID)

    # ── Tracker：儲存建議 & 每日回查未平倉部位 ───────────────────────────────
    _report_ok = bool(final_report and not final_report.startswith("🚨"))
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
                    _tb.TeleBot(token).send_message(chat_id, perf_summary, parse_mode="HTML", timeout=30)
                    logger.info("Weekly performance summary sent to Telegram.")
                except Exception as _e:
                    logger.warning("Failed to send weekly performance summary: %s", _e)

    # ── 移除機器可讀區塊，再發送 Telegram ────────────────────────────────────
    clean_report = tracker.strip_tracker_blocks(final_report)

    if not SKIP_TELEGRAM:
        if token and chat_id:
            _send_telegram_report(clean_report, token, chat_id, image_path="daily_chart.png")
        else:
            logger.warning("Telegram configuration missing. Skipping push.")
    else:
        logger.info("SKIP_TELEGRAM=1: skipping Telegram push.")

    if not SKIP_BIGQUERY and _report_ok:
        extract_and_save_metrics(final_report)

        trade_signals = parse_trade_signals(final_report)
        if trade_signals:
            log_signals_to_bigquery(trade_signals)
            logger.info("Logged %d trade signal(s) to BigQuery.", len(trade_signals))
    elif SKIP_BIGQUERY:
        logger.info("SKIP_BIGQUERY=1: skipping metrics write.")
    elif not _report_ok:
        logger.warning("Skipping BigQuery metrics write — report is an error or empty.")
