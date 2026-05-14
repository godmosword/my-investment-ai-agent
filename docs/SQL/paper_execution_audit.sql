-- Paper execution state transition audit (queue 28a, optional BigQuery).
-- Set PAPER_EXECUTION_AUDIT_TABLE=project.dataset.paper_execution_audit in env.
-- bigquery_writer.write_paper_execution_audit_row creates the table if missing
-- (same column set as below); use this DDL for manual provisioning if preferred.

-- Replace YOUR_PROJECT.YOUR_DATASET with values matching PAPER_EXECUTION_AUDIT_TABLE.
CREATE TABLE IF NOT EXISTS `YOUR_PROJECT.YOUR_DATASET.paper_execution_audit` (
  signal_id STRING NOT NULL,
  new_status STRING,
  reason STRING,
  quote_as_of STRING,
  asset STRING,
  source STRING,
  prev_status STRING,
  created_at TIMESTAMP NOT NULL
);
