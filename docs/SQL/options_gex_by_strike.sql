-- 每日 per-strike Gamma Exposure 分布（供 by-strike 柱狀圖 + gamma flip 分析）。
-- 由 options_bigquery_writer.write_gex_by_strike 寫入（與 gex_history 同次計算落地）。
-- 啟用：設環境變數 OPTIONS_GEX_BY_STRIKE_TABLE=PROJECT.market_data.options_gex_by_strike
-- 在 BigQuery 中執行一次；PROJECT 請替換為實際 GCP 專案 ID。
-- 慣例（D3 標準 dealer GEX）：calls 正、puts 負；net = call + put（每 1% 移動 USD）。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.options_gex_by_strike` (
  trade_date DATE NOT NULL,
  underlying STRING NOT NULL,
  spot_price FLOAT64,
  strike FLOAT64 NOT NULL,
  call_gex FLOAT64,
  put_gex FLOAT64,
  net_gex FLOAT64,
  as_of TIMESTAMP,
  computed_at TIMESTAMP
)
PARTITION BY trade_date
CLUSTER BY underlying
OPTIONS (
  description = "Q-Silicon Polygon per-strike GEX 分布（idempotent insert_id = sha1(gexstrike|trade_date|underlying|strike)）"
);
