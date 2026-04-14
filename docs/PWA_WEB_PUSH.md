# PWA Web Push（分階實作）

對齊 [`TODOS.md`](../TODOS.md) 隊列 **PWA Web Push** 與 Direction **1A**。

## 現況（API）

| 變數 | 行為 |
|------|------|
| `WEB_PUSH_ENABLED=0`（預設） | `POST /api/push/subscribe` → **501** |
| `WEB_PUSH_ENABLED=1` | 驗證 JSON body；**log-only**（`stored: false`） |
| `WEB_PUSH_ENABLED=1` 且 `WEB_PUSH_STORE=1` | 將訂閱摘要寫入 **程序內** `deque`（重啟即失；**非**生產持久化） |

實作見 [`web_push_store.py`](../web_push_store.py)、[`api.py`](../api.py) `POST /api/push/subscribe`。

## 前端（可選註冊）

- [`data-verification-ui/src/pushClient.js`](../data-verification-ui/src/pushClient.js)：若 `VITE_WEB_PUSH_REGISTER=1` 且瀏覽器支援 **PushManager**，於載入時呼叫 `POST /api/push/subscribe`（失敗不阻斷 UI）。
- 預設 **不** 自動註冊，避免開發者本機對後端送垃圾訂閱。

## 下一階（未實作）

1. **VAPID** 金鑰與 `pushManager.subscribe({ userVisibleOnly: true, applicationServerKey })`。
2. **持久化**（Redis／Firestore／BQ）與 **rate limit**、endpoint 去重。
3. **後端發送**（`pywebpush` 或等效）與訊息模板審核。

## 修訂紀錄

- **2026-04-14**：初版 — API 雙模式 + 前端可選註冊環境變數。
