"""建議追蹤與績效問責模組。

功能：
  1. 從每日戰報解析 [QSREC_START]…[QSREC_END] JSON 建議區塊
  2. 寫入 BigQuery trade_recommendations 資料表
  3. 每日回查 OPEN 狀態建議，抓最新價格，更新 HIT_TARGET / HIT_STOP / EXPIRED
  4. 生成週度績效摘要 Telegram HTML
"""

import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from google.cloud import bigquery

from config import PAPER_TRADE_TABLE, PROJECT_ID, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

# ── 建議 JSON 區塊標記 ─────────────────────────────────────────────────────────
_QSREC_RE = re.compile(r'\[QSREC_START\]\s*([\s\S]*?)\[QSREC_END\]')

# 已知 crypto 代號，用於判斷 category 與 yfinance symbol 轉換
_CRYPTO_ASSETS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "LINK", "DOT", "MATIC",
    "ARB", "OP", "SUI", "APT", "INJ", "TIA", "NEAR", "ATOM", "DOGE", "ADA",
}

# BigQuery trade_recommendations schema
_SCHEMA = [
    bigquery.SchemaField("report_date",              "DATE"),
    bigquery.SchemaField("asset",                    "STRING"),
    bigquery.SchemaField("direction",                "STRING"),
    bigquery.SchemaField("current_price_at_signal",  "FLOAT"),
    bigquery.SchemaField("entry_price",              "FLOAT"),
    bigquery.SchemaField("target_price",             "FLOAT"),
    bigquery.SchemaField("stop_price",               "FLOAT"),
    bigquery.SchemaField("target_pct",               "FLOAT"),
    bigquery.SchemaField("stop_pct",                 "FLOAT"),
    bigquery.SchemaField("confidence",               "INTEGER"),
    bigquery.SchemaField("narrative",                "STRING"),
    bigquery.SchemaField("category",                 "STRING"),
    bigquery.SchemaField("status",                   "STRING"),
    bigquery.SchemaField("exit_price",               "FLOAT"),
    bigquery.SchemaField("exit_date",                "DATE"),
    bigquery.SchemaField("pnl_pct",                  "FLOAT"),
    bigquery.SchemaField("days_held",                "INTEGER"),
    bigquery.SchemaField("created_at",               "TIMESTAMP"),
]


def _yf_symbol(asset: str) -> str:
    """將代幣/股票代號轉換為 yfinance 查詢用的 symbol。"""
    a = asset.upper().strip("$")
    return f"{a}-USD" if a in _CRYPTO_ASSETS else a


def extract_recommendations_json(report_text: str) -> list[dict]:
    """從報告文字中解析所有 [QSREC_START]…[QSREC_END] 區塊，回傳原始 dict 列表。"""
    recs: list[dict] = []
    for m in _QSREC_RE.finditer(report_text):
        raw = m.group(1).strip()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                recs.extend(parsed)
            elif isinstance(parsed, dict):
                recs.append(parsed)
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse QSREC JSON: %s | snippet=%r", e, raw[:200])
    return recs


def strip_tracker_blocks(report_text: str) -> str:
    """移除報告中的機器讀取區塊，防止這些標記出現在 Telegram 訊息中。"""
    return _QSREC_RE.sub("", report_text).rstrip()


