# Codex Handoff — 下一批切片規劃（接續 Frontend UX Overhaul）

> **產生於 2026-05-20，作者：Claude Code on the Web**
> **接手者：Codex**
> **狀態**：尚未動工。每個切片自帶完成標準與測試錨點，可獨立切 PR。

## 0) 為什麼需要這份文件

Frontend UX Overhaul（FE-1～FE-6 / [TODOS](../TODOS.md) 隊列 46–51）剛剛在 2026-05-20 全數合併，對齊紀錄落在 [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4f 與 [`CHANGELOG.md`](../CHANGELOG.md) 同日區塊。此檔把「下一輪可以馬上開工」的工項收斂成 5 個切片：

1. **NEXT-1**　TouchTarget + Dead-CSS Audit（FE-6 故意延後的部份）
2. **NEXT-2**　Quant Intraday Monitor scaffold（隊列 33 後續）
3. **NEXT-3**　Gate Failure 詳情抽屜（FE-4 衍生）
4. **NEXT-4**　Phase 4 IA · 44b 高密度區塊進階收斂
5. **NEXT-5**　`api.py` 端點合約測試（隊列 9）

> **共通紅線**（沿用 [`CLAUDE.md`](../CLAUDE.md) / [`.cursorrules`](../.cursorrules)）
> 1. 不引入未審核即時付費資料源；新來源需先進 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)。
> 2. 不弱化 `validate_report`／Telegram HTML 白名單／無數據幻覺。
> 3. **commit 後直接 `git push origin <branch>`**（不上 PR 也可）；若用 PR 工作流，draft + 自我合併。
> 4. 每個切片完成寫 `CHANGELOG`（同日 `## 2026-MM-DD` 區塊）+ `TODOS`（隊列加 strikethrough / 同步狀態行）。

> **共通驗證命令**
> ```
> cd data-verification-ui && npm run lint && npm run build && npm run test:e2e
> pytest tests/api/<新增測試>.py -x
> ```
> 沙箱無法下載 Playwright 1.59 的 chromium 1217；本機已準備 `/opt/pw-browsers/chromium_headless_shell-1217 → 1194` symlink workaround，必要時可重建。CI 是 source of truth。

---

## NEXT-1 — TouchTarget + Dead-CSS Audit

**動機**：FE-6（隊列 51）刻意未做的兩塊（觸控掃描、`index.css` dead-CSS）blast radius 高、需獨立切片做才安全。對齊 [`DESIGN.md`](../DESIGN.md) §響應式與無障礙 的 **44px 觸控標準**。

**範圍（DO）**

- 掃描 [`data-verification-ui/src/`](../data-verification-ui/src) 所有 `<button>` / `<a>` / `role="button"` / 表單 input；列出 `min-height < 44px` 或 hardcoded `28px`/`32px`/`36px` 的元素。
- 對掃描清單分三類處理：
  1. **主要互動**（list row click / submit / nav） → 拉到 `min-height: 44px`（Tailwind `min-h-[44px]` 或 CSS）。
  2. **次要 icon-only**（chip 內 `×`、刪除小按鈕） → 改 `min-height: 36px` 並把 padding 拉大 hit-slop（`::before` 透明擴大）。
  3. **明顯裝飾**（純文字 link inline） → 保持，但確認 `:focus-visible` 樣式存在。
- **Dead-CSS cleanup**：對 [`index.css`](../data-verification-ui/src/index.css) 每個 class 做 Find All References（`grep -rn "<class>"` over `src/`）；若 0 個 reference 就移除。**保守起見**先 grep `className=`、`class=`、`data-*` selector、`@apply`、`:is(...)` 等，避免誤刪。

**範圍（DO NOT）**

- 不重排 `index.css` 段落結構（保留歷史 git blame）。
- 不引入 CSS-in-JS 或新預處理器。
- 不修改 Tailwind config（額外 utility 不在此切片做）。

**驗收**

- 新檔 [`docs/TOUCH_TARGET_AUDIT.md`](TOUCH_TARGET_AUDIT.md)：列出掃描結果、處理分類、變更清單。
- 全部 E2E 綠（82 案目前，且不應 regression）。
- `git diff --stat` 顯示 `index.css` 行數**淨減**（dead-CSS 真的有刪到）。
- CHANGELOG 區塊 `### PWA（觸控標準掃描）` + `### PWA（dead-CSS 清理）`。

**參考檔**

