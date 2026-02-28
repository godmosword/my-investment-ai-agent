import os
import re
import logging
import telebot
from datetime import datetime, timezone
from dotenv import load_dotenv
from google.cloud import bigquery

from crew import QSiliconResearchCrew

# 載入環境變數
load_dotenv()

# 設定日誌
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Telegram HTML 支援的標籤白名單
_ALLOWED_TAGS = {"b", "i", "u", "s", "code", "pre", "blockquote"}

PROJECT_ID = "my-investment-ai-agent"
METRICS_TABLE = f"{PROJECT_ID}.market_data.daily_metrics"


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


def validate_report(text: str) -> dict:
    """驗證戰報是否包含足夠的新聞與推文，回傳驗證結果與詳細計數。"""
    news_count  = len(re.findall(r'〔新聞', text))
    tweet_count = len(re.findall(r'〔推文', text))
    has_regime  = bool(re.search(r'risk_on|risk_off|neutral', text, re.IGNORECASE))
    has_dashboard = bool(re.search(r'ICE\s*DXY|BTC\s*OI|H100', text, re.IGNORECASE))

    issues = []
    if news_count < 5:
        issues.append(f"新聞數不足（{news_count}/5）")
    if tweet_count < 3:
        issues.append(f"推文數不足（{tweet_count}/6）")
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


def extract_and_save_metrics(report_text: str, project_id: str = PROJECT_ID) -> None:
    """從戰報文字萃取關鍵指標並寫入 BigQuery daily_metrics 資料表。"""
    # 先剝除 HTML 標籤，避免 <code>97.65</code> 等結構干擾 regex 萃取
    clean_text = strip_html(report_text)

    # ── 1. 萃取 DXY：匹配 "ICE DXY → 97.65" 格式 ──────────────────
    dxy = None
    dxy_match = re.search(
        r'ICE\s+DXY\s*[→\->\s→]+\s*(\d{2,3}\.\d{1,4})',
        clean_text, re.IGNORECASE
    )
    if dxy_match:
        try:
            dxy = float(dxy_match.group(1))
        except ValueError:
            pass

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
        try:
            direction_raw = etf_match.group(1).lower()
            value = float(etf_match.group(2))
            is_outflow = any(k in direction_raw for k in ('流出', '外流'))
            etf_flow = -value if is_outflow else value
        except ValueError:
            pass

    # ── 3. 萃取所有 "RISK x/5" 並計算平均（含 RISK 4/5、RISK_SCORE 格式）──
    avg_risk = None
    risk_scores = re.findall(
        r'RISK(?:_SCORE)?[】\s]*(\d(?:\.\d)?)\s*/\s*5',
        clean_text, re.IGNORECASE
    )
    if risk_scores:
        try:
            scores = [float(s) for s in risk_scores]
            avg_risk = round(sum(scores) / len(scores), 2)
        except ValueError:
            pass

    logging.info(f"Extracted metrics — DXY: {dxy}, ETF Flow: {etf_flow}億, Avg Risk: {avg_risk}")

    # ── 4. 寫入 BigQuery ──────────────────────────────────────────
    try:
        client = bigquery.Client(project=project_id)  # noqa: 每次戰報執行一次，不需全域 client

        # 自動建表（若不存在）
        schema = [
            bigquery.SchemaField("timestamp",          "TIMESTAMP"),
            bigquery.SchemaField("dxy",                "FLOAT"),
            bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
            bigquery.SchemaField("avg_risk_score",     "FLOAT"),
        ]
        table_ref = bigquery.Table(METRICS_TABLE, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        row = {
            "timestamp":         datetime.now(timezone.utc).isoformat(),
            "dxy":               dxy,
            "etf_flow_millions": etf_flow,
            "avg_risk_score":    avg_risk,
        }
        errors = client.insert_rows_json(METRICS_TABLE, [row])
        if errors:
            logging.error(f"BigQuery insert errors: {errors}")
        else:
            logging.info("Daily metrics written to BigQuery successfully.")
    except Exception as e:
        logging.error(f"Failed to write metrics to BigQuery: {e}")


if __name__ == "__main__":
    logging.info("Initializing Q-Silicon Ultimate Agent...")

    _MAX_REPORT_RETRIES = 2
    final_report = ""
    report_valid = False

    for attempt in range(_MAX_REPORT_RETRIES + 1):
        try:
            research_crew = QSiliconResearchCrew()
            final_report = str(research_crew.run())

            result = validate_report(final_report)
            logging.info(
                f"[Attempt {attempt + 1}] Validation — "
                f"news={result['news_count']}, tweets={result['tweet_count']}, "
                f"valid={result['valid']}"
            )

            if result["valid"]:
                logging.info("Report Generation Successful.")
                report_valid = True
                break
            else:
                logging.warning(f"Report incomplete: {result['issues']}")
                if attempt < _MAX_REPORT_RETRIES:
                    logging.info(f"Retrying report generation (attempt {attempt + 2}/{_MAX_REPORT_RETRIES + 1})...")

        except Exception as e:
            final_report = f"🚨 Q-Silicon 智庫執行失敗，請檢查系統日誌。\n錯誤訊息：{str(e)}"
            logging.error(f"Execution Failed: {e}")
            break

    if not report_valid and final_report and not final_report.startswith("🚨"):
        logging.warning("Sending report despite validation issues (all retries exhausted).")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if token and chat_id:
        from telebot import apihelper
        import time

        apihelper.SESSION_TIME_TO_LIVE = 5 * 60
        bot = telebot.TeleBot(token)

        cleaned_report = sanitize_telegram_html(final_report)

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
                # 若切點落在未閉合標籤中，回退到最後一個 '<' 前。
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

        chunks = _safe_chunks(cleaned_report)

        for chunk in chunks:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    bot.send_message(chat_id, chunk, parse_mode="HTML", timeout=60)
                    break
                except Exception as e:
                    logging.warning(f"Telegram Message Failed on attempt {attempt+1}: {e}")
                    if attempt < max_retries - 1:
                        logging.info("Retrying in 5 seconds...")
                        time.sleep(5)
                    else:
                        logging.error("Max retries reached. Falling back to plain text.")
                        try:
                            plain = strip_html(chunk)
                            bot.send_message(chat_id, plain, timeout=60)
                        except Exception as final_e:
                            logging.error(f"Ultimate fallback failed: {final_e}")
    else:
        logging.warning("Telegram configuration missing. Skipping push.")

    # 每日戰報指標寫入 BigQuery（Telegram 推送完畢後執行）
    extract_and_save_metrics(final_report)
