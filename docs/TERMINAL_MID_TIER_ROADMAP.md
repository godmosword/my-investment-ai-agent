# Terminal 中段路線（資料可審計 · 互動節奏 · 執行銜接）

**目標**：把「類 Terminal」從 **1–2（早段）** 拉到 **3（中段）** — 不靠專有資料壟斷，而是靠 **可追溯來源（as-of）**、**可預期的更新節奏**、以及 **執行意圖 → 人審／紙上** 的閉環。對齊 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) 紅線與 Phase 0 驗收精神。

---

## 1) 現況錨點（已落地）

| 能力 | 實作 |
|------|------|
| Symbol 快照 + OHLC + 事件標記 | `GET /api/symbols/{symbol}/snapshot`、`symbol_snapshot_service.build_symbol_snapshot` |
| 快照 **data_provenance** | 回應內 `data_provenance`：`ohlc`（yfinance）、`daily_metrics`／`recommendations`（BQ 表與 as_of） |
| 執行意圖 JSONL | `execution_intents.py`；`append_execution_intents` 寫入 |
| 意圖列表（去重） | `GET /api/execution-intents` — 每 `signal_id` 只保留**最新**一列 |
| 狀態機（人審／紙上） | `PATCH /api/execution-intents/{signal_id}` + `GET /api/execution-intents/allowed-statuses` |
| War Room 聚合 | `GET /api/war-room/latest`（仍含 `execution_intents`） |

**允許狀態**（可擴）：`PENDING_REVIEW` · `APPROVED_FOR_PAPER` · `REJECTED` · `SUPERSEDED`。

---

## 2) 中段定義（驗收語意）

1. **資料**：關鍵聚合 API 能回答「這個數字從哪來、截至何時」— **Phase 0 第 2 條**方向。
2. **互動**：PWA 能以 **輪詢或輕量推送** 維持「感覺即時」— 中段先 **30s–60s 輪詢** `snapshot` + `war-room/latest`；WebSocket 列下一段。
3. **執行**：意圖可 **列出 → 改狀態 → 審計軌跡**（append-only），仍 **不下單**。

---

## 3) 實作切片（建議順序）

| 切片 | 內容 | 風險 |
|------|------|------|
| **M1** | `data_provenance` + execution intent **PATCH/GET**（本輪） | 低 |
| **M2** | PWA Terminal：顯示 `data_provenance`、意圖狀態按鈕（打 PATCH）、輪詢間隔 env | 低 |
| **M3** | `GET /api/symbols/{symbol}/quote` — 輕量 last（yfinance 短 TTL），圖表外 KPI 刷新 | yfinance 限流；需快取 |
| **M4** | `SSE` 或 **WebSocket** 推送 `war-room` + 單 symbol 訂閱（Redis pub/sub 可選） | 部署與 auth |
| **M5** | **紙上撮合** worker：讀 `APPROVED_FOR_PAPER`、寫回 `PAPER_FILLED`（新狀態需 migration 討論） | 合規／ToS |

---

<a id="m2-terminal-pwa"></a>

## 3b) M2 — PWA：溯源顯示 + 意圖操作 + 輪詢節奏

**目標**：讓操作者在 **不開後台** 的情況下，完成「看來源 → 看意圖 → 改狀態」，且畫面以可預期節奏刷新（中段「感覺即時」）。

### 驗收（DoD）

1. **Symbol 卡**：若 API 回傳 `data_provenance`，以可摺疊區塊顯示 **OHLC／daily_metrics／recommendations** 的 `source`、`as_of`、`underlying_symbol`（若有）、`table_id`（若有）；mock 與實盤視覺上可辨（沿用既有 demo 提示 pattern 即可）。
2. **執行意圖**：Terminal 頁（或共用 drawer）列出 `GET /api/execution-intents`；每列可對 **允許狀態** 發 `PATCH`（至少：核准紙上、駁回）；成功後列表與 War Room 區塊 refetch。
3. **輪詢**：`useSymbolSnapshot`（及 War Room 若同頁顯示）在 **Terminal 路由** 下 `refetchInterval` 可設；預設 **45s**，可由 **`import.meta.env.VITE_TERMINAL_POLL_MS`** 覆寫（僅數字 ms）；未設 env 時維持現有 staleTime 行為於非 Terminal 頁。
4. **錯誤態**：PATCH 4xx/5xx 顯示可讀訊息，不中斷整頁。

