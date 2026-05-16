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
| SEC EDGAR（10-Q capex） | free | hyperscaler 季度 capex（MSFT／GOOG／META／AMZN／ORCL） | 官方 fair-use；User-Agent 須含聯絡 email；無 quota 但需 ≤10 req/s | `tools/sec_edgar_capex.py`、`api_routers/macro.py:get_compute_memory()` | pending |
| CoreWeave public pricing | free | GPU hourly spot（H100／H200／B200／A100） | 公開定價頁；非官方 API；ToS 允許資訊性引用 | `tools/coreweave_gpu_spot.py`、`api_routers/macro.py:get_compute_memory()` | pending |
| TrendForce / DRAMeXchange | paid | HBM／DRAM contract spot | 付費訂閱；免費 tier 不足；需採購後再接入 | （未接入；占位） | pending |

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

---

## 6) P2-live 三來源審核表（queue 45）

登錄日期：**2026-05-16**。SEC EDGAR 與 CoreWeave 為 `pending`，待 PR-A／PR-B 接入時於 §2 改 `active`；TrendForce 保持 `pending` 占位，等待付費訂閱決策。

### 6.1 SEC EDGAR（10-Q capex）

```
- Name: SEC EDGAR submissions / company facts API
- Vendor / Provider: U.S. Securities and Exchange Commission
- Tier: free
- ToS URL: https://www.sec.gov/about/webmaster-faq#code-of-conduct
- Rate limit / quota: fair-use；≤10 req/s；無 daily quota
- 是否需要 API key（環境變數名稱）：否；但 User-Agent 須含聯絡 email → SEC_EDGAR_CONTACT_EMAIL
- 是否可用於商業用途：是（公開資料）
- 是否包含個人資料（PII）：否
- 失敗模式（API 503/429 時行為）：fetcher 回 None → router 退 fixture 並標 live_block_status.capex="fallback"
- 是否覆蓋既有來源：否（新增；無 fallback chain 衝突）
- 接入點：tools/sec_edgar_capex.py:fetch_latest_capex()、api_routers/macro.py:get_compute_memory()
- 對齊 DASHBOARD_CONTRACT 欄位：hyperscaler_capex.items[].{ticker, quarter, capex_b_usd, as_of, source}
- 測試：tests/api/test_sec_edgar_capex.py、tests/api/test_compute_memory.py
```

維護者勾選：
- [x] ToS 允許本 repo 的用途（公開財報資料；個人研究與開源無虞）
- [x] 不會破壞 `validate_report` 之輸入契約（只進 `/api/macro/compute-memory`，不進日報主管線）
- [x] 失敗時退化為 fixture（mock），**不**由 LLM 補數字
- [x] secret 走環境變數（`SEC_EDGAR_CONTACT_EMAIL`），於 `ENV_TEMPLATE.txt` 登錄
- [x] 有 pytest 覆蓋（正常／429／503／schema 異常／cache）
- [x] CHANGELOG 與本文件第 2 節同步更新（PR-A）

### 6.2 CoreWeave public pricing

```
- Name: CoreWeave public GPU instance pricing
- Vendor / Provider: CoreWeave, Inc.
- Tier: free
- ToS URL: https://www.coreweave.com/legal/terms-of-service
- Rate limit / quota: 公開定價頁；無正式 API；以 1h cache 降至 ≤1 req/h
- 是否需要 API key（環境變數名稱）：否
- 是否可用於商業用途：資訊性引用（非轉售定價服務）
- 是否包含個人資料（PII）：否
- 失敗模式：fetcher 回 None → router 退 fixture 並標 live_block_status.gpu="fallback"
- 是否覆蓋既有來源：否
- 接入點：tools/coreweave_gpu_spot.py:fetch_gpu_pricing()、api_routers/macro.py:get_compute_memory()
- 對齊 DASHBOARD_CONTRACT 欄位：gpu_spot.items[].{sku, provider, hourly_usd, as_of, source}
- 測試：tests/api/test_coreweave_gpu_spot.py、tests/api/test_compute_memory.py
```

維護者勾選：
- [x] ToS 允許本 repo 的用途（資訊性引用公開定價）
- [x] 不會破壞 `validate_report` 之輸入契約
- [x] 失敗時退化為 fixture（mock），**不**由 LLM 補數字
- [x] 不需 secret；無對應環境變數
- [x] 有 pytest 覆蓋（正常／5xx／parse error／cache）
- [x] CHANGELOG 與本文件第 2 節同步更新（PR-B）

### 6.3 TrendForce／DRAMeXchange（pending — 未接入）

```
- Name: TrendForce HBM/DRAM contract pricing（含 DRAMeXchange spot）
- Vendor / Provider: TrendForce Corp.
- Tier: paid
- ToS URL: https://www.trendforce.com/about/agreement
- Rate limit / quota: 視訂閱方案
- 是否需要 API key：是（訂閱後核發）；環境變數名稱待定
- 是否可用於商業用途：受訂閱合約限制
- 是否包含個人資料：否
- 失敗模式：未接入；HBM 區塊保持 mock fixture
- 是否覆蓋既有來源：否
- 接入點：未接入
- 對齊 DASHBOARD_CONTRACT 欄位：hbm_dram_spot.items[].{product, spec, spot_usd, as_of, source}（mock 已對齊）
- 測試：未接入
```

維護者勾選（全未勾選）：
- [ ] ToS 允許本 repo 的用途（待訂閱合約評估）
- [ ] 不會破壞 `validate_report` 之輸入契約
- [ ] 失敗時退化為 `[DATA_MISSING:...]`，**不**由 LLM 補數字
- [ ] secret 走環境變數，於 `ENV_TEMPLATE.txt` 登錄
- [ ] 有 pytest 覆蓋
- [ ] CHANGELOG 與本文件第 2 節同步更新

**狀態**：保留 mock；HBM 區塊在 `/api/macro/compute-memory` response 中 `live_block_status.hbm` 永遠為 `"mock"`，直到訂閱核可。
