-- Portfolio holdings (optional BigQuery backend).
-- Set PORTFOLIO_STORE_BACKEND=bigquery and
-- PORTFOLIO_HOLDINGS_TABLE=project.dataset.portfolio_holdings to enable.
--
-- The default backend remains JSONL via PORTFOLIO_HOLDINGS_FILE.

CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.YOUR_DATASET.portfolio_holdings` (
  id STRING NOT NULL,
  symbol STRING NOT NULL,
  shares FLOAT64 NOT NULL,
  cost_basis FLOAT64 NOT NULL,
  opened_at DATE NOT NULL,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP
)
CLUSTER BY symbol
OPTIONS (
  description = "Q-Silicon portfolio holdings for Portal Portfolio board"
);
