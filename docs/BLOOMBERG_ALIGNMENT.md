# Bloomberg Terminal 對齊藍圖（Q-Silicon）

本文件定義「對齊 Bloomberg Terminal」在本 repo 的可驗收範圍：  
重點是 **機構工作流與資料可審計性**，不是外觀複製。

關聯文件：
- 儀表板與 API 契約：[docs/DASHBOARD_CONTRACT.md](docs/DASHBOARD_CONTRACT.md)
- Terminal「中段」執行切片：[docs/TERMINAL_MID_TIER_ROADMAP.md](TERMINAL_MID_TIER_ROADMAP.md)
- 產品與技術路線：[docs/ROADMAP_VISION.md](docs/ROADMAP_VISION.md)
- 工程待辦總表：[TODOS.md](TODOS.md)
- ADR 索引：[docs/ADR_INDEX.md](ADR_INDEX.md)

---

## 1) 對齊原則（Scope）

1. 對齊「工作方式」：多資產監控、時間序列 + 事件、投組風險框架、快速切換。
2. 對齊「資料密度」：每個關鍵數值皆能標示來源與時間（as-of）。
3. 對齊「可審計性」：所有客觀數字必須可回溯到工具/BQ，不可由 LLM 推導。
4. 不對齊「專有資產」：Bloomberg 專有欄位、聊天網路、品牌 UI 不納入。

---

## 2) 紅線（不可破）

1. 客觀數據只能來自工具層/BigQuery；不得在渲染層捏造。
2. `validate_report` 仍是日報可信度的最終 Gate，不因終端化放寬。
3. API/PWA 僅做讀取與監控，不替代主管線事實產生流程。

---

## 3) 能力映射（Terminal Capability Map）

| Terminal 能力 | 現況 | 下一步 |
|---|---|---|
| 多監控清單（Launchpad） | War Room + 多頁面 | **Phase 2**：Terminal v2 多分組 + 模板（`qs_terminal_workspace_v2`）、v1 遷移 |
| Symbol 深度頁 | `/api/symbols/{ticker}/snapshot` + Terminal 卡 | **Phase 2**：跨頁 `SymbolFocusBar`（`qs_symbol_focus_v1`）與卡片「設為全域關注」 |
| 事件與價格關聯 | 報告有結構化建議、圖表有時序 | OHLC 上疊加 QSREC/事件標記 |
| 投組/風險 | trades/performance + open positions | watchlist／symbol focus 已接；狀態面板持續迭代 |

---

## 4) 驗收清單（Phase 0 Definition of Done）

以下 15 條至少通過 12 條，才可宣稱「Bloomberg 對齊 Phase 0」：