### 建議修改檔案

| 檔案 | 工作 |
|------|------|
| [`data-verification-ui/src/hooks/useApi.js`](../data-verification-ui/src/hooks/useApi.js) | 新增 `apiPatch(path, body)`；`useSymbolSnapshot` 接受 options `{ refetchInterval }` 或讀 env；新增 `useExecutionIntents`、`useExecutionIntentStatuses`、`usePatchExecutionIntent`（`useMutation`） |
| [`data-verification-ui/src/components/TerminalSymbolCard.jsx`](../data-verification-ui/src/components/TerminalSymbolCard.jsx) | 摺疊 **資料溯源** 區；必要時小字重複 `as_of` 與 provenance 對齊 BLOOMBERG Phase 0 §2 |
| 新檔 `ExecutionIntentsBlotter.jsx`（或內嵌 [`Terminal.jsx`](../data-verification-ui/src/pages/Terminal.jsx)） | 表格 + 狀態按鈕 + optional note textarea |
| [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)（可選） | 註解 `VITE_TERMINAL_POLL_MS`；README PWA 小節一行 |

### 測試

- 前端：若專案已有 **Playwright／Vitest** 則加 1 條 mock API 的 PATCH 流程；否則以 **手動 checklist** 寫入本檔 §7。

---

<a id="m3-symbol-quote"></a>

## 3c) M3 — 輕量 Quote API（K 線外「最新價」刷新）

**目標**：降低 **整包 snapshot** 呼叫頻率；圖表仍用日線 OHLC，**頂欄 last** 用更小 payload 輪詢。

### API 設計

- `GET /api/symbols/{symbol}/quote`  
  回傳建議欄位：`symbol`、`as_of`（UTC ISO）、`source`（`yfinance`）、`last`、`currency`（若可得）、`change_pct_1d`（可選，需前一交易日則與 snapshot 共用快取策略）。

### 後端實作要點

