# 儀表板與 API 契約（BL-12）

本檔描述 **Streamlit 戰情室**（[`dashboard.py`](../dashboard.py)）、**FastAPI**（[`api.py`](../api.py)）與 PWA（[`data-verification-ui/`](../data-verification-ui/)）對齊時應遵守的資料語意。欄位名以實作為準；缺憑證時行為為 **優雅降級（N/A／錯誤提示）**。  
「Bloomberg Terminal 對齊」能力映射與驗收清單見 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md)。

## Streamlit 區塊 ↔ 資料來源

| UI 區塊 | 主要來源 | 更新頻率（預設） | 缺資料 |
|---------|-----------|------------------|--------|
| 篩選設定 | 使用者輸入 | — | — |
| 財經儀表板 | `load_daily_metrics()` → BigQuery | 頁面載入；自動刷新 5 分 | 顯示無資料提示 |
| 鏈上情緒與衍生品快照 | 同 metrics + 內嵌文字摘要（funding 等） | 同上 | N/A 字樣 |
| 每日指標趨勢 | `load_risk_trend(days)` → BQ | 同上 | 空圖表／提示 |
| 鏈上三指標趨勢 | 同趨勢資料之 **SOPR／情緒分數／交易所淨流** 獨立 Tab（⛓／🎭／🏦） | 同上 | 與 `daily_metrics` 欄位一致 |
| QSREC 頻率 | `load_qsrec_asset_frequency` → `RECOMMENDATIONS_TABLE` | 同上 | 無資料時提示 |
| 鏈上巨鯨流向 | `load_whale_data()` → BQ | 同上 | 空表 |
| 公司戰情（試點） | `load_company_war_room_snapshot`（本機 JSON） | 檔案 mtime | 區塊說明無檔案 |
| Symbol 快照（唯讀 expander） | `build_symbol_snapshot` 或 `SYMBOL_SNAPSHOT_HTTP_BASE` + `/api/symbols/…/snapshot` | `st.cache_data` TTL 120s | 無 BQ／API 時錯誤提示 |
| 核心 Agent 戰略點評 | BQ 報告欄位 | 同上 | 提示 |

## FastAPI（對 PWA / 外部客戶端）

| 路由 | 用途 | 備註 |
|------|------|------|
| `GET /api/metrics/latest` | 最新日報指標 | 對齊 BQ schema |
| `GET /api/metrics/history` | 歷史指標 | query：`days` |
| `GET /api/symbols/{symbol}/snapshot` | 單一代號快照（Terminal-style） | query：`days`、`recommendation_limit`；回應含 **`data_provenance`**（OHLC／BQ 來源與 as_of）；**`price_alignment`** 描述 **yfinance OHLC 尾端** vs **`/quote` 之 last**（皆 yfinance），並標 **`daily_metrics_source: bigquery`**；staging 可選 **`PRICE_ALIGNMENT_E2E_OVERRIDES`** 強制數值（見 `ENV_TEMPLATE.txt`） |
| `GET /api/symbols/{symbol}/quote` | 輕量 **最新日線收盤** + 可選 **1D %**（僅 yfinance，無 BQ） | 失敗 **503**；伺服端快取約 **45s**；回應含 **`data_provenance.price`** |
| `GET /api/execution-intents` | 執行意圖列表（每 `signal_id` 最新一列） | query：`limit`；可選 **`status`**（狀態字串之子字串比對，大小寫不敏感）、**`category`**（`CRYPTO`／`AI` 前綴）、**`sort_by`**（`updated_desc`｜`created_desc`｜`asset_asc`）。若存在本機 **`.qsilicon/last_gate_failure/validation_summary.json`**，列表列會附加唯讀 **`gate_issue_hints`**（資產代號出現在 gate issue 行時） |
| `GET /api/execution-intents/allowed-statuses` | 意圖狀態集合 | 回傳 **`statuses`**（含紙上 `PAPER_*`）與 **`client_patchable`**（僅人審可 PATCH 子集） |
| `PATCH /api/execution-intents/{signal_id}` | 意圖狀態轉移（append-only；**不下單**） | body：`status`、`note`、可選 **`reference_entry_price`／`reference_target_price`／`reference_stop_price`**（紙上模擬錨點） |
| `GET /api/stream/war-room` | **SSE**：`data:` 為 `GET /api/war-room/latest` 同源 JSON | 預設 **404**；設 **`TERMINAL_SSE_ENABLED=1`** 啟用；可選 **`API_STREAM_AUTH_KEY`**（`X-QS-Stream-Key` 或 `?stream_key=`） |
| `POST /api/paper/execution-tick` | 紙上模擬 **一輪**（`run_paper_execution_tick`） | 預設 **404**；設 **`PAPER_TICK_HTTP_ENABLED=1`**；可選 **`PAPER_TICK_API_KEY`**（`X-Paper-Tick-Key`）；CLI 見 `scripts/paper_execution_tick.py` |
| `GET /api/reports` | 報告列表 | 分頁參數見實作 |
| `GET /api/reports/{report_date}` | 單日報告內容 | |
| `GET /api/trades` | 交易列表 | |
| `GET /api/trades/performance` | 績效彙總 | |
| `GET /healthz` | 存活探測 | |
| `POST /api/push/subscribe` | Web Push 訂閱 | 預設 **501**；`WEB_PUSH_ENABLED=1` 時：可設 **`WEB_PUSH_REDIS_URL`**（分散式儲存 + **Redis** rate limit）、或 **`WEB_PUSH_STORE=1`**（程序內）；可選 **`WEB_PUSH_BQ_PERSIST`**／**`WEB_PUSH_BQ_AUDIT`**。見 [`docs/PWA_WEB_PUSH.md`](PWA_WEB_PUSH.md) |
| `POST /api/push/test-send` | 管理端 **測試推送**（`pywebpush`） | 預設 **404**；須 **`WEB_PUSH_ADMIN_KEY`** + Header **`X-Web-Push-Admin-Key`** + **`WEB_PUSH_VAPID_PRIVATE_KEY`** + 已存完整訂閱 |

