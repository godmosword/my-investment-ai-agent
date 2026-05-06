-- daily_brief_report_json: optional full DailyBriefReport JSON archive.
-- Written by bigquery_writer.write_daily_brief_json when DAILY_BRIEF_JSON_BQ_TABLE is set.

CREATE TABLE IF NOT EXISTS `{PROJECT}.market_data.daily_brief_report_json` (
  timestamp       TIMESTAMP OPTIONS(description='UTC write timestamp'),
  report_date     DATE      OPTIONS(description='Report date used by API/PWA lookup'),
  profile         STRING    OPTIONS(description='REPORT_PROFILE at persistence time'),
  run_id          STRING    OPTIONS(description='logs/run_YYYYMMDD_HHMMSS identifier'),
  source          STRING    OPTIONS(description='pipeline, replay, or test writer source'),
  payload_json    STRING    OPTIONS(description='DailyBriefReport model_dump_json payload'),
  payload_sha256  STRING    OPTIONS(description='SHA-256 of payload_json for dedup/audit')
);
