"""
Q-Silicon Historical Data Backfill
====================================
一次性腳本：從公開 API 批次拉取過去 N 年的歷史指標數據，
寫入 BigQuery daily_metrics，讓回測引擎立刻擁有完整歷史數據。

數據來源：
  - BTC 收盤價  → CoinGecko 免費 API（無需 key）
  - DXY 指數    → FRED API（需 FRED_API_KEY）
  - MVRV Z-Score→ CryptoQuant API（需 CRYPTOQUANT_API_KEY，Advanced 方案）
  - ETF 資金流  → 無公開免費歷史 API，以 0 填充（未來可手動補入）
  - Risk Score  → 由 DXY、MVRV、BTC 日波動率回算（0~5 分）

執行方式：
    python backfill_data.py --years 3
    python backfill_data.py --years 1 --dry-run   # 僅預覽，不寫入 BQ
"""

from __future__ import annotations

import argparse
import logging
import os
import time
from datetime import date, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SCHEMA = [
    bigquery.SchemaField("timestamp",          "TIMESTAMP"),
    bigquery.SchemaField("dxy",                "FLOAT"),
    bigquery.SchemaField("etf_flow_millions",  "FLOAT"),
    bigquery.SchemaField("avg_risk_score",     "FLOAT"),
    bigquery.SchemaField("gpu_b200_price",     "FLOAT"),
    bigquery.SchemaField("grok_summary",       "STRING"),
    bigquery.SchemaField("gpt_summary",        "STRING"),
    bigquery.SchemaField("mvrv_z_score",       "FLOAT"),
]


# ══════════════════════════════════════════════════════════════════════════
# 數據抓取
# ══════════════════════════════════════════════════════════════════════════

def fetch_btc_price_history(days: int) -> pd.Series:
    """CoinGecko：BTC/USD 日收盤（免費，無需 key）。"""
    url = (
        f"https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        f"?vs_currency=usd&days={days}&interval=daily"
    )
    logging.info("CoinGecko: 拉取 BTC 價格 %d 天...", days)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    prices = resp.json().get("prices", [])
    if not prices:
        logging.warning("CoinGecko 回應無價格資料。")
        return pd.Series(dtype=float)
    df = pd.DataFrame(prices, columns=["ts_ms", "close"])
    df["date"] = pd.to_datetime(df["ts_ms"], unit="ms").dt.date
    return df.drop_duplicates("date").set_index("date")["close"]


def fetch_dxy_history(days: int) -> pd.Series:
    """FRED：DXY（DTWEXBGS）日線數據。"""
    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        logging.warning("FRED_API_KEY 未設定，DXY 歷史數據以 NaN 填充。")
        return pd.Series(dtype=float)

    start = (date.today() - timedelta(days=days)).isoformat()
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id":    "DTWEXBGS",   # Nominal Broad U.S. Dollar Index
        "api_key":      fred_key,
        "file_type":    "json",
        "observation_start": start,
        "sort_order":   "asc",
    }
    logging.info("FRED: 拉取 DXY 歷史 %d 天...", days)
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    if not obs:
        logging.warning("FRED 回應無 observations 資料。")
        return pd.Series(dtype=float)
    df = pd.DataFrame(obs)[["date", "value"]]
    df["date"]  = pd.to_datetime(df["date"]).dt.date
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.dropna().set_index("date")["value"]


