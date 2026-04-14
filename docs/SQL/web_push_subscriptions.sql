-- Web Push 訂閱持久化（T4a）：由 `WEB_PUSH_BQ_PERSIST=1` 時 `web_push_store` 寫入。
-- 在 BigQuery 中執行一次；`PROJECT` 請替換為實際 GCP 專案 ID。

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.web_push_subscriptions` (
  endpoint_fingerprint STRING NOT NULL,
  endpoint_prefix STRING,
  has_p256dh BOOL,
  has_auth BOOL,
  last_client_ip STRING,
  first_seen TIMESTAMP NOT NULL,
  last_seen TIMESTAMP NOT NULL
)
PARTITION BY DATE(last_seen)
OPTIONS (
  description = "Q-Silicon PWA Web Push subscriptions (endpoint fingerprint; no full URL in BQ by default)"
);

CREATE TABLE IF NOT EXISTS `PROJECT.market_data.web_push_subscribe_audit` (
  event_ts TIMESTAMP NOT NULL,
  endpoint_fingerprint STRING,
  client_ip STRING,
  stored BOOL,
  deduped BOOL,
  rate_limited BOOL,
  detail STRING
)
PARTITION BY DATE(event_ts)
OPTIONS (
  description = "Append-only audit of POST /api/push/subscribe (compliance / abuse review)"
);
