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
import os
import re
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from google.cloud import bigquery

from config import PROJECT_ID, RECOMMENDATIONS_TABLE

logger = logging.getLogger(__name__)

# 動態資產清單：預設路徑為專案根目錄 assets_config.json，可由 ASSETS_CONFIG_PATH 覆寫
_DEFAULT_ASSETS_PATH = Path(__file__).resolve().parent / "assets_config.json"
_CRYPTO_ASSETS_CACHE: set[str] | None = None

# ── BigQuery client singleton ──────────────────────────────────────────────────
_bq_clients: dict[str, bigquery.Client] = {}


def _get_bq_client(project_id: str = PROJECT_ID) -> bigquery.Client:
    """Module-level BigQuery client singleton（按 project_id 快取，節省連線開銷）。"""
    if project_id not in _bq_clients:
        _bq_clients[project_id] = bigquery.Client(project=project_id)
    return _bq_clients[project_id]


# ── 建議 JSON 區塊標記 ─────────────────────────────────────────────────────────
_QSREC_RE = re.compile(r'\[QSREC_START\]\s*([\s\S]*?)\[QSREC_END\]')

# 已知 crypto 代號（寫死 fallback），供 _load_crypto_assets() 無法讀取設定時使用
_CRYPTO_ASSETS_DEFAULT: set[str] = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "AVAX", "LINK", "DOT", "MATIC",
    "ARB", "OP", "SUI", "APT", "INJ", "TIA", "NEAR", "ATOM", "DOGE", "ADA",
}


def _load_crypto_assets() -> set[str]:
    """從 assets_config.json 讀取 crypto 清單；缺失或錯誤時回傳預設 set。"""
    global _CRYPTO_ASSETS_CACHE
    if _CRYPTO_ASSETS_CACHE is not None:
        return _CRYPTO_ASSETS_CACHE
    path = os.getenv("ASSETS_CONFIG_PATH")
    if path:
        path = Path(path)
    else:
        path = _DEFAULT_ASSETS_PATH
    if not path.exists():
        logger.debug("Assets config not found at %s, using default crypto set.", path)
        _CRYPTO_ASSETS_CACHE = _CRYPTO_ASSETS_DEFAULT
        return _CRYPTO_ASSETS_CACHE
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data.get("crypto"), list):
            _CRYPTO_ASSETS_CACHE = {str(a).upper().strip() for a in data["crypto"] if a}
            return _CRYPTO_ASSETS_CACHE
    except Exception as e:
        logger.warning("Failed to load assets config from %s: %s. Using default.", path, e)
    _CRYPTO_ASSETS_CACHE = _CRYPTO_ASSETS_DEFAULT
    return _CRYPTO_ASSETS_CACHE


def _get_crypto_assets() -> set[str]:
    """取得目前生效的 crypto 資產 set（供 _yf_symbol、_validate_rec 等使用）。"""
    return _load_crypto_assets()

# 各資產合理進場價格範圍（用於防止 LLM 輸出單位錯誤的資料）
# 例如：BTC/SOL 比值 ($815) 被誤記為 BTC USD 進場價
# 上限設為現價約 3–5 倍以容納黑天鵝牛市行情，每季複審一次
_PRICE_SANITY_RANGES: dict[str, tuple[float, float]] = {
    "BTC":  (10_000, 500_000),
    "ETH":  (500,    20_000),
    "SOL":  (10,     2_000),
    "BNB":  (100,    5_000),
    "XRP":  (0.1,    50),
    "AVAX": (5,      500),
    "DOGE": (0.01,   5),
    "NVDA": (50,     5_000),
    "MSFT": (100,    1_000),
    "AAPL": (100,    600),
    "TSLA": (100,    3_000),
    "GOOGL": (80,    500),
    "AMZN": (100,    500),
    "META": (100,    2_000),
}

# 依市場模式限制單筆建議倉位（%）
_REGIME_POSITION_CAP: dict[str, float] = {
    "risk_off": 5.0,
    "neutral": 10.0,
    "risk_on": 15.0,
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
    bigquery.SchemaField("regime_at_signal",         "STRING"),
    bigquery.SchemaField("rr_ratio",                 "FLOAT"),
    bigquery.SchemaField("max_drawdown_pct",         "FLOAT"),
    bigquery.SchemaField("expected_win_rate",        "FLOAT"),
    bigquery.SchemaField("expected_value_pct",       "FLOAT"),
    bigquery.SchemaField("signal_score",             "FLOAT"),
]


