# 儀表板與 API 契約（BL-12）

本檔描述 **Streamlit 戰情室**（[`dashboard.py`](../dashboard.py)）、**FastAPI**（[`api.py`](../api.py)）與 PWA（[`data-verification-ui/`](../data-verification-ui/)）對齊時應遵守的資料語意。欄位名以實作為準；缺憑證時行為為 **優雅降級（N/A／錯誤提示）**。

## Streamlit 區塊 ↔ 資料來源

| UI 區塊 | 主要來源 | 更新頻率（預設） | 缺資料 |
|---------|-----------|------------------|--------|
| 篩選設定 | 使用者輸入 | — | — |
| 財經儀表板 | `load_daily_metrics()` → BigQuery | 頁面載入；自動刷新 5 分 | 顯示無資料提示 |
| 鏈上情緒與衍生品快照 | 同 metrics + 內嵌文字摘要（funding 等） | 同上 | N/A 字樣 |
| 每日指標趨勢 | `load_risk_trend(days)` → BQ | 同上 | 空圖表／提示 |
| 鏈上巨鯨流向 | `load_whale_data()` → BQ | 同上 | 空表 |
| 公司戰情（試點） | `load_company_war_room_snapshot`（本機 JSON） | 檔案 mtime | 區塊說明無檔案 |
| 核心 Agent 戰略點評 | BQ 報告欄位 | 同上 | 提示 |

## FastAPI（對 PWA / 外部客戶端）

| 路由 | 用途 | 備註 |
|------|------|------|
| `GET /api/metrics/latest` | 最新日報指標 | 對齊 BQ schema |
| `GET /api/metrics/history` | 歷史指標 | query：`days` |
| `GET /api/reports` | 報告列表 | 分頁參數見實作 |
| `GET /api/reports/{report_date}` | 單日報告內容 | |
| `GET /api/trades` | 交易列表 | |
| `GET /api/trades/performance` | 績效彙總 | |
| `GET /healthz` | 存活探測 | |

PWA 應與上述鍵名一致；若前端另有聚合，請在 PR 中更新本表。

## 變更流程

1. 修改 `dashboard.py` / `api.py` 時，同步更新本檔與（若對外）OpenAPI。  
2. KPI 閾值（例如 gauge 2.5 / 3.5）變更時，註記於 PR 與 `CHANGELOG.md`。
