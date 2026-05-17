# PWA Web Push（T4a 生產級元件 + 分階營運）

對齊 [`TODOS.md`](../TODOS.md) 隊列 **PWA Web Push** 與 Direction **1A**。

## 依賴

- **`redis`** + **`WEB_PUSH_REDIS_URL`**：分散式訂閱儲存與 **Redis INCR** rate limit。
- **`pywebpush`** + **`WEB_PUSH_VAPID_PRIVATE_KEY`**（PEM）：後端發送。
- **`py-vapid`**：本機產鑰（[`scripts/vapid_generate.py`](../scripts/vapid_generate.py)）。

## API 行為

| 變數 | 行為 |
|------|------|
| `WEB_PUSH_ENABLED=0`（預設） | `POST /api/push/subscribe` → **501** |
| `WEB_PUSH_ENABLED=1` | 驗證 JSON；若**未**設 Redis 且**未**設 `WEB_PUSH_STORE=1` → **log-only**（`stored: false`） |
| `WEB_PUSH_REDIS_URL` | **優先**：訂閱寫入 Redis `HASH` `webpush:subscriptions`（field = endpoint **fingerprint**）；預設存 **完整** `endpoint`+`keys` JSON（供 `pywebpush`）。`WEB_PUSH_REDIS_SUMMARY_ONLY=1` 改為僅摘要（**無法**發送）。 |
| `WEB_PUSH_STORE=1`（無 Redis） | 程序內 dict；`WEB_PUSH_STORE_FULL_SUBSCRIPTION=1` 存完整 JSON 才可 `pywebpush` |
| `WEB_PUSH_SUBSCRIBE_RATE_PER_MIN` | 有 Redis 時用 **Redis 滾動視窗**；否則程序內 IP 計數。`0` 關閉。觸發時 `rate_limited: true` |
| `WEB_PUSH_BQ_PERSIST=1` | 每次訂閱（成功儲存後）**append** 一筆至 `WEB_PUSH_SUBSCRIPTIONS_TABLE`（須先建表，見 [`docs/SQL/web_push_subscriptions.sql`](SQL/web_push_subscriptions.sql)） |
| `WEB_PUSH_BQ_AUDIT=1` | append 至 `WEB_PUSH_AUDIT_TABLE`（預設 `…web_push_subscribe_audit`） |
| `WEB_PUSH_ADMIN_KEY` | 非空時啟用 `POST /api/push/test-send`（Header **`X-Web-Push-Admin-Key`**） |
| `WEB_PUSH_VAPID_PRIVATE_KEY` | PEM；與 `WEB_PUSH_VAPID_MAILTO`（`sub` claim，預設 `mailto:ops@example.com`） |
| `WEB_PUSH_SEND_MAX` | 單次 test-send 最多嘗試筆數（預設 **50**） |

### 端點

- `POST /api/push/subscribe` — 瀏覽器訂閱後上傳（見 [`pushClient.js`](../data-verification-ui/src/pushClient.js)）。
- `POST /api/push/test-send` — **管理用**測試推送 JSON `{title, body}`；須 **`WEB_PUSH_ADMIN_KEY`** + VAPID private + 已存完整訂閱。

## VAPID 產生

```bash
python scripts/vapid_generate.py
```

將輸出之 **public** 貼到 `VITE_WEB_PUSH_VAPID_PUBLIC_KEY`（與後端 `WEB_PUSH_VAPID_PUBLIC_KEY` 相同字串）；**private** 僅後端。

## BigQuery 表

見 [`SQL/web_push_subscriptions.sql`](SQL/web_push_subscriptions.sql)（`web_push_subscriptions` + `web_push_subscribe_audit`）。

## 前端（可選註冊）

- [`data-verification-ui/src/pushClient.js`](../data-verification-ui/src/pushClient.js)：`VITE_WEB_PUSH_REGISTER=1` 且 `VITE_WEB_PUSH_VAPID_PUBLIC_KEY` 非空時 `pushManager.subscribe` 並 `POST /api/push/subscribe`。

## 通知事件語意（T4b × Queue 34）

對齊 [`TODOS.md`](../TODOS.md) 隊列 **34**（排程型 digest／推送）與 Master Plan §0 Phase 3 已交付之 [`push-digest-tick.yml`](../.github/workflows/push-digest-tick.yml)（每 30 分鐘）、`event: price_alert` SSE、[`PriceAlertToaster.jsx`](../data-verification-ui/src/components/PriceAlertToaster.jsx)。

| 事件類型 | 通道 | 預設行為 | 去重／節流 |
|---------|------|----------|-----------|
| **`price_alert`** 觸發 | SSE → `PriceAlertToaster` + 可選 Telegram | `PRICE_ALERTS_TELEGRAM_ENABLED=1` 時推 Telegram | 以 `triggered_at` 自然去重（`push-digest-tick.yml`）；SSE 端額外受 `SSE_MAX_EVENTS_PER_SEC` 節流 |
| **Workspace digest** 摘要 | 唯讀 `GET /api/push/price-alerts/digest` | 由 PWA Workspace 主動拉取顯示 | 不主動推；避免重複通知 |
| **`validate_report`** blocking 失敗 | digest（內部） | 不對使用者推；走 [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](GATE_FAILURE_HINT_WORKFLOW.md) | 內部 digest |
| **意圖狀態變更**（PATCH） | 關閉或僅 in-app | 不外推 | 與真 OMS 分離 |
| **War Room SSE** `node_complete`／非告警事件 | 不外推 | PWA invalidate query | 受 `SSE_MAX_EVENTS_PER_SEC` 節流 |

**原則**：使用者面外部推送只走 `price_alert` 通道（SSE + 可選 Telegram + 排程 digest 三者共用同一去重鍵 `triggered_at`）；其他事件留 in-app／內部 digest，避免「同一事件被多通道同時喚醒」。

**新增推送類別流程**：（1）寫入本表新行 + 預設關；（2）若涉及新資料源走 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)；（3）staging `test-send` 與真 Push Service 驗證後再開生產 flag。

## 修訂紀錄

- **2026-04-14**：初版 — API 雙模式 + 前端可選註冊。
- **2026-04-14（T4b 草案）**：通知事件語意表。
- **2026-04-14（T4a 小步）**：程序內去重／IP limit。
- **2026-04-14（T4a 完整）**：Redis、`pywebpush`、`POST /api/push/test-send`、可選 BQ persist／audit、[`scripts/vapid_generate.py`](../scripts/vapid_generate.py)。
- **2026-05-16（T4b × Queue 34）**：通知事件語意改寫為 `price_alert` 主通道 + 共用 `triggered_at` 去重；新增推送類別流程入治理。