def _yf_symbol(asset: str) -> str:
    """將代幣/股票代號轉換為 yfinance 查詢用的 symbol。"""
    a = asset.upper().strip("$")
    return f"{a}-USD" if a in _get_crypto_assets() else a


def canonical_asset_key(asset: str) -> str:
    """BigQuery 去重與 PARTITION BY 用：大寫、去 $、去空白、比值 '-' 統一為 '/'。"""
    a = str(asset or "").upper().strip().replace("$", "").replace(" ", "")
    a = a.replace("-", "/")
    return a or "UNKNOWN"


def _parse_pair_asset(asset: str) -> tuple[str, str] | None:
    """若 asset 為兩幣比值（如 BTC/SOL、BTC-SOL），回傳 (base, quote) 代號。"""
    a = asset.upper().strip().replace("$", "").replace(" ", "")
    for sep in ("/", "-", "／"):
        if sep in a:
            left, right = a.split(sep, 1)
            left, right = left.strip(), right.strip()
            crypto = _get_crypto_assets()
            if left in crypto and right in crypto:
                return left, right
    return None


def _last_closes_from_yf_df(df: pd.DataFrame | None, symbols: list[str]) -> dict[str, float | None]:
    """從 yfinance 回傳的 OHLCV DataFrame 萃取各 ticker 最近有效收盤價。"""
    out: dict[str, float | None] = {s: None for s in symbols}
    if df is None or df.empty or not symbols:
        return out
    close = df.get("Close")
    if close is None:
        return out
    # 新版 yfinance：單檔或多檔常為 MultiIndex，df['Close'] 多為 DataFrame（每欄一 ticker）
    if isinstance(close, pd.Series):
        ser = close.dropna()
        if not ser.empty:
            out[symbols[0]] = float(ser.iloc[-1])
        return out
    if isinstance(close, pd.DataFrame):
        for sym in symbols:
            col = sym if sym in close.columns else None
            if col is None:
                sup = sym.upper()
                for c in close.columns:
                    if str(c).upper() == sup:
                        col = c
                        break
            if col is None:
                continue
            ser = close[col].dropna()
            out[sym] = float(ser.iloc[-1]) if not ser.empty else None
        return out
    return out