def _validate_rec(raw: dict, report_date: str) -> dict | None:
    """驗證並補全建議欄位；必要欄位缺失時回傳 None。"""
    asset = str(raw.get("asset", "")).upper().strip("$")
    direction = str(raw.get("direction", "LONG")).upper()
    if not asset or direction not in ("LONG", "SHORT"):
        logger.debug("Skipping invalid rec (asset=%r direction=%r)", asset, direction)
        return None
    try:
        entry  = float(raw["entry"])
        target = float(raw["target"])
        stop   = float(raw["stop"])
    except (KeyError, ValueError, TypeError) as e:
        logger.debug("Skipping rec for %s — missing price fields: %s", asset, e)
        return None

    category = str(raw.get("category", "CRYPTO")).upper()
    if category not in ("CRYPTO", "EQUITY"):
        category = "CRYPTO" if asset in _CRYPTO_ASSETS else "EQUITY"

    return {
        "report_date":             report_date,
        "asset":                   asset,
        "direction":               direction,
        "current_price_at_signal": float(raw.get("current_price", entry)),
        "entry_price":             entry,
        "target_price":            target,
        "stop_price":              stop,
        "target_pct":              float(raw.get("target_pct", 0.0)),
        "stop_pct":                float(raw.get("stop_pct", 0.0)),
        "confidence":              max(1, min(4, int(raw.get("confidence", 3)))),
        "narrative":               str(raw.get("narrative", ""))[:500],
        "category":                category,
        "status":                  "OPEN",
        "exit_price":              None,
        "exit_date":               None,
        "pnl_pct":                 None,
        "days_held":               None,
        "created_at":              datetime.now(timezone.utc).isoformat(),
    }


def _ensure_table(client: bigquery.Client) -> None:
    """確保 trade_recommendations 表存在且 schema 完整。"""
    tbl_ref = bigquery.Table(RECOMMENDATIONS_TABLE, schema=_SCHEMA)
    client.create_table(tbl_ref, exists_ok=True)
    existing_tbl = client.get_table(RECOMMENDATIONS_TABLE)
    existing_cols = {f.name for f in existing_tbl.schema}
    missing = [f for f in _SCHEMA if f.name not in existing_cols]
    if missing:
        existing_tbl.schema = list(existing_tbl.schema) + missing
        client.update_table(existing_tbl, ["schema"])
        logger.info("Added missing columns to trade_recommendations: %s", [f.name for f in missing])


def save_recommendations(report_text: str,
                         project_id: str = PROJECT_ID,
                         report_date: str | None = None) -> int:
    """
    從戰報文字解析 JSON 建議並寫入 BigQuery。
    回傳成功儲存的建議數量；BigQuery 不可用時回傳 0 並記錄警告。
    """
    if report_date is None:
        report_date = date.today().isoformat()

    raw_recs = extract_recommendations_json(report_text)
    recs = [r for raw in raw_recs if (r := _validate_rec(raw, report_date)) is not None]

    if not recs:
        logger.info("No valid recommendations found in report (raw_count=%d).", len(raw_recs))
        return 0

    try:
        client = bigquery.Client(project=project_id)
        _ensure_table(client)
        errors = client.insert_rows_json(RECOMMENDATIONS_TABLE, recs)
        if errors:
            logger.error("BigQuery insert errors for recommendations: %s", errors)
            return 0
        logger.info("Saved %d recommendations to BigQuery (date=%s).", len(recs), report_date)
        return len(recs)
    except Exception as e:
        logger.error("Failed to save recommendations to BigQuery: %s", e)
        return 0