1. 單一 ticker 可在一頁看到「快照 + 趨勢 + 建議摘要」。
2. 每個 KPI 顯示 `as_of`（時間戳）與資料來源說明。
3. API 鍵名與 [docs/DASHBOARD_CONTRACT.md](docs/DASHBOARD_CONTRACT.md) 一致。
4. 錯誤態明確（不可靜默失敗）；可區分網路錯誤 vs 無資料。
5. demo/mock 與實盤資料視覺上可辨識（提示條）。
6. 同一 ticker 在 Today / Charts / 新頁顯示一致。
7. watchlist/workspace 可保存與恢復（至少 localStorage）。
8. workspace 允許快速重排卡片順序（不需重新載入）。
9. OHLC 圖可疊加 QSREC 事件點（entry/target/stop）。
10. 事件標記僅來自結構化資料，不從自由文字猜測。
11. API 端點有 pytest 覆蓋（正常、404、參數錯誤、BQ 異常）。
12. 前端新增視圖不破壞既有路由與底部導覽。
13. 變更同步更新 CHANGELOG + TODOS（雙向對齊）。
14. 不新增會破壞 Telegram HTML 白名單的輸出流程。
15. 不引入未審核的即時付費資料依賴 — 已審核來源清單與審核流程見 [`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)（2026-05-11）。

### 4b) 條目 6／14／15 的 repo 內自動化錨點（2026-04-14 / 2026-05-11）

- **條目 6（跨頁 ticker 數值一致）**：pytest [`test_terminal_numeric_consistency.py`](../test_terminal_numeric_consistency.py)（`fetch_symbol_quote` 之 `last`／`change_pct_1d` 與 `fetch_symbol_ohlc` 最後一筆 close 於同源 yfinance 時一致）；`GET /api/symbols/{symbol}/snapshot` 回應另含 **`price_alignment`**（`symbol_snapshot_service._align_snapshot_price`；欄位含 **`ohlc_source`／`quote_source`／`daily_metrics_source`** 與 **`routes`**）與 `data_provenance.price_alignment`；可選 **`PRICE_ALIGNMENT_E2E_OVERRIDES`**（JSON，見 `ENV_TEMPLATE.txt`）。**實盤觀測**：[`scripts/symbol_price_probe.py`](../scripts/symbol_price_probe.py)（stdout JSON；可選 **`PRICE_PROBE_WRITE_BQ`** 寫入 [`docs/SQL/price_probe_log.sql`](../docs/SQL/price_probe_log.sql)）。**UI 層**：Playwright [`e2e/cross-page-btc-price.spec.js`](../data-verification-ui/e2e/cross-page-btc-price.spec.js)、[`e2e/nvda-cross-route-banner.spec.js`](../data-verification-ui/e2e/nvda-cross-route-banner.spec.js)（`npm run test:e2e`）。
- **條目 14（Terminal 變更回歸紀錄）**：CI 步驟「Terminal contract」執行 [`scripts/ci_terminal_contract_check.sh`](../scripts/ci_terminal_contract_check.sh)（`pytest test_terminal_numeric_consistency` + PWA `npm run build`）。
- **條目 15（即時付費資料依賴審核）**：治理文件 [`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md)（已審核來源清單、新增來源 PR 審核表、移除流程）。新增來源前須於 PR 描述完成第 3 節審核表。

### 4c) 跨路由數字口徑（T2a — snapshot vs quote）

| 欄位／UI | 資料來源 | 語意 |
|---------|----------|------|
| `GET …/snapshot` 之 `price_series[].close` | yfinance 日線 OHLC（經 `symbol_snapshot_service`） | K 線與「尾端 bar」錨點 |
| `GET …/quote` 之 `last` | 同源 yfinance 日線 **收盤**（`fetch_symbol_quote`） | Terminal／Today 頂欄「最新收盤（日線）」 |
| `price_alignment` | 後端比對 OHLC 最後一筆 `close` 與 quote `last` | `aligned: true` 表示兩者一致；`false` 時 UI **必須**顯示警告（見 PWA `TerminalSymbolCard`／`TodayBtcSnapshotStrip`） |
| 任一來源失敗 | — | quote 503 或 snapshot BQ 異常時顯示錯誤態＋重試；**不以 LLM 補數字** |

### 4d) Insights／儀表板與 `symbol` query（T5a 補遺）

| 能力 | 路由／參數 | 備註 |
|------|------------|------|
| 結構化日報（區塊導覽） | `GET /api/reports/{date}/structured?profile=…` | `profile` 與 `REPORT_PROFILE`／validate_report 對齊；PWA Archive／Report 深連結 |
| 產業趨勢頁 | `/industries` + `useIndustryThemes` + `useStructuredReports` | 靜態 M5 卡與近 N 日 `industry_trends` 區塊；另可讀 **`GET /api/brief-layouts`** 對照 YAML 庫存（不推斷 `BRIEF_DYNAMIC_RENDER` 執行態） |
| 數據儀表板 macro | `GET /api/macro/snapshot` | 指標 grid + `as_of`；離線提示見 `docs/PWA_OFFLINE.md` |

Streamlit 與 PWA 應消費**同一 JSON**（`build_symbol_snapshot` 或 `SYMBOL_SNAPSHOT_HTTP_BASE` + HTTP），見 [`docs/DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md) 與 [`dashboard.py`](../dashboard.py) `_dashboard_symbol_snapshot_payload`。

### 4e) Phase 4 IA（讀者層 × 工作台層）對 §4 驗收的影響（2026-05-16）

> 對齊 [`Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) **§0 Phase 4**「BLOOMBERG_ALIGNMENT」對齊點：「延續工作流可審計與 §4 驗收習慣；不把新聞／專欄首屏做成報價牆或不可溯源數字堆疊。」Gate 0 權威值見 [`portalPhase4.js`](../data-verification-ui/src/constants/portalPhase4.js) `PORTAL_PHASE4_GATE0`。