def fetch_mvrv_history(days: int) -> pd.Series:
    """CryptoQuant：MVRV Z-Score 歷史數據（需 Advanced 方案）。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key:
        logging.warning("CRYPTOQUANT_API_KEY 未設定，MVRV 歷史數據以 NaN 填充。")
        return pd.Series(dtype=float)

    url = f"https://api.cryptoquant.com/v1/btc/market-data/mvrv-z-score?limit={days}&window=day"
    headers = {"Authorization": f"Bearer {api_key}"}
    logging.info("CryptoQuant: 拉取 MVRV Z-Score 歷史 %d 天...", days)
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 403:
            logging.warning(
                "CryptoQuant HTTP 403：MVRV Z-Score 需要 Advanced 方案，"
                "請至 https://cryptoquant.com/pricing 確認訂閱等級。MVRV 以 NaN 填充。"
            )
            return pd.Series(dtype=float)
        resp.raise_for_status()
        data = resp.json().get("result", {}).get("data", [])
        df = pd.DataFrame(data)
        if df.empty or "date" not in df.columns:
            logging.warning("CryptoQuant 回應無資料，MVRV 以 NaN 填充。")
            return pd.Series(dtype=float)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["mvrv"] = pd.to_numeric(df.get("mvrv_z_score", df.get("value")), errors="coerce")
        return df.dropna(subset=["mvrv"]).set_index("date")["mvrv"]
    except Exception as e:
        logging.error("CryptoQuant 拉取失敗：%s，MVRV 以 NaN 填充。", e)
        return pd.Series(dtype=float)


# ══════════════════════════════════════════════════════════════════════════
# 合併 & 寫入 BigQuery
# ══════════════════════════════════════════════════════════════════════════

def build_dataframe(days: int) -> pd.DataFrame:
    """合併各來源，生成可寫入 BigQuery 的 DataFrame。"""
    btc   = fetch_btc_price_history(days)
    time.sleep(1)  # CoinGecko rate limit
    dxy   = fetch_dxy_history(days)
    time.sleep(0.5)
    mvrv  = fetch_mvrv_history(days)

    # 以 BTC 日期為主索引，left join 其他指標
    df = pd.DataFrame({"btc_close": btc})
    df.index = pd.to_datetime(df.index)
    df.index.name = "date"

    if not dxy.empty:
        dxy.index = pd.to_datetime(dxy.index)
        df["dxy"] = dxy.reindex(df.index, method="ffill")  # FRED 有節假日缺口，用前值填補
    else:
        df["dxy"] = float("nan")

    if not mvrv.empty:
        mvrv.index = pd.to_datetime(mvrv.index)
        df["mvrv_z_score"] = mvrv.reindex(df.index)
    else:
        df["mvrv_z_score"] = float("nan")

    # 回算歷史 Risk Score（DXY + MVRV + BTC 日波動率，0~5 分）
    df["btc_return"] = df["btc_close"].pct_change().abs()
    risk = 2.5  # 中性基準
    risk = risk + (df["dxy"] > 104).astype(float) * 1.0 - (df["dxy"] <= 100).astype(float) * 0.8
    risk = risk + (df["mvrv_z_score"] > 5).astype(float) * 1.0 - (df["mvrv_z_score"] < 0).astype(float) * 0.8
    risk = risk + (df["btc_return"] > 0.05).astype(float) * 0.8
    df["avg_risk_score"] = risk.clip(0, 5).round(2)
    df = df.drop(columns=["btc_return"])

    # 無歷史來源的欄位以 None 填充
    df["etf_flow_millions"] = None
    df["gpu_b200_price"]    = None
    df["grok_summary"]      = None
    df["gpt_summary"]       = None

    df = df.reset_index()
    df["timestamp"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%dT12:00:00+00:00")
    df = df.drop(columns=["date", "btc_close"])

    logging.info("合併完成：%d 筆記錄，欄位：%s", len(df), list(df.columns))
    return df


def write_to_bigquery(df: pd.DataFrame, dry_run: bool = False) -> None:
    """將 DataFrame 寫入 BigQuery（去重：同一 timestamp 不重複插入）。"""
    client = bigquery.Client(project=PROJECT_ID)

    # 確保表存在且有正確 schema（schema migration）
    table_ref = bigquery.Table(METRICS_TABLE, schema=SCHEMA)
    client.create_table(table_ref, exists_ok=True)
    table = client.get_table(METRICS_TABLE)
    existing_cols = {f.name for f in table.schema}
    missing = [f for f in SCHEMA if f.name not in existing_cols]
    if missing:
        table.schema = list(table.schema) + missing
        client.update_table(table, ["schema"])
        logging.info("已補充缺失欄位：%s", [f.name for f in missing])

    if dry_run:
        logging.info("[DRY RUN] 不寫入 BigQuery，預覽前 5 筆：")
        print(df.head().to_string())
        return

    # 查詢已存在的 timestamp，避免重複寫入
    existing_ts_query = f"SELECT CAST(timestamp AS STRING) FROM `{METRICS_TABLE}`"
    try:
        existing = {row[0][:10] for row in client.query(existing_ts_query).result()}
    except Exception:
        existing = set()

    df["_date"] = df["timestamp"].str[:10]
    new_rows = df[~df["_date"].isin(existing)].drop(columns=["_date"])
    logging.info("現有紀錄日期數：%d，本次新增：%d 筆", len(existing), len(new_rows))

    if new_rows.empty:
        logging.info("沒有新數據需要寫入。")
        return

    # 批次寫入（load_table_from_dataframe 比 insert_rows_json 更高效）
    clean_df = new_rows.where(pd.notna(new_rows), None)
    try:
        job_config = bigquery.LoadJobConfig(
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
        )
        job = client.load_table_from_dataframe(clean_df, METRICS_TABLE, job_config=job_config)
        job.result()
        logging.info("成功批次寫入 %d 筆歷史數據到 BigQuery。", len(new_rows))
    except Exception as e:
        logging.warning("load_table_from_dataframe 失敗（%s），降級為 insert_rows_json。", e)
        rows = clean_df.to_dict(orient="records")
        errors = client.insert_rows_json(METRICS_TABLE, rows)
        if errors:
            logging.error("BigQuery 插入錯誤：%s", errors[:3])
        else:
            logging.info("成功寫入 %d 筆歷史數據到 BigQuery。", len(rows))


# ══════════════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Q-Silicon Historical Data Backfill")
    parser.add_argument("--years",   type=int,  default=3,     help="回補年數（預設 3 年）")
    parser.add_argument("--dry-run", action="store_true",       help="僅預覽數據，不寫入 BigQuery")
    args = parser.parse_args()

    days = args.years * 365
    logging.info("開始回補 %d 年（%d 天）歷史數據...", args.years, days)

    df = build_dataframe(days)
    write_to_bigquery(df, dry_run=args.dry_run)

    logging.info("回補完成！請執行 python backtest.py --days %d 驗證回測效果。", days)


if __name__ == "__main__":
    main()
