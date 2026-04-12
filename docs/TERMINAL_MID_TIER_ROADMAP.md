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

## 4) 環境變數（預留）

| 變數 | 用途 |
|------|------|
| `EXECUTION_INTENT_STORE` | JSONL 路徑（既有） |
| `TERMINAL_POLL_MS`（前端） | War Room / snapshot 輪詢間隔，預設建議 45000 |

---

## 5) 相關測試

- `test_api_symbols_snapshot.py` — snapshot 契約與 `data_provenance`
- `test_execution_intents_api.py` — list / patch / allowed-statuses
