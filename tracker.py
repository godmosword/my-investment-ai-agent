"""建議追蹤與績效問責模組。

功能：
  1. 從每日戰報解析 [QSREC_START]…[QSREC_END] JSON 建議區塊
  2. 寫入 BigQuery trade_recommendations 資料表
  3. 每日回查 OPEN 狀態建議，抓最新價格，更新 HIT_TARGET / HIT_STOP / EXPIRED
  4. 生成週度績效摘要 Telegram HTML
  5. 生成上期建議追蹤區塊，注入當日報告
"""

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
from google.cloud import bigquery

from config import PROJECT_ID, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

# ── BigQuery client singleton ──────────────────────────────────────────────────
_bq_clients: dict[str, bigquery.Client] = {}


def _get_bq_client(project_id: str = PROJECT_ID) -> bigquery.Client:
    """Module-level BigQuery client singleton（按 project_id 快取，節省連線開銷）。"""
    if project_id not in _bq_clients:
        _bq_clients[project_id] = bigquery.Client(project=project_id)
    return _bq_clients[project_id]


# ── 建議 JSON 區塊標記 ─────────────────────────────────────────────────────────
_QSREC_RE = re.compile(r'\[QSREC_START\]\s*([\s\S]*?)\[QSREC_END\]')

# 已知 crypto 代號，用於判斷 category 與 yfinance symbol 轉換
_CRYPTO_ASSETS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "LINK", "DOT", "MATIC",
    "ARB", "OP", "SUI", "APT", "INJ", "TIA", "NEAR", "ATOM", "DOGE", "ADA",
}

# 各資產合理進場價格範圍（用於防止 LLM 輸出單位錯誤的資料）
# 例如：BTC/SOL 比值 ($815) 被誤記為 BTC USD 進場價
_PRICE_SANITY_RANGES: dict[str, tuple[float, float]] = {
    "BTC":  (10_000, 300_000),
    "ETH":  (500,    15_000),
    "SOL":  (10,     1_000),
    "BNB":  (100,    2_000),
    "XRP":  (0.1,    50),
    "AVAX": (5,      500),
    "DOGE": (0.01,   5),
    "NVDA": (50,     2_000),
    "MSFT": (100,    600),
    "AAPL": (100,    400),
    "TSLA": (100,    2_000),
    "GOOGL": (80,    300),
    "AMZN": (100,    300),
    "META": (100,    800),
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
    # Phase 3：機構級建議新增欄位
    bigquery.SchemaField("trigger",                  "STRING"),
    bigquery.SchemaField("invalidation",             "STRING"),
    bigquery.SchemaField("position_pct",             "FLOAT"),
    bigquery.SchemaField("timeframe",                "STRING"),
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

    # 驗證進場價格是否在合理範圍內，防止 LLM 輸出單位錯誤（例如比值當 USD）
    if asset in _PRICE_SANITY_RANGES:
        lo, hi = _PRICE_SANITY_RANGES[asset]
        if not (lo <= entry <= hi):
            logger.warning(
                "Skipping %s %s: entry $%s outside sanity range $%s–$%s (likely unit error)",
                asset, direction, entry, lo, hi,
            )
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
        # Phase 3 新欄位
        "trigger":                 str(raw.get("trigger", ""))[:300] or None,
        "invalidation":            str(raw.get("invalidation", ""))[:300] or None,
        "position_pct":            float(raw["position_pct"]) if raw.get("position_pct") is not None else None,
        "timeframe":               str(raw.get("timeframe", ""))[:100] or None,
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
        client = _get_bq_client(project_id)
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
        client = _get_bq_client(project_id)
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


def load_previous_recs_block(project_id: str = PROJECT_ID) -> str:
    """
    查詢最近一個交易日的 QSREC 建議，抓取當前價格，
    回傳 Telegram HTML 格式的「上期建議追蹤」區塊。
    若無數據或 BigQuery 不可用，回傳空字串。
    """
    try:
        client = _get_bq_client(project_id)
        rows = list(client.query(f"""
            SELECT asset, direction, entry_price, target_price, stop_price, narrative, report_date
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date = (
                SELECT MAX(report_date) FROM `{RECOMMENDATIONS_TABLE}`
                WHERE report_date < CURRENT_DATE()
            )
            ORDER BY asset
        """).result())
    except Exception as e:
        logger.warning("load_previous_recs_block: BigQuery query failed: %s", e)
        return ""

    if not rows:
        return ""

    # 批次取得最新收盤價
    assets = {row["asset"] for row in rows}
    current_prices: dict[str, float | None] = {}
    for asset in assets:
        sym = _yf_symbol(asset)
        try:
            df = yf.download(sym, period="3d", interval="1d", progress=False, auto_adjust=True)
            if df is None or df.empty:
                current_prices[asset] = None
                continue
            close = df["Close"].dropna()
            if hasattr(close, "ndim") and close.ndim > 1:
                close = close.iloc[:, 0]
            current_prices[asset] = float(close.iloc[-1]) if not close.empty else None
        except Exception:
            current_prices[asset] = None

    lines = ["<b>【上期建議追蹤】</b>"]
    rep_date = str(rows[0]["report_date"])
    lines.append(f"<i>（{rep_date} 建議，現價對比）</i>")

    for row in rows:
        asset = row["asset"]
        direction = row["direction"]
        entry = float(row["entry_price"])
        target = float(row["target_price"])
        stop = float(row["stop_price"])
        current = current_prices.get(asset)

        if current is None:
            pnl_str = "N/A"
            status_icon = "❓"
        else:
            # 方向感知 P&L
            if direction == "LONG":
                pnl = (current - entry) / entry * 100
                hit_target = current >= target
                hit_stop = current <= stop
            else:
                pnl = (entry - current) / entry * 100
                hit_target = current <= target
                hit_stop = current >= stop

            # 防護：超過 ±1000% 視為資料異常（例如比值單位被當成 USD）
            if abs(pnl) > 1000:
                logger.warning(
                    "Skipping %s %s from tracking: P&L %+.1f%% exceeds sanity threshold "
                    "(entry=$%s current=$%s — likely unit/data error)",
                    asset, direction, pnl, entry, current,
                )
                pnl_str = "[資料異常]"
                status_icon = "⚠️"
            else:
                pnl_str = f"{pnl:+.1f}%"
                if hit_target:
                    status_icon = "✅"
                elif hit_stop:
                    status_icon = "🛑"
                elif pnl > 0:
                    status_icon = "📈"
                else:
                    status_icon = "📉"

        dir_icon = "🔼" if direction == "LONG" else "🔽"
        current_str = f"${current:,.2f}" if current else "N/A"
        lines.append(
            f"{status_icon} <b>${asset}</b> {dir_icon}{direction} | "
            f"進場 <code>${entry:,.2f}</code> → 現價 <code>{current_str}</code> | "
            f"<b>{pnl_str}</b>"
        )

    return "\n".join(lines)


def generate_performance_summary(project_id: str = PROJECT_ID, days: int = 30) -> str:
    """
    查詢過去 days 天的已關倉建議，生成 Telegram HTML 格式績效週報。
    無數據或查詢失敗時回傳空字串。
    """
    try:
        client = _get_bq_client(project_id)
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

