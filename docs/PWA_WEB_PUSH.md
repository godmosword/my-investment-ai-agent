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

## 通知事件語意草案（T4b，文件先行）

在 **合規／產品拍板** 前僅列候選，避免預設開啟高噪音推播：

| 事件類型 | 建議預設 | 說明 |
|---------|----------|------|
| `validate_report` **blocking** 失敗（gate artifact 寫入） | 可考慮 **digest**（每日至多 1 則摘要） | 與 [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](GATE_FAILURE_HINT_WORKFLOW.md) 人審流程銜接；避免每條 issue 一推 |
| 執行意圖 `PENDING_REVIEW` → `APPROVED_FOR_PAPER` | 關閉或僅 in-app | 紙上仍非真下單；推播須與 OMS 真實事件分離 |
| War Room SSE bump（僅版本變更） | **不**直推使用者裝置 | 已由 PWA `EventSource` + React Query invalidate 覆蓋 |
| 管線成功交付 | 不推（或每週週報 opt-in） | 與 Telegram 主通道重複風險 |

實作 T4 時應再定：訂閱維度（per-user vs per-workspace）、靜音窗、與 **BigQuery** 事件表（若寫入）之 schema。

## 修訂紀錄

- **2026-04-14**：初版 — API 雙模式 + 前端可選註冊環境變數。
- **2026-04-14（T4b 草案）**：補「通知事件語意」表 — 與 [`TODOS.md`](../TODOS.md) Terminal T4b 對齊（僅規格、未改 runtime）。
