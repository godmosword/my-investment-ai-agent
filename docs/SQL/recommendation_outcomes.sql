-- Recommendation outcome snapshots (Queue 41 Track Record, optional BigQuery).
-- Set RECOMMENDATION_OUTCOMES_TABLE=project.dataset.recommendation_outcomes in env.
-- scripts/mark_recommendations.py writes the same column set through
-- bigquery_writer.write_recommendation_outcome_rows.

-- Replace YOUR_PROJECT.YOUR_DATASET with values matching RECOMMENDATION_OUTCOMES_TABLE.
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.YOUR_DATASET.recommendation_outcomes` (
  signal_id STRING NOT NULL,
  as_of TIMESTAMP NOT NULL,
  quote_as_of STRING,
  asset STRING,
  direction STRING,
  category STRING,
  status STRING,
  entry_price FLOAT64,
  mark_price FLOAT64,
  exit_price FLOAT64,
  return_pct FLOAT64,
  outcome STRING,
  source STRING,
  created_at TIMESTAMP NOT NULL
);