def check_and_update_positions(project_id: str = PROJECT_ID) -> list[dict]:
    """
    查詢所有 OPEN 狀態建議（最近 30 天），抓取最新收盤價，
    判斷是否觸及目標（HIT_TARGET）、停損（HIT_STOP）或逾期（EXPIRED ≥30天）。

    已關倉的建議以 BigQuery DML UPDATE 更新狀態與 P&L。
    回傳當日已關倉的建議摘要列表。
    """
    try:
        client = bigquery.Client(project=project_id)
    except Exception as e:
        logger.error("BigQuery client init failed in check_and_update_positions: %s", e)
        return []

    # 查詢所有未平倉建議
    try:
        rows = list(client.query(f"""
            SELECT *
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE status = 'OPEN'
              AND report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
        """).result())
    except Exception as e:
        logger.warning("Failed to query open positions: %s", e)
        return []

    if not rows:
        logger.info("No open positions to check today.")
        return []

    # 批次抓取最新收盤價（每個 asset 只下載一次）
    assets = {row["asset"] for row in rows}
    prices: dict[str, float | None] = {}
    for asset in assets:
        sym = _yf_symbol(asset)
        try:
            df = yf.download(sym, period="2d", interval="1d", progress=False, auto_adjust=True)
            if df is None or df.empty:
                prices[asset] = None
                continue
            close = df["Close"].dropna()
            if hasattr(close, "ndim") and close.ndim > 1:
                close = close.iloc[:, 0]
            prices[asset] = float(close.iloc[-1]) if not close.empty else None
        except Exception as e:
            logger.warning("Price fetch failed for %s: %s", asset, e)
            prices[asset] = None

    today = date.today()
    closed: list[dict] = []

    for row in rows:
        asset    = row["asset"]
        price    = prices.get(asset)
        if price is None:
            continue

        direction = row["direction"]
        entry     = float(row["entry_price"])
        target    = float(row["target_price"])
        stop      = float(row["stop_price"])
        rep_date  = row["report_date"]
        days_held = (today - rep_date).days if rep_date else 0

        # 判斷是否已觸及目標或停損
        if direction == "LONG":
            new_status = (
                "HIT_TARGET" if price >= target else
                "HIT_STOP"   if price <= stop   else
                "OPEN"
            )
        else:  # SHORT
            new_status = (
                "HIT_TARGET" if price <= target else
                "HIT_STOP"   if price >= stop   else
                "OPEN"
            )

        if new_status == "OPEN" and days_held >= 30:
            new_status = "EXPIRED"

        if new_status == "OPEN":
            continue

        # 計算 P&L
        pnl = round(
            ((price - entry) / entry * 100) if direction == "LONG"
            else ((entry - price) / entry * 100),
            2,
        )

        # 以 parameterized DML 更新（防注入）
        try:
            client.query(
                f"""
                UPDATE `{RECOMMENDATIONS_TABLE}`
                SET status     = @status,
                    exit_price = @price,
                    exit_date  = @today,
                    pnl_pct    = @pnl,
                    days_held  = @days
                WHERE asset       = @asset
                  AND report_date = @rep_date
                  AND status      = 'OPEN'
                """,
                job_config=bigquery.QueryJobConfig(query_parameters=[
                    bigquery.ScalarQueryParameter("status",   "STRING",  new_status),
                    bigquery.ScalarQueryParameter("price",    "FLOAT64", price),
                    bigquery.ScalarQueryParameter("today",    "DATE",    today.isoformat()),
                    bigquery.ScalarQueryParameter("pnl",      "FLOAT64", pnl),
                    bigquery.ScalarQueryParameter("days",     "INT64",   days_held),
                    bigquery.ScalarQueryParameter("asset",    "STRING",  asset),
                    bigquery.ScalarQueryParameter("rep_date", "DATE",    str(rep_date)),
                ]),
            ).result()
            logger.info(
                "Position closed: %s %s → %s | P&L: %+.1f%% | held %d days",
                asset, direction, new_status, pnl, days_held,
            )
            closed.append({
                "asset":     asset,
                "direction": direction,
                "status":    new_status,
                "pnl_pct":   pnl,
            })
        except Exception as e:
            logger.error("Failed to update position %s (date=%s): %s", asset, rep_date, e)

    return closed


