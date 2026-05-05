# 營運 Runbook：TODOS 隊列 18–21（Web Push／probe 雲端接線）

本檔為 **GCP／Redis／VAPID／staging 驗證** 的步驟清單；**不在此 repo 內自動執行**。完成雲端步驟後，請在 [`TODOS.md`](../TODOS.md) 將 **18–21** 勾選並於 [`CHANGELOG.md`](../CHANGELOG.md) 記 `### Ops`。

## 前置

- 具 **BigQuery Admin** 與 **Cloud Run／後端部署** 權限之專案（`GCP_PROJECT_ID`）。
- 本機已能呼叫後端 `POST /api/push/subscribe`（見 [`docs/PWA_WEB_PUSH.md`](PWA_WEB_PUSH.md)）。

## 18 — BigQuery DDL（Web Push + price probe）

1. 在 BigQuery 以專案替換 `{PROJECT}` 後執行：
   - [`docs/SQL/web_push_subscriptions.sql`](SQL/web_push_subscriptions.sql)
   - [`docs/SQL/price_probe_log.sql`](SQL/price_probe_log.sql)（若啟用 probe 寫入）
2. 設定環境變數（與 DDL 表名一致）：
   - `WEB_PUSH_SUBSCRIPTIONS_TABLE`（可沿用 `config.py` 預設或自訂）
   - 可選：`WEB_PUSH_AUDIT_TABLE`、`PRICE_PROBE_LOG_TABLE`
3. 重新部署後端；確認 `SKIP_BIGQUERY` 未阻擋寫入時之預期。

## 19 — Redis + `WEB_PUSH_REDIS_URL`

1. 建立可從後端連線之 **Redis**（Memorystore 或託管 Redis）。
2. 設定 `WEB_PUSH_REDIS_URL`（含 auth 之 URL，勿提交 repo）。
3. 呼叫 `POST /api/push/subscribe`（合法 body），回應 JSON 應含 **`backend: redis`**（或專案約定之欄位）；見 `PWA_WEB_PUSH.md`。

## 20 — VAPID 金鑰

1. 本機執行：`python3 scripts/vapid_generate.py`（或專案文件路徑）。
2. **Public** → PWA 建置環境（例如 `VITE_WEB_PUSH_VAPID_PUBLIC_KEY`／文件所列變數名）。
3. **Private** → **僅後端** secret／Secret Manager；**勿** commit。

## 21 — staging `test-send`

1. 設定 `WEB_PUSH_ADMIN_KEY`（後端）與已訂閱之瀏覽器端。
2. `POST /api/push/test-send`（Header 帶管理金鑰），小流量驗證裝置能收到通知。
3. 確認無誤後再放量；觀測見 `PWA_WEB_PUSH.md` 與 BQ audit（若有）。

## 驗收勾選

- [ ] 18 BQ 表已建且後端可寫（或已確認略過理由）
- [ ] 19 Redis 已接且 subscribe 回應正確
- [ ] 20 VAPID 已分離公私鑰且未外洩私鑰
- [ ] 21 staging test-send 成功

完成後：**TODOS 18–21** 打勾 + **CHANGELOG** 同日條目 +（可選）本檔末列「完成日期」。
