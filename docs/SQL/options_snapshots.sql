-- Options 每日/每小時快照（OI、IV、Greeks、量）。由 options_bigquery_writer.write_snapshots 寫入。
-- 啟用：設環境變數 OPTIONS_SNAPSHOTS_TABLE=PROJECT.market_data.options_snapshots
-- 在 BigQuery 中執行一次；PROJECT 請替換為實際 GCP 專案 ID。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.options_snapshots` (
  trade_date DATE NOT NULL,
  underlying STRING NOT NULL,
  option_ticker STRING NOT NULL,
  expiration DATE,
  strike FLOAT64,
  contract_type STRING,          -- 'call' | 'put'
  open_interest INT64,
  implied_volatility FLOAT64,
  day_volume INT64,
  last_price FLOAT64,
  gamma FLOAT64,
  delta FLOAT64,
  as_of TIMESTAMP,
  source STRING
)
PARTITION BY trade_date
CLUSTER BY underlying, expiration, contract_type
OPTIONS (
  description = "Q-Silicon Polygon options 每日快照（idempotent insert_id = sha1(snap|trade_date|option_ticker)）"
);
