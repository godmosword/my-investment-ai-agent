# ADR — Command Bar 權限與資料源邊界（Queue 29）

**狀態**：v1（2026-05-16，agent-side 草稿；如需擴張 multi-tenant 或 JWT，另開新 ADR）
**範圍**：[`TerminalCommandBar.jsx`](../data-verification-ui/src/components/TerminalCommandBar.jsx) 之指令分類與後端 `/api/*` 邊界。
**對齊**：[`docs/architecture/Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) §0 Phase 2、[`TODOS.md`](../TODOS.md) 隊列 **29**、[`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)、[`docs/PORTAL_SHIP_CHECKLIST.md`](PORTAL_SHIP_CHECKLIST.md)。

## 1. 為何寫這一頁

Command Bar 已支援 5 板塊跳轉、`SYM <GO>`、`WATCH`、`RUN Crew`、recent chips、`Ctrl/Cmd+K`。當被問到「未來要不要加更多 Bloomberg 感」時，先把**現有指令的權限分類**寫成一頁書面契約，避免後續切片無意間把唯讀指令送進需金鑰的端點，或反向把寫入指令做成匿名可呼叫。

## 2. 指令分類（v1）

| 類別 | 行為 | 後端 | 金鑰需求 | 範例 |
|------|------|------|----------|------|
| **N — 純前端導覽** | 路由跳轉、focus 設定 | 無 | 無 | `NEWS`、`PORTFOLIO`、`AAPL GO` |
| **R — 唯讀查詢** | 讀取 quote／snapshot／report／digest | `/api/symbols/*`、`/api/run-crew/status`、`/api/reports/*`、`/api/push/price-alerts/digest` | 由 `QSILICON_MASTER_KEY`（若設）統一中介層處理；前端送 `X-Q-Silicon-Key` | `WATCH AAPL`（讀 SSE quote）、Crew HUD |
| **W — 觸發後端動作** | 提交運算或寫入 | `POST /api/run-crew`、`POST /api/push/test-send`、`PATCH /api/execution-intents/*` | 一律走 master key；`test-send` 另需 `WEB_PUSH_ADMIN_KEY` | `RUN`、紙上意圖 PATCH |
| **S — SSE 連線** | EventSource | `GET /api/stream/war-room` | 短期 token（[`sse_token.py`](../sse_token.py)，2026-05-16 交付） | `WATCH` 後背景連線 |

**結論**：master key 模型對自用足夠；現況 N/R/W/S 已分層，**無需** 在 Command Bar 新增「免金鑰公開查詢」端點。

## 3. 紅線

1. **不**新增匿名（無 `X-Q-Silicon-Key`）的 W 類指令。
2. **不**為了「Bloomberg 感」自動拉付費即時資料；任何新資料源走 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md) 審核流程後再進 Command Bar。
3. SSE 一律經短期 token；不接受長期 query string 金鑰。
4. Telegram HTML 白名單與 [`validate_report`](../report_html_gates.py) 不因 Command Bar 改動而放寬。

## 4. 升級路徑（不在本 ADR 落地）

- 多租戶／JWT：見 [`TODOS.md`](../TODOS.md) 隊列 **11**（`httpOnly` cookie + `/api/auth/login`），需產品決策。
- 命令分權（如管理員 `RUN-FORCE`）：本 ADR v1 不開；若必要，先補 RBAC schema 再實作 UI。

## 5. 驗收

- [`command-bar-route.spec.js`](../data-verification-ui/e2e/command-bar-route.spec.js) 覆蓋 N／W：placeholder 分路（44d）、`AAPL GO` 設 focus、`WATCH` 寫 `terminal_sse_watch`、`RUN` 觸發 `cmd-bar-run-toast`。
- 後端中介層 `_require_master_key` 已對 `/api/*`（除 SSE）強制；見 [`api.py`](../api.py)。
- 任何新增 W 類指令的 PR 必須在 description 列出對應 `_require_master_key` 路徑與是否新增資料源（若有，附治理審核連結）。
