"""解析戰報交易建議並寫入 BigQuery 進行 PnL 追蹤。"""

import logging
import re
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from config import PAPER_TRADE_TABLE, PROJECT_ID

logger = logging.getLogger(__name__)


def parse_trade_signals(report_text: str) -> list[dict]:
    """從戰報中解析【資金流向與精準操作】區塊的交易建議。

    支援格式：
        · <b>$BTC (做多)</b>｜現價：$95,000｜信心水準：⭐️⭐️⭐️
        · 進場：<code>$94,500</code>｜目標：<code>$100,000 (+5.8%)</code>｜停損：<code>$91,000 (-3.7%)</code>
    """
    signals: list[dict] = []

    try:
        # 抓取操作區塊（Crypto 與 US Equities 兩段）
        section_pattern = re.compile(
            r'(?:資金流向與精準操作|精準操作)[^】\n]*',
            re.IGNORECASE,
        )
        sections = section_pattern.findall(report_text)
        if not sections:
            logger.debug("No trade sections found in report.")
            return signals

        # ── 第一行：標的 / 方向 / 現價 / 信心 ──
        header_pattern = re.compile(
            r'·\s*<b>\$?(?P<symbol>[A-Za-z0-9./-]+)\s*\((?P<direction>做多|做空)\)</b>'
            r'[｜|]\s*現價[：:]\s*\$?[\d,]+(?:\.\d+)?'
            r'[｜|]\s*信心水準[：:]?\s*(?P<stars>(?:⭐️)+)',
        )

        # ── 第二行：進場 / 目標 / 停損 ──
        detail_pattern = re.compile(
            r'·\s*進場[：:]\s*<code>\$?(?P<entry>[\d,]+(?:\.\d+)?)</code>'
            r'[｜|]\s*目標[：:]\s*<code>\$?(?P<target>[\d,]+(?:\.\d+)?)(?:\s*\([^)]*\))?</code>'
            r'[｜|]\s*停損[：:]\s*<code>\$?(?P<stop>[\d,]+(?:\.\d+)?)(?:\s*\([^)]*\))?</code>',
        )

        headers = list(header_pattern.finditer(report_text))
        details = list(detail_pattern.finditer(report_text))

        for header in headers:
            symbol = header.group("symbol").strip()
            direction = "LONG" if header.group("direction") == "做多" else "SHORT"
            confidence_level = header.group("stars").count("⭐️")

            # 找到最近的 detail 行（出現在 header 之後）
            matched_detail = None
            for detail in details:
                if detail.start() > header.start():
                    matched_detail = detail
                    break

            if matched_detail is None:
                logger.warning("No detail line found for signal %s, skipping.", symbol)
                continue

            try:
                entry_price = float(matched_detail.group("entry").replace(",", ""))
                target_price = float(matched_detail.group("target").replace(",", ""))
                stop_loss = float(matched_detail.group("stop").replace(",", ""))
            except (ValueError, AttributeError) as exc:
                logger.warning("Failed to parse prices for %s: %s", symbol, exc)
                continue

            signals.append({
                "symbol": symbol,
                "direction": direction,
                "entry_price": entry_price,
                "target_price": target_price,
                "stop_loss": stop_loss,
                "confidence_level": confidence_level,
            })

    except Exception:
        logger.warning("Unexpected error while parsing trade signals.", exc_info=True)

    return signals


def log_signals_to_bigquery(
    signals: list[dict],
    project_id: str = PROJECT_ID,
    table_id: str = PAPER_TRADE_TABLE,
) -> None:
    """將解析出的交易訊號寫入 BigQuery。"""
    if not signals:
        return

    try:
        client = bigquery.Client(project=project_id)

        schema = [
            bigquery.SchemaField("trade_id", "STRING"),
            bigquery.SchemaField("timestamp", "TIMESTAMP"),
            bigquery.SchemaField("symbol", "STRING"),
            bigquery.SchemaField("direction", "STRING"),
            bigquery.SchemaField("entry_price", "FLOAT"),
            bigquery.SchemaField("target_price", "FLOAT"),
            bigquery.SchemaField("stop_loss", "FLOAT"),
            bigquery.SchemaField("confidence_level", "INTEGER"),
            bigquery.SchemaField("status", "STRING"),
        ]
        table_ref = bigquery.Table(table_id, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "trade_id": str(uuid.uuid4()),
                "timestamp": now,
                "symbol": s["symbol"],
                "direction": s["direction"],
                "entry_price": s["entry_price"],
                "target_price": s["target_price"],
                "stop_loss": s["stop_loss"],
                "confidence_level": s["confidence_level"],
                "status": "OPEN",
            }
            for s in signals
        ]

        errors = client.insert_rows_json(table_id, rows)
        if errors:
            logger.error("BigQuery insert errors (trade signals): %s", errors)
        else:
            logger.info("Trade signals written to BigQuery successfully.")
    except Exception as exc:
        logger.error("Failed to write trade signals to BigQuery: %s", exc)
