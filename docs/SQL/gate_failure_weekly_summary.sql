-- Gate 失敗週聚合（BL-08）— 表名須與 config.GATE_FAILURE_LOG_TABLE 一致（預設 PROJECT.market_data.gate_failure_log）
-- 用法：將 `my-project` 換成實際 GCP project id，或於 BQ 主控台選定專案後執行。

SELECT
  DATE(timestamp, 'Asia/Taipei') AS day_tpe,
  COUNT(*) AS failure_events,
  SUM(blocking_count) AS sum_blocking,
  SUM(warning_count) AS sum_warnings,
  APPROX_TOP_COUNT(fingerprint, 5) AS top_fingerprints
FROM `my-project.market_data.gate_failure_log`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 14 DAY)
GROUP BY 1
ORDER BY 1 DESC;
