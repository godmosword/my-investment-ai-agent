"""
Q-Silicon Historical Data Backfill
====================================
一次性腳本：從 FRED 與 CryptoQuant 拉取過去 1 年歷史指標，寫入 BigQuery daily_metrics。
供儀表板與回測使用。

執行方式：
    python backfill_data.py
    python backfill_data.py --dry-run   # 僅預覽，不寫入 BigQuery
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import date, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv
from google.cloud import bigquery

from config import PROJECT_ID, METRICS_TABLE

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# BigQuery schema（與 main.py extract_and_save_metrics 一致）
SCHEMA = [
    bigquery.SchemaField("timestamp", "TIMESTAMP"),
    bigquery.SchemaField("dxy", "FLOAT"),
    bigquery.SchemaField("etf_flow_millions", "FLOAT"),
    bigquery.SchemaField("avg_risk_score", "FLOAT"),
    bigquery.SchemaField("gpu_b200_price", "FLOAT"),
    bigquery.SchemaField("grok_summary", "STRING"),
    bigquery.SchemaField("gpt_summary", "STRING"),
    bigquery.SchemaField("mvrv_z_score", "FLOAT"),
]


def fetch_historical_fred(days: int = 365) -> pd.DataFrame:
    """使用 FRED API 拉取過去指定天數的 DXY 每日歷史數據。"""
    fred_key = os.getenv("FRED_API_KEY")
    if not fred_key:
        logging.warning("FRED_API_KEY 未設定，DXY 歷史數據將為空。")
        return pd.DataFrame(columns=["date", "dxy"])

    start = (date.today() - timedelta(days=days)).isoformat()
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "DTWEXBGS",  # DXY
        "api_key": fred_key,
        "file_type": "json",
        "observation_start": start,
        "sort_order": "asc",
    }

    print("[1/4] FRED: 拉取 DXY 歷史數據...")
    logging.info("FRED: 拉取 DXY 過去 %d 天...", days)

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        obs = resp.json().get("observations", [])
        if not obs:
            logging.warning("FRED 回應無 observations 資料。")
            return pd.DataFrame(columns=["date", "dxy"])

        df = pd.DataFrame(obs)[["date", "value"]]
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna().rename(columns={"value": "dxy"})
        print(f"      → 取得 {len(df)} 筆 DXY 紀錄")
        logging.info("FRED: 取得 %d 筆 DXY 紀錄", len(df))
        return df
    except Exception as e:
        logging.error("FRED 拉取失敗：%s", e)
        return pd.DataFrame(columns=["date", "dxy"])


def fetch_historical_cryptoquant(days: int = 365) -> pd.DataFrame:
    """使用 CryptoQuant API 拉取過去指定天數的 BTC MVRV Z-Score 歷史數據。"""
    api_key = os.getenv("CRYPTOQUANT_API_KEY")
    if not api_key:
        logging.warning("CRYPTOQUANT_API_KEY 未設定，MVRV 歷史數據將為空。")
        return pd.DataFrame(columns=["date", "mvrv_z_score"])

    url = f"https://api.cryptoquant.com/v1/btc/market-data/mvrv-z-score?limit={days}&window=day"
    headers = {"Authorization": f"Bearer {api_key}"}

    print("[2/4] CryptoQuant: 拉取 MVRV Z-Score 歷史數據...")
    logging.info("CryptoQuant: 拉取 MVRV Z-Score 過去 %d 天...", days)

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 403:
            logging.warning("CryptoQuant HTTP 403：MVRV 需 Advanced 方案，請確認訂閱等級。")
            return pd.DataFrame(columns=["date", "mvrv_z_score"])
        resp.raise_for_status()

        data = resp.json().get("result", {}).get("data", [])
        if not data:
            logging.warning("CryptoQuant 回應無資料。")
            return pd.DataFrame(columns=["date", "mvrv_z_score"])

        df = pd.DataFrame(data)
        if df.empty or "date" not in df.columns:
            logging.warning("CryptoQuant 回應格式異常。")
            return pd.DataFrame(columns=["date", "mvrv_z_score"])

        df["date"] = pd.to_datetime(df["date"]).dt.date
        mvrv_col = "mvrv_z_score" if "mvrv_z_score" in df.columns else "value"
        df["mvrv_z_score"] = pd.to_numeric(df[mvrv_col], errors="coerce")
        df = df[["date", "mvrv_z_score"]].dropna(subset=["mvrv_z_score"])
        print(f"      → 取得 {len(df)} 筆 MVRV Z-Score 紀錄")
        logging.info("CryptoQuant: 取得 %d 筆 MVRV Z-Score 紀錄", len(df))
        return df
    except Exception as e:
        logging.error("CryptoQuant 拉取失敗：%s", e)
        return pd.DataFrame(columns=["date", "mvrv_z_score"])


def build_daily_dataframe(dxy_df: pd.DataFrame, mvrv_df: pd.DataFrame) -> pd.DataFrame:
    """
    將 FRED DXY 與 CryptoQuant MVRV 對齊為 Daily 頻率 DataFrame。
    欄位：timestamp, dxy, mvrv_z_score, etf_flow_millions, avg_risk_score, gpu_b200_price, grok_summary, gpt_summary
    """
    print("[3/4] 對齊為 Daily 頻率 DataFrame...")

    # 建立完整日期範圍（過去一年每日）
    end = date.today()
    start = end - timedelta(days=365)
    all_dates = pd.date_range(start=start, end=end, freq="D").date

    df = pd.DataFrame({"date": all_dates})
    df = df.merge(dxy_df, on="date", how="left")
    df = df.merge(mvrv_df, on="date", how="left")

    # 前向填補缺失的 DXY（FRED 節假日無數據）
    df["dxy"] = df["dxy"].ffill().bfill()

    # 無法回溯的欄位：mock 填補
    df["etf_flow_millions"] = 0.0
    df["avg_risk_score"] = 2.5  # 中性值
    df["gpu_b200_price"] = None
    df["grok_summary"] = None
    df["gpt_summary"] = None

    # 產出 timestamp 欄位（UTC 中午）
    df["timestamp"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%dT12:00:00+00:00")
    df = df.drop(columns=["date"])

    # 確保欄位順序
    cols = [
        "timestamp", "dxy", "etf_flow_millions", "avg_risk_score",
        "gpu_b200_price", "grok_summary", "gpt_summary", "mvrv_z_score",
    ]
    df = df[[c for c in cols if c in df.columns]]

    print(f"      → 共 {len(df)} 筆日紀錄，欄位：{list(df.columns)}")
    logging.info("對齊完成：%d 筆記錄", len(df))
    return df


def write_to_bigquery(df: pd.DataFrame, dry_run: bool = False) -> None:
    """使用 WRITE_APPEND 寫入 BigQuery，避免覆蓋現有資料；跳過已存在的 timestamp。"""
    if dry_run:
        print("[4/4] [DRY RUN] 不寫入 BigQuery，預覽前 5 筆：")
        print(df.head().to_string())
        return

    print("[4/4] 寫入 BigQuery...")
    logging.info("開始寫入 BigQuery 表：%s", METRICS_TABLE)

    client = bigquery.Client(project=PROJECT_ID)

    # 確保表存在
    table_ref = bigquery.Table(METRICS_TABLE, schema=SCHEMA)
    client.create_table(table_ref, exists_ok=True)
    table = client.get_table(METRICS_TABLE)
    existing_cols = {f.name for f in table.schema}
    missing = [f for f in SCHEMA if f.name not in existing_cols]
    if missing:
        table.schema = list(table.schema) + missing
        client.update_table(table, ["schema"])
        logging.info("已補充缺失欄位：%s", [f.name for f in missing])

    # 只查本次回補區間內既有日期，避免全表掃描造成高成本。
    df_dates = pd.to_datetime(df["timestamp"], errors="coerce").dt.date
    start_date = df_dates.min()
    end_date = df_dates.max()
    existing: set[str] = set()
    if start_date is not None and end_date is not None:
        existing_ts_query = f"""
            SELECT DISTINCT DATE(timestamp) AS d
            FROM `{METRICS_TABLE}`
            WHERE DATE(timestamp) BETWEEN @start_date AND @end_date
        """
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("start_date", "DATE", start_date.isoformat()),
                    bigquery.ScalarQueryParameter("end_date", "DATE", end_date.isoformat()),
                ]
            )
            existing = {
                str(row["d"])
                for row in client.query(existing_ts_query, job_config=job_config).result()
                if row["d"] is not None
            }
        except Exception as e:
            logging.warning("backfill existing_ts query failed, assuming empty: %s", e)
            existing = set()

    df["_date"] = pd.to_datetime(df["timestamp"], errors="coerce").dt.strftime("%Y-%m-%d")
    new_rows = df[~df["_date"].isin(existing)].drop(columns=["_date"])

    print(f"      現有紀錄日期數：{len(existing)}，本次將新增：{len(new_rows)} 筆")
    logging.info("現有紀錄：%d 筆，本次新增：%d 筆", len(existing), len(new_rows))

    if new_rows.empty:
        print("      無新數據需要寫入。")
        logging.info("沒有新數據需要寫入。")
        return

    clean_df = new_rows.where(pd.notna(new_rows), None)
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        schema_update_options=[bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION],
    )

    try:
        job = client.load_table_from_dataframe(clean_df, METRICS_TABLE, job_config=job_config)
        job.result()
        print(f"      → 成功批次寫入 {len(new_rows)} 筆到 BigQuery。")
        logging.info("成功批次寫入 %d 筆歷史數據到 BigQuery。", len(new_rows))
    except Exception as e:
        logging.warning("load_table_from_dataframe 失敗，降級為 insert_rows_json：%s", e)
        rows = clean_df.to_dict(orient="records")
        errors = client.insert_rows_json(METRICS_TABLE, rows)
        if errors:
            logging.error("BigQuery 插入錯誤：%s", errors[:5])
        else:
            print(f"      → 成功寫入 {len(rows)} 筆到 BigQuery。")
            logging.info("成功寫入 %d 筆歷史數據到 BigQuery。", len(rows))


def main() -> None:
    parser = argparse.ArgumentParser(description="Q-Silicon 歷史數據回補（過去 1 年）")
    parser.add_argument("--dry-run", action="store_true", help="僅預覽數據，不寫入 BigQuery")
    parser.add_argument("--days", type=int, default=365, help="回補天數（預設 365）")
    args = parser.parse_args()

    print("=" * 60)
    print("Q-Silicon 歷史數據回補")
    print(f"  目標表：{PROJECT_ID}.market_data.daily_metrics")
    print(f"  回補天數：{args.days}")
    print("=" * 60)

    dxy_df = fetch_historical_fred(days=args.days)
    mvrv_df = fetch_historical_cryptoquant(days=args.days)

    df = build_daily_dataframe(dxy_df, mvrv_df)
    write_to_bigquery(df, dry_run=args.dry_run)

    print("=" * 60)
    print("回補完成！")
    print("=" * 60)
    logging.info("回補流程結束。")


if __name__ == "__main__":
    main()
