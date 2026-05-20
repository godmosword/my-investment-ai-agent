# Codex Next Batch — Post FE-1..FE-6 Handoff

**Status (2026-05-20)**：Frontend UX Overhaul（隊列 **46–51** / FE-1..FE-6）已在 `main` 收尾。本文件為 **下一批五個可獨立開工的切片**，Codex 或 Cloud Agent 可直接依序實作，無需額外產品規格。

**導覽**：工程隊列 → [`TODOS.md`](../TODOS.md) · FE 驗收表 → [`BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4f · 變更紀錄 → [`CHANGELOG.md`](../CHANGELOG.md)

**紅線（全切片共用）**

- 客觀報價／指標／日期：**禁止** LLM 推導；沿用既有 Python 工具與 API。
- **不**改 `main.py` 日報 pipeline、`graph/`、Telegram HTML 白名單。
- **不**新增未審核或不可溯源的即時付費資料源（見 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)）。
- **不**接券商、不自動下單、不承諾收益。

---

## 建議實作順序

| 順序 | 切片 | 理由 |
|------|------|------|
| 1 | **NEXT-5** | 為後續 API／UI 改動提供契約安全網 |
| 2 | **NEXT-1** | 低風險 a11y／CSS，與 FE-6 刻意延後項對齊 |
| 3 | **NEXT-3** | Settings 高價值；依賴 NEXT-5 的 endpoint 契約 |
| 4 | **NEXT-2** | 新 UI；僅 paper + 既有 quote，無新資料源 |
| 5 | **NEXT-4** | **僅文件**；44b 進階收斂需維護者選項後再寫程式 |

---

## NEXT-1 — Touch target sweep + `index.css` dead-CSS audit

**對齊**：FE-6（隊列 51）刻意未做項 · [`CHANGELOG.md`](../CHANGELOG.md) 2026-05-20 `### PWA（隊列 51）`

### 為什麼現在做

FE-1..FE-5 已對 BottomNav／SideNav／Settings toggle／Monitor row／Brief 折疊等採 `min-height: 44px`，但**未**做全站掃描；`index.css` 累積歷史 class 可能已无引用。

### DO

- 以 **375px（iPhone 14 級）** 與 **1280px（桌面）** 兩種 viewport 盤點可點擊元素（`button`、`a[href]`、`.nav-item`、`[role="button"]`、表單 control）。
- 對 **interactive box &lt; 44×44px** 的元素補 `min-height`／`min-width`（優先 Tailwind `min-h-[44px]`／`min-w-[44px]`，與 [`Settings.jsx`](../data-verification-ui/src/pages/Settings.jsx) 一致）。
- 已知缺口（優先修）：[`GlobalWatchlistDock.jsx`](../data-verification-ui/src/components/GlobalWatchlistDock.jsx) 手機 `md:min-h-[44px]` 前為 36px；[`TerminalCommandBar.jsx`](../data-verification-ui/src/components/TerminalCommandBar.jsx) 小屏 `min-h-[40px]`。
- `index.css`：用 repo 內搜尋（class 名 → `data-verification-ui/src`）確認 **零引用** 後才刪除；刪除以 **單一 PR 內小批**（≤15 條規則）提交，方便 bisect。
- 新增 Playwright：**一條** mobile smoke，量測 2–3 個 `data-testid` 錨點的 bounding box ≥ 44（例如 BottomNav 第一項、Settings 輪詢 toggle）。

### DO NOT

- 不改路由、不新增頁面、不重寫 Tailwind 為全新設計系統。
- 不刪除仍被 E2E／`data-testid` 依賴的 class。
- 不做全檔 `index.css` 格式化或無關重排。

### 驗收標準

- [ ] 盤點表（可寫在 PR 描述）：列出修復的 selector／檔案；未修項註明原因。
- [ ] `cd data-verification-ui && npm run lint && npm run build` 綠。
- [ ] `npm run test:e2e` 全綠（含新 touch-target smoke）。
- [ ] `CHANGELOG` + `TODOS` 同步（隊列 51 延後項 → 已交付或新子項）。

### 參考檔案

| 檔案 | 用途 |
|------|------|
| [`data-verification-ui/src/index.css`](../data-verification-ui/src/index.css) | 全域觸控與 nav 規則 |
| [`DESIGN.md`](../DESIGN.md) | 44px 觸控標準敘述 |
| [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4f | FE 驗收錨點 |
| [`e2e/responsive-app-shell.spec.js`](../data-verification-ui/e2e/responsive-app-shell.spec.js) | 既有 shell viewport 模式 |

### 驗證指令

```bash
cd data-verification-ui && npm run lint && npm run build && npm run test:e2e
```

---

## NEXT-2 — Quant Intraday Monitor scaffold（隊列 33 續）

> **2026-05-20 已交付**：`GET /api/quant/signals` 改 paper-derived active rows；`QuantHome.jsx` 新增 Intraday Monitor（既有 quote polling、filter、offline banner、row deep link）；測試見 `test_api_quant_signals.py` 與 `e2e/quant-intraday-monitor.spec.js`。

**對齊**：隊列 **33**「仍待：Intraday Monitor」· [`TODOS.md`](../TODOS.md) 隊列 33 · [`QuantHome.jsx`](../data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx)

### 為什麼現在做

M7 已交付 backtest 與 stub `GET /api/quant/signals`；缺 **盤中監控列表**（paper 訊號 + 既有 live quote），且可重用 [`WatchlistMonitor.jsx`](../data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx) 模式。

### DO

- **路由**：在 **`/insights?tab=quant`**（或 Quant 模組既有 tab）新增 **「Intraday」** 子區／tab，**不**新增第六板塊路由。
- **資料**：
  - 訊號列：由 **`execution_intents.jsonl`**（`GET /api/execution-intents` 或 paper lifecycle 衍生列）篩 **ACTIVE** 狀態，帶 `symbol`、`direction`、`status`、`quality`（已有欄位則顯示）。
  - 報價：每 row 用既有 [`useSymbolQuote(sym, { livePoll: true })`](../data-verification-ui/src/hooks/useApi.js)（與 Monitor tab 相同；尊重 `qs_terminal_poll_ms_override`）。
- **UI**：列表 + 搜尋/filter；row click → `/insights?symbol=…`；離線時掛 [`OfflineBanner`](../data-verification-ui/src/components/OfflineBanner.jsx)。
- **後端（可選本切片）**：將 [`api.py`](../api.py) `GET /api/quant/signals` 由 placeholder 改為 **paper-derived** 列（讀 `execution_intents`／`paper_lifecycle`，**非**新行情源）；保留 `disclaimer` 欄位。
- **測試**：擴充 [`test_api_quant_signals.py`](../test_api_quant_signals.py)；新增 `e2e/quant-intraday-monitor.spec.js`（mock API + 至少一列顯示）。

### DO NOT

- 不新增 Binance／付費 intraday feed、不承諾 alpha、不顯示「保證收益」。
- 不讓 LLM 生成即時價格或訊號文字。
- 不拆 `api.py` 為新 router（除非維護者另開隊列 26 子項）。

### 驗收標準

- [x] `/insights?tab=quant`（或文件化之 deep link）可見 Intraday 區塊與 ≥1 筆 paper 列（fixture／mock 下）。
- [x] live quote 欄位在 mock 下顯示價格或 `—`；`livePoll` 不新增 env 旗標。
- [x] `pytest test_api_quant_signals.py -q` 綠；`npm run test:e2e` 綠。
- [x] `CHANGELOG`：`### PWA/API（NEXT-2 · Quant Intraday Monitor）`；`TODOS` 隊列 33「仍待」改寫。

### 參考檔案

| 檔案 | 用途 |
|------|------|
| [`modules/portfolio/components/WatchlistMonitor.jsx`](../data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx) | row + livePoll 範本 |
| [`modules/quant-trading/pages/QuantHome.jsx`](../data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) | 掛載點 |
| [`paper_lifecycle.py`](../paper_lifecycle.py) | ACTIVE／CLOSED 語意 |
| [`api.py`](../api.py) L991+ | `/api/quant/signals` |
| [`test_api_quant_signals.py`](../test_api_quant_signals.py) | 契約測試 |

### 驗證指令

```bash
pytest test_api_quant_signals.py tests/api/test_paper_lifecycle_api.py -q
cd data-verification-ui && npm run lint && npm run build && npm run test:e2e
```

---

## NEXT-3 — Gate failure detail drawer（FE-4 續）

**對齊**：隊列 **49** / FE-4 · 既有 `GET /api/gate-failures?days=7` · [`Settings.jsx`](../data-verification-ui/src/pages/Settings.jsx) 僅顯示前 5 筆 + `issues_preview`

### 為什麼現在做

Settings 已有摘要列表；維運需 **單次失敗的完整 issue 列表** 與 metadata，對齊 [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](GATE_FAILURE_HINT_WORKFLOW.md)。

### DO

- **API**：新增 `GET /api/gate-failures/{timestamp}`（`timestamp` = URL-safe ISO-8601，與列表列 `timestamp` 一致）。
  - 回傳：`timestamp`、`attempt`、`profile`、`blocking_count`、`warning_count`、`issue_count`、`used_fallback`、`report_chars`（若有）、`issues`（`string[]`）、`issues_preview`、`source`（`bq`｜`fixture`｜`empty`）。
  - **Fixture 路徑**：擴充 [`fixtures/gate_failure_log_fixture.json`](../fixtures/gate_failure_log_fixture.json) 每筆可選 `"issues": ["…", "…"]`（完整列表）；無 `issues` 時 fallback 將 `issues_preview` 以 ` | ` split。
  - **BQ 路徑**：現表僅存 `issues_preview`（見 [`bigquery_writer.py`](../bigquery_writer.py) `write_gate_failure_log`）；本切片 **允許** detail 端點在 BQ 列回傳 `issues: [issues_preview]` 單元素，並在 PR 註記「完整 issues 需另列 BQ migration」— **不要**在本切片改 pipeline 寫入邏輯。
- **前端**：Settings 列表 row 可點擊 → 右側 **drawer** 或全屏 modal（mobile），顯示完整 `issues` 清單 + 計數 badge；`data-testid="settings-gate-failure-drawer"`。
- **Hook**：[`useGateFailureDetail(ts)`](../data-verification-ui/src/hooks/useApi.js) 或擴充既有 query。
- **測試**：[`tests/api/test_gate_failures_api.py`](../tests/api/test_gate_failures_api.py) 新增 detail 404／fixture hit；[`e2e/settings-page.spec.js`](../data-verification-ui/e2e/settings-page.spec.js) 點第一列開 drawer 斷言 issue 文字。

### DO NOT

- 不修改 `validate_report` 規則、不自動改 prompt。
- 不在 UI 假造 Telegram bot 狀態（仍無 endpoint）。
- 不強制 BQ schema migration（可另開維運票）。

### 驗收標準

- [ ] `GET /api/gate-failures/{ts}` 對 fixture 中已知 `timestamp` 回 200 + `issues` 陣列。
- [ ] 未知 `timestamp` → 404；非法 path → 422。
- [ ] Settings 點列開 drawer，顯示比 `issues_preview` 更完整的列表（fixture 含多條 `issues` 時）。
- [ ] `pytest tests/api/test_gate_failures_api.py -q` 綠；`npm run test:e2e` 綠。

### 參考檔案

| 檔案 | 用途 |
|------|------|
| [`api.py`](../api.py) L814+ | 列表 endpoint |
| [`fixtures/gate_failure_log_fixture.json`](../fixtures/gate_failure_log_fixture.json) | fallback 資料 |
| [`tests/api/test_gate_failures_api.py`](../tests/api/test_gate_failures_api.py) | 契約 |
| [`e2e/settings-page.spec.js`](../data-verification-ui/e2e/settings-page.spec.js) | E2E |
| [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](GATE_FAILURE_HINT_WORKFLOW.md) | 人審流程 |

### 驗證指令

```bash
pytest tests/api/test_gate_failures_api.py -q
cd data-verification-ui && npm run test:e2e -- settings-page.spec.js
```

---

## NEXT-4 — Phase 4 IA 44b high-density audit doc（僅文件）

> **2026-05-21 已交付**：新增 [`docs/PHASE4_44B_DENSITY_AUDIT.md`](PHASE4_44B_DENSITY_AUDIT.md)，25 列區塊盤點與維護者 A/B/C 勾選欄；未動 React／API，隊列 62 等待 maintainer pick。

**對齊**：隊列 **44** · [`TODOS.md`](../TODOS.md)「44b 第二波 — 高密度區塊清單」· [`Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) §0 Phase 4

### 為什麼現在做

44b 第一波（dashboard tab、portfolio risk tab、dock 化）已交付；**進階收斂**仍待維護者指定哪些區塊算「高密度」。本切片只產出 **可勾選的盤點表**，不動 React。

### DO

- 新增 [`docs/PHASE4_44B_DENSITY_AUDIT.md`](PHASE4_44B_DENSITY_AUDIT.md)（或併入 `Terminal_Master_Plan` 附錄，二擇一，**勿兩份重複**）：
  - 表格欄位：**路由**｜**區塊名稱**｜**DOM/`data-testid` 錨點**｜**密度標籤**（`reader-low`｜`workbench-mid`｜`workbench-high`）｜**首屏可見？**｜**建議收斂**（tab／dock／defer／keep）｜**N=3 路徑影響**（點擊數估計）。
  - 覆蓋：`/news`、`/columns`（讀者層）、`/insights`、`/dashboard`、`/portfolio`（工作台）；引用既有清單（[`TODOS.md`](../TODOS.md) 隊列 44 內「44b 第二波」三條）。
  - **建議欄**須標「待維護者勾選 A/B/C」— 例如 A=收進 tab、B=移 GlobalWatchlistDock、C=保留。
- 交叉連結 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4f 與 [`DESIGN.md`](../DESIGN.md) Portal Phase 4 腳本。
- `CHANGELOG` + `TODOS`：註明文件已就緒，**程式實作等待 maintainer pick**。

### DO NOT

- **零** `.jsx`／`.py` 行為變更（本切片例外：僅 `.md`）。
- 不擅自改 Gate 0 五項決議或 `portalPhase4.js` 常數。

### 驗收標準

- [x] 新文件至少 **15 列**具體區塊（含 3 工作台 × 各 ≥3 區塊）。
- [x] 每列有可點擊的檔案路徑或 `data-testid`。
- [x] `TODOS` 隊列 44 連結至該文件；`CHANGELOG` `### Docs` 條目。

### 參考檔案

| 檔案 | 用途 |
|------|------|
| [`TODOS.md`](../TODOS.md) § 隊列 44 | 44b 清單來源 |
| [`data-verification-ui/src/constants/portalPhase4.js`](../data-verification-ui/src/constants/portalPhase4.js) | Gate 0 常數 |
| [`e2e/phase4-ia-portal.spec.js`](../data-verification-ui/e2e/phase4-ia-portal.spec.js) | 既有 44b 斷言 |

### 驗證指令

```bash
# Doc-only：確認連結目標存在
test -f docs/BLOOMBERG_ALIGNMENT.md && test -f data-verification-ui/e2e/phase4-ia-portal.spec.js
```

---

## NEXT-5 — `api.py` contract test coverage（隊列 9 續）

**對齊**：隊列 **9** 起點 · [`tests/api/test_api_contract_smoke.py`](../tests/api/test_api_contract_smoke.py) · `TODOS` 隊列 26「依賴隊列 9」

### 為什麼現在做

`api_routers/*` 多有專檔測試，但 [`api.py`](../api.py) 仍掛 **~20 條** inline route；Router 拆分時易靜默回歸。

### DO

- 新增 [`tests/api/test_api_py_contract.py`](../tests/api/test_api_py_contract.py)（或擴充 `test_api_contract_smoke.py`，**擇一**，避免重複）：
  - 每個 endpoint 至少：**status 形狀** + **top-level JSON keys** + **錯誤路徑**（404/422/503 擇 applicable）。
  - `monkeypatch.setenv("SKIP_BIGQUERY", "1")` 為預設；需寫入的用 `tmp_path` + `EXECUTION_INTENT_STORE` 等既有模式。
- **優先覆蓋（目前無專檔或僅間接覆蓋）**：

| Method | Path | 備註 |
|--------|------|------|
| GET | `/api/reports` | `limit`／`profile` query |
| GET | `/api/reports/{date}` | legacy summary |
| GET | `/api/reports/{date}/gate-status` | fixture fallback |
| GET | `/api/reports/{date}/html` | 容忍 404 無檔 |
| GET | `/api/reports/qsrec-stats` | `days` 邊界 1–30 |
| GET | `/api/trades` | 形狀 smoke |
| GET | `/api/trades/performance` | 形狀 smoke |
| GET | `/api/positions/open` | 與 positions bundle 區分 |
| POST | `/api/push/subscribe` | 非法 body → 422（不必真 push） |

- 已有專檔者（`gate-failures`、`quant/*`、`paper/*` 大部分）→ **不重複** exhaustive 測試，僅在表內註記 `covered by X`。

### DO NOT

- 不為通過測試而改 API 語意。
- 不 mock 外部 HTTP（保持 unit／TestClient 層）。
- 本切片不要求 100% line coverage。

### 驗收標準

- [ ] 上表 **≥8** 條新增或明確標註既有測試檔案。
- [ ] `pytest tests/api/test_api_py_contract.py -q`（或擴充後之 smoke 檔）綠。
- [ ] `pytest tests/api/ -q` 全綠。
- [ ] `CHANGELOG`：`### Tests（隊列 9 續 · api.py contract）`。

### 參考檔案

| 檔案 | 用途 |
|------|------|
| [`api.py`](../api.py) | route 定義 |
| [`tests/api/test_api_contract_smoke.py`](../tests/api/test_api_contract_smoke.py) | 既有 smoke 風格 |
| [`test_reports_profile_api.py`](../test_reports_profile_api.py) | reports 相關 |
| [`test_report_structured_api.py`](../test_report_structured_api.py) | structured |
| [`test_brief_layouts_api.py`](../test_brief_layouts_api.py) | brief-layouts |

### 驗證指令

```bash
pytest tests/api/test_api_py_contract.py tests/api/test_api_contract_smoke.py -q
pytest tests/api/ -q
```

---

## 完成任一切片後的必做同步

1. [`CHANGELOG.md`](../CHANGELOG.md) — 使用者可見或測試條目。
2. [`TODOS.md`](../TODOS.md) — 「已交付摘要」或「下一批隊列」對齊；**雙向一致**（見兩檔檔首契約）。
3. 若改 API 契約 — 更新 [`README.md`](../README.md) API 表（如有該 route）。
4. PR 描述貼 **驗證指令輸出**（pytest / e2e 節錄即可）。

---

## 快速自檢（開工前）

```bash
# 確認 FE-6 基線仍綠
cd data-verification-ui && npm run test:e2e

# 確認 API smoke 基線
pytest tests/api/test_api_contract_smoke.py tests/api/test_gate_failures_api.py -q
```

---

*文件版本：2026-05-20 · 對應 `main` 上 FE-1..FE-6 交付狀態。*
