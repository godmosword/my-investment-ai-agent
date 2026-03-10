"""解析戰報交易建議並寫入 BigQuery 進行 PnL 追蹤。"""

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
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

        # ── 第三行：敘事邏輯 ──
        narrative_pattern = re.compile(
            r'·\s*敘事邏輯[：:]\s*(?P<narrative>[^\n]+)',
        )

        headers = list(header_pattern.finditer(report_text))
        details = list(detail_pattern.finditer(report_text))
        narratives = list(narrative_pattern.finditer(report_text))

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

            # 找到最近的 narrative 行（出現在 header 之後）
            matched_narrative = None
            for narrative in narratives:
                if narrative.start() > header.start():
                    matched_narrative = narrative
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
                "narrative": matched_narrative.group("narrative").strip() if matched_narrative else "",
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
            bigquery.SchemaField("narrative", "STRING"),
            bigquery.SchemaField("close_price", "FLOAT", mode="NULLABLE"),
            bigquery.SchemaField("close_time", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("pnl_pct", "FLOAT", mode="NULLABLE"),
        ]
        table_ref = bigquery.Table(table_id, schema=schema)
        client.create_table(table_ref, exists_ok=True)

        # 補齊既有表缺少的新欄位（close_price / close_time / pnl_pct）
        existing_table = client.get_table(table_id)
        existing_columns = {field.name for field in existing_table.schema}
        missing_fields = [f for f in schema if f.name not in existing_columns]
        if missing_fields:
            existing_table.schema = list(existing_table.schema) + missing_fields
            client.update_table(existing_table, ["schema"])
            logger.info(
                "Added missing BigQuery columns to trade table: %s",
                ", ".join(f.name for f in missing_fields),
            )

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
                "narrative": s.get("narrative", ""),
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


def _fetch_price_range(
    symbol: str,
    start_date: date,
) -> tuple[float | None, float | None, float | None]:
    """取得標的從 start_date 至今的最高價、最低價、最新收盤價。

    Returns:
        (period_high, period_low, latest_close) — 任一欄位失敗回傳 (None, None, None)。
    """
    end_date = date.today() + timedelta(days=1)

    # 依序嘗試多種 ticker 格式（美股直接用 symbol，加密貨幣補 -USD）
    tickers_to_try: list[str] = [symbol]
    if not symbol.upper().endswith("-USD"):
        tickers_to_try.append(f"{symbol.upper()}-USD")

    for ticker in tickers_to_try:
        try:
            df = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                interval="1d",
                progress=False,
                auto_adjust=True,
            )
            if df is None or df.empty:
                continue

            high_col = df["High"]
            low_col = df["Low"]
            close_col = df["Close"]

            # 處理 yfinance MultiIndex DataFrame
            if hasattr(high_col, "ndim") and high_col.ndim > 1:
                high_col = high_col.iloc[:, 0]
                low_col = low_col.iloc[:, 0]
                close_col = close_col.iloc[:, 0]

            high_col = high_col.dropna()
            low_col = low_col.dropna()
            close_col = close_col.dropna()

            if close_col.empty:
                continue

            return float(high_col.max()), float(low_col.min()), float(close_col.iloc[-1])

        except Exception as exc:
            logger.debug("yfinance fetch failed for ticker %s: %s", ticker, exc)

    return None, None, None


def settle_open_trades(
    project_id: str = PROJECT_ID,
    table_id: str = PAPER_TRADE_TABLE,
) -> None:
    """掃描 BigQuery 中狀態為 OPEN 的交易紀錄，並根據歷史價格觸發停利/停損結算。

    結算邏輯：
      - LONG：區間 High >= target_price → 停利；區間 Low <= stop_loss → 停損。
      - SHORT：區間 Low <= target_price → 停利；區間 High >= stop_loss → 停損。
    觸發時計算實際 PnL %，並將紀錄更新為 CLOSED，填入 close_price / close_time / pnl_pct。
    """
    try:
        client = bigquery.Client(project=project_id)

        query = f"""
            SELECT trade_id, symbol, direction, entry_price, target_price, stop_loss, timestamp
            FROM `{table_id}`
            WHERE status = 'OPEN'
        """  # noqa: S608 — table_id comes from trusted config constant
        rows = list(client.query(query).result())
        if not rows:
            logger.info("settle_open_trades: no open trades found.")
            return

        logger.info("settle_open_trades: checking %d open trade(s).", len(rows))
        now = datetime.now(timezone.utc)

        for row in rows:
            trade_id: str = row["trade_id"]
            symbol: str = row["symbol"]
            direction: str = row["direction"]
            entry_price: float = float(row["entry_price"])
            target_price: float = float(row["target_price"])
            stop_loss: float = float(row["stop_loss"])
            entry_ts = row["timestamp"]  # BigQuery TIMESTAMP → datetime-like

            # BigQuery が返す timestamp は aware datetime または date-aware 型
            if hasattr(entry_ts, "date"):
                start_date = entry_ts.date()
            else:
                start_date = date.fromisoformat(str(entry_ts)[:10])

            period_high, period_low, latest_close = _fetch_price_range(symbol, start_date)
            if period_high is None or period_low is None or latest_close is None:
                logger.warning(
                    "settle_open_trades: could not fetch price data for %s (trade_id=%s), skipping.",
                    symbol,
                    trade_id,
                )
                continue

            # ── 結算判斷 ──
            triggered = False
            close_price = latest_close

            if direction == "LONG":
                if period_high >= target_price:
                    triggered = True
                    close_price = target_price
                    close_reason = "TARGET"
                elif period_low <= stop_loss:
                    triggered = True
                    close_price = stop_loss
                    close_reason = "STOP_LOSS"
            elif direction == "SHORT":
                if period_low <= target_price:
                    triggered = True
                    close_price = target_price
                    close_reason = "TARGET"
                elif period_high >= stop_loss:
                    triggered = True
                    close_price = stop_loss
                    close_reason = "STOP_LOSS"

            if not triggered:
                logger.debug(
                    "settle_open_trades: trade %s (%s %s) still open — range [%.4f, %.4f].",
                    trade_id, direction, symbol, period_low, period_high,
                )
                continue

            # ── 計算 PnL % ──
            if direction == "LONG":
                pnl_pct = (close_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - close_price) / entry_price * 100

            # ── 更新 BigQuery 紀錄 ──
            update_dml = f"""
                UPDATE `{table_id}`
                SET
                    status = 'CLOSED',
                    close_price = @close_price,
                    close_time = @close_time,
                    pnl_pct = @pnl_pct
                WHERE trade_id = @trade_id
            """  # noqa: S608 — table_id is a trusted config constant; values are parameterized
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("close_price", "FLOAT64", close_price),
                    bigquery.ScalarQueryParameter("close_time", "TIMESTAMP", now),
                    bigquery.ScalarQueryParameter("pnl_pct", "FLOAT64", round(pnl_pct, 4)),
                    bigquery.ScalarQueryParameter("trade_id", "STRING", trade_id),
                ]
            )
            try:
                client.query(update_dml, job_config=job_config).result()
                logger.info(
                    "settle_open_trades: CLOSED trade %s (%s %s) — %s at %.4f, PnL=%.2f%%",
                    trade_id, direction, symbol, close_reason, close_price, pnl_pct,
                )
            except Exception as exc:
                logger.error(
                    "settle_open_trades: failed to update trade %s in BigQuery: %s",
                    trade_id, exc,
                )

    except Exception as exc:
        logger.error("settle_open_trades: unexpected error: %s", exc)
