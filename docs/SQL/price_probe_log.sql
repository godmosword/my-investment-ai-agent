-- 實盤 BQ vs yfinance 觀測：`scripts/symbol_price_probe.py` 於 `PRICE_PROBE_WRITE_BQ=1` 時寫入。
-- `PROJECT` 請替換為實際 GCP 專案 ID。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.price_alignment_probe_log` (
  probe_ts TIMESTAMP NOT NULL,
  symbol STRING NOT NULL,
  bq_metric_field STRING,
  bq_value FLOAT64,
  bq_as_of TIMESTAMP,
  yf_ohlc_close FLOAT64,
  yf_ohlc_bar_date STRING,
  yf_quote_last FLOAT64,
  abs_diff FLOAT64,
  rel_diff FLOAT64,
  aligned BOOL,
  note STRING
)
PARTITION BY DATE(probe_ts)
OPTIONS (
  description = "Scheduled or manual probe: BigQuery daily_metrics scalar vs yfinance OHLC/quote"
);
