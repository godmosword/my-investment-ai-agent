-- 每日 Gamma Exposure (GEX) 歷史，供畫圖與均值回歸分析。由 options_bigquery_writer.write_gex 寫入。
-- 啟用：設環境變數 OPTIONS_GEX_HISTORY_TABLE=PROJECT.market_data.options_gex_history
-- 在 BigQuery 中執行一次；PROJECT 請替換為實際 GCP 專案 ID。
-- 慣例（D3 標準 dealer GEX）：calls 正、puts 負；用 OI；乘數 100；含 spot^2 縮放；單位＝每 1% 移動的美元 gamma。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.options_gex_history` (
  trade_date DATE NOT NULL,
  underlying STRING NOT NULL,
  spot_price FLOAT64,
  total_gex FLOAT64,             -- call_gex + put_gex（每 1% 移動 USD）
  call_gex FLOAT64,
  put_gex FLOAT64,
  contracts_used INT64,
  as_of TIMESTAMP,
  method STRING,                 -- 'snapshot_greeks'
  computed_at TIMESTAMP
)
PARTITION BY trade_date
CLUSTER BY underlying
OPTIONS (
  description = "Q-Silicon Polygon GEX 每日歷史（idempotent insert_id = sha1(gex|trade_date|underlying)）"
);