| 項目 | 說明 |
|------|------|
| 實作位置 | 新函式 `fetch_symbol_quote` + 路由於 [`api.py`](../api.py)；**快取**與 `symbol_snapshot_service.fetch_symbol_ohlc` 類似（例如 **TTL 30–60s**、每 symbol key 上限） |
| 限流 | 多 symbol 輪詢時 TTL 必須夠長；可選 **單 IP rate limit**（middleware 或依 path 計數） |
| 契約 | 更新 [`docs/DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md)；PWA `useSymbolQuote(symbol, { refetchInterval })` |

### 驗收（DoD）

1. pytest：`200`、無效 symbol `400`、yfinance 失敗回 **503 或** 帶明確 `detail` 的 JSON（與現有 API 錯誤態一致）。  
2. Terminal 卡：**last** 來自 quote；**圖**仍來自 snapshot（避免每 30s 重打 BQ）。

---

<a id="m4-realtime-stream"></a>

## 3d) M4 — 即時通道（SSE 優先，WebSocket 備選）

**目標**：War Room／關注 symbol 在 **後端事件**（新 intent 行、新 gate artifact、可選 pipeline hook）發生時，**秒級**推送至瀏覽器，減少輪詢空轉。

### 方案 A（建議先）：**Server-Sent Events (SSE)**

- `GET /api/stream/war-room`：`StreamingResponse`，`media_type="text/event-stream"`，週期推送 `war-room/latest` JSON 或 **ETag／mtime** 變更後才推全文。  
- 優點：FastAPI 單向即可、穿透代理較單純、與現有 **唯讀** 語意一致。  
- 缺點：瀏覽器連線數限制；需 **心跳 comment** 避免逾時斷線。

### 方案 B：**WebSocket**

- `/ws/terminal`：訊息 `{ "subscribe": ["war-room", "BTC"] }`；後端聚合 snapshot 片段或只推「請 refetch」信號。  
- 若多實例部署，需 **Redis Pub/Sub** 或共用儲存做 fan-out（複雜度顯著上升）。

### 橫切

| 項目 | 說明 |
|------|------|
| **Auth** | 生產建議 **`API_KEY` header** 或 cookie session；dev 可關閉；文件寫入 `DASHBOARD_CONTRACT` |
| **負載** | 預設只推 **「有變更」**（比對 scratchpad／intents 檔 mtime 或 last line hash） |
| **前端** | `EventSource` 或 `@microsoft/fetch-event-source`；Terminal unmount 時 `close()` |

### 驗收（DoD）

1. 本地：手動觸發 execution intent append 後，訂閱 SSE 的頁面 **≤2s** 內更新（或收到 refetch 事件）。  
2. pytest：`TestClient` 對 SSE 端點讀取首個 chunk（可 mock 檔案 mtime）。

---

<a id="m5-paper-execution"></a>

## 3e) M5 — 紙上執行層（仍不下真單）

**目標**：把 `APPROVED_FOR_PAPER` 與 **模擬成交／模擬部位** 串成可審計閉環；與真 OMS 分界清楚。

### 狀態擴充（需產品拍板）

| 狀態 | 語意 |
|------|------|
| `PAPER_SUBMITTED` | 已進入紙上佇列（worker 已讀） |
| `PAPER_FILLED` | 以規則或下一根 OHLC **模擬**成交 |
| `PAPER_CLOSED` | 模擬平倉（觸發價／到期） |

**遷移**：擴充 `ALLOWED_INTENT_STATUSES` + `PATCH` 白名單；舊列無 `status_note` 仍須可 PATCH。

### Worker 形態（擇一）

1. **獨立腳本** `scripts/paper_execution_tick.py` + cron（每 1–5 分鐘）：讀 JSONL tail、append 新狀態行。  
2. **選進 api**：BackgroundTasks / `asyncio.create_task`（僅單機可靠；多副本需外佇列）。

### 成交規則（MVP）

- 以 **quote last** 或 **日線 close** 與 `entry_price`／`stop`／`target` 比較，採 **保守假設**（例如觸發 stop 優先）；結果寫入 **新 JSONL 檔** `execution_paper_fills.jsonl` 或同一檔 `event_type: PAPER_FILL`。  
- **禁止**：呼叫真券商 API。

### 可選觀測

- BigQuery 表 `paper_execution_log`（與 `SKIP_BIGQUERY` 一致）；非 M5 必須。

### 驗收（DoD）

1. pytest：給定一行 `APPROVED_FOR_PAPER` + 模擬 quote，worker 一次 tick 產出預期 `PAPER_FILLED` 或維持待成交。  
2. 文件：本檔 + `ROADMAP_VISION` 一句「紙上層不替代 validate_report／日報主線」。

---

## 4) 環境變數（預留）

| 變數 | 用途 |
|------|------|
| `EXECUTION_INTENT_STORE` | JSONL 路徑（既有） |
| `VITE_TERMINAL_POLL_MS` | PWA：Terminal 內 snapshot／war-room **refetchInterval**（ms），建議 `45000` |
| `TERMINAL_SSE_ENABLED`（M4） | `1` 時註冊 `GET /api/stream/war-room`；預設 `0` |
| `API_STREAM_AUTH_KEY`（M4，可選） | SSE／WS 訂閱需 header `X-QS-Stream-Key` |

---

## 5) 相關測試

- `test_api_symbols_snapshot.py` — snapshot 契約與 `data_provenance`
- `test_execution_intents_api.py` — list / patch / allowed-statuses
- **M3**：`test_api_symbol_quote.py`（新）— 成功、400、快取命中  
- **M4**：`test_api_stream_war_room.py`（新）— 首包或 403（auth）  
- **M5**：`test_paper_execution_tick.py`（新）— 純函式 + tmp JSONL

---

## 6) 建議排程（依賴）

```text
M2 ──► M3（quote 可餵 M5 規則）
  │
  └──► M4（與 M2/M3 並行規劃可行；部署複雜度較高，建議 M2 後）
         │
         └──► M5（依賴 quote 或 OHLC + 狀態擴充定案）
```

---

## 7) M2 手動驗收 checklist（無 E2E 時）

- [ ] 設 `VITE_API_URL` + `VITE_TERMINAL_POLL_MS=15000`，開 `/terminal`，Network 可見週期 snapshot 請求。  
- [ ] 摺疊「資料溯源」與卡片頂部 `as_of` 一致。  
- [ ] 對一筆 intent 執行 PATCH → 列表與（若有）War Room 意圖區同步更新。  
- [ ] 關閉 API 時錯誤提示可讀。
