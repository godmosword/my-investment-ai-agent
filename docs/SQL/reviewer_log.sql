-- reviewer_log: LangGraph Reviewer Loop audit table
-- Written by bigquery_writer.write_reviewer_log (via degrade_node / llm_reviewer_node).
-- One row per graph run that went through the reviewer loop.

CREATE TABLE IF NOT EXISTS `{PROJECT}.market_data.reviewer_log` (
  run_id          STRING    OPTIONS(description='UUID per graph invocation (from graph_run_id state field)'),
  profile         STRING    OPTIONS(description='Report profile: full | lite | crypto-only'),
  track           STRING    OPTIONS(description='Research track: crypto | ai'),
  revision_count  INT64     OPTIONS(description='Number of trade_picker retries triggered by review failures'),
  python_fail_reasons  STRING OPTIONS(description='JSON array of reasons from python_validate_node failures'),
  llm_fail_reasons     STRING OPTIONS(description='JSON array of reasons from llm_reviewer_node failures'),
  degraded        BOOL      OPTIONS(description='True if hard cap (revision_count >= 2) triggered degrade_node'),
  final_trade_count    INT64 OPTIONS(description='Number of trades in trade_watch_final after review'),
  total_latency_ms     INT64 OPTIONS(description='Reviewer loop wall time in ms (0 if not tracked)'),
  created_at      TIMESTAMP OPTIONS(description='UTC timestamp of the write')
);

-- Weekly summary: degradation rate and average revision count per track
-- SELECT
--   DATE_TRUNC(DATE(created_at), WEEK) AS week,
--   track,
--   COUNT(*) AS total_runs,
--   COUNTIF(degraded) AS degraded_runs,
--   ROUND(100.0 * COUNTIF(degraded) / COUNT(*), 1) AS degradation_rate_pct,
--   ROUND(AVG(revision_count), 2) AS avg_revision_count,
--   ROUND(AVG(final_trade_count), 2) AS avg_final_trades
-- FROM `{PROJECT}.market_data.reviewer_log`
-- WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
-- GROUP BY 1, 2
-- ORDER BY 1 DESC, 2;
