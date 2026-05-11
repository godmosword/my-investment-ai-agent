# 即時／訂閱資料來源治理（Q-Silicon）

本文件補上 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4 條目 **15**（不引入未審核的即時付費資料依賴）所需的「已審核來源清單」與審核流程。

關聯：
- [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md)（驗收清單）
- [`docs/DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md)（資料口徑與來源欄位）
- [`CLAUDE.md`](../CLAUDE.md) ／ [`.cursorrules`](../.cursorrules)（紅線：無數據幻覺、Telegram HTML 白名單）

---

## 1) 紅線（不可破）

1. **未經本文件登錄之即時／訂閱資料來源不得進入主管線**。包含但不限於：訂閱型 quote API、券商 streaming feed、付費 sentiment／onchain feed。
2. **客觀數字必須帶 `as_of` 與 `source`**（對齊 [`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md)），不得由 LLM 推導。
3. **不得寫死 API key 或 endpoint URL**；所有 secret 走環境變數（見 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)）。
4. **新增來源前須先填寫第 3 節審核表**，由維護者於 PR 通過後方可合併。

---

## 2) 已審核來源清單（Approved Sources）

`tier`：`free` ＝ 公開／免費；`freemium` ＝ 有免費額度；`paid` ＝ 付費訂閱。  
`status`：`active` ＝ 已上線；`fallback` ＝ 僅備援；`removed` ＝ 已下線。

| Source | Tier | 用途 | ToS / Rate limits | repo 接入點 | Status |
|--------|------|------|--------------------|-------------|--------|
| yfinance | free | 日線 OHLC、quote、`SymbolSnapshot` | 非官方；不保證 SLA；個人用途可接受 | `symbol_snapshot_service.py`、`fetch_symbol_quote`／`fetch_symbol_ohlc` | active |
| Polygon.io（基礎免費層） | freemium | 備援 quote／OHLC | 免費層 5 req/min；商業用須升級 | （未接入；保留） | fallback |
| BigQuery `market_data` | free（自管） | 歷史日報、reviewer log、gate failure | 受 GCP IAM；無外部 ToS | `bigquery_writer.py`、`/api/reports/*` | active |
| FRED | free | 宏觀經濟序列 | 每 IP rate limit；需 API key | `tools/`（依需求接入） | active |
| NewsAPI／NewsData | freemium | 時事擷取（隊列 27） | 免費層每日上限；不得轉售原文 | `current_affairs_crew.py`／`tools/` | active |
| Tech pulse（aggregator） | free | 科技題材匯流 | 公開 RSS／API | `tools/tech_pulse_tool.py`（`TECH_PULSE_IN_BRIEF`） | active |

---

## 3) 新來源審核表（必填）

新增來源前在 PR 描述貼上以下表格並逐條回答：

```
- Name:
- Vendor / Provider:
- Tier (free/freemium/paid):
- ToS URL:
- Rate limit / quota:
- 是否需要 API key（環境變數名稱）：
- 是否可用於商業用途：
- 是否包含個人資料（PII）：
- 失敗模式（API 503／429 時行為）：
- 是否覆蓋既有來源（若是，列出 fallback 順序）：
- 接入點（檔案／函式）：
- 對齊 DASHBOARD_CONTRACT 欄位（如有新增）：
- 測試（pytest 路徑）：
```

審核維度（維護者勾選）：

- [ ] ToS 允許本 repo 的用途（含產生 Telegram 日報、開源研究）
- [ ] 不會破壞 [`validate_report`](../report_html_gates.py) 之輸入契約
- [ ] 失敗時退化為 `[DATA_MISSING:...]`，**不**由 LLM 補數字
- [ ] secret 走環境變數，於 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 登錄
- [ ] 有 pytest 覆蓋（正常／429／503／schema 異常）
- [ ] CHANGELOG 與本文件第 2 節同步更新

---

## 4) 移除流程

若來源 ToS 變動、SLA 不可接受、或被更佳替代取代：

1. 在 PR 描述說明移除原因。
2. 將第 2 節對應列 `status` 改為 `removed`，保留紀錄以利回溯。
3. 移除環境變數（保留變數名於 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 註解，避免歷史部署誤觸）。
4. 更新所有 fallback chain（`symbol_snapshot_service` 等）。
5. 同步 [`CHANGELOG.md`](../CHANGELOG.md) `### Removed`。

---

## 5) 對應驗收

本文件存在即覆蓋 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) 第 15 條「不引入未審核的即時付費資料依賴」之治理要求。新來源需走第 3 節審核表後方可接入。