PWA 應與上述鍵名一致；若前端另有聚合，請在 PR 中更新本表。  
Streamlit 若需重用 Symbol 快照，應優先消費 `GET /api/symbols/{symbol}/snapshot`（唯讀聚合），避免重複資料組裝邏輯。實作上 [`dashboard.py`](../dashboard.py) 預設以 [`symbol_snapshot_service.build_symbol_snapshot`](../symbol_snapshot_service.py) 與 API **同形**；若設環境變數 **`SYMBOL_SNAPSHOT_HTTP_BASE`**（例 `http://127.0.0.1:8000`），則改以 HTTP 取得該 JSON。可選 **`DASHBOARD_SYMBOL_FOCUS`** 作為「載入快照」預設代號。

**PWA（Vite）**：[`data-verification-ui`](../data-verification-ui/) 的 **`/terminal`** 頁對 `snapshot`、`execution-intents`、`war-room/latest` 啟用 **輪詢**（預設 45s）。可選 **`VITE_TERMINAL_POLL_MS`**（毫秒，建議 ≥15000）覆寫；見 [`docs/TERMINAL_MID_TIER_ROADMAP.md`](TERMINAL_MID_TIER_ROADMAP.md)。可選 **`VITE_TERMINAL_QUERY_COALESCE=1`**（預設）讓同頁多卡之 `snapshot`／`quote`／`intents` 輪詢 **微錯開**，降低 burst（設 **`0`** 關閉）。  
可選 **`VITE_WEB_PUSH_REGISTER=1`** + **`VITE_WEB_PUSH_VAPID_PUBLIC_KEY`**（URL-safe base64）在 SW 就緒後嘗試 `pushManager.subscribe` 並 `POST /api/push/subscribe`（後端須 `WEB_PUSH_ENABLED=1`）；預設關閉。  
可選 **`VITE_SSE_ENABLED=1`** + **`VITE_SSE_STREAM_KEY`**（與後端 `API_STREAM_AUTH_KEY` 對齊）以 **EventSource** 訂閱 `/api/stream/war-room` 並 invalidate React Query（後端須 `TERMINAL_SSE_ENABLED=1`）。

### PWA 設計 tokens（Visualization V1）

機構深色儀表板之 **色票**、`regime`（on／neutral／off）與 **`qs`**（accent、danger …）語意見 [`data-verification-ui/src/design/tokens.js`](../data-verification-ui/src/design/tokens.js)，並經 [`data-verification-ui/tailwind.config.js`](../data-verification-ui/tailwind.config.js) **`theme.extend`** 暴露為 Tailwind class（例如 `text-regime-on`、`text-qs-accent`）。

審計用共用元件：`AsOfChip`（as-of + 來源）、`ProvenancePopover`（`GET /api/symbols/…/snapshot` 之 **`data_provenance`**）、`ProfileBadge`、`GateStatusBadge` 等見 [`data-verification-ui/src/components/common/`](../data-verification-ui/src/components/common/)。

開發環境（`npm run dev`）可開 **`/design`** 預覽上述元件（[`data-verification-ui/src/pages/DesignShowcase.jsx`](../data-verification-ui/src/pages/DesignShowcase.jsx)；production build 仍為標準路由，不含 Storybook）。路線圖見 [`visualization_plan.md`](../visualization_plan.md) Phase **V1**；Streamlit `dashboard.py` 與 token **視覺對齊**排入同檔 Phase **V6**，避免首階混拆後端戦情室。

## 變更流程

1. 修改 `dashboard.py` / `api.py` 時，同步更新本檔與（若對外）OpenAPI。  
2. KPI 閾值（例如 gauge 2.5 / 3.5）變更時，註記於 PR 與 `CHANGELOG.md`。
