-- notebooklm_cost_log: optional NotebookLM usage/cost audit table.
-- Written by bigquery_writer.write_notebooklm_cost_log when NOTEBOOKLM_COST_LOG_TABLE is set.

CREATE TABLE IF NOT EXISTS `{PROJECT}.market_data.notebooklm_cost_log` (
  timestamp       TIMESTAMP OPTIONS(description='UTC write timestamp'),
  run_id          STRING    OPTIONS(description='Graph/pipeline run identifier when available'),
  notebook_id     STRING    OPTIONS(description='NotebookLM notebook id used for the query'),
  ticker          STRING    OPTIONS(description='Ticker or company under filing analysis'),
  question_count  INT64     OPTIONS(description='Number of questions requested'),
  status          STRING    OPTIONS(description='success, skipped, disabled, degraded, or error'),
  latency_ms      INT64     OPTIONS(description='Measured wall-clock latency in ms'),
  cost_usd        FLOAT64   OPTIONS(description='Estimated direct cost, NULL when unknown'),
  metadata_json   STRING    OPTIONS(description='Small JSON metadata payload')
);