| # | 驗收條目 | Phase 4 IA 落地後狀態 | 證據 |
|---|---------|---------------------|------|
| 6 | 同一 ticker 在不同頁顯示一致 | **仍合規**：44c `?focus=` 只做卡片過濾，未引入新報價來源；symbol → `/insights?symbol=` 仍走 `useAnalysisBundle`（quote/snapshot 同源）。`price_alignment` 規則不變。 | [`SymbolDeepDive.jsx`](../data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx)、[`NewsHome.jsx`](../data-verification-ui/src/modules/news/pages/NewsHome.jsx) |
| 7 | watchlist／workspace localStorage 持久化 | **不受影響**：Phase 4 IA 未動 [`WorkspacePanel.jsx`](../data-verification-ui/src/components/WorkspacePanel.jsx) 與 `qs_workspace_size_weights_v1` 鍵。 | 既有 Phase 2 切片 |
| 8 | workspace 卡片重排 | **不受影響** | 同上 |
| 9 | OHLC + QSREC 事件標記 | **不受影響**：未動圖表層。 | — |
| 10 | 事件標記僅來自結構化資料 | **強化**：讀者頁 `?focus=` 過濾條件來自 `tickers`（結構化欄位）並加文字 fallback；過濾結果不衍生新數字。 | `matchesFocus` / `columnsMatchFocus` |
| 11 | API 端點 pytest 覆蓋 | **不受影響**：Phase 4 未開新 API；既有 SSE 安全收尾 [`tests/api/test_sse_token.py`](../tests/api/test_sse_token.py)。 | — |
| 12 | 前端新增視圖不破壞既有路由與底部導覽 | **合規**：44c 僅加 query param `?focus=`、`?symbol=`、`?tab=`；未新增路由；`Shell` + `SideNav`／`ModuleNav` 不變。 | [`phase4-ia-portal.spec.js`](../data-verification-ui/e2e/phase4-ia-portal.spec.js) |
| 13 | 變更同步更新 CHANGELOG + TODOS | **合規**：44a／b／c／d 與 Gate 0 簽核每切片寫 CHANGELOG／TODOS 雙向對齊。 | CHANGELOG 2026-05-16；TODOS 隊列 44 |
| 14 | 不破壞 Telegram HTML 白名單 | **合規**：Phase 4 為 PWA-only，未動 `main.py`／`report_html_gates`／Telegram 出口。 | 隊列 44 紅線 |
| 15 | 不引入未審核的即時付費資料依賴 | **合規**：44c 未新增資料源；雙向 CTA 僅重用既有 `?focus=`／`?symbol=` 深連結契約。 | [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](REALTIME_DATA_SOURCES_GOVERNANCE.md) |

**Phase 4 IA 專屬驗收尺**（不屬 §4 原 15 條，但對齊 Master Plan §0 Phase 4 原則）：

- **讀者首屏密度**：`/news`／`/columns` 不放高密度報價／矩陣表（Gate 0 #2）。
- **工作台關鍵路徑** ≤ **N=3** 點擊（Gate 0 #5）：警報 → 標的／狀態 →（可選）回新聞／專欄脈絡。**人測驗收**，未自動化；44b 進階收斂時再以此為尺。
- **融合方向**：雙向，但**反向（workbench → reader）僅做 CTA + `?focus=`**，不在工作台層放讀者導覽元件。

### 4f) PWA 行動裝置 + 桌面體驗（2026-05-20 — FE-1～FE-6 收尾）