- [`docs/BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) §4f 觸控標準列。
- [`data-verification-ui/src/index.css`](../data-verification-ui/src/index.css)（~1500 行）。

---

## NEXT-2 — Quant Intraday Monitor scaffold

**動機**：隊列 33（M7 Quant Trading）已交付 Backtest panel，但「Intraday Monitor 與更完整 Signal Table」仍是 backlog。MVP 切片不接 live tick，先以 paper-derived signals + quote refresh 串起來。

**範圍（DO）**

- 後端：新增 `GET /api/quant/signals?days=7`（[`api_routers/quant.py`](../api_routers/quant.py) 已存在，附加端點）；讀 `execution_intents.jsonl` 中 `status in {PENDING_REVIEW, PAPER_OPEN}` 的 row，回 `{ signals: [{symbol, side, entry, sl, tp, signal_quality, opened_at, source}], as_of }`。fixture fallback 用既有 paper data。
- 前端：[`modules/quant-trading/pages/QuantHome.jsx`](../data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 加 `Intraday Monitor` tab 或新區塊；每 row 顯示 symbol／entry／SL／TP／quality grade／距入場時間，row click → `/insights?symbol=`。
- 報價刷新沿用 `useSymbolQuote({ livePoll: true })`，60s 間隔；不另開 SSE。
- 加 E2E [`quant-intraday-monitor.spec.js`](../data-verification-ui/e2e/quant-intraday-monitor.spec.js)：mock 2 signals、表格渲染、row click 跳轉。
- 加後端 test [`tests/api/test_quant_signals_api.py`](../tests/api/test_quant_signals_api.py)：shape、days 邊界、空狀態。

**範圍（DO NOT）**

- 不接券商實盤、不自動下單（保留紅線）。
- 不引入 WebSocket／新 SSE 通道（用既有 polling）。
- 不改 paper_execution.py state machine（讀，不寫）。

**驗收**

- `pytest tests/api/test_quant_signals_api.py` 綠（≥3 案）。
- E2E 全綠（新增 ≥2 案，全套 84/84+）。
- CHANGELOG `### API (/api/quant/signals)` + `### PWA（Quant Intraday Monitor MVP）`。

**參考檔**

- [`api_routers/quant.py`](../api_routers/quant.py)、[`execution_intents.py`](../execution_intents.py)、[`signal_quality.py`](../signal_quality.py)。

---

## NEXT-3 — Gate Failure 詳情抽屜

**動機**：FE-4（隊列 49）的 Settings 列表只顯示 5 個 row + `issues_preview` 摘要。維護者下一步想點 row 看「該次完整 issues」+「對應 report_date／profile 連結」。

**範圍（DO）**

- 後端：[`api.py`](../api.py) `GET /api/gate-failures` 已有 `entries[]`；新增 `GET /api/gate-failures/{timestamp}`（或 `?ts=...`）回 `{ timestamp, attempt, profile, blocking_count, warning_count, issues: [str], fingerprint, report_chars }`；BQ `gate_failure_log` `WHERE timestamp = @ts` LIMIT 1；fixture fallback。
- 前端：新增 `components/report/GateFailureDrawer.jsx`（複用既有 [`GateIssuesDrawer.jsx`](../data-verification-ui/src/components/report/GateIssuesDrawer.jsx) 樣式），點 [`pages/Settings.jsx`](../data-verification-ui/src/pages/Settings.jsx) `settings-gate-failure-row` 開抽屜；抽屜顯示 issues list（每行套 [`gateIssueSeverity.js`](../data-verification-ui/src/components/report/gateIssueSeverity.js)）+ 「跳至報告」連結（若 `timestamp` 對應 `report_date` 可推導）。
- 加 E2E [`settings-gate-detail.spec.js`](../data-verification-ui/e2e/settings-gate-detail.spec.js)：點 row → 抽屜顯示 issues → Esc 關閉。
- 加 backend test [`tests/api/test_gate_failure_detail_api.py`](../tests/api/test_gate_failure_detail_api.py)：404 on 未知 ts、200 + issues array on fixture row。
- mock-api-server 補 endpoint。

**範圍（DO NOT）**

- 不抓 BQ `validate_report` 全文（成本）；只 read `gate_failure_log` 已有欄位。
- 不寫入任何狀態（純讀）。

**驗收**

- `pytest tests/api/test_gate_failure_detail_api.py` 綠。
- E2E 全綠。
- CHANGELOG `### API (/api/gate-failures/{ts})` + `### PWA（Settings · Gate detail drawer）`。

**參考檔**

- [`docs/SQL/bq_brief_profile_columns.sql`](SQL/bq_brief_profile_columns.sql)、[`bigquery_writer.py`](../bigquery_writer.py) `write_gate_failure_log`。
- 既有 [`fixtures/gate_failure_log_fixture.json`](../fixtures/gate_failure_log_fixture.json) — 補 `issues` array 欄位（陣列字串）即可承接。

---

## NEXT-4 — Phase 4 IA · 44b 高密度區塊進階收斂

**動機**：[TODOS 隊列 44](../TODOS.md#queue-44) **44b 仍待維護者指定哪幾塊算「高密度」**（CHANGELOG 2026-05-16 註記）；本切片不擅自指定範圍，但先把工具鏈備好。

**範圍（DO）**

- 新檔 [`docs/PHASE4_HIGH_DENSITY_AUDIT.md`](PHASE4_HIGH_DENSITY_AUDIT.md)：枚舉 [`PortfolioHome`](../data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx)、[`DashboardHome`](../data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`InsightsHome`](../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 三大工作台頁面內**所有 region**（卡片、表格、grid），對每個 region 標記「資訊密度等級」（low/mid/high）、「對工作台關鍵路徑 ≤ 3 click 的影響」、是否屬讀者層。
- 每 region 給「建議動作」：保留 / 折疊到 `<details>` / 移到 Drawer / 移到 `/insights?symbol=`。
- **不真的做收斂**，只交付盤點表 + 建議；維護者拍板後再切 44b 實作子片。
- 若維護者已在某處 inline 指定，可以同 PR 做 1 塊先示範（e.g. PortfolioHome 的某 panel 用 `BriefSectionCard` 包覆）。

**範圍（DO NOT）**

- 不大幅 refactor 工作台頁面結構。
- 不引入新 region 或新 panel。

**驗收**

- 新檔 audit 表 + 建議完整。
- TODOS 隊列 44 補一行 sync status 指向新檔；CHANGELOG `### Docs（Phase 4 IA · 高密度盤點）`。
- 若同 PR 做 1 塊示範，須附 E2E。

**參考檔**

- [`docs/architecture/Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) §0 Phase 4。
- [`data-verification-ui/src/constants/portalPhase4.js`](../data-verification-ui/src/constants/portalPhase4.js) `PORTAL_PHASE4_GATE0`。

---

## NEXT-5 — `api.py` 端點合約測試（隊列 9）

**動機**：[TODOS 隊列 9](../TODOS.md) 早列 P2 / S：「Phase 3 APIRouter 拆分前，先為所有現有 `/api/*` 路由寫合約測試」。隊列 26 已陸續搬到 `api_routers/`，但 `api.py` 仍有約 20+ 端點未有 schema 級合約測試。FE-4 期間新增 `GET /api/gate-failures` 時已示範一個。

**範圍（DO）**

- 盤點 [`api.py`](../api.py) 所有 `@app.get/@app.post/@app.patch` 端點（用 `grep -nE "^@app\.(get|post|patch|delete)" api.py`）。
- 為**尚無 contract test**的端點各補一個 `tests/api/test_<endpoint>_contract.py`：
  - shape 斷言（required keys、type）。
  - 邊界（query param min/max、不存在 ID 404、空狀態）。
  - 必要時用 `monkeypatch.setenv("SKIP_BIGQUERY", "1")` 走 fixture 路徑。
- 補完一份 [`docs/API_CONTRACT_INDEX.md`](API_CONTRACT_INDEX.md)：endpoint → test file 對照表。

**範圍（DO NOT）**

- 不 refactor `api.py`；不抽 router。
- 不引入 schema 驗證庫（Pydantic 已用）；繼續純 dict + assert。
- 不測 BQ live（只 fixture）。

**驗收**

- 至少 **新增 8 個** contract test file，全部 pytest 綠。
- API_CONTRACT_INDEX.md 涵蓋現有 `api.py` 主端點（≥80% coverage）。
- TODOS 隊列 9 strikethrough。
- CHANGELOG `### Tests（api.py 合約測試補完）`。

**參考檔**

- 既有範本：[`tests/api/test_gate_failures_api.py`](../tests/api/test_gate_failures_api.py)、[`tests/api/test_gate_intent_index_api.py`](../tests/api/test_gate_intent_index_api.py)。

---

## 建議執行順序

| 順位 | 切片 | 理由 |
|---|---|---|
| 1 | **NEXT-5** | 風險最低；做完後其他切片改 API 有 safety net |
| 2 | **NEXT-1** | 一次性技術債清理；blast radius 低（純樣式 + 觸控） |
| 3 | **NEXT-3** | 高使用者價值（Settings 串完整 Gate 詳情） |
| 4 | **NEXT-2** | 中度新功能；不需新資料源 |
| 5 | **NEXT-4** | 需維護者拍板；先交付盤點即可 |

---

## 交接備忘

- **PR 命名**：`feat(<scope>): NEXT-<n> — <短描述> (queue <##>)`，draft + 自我合併。
- **branch 命名**：`claude/next-<n>-<slug>` 或 `codex/next-<n>-<slug>`。
- **PR description 模板**沿用 FE-1～FE-6 的「Summary / Decisions / Test plan」三段式。
- **每個切片 commit 後直推 origin/main 也可**（維護者紅線在 [`CLAUDE.md`](../CLAUDE.md)）。
- **問問題**：寧可在 PR description 留 `## Decisions` 段說明擇一即可，不必每件事都先 issue。

收工。
