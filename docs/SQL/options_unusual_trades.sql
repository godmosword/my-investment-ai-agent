-- 不尋常期權流偵測記錄。由 options_bigquery_writer.write_unusual 寫入。
-- 啟用：設環境變數 OPTIONS_UNUSUAL_TRADES_TABLE=PROJECT.market_data.options_unusual_trades
-- 在 BigQuery 中執行一次；PROJECT 請替換為實際 GCP 專案 ID。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.options_unusual_trades` (
  trade_date DATE NOT NULL,
  underlying STRING NOT NULL,
  option_ticker STRING NOT NULL,
  signal_type STRING,            -- 'premium' | 'volume_oi' | 'sweep' | 'block' | 'concentration'
  score FLOAT64,                 -- 0..1 相對異常程度
  premium FLOAT64,
  volume INT64,
  open_interest INT64,
  rationale STRING,
  as_of TIMESTAMP,
  source STRING
)
PARTITION BY trade_date
CLUSTER BY underlying, signal_type
OPTIONS (
  description = "Q-Silicon Polygon 不尋常期權流（idempotent insert_id = sha1(unusual|trade_date|ticker|signal_type|rationale)）"
);