| 面向 | 現況 | 錨點 |
|------|------|------|
| Mobile bottom-tab + Desktop side-nav 共存 | `.bottom-nav` 手機顯示、768px+ 隱；`.side-nav` 手機隱、768px+ `display:flex`；五板塊 routes 共用 | FE-1 / 隊列 46；[`responsive-app-shell.spec.js`](../data-verification-ui/e2e/responsive-app-shell.spec.js) |
| CSS 變數 | `--bottom-tab-height`、`--sidebar-width`、`--sidebar-width-xl` 在 `:root`；`.side-nav` 寬度全部走變數 | FE-1；[`index.css`](../data-verification-ui/src/index.css) |
| Daily Brief 折疊 + 主代號條 + Gate 徽章 | `StructuredReportView` 包覆 `BriefSectionCard` 折疊；頁頂 `TickerStrip` 手機 scroll／桌面 wrap；`GateBadge` 緊湊 ✓／✗ | FE-2 / 隊列 47；[`daily-brief-collapse.spec.js`](../data-verification-ui/e2e/daily-brief-collapse.spec.js) |
| Watchlist Monitor + live 報價 | Portfolio `?tab=monitor` 掛 `WatchlistMonitor`，逐 row `useSymbolQuote(livePoll)`，row click → `/insights?symbol=` | FE-3 / 隊列 48；[`monitor-watchlist.spec.js`](../data-verification-ui/e2e/monitor-watchlist.spec.js) |
| Settings 集中化 | `.settings-grid`（手機單欄 → 768px+ 3 欄）：Gate 通過率、輪詢頻率 toggle、Gate 失敗列表 + `GET /api/gate-failures` | FE-4 / 隊列 49；[`settings-page.spec.js`](../data-verification-ui/e2e/settings-page.spec.js) + [`tests/api/test_gate_failures_api.py`](../tests/api/test_gate_failures_api.py) |
| 桌面鍵盤捷徑 | `useKeyboardShortcuts` chord `G B / G M / G S` + SideNav `⌘K · G B · G M · G S` hint；手機 `< 768px` no-op | FE-5 / 隊列 50；[`command-bar.spec.js`](../data-verification-ui/e2e/command-bar.spec.js) |
| 離線提示 | `OfflineBanner`（`today-offline-banner`）掛在 `StructuredReportView` 與 `WatchlistMonitor`，`navigator.onLine === false` 時顯示；對齊 [`service-worker.js`](../data-verification-ui/src/service-worker.js) `/api` NetworkOnly 策略 | FE-6 / 隊列 51；[`offline-banner.spec.js`](../data-verification-ui/e2e/offline-banner.spec.js) |
| BottomNav active 動畫 | `.nav-item.active .nav-icon { transform: scale(1.1) }` + label fade（opacity 0.85 → 1） | FE-6 / 隊列 51 |
| 觸控標準 | BottomNav／SideNav／Settings toggle／Monitor row／Brief 折疊按鈕 ≥ 44px；既有 `min-h-[44px]` Tailwind 慣例延續 | DESIGN.md §響應式與無障礙 |

**驗證**：mobile 375px + desktop 1280px viewport 由 [`responsive-app-shell.spec.js`](../data-verification-ui/e2e/responsive-app-shell.spec.js)、[`daily-brief-collapse.spec.js`](../data-verification-ui/e2e/daily-brief-collapse.spec.js)、[`settings-page.spec.js`](../data-verification-ui/e2e/settings-page.spec.js)、[`command-bar.spec.js`](../data-verification-ui/e2e/command-bar.spec.js)、[`offline-banner.spec.js`](../data-verification-ui/e2e/offline-banner.spec.js) 分別覆蓋；`npm run test:e2e` 整體 ≥ 80 案綠（隊列 50 已 80/80，隊列 51 視 CI 為準）。

---

## 5) 分階實作路徑（Execution Slices）

1. **Slice A**：Symbol Snapshot API + 測試 + 契約欄位。  
2. **Slice B**：PWA Symbol 深度頁（快照、趨勢、報告連結）。  
3. **Slice C**：Workspace（可儲存、可重排）串接 Symbol 卡。  
4. **Slice D**：OHLC + QSREC/事件標記。  
5. **Phase 2**：Workspace 分組／模板、跨頁 Symbol Context、Streamlit 與 API 共用 snapshot 組裝（`symbol_snapshot_service` + 可選 `SYMBOL_SNAPSHOT_HTTP_BASE`）。

每個 slice 落地後都需同步更新 [CHANGELOG.md](CHANGELOG.md) 與 [TODOS.md](TODOS.md)。