def _yf_last_close_single(sym: str) -> float | None:
    """單一 yahoo symbol 下載（批次缺值時 fallback，避免整批失敗無價格）。"""
    try:
        df = yf.download(
            sym,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        m = _last_closes_from_yf_df(df, [sym])
        return m.get(sym)
    except Exception as e:
        logger.warning("yfinance close failed for %s: %s", sym, e)
        return None


def _yf_last_closes_batch(symbols: list[str]) -> dict[str, float | None]:
    """
    一次請求抓取多個 yahoo symbol 的最近收盤，降低 OPEN 建議追蹤時的 N+1 HTTP。
    批次仍缺之 symbol 再個別 fallback。
    """
    syms = list(dict.fromkeys(s.strip() for s in symbols if s and str(s).strip()))
    out: dict[str, float | None] = {s: None for s in syms}
    if not syms:
        return out
    try:
        df = yf.download(
            syms,
            period="5d",
            interval="1d",
            progress=False,
            auto_adjust=True,
            threads=False,
        )
        out = _last_closes_from_yf_df(df, syms)
    except Exception as e:
        logger.warning("yfinance batch download failed: %s", e)

    for sym in syms:
        if out.get(sym) is None:
            out[sym] = _yf_last_close_single(sym)
    return out


def _current_prices_for_assets(assets: Iterable[str]) -> dict[str, float | None]:
    """為多筆建議資產批次取現價（單幣或 crypto 比值）；內部合併 yahoo symbol 後僅少數次下載。"""
    ordered = list(dict.fromkeys(assets))
    legs: list[str] = []
    pair_legs: dict[str, tuple[str, str]] = {}
    single_sym: dict[str, str] = {}

    for asset in ordered:
        parsed = _parse_pair_asset(asset)
        if parsed:
            left, right = parsed
            sl, sr = _yf_symbol(left), _yf_symbol(right)
            pair_legs[asset] = (sl, sr)
            legs.extend([sl, sr])
        else:
            s = _yf_symbol(asset)
            single_sym[asset] = s
            legs.append(s)

    uniq_legs = list(dict.fromkeys(legs))
    close_by_sym = _yf_last_closes_batch(uniq_legs)

    out: dict[str, float | None] = {}
    for asset in ordered:
        if asset in pair_legs:
            sl, sr = pair_legs[asset]
            pl, pr = close_by_sym.get(sl), close_by_sym.get(sr)
            if pl is None or pr is None or pr <= 0:
                out[asset] = None
            else:
                out[asset] = round(pl / pr, 4)
        else:
            out[asset] = close_by_sym.get(single_sym[asset])
    return out


def _current_price_for_asset(asset: str) -> float | None:
    """單幣或比值建議的追蹤用現價（內部仍走批次路徑，僅一檔時一次下載）。"""
    return _current_prices_for_assets([asset]).get(asset)


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


def _detect_regime_from_report(report_text: str) -> str:
    """從報告文字偵測 regime，預設 neutral。"""
    m = re.search(r'【今日市場模式】\s*(risk_on|risk_off|neutral)', report_text, re.IGNORECASE)
    return m.group(1).lower() if m else "neutral"


def _compute_trade_metrics(entry: float, target: float, stop: float, direction: str, confidence: int) -> dict[str, float]:
    """計算 R:R、最大回撤、預期勝率、期望值、訊號分數。"""
    if direction == "LONG":
        reward = max(0.0, (target - entry) / entry * 100)
        risk = max(0.0, (entry - stop) / entry * 100)
    else:
        reward = max(0.0, (entry - target) / entry * 100)
        risk = max(0.0, (stop - entry) / entry * 100)

    rr_ratio = round(reward / risk, 3) if risk > 0 else 0.0
    max_drawdown_pct = round(-risk, 2)
    expected_win_rate = 40.0 + confidence * 8.0  # 1~4 星 => 48~72%
    expected_value_pct = round((expected_win_rate / 100) * reward - (1 - expected_win_rate / 100) * risk, 2)

    # 0~100：confidence(40%) + R:R(35%) + 執行完整度(25%)
    conf_score = min(100.0, confidence * 25.0)
    rr_score = min(100.0, rr_ratio * 25.0)
    execution_score = 50.0  # 預設；若 trigger/invalidation/timeframe 完整，於 _validate_rec 後補齊
    signal_score = round(conf_score * 0.40 + rr_score * 0.35 + execution_score * 0.25, 1)

    return {
        "rr_ratio": rr_ratio,
        "max_drawdown_pct": max_drawdown_pct,
        "expected_win_rate": expected_win_rate,
        "expected_value_pct": expected_value_pct,
        "signal_score": signal_score,
    }


def _has_valid_trade_structure(entry: float, target: float, stop: float, direction: str) -> bool:
    """檢查 LONG/SHORT 的目標與停損方向是否合理。"""
    if direction == "LONG":
        return target > entry and stop < entry
    return target < entry and stop > entry


def _validate_rec(raw: dict, report_date: str, regime_at_signal: str) -> dict | None:
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

    # 拒絕非正價格（$0.00 / 負值）：LLM 解析比值對或格式錯誤時常見
    if entry <= 0 or target <= 0 or stop <= 0:
        logger.warning(
            "Skipping %s %s: price fields must be positive (entry=%s target=%s stop=%s)",
            asset, direction, entry, target, stop,
        )
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

    if not _has_valid_trade_structure(entry, target, stop, direction):
        logger.warning(
            "Skipping %s %s: invalid trade structure (entry=%s target=%s stop=%s)",
            asset, direction, entry, target, stop,
        )
        return None

    category = str(raw.get("category", "CRYPTO")).upper()
    if category not in ("CRYPTO", "EQUITY"):
        category = (
            "CRYPTO"
            if asset in _get_crypto_assets() or _parse_pair_asset(asset)
            else "EQUITY"
        )

    confidence = max(1, min(4, int(raw.get("confidence", 3))))
    trigger = str(raw.get("trigger", ""))[:300] or None
    invalidation = str(raw.get("invalidation", ""))[:300] or None
    timeframe = str(raw.get("timeframe", ""))[:100] or None

    position_pct_raw = raw.get("position_pct")
    position_pct = float(position_pct_raw) if position_pct_raw is not None else None
    cap = _REGIME_POSITION_CAP.get(regime_at_signal, 10.0)
    if position_pct is None:
        # 依 regime 與信心給保守預設倉位，避免遺漏時無法落地執行
        position_pct = round(min(cap, 2.0 + confidence * 1.5), 2)
    if position_pct <= 0:
        logger.warning("Skipping %s %s: non-positive position_pct=%s", asset, direction, position_pct)
        return None
    if position_pct is not None and position_pct > cap:
        logger.info(
            "Clamping %s position_pct %.2f%% -> %.2f%% due to regime=%s",
            asset, position_pct, cap, regime_at_signal,
        )
        position_pct = cap

    metrics = _compute_trade_metrics(entry, target, stop, direction, confidence)
    if metrics["rr_ratio"] < 0.8:
        logger.warning(
            "Skipping %s %s: rr_ratio %.3f below minimum threshold 0.8",
            asset, direction, metrics["rr_ratio"],
        )
        return None
    execution_complete = all([trigger, invalidation, timeframe])
    if execution_complete:
        metrics["signal_score"] = round(min(100.0, metrics["signal_score"] + 12.5), 1)
    else:
        metrics["signal_score"] = round(max(0.0, metrics["signal_score"] - 10.0), 1)

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
        "confidence":              confidence,
        "narrative":               str(raw.get("narrative", ""))[:500],
        "category":                category,
        "status":                  "OPEN",
        "exit_price":              None,
        "exit_date":               None,
        "pnl_pct":                 None,
        "days_held":               None,
        "created_at":              datetime.now(timezone.utc).isoformat(),
        # Phase 3 新欄位
        "trigger":                 trigger,
        "invalidation":            invalidation,
        "position_pct":            position_pct,
        "timeframe":               timeframe,
        "regime_at_signal":        regime_at_signal,
        "rr_ratio":                metrics["rr_ratio"],
        "max_drawdown_pct":        metrics["max_drawdown_pct"],
        "expected_win_rate":       metrics["expected_win_rate"],
        "expected_value_pct":      metrics["expected_value_pct"],
        "signal_score":            metrics["signal_score"],
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

    regime_at_signal = _detect_regime_from_report(report_text)
    raw_recs = extract_recommendations_json(report_text)
    recs = [r for raw in raw_recs if (r := _validate_rec(raw, report_date, regime_at_signal)) is not None]

    # P2 衝突偵測：同日同資產出現 LONG 與 SHORT，記警告（可能是 LLM 輸出矛盾）
    _direction_seen: dict[str, str] = {}
    for row in recs:
        key = canonical_asset_key(row["asset"])
        prev_dir = _direction_seen.get(key)
        if prev_dir is not None and prev_dir != row["direction"]:
            logger.warning(
                "Conflicting directions for %s on %s: %s vs %s — keeping last entry only",
                key, report_date, prev_dir, row["direction"],
            )
        _direction_seen[key] = row["direction"]

    # 同日同 canonical asset 只保留最後一筆（避免 QSREC 陣列或重跑造成多進場價）
    _by_key: dict[str, dict] = {}
    _order: list[str] = []
    for row in recs:
        key = canonical_asset_key(row["asset"])
        if key not in _by_key:
            _order.append(key)
        _by_key[key] = row
    recs = [_by_key[k] for k in _order]

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

    # 批次抓取最新收盤價（合併 yahoo symbol，減少 HTTP 次數）
    assets = [row["asset"] for row in rows]
    prices = _current_prices_for_assets(assets)
    for asset in set(assets):
        if prices.get(asset) is None:
            logger.warning("Price fetch failed for %s", asset)

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
        # 同一 report_date + canonical asset + direction 可能有多筆（同日重跑）；
        # 僅保留一筆：優先 OPEN，否則最新 created_at，避免同標同方向多進場價洗版。
        rows = list(client.query(f"""
            WITH last_day AS (
              SELECT MAX(report_date) AS d
              FROM `{RECOMMENDATIONS_TABLE}`
              WHERE report_date < CURRENT_DATE()
            ),
            normalized AS (
              SELECT
                asset,
                direction,
                entry_price,
                target_price,
                stop_price,
                narrative,
                report_date,
                status,
                created_at,
                REGEXP_REPLACE(
                  REGEXP_REPLACE(
                    UPPER(TRIM(REGEXP_REPLACE(asset, '^\\\\$+', ''))),
                    '\\\\s+',
                    ''
                  ),
                  '-',
                  '/'
                ) AS canon_asset,
                UPPER(COALESCE(direction, '')) AS canon_dir
              FROM `{RECOMMENDATIONS_TABLE}`
              WHERE report_date = (SELECT d FROM last_day)
            ),
            ranked AS (
              SELECT
                asset,
                direction,
                entry_price,
                target_price,
                stop_price,
                narrative,
                report_date,
                canon_asset,
                ROW_NUMBER() OVER (
                  PARTITION BY report_date, canon_asset, canon_dir
                  ORDER BY
                    CASE WHEN status = 'OPEN' THEN 0 ELSE 1 END,
                    COALESCE(created_at, TIMESTAMP(report_date)) DESC
                ) AS rn
              FROM normalized
            )
            SELECT asset, direction, entry_price, target_price, stop_price, narrative, report_date
            FROM ranked
            WHERE rn = 1
            ORDER BY canon_asset ASC, direction ASC
        """).result())
    except Exception as e:
        logger.warning("load_previous_recs_block: BigQuery query failed: %s", e)
        return ""

    if not rows:
        return ""

    # 批次取得最新收盤價（合併 symbol 一次 yfinance 請求為主）
    assets = [row["asset"] for row in rows]
    current_prices = _current_prices_for_assets(assets)

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

            # 防護：超過 ±1000% 視為資料異常（例如比值單位被當成 USD），直接跳過不顯示
            if abs(pnl) > 1000:
                logger.warning(
                    "Skipping %s %s from tracking: P&L %+.1f%% exceeds sanity threshold "
                    "(entry=$%s current=$%s — likely unit/data error)",
                    asset, direction, pnl, entry, current,
                )
                continue

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

        pnl_rows = list(client.query(f"""
            SELECT report_date, created_at, pnl_pct, regime_at_signal
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
              AND status != 'OPEN'
              AND pnl_pct IS NOT NULL
            ORDER BY report_date, created_at
        """).result())

        regime_rows = list(client.query(f"""
            SELECT
                COALESCE(regime_at_signal, 'unknown') AS regime,
                COUNT(*) AS cnt,
                ROUND(AVG(pnl_pct), 2) AS avg_pnl,
                ROUND(SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) / COUNT(*) * 100, 1) AS win_rate
            FROM `{RECOMMENDATIONS_TABLE}`
            WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)
              AND status != 'OPEN'
              AND pnl_pct IS NOT NULL
            GROUP BY regime
            ORDER BY cnt DESC
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

    pnl_values = [float(r["pnl_pct"]) for r in pnl_rows]
    gross_profit = sum(p for p in pnl_values if p > 0)
    gross_loss = abs(sum(p for p in pnl_values if p < 0))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else None
    expectancy = round(sum(pnl_values) / len(pnl_values), 2) if pnl_values else 0.0

    # 以已平倉單序列近似計算 max drawdown（乘法複利曲線，範圍 0–100%）
    # 原先用加法累加 P&L，導致 peak-to-trough 可超過 -100%，顯示失真。
    # 改為複利淨值曲線：每筆以 (1 + p/100) 相乘，dd 為相對回撤，上限 100%。
    equity = 100.0
    peak = 100.0
    max_dd = 0.0
    for p in pnl_values:
        equity *= (1.0 + p / 100.0)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100.0
        if dd > max_dd:
            max_dd = dd
    max_dd = round(max_dd, 2)

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
        f"· Profit Factor：<code>{profit_factor if profit_factor is not None else 'N/A'}</code> | Expectancy：<code>{expectancy:+.2f}%</code>",
        f"· Max Drawdown（closed-trade curve）：<code>-{max_dd:.2f}%</code>",
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

    if regime_rows:
        lines.append("────────────")
        lines.append("<b>🧭 Regime 分層績效</b>")
        for r in regime_rows:
            lines.append(
                f"· {r['regime']}: <code>{r['cnt']}</code> 筆 | 勝率 <code>{r['win_rate']}%</code> | 均損益 <code>{(r['avg_pnl'] or 0.0):+.2f}%</code>"
            )
    return "\n".join(lines)

