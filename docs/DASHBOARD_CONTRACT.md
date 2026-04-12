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
| `GET /api/symbols/{symbol}/snapshot` | 單一代號快照（Terminal-style） | query：`days`、`recommendation_limit`；回應含 **`data_provenance`**（OHLC／BQ 來源與 as_of） |
| `GET /api/execution-intents` | 執行意圖列表（每 `signal_id` 最新一列） | query：`limit` |
| `GET /api/execution-intents/allowed-statuses` | 允許的意圖狀態集合 | |
| `PATCH /api/execution-intents/{signal_id}` | 意圖狀態轉移（append-only；**不下單**） | JSON body：`status`、`note` |
| `GET /api/reports` | 報告列表 | 分頁參數見實作 |
| `GET /api/reports/{report_date}` | 單日報告內容 | |
| `GET /api/trades` | 交易列表 | |
| `GET /api/trades/performance` | 績效彙總 | |
| `GET /healthz` | 存活探測 | |
| `POST /api/push/subscribe` | Web Push 訂閱（**預留**） | 預設 **501**；`WEB_PUSH_ENABLED=1` 時 noop 接受，持久化待實作 |

PWA 應與上述鍵名一致；若前端另有聚合，請在 PR 中更新本表。  
Streamlit 若需重用 Symbol 快照，應優先消費 `GET /api/symbols/{symbol}/snapshot`（唯讀聚合），避免重複資料組裝邏輯。實作上 [`dashboard.py`](../dashboard.py) 預設以 [`symbol_snapshot_service.build_symbol_snapshot`](../symbol_snapshot_service.py) 與 API **同形**；若設環境變數 **`SYMBOL_SNAPSHOT_HTTP_BASE`**（例 `http://127.0.0.1:8000`），則改以 HTTP 取得該 JSON。可選 **`DASHBOARD_SYMBOL_FOCUS`** 作為「載入快照」預設代號。

## 變更流程

1. 修改 `dashboard.py` / `api.py` 時，同步更新本檔與（若對外）OpenAPI。  
2. KPI 閾值（例如 gauge 2.5 / 3.5）變更時，註記於 PR 與 `CHANGELOG.md`。