def generate_performance_summary(project_id: str = PROJECT_ID, days: int = 30) -> str:
    """
    查詢過去 days 天的已關倉建議，生成 Telegram HTML 格式績效週報。
    無數據或查詢失敗時回傳空字串。
    """
    try:
        client = bigquery.Client(project=project_id)
        rows = list(client.query(f"""
            SELECT
                status,
                COUNT(*)                AS cnt,
                ROUND(AVG(pnl_pct), 2)  AS avg_pnl,
                ROUND(MAX(pnl_pct), 2)  AS best,
                ROUND(MIN(pnl_pct), 2)  AS worst,
                ROUND(AVG(days_held), 1) AS avg_days
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
              AND status != 'OPEN'
            GROUP BY status
            ORDER BY status
        """).result())
    except Exception as e:
        logger.warning("Cannot generate performance summary: %s", e)
        return ""

    if not rows:
        logger.info("No closed positions in the last %d days for performance summary.", days)
        return ""

    total    = sum(r["cnt"] for r in rows)
    wins     = next((r["cnt"] for r in rows if r["status"] == "HIT_TARGET"), 0)
    win_rate = round(wins / total * 100, 1) if total else 0.0

    # 加權平均 P&L（以筆數加權）
    weighted_sum = sum(
        (r["avg_pnl"] or 0.0) * r["cnt"] for r in rows if r["avg_pnl"] is not None
    )
    avg_all = round(weighted_sum / total, 2) if total else 0.0

    _STATUS_LABEL = {
        "HIT_TARGET": "✅ 達標",
        "HIT_STOP":   "❌ 停損",
        "EXPIRED":    "⏳ 過期",
    }
    lines = [
        f"<b>📊 Q-Silicon 近 {days} 天建議績效報告</b>",
        "────────────",
        f"· 總建議：<code>{total}</code> 筆 | 勝率：<code>{win_rate}%</code>",
        f"· 加權平均報酬：<code>{avg_all:+.2f}%</code>",
        "────────────",
    ]
    for r in rows:
        label = _STATUS_LABEL.get(r["status"], r["status"])
        avg_days_str = f" | 均持倉 <code>{r['avg_days']:.0f}天</code>" if r["avg_days"] else ""
        lines.append(
            f"· {label} <code>{r['cnt']}</code> 筆"
            f" | 均損益 <code>{(r['avg_pnl'] or 0.0):+.1f}%</code>"
            f"（最佳 <code>{(r['best'] or 0.0):+.1f}%</code>"
            f" / 最差 <code>{(r['worst'] or 0.0):+.1f}%</code>）"
            f"{avg_days_str}"
        )
    return "\n".join(lines)


# ── 交易訊號解析與 Paper Trade 結算 ──────────────────────────────────────────


def parse_trade_signals(report_text: str) -> list[dict]:
    """從戰報中解析【資金流向與精準操作】區塊的交易建議。

    支援格式：
        · <b>$BTC (做多)</b>｜現價：$95,000｜信心水準：⭐️⭐️⭐️
        · 進場：<code>$94,500</code>｜目標：<code>$100,000 (+5.8%)</code>｜停損：<code>$91,000 (-3.7%)</code>
    """
    signals: list[dict] = []

    try:
        section_pattern = re.compile(
            r'(?:資金流向與精準操作|精準操作)[^】\n]*',
            re.IGNORECASE,
        )
        sections = section_pattern.findall(report_text)
        if not sections:
            logger.debug("No trade sections found in report.")
            return signals

        header_pattern = re.compile(
            r'·\s*<b>\$?(?P<symbol>[A-Za-z0-9./-]+)\s*\((?P<direction>做多|做空)\)</b>'
            r'[｜|]\s*現價[：:]\s*\$?[\d,]+(?:\.\d+)?'
            r'[｜|]\s*信心水準[：:]?\s*(?P<stars>(?:⭐️)+)',
        )
        detail_pattern = re.compile(
            r'·\s*進場[：:]\s*<code>\$?(?P<entry>[\d,]+(?:\.\d+)?)</code>'
            r'[｜|]\s*目標[：:]\s*<code>\$?(?P<target>[\d,]+(?:\.\d+)?)(?:\s*\([^)]*\))?</code>'
            r'[｜|]\s*停損[：:]\s*<code>\$?(?P<stop>[\d,]+(?:\.\d+)?)(?:\s*\([^)]*\))?</code>',
        )
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

            matched_detail = next(
                (d for d in details if d.start() > header.start()), None
            )
            matched_narrative = next(
                (n for n in narratives if n.start() > header.start()), None
            )

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
            entry_ts = row["timestamp"]

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

            triggered = False
            close_price = latest_close
            close_reason = ""

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

            if direction == "LONG":
                pnl_pct = (close_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - close_price) / entry_price * 100

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
