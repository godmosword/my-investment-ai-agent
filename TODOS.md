# Q-Silicon — 工程與產品待辦（導覽）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md) · **Terminal 總表** → [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) · **路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) · **Bloomberg 對齊驗收** → [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) · [**進度分析表（日報／財報／Terminal 對齊）**](#progress-vs-wall-st-bloomberg) · **執行路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) · **長期里程碑索引** → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) · [**git pull／讀 codebase 時先看**](#pull-or-read-codebase-reminder)

**`docs/architecture/` Phase 0（判讀治理）**：**事實**以 [`CHANGELOG.md`](CHANGELOG.md) 與程式為準；**架構目錄索引**僅認 [`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) **§0 狀態矩陣**（✅／🟡）。矩陣標 🟡 之 `*_research.md` 等為研究或 optional scaffold，**非**預設產品承諾；若列為里程碑須帶 ENV／紅線／驗收並寫入本檔隊列。協作準則見 [`AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md)。**§0 Phase 4（讀者層×工作台層 IA）**：新聞／專欄與工作台同一 Portal、不同密度；維護者 REVIEW 決策見該節；**實作切片**見 [`TODOS.md`](#terminal-master-plan-phase4-queue-44) **隊列 44**（44a–44d）與 [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) **§ Phase 4 IA**；落地後同步本檔／`CHANGELOG`。**§3 前端尚缺方向** 是 CEO 盤點／滾動索引，不取代本檔隊列；重大 Portal ship 後須對帳 `CHANGELOG`／本檔，必要時補 `Terminal_Master_Plan` §3 修訂紀錄。

**同步狀態（2026-09-06 — ITER-API-SLIM-002 · P2-1）**：`/api/reports*` 九條 route 由 `api.py` 搬入 [`api_routers/reports.py`](api_routers/reports.py)，宣告順序照搬（`profile-stats`／`qsrec-stats` 需在 `/{report_date}` 之前），OpenAPI path／method 表逐字相同；`api.py` 1806 → 902 行。**已知既有缺陷**：`GET /api/reports/{date}/html` 因 `jinja2.Markup`（3.1 起移至 `markupsafe`）在報告存在時 500，搬遷前即如此，另切片修。下一批：trades／paper（含 `_paper_tick_lock`）／push／SSE，各一 PR；paper `pnl`／`execution-tick` 與 `/api/war-room/latest` 需先補最小契約測試。**本整理不部署 Service**。見 CHANGELOG **2026-09-06**。

**同步狀態（2026-09-06 — ITER-API-SLIM-001 · P1）**：HTTP API 與日報 Job 的**啟動路徑**解耦 — `scipy`（`bigquery_writer` 語義去重）、`telebot`／`redis`（`telegram_sender`）、`yaml`／`paper_execution`（`api.py`）改 lazy，`import api` 1.15s → 0.80s；新增 [`tests/api/test_api_import_boundary.py`](tests/api/test_api_import_boundary.py) 守門。`google.cloud.bigquery` 仍在啟動路徑（`api_deps`／`symbol_snapshot_service` 頂層 import），待 router 搬遷切片。**Job ≠ Service：本整理不部署 Service**，正式 Cloud Run Service 503 未動。見 CHANGELOG **2026-09-06**。

**同步狀態（2026-09-05 — ITER-GO-LIVE-001）**：`GET /healthz` 廉價 liveness（無 master key；`{"ok": true, "service": "api"}`）；`smoke:prod` fail-closed 只認該契約。Job ≠ Service；正式 Cloud Run Service 仍 **503**、`/healthz` **404** — 本切片不部署、不假裝康復。見 [`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)「2026-09-05 正式上線」、CHANGELOG **2026-09-05**。

**同步狀態（2026-09-05 — ITER-TR-LOOP-001）**：`/insights` 首屏今日建議下「紙上對帳」— 只對已解析標的標無紙上／未結／已結＋API 報酬／UNKNOWN；未結只看生命週期／意圖（實績 closed 舊市價快照不誤判）。未上 production。見 CHANGELOG **2026-09-05**。

**同步狀態（2026-09-05 — ITER-TR-AUDIT-001）**：`/insights` 實績頁紙上可審計摘要 — 期間／截至／樣本／來源、內部透明度／納入規則依 source（jsonl 已結 vs BQ 可含市價結算）、無 quality 不假裝過濾、上期追蹤有連結欄才顯示否則 UNKNOWN。既有 KPI 語意不變；未上 production。見 CHANGELOG **2026-09-05**。

**同步狀態（2026-08-15 — Portal Vercel harden）**：[`data-verification-ui/vercel.json`](data-verification-ui/vercel.json) **`git.deploymentEnabled.main=false`** — `main` 不再由 Git Integration 遠端 `vite build` 上正式站；Production 只走 [`pwa-deploy.yml`](.github/workflows/pwa-deploy.yml) prebuilt。`VITE_API_URL` 真相來源＝GitHub secret；Preview 須 Dashboard Preview env。SSO：建議 Production 關、Preview 留（Dashboard 人工）。見 [`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)、CHANGELOG **2026-08-15**。

**同步狀態（2026-06-16 — PWA + Cloud Run Service 已對接）**：[`pwa-deploy.yml`](.github/workflows/pwa-deploy.yml) **verify**（lint + E2E **86/86**）+ **deploy-vercel** 全綠；正式站 [`my-investment-ai-agent.vercel.app`](https://my-investment-ai-agent.vercel.app) 靜態路由 200。**Cloud Run Service** `my-investment-ai-agent-api`（FastAPI）已部署；GitHub secret **`VITE_API_URL`** 已指向該 Service origin，PWA macro 數據已驗證。**Job**（日報 pipeline）與 **Service**（HTTP API）並存 — 勿再假設「僅 Job、無 Service」。**`npm run smoke:prod`** 見 [`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)（API liveness 只認 `GET /healthz` HTTP 200 + 精確 `{"ok": true, "service": "api"}`；不以 `/docs`／`/openapi.json` 當 liveness）。**Agent 編排**：[`docs/AGENT-WORKFLOW.md`](docs/AGENT-WORKFLOW.md) + [`.cursor/commands/`](../.cursor/commands/)。見 CHANGELOG **2026-06-16**。

**同步狀態（2026-05-20 — Session 總表 · 隊列 57–71 入列）**：維護者策略 **工作流脊骨優先**、**不採** Glassnode／CryptoQuant／TrendForce 付費訂閱；[Session 總執行順序](#session-2026-05-20-execution-order) 收斂 CODEX **NEXT-1～5**（隊列 **57–61**）、免費資料 **52–56**、工作流／閉環／研究／規劃流程（隊列 **62–71**）。見 [§ Codex／FE-6 收尾](#codex-fe6-closeout-queue-57)、[§ 工作流脊骨](#workflow-spine-queue-62)、[§ Terminal 閉環](#terminal-closed-loop-queue-65)、[§ 研究與 Gate](#research-gate-queue-68)。

**同步狀態（2026-05-22 — GATE_EXECUTION_FAILED · Agency 空 deliverables）**：[`schemas.py`](schemas.py) **`normalize_optional_agency_research_output`** + **`AISection`** 解析前丟棄無效 payload；[`graph/graph_nodes.py`](graph/graph_nodes.py) formatter 組裝與 **`agency_researcher_node`** 獨立 dump；[`graph/graph_crew.py`](graph/graph_crew.py) 初始 state 移除空 **`agency_research_output`**。CHANGELOG **2026-05-22** `### Fix（GATE_EXECUTION_FAILED · AgencyResearchOutput 空 deliverables）`。

**同步狀態（2026-05-21 — NEXT-4 44b 高密度盤點）**：新增 [`docs/PHASE4_44B_DENSITY_AUDIT.md`](docs/PHASE4_44B_DENSITY_AUDIT.md)，盤點 `/news`、`/columns`、`/insights`、`/dashboard`、`/portfolio` 與 global dock 共 25 個區塊，附 DOM／`data-testid` 錨點、密度標籤、首屏可見性、建議收斂、N≤3 影響與維護者 A/B/C 勾選欄。此切片純文件，隊列 **62** 實作需等待 maintainer pick。CHANGELOG **2026-05-21** `### Docs（NEXT-4 · 44b high-density audit）`。

**同步狀態（2026-05-21 — 隊列 52 F0 免費資料治理底座）**：[`REALTIME_DATA_SOURCES_GOVERNANCE.md`](docs/REALTIME_DATA_SOURCES_GOVERNANCE.md) 補登 CoinGecko public/Demo API、Alternative.me Fear & Greed、Blockchain.com charts、DefiLlama public API（pending）；[`DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) 新增「免費資料擴充區塊」欄位語意與降級契約；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 補治理註記。未新增 fetcher、未新增讀取中的 secret。CHANGELOG **2026-05-21** `### Docs（隊列 52 · F0 免費資料治理底座）`。

**同步狀態（2026-05-21 — 隊列 53 FA-2 exchange-flow honesty）**：[`GET /api/macro/onchain`](api_routers/macro.py) 的 `exchange_flow` 改為 `enabled=false`／`reason=no_free_equivalent`／`live_block_status.exchange_flow=disabled`，Portal [`OnchainMetricsPanel.jsx`](data-verification-ui/src/components/OnchainMetricsPanel.jsx) 顯示「CEX 淨流：無免費同級來源」，不再渲染 All CEX／Binance／Coinbase mock 淨流表。未新增資料源、未用 funding 冒充 netflow、未動日報 pipeline。CHANGELOG **2026-05-21** `### API/PWA（隊列 53 · FA-2 exchange-flow honesty）`。

**同步狀態（2026-05-20 — 免費資料擴充路線 F0～FD · A/B/C/D 入列）**：維護者決策 **不採** Glassnode／CryptoQuant／TrendForce 付費訂閱；改以 **free／freemium 盤活 + Portal 露出** 拉高 Bloomberg 對齊之資料廣度（隊列 **52–56**）。橫切 **F0** 對齊 [`CODEX_NEXT_BATCH`](docs/CODEX_NEXT_BATCH.md) NEXT-5／治理表；**FA** 加密鏈上／情緒、**FB** 算力／半導體、**FC** 宏觀、**FD** 財報／基本面。隊列 **45** 付費 live backlog 改列「刻意延後」。見本檔 [「免費資料擴充（隊列 52–56）」](#free-data-expansion-queue-52)。

**同步狀態（2026-05-20 — Codex 下一批 handoff 文件）**：新增 [`docs/CODEX_NEXT_BATCH.md`](docs/CODEX_NEXT_BATCH.md)（NEXT-1 touch target／dead CSS、NEXT-2 Quant intraday、NEXT-3 Gate failure drawer、NEXT-4 44b 密度盤點、NEXT-5 `api.py` contract tests；建議順序與 FE-6 延後項對齊）。CHANGELOG **2026-05-20** `### Docs（Codex 下一批 handoff）`。

**同步狀態（2026-05-20 — NEXT-2 Quant Intraday Monitor）**：`GET /api/quant/signals` 改由 paper `execution_intents.jsonl` active rows 衍生（無 active row 時保留 placeholder fallback）；[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 新增 Intraday Monitor，使用既有 `useSymbolQuote({ livePoll: true })` 顯示報價、支援 filter 與 row → `/insights?symbol=...`。新增 [`quant-intraday-monitor.spec.js`](data-verification-ui/e2e/quant-intraday-monitor.spec.js)，紅線：無新付費行情源、無自動交易、未動日報 pipeline。CHANGELOG **2026-05-20** `### PWA/API（NEXT-2 · Quant Intraday Monitor）`。

**同步狀態（2026-05-20 — FE-6 切片 · Frontend UX Overhaul 收尾）**：新增 [`components/OfflineBanner.jsx`](data-verification-ui/src/components/OfflineBanner.jsx) 共用組件（`navigator.onLine` event listener，`today-offline-banner` class／testid），掛入 [`StructuredReportView`](data-verification-ui/src/components/report/StructuredReportView.jsx)（戰報頁）與 [`WatchlistMonitor`](data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx)（`/portfolio?tab=monitor`）；BottomNav `.nav-item.active .nav-icon { transform: scale(1.1) }` + label opacity fade（[`index.css`](data-verification-ui/src/index.css)）；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) 新增 **§4f PWA 行動裝置 + 桌面體驗驗收表**（覆蓋 FE-1～FE-6 全部錨點）；新增 [`e2e/offline-banner.spec.js`](data-verification-ui/e2e/offline-banner.spec.js)；`npm run test:e2e` 全綠（82/82）。**刻意未實作**：規格的全頁 touch target 掃描與 `index.css` dead CSS 清理（blast radius 高，留待 a11y audit 切細片）。CHANGELOG **2026-05-20** `### PWA（隊列 51 · FE-6 PWA Polish + 離線橫幅 + 跨裝置驗收）` + `### Docs（BLOOMBERG_ALIGNMENT §4f）`。**FE-1～FE-6 全數交付**，Frontend UX Overhaul 階段 6/6 收尾完成。

**同步狀態（2026-05-20 — FE-5 切片）**：規格新 `CommandBar.jsx` 與既有 [`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx)（已含 `Cmd+K`）重複；本切片補差距 — 新增 [`hooks/useKeyboardShortcuts.js`](data-verification-ui/src/hooks/useKeyboardShortcuts.js)（chord `G→B`／`G→M`／`G→S`，1500ms 視窗，輸入框不攔截，`window.innerWidth < 768` 早返），於 [`Shell.jsx`](data-verification-ui/src/app/layout/Shell.jsx) 掛全域 listener；[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) footer 補 `⌘K · G B · G M · G S` kbd 鏈；新增 [`e2e/command-bar.spec.js`](data-verification-ui/e2e/command-bar.spec.js) 五案。`npm run test:e2e` 全綠（80/80）。CHANGELOG **2026-05-20** `### PWA（隊列 50 · FE-5 Command Bar + Shortcuts 差距補完）`。

**同步狀態（2026-05-20 — FE-4 切片）**：規格新檔 `SettingsPage.jsx` 與既有 [`pages/Settings.jsx`](data-verification-ui/src/pages/Settings.jsx) 重複；改在既有檔頂部加 `.settings-grid`（mobile 單欄 → 768px+ 3 欄），新增三區段 — **Gate 通過率（qsrec-stats）**、**盤中輪詢頻率 toggle**（localStorage `qs_terminal_poll_ms_override`）、**Gate 失敗記錄**（新 endpoint `GET /api/gate-failures?days=7`，[`api.py`](api.py) + [`fixtures/gate_failure_log_fixture.json`](fixtures/gate_failure_log_fixture.json) fallback）；新增 [`useGateFailures`](data-verification-ui/src/hooks/useApi.js)、[`tests/api/test_gate_failures_api.py`](tests/api/test_gate_failures_api.py)、[`e2e/settings-page.spec.js`](data-verification-ui/e2e/settings-page.spec.js)；`pytest` 3/3、`npm run test:e2e` 75/75 全綠。**刻意未實作**：Telegram bot 狀態（無 endpoint，避免假狀態）。CHANGELOG **2026-05-20** `### API（/api/gate-failures）` + `### PWA（隊列 49 · FE-4 Settings 集中化差距補完）`。

**同步狀態（2026-05-20 — FE-3 切片）**：FE-3 規格 `/monitor` 新路由與 5 板塊收斂衝突；改為在 [`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) 新增 `Monitor` tab（`/portfolio?tab=monitor`），新增 [`modules/portfolio/components/WatchlistMonitor.jsx`](data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx)（共用 `qsi_watchlist`、`useSymbolQuote { livePoll:true }` 即時報價、漲跌 badge、搜尋過濾、row click → `/insights?symbol=…`）；新增 [`e2e/monitor-watchlist.spec.js`](data-verification-ui/e2e/monitor-watchlist.spec.js)。`npm run test:e2e` 全綠（73/73）。**刻意未實作**：桌面 split-pane（既有 SymbolDeepDive 已是詳情頁）、`assets_config.json` 預載（避免覆蓋使用者）、`wl_symbols` key（沿用 `qsi_watchlist`）。CHANGELOG **2026-05-20** `### PWA（隊列 48 · FE-3 Monitor tab 差距補完）`。

**同步狀態（2026-05-20 — FE-2 切片）**：FE-2 規格目標頁實際為 Terminal 工作區（非戰報），真正戰報頁是 `/report/:date` → `StructuredReportView`；本切片在該檔補差距 — 新增 [`components/report/BriefSectionCard.jsx`](data-verification-ui/src/components/report/BriefSectionCard.jsx)（chevron 折疊、blockId localStorage 持久化）、[`TickerStrip.jsx`](data-verification-ui/src/components/report/TickerStrip.jsx)（頁頂主代號條，手機 scroll／桌面 wrap）、[`GateBadge.jsx`](data-verification-ui/src/components/report/GateBadge.jsx)（緊湊 Gate 通過徽章）；ProfileSwitcher 沿用既有 `BriefProfileBar`；新增 [`e2e/daily-brief-collapse.spec.js`](data-verification-ui/e2e/daily-brief-collapse.spec.js)。CHANGELOG **2026-05-20** `### PWA（隊列 47 · FE-2 Daily Brief 重構差距補完）`。

**同步狀態（2026-05-20 — FE-1 切片）**：核對後 FE-1 主體（mobile BottomNav + desktop SideNav 共存）早已隨 5 板塊改版交付；本切片補差距 — [`data-verification-ui/src/index.css`](data-verification-ui/src/index.css) `:root` 新增 `--bottom-tab-height`／`--sidebar-width`／`--sidebar-width-xl` 並替換 `.side-nav` 寬度 hardcode；新增 [`data-verification-ui/e2e/responsive-app-shell.spec.js`](data-verification-ui/e2e/responsive-app-shell.spec.js)（375px BottomNav 顯示、1280px SideNav 顯示、CSS 變數存在性）。**刻意未實作**：規格原文「三 Tab + `/briefs`／`/monitor`」與 5 板塊路由衝突，沿用 5 板塊不改 routes、不另建 `BottomTabBar.jsx`。CHANGELOG **2026-05-20** `### PWA（隊列 46 · FE-1 Responsive App Shell 差距補完）`。

**同步狀態（2026-05-20）**：新增 Frontend UX Overhaul FE-1～FE-6 隊列規劃（Mobile + Desktop Responsive；底部 Tab、SideNav 共存、可折疊卡片、Monitor split-pane、Command Bar、PWA Polish）；程式未動，純文件對齊。

**同步狀態（2026-05-17 — Terminal Master Plan §3 對帳）**：[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 新增／補強 **§3 前端尚缺方向**，將前端缺口收斂為交付與可觀測、隊列 26 架構、Command Bar／ADR、隊列 45 live 解鎖、模組深度、效能／a11y／i18n、刻意往後與 NOT in scope；同節補 **Portal ship 對帳儀式**，規定重大 ship 後回寫 `CHANGELOG`／本檔，細項仍回 `TODOS` 隊列承接。CHANGELOG **2026-05-17** `### Docs（Terminal Master Plan §3 前端缺口盤點）`。

**同步狀態（2026-05-17 — 隊列 26 Router 抽出／邊界補強／bundle 續拆 + 隊列 29 Command Bar 說明）**：[`App.jsx`](data-verification-ui/src/App.jsx) 將 route table、legacy redirects、`SymbolQuerySync`、`Shell`／`BottomNav` 包裝抽至 [`PortalRoutes.jsx`](data-verification-ui/src/app/routes/PortalRoutes.jsx)；`App.jsx` 保留全域 providers 與 Router wiring，路由行為不變。[`PortalRoutes.jsx`](data-verification-ui/src/app/routes/PortalRoutes.jsx) 以 **`React.lazy` + `<Suspense>`** 做 route-level code split（板塊頁與 `Report`／`Settings`／`ApiKeyPage`／`Archive`），主入口 bundle 縮小、**已無**既有 ~500 kB 單檔警告。[`vite.config.js`](data-verification-ui/vite.config.js) **`manualChunks`** 拆 `react`／`react-dom`／`react-router`；[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 各 Insights tab **`React.lazy`** + 共用 `Suspense`，`SymbolDeepDive` 僅 `symbol` query 時 lazy；[`DailyBriefPage.jsx`](data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx) 對 `TerminalSymbolCard`／`ExecutionIntentsBlotter` **`lazy`**；[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) 內 **`SymbolCandleChart`** 再 **`lazy` + `Suspense`**，符號卡殼層與 **`lightweight-charts`** 圖表 async 分離。[`eslint.config.js`](data-verification-ui/eslint.config.js) 模組邊界擴至 `daily-brief`、`investment-analysis`、`industry-trends`、`quant-trading`；[`briefs-alias-route.spec.js`](data-verification-ui/e2e/briefs-alias-route.spec.js) 補 `/` redirect smoke。隊列 29 追加 [`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) inline help 與 [`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js) `getTerminalCommandExamples()`，只揭示現有指令與權限邊界，不新增後端 W 類指令。驗證：`cd data-verification-ui && npm run lint && npm run build && npm run test:e2e`（65/65）綠。CHANGELOG **2026-05-17** `### PWA（隊列 26 · Router 抽出／bundle 續拆）`、`### PWA（隊列 29 · Command Bar 權限說明）`；[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) §3.2／§3.6／修訂紀錄。

**同步狀態（2026-05-16 — PWA 上線前生產準備）**：[`data-verification-ui/.env.example`](data-verification-ui/.env.example)、[`PortalShellAlerts.jsx`](data-verification-ui/src/components/PortalShellAlerts.jsx)（production 缺 `VITE_API_URL` banner、API 網路／5xx 簡訊、SW 更新條）、[`Settings.jsx`](data-verification-ui/src/pages/Settings.jsx)（SSE／STRUCTURED 唯讀 + `/healthz` 探活）、[`pwa-deploy.yml`](.github/workflows/pwa-deploy.yml)（**verify** job 已含 lint→build→E2E；**`deploy-placeholder`** 為**設計上的占位**，待維護者選定託管商後補 secrets 與實際 deploy 步驟，見檔頭 `TODO(maintainer)` 註解與 [`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)）、[`smoke-prod.sh`](data-verification-ui/scripts/smoke-prod.sh)、`npm run smoke:prod`、README 旗標表；[`package-lock.json`](data-verification-ui/package-lock.json)（根 `.gitignore` `!data-verification-ui/package-lock.json` 例外後已提交，供 `actions/setup-node` `cache-dependency-path` 與 **`npm ci`**）；CHANGELOG **2026-05-16**「### PWA — 正式上線前生產準備」與「### CI（`pwa-deploy` — `setup-node` npm 快取）」。

**同步狀態（2026-05-16 — Phase 4 IA）**：[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) §0 **實作規劃**（Gate 0、**44a–44d** 表）；[`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) **§ Phase 4 IA**；本檔 [**隊列 44**](#terminal-master-plan-phase4-queue-44)；[`CLAUDE.md`](CLAUDE.md) **Phase 0–4**；**首波 PWA 實作** — [`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js)（Gate 0 預設常數）、讀者／工作台導引條、Command Bar placeholder 分路、Playwright **`phase4-ia-portal.spec.js`**；CHANGELOG **2026-05-16**「### PWA（隊列 44）」。**2026-05-16（續）— 44c 融合層**：`PORTAL_PHASE4_CTA` 文案表 + `newsContextHref`／`columnsContextHref`／`ctaWithSymbol`；`fusionDirection=bidirectional`；`InsightsHome` 反向 CTA、`SymbolDeepDive` 雙向 CTA、`NewsHome`／`ColumnsHome` `?focus=` 過濾與 focus badge；E2E 擴充兩條 44c 斷言。

**Portal ship readiness（2026-05-14）**：repo-side 補完 `api_routers/execution_intents.py`、`api_routers/symbols.py`、`api_routers/run_crew.py`，保留既有 public URL；quote provenance 補 `ttl_seconds=45`，Crew status 補 `age_seconds`／`is_stale`／`stale_after_seconds`。新增 [`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md) 作為 API／PWA／staging signoff 清單。**18–21／35 仍是雲端／staging signoff，不因 repo tests 自動關閉**；完成後須回填日期與 CHANGELOG。

**同步狀態（2026-05-14 — Phase 3 Backlog Go-Live；2026-05-16 SSE 安全收尾）**：M4 / M5 後端 backlog 收口至 production main。**M5** — [`paper-execution-tick.yml`](.github/workflows/paper-execution-tick.yml) 每 15 分鐘排程 + [`requirements-paper-tick.txt`](requirements-paper-tick.txt)；**M4 push digest** — [`push-digest-tick.yml`](.github/workflows/push-digest-tick.yml) 每 30 分鐘，`PRICE_ALERTS_TELEGRAM_ENABLED=1` 啟用 Telegram，自然去重；**M4 SSE 閉環** — `event: price_alert` + PWA [`PriceAlertToaster.jsx`](data-verification-ui/src/components/PriceAlertToaster.jsx)；**Contract smoke** — `paper-tick 404` / `push-check shape` / `SSE 404` / `stream/token 404` 四斷言；**四模組 MVP** — 校正：`analysis`／`positions`／`industries`／`quant` 早於 `eec74e0`／`53fa790` 已落 MVP，無 placeholder。**SSE 安全收尾（2026-05-16）** — `POST /api/stream/token` 短期 token（[`sse_token.py`](sse_token.py)，`SSE_TOKEN_TTL_SECONDS`）、`SSE_MAX_EVENTS_PER_SEC` 每連線事件節流（超量 yield `event: throttled`）、[`tests/api/test_sse_token.py`](tests/api/test_sse_token.py)。明細見 CHANGELOG **2026-05-14** `### Backlog Go-Live` 與 **2026-05-16** `### SSE 安全強化`、Master Plan §0 Phase 3。**仍 backlog**：研究稿（NotebookLM／Agency／TradingView）仍 🟡 不入本階段。

**同步狀態（2026-05-14）**：**28d repo 側 MVP** — [`scenario_optimizer.py`](scenario_optimizer.py)、`GET /api/scenario/suggestions`（`SCENARIO_OPTIMIZER_ENABLED=1`）、`/insights?tab=scenario` + [`ScenarioPlannerHome.jsx`](data-verification-ui/src/modules/insights/pages/ScenarioPlannerHome.jsx)；**34** — Workspace 預覽條 `qs_workspace_size_weights_v1` sm/md 持久化 + 垂直 divider drag + **唯讀** `GET /api/push/price-alerts/digest` 與 digest UI；**29** — Command Bar `Ctrl/Cmd+K` 聚焦、`MACRO`／`MRKT` → `/dashboard`、**RUN Crew 4.5s 節流**；**Ops** — `scripts/verify_reviewer_rollout_env.py`（含 **`--probe-api-base`**）、Runbook 交叉引用；**合約測試** — [`tests/api/test_api_contract_smoke.py`](tests/api/test_api_contract_smoke.py) 擴充 macro／paper／track-record／gate-index／digest；**產業路由** — `GET /api/industries/themes` 遷至 [`api_routers/industries.py`](api_routers/industries.py)；**前端 transport** — [`siliconApiClient.js`](data-verification-ui/src/lib/siliconApiClient.js)；**Dashboard 離線** — `qsi_offline_macro_as_of_hint`；**28a 續** — `PATCH /api/execution-intents` 可選 BQ audit（`PAPER_EXECUTION_AUDIT_TABLE`）+ BQ clustering 建議（`bq_brief_profile_columns.sql`）+ **Industries** `brief_layouts` hint + **`runtime_hints`**（`BRIEF_LAYOUT_FILE`／`BRIEF_DYNAMIC_RENDER`／`REPORT_PROFILE`）+ **BLOOMBERG** §4d。**隊列 36** — Playwright [`queue36-modules.spec.js`](data-verification-ui/e2e/queue36-modules.spec.js) + `npm run test:e2e` 全綠；PWA 路由 **`/analysis`**／**`/industries`**／**`/archive`**。**T5b** — `GET /api/execution-intents/gate-index` + [`tests/api/test_gate_intent_index_api.py`](tests/api/test_gate_intent_index_api.py)。**Phase 0** — `docs/architecture/` 判讀治理落檔（`Terminal_Master_Plan` §0 下小節 + `TODOS`／`AI_CONTEXT`／`CLAUDE` 交叉引用）。**Phase 1（隊列 27）** — [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](docs/STAGING_CURRENT_AFFAIRS_SMOKE.md) 補環境核對表／回填模板；`Terminal_Master_Plan`／`visualization_plan`／隊列 27 敘述對齊。**Phase 2（Portal 產品切片）** — Command Bar **`terminal-crew-status-hud`**（`useRunCrewStatus` → `GET /api/run-crew/status`）+ Workspace **`storage`／`qsi_workspace_changed`**（[`workspaceSync.js`](data-verification-ui/src/constants/workspaceSync.js)）+ Playwright（[`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)、[`workspace-cross-tab.spec.js`](data-verification-ui/e2e/workspace-cross-tab.spec.js)）；[`README.md`](README.md)「Portal 架構 Phase 2」、`Terminal_Master_Plan` §0 Phase 2。CHANGELOG **2026-05-14**。

**同步狀態（2026-05-13 Phase 2）**：**隊列 28a／28b／28c／30／31／32／33 repo 側切片已交付，34 local-first workspace 已深化，35 runbook 已補**（CHANGELOG **2026-05-13** `### Phase 2 TODO`）。新增 `/api/paper/lifecycle`、`/api/paper/pnl`、`/api/paper/transparency-letter`、manual `POST /api/execution-intents`、quality-adjusted scoring（`signal_quality.py`；score/grade/reasons 不看事後 P&L）、`/insights` 紙上生命週期 tab與內部透明月報、`/insights?symbol=...` Analysis Deep Dive、`/columns` sector rotation、paper-derived `GET /api/quant/backtest`（仍 gated by `QUANT_BACKTEST_ENABLED=1`），以及 shared monitor 內的 workspace layout/panel order/digest/import/export。Ops 側新增 [`docs/REVIEWER_PRODUCTION_ROLLOUT.md`](docs/REVIEWER_PRODUCTION_ROLLOUT.md)，18–21 仍需真雲端／secrets staging 才可勾選。測試錨點：[`tests/api/test_signal_quality.py`](tests/api/test_signal_quality.py)、[`tests/api/test_transparency_letter_api.py`](tests/api/test_transparency_letter_api.py)、[`tests/api/test_paper_lifecycle_api.py`](tests/api/test_paper_lifecycle_api.py)、[`tests/api/test_industries_api.py`](tests/api/test_industries_api.py)、[`tests/api/test_quant_backtest_api.py`](tests/api/test_quant_backtest_api.py)、[`insights-paper-lifecycle.spec.js`](data-verification-ui/e2e/insights-paper-lifecycle.spec.js)、[`insights-symbol-deep-dive.spec.js`](data-verification-ui/e2e/insights-symbol-deep-dive.spec.js)、[`quant-backtest.spec.js`](data-verification-ui/e2e/quant-backtest.spec.js)、[`queue43-cross-board.spec.js`](data-verification-ui/e2e/queue43-cross-board.spec.js)。**下一步**：若要真正關閉 18–21／35，需在 staging 執行 Runbook 並回填日期；產品面下一波為 **28d beta／launch**、**Queue 34 排程型 digest／推送**（2026-05-14 已補 28d MVP、workspace drag 預覽條、**唯讀 price digest API**、**Portal 架構 Phase 2**：Crew HUD + Workspace **跨分頁** 同步）。

**同步狀態（2026-05-13）**：**隊列 42–43 已交付**（已交付摘要新增列；CHANGELOG **2026-05-13**）。`/columns` 已接 Deep Brief pillar list API（`GET /api/news/deep?pillar=ai|semiconductor|crypto`）、AI／半導體／Crypto tabs、相關主題卡、side panel 與 ticker chip deep-link；跨板塊完善已補 Command Bar 5 板塊跳轉、`/insights?symbol=...` lookup、shared Watchlist dock、JSONL price alert queue（`/api/push/price-alerts`）與 terminal theme。測試錨點：[`tests/api/test_news_router.py`](tests/api/test_news_router.py)、[`tests/api/test_price_alerts_router.py`](tests/api/test_price_alerts_router.py)、[`industries-route.spec.js`](data-verification-ui/e2e/industries-route.spec.js)、[`queue43-cross-board.spec.js`](data-verification-ui/e2e/queue43-cross-board.spec.js)。

**同步狀態（2026-05-11）**：**營運 18–21（repo 側）** — [`scripts/verify_ops_queue_18_21.py`](scripts/verify_ops_queue_18_21.py) + Runbook [`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md) Step 0；**GCP BQ／Redis／VAPID／實機 test-send** 仍須人類在雲端完成後方勾選 18–21。**隊列 27** — staging 手順 [`docs/STAGING_CURRENT_AFFAIRS_SMOKE.md`](docs/STAGING_CURRENT_AFFAIRS_SMOKE.md)（**Phase 1** 已補環境核對／回填模板）；[`visualization_plan.md`](docs/architecture/visualization_plan.md) 已鏈接。**隊列 29–33（本切片）** — Command Bar Playwright [`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)；M4 表與 NVDA mock [`positions-route.spec.js`](data-verification-ui/e2e/positions-route.spec.js)；API 契約 [`test_api_positions_bundle.py`](test_api_positions_bundle.py)、SSE `watch_symbols` [`test_api_stream_war_room.py`](test_api_stream_war_room.py)。**tech-pulse** — ADR [`docs/ADR_TECH_PULSE_INTEGRATION.md`](docs/ADR_TECH_PULSE_INTEGRATION.md)、[`tools/tech_pulse_tool.py`](tools/tech_pulse_tool.py)、[`test_tech_pulse_tool.py`](test_tech_pulse_tool.py)。**文件** — [`README.md`](README.md) 補 Portal API／Tech pulse／自檢腳本索引；[`CHANGELOG.md`](CHANGELOG.md) **2026-05-11** `### Docs` 對齊本行。

**同步狀態（2026-05-10）**：**README** — 對齊 `api_routers/`、`symbol_snapshot_service.py`、`verify_graph_gate.sh`、`GRAPH_REVIEWER_CHANGE_CHECKLIST.md`、精簡目錄與 **gstack.md** 連結；見 CHANGELOG **2026-05-10** `### Docs`。

**同步狀態（2026-05-08）**：**HTML 匯出 API** — [`GET /api/reports/{report_date}/html`](api.py)、[`templates/html_export/brief_card.html.j2`](templates/html_export/brief_card.html.j2)。**Gate 重試反饋** — [`report_html_gates.py`](report_html_gates.py) **`format_gate_feedback_for_llm`** + [`main.py`](main.py) **`run_pipeline_with_retries`**。**PWA** — TradeCard／StructuredReportView／tokens／index.css／Today 等（見 CHANGELOG **2026-05-08** `### Added`／`### Changed` 末批）。**Terminal／DailyBrief** — [`TerminalSseStatusBar.jsx`](data-verification-ui/src/components/TerminalSseStatusBar.jsx)（**`VITE_SSE_ENABLED=1`**、`md:hidden`，與 **`WarRoomSseProvider`**／[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) 同源）；[`DailyBriefPage.jsx`](data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx) **空工作區** **`terminal-workspace-empty`**；[`SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx) 無 OHLC **`role="status"`**。見 CHANGELOG **2026-05-08** `### Changed` 首條。**Crew 結構化 JSON** — [`crew_output_parse.py`](crew_output_parse.py) **`repair_llm_json_text`** + **`kickoff_to_pydantic`**／**`parse_pydantic_from_llm_json_text`**；**第二層** **`kickoff_with_structured_fallback`**（**`crew.kickoff`** 先拋 **`json_invalid`** 時從例外鏈抽原始 JSON 再修復）；[`crew.py`](crew.py) **Crypto／AI** 已套用；測試 [`test_crew_output_parse.py`](test_crew_output_parse.py)。**QSREC `direction`** — [`schemas.py`](schemas.py) 解析前補齊（別名、價位幾何、**`trade_legs` 同資產**）；測試 [`test_trade_recommendation_schema.py`](test_trade_recommendation_schema.py)。**PWA（交接熱點閉環）** — [`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 紙上價格／狀態與 [`execution_intents.py`](execution_intents.py) 對齊；[`WarRoomSseProvider`](data-verification-ui/src/hooks/useWarRoomSse.js) 單一 SSE + [`SideNav`](data-verification-ui/src/app/layout/SideNav.jsx) 狀態燈；[`SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx) 延遲資料建圖；[`index.css`](data-verification-ui/src/index.css) **`.metrics-grid`**；review 報告 [`docs/UI_REVIEW_REPORT.md`](data-verification-ui/docs/UI_REVIEW_REPORT.md)、提示詞 [`docs/UI_REVIEW_PROMPT.md`](data-verification-ui/docs/UI_REVIEW_PROMPT.md)。**PWA — design review 按表實作** — [`DESIGN.md`](DESIGN.md) IA／狀態矩陣／storyboard／token 語意／a11y；[`ModuleNav.jsx`](data-verification-ui/src/app/layout/ModuleNav.jsx) **`md:hidden`**；[`index.css`](data-verification-ui/src/index.css) **1120px** 主內容、`focus-visible`、44px 觸控、側欄圓角 10px；[`AnalysisHome.jsx`](data-verification-ui/src/modules/investment-analysis/pages/AnalysisHome.jsx)／[`IndustriesHome.jsx`](data-verification-ui/src/modules/industry-trends/pages/IndustriesHome.jsx)／[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 移除巢狀 **`page-content`** 並對齊 loading／error／empty；lint + `npm run test:e2e` 綠。見 CHANGELOG **2026-05-08** `### Changed` **PWA — design review**。

**同步狀態（2026-05-05）**：**視覺化隊列 27** — `BlockSectionShell` **`data-section`**、`crypto_dashboard`／`current_affairs_roundtable` 專用區塊 + E2E mock／[`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js)；**Today** 離線橫幅 **`today-offline-banner`**；**staging PWA↔Telegram** 與 **預快取** 仍待（見 [`visualization_plan.md`](docs/architecture/visualization_plan.md) §3）。**Portal 隊列 26 切片** — [`PositionsHome.jsx`](data-verification-ui/src/modules/position-management/pages/PositionsHome.jsx) + [`positions-route.spec.js`](data-verification-ui/e2e/positions-route.spec.js)。**驗證** — 全庫 **`pytest` 綠**（[`test_validate_report.py`](test_validate_report.py) 動態新聞時間戳 + `STRICT_NEWS_FRESHNESS_GATE`）；**`npm run test:e2e` 綠**（`positions-route` strict `cell` 斷言）；見 CHANGELOG **2026-05-05** `### Tests`。**28a** — 可選 [`PAPER_EXECUTION_AUDIT_TABLE`](ENV_TEMPLATE.txt) + [`paper_execution_audit.sql`](docs/SQL/paper_execution_audit.sql)。**NotebookLM 24 Phase 0–1** — [`test_notebooklm_tool.py`](test_notebooklm_tool.py)。**營運 18–21** — 手順見 [`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)，**GCP 側仍未自動完成**，本日不勾選 18–21。

**同步狀態（2026-05-04）**：**Portal Phase 1** 對 [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 驗收清單已閉環：`siliconApiHeaders.js` + [`useApi.js`](data-verification-ui/src/hooks/useApi.js)／[`pushClient.js`](data-verification-ui/src/pushClient.js) 送 `X-Q-Silicon-Key`；401→[`/api-key`](data-verification-ui/src/pages/ApiKeyPage.jsx)（`VITE_E2E=1` 不跳）；**`/`→`/briefs`**、**Today→`/today`**、BottomNav；[`eslint.config.js`](data-verification-ui/eslint.config.js) 模組邊界；後端可選 **`QSILICON_MASTER_KEY`**（`/api/stream/war-room` 豁免，見 [`test_api_master_key_middleware.py`](test_api_master_key_middleware.py)）。隊列 **26** 設計稿之 `shared/api/client.ts` 仍以驗收清單註記為「設計錨點」；實作路徑見上。

**同步狀態（2026-05-06）**：**文件對齊** — [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 曾列待辦之 API／401／`/`／eslint 項 **已於 2026-05-04 程式交付**（見 CHANGELOG **2026-05-04** `### PWA`／`### API`）；本行保留為歷史錨點。

**同步狀態（2026-05-06）**：**architecture backlog repo-side 補完** — [`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md#0-architecture-文件狀態矩陣) 已改列最新狀態：視覺化補 `data-section`／新 block JSX／DailyBriefReport JSON 持久化／Streamlit snapshot helper；NotebookLM 補 `DeepFilingAnalysis`／`deep_filing_analysis_node`／`deep_filing_block`／cost log DDL（live client 仍未接）；Agency 補 template parser／`AgencyResearchOutput`／`agency_researcher_node`／Crew backstory opt-in／`agency_finance_block`；TradingView 補 repo-side bridge／fixture／Crew + LangGraph tool tail。所有新能力預設關或空資料不渲染。

**同步狀態（2026-05-07）**：**Terminal 12 週 Roadmap 入列** — 隊列 **29–34** 新增 Portal Phase 2（Command Bar + SSE）、M4 Position Management、M5 Industry Trends、M6 Investment Analysis、M7 Quant Trading、Portal Phase 3（多視窗 + Alert + 個人化）；對應 [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 五模組完整 MVP；本次僅文件對齊，不進「已交付摘要」。

**同步狀態（2026-05-06）**：**CI** — [`deploy.yml`](.github/workflows/deploy.yml) 已升級 **docker/setup-buildx-action v4.0.0**、**docker/build-push-action v7.1.0**（SHA pin），對齊 GitHub Actions Node 24；見 CHANGELOG **2026-05-06** `### CI`。

**同步狀態（2026-04-18）**：**Terminal 總表／架構看法** — 新增 [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md)、[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md) **`architecture/`** 列、[§ AI／架構文件看法](#ai-architecture-views)；見 CHANGELOG **2026-04-18** `### Docs`。**延續**：補登 **`exec_summary`／`market_mode` 專用區塊 + mock `daily_brief_report` E2E**（[`ExecSummaryBlock.jsx`](data-verification-ui/src/components/report/blocks/ExecSummaryBlock.jsx)、[`MarketModeBlock.jsx`](data-verification-ui/src/components/report/blocks/MarketModeBlock.jsx)、[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js)）— 見 CHANGELOG **2026-04-18** `### Changed`。**前項**：補登 **視覺化計畫 Phase 6／7（PWA 保守離線 + Streamlit 戰情室 v4）** — [`service-worker.js`](data-verification-ui/src/service-worker.js)、[`docs/PWA_OFFLINE.md`](docs/PWA_OFFLINE.md)；[`dashboard/theme.py`](dashboard/theme.py)、[`dashboard.py`](dashboard.py)；見 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Added` **前二條**。**前項（同日）**：**PWA 視覺化 V2（結構化本文原生渲染）** — [`structuredBlockContent.js`](data-verification-ui/src/components/report/structuredBlockContent.js)、[`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx)；見 CHANGELOG **2026-04-18** `### Changed` **第二條**。**前次同步（2026-04-16）**：**視覺化階段 A（2026-04-14）**：[`visualization_plan.md`](docs/architecture/visualization_plan.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「視覺化與數字段語意」、[`dashboard.py`](dashboard.py) Symbol 快照口徑／`price_alignment` 提示 — 見 CHANGELOG **2026-04-14** `### Docs`。本檔於 **2026-04-27** **日報模組化 Phase 5（5a–5d + 5b + 4d 動態組版）**（[`current_affairs_crew.py`](current_affairs_crew.py)、[`main.py`](main.py) 並行、`BRIEF_DYNAMIC_RENDER`、`validate_report(..., structured_report=)`、[`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)、[`test_dynamic_full_render.py`](test_dynamic_full_render.py)）— 見 CHANGELOG **2026-04-27** `### Changed`；**2026-04-14** **日報模組化 Phase 4d**（[`modularization_plan.md#phase-4d`](docs/architecture/modularization_plan.md#phase-4d)、[`report_html_gates.py`](report_html_gates.py) `_check_profile_block_consistency`、[`main.py`](main.py) `_validate_report_profile_env`）— 見 CHANGELOG **2026-04-14** `### Changed`；**2026-04-16** **日報模組化 Phase 4c**（[`bigquery_writer.py`](bigquery_writer.py) `write_llm_run_log`／`write_gate_failure_log` **`profile`**、[`main.py`](main.py)、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)、[`test_llm_run_log.py`](test_llm_run_log.py)／[`test_gate_failure_log.py`](test_gate_failure_log.py)）— 見 CHANGELOG **2026-04-16** `### Changed`；**2026-04-27** **日報模組化 Phase 4b**（[`brief_profiles_layout.py`](brief_profiles_layout.py)、`BRIEF_LAYOUT_FILE`、`profile_block_ids` merge、[`config/brief_layouts/`](config/brief_layouts/)、[`test_brief_profiles_layout.py`](test_brief_profiles_layout.py)、**PyYAML** 依賴）— 見 CHANGELOG **2026-04-27** `### Changed`；同日 **日報模組化 Phase 4a**（[`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2)、`REPORT_PROFILE=crypto-only`、`report_html_gates` `crypto-only` Gate／一致性、[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)）— 見 CHANGELOG **2026-04-27** `### Changed`；同日 **日報 Gate Phase 3**（[`validate_report(..., profile=)`](report_html_gates.py)、`lite` 放寬、機構 HTML strict **不誤擋 lite**、[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)）— 見 CHANGELOG **2026-04-27** `### Changed`；同日 **Phase 2**（[`brief_profiles.py`](brief_profiles.py)、`REPORT_PROFILE`、`templates/profiles/telegram_{full,lite}.j2`；**`full` 仍 byte-identical**；[`test_brief_profiles.py`](test_brief_profiles.py)）— 見 CHANGELOG **2026-04-27** `### Changed`；**2026-04-26** **Phase 1**（[`templates/blocks/`](templates/blocks/) macro、合併門檻 [`test_telegram_template_modularization.py`](test_telegram_template_modularization.py)）— 見 CHANGELOG **2026-04-26** `### Changed`；**2026-04-26** [`modularization_plan.md`](docs/architecture/modularization_plan.md) **產品與交付原則** — 見 CHANGELOG **2026-04-26** `### Docs`；**2026-04-25** 補 **日報區塊模組化計畫**（[`modularization_plan.md`](docs/architecture/modularization_plan.md) — 五 Phase、短中長期、可切片 PR；**程式未動**）— 見 CHANGELOG **2026-04-25** `### Docs`；**2026-04-24** 補 **日報 Telegram 行動格式**（`tg_emphasize_numbers`／`tg_soft_wrap_mobile`、執行摘要後處理、品質代理格式 hints、[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) §8）— 見 CHANGELOG **2026-04-24**；**2026-04-23 改寫**；**2026-04-16** [`README.md`](README.md) 補 **日報品質代理 `.env` 啟用說明**（`REPORT_QUALITY_AGENT=1`、預設 **gpt-4o-mini**）— 見 CHANGELOG **2026-04-16**；**2026-04-15** **T4a 完整元件**（Redis、`pywebpush`、`POST /api/push/test-send`、可選 BQ persist／audit、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)）與 **實盤觀測 CLI** [`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py) — 見 CHANGELOG **2026-04-15**；**2026-04-14（八）** 下一輪：**NVDA mock 跨路由 E2E**、`price_alignment` **來源欄位**與 **`PRICE_ALIGNMENT_E2E_OVERRIDES`**、**Web Push store 去重／IP rate limit**、**gate_issue_hints 單字邊界**（見 CHANGELOG **2026-04-14**）；**2026-04-14（七）** 依建議順序落地 **Terminal 主線 T1–T3** 首批實作並穿插 **T4b（通知語意草案）**／**T5a／T5b**（見 CHANGELOG **2026-04-14** 與下節 T1–T5 錨點）；**2026-04-14（六）** 精煉 T1–T5 **建議執行順序**（主線／並線／交錯表）；**2026-04-14（五）** 新增 [**Terminal／戰情室後中段路線（T1–T5）**](#terminal-post-mid-tier-t1-t5)（每切片對應檔案）；**2026-04-14（四）** Playwright E2E；**2026-04-14（三）** 可加強項；**2026-04-14（二）** Phase A–E；**2026-04-14** 日報品質代理；**2026-04-12** [**CHANGELOG 2026-04-10** Pipeline](CHANGELOG.md)。先前版本中數百條可勾選項（G-1～G-8 全表、OSS Phase 1–4 細拆、演進 Phase 1–4、商業化階段 E、週報 spike 清單等）**並未在程式庫中全部實作**；為避免「待辦檔＝永遠勾不滿的巨型清單」與正文重複，改為 **導覽 + 下一批隊列 + 外部文件索引**。細項論述與威脅建模仍見 `docs/` 與 `docs/oss_candidates/`。**紅線**見 [`.cursorrules`](.cursorrules) 與 [`CLAUDE.md`](CLAUDE.md)（無數據幻覺、Telegram HTML 白名單、`main.py` 雙線程安全、`validate_report` 契約）。

---

<a id="pull-or-read-codebase-reminder"></a>

## git pull／讀 codebase 時請先看（營運待辦）

> **觸發**：每次 **`git pull`** 自 remote 更新後、或 **第一次讀本 repo／切大任務** 載入 `TODOS.md`／`CLAUDE.md` 時，請掃一眼本節與下方隊列 **18–21**（T4a／price probe **環境與基礎設施** 尚未在雲端自動完成）。

| # | 動作 | 說明 |
|---|------|------|
| 1 | **BigQuery 建表** | 在 GCP 執行 DDL：[`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql)、[`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)；並在執行環境設定 **`WEB_PUSH_SUBSCRIPTIONS_TABLE`**（若與預設 `{PROJECT}.market_data.web_push_subscriptions` 不同）、**`PRICE_PROBE_LOG_TABLE`**（寫入觀測時必填）。見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。 |
| 2 | **Redis** | 部署 Redis，設定 **`WEB_PUSH_REDIS_URL`**（訂閱儲存 + 分散式 rate limit）。 |
| 3 | **VAPID** | 執行 **`python3 scripts/vapid_generate.py`**：**public** → PWA `VITE_WEB_PUSH_VAPID_PUBLIC_KEY`；**private（PEM）** → 僅後端 `WEB_PUSH_VAPID_PRIVATE_KEY`（勿進前端 repo）。 |
| 4 | **staging 驗證 test-send** | `POST /api/push/test-send` 會打真 **Push Service**；設 **`WEB_PUSH_ADMIN_KEY`**，Header **`X-Web-Push-Admin-Key`**，**小流量** 驗證後再開 production。見 [`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)。 |

---

<a id="progress-vs-wall-st-bloomberg"></a>

## 進度分析表（華爾街級日報 · 財報週期 · Bloomberg 對齊）

**目的**：把「離終局還差多少」收斂成**可複查指標**（粗分 1–5，5＝接近本 repo 定義之終局形態，非字面複製 Terminal UI）。**對齊定義**見 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)（工作流、資料可審計、多資產監控；不含 BBG 專有欄位／聊天網）。

### 維度粗評（2026-04-12 盤點；含 M1–M5 回寫）

| 維度 | 粗評 (1–5) | 說明（現況／缺口） |
|------|------------|-------------------|
| 日報敘事與機構區塊 | **3–4** | [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) + 可選 `STRICT_INSTITUTIONAL_PHASE_A/B/C`（[`report_html_gates.py`](report_html_gates.py)、[`schemas.py`](schemas.py)）；預設環境未必全開，敘事仍受 LLM 波動影響。 |
| 「華爾街級」財報文字紀律 | **3–4** | [`crew.py`](crew.py) `_EARNINGS_ANALYSIS_WALL_STREET_RULE` 等；缺口在 sell-side 式「每檔每季完整模型表」尚未成主產物。 |
| 週期性財報（系統化） | **2–3** | [`earnings_watchlist.py`](earnings_watchlist.py)、[`earnings_focus.py`](earnings_focus.py)、`EARNINGS_FOCUS_MODE`；主軸仍是**日報管線內**之財報章節 + 固定 watchlist，非全市場週期研究庫。 |
| 資料可審計（無幻覺） | **4** | 客觀數字走工具／BQ；[`validate_report`](report_html_gates.py) 為可信度邊界（對齊 alignment 紅線）。 |
| Terminal 式產品面（監控／深度頁／workspace） | **3–4** | Phase 0–2 + Terminal 中段 M1–M5（snapshot/provenance、quote、SSE、paper tick）已交付（見「已交付摘要」與 CHANGELOG）；仍與「即時交叉篩選＋專有資料密度」有距離。 |
| 即時與專有市場資料 | **1–2** | 公開／訂閱 API 組合；alignment 驗收亦約束**不**盲目新增未審核即時付費依賴。 |
| 執行與交易基礎設施 | **1–2** | 見 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) 演進藍圖、`execution_intents`／OMS 等多在路線圖。 |

### 硬指標錨點

- **Bloomberg 對齊 Phase 0**：[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4 — **15 條驗收至少通過 12 條**方可宣稱 Phase 0；建議內部逐條勾選作為「Terminal 面差距」的**量化分母**。
- **內部勾選（2026-04-14）**：暫列 **13/15** 通過、**2 項例外**（對齊 CHANGELOG **2026-04-14** Terminal 契約測試 + CI）。  
  - 已通過：1/2/3/4/5/6/7/8/9/10/11/12/13（含 **6** — [`test_terminal_numeric_consistency.py`](test_terminal_numeric_consistency.py)；**14** — CI `ci_terminal_contract_check` + [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4b）。  
  - ~~例外：15~~ **已覆蓋（2026-05-11）** — 治理文件 [`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](docs/REALTIME_DATA_SOURCES_GOVERNANCE.md)（已審核來源清單 + 新增來源 PR 審核表 + 移除流程）；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4 條目 15 + §4b 錨點同步。**6** 已補 API **`price_alignment`** + Playwright **UI 對照**（[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)）。新內部勾選：**15/15**（Phase 0 條目全數有文件或實作錨點；後續仍可比對產品深度與 staging 儀表板）。  
- **建議內部 KPI（可自訂盤點）**：(1) Phase 0 通過條數／15；(2) 生產是否固定開 `STRICT_INSTITUTIONAL_PHASE_A/B/C`；(3) 財報聚焦觸發率／工具命中率（log／BQ）；(4) 儀表板與敘事含 **as_of／來源** 覆蓋率（對齊 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)）；(5) QSREC→監控→告警／紙上交易閉環程度。

**一句話**：**可驗證日報＋ Gate** 軸線偏中上；**類 Terminal 資料壟斷＋即時互動＋執行層** 軸線仍早中段，差距主要在資料深度、產品互動與執行閉環，而非「有無 LLM 寫報告」。

---

## 維護者意見（執行順序，不變）

1. **先穩「選標多樣性 + Gate 可信」** — Direction **1A／2A**；**1B 商業化暫緩** → 階段 E。
2. **Direction 2B** — [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) → `docs/oss_candidates/`；[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)。**勿手改** `OSS_SCOUT_AUTO_BEGIN`～`OSS_SCOUT_AUTO_END` 區塊。
3. **Direction 3** — [`crew_company.py`](crew_company.py)；擴四職能前先量測 **`CREW_FUTURE_TIMEOUT_SEC`**。
4. **P0** — [`PIPELINE_STRICT_ENV`](main.py) + 金鑰盤點；生產／排程強制。

<a id="ai-architecture-views"></a>

## AI／架構文件看法（`docs/architecture/`）

**總表**（中段路線 + 完整狀態矩陣 + **Phase 0 判讀治理**）：[`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md)。

| 檔案 | 狀態 | 看法摘要 |
|------|------|-----------|
| [`architecture/modularization_plan.md`](docs/architecture/modularization_plan.md) | 已落地／維護導覽 | Phase 1–5 已交付；以 CHANGELOG 為權威，保留 byte-identical、profile 與 YAML 維護紀律。 |
| [`architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) | Portal Phase 1 已閉環 | 延續 Vite 務實；`/briefs`、master key、401、eslint 模組邊界已對齊；後續模組仍需切片與 E2E。 |
| [`architecture/REVIEWER_LOOP_DESIGN.md`](docs/architecture/REVIEWER_LOOP_DESIGN.md) | 第一版已落地 | Python 先行 + LLM 查邏輯矛盾是正解；Reviewer **不取代** `validate_report`／Telegram HTML 白名單。 |
| [`architecture/GRAPH_REVIEWER_CHANGE_CHECKLIST.md`](docs/architecture/GRAPH_REVIEWER_CHANGE_CHECKLIST.md) | 維護檢查清單 | `graph/`／Reviewer 變更時必跑 `test_reviewer_loop.py` 與 `scripts/verify_graph_gate.sh`。 |
| [`architecture/visualization_plan.md`](docs/architecture/visualization_plan.md) | 主要 repo backlog 已補，仍有 staging／離線細項 | 2026-05-06 補 optional blocks JSX、`data-section`、DailyBriefReport JSON／可選 BQ、Streamlit helper；**Phase 1（隊列 27）** 執行稿見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](docs/STAGING_CURRENT_AFFAIRS_SMOKE.md)；預快取等仍可後續切片。 |
| [`architecture/AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md) | 協作 context | 行為準則與工程紅線仍有效；「現況」需以 CHANGELOG／程式校正；`qsilicon/` 邊界仍屬長線方向。 |
| [`architecture/notebooklm_research.md`](docs/architecture/notebooklm_research.md) | Repo-side 主流程 scaffold 已接，live client 未接 | 已有 `DeepFilingAnalysis`／`Citation`、`deep_filing_analysis_node`、`deep_filing_block`、多題 helper、`notebooklm_cost_log` DDL；`notebooklm_query()` 仍預設關閉／未接 live client。 |
| [`architecture/agency_agents_research.md`](docs/architecture/agency_agents_research.md) | Repo-side 主流程 scaffold 已接 | 已有 template parser、`AgencyResearchOutput`／`AgencyDeliverable`、`agency_researcher_node`、Crew backstory opt-in、`agency_finance_block`；完整多 Agent 模板庫仍屬長線。 |
| [`architecture/tradingview_mcp_research.md`](docs/architecture/tradingview_mcp_research.md) | Repo-side bridge 已接，外部 MCP 未安裝 | 已有 `tools/tradingview.py`、mock fixture、Crew／LangGraph tool tail、sample setup；不修改 `~/.claude`。 |
| [`architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) | 狀態索引 + Phase 0 | §0 矩陣（✅／🟡）；§0 下 **Phase 0** 定權威順序、研究稿≠產品承諾、`AI_CONTEXT` 與事實分工；實作仍以程式與 CHANGELOG 為準。 |

詳見總表 §0（含 **Phase 0**）／§2。

---

## 已交付摘要（備查，非 exhaustive）

以下為 **已進 main 管線／產品** 之摘要；**逐日條目**以 CHANGELOG 為準。**維護契約**：與 [`CHANGELOG.md`](CHANGELOG.md) **雙向對齊** — 改版寫入 CHANGELOG 時同步更新本檔；本檔補登「已交付」須對應 CHANGELOG 既有或同日條目（見 CHANGELOG 檔首說明）。

| 主題 | 代表檔案／行為 |
|------|----------------|
| **ITER-GO-LIVE-001 — API liveness and ship probe（2026-09-05）** | [`GET /healthz`](api_routers/health.py) 固定 `{"ok": true, "service": "api"}`（無憑證、不探 BQ／LLM／crew）。文件 [`PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)「2026-09-05 正式上線」。[`smoke-prod.sh`](data-verification-ui/scripts/smoke-prod.sh) fail-closed。測試 [`tests/api/test_healthz.py`](tests/api/test_healthz.py)、[`tests/test_smoke_prod_script.py`](tests/test_smoke_prod_script.py)。**不部署 Service**。CHANGELOG **2026-09-05**。 |
| **ITER-TR-LOOP-001 — 今日建議對上紙上狀態（2026-09-05）** | [`PaperReconcileStrip.jsx`](data-verification-ui/src/modules/daily-brief/pages/PaperReconcileStrip.jsx) 首屏對帳條；標的只取日報已解析欄，狀態只讀既有紙上／意圖／已結 API。E2E [`insights-first-screen.spec.js`](data-verification-ui/e2e/insights-first-screen.spec.js)。CHANGELOG **2026-09-05**。 |
| **ITER-TR-AUDIT-001 — 紙上實績可審計摘要（2026-09-05）** | [`track_record.py`](track_record.py) additive `as_of`／期間／`sample_size`／`inclusion_rules`／`prior_alignment`（無證據→`null`，不捏合對齊率）；[`TrackRecordHome.jsx`](data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) 審計列＋納入規則面板＋殘英欄名繁中。E2E 三態 [`insights-track-record.spec.js`](data-verification-ui/e2e/insights-track-record.spec.js)。CHANGELOG **2026-09-05**。 |
| **ITER-P4-44A — /insights 首屏為今日建議（2026-08-30）** | [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 第一屏改為 `DailyBriefHonesty`；工作台說明／CTA／`DataHealthSummary` 摺疊於 `insights-workbench-intro`。E2E [`insights-first-screen.spec.js`](data-verification-ui/e2e/insights-first-screen.spec.js)。CHANGELOG **2026-08-30**。 |
| **Portal Vercel harden（2026-08-15）** | [`vercel.json`](data-verification-ui/vercel.json) `git.deploymentEnabled.main=false`；Production 只走 `pwa-deploy.yml` prebuilt；`VITE_API_URL` 真相來源＝GitHub secret、Preview＝Dashboard Preview env；SSO 建議 Production 關／Preview 留（Dashboard 人工）。文件：[`PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)、README「Vercel 正式站」。CHANGELOG **2026-08-15**。 |
| **Portal 視覺化升級 VU2 — Portfolio donut + Track Record 曲線（2026-06-20）** | [`charts/AllocationDonut.jsx`](data-verification-ui/src/components/charts/AllocationDonut.jsx)（SVG 配置 donut，真資料 holdings weight）掛 [`PortfolioHome`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx)；[`charts/EquityCurveChart.jsx`](data-verification-ui/src/components/charts/EquityCurveChart.jsx)（themed line）取代 [`TrackRecordHome`](data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) Sparkline 累積曲線（真實現 P&L 曲線）。E2E donut/曲線（95/95 綠）。組合層級 P&L 時序無 backend 歷史→不硬做。**待辦 VU3–VU5**：News/Columns 密度、Report/SymbolDeepDive、Streamlit V6。CHANGELOG **2026-06-20**。 |
| **Portal 視覺化升級 Phase 1 + Options by-strike + DB 補齊（2026-06-20）** | 共用圖表 kit [`charts/{themedChart,ChartStates,GammaBarChart}`](data-verification-ui/src/components/charts/)；Options by-strike：`/api/options/gex` additive `per_strike`（[`options_bigquery_reader.read_latest_by_strike`](options_bigquery_reader.py)/[`write_gex_by_strike`](options_bigquery_writer.py)/[`pipeline`](tools/options/pipeline.py) 寫入路徑/[DDL](docs/SQL/options_gex_by_strike.sql)）→ [`OptionsFlowHome`](data-verification-ui/src/modules/insights/pages/OptionsFlowHome.jsx) `GammaBarChart`；Dashboard regime tokens 對齊 + driver bar；[`scripts/verify_bq_tables.py`](scripts/verify_bq_tables.py) 表診斷；backfill 誠實註記。**契約**：by-strike 無資料回 `per_strike:[]` 不示意。**待辦 VU2–VU5**：Portfolio/News/Columns/Report/Streamlit 視覺；options 真資料需 Polygon。CHANGELOG **2026-06-20**。 |
| **日報改 Web Push 投遞（取代 Telegram，2026-06-20）** | [`web_push_store.broadcast()`](web_push_store.py)（`ok=sent>0`、url payload、body cap）+ [`main._deliver_daily_brief_webpush()`](main.py)（旗標 `WEB_PUSH_DAILY_BRIEF`、preflight 共享 Redis/VAPID、`report_ok` 才送、try/except 不阻塞、零幻覺固定文案）+ [`service-worker.js`](data-verification-ui/src/service-worker.js) `push` handler（同源化 data）+ [`deploy.yml`](.github/workflows/deploy.yml) 條件式 secret/env；測試 [`test_web_push_broadcast.py`](test_web_push_broadcast.py)/[`test_main_webpush_delivery.py`](test_main_webpush_delivery.py)。**取代 TG＝`SKIP_TELEGRAM=1`+`WEB_PUSH_DAILY_BRIEF=1`**；其他 TG 用途未動。**上線**：共享 Redis 訂閱 + VAPID secret + Portal 重部署（Vercel）+ 裝置訂閱。`/agent-plan` 雙審（codex CRITICAL×5 全折入）。CHANGELOG **2026-06-20**。 |
| **Options Flow + GEX — 完整異常流表 F3（2026-06-19）** | [`UnusualFlowTable.jsx`](data-verification-ui/src/components/UnusualFlowTable.jsx)（桌機表格 + 手機卡片 + OCC 合約解析 + score 條 + 中文 signal 標籤）取代舊清單；[`OptionsFlowHome.jsx`](data-verification-ui/src/modules/insights/pages/OptionsFlowHome.jsx) `?symbol=` deep-link 即時驅動選取；E2E 補桌機/手機/切標的斷言（92/92 綠）。**Options 前端 F1–F3 完成**；剩上線：Polygon 訂閱 + `POLYGON_API_KEY` → 跑 pipeline → 設 `OPTIONS_*_TABLE` 點亮真資料。CHANGELOG **2026-06-19** `### PWA（Options Flow + GEX — 完整異常流表 F3）`。 |
| **Options Flow + GEX — GEX 歷史圖 F2（2026-06-19）** | [`GexHistoryChart.jsx`](data-verification-ui/src/components/GexHistoryChart.jsx)（lightweight-charts BaselineSeries，0 軸正/負 gamma）lazy 掛入 [`OptionsFlowHome.jsx`](data-verification-ui/src/modules/insights/pages/OptionsFlowHome.jsx) GEX panel；消費 `/api/options/gex/{sym}` 的 `history`；E2E 補圖表斷言（90/90 綠）。**待辦**：F3 完整異常流表／symbol 切換（見 [`docs/OPTIONS_FRONTEND_DESIGN.md`](docs/OPTIONS_FRONTEND_DESIGN.md)）。CHANGELOG **2026-06-19** `### PWA（Options Flow + GEX — GEX 歷史圖 F2）`。 |
| **Options Flow + GEX — Insights 分頁 F1（2026-06-19）** | [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 新分頁「選擇權流」（`insights-tab-options`）→ [`OptionsFlowHome.jsx`](data-verification-ui/src/modules/insights/pages/OptionsFlowHome.jsx)：watchlist GEX 概覽條 + 單標的 GEX 讀數 + 異常流列表；三態（pending／no_data／data）；`?symbol=` 同步。[`useApi.js`](data-verification-ui/src/hooks/useApi.js) `useOptions{Summary,Gex,Flow}`；E2E [`options-flow-route.spec.js`](data-verification-ui/e2e/options-flow-route.spec.js)（89/89 綠）。**待辦**：F2 GEX 歷史圖、F3 完整表／symbol 切換（見 [`docs/OPTIONS_FRONTEND_DESIGN.md`](docs/OPTIONS_FRONTEND_DESIGN.md)）。CHANGELOG **2026-06-19** `### PWA（Options Flow + GEX — Insights 分頁 F1）`。 |
| **Options 讀取 API + 前端設計稿（2026-06-19）** | [`api_routers/options.py`](api_routers/options.py) `GET /api/options/summary`／`/gex/{sym}`／`/flow/{sym}`（唯讀 BQ；三態穩定契約：`polygon_options_pending`／`no_data_yet`／data；[`options_bigquery_reader.py`](options_bigquery_reader.py) graceful）；[`tests/api/test_options_router.py`](tests/api/test_options_router.py)。前端設計稿 [`docs/OPTIONS_FRONTEND_DESIGN.md`](docs/OPTIONS_FRONTEND_DESIGN.md)（IA placement 建議 Insights 分頁；hooks／元件樹／三態／分期 F1–F4）。**待辦**：placement 確認 → 進 `/agent-action` 實作 React（`OptionsFlowHome` + E2E）。CHANGELOG **2026-06-19** `### Feat（Options 讀取 API + 前端設計稿）`。 |
| **Polygon Options Flow + GEX 管線（2026-06-19）** | [`tools/options/`](tools/options/) 子套件（`client`／`analyzer`／`models`／`pipeline`／`agent_tools`／`prompts`）；`run_daily_options_pipeline()` 每日抓 Polygon snapshot+Greeks／trades，算 Unusual Flow（volume/OI、tick sweep/block）+ **標準 dealer GEX**（calls+/puts−、OI、×100、spot² 縮放）；BigQuery [`options_bigquery_writer.py`](options_bigquery_writer.py) + DDL [`docs/SQL/options_*.sql`](docs/SQL/)（partition／cluster／deterministic insert_id）；排程 [`scripts/options_flow_tick.py`](scripts/options_flow_tick.py) + [`.github/workflows/options-flow-tick.yml`](.github/workflows/options-flow-tick.yml)；**紅線**：Agent tools 走共用 `tools_cache_http` 快取、prompt analysis-only、缺料回 `[DATA_MISSING:polygon_options_*]`（capability probe 分級）；需付費 Polygon Options 方案 + `POLYGON_API_KEY`（[`deploy.yml`](.github/workflows/deploy.yml) secret）；測試 `test_options_{gex,analyzer,pipeline_smoke,tool_contract}.py`（GEX golden +300k）；範例 [`examples/run_daily_options.py`](examples/run_daily_options.py)。**未含**：Telegram 戰報四大區塊整合、前端視覺化（另開隊列）。CHANGELOG **2026-06-19** `### Feat`。 |
| **視覺化階段計畫（2026-04-14）** | [`visualization_plan.md`](docs/architecture/visualization_plan.md) 階段 A–D；**階段 A**：[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「視覺化與數字段語意」、[`dashboard.py`](dashboard.py) Symbol 快照口徑／`price_alignment` UI；CHANGELOG **2026-04-14** § 視覺化階段 A |
| **Portal Phase 1 + FastAPI 增量路由 + Runbook／研究 scaffold（2026-05-04／05-06）** | PWA **`/briefs`**（與 **`/terminal`** 同頁）、Shell、API 出口現於 [`useApi.js`](data-verification-ui/src/hooks/useApi.js)；Settings 溯源文案；[`api_routers/`](api_routers/)、[`api_deps.py`](api_deps.py)；[`visualizer.py`](visualizer.py) `VISUALIZER_BTC_SOURCE`；2026-05-06 補 NotebookLM／Agency／TradingView repo-side scaffold（預設關、空資料不渲染）；E2E [`briefs-alias-route.spec.js`](data-verification-ui/e2e/briefs-alias-route.spec.js)；Graph／Reviewer 變更見 [`GRAPH_REVIEWER_CHANGE_CHECKLIST.md`](docs/architecture/GRAPH_REVIEWER_CHANGE_CHECKLIST.md)、[`scripts/verify_graph_gate.sh`](scripts/verify_graph_gate.sh)。 |
| **Portal Phase 2 切片 + M4–M7 讀取 API + Tech pulse + 營運自檢（2026-05-11）** | `GET /api/positions`／`GET /api/industries/themes`／`GET /api/analysis/{symbol}`／`GET /api/quant/signals`（M7 為 **stub**，非完整 backtest）；SSE **`watch_symbols`** + PWA Command Bar（[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx)、[`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js)）；[`main.py`](main.py) 可選 **`TECH_PULSE_IN_BRIEF`** 經 [`tech_pulse_tool.py`](tools/tech_pulse_tool.py) 併入 exclusion；測試 [`test_api_positions_bundle.py`](test_api_positions_bundle.py)、[`test_api_stream_war_room.py`](test_api_stream_war_room.py)、[`test_tech_pulse_tool.py`](test_tech_pulse_tool.py)；E2E [`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)、[`positions-route.spec.js`](data-verification-ui/e2e/positions-route.spec.js)；營運自檢 [`scripts/verify_ops_queue_18_21.py`](scripts/verify_ops_queue_18_21.py)；CHANGELOG **2026-05-11**。 |
| **5 板塊 Terminal Phase 0 — 路由整合 + 框架（2026-05-13）** | [`App.jsx`](data-verification-ui/src/App.jsx) 5 canonical routes（`/news`、`/dashboard`、`/insights`、`/columns`、`/portfolio`）；`/briefs`／`/terminal` 相容 redirect → `/insights`；[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx)、[`ModuleNav.jsx`](data-verification-ui/src/app/layout/ModuleNav.jsx)、[`BottomNav.jsx`](data-verification-ui/src/components/BottomNav.jsx) 改 5 板塊；新薄 wrapper：[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx)、[`DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)、[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx)、[`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx)；舊路由 `/today`／`/archive`／`/charts`／`/trades` 已移除；E2E 遷移 + 新增 [`five-routes-smoke.spec.js`](data-verification-ui/e2e/five-routes-smoke.spec.js)；CHANGELOG **2026-05-13** `### PWA`／`### Tests`。**未含**：38–43 的新後端 API、CSV、Firestore、Track Record。 |
| **Portfolio Tracker Phase 1（Queue 38，2026-05-13）** | [`portfolio_holdings.py`](portfolio_holdings.py) JSONL storage（`PORTFOLIO_HOLDINGS_FILE`，atomic rewrite）、[`api_routers/portfolio.py`](api_routers/portfolio.py) `GET/POST/PATCH/DELETE /api/portfolio` + `POST /import` + `GET /pnl`；[`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) KPI、桌面表格、手機卡片、新增 modal、CSV 匯入／拖放／匯出、刪除與 toast/error；[`Watchlist.jsx`](data-verification-ui/src/components/Watchlist.jsx) localStorage watchlist；測試 [`tests/api/test_portfolio_router.py`](tests/api/test_portfolio_router.py)、[`portfolio-route.spec.js`](data-verification-ui/e2e/portfolio-route.spec.js)。 |
| **Macro Dashboard Phase 2（Queue 39，2026-05-13）** | [`api_routers/macro.py`](api_routers/macro.py) `GET /api/macro/snapshot`（8 指標、7 點 spark、source/as_of、60s cache、逐指標降級、FMP optional catalyst）；[`DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) macro card grid、[`Sparkline.jsx`](data-verification-ui/src/components/Sparkline.jsx)、[`CatalystCalendar.jsx`](data-verification-ui/src/components/CatalystCalendar.jsx)、regime breakdown，並保留 [`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)；測試 [`tests/api/test_macro_router.py`](tests/api/test_macro_router.py)、[`dashboard-route.spec.js`](data-verification-ui/e2e/dashboard-route.spec.js)。 |
| **Tech News Phase 3（Queue 40，2026-05-13）** | [`api_routers/news.py`](api_routers/news.py) `GET /api/news/digest`、`GET /api/news/deep/{item_id}`、`GET /api/news/themes`（Firestore lazy init；`TECH_PULSE_FIRESTORE_COLLECTION`，預設 `tech_pulse_memory_items`；無來源 item 過濾）；[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx) digest list、tag filter chips、每則 source domain、今日主軸、deep brief side panel（手機全屏）；測試 [`tests/api/test_news_router.py`](tests/api/test_news_router.py)、[`news-route.spec.js`](data-verification-ui/e2e/news-route.spec.js)。 |
| **Track Record Phase 4（Queue 41，2026-05-13）** | [`track_record.py`](track_record.py) + [`api_routers/track_record.py`](api_routers/track_record.py) `GET /api/track-record/summary`、`/closed`、`/by-tag`（paper-only W/L、hit rate、avg return、Sharpe 近似、max drawdown、equity curve；每列 `source`／`source_id`）；[`TrackRecordHome.jsx`](data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) KPI、累積曲線、closed table、tag slice；[`scripts/mark_recommendations.py`](scripts/mark_recommendations.py) + [`docs/SQL/recommendation_outcomes.sql`](docs/SQL/recommendation_outcomes.sql) optional BQ sink；測試 [`tests/api/test_track_record_router.py`](tests/api/test_track_record_router.py)、[`insights-track-record.spec.js`](data-verification-ui/e2e/insights-track-record.spec.js)。 |
| **Columns + Cross-board Terminal（Queues 42–43，2026-05-13）** | [`api_routers/news.py`](api_routers/news.py) `GET /api/news/deep?pillar=...` list contract；[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) AI／半導體／Crypto tabs、Deep Brief cards、related themes、side panel、ticker chips → `/insights?symbol=...`；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) 5 板塊跳轉與 symbol deep-link；[`GlobalWatchlistDock.jsx`](data-verification-ui/src/components/GlobalWatchlistDock.jsx) + [`Watchlist.jsx`](data-verification-ui/src/components/Watchlist.jsx) shared monitor；[`price_alerts.py`](price_alerts.py) + [`api_routers/price_alerts.py`](api_routers/price_alerts.py) JSONL price alert queue；[`theme/terminal.css`](data-verification-ui/src/theme/terminal.css) terminal palette。測試 [`tests/api/test_price_alerts_router.py`](tests/api/test_price_alerts_router.py)、[`queue43-cross-board.spec.js`](data-verification-ui/e2e/queue43-cross-board.spec.js)。 |
| **Phase 2 TODO — Paper lifecycle / Quality / Columns / Analysis / Quant / Workspace（Queues 28a–28b, 30–35，2026-05-13）** | [`paper_lifecycle.py`](paper_lifecycle.py) + `GET /api/paper/lifecycle`／`GET /api/paper/pnl`／manual `POST /api/execution-intents`；[`signal_quality.py`](signal_quality.py) quality score/grade/reasons read model（不使用事後 P&L）；[`PaperLifecycleHome.jsx`](data-verification-ui/src/modules/insights/pages/PaperLifecycleHome.jsx) + [`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx)；[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) sector rotation；`GET /api/quant/backtest` 改 paper-derived deterministic curve（`QUANT_BACKTEST_ENABLED=1`）；[`WorkspacePanel.jsx`](data-verification-ui/src/components/WorkspacePanel.jsx) localStorage workspace import/export；Ops docs [`docs/REVIEWER_PRODUCTION_ROLLOUT.md`](docs/REVIEWER_PRODUCTION_ROLLOUT.md) + [`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)。測試 [`tests/api/test_signal_quality.py`](tests/api/test_signal_quality.py)、[`tests/api/test_paper_lifecycle_api.py`](tests/api/test_paper_lifecycle_api.py)、[`tests/api/test_industries_api.py`](tests/api/test_industries_api.py)、[`tests/api/test_quant_backtest_api.py`](tests/api/test_quant_backtest_api.py)、[`insights-paper-lifecycle.spec.js`](data-verification-ui/e2e/insights-paper-lifecycle.spec.js)、[`insights-symbol-deep-dive.spec.js`](data-verification-ui/e2e/insights-symbol-deep-dive.spec.js)、[`quant-backtest.spec.js`](data-verification-ui/e2e/quant-backtest.spec.js)、[`queue43-cross-board.spec.js`](data-verification-ui/e2e/queue43-cross-board.spec.js)。 |
| **Queue 28d + Workspace drag + Command Bar + Queue 36 E2E + T5b gate-index（2026-05-14）** | [`scenario_optimizer.py`](scenario_optimizer.py)、[`api_routers/scenario.py`](api_routers/scenario.py) `GET /api/scenario/suggestions`（`SCENARIO_OPTIMIZER_ENABLED=1`）；[`ScenarioPlannerHome.jsx`](data-verification-ui/src/modules/insights/pages/ScenarioPlannerHome.jsx)、`/insights?tab=scenario`；[`WorkspacePanel.jsx`](data-verification-ui/src/components/WorkspacePanel.jsx) `qs_workspace_size_weights_v1` + 垂直 divider drag；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) `Ctrl/Cmd+K`、`MACRO`／`MRKT`；[`scripts/verify_reviewer_rollout_env.py`](scripts/verify_reviewer_rollout_env.py)；[`App.jsx`](data-verification-ui/src/App.jsx) `/analysis`／`/industries`／`/archive`；[`queue36-modules.spec.js`](data-verification-ui/e2e/queue36-modules.spec.js)、[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 擴充；`GET /api/execution-intents/gate-index`（[`api.py`](api.py)）；[`tests/api/test_scenario_optimizer_api.py`](tests/api/test_scenario_optimizer_api.py)、[`tests/api/test_api_contract_smoke.py`](tests/api/test_api_contract_smoke.py)、[`tests/api/test_gate_intent_index_api.py`](tests/api/test_gate_intent_index_api.py)、[`insights-scenario.spec.js`](data-verification-ui/e2e/insights-scenario.spec.js)。 |
| **Portal Phase 2 產品切片（2026-05-14）** | [`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) **`useRunCrewStatus`** + **`terminal-crew-status-hud`**；[`workspaceSync.js`](data-verification-ui/src/constants/workspaceSync.js)、[`WorkspacePanel.jsx`](data-verification-ui/src/components/WorkspacePanel.jsx) **`storage`／`qsi_workspace_changed`** 跨分頁同步；E2E [`workspace-cross-tab.spec.js`](data-verification-ui/e2e/workspace-cross-tab.spec.js)、[`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)；[`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 現況補錨點。 |
| **Graph Reviewer market gate + War Room pipeline telemetry（2026-05-13）** | [`graph/graph_nodes.py`](graph/graph_nodes.py) pre-reviewer gate 擴為 CRYPTO BTC/ETH allowlist、AI equity universe allowlist、非美 suffix/TW local code 阻擋；[`symbol_snapshot_service.py`](symbol_snapshot_service.py) reviewer ground-truth block（quote/OHLC，bypass cache）；[`war_room_stream.py`](war_room_stream.py) `node_complete` v1 envelope；[`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js)／[`TerminalSseStatusBar.jsx`](data-verification-ui/src/components/TerminalSseStatusBar.jsx) 顯示 Pipeline 終端；測試 [`test_reviewer_loop.py`](test_reviewer_loop.py)、[`test_war_room_stream.py`](test_war_room_stream.py)。 |
| **PWA 視覺化 V1**（Design Foundation） | [`visualization_plan.md`](docs/architecture/visualization_plan.md) Phase **V1** — [`DESIGN.md`](DESIGN.md)、[`data-verification-ui/src/design/tokens.js`](data-verification-ui/src/design/tokens.js)（含 typography／spacing／radius）、[`tailwind.config.js`](data-verification-ui/tailwind.config.js)、[`components/common/`](data-verification-ui/src/components/common/)（`AsOfChip`、`ProvenancePopover`、…）、dev **`/design`**；[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)／[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) 已接入；CHANGELOG **2026-04-18**；契約 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「PWA 設計 tokens」。 |
| **PWA 視覺化 V2／V3 前置**（結構化 Report + profile／錨點／layout 清單 + **逐區塊原生映射** + optional research blocks） | 同上 API／PWA 主線；另 [`ExecSummaryBlock.jsx`](data-verification-ui/src/components/report/blocks/ExecSummaryBlock.jsx)、[`MarketModeBlock.jsx`](data-verification-ui/src/components/report/blocks/MarketModeBlock.jsx)、[`DeepFilingBlock.jsx`](data-verification-ui/src/components/report/blocks/DeepFilingBlock.jsx)、[`AgencyResearchBlock.jsx`](data-verification-ui/src/components/report/blocks/AgencyResearchBlock.jsx)、[`BlockSection.jsx`](data-verification-ui/src/components/report/BlockSection.jsx)；`BlockSectionShell` 全區塊 `data-section`；DailyBriefReport JSON 寫 `.qsilicon/daily_brief_reports`／可選 BQ；E2E [`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js)。 |
| **Streamlit 戰情室 v4 + PWA Phase 6 離線**（視覺化計畫 Phase 7／6） | [`dashboard/theme.py`](dashboard/theme.py)、[`dashboard.py`](dashboard.py)（**`st.tabs`**、**`DASHBOARD_AUTO_REFRESH_SEC`**、`render_profile_tab`／`render_gate_tab`／`render_roundtable_tab`）；[`data-verification-ui/src/service-worker.js`](data-verification-ui/src/service-worker.js)（Workbox **`/api` NetworkOnly** 等）、[`docs/PWA_OFFLINE.md`](docs/PWA_OFFLINE.md)；CHANGELOG **2026-04-18** `### Added` **前二條**；[`README.md`](README.md) 戰情室／War Room 節。 |
| **日報區塊模組化** | **文件**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 1–5、**[產品與交付原則](docs/architecture/modularization_plan.md#產品與交付原則)**。**Phase 1（2026-04-26）**：[`templates/blocks/`](templates/blocks/) + **`_footer_tail`**；smoke [`test_telegram_template_modularization.py`](test_telegram_template_modularization.py)。**Phase 2（2026-04-27）**：[`brief_profiles.py`](brief_profiles.py)、[`templates/profiles/`](templates/profiles/)、`REPORT_PROFILE`；[`report_render.py`](report_render.py)；[`test_brief_profiles.py`](test_brief_profiles.py)。**Phase 3（2026-04-27）**：[`report_html_gates.validate_report`](report_html_gates.py) `profile=`、`lite` 放寬、`_check_profile_block_consistency`；[`main.py`](main.py)；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)。**Phase 4a（2026-04-27）**：`crypto-only` 模板 + Gate／一致性（同上測試擴充）。**Phase 4b（2026-04-27）**：[`config/brief_layouts/`](config/brief_layouts/)、`BRIEF_LAYOUT_FILE`、[`brief_profiles_layout.py`](brief_profiles_layout.py)。**Phase 4c（2026-04-16）**：BQ `llm_run_log`／`gate_failure_log` **`profile`**（[`bigquery_writer.py`](bigquery_writer.py)、[`main.py`](main.py)、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)）。**Phase 4d（2026-04-14）**：[`modularization_plan.md#phase-4d`](docs/architecture/modularization_plan.md#phase-4d) — 一致性錨點、[`main._validate_report_profile_env`](main.py)、YAML／BQ 文件；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_critical_paths.py`](test_critical_paths.py)。**Phase 5（2026-04-27）**：[`schemas.py`](schemas.py)、[`current_affairs_crew.py`](current_affairs_crew.py)、[`main.py`](main.py)、[`report_render.py`](report_render.py)（`BRIEF_DYNAMIC_RENDER`）、[`report_html_gates.py`](report_html_gates.py)（`STRICT_*`／Lite Pass6）、[`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)；[`test_current_affairs_schema.py`](test_current_affairs_schema.py)、[`test_current_affairs_render.py`](test_current_affairs_render.py)、[`test_dynamic_full_render.py`](test_dynamic_full_render.py) |
| 雙軌 Crew + 可選 LangGraph | [`main.py`](main.py)、[`graph/`](graph/)、`USE_LANGGRAPH_ENGINE`、`GRAPH_*` |
| LangGraph 工具橋接與深度查證 | [`graph/graph_tools.py`](graph/graph_tools.py)、`RESEARCH_TOOLS`、`deep_research_node` |
| **LangGraph Reviewer Loop（Phase 3.5）** | [`graph/graph_nodes.py`](graph/graph_nodes.py) `python_validate_node`／`llm_reviewer_node`／`review_retry_node`／`degrade_node`；[`graph/graph_crew.py`](graph/graph_crew.py) wiring；[`bigquery_writer.py`](bigquery_writer.py) `write_reviewer_log` + [`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)；`GRAPH_LLM_TRADE_REVIEWER`、`REVIEWER_LOG_BQ`；[`test_reviewer_loop.py`](test_reviewer_loop.py)。Reviewer 僅查 trade 邏輯，**不取代** `validate_report`／Telegram HTML 白名單。 |
| 日報 HTML／Gate／schema | [`report_html_gates.py`](report_html_gates.py)、[`schemas.py`](schemas.py)、[`report_render.py`](report_render.py)（**2026-04-24** 行動閱讀濾鏡與執行摘要後處理）、[`templates/telegram_report.j2`](templates/telegram_report.j2) |
| 日報投資者可讀性清理（2026-04-29） | [`report_render.py`](report_render.py)、[`main.py`](main.py)、[`schemas.py`](schemas.py)、[`templates/blocks/_ai_section.j2`](templates/blocks/_ai_section.j2)、[`crew.py`](crew.py)：Polymarket production 預設關閉；AI 儀表板改「可交易市場／基本面／財報錨點／需求代理」；新增【財報雷達｜未來 7 天】事件預告（無 EPS／營收 forecast）；區塊②b 去除重複摘要。見 CHANGELOG **2026-04-29**。 |
| 日報品質代理（複合分／TODOS 後續） | [`report_quality_agent.py`](report_quality_agent.py)（**2026-04-24** 格式品質 hints）、[`main.py`](main.py)（成功交付後掛勾）、`REPORT_QUALITY_AGENT*`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；scratchpad `quality_agent_result`；[`README.md`](README.md) **快速開始**旁「日報品質代理」啟用步驟（**2026-04-16**） |
| Phase A–E 觀測與 Terminal 契約 | [`main.py`](main.py) scratchpad `init.meta.pipeline_config`；[`graph/graph_nodes.py`](graph/graph_nodes.py) `graph_deep_research_metrics`（含 `finish_kind` 等）；[`scripts/ci_terminal_contract_check.sh`](scripts/ci_terminal_contract_check.sh)、[`.github/workflows/ci.yml`](.github/workflows/ci.yml)（含 **npm cache**、**Node 24**／`setup-node@v5` — CHANGELOG **2026-04-18**）；[`test_terminal_numeric_consistency.py`](test_terminal_numeric_consistency.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py)、[`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)、[`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)；PWA [`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js)；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`README.md`](README.md) badges |
| Snapshot 價格對齊／Web Push 分階 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment`；[`api.py`](api.py) `SymbolSnapshot`；[`web_push_store.py`](web_push_store.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`data-verification-ui/src/pushClient.js`](data-verification-ui/src/pushClient.js) |
| **實盤 BQ vs yfinance 觀測**（2026-04-15） | [`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py)、[`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)、`PRICE_PROBE_*`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)） |
| **Web Push T4a（Redis／VAPID／pywebpush／BQ）**（2026-04-15） | [`web_push_store.py`](web_push_store.py)、[`api.py`](api.py) `POST /api/push/test-send`、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)、[`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql)、[`test_web_push_redis.py`](test_web_push_redis.py) |
| Playwright E2E（Bloomberg §6 UI） | [`data-verification-ui/e2e/`](data-verification-ui/e2e/)（`cross-page-btc-price`、`today-btc-mismatch-banner`、`terminal-spy-mismatch`）、[`data-verification-ui/playwright.config.js`](data-verification-ui/playwright.config.js)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；[`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)；mock **`e2e_btc_misaligned`**（CHANGELOG **2026-04-16**） |
| Terminal 後中段 **T1–T3**／**T5** 首次切片（2026-04-14） | [`execution_intents.py`](execution_intents.py)（`status`／`category`／`sort_by`）；[`api.py`](api.py)（`API_HTTP_REQUEST_LOG`、`gate_issue_hints` 富化、`GET /api/execution-intents` query）；[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)（輪詢 coalesce、5xx backoff）；PWA [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)、[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4c、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)（T4b 草案）；[`test_execution_intents_api.py`](test_execution_intents_api.py) |
| Terminal 下一輪（2026-04-14）— E2E／T5b／T4a 小步 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment` 來源欄位 + `PRICE_ALIGNMENT_E2E_OVERRIDES`；[`web_push_store.py`](web_push_store.py) endpoint 去重、**`WEB_PUSH_SUBSCRIBE_RATE_PER_MIN`**、**`WEB_PUSH_STORE_MAX_SUBSCRIPTIONS`**；[`api.py`](api.py) `push_subscribe` 傳 **client_ip**；[`data-verification-ui/e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)；[`test_api_push.py`](test_api_push.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py) |
| 日報組裝衛生（三情境、儀表板分區） | [`report_render.py`](report_render.py)：BTC 現價 **>50k** 且情境列含 **突破** 時 **`7.6k`→`76k`**；**`instrument_sections`** 前剔除與 IB 區塊標題同名之**空白佔位列**、**連續重複** `is_section_header`；**評分卡 ↔ 儀表板** BTC RSI `status_emoji` 同步、MA20/MA50 鄰近 **$** 敘事對齊儀表板（CHANGELOG **2026-04-12**）；[`test_report_render.py`](test_report_render.py)（含 **2026-04-10** 情境／分區測試） |
| Crew 新聞／工具敘述邊界 | [`crew.py`](crew.py)：加密 **1–3** `investment_takeaway` 禁止無據 **垃圾債／HY／spread** 跳喻；**FinancialDatasets** 營收相關 MetricLine **`label` 須含期間口徑**（annual／quarterly／FY／年份等）；[`tools_legacy.py`](tools_legacy.py) `_fd_summarize_ticker` 尾註提醒 **fiscal／口徑**（CHANGELOG **2026-04-10**） |
| 模板 `$` 與交易卡顯示 | `strip_usd` 濾鏡、`ExecutableTradeLeg` 欄位正規化（CHANGELOG **2026-04-22**） |
| **日報 Opus 回饋落地（SPX 錨／Polymarket 過濾／Telegram 版面／HF·DXY 敘事）**（2026-04-15） | [`tools_legacy.py`](tools_legacy.py) `fetch_gspc_last_close_anchor`、`fetch_spy_etf_last_close_anchor`、`macro_context_tool`（**v4** ^GSPC+SPY ETF 行）、`fetch_polymarket_hot_highlight_lines`（`PREDICTION_MARKETS_KEYWORDS`／`DENYLIST`／**`TAG_IDS`／`EXCLUDE_TAG_IDS`**、Gamma `volume_24hr`）；[`report_render.py`](report_render.py)、[`report_html_gates.py`](report_html_gates.py) `STRICT_SPX_LEVEL_SANITY_GATE`；[`templates/telegram_report.j2`](templates/telegram_report.j2) 免責位移、**🤖 區塊①**；[`crew.py`](crew.py) `_BRIEF_V2_RULE`／HF watchlist 鏈路／單標禁 DXY 唯一主因；[`graph/graph_nodes.py`](graph/graph_nodes.py) LangGraph **上下文刪減**（trade_picker／final_formatter）；[`test_report_render.py`](test_report_render.py)、[`test_prediction_markets_tool.py`](test_prediction_markets_tool.py)、[`test_spy_etf_anchor.py`](test_spy_etf_anchor.py)；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-15**、**2026-04-23** |
| 預測市場熱門 | [`tools_legacy.py`](tools_legacy.py) `prediction_markets_tool`、組裝注入、Crew／Graph 掛載 |
| 財報焦點／watchlist | [`earnings_watchlist.py`](earnings_watchlist.py)、[`earnings_focus.py`](earnings_focus.py) |
| 資產宇宙 | [`assets_config.json`](assets_config.json)、[`assets_universe.py`](assets_universe.py) |
| PWA War Room（首期） | [`data-verification-ui/src/hooks/useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js) |
| Bloomberg 對齊（Phase 0–2） | Phase 0–1：[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)、[`api.py`](api.py) `GET /api/symbols/{symbol}/snapshot`、`symbol_snapshot_service`、`test_api_symbols_snapshot`、PWA Terminal／K 線。**Phase 2**：Terminal v2 分組／模板、[`SymbolFocusContext`](data-verification-ui/src/context/SymbolFocusContext.jsx)／[`SymbolFocusBar`](data-verification-ui/src/components/SymbolFocusBar.jsx)、Streamlit 快照區（`SYMBOL_SNAPSHOT_HTTP_BASE`／`DASHBOARD_SYMBOL_FOCUS`）；[`README.md`](README.md) **`/terminal`／`VITE_API_URL`**；[`App.jsx`](data-verification-ui/src/App.jsx) **`lazy` 載入 Terminal** |
| Terminal 中段 M1（資料溯源 + 執行意圖 API） | [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)；snapshot **`data_provenance`**（[`symbol_snapshot_service.py`](symbol_snapshot_service.py)）；`GET`／`PATCH` [`api.py`](api.py) **`/api/execution-intents`**；[`execution_intents.py`](execution_intents.py) 去重列表、`update_execution_intent_status`；[`test_execution_intents_api.py`](test_execution_intents_api.py)（CHANGELOG **2026-04-12**） |
| Terminal 中段 M2（PWA 輪詢 + 溯源 UI + 意圖 PATCH） | [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js) `livePoll`／`getTerminalRefetchIntervalMs`；[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)；`VITE_TERMINAL_POLL_MS`（README／`DASHBOARD_CONTRACT`）；CHANGELOG **2026-04-12** `### PWA` |
| Terminal 中段 M3（quote API + 卡片 last） | [`api.py`](api.py) `GET /api/symbols/{symbol}/quote`；[`symbol_snapshot_service.fetch_symbol_quote`](symbol_snapshot_service.py)；[`test_api_symbol_quote.py`](test_api_symbol_quote.py)；PWA [`useSymbolQuote`](data-verification-ui/src/hooks/useApi.js)、[`TerminalSymbolCard`](data-verification-ui/src/components/TerminalSymbolCard.jsx)；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)；CHANGELOG **2026-04-12** `### API（Terminal M3）` |
| Terminal 中段 M4（SSE war-room） | [`api.py`](api.py) `GET /api/stream/war-room`；[`war_room_stream.py`](war_room_stream.py)；PWA `VITE_SSE_ENABLED`／[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)；`ENV_TEMPLATE` `TERMINAL_SSE_*`／`API_STREAM_AUTH_KEY`；[`test_api_stream_war_room.py`](test_api_stream_war_room.py) |
| Terminal 中段 M5（紙上 tick） | [`paper_execution.py`](paper_execution.py)、[`scripts/paper_execution_tick.py`](scripts/paper_execution_tick.py)、`POST /api/paper/execution-tick`；意圖 **`reference_*`**／**`PAPER_*`** 狀態；[`test_paper_execution.py`](test_paper_execution.py)；`ENV_TEMPLATE` `PAPER_TICK_*` |
| 開源社群骨架 | [`LICENSE`](LICENSE)、[`CONTRIBUTING.md`](CONTRIBUTING.md)、[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| 訂閱取代堆疊 — **研究稿**（非已實作） | [`docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md`](docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md) |

---

<a id="continuation-plan-queues-42-43"></a>

## 續作安排（隊列 42–43，已交付備查）

> **2026-05-13**：下列 42a–42c 與 43a–43c 已一次落地；保留本段作為後續 review 的拆分脈絡。

**Queue 42 target：科技專欄 Deep Brief 串接（先做 repo-side M slice）**

1. **42a — Deep Brief API contract**：在 [`api_routers/news.py`](api_routers/news.py) 補 `GET /api/news/deep?pillar=ai|semiconductor|crypto&limit=...`，沿用 Queue 40 Firestore lazy-init 與來源過濾規則；回傳 `items` 時包含 `id`、`pillar`、`title`、`summary`、`body` 或 `content`、`source`、`source_url`、`published_at`、`tickers`、`reading_minutes`。驗收：新增／擴充 [`tests/api/test_news_router.py`](tests/api/test_news_router.py)，覆蓋 pillar filter、source-missing skip、空資料降級。
2. **42b — Columns UI**：把 [`modules/columns/pages/ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 從現有 industry shell 升級為 AI／半導體／Crypto 三支柱 toggle；deep brief 卡片流顯示閱讀時長、來源、ticker chips（跳 `/insights?symbol=X`），並保留 `GET /api/industries/themes` 的相關主題卡。驗收：desktop table/card 與 mobile side panel 都可開關，無新全域狀態。
3. **42c — Tests/docs handoff**：新增或更新 Playwright `/columns` smoke（toggle 切換、至少一張 deep brief 卡、side panel 開關、ticker chip href）；同步 README／DASHBOARD_CONTRACT／CHANGELOG／TODOS。建議驗證：`pytest tests/api/test_news_router.py`、`pytest -m smoke`、`cd data-verification-ui && npm run build && npm run test:e2e`。

**Queue 43 target：跨板塊完善（Queue 42 綠後接）**

1. **43a — Command Bar board jumps**：擴充現有 Command Bar 5 板塊跳轉、symbol lookup → `/insights?symbol=...`、recent chips 持久化；驗收以 `command-bar-route.spec.js` 擴充為主。
2. **43b — Watchlist + Push Alert**：把 [`Watchlist.jsx`](data-verification-ui/src/components/Watchlist.jsx) 從 Portfolio 局部元件整理成可被其他板塊掛載的共享 surface；price trigger 只接既有 Web Push subscribe/test-send 基礎，不新增 broker 或付費即時資料依賴。
3. **43c — Mobile density + terminal theme**：逐板塊 iPhone 14 viewport 檢查 44px touch target、文字不溢出、Portfolio card list 回歸；新增 `data-verification-ui/src/theme/terminal.css` 時只套 Shell/theme token，不重寫既有 Tailwind 元件。

**紅線**：隊列 42/43 不碰 `main.py` 日報 pipeline、`graph/`、Telegram output、不新增未審核資料源、不承諾投資收益、不自動下單。

<a id="terminal-master-plan-phase4-queue-44"></a>

## Terminal Master Plan §0 Phase 4 — 實作（隊列 44）

> **文件錨點**：[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) **§0 Phase 4**（讀者層×工作台層：原則與 A／B／C 表）及同節 **「Phase 4 — 實作規劃」**（滾動切片 **44a–44d**）。PWA 工程邊界與驗收分工見 [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) **§ Phase 4 IA**；讀者層細節（視線、`?focus=`、90s 腳本、CTA／Command Bar、Skip link P2）見 [`DESIGN.md`](DESIGN.md) **「Portal Phase 4」**。

**Gate 0（維護者 REVIEW；齊備後視為可開 44a）** ✅ **已簽核（2026-05-16）**

權威值寫在 [`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js) 之 `PORTAL_PHASE4_GATE0`；本表為**人類可讀對照**，若日後改決策請**同步**改該檔與本表。

| # | 決議項 | 簽核值 | 對應程式錨點 |
|---|--------|--------|-------------|
| 1 | 工作台「主戰場」兩條路由 | **`/insights` + `/portfolio`**（宏觀狀態台 `/dashboard` 並列但**不**佔主戰場名額） | `workbenchPrimaryRoutes` / `workbenchMacroRoute` |
| 2 | 讀者層首屏是否「零表格」 | **是**（避高密度報價／矩陣表；既有 digest 卡片流不算 dense table，視為合規） | `readerFirstScreenAvoidDenseTables: true` |
| 3 | 融合第一刀方向 | **雙向**（reader ↔ workbench；44c 落地） | `fusionDirection: "bidirectional"` |
| 4 | 「終端感」保留元素上限（三至五項） | **5 項**：Command Bar、mono symbol chips、macro spark grid、SSE WATCH、Workspace dock | `terminalToneKeep` |
| 5 | 工作台關鍵路徑最大點擊數 **N** | **N=3**（「警報 → 標的／狀態 →（可選）回新聞／專欄脈絡」） | `maxWorkbenchPathClicks: 3` |

**44b 進階收斂**（**2026-05-16 交付**）：
- `/dashboard` 拆 2 tab — 宏觀總覽（`?tab=overview` 預設）／市場深度（`?tab=depth`）；高密度區塊由 5 縮至 ≤ 3。
- `/portfolio` 移除內嵌 `<Watchlist />`；改由 `GlobalWatchlistDock`（已掛 Shell 全站）承接。
- E2E [`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js) 補 2 條 44b 斷言 + 既有 dashboard-compute-memory／dashboard-onchain 改走 `?tab=depth`；10/10 綠。

**44b 第二波 — 高密度區塊清單（對齊 Gate 0 N=3；2026-05-14）**（維護者可據此擴 E2E／人測勾選）：
- **`/dashboard`**：`?tab=overview` 僅宏觀 KPI／行事曆／regime；**`ComputeMemoryPanel`**、**`OnchainMetricsPanel`** 僅在 **`?tab=depth`**（與第一波一致）。
- **`/portfolio`**：`?tab=overview` 僅 KPI 帶、操作列、持倉表／卡；**`PortfolioRiskPanel`**（TP/SL 高密度）僅在 **`?tab=risk`**（`portfolio-tab-overview`／`portfolio-tab-risk`；深連結供 E2E 與手測）。
- **`/insights`**：維持既有 **tab 分拆**（Paper lifecycle／Scenario 等）— 首屏不與主圖表區再疊第二個「全寬密表」級區塊；細項見 [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)。

**44b 第二波（2026-05-14 repo 交付）**：[`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) — `useSearchParams` 驅動 **`?tab=overview`（預設）／`?tab=risk`**，`PortfolioRiskPanel` 僅 `tab=risk` 掛載；[`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js) 補 portfolio risk tab 斷言；[`portfolio-tpsl.spec.js`](data-verification-ui/e2e/portfolio-tpsl.spec.js) 改走 **`/portfolio?tab=risk`**。

**P2 Skip link（2026-05-14 repo 交付）**：[`Shell.jsx`](data-verification-ui/src/app/layout/Shell.jsx) 略過連結 + [`App.jsx`](data-verification-ui/src/App.jsx) **`#main-content`**／`tabIndex={-1}`；[`index.css`](data-verification-ui/src/index.css) `.skip-to-main`；E2E [`skip-link.spec.js`](data-verification-ui/e2e/skip-link.spec.js)。

**44a — 讀者層（對齊 Master Plan A）**：[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx)、[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) — 首屏單一主任務、來源／時間軸可掃讀、避免首屏多區高密度表；可選 reader 副標 + `data-testid`。驗收：擴充／新增 Playwright + Master Plan A 人測；`npm run build`。**原則上不開新 API**。**2026-08-30（工作台對齊）**：[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 預設首屏改為今日建議本體，說明／CTA／健康晶片摺疊，見 CHANGELOG **2026-08-30**。

**44b — 工作台層（對齊 B）**：[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)、[`DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) — 一屏一主問題；超過 **N** 個高密度區塊時收斂至 tab／[`GlobalWatchlistDock`](data-verification-ui/src/components/GlobalWatchlistDock.jsx)／[`WorkspacePanel`](data-verification-ui/src/components/WorkspacePanel.jsx)。驗收：人測路徑 ≤ **N**；與 Phase 3 `PriceAlertToaster`／SSE 不衝突。

**44c — 融合層（對齊 C）** ✅ **已交付（2026-05-16 續）**：[`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js) 新增 `PORTAL_PHASE4_CTA` 文案表 + `newsContextHref` / `columnsContextHref` / `ctaWithSymbol` helpers；`fusionDirection` 切 `bidirectional`；[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 工作台導引條補 **`portal-cta-insights-to-news` / `portal-cta-insights-to-columns`** 反向 CTA；[`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx) 增 **`symbol-cta-to-news` / `symbol-cta-to-columns`**（帶 `?focus={SYM}`）；[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx)、[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 讀 `?focus=` 過濾並顯示 **`news-focus-badge` / `columns-focus-badge`**（含清除）。E2E：[`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js) 擴充 44c 雙向 CTA + symbol focus 流程。`npm run build` 綠。

**44d — Command Bar 情境化（可選；對齊 Phase 4 原則 5）**：[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) — 依 `pathname` 切 placeholder／title；不改 401／RUN 節流。驗收：擴充 `command-bar-route.spec.js`。**建議獨立 PR、排在 44c 後**。

**紅線（隊列 44）**：不碰 `main.py` 日報 pipeline、`graph/`、Telegram HTML 出口；不新增未審核或不可溯源資料源；不自動下單。

---

## 下一批隊列（建議接續實作，邊界清楚）

**Codex／Agent 自包含 handoff（2026-05-20）**：[`docs/CODEX_NEXT_BATCH.md`](docs/CODEX_NEXT_BATCH.md) — NEXT-1..NEXT-5 已入列 **隊列 57–61**；**跨軸總順序**見 [Session 2026-05-20 總執行順序](#session-2026-05-20-execution-order)（**57／NEXT-5 ≈ 52 F0** → **58 NEXT-1** → **59 NEXT-3** → **53 FA**（可與 **60 NEXT-2** 同迭代）→ **61 NEXT-4** → **62 44b 實作** → **54–56** → **63–71**）。

**NEXT-5 / 52-F0-1 已交付（2026-05-20）**：新增 [`tests/api/test_api_py_contract.py`](tests/api/test_api_py_contract.py)，補 `api.py` inline routes 契約安全網（reports list／legacy report／gate-status／html 404／qsrec-stats／trades／positions/open／trades performance／push subscribe 422 等），未改 API 語意。CHANGELOG **2026-05-20** `### Tests（隊列 9 續 · api.py contract / NEXT-5）`。

**NEXT-1 已交付（2026-05-20）**：新增 [`data-verification-ui/e2e/touch-target.spec.js`](data-verification-ui/e2e/touch-target.spec.js)，在 375px mobile / 1280px desktop 量測 Command Bar 主要控制與 shared monitor toggle ≥44px；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) 與 [`GlobalWatchlistDock.jsx`](data-verification-ui/src/components/GlobalWatchlistDock.jsx) 補 44px 觸控高度。`index.css` dead-CSS audit 僅做 scoped 搜尋確認，本切片未刪大批全域 CSS。CHANGELOG **2026-05-20** `### PWA（NEXT-1 · touch target sweep）`。

**NEXT-3 / 隊列 59 已交付（2026-05-20）**：[`Settings.jsx`](data-verification-ui/src/pages/Settings.jsx) Gate 失敗 row 可點開 `settings-gate-failure-drawer`，顯示完整 `issues_preview`、timestamp、attempt、profile、blocking／warning／issue 計數與 `used_fallback`；沿用既有 `GET /api/gate-failures?days=7`，未改 Gate pipeline／BQ schema。擴充 [`settings-page.spec.js`](data-verification-ui/e2e/settings-page.spec.js)。CHANGELOG **2026-05-20** `### PWA（NEXT-3 · Gate failure detail drawer）`。

**NEXT-2 / 隊列 60 已交付（2026-05-20）**：`GET /api/quant/signals` 由 paper `execution_intents.jsonl` active rows 衍生；[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 新增 Intraday Monitor，使用既有 `useSymbolQuote({ livePoll: true })`、filter、offline banner、row → `/insights?symbol=...`；新增 [`quant-intraday-monitor.spec.js`](data-verification-ui/e2e/quant-intraday-monitor.spec.js)。未新增付費行情源、未自動交易。CHANGELOG **2026-05-20** `### PWA/API（NEXT-2 · Quant Intraday Monitor）`。

**免費資料擴充（2026-05-20 規劃 · 隊列 52–56）**：付費源（Glassnode／CryptoQuant／TrendForce）**暫緩**；四軸 **A 鏈上／B 算力／C 宏觀／D 財報** 分 Phase **F0→FA→FB→FC→FD** 入列，見 [§ 免費資料擴充](#free-data-expansion-queue-52)。**建議實作順序**：**52（F0）→ 53（FA）→ 54（FB）→ 55（FC）→ 56（FD）**；**F0 與隊列 57（NEXT-5）同一 PR 或緊鄰**；FA 末尾可與 **隊列 60（NEXT-2）** 交錯；**每切片一 PR**。

依維護者順序與工程可切性排列；**完成後**把對應句寫進 CHANGELOG，並在本節刪行或改「✓」。

**提醒**：**`git pull` 後或讀 codebase 前**請看 [§ git pull／讀 codebase 時請先看](#pull-or-read-codebase-reminder) 與隊列 **18–21**（雲端尚未自動完成的 T4a／觀測表與金鑰）。

1. ~~**P0 Critical env 定稿**~~ — **已交付（2026-04-14）**：[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) 修訂；[`main.py`](main.py) `_validate_env_types` 納入 `ADAPTIVE_*` 數值校驗；scratchpad `pipeline_config`。
2. ~~**橫切閾值實驗**~~ — **已交付（2026-04-14）**：[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) 補 scratchpad 實驗紀錄欄位。
3. ~~**P3 Gate 失敗 → 人審提示**~~ — **已交付（2026-04-14）**：[`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md) 補 CI 錨點（digest 腳本／BQ 流程既有）。
4. ~~**自適應門檻 BQ 接線**~~ — **已確認落地**：[`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) + [`report_html_gates.py`](report_html_gates.py)；**2026-04-14** 補啟動數值校驗與 scratchpad 可觀測性。
5. ~~**LG-3 補齊**~~ — **已交付（2026-04-14）**：[`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)（`smoke`，mock `bind_tools`）。
6. ~~**LG-1 觀測**~~ — **已交付（2026-04-14）**：`graph_deep_research_metrics` scratchpad 事件；`pipeline_config` 旗標快照。
7. ~~**G-7 小項**~~ — **已交付（2026-04-14）**：[`README.md`](README.md) badges + LICENSE 對齊句；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)；[`CLAUDE.md`](CLAUDE.md) 索引。
8. ~~**G-8 漸進**~~ — **已交付（2026-04-14）**：[`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)（`boundary` + `hypothesis`）。
9. ~~**PWA War Room 二期**~~ — **已交付（最小切片，2026-04-14）**：[`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js) 錯誤態重試／成功態重新整理；視覺拋光仍可在後續波次加強。
10. ~~**PWA Web Push（分階 1）**~~ — **已交付（2026-04-14）**：[`web_push_store.py`](web_push_store.py)、`WEB_PUSH_ENABLED`／`WEB_PUSH_STORE`、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、PWA [`pushClient.js`](data-verification-ui/src/pushClient.js)（`VITE_WEB_PUSH_*`）。**未完成（分階 2）**見隊列 **11**。
11. ~~**PWA Web Push（分階 2 — 生產級）**~~ — **已交付（2026-04-15）**：Redis（`WEB_PUSH_REDIS_URL`）、**分散式** rate limit（Redis INCR）、可選 **BQ** persist／audit（`WEB_PUSH_BQ_*`）、**`pywebpush`** + `POST /api/push/test-send`（`WEB_PUSH_ADMIN_KEY`）、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)；見 [`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)。**仍待營運**：建表／配 Redis／合規審閱訊息模板與排程 digest（T4b）。
12. ~~**Terminal E2E（Playwright）**~~ — **已交付（2026-04-14）**：[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)、[`e2e/terminal-spy-mismatch.spec.js`](data-verification-ui/e2e/terminal-spy-mismatch.spec.js)、[`e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)（mock **BQ vs OHLC/quote 分歧** UI 迴歸）、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；`SymbolCandleChart` 修正 **lightweight-charts v5** `addSeries(CandlestickSeries)`（避免 Terminal 卡白屏）。
13. ~~**Bloomberg 對齊 Phase 2**~~ — **已交付（2026-04-10 CHANGELOG）**：Terminal v2 分組／模板、跨頁 Symbol Context（`SymbolFocusBar` + `TerminalSymbolCard` 設為全域關注）、Streamlit 與 `symbol_snapshot_service`／可選 HTTP 對齊 snapshot 形狀。
14. ~~**Terminal 中段 M2**~~ — **已交付**：見「已交付摘要」列與 CHANGELOG **2026-04-12** `### PWA`；規格見 [`docs/TERMINAL_MID_TIER_ROADMAP.md` — M2](docs/TERMINAL_MID_TIER_ROADMAP.md#m2-terminal-pwa)。
15. ~~**Terminal 中段 M3**~~ — **已交付**：見「已交付摘要」與 CHANGELOG **2026-04-12** `### API（Terminal M3）`；規格 [M3](docs/TERMINAL_MID_TIER_ROADMAP.md#m3-symbol-quote)。
16. ~~**Terminal 中段 M4**~~ — **已交付**：見「已交付摘要」與 [`docs/TERMINAL_MID_TIER_ROADMAP.md` M4](docs/TERMINAL_MID_TIER_ROADMAP.md#m4-realtime-stream)。
17. ~~**Terminal 中段 M5**~~ — **已交付**：見「已交付摘要」與 [M5](docs/TERMINAL_MID_TIER_ROADMAP.md#m5-paper-execution)。
18. **營運：BigQuery DDL（Web Push + price probe）** — 在專案 BQ 執行 [`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql) 與 [`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)；設定 **`WEB_PUSH_SUBSCRIPTIONS_TABLE`**／**`WEB_PUSH_AUDIT_TABLE`**（可選）／**`PRICE_PROBE_LOG_TABLE`**（寫入觀測時）。完成後可勾掉並註記日期。**Runbook（2026-05-05）**：[`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)「## 18」。
19. **營運：Redis + `WEB_PUSH_REDIS_URL`** — 接上後端可連之 Redis；與 **18** 一併驗證 `POST /api/push/subscribe` 回 `backend: redis`。**Runbook**：[`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)「## 19」。
20. **營運：VAPID 金鑰** — `python3 scripts/vapid_generate.py`；public → PWA env、private → 後端 only；勿提交私鑰。**Runbook**：[`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)「## 20」。
21. **營運：staging 小流量 `test-send`** — `WEB_PUSH_ADMIN_KEY` + `POST /api/push/test-send`；確認瀏覽器能收再放量。**Runbook**：[`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md)「## 21」。
22. **日報區塊模組化（實作）** — ~~**Phase 1**~~ **已交付（2026-04-26）**；~~**Phase 2**~~ **已交付（2026-04-27）**；~~**Phase 3**（`validate_report(..., profile=)`、`lite`／機構 Gate、`main.py` 傳 profile、一致性檢查）~~ **已交付（2026-04-27）**；~~**Phase 4a**（`crypto-only` 模板 + Gate）~~ **已交付（2026-04-27）**；~~**Phase 4b**（`BRIEF_LAYOUT_FILE` YAML、`profile_block_ids` merge）~~ **已交付（2026-04-27）**；~~**Phase 4c**（BQ `profile`）~~ **已交付（2026-04-16）**；~~**Phase 4d**（Phase 1–4 補強：一致性錨點、啟動 `REPORT_PROFILE` 檢、YAML／BQ 文件）~~ **已交付（2026-04-14）** — 見 CHANGELOG **2026-04-14** `### Changed` 與 [`modularization_plan.md` Phase 4d](docs/architecture/modularization_plan.md#phase-4d)。~~**Phase 4d 動態組版**~~ **已交付（2026-04-27）** — `BRIEF_DYNAMIC_RENDER` + YAML 範例 [`config/brief_layouts/example_full_reorder_header_exec.yaml`](config/brief_layouts/example_full_reorder_header_exec.yaml)。~~**Phase 5（5a–5d + 5b）**~~ **已交付（2026-04-27）** — 見 CHANGELOG **2026-04-27** `### Changed` 與 [`modularization_plan.md` Phase 5](docs/architecture/modularization_plan.md#phase-5時事多觀點區塊podcast-型態文字)。**運營／staging**：`BRIEF_CURRENT_AFFAIRS=1`、可選 `BRIEF_CURRENT_AFFAIRS_JSON`、動態組版前 smoke。原則見 **[產品與交付原則](docs/architecture/modularization_plan.md#產品與交付原則)**（過渡期 **production 固定 `full`／等價**、`lite`／`crypto-only` 先 staging）。
23. ~~**Reviewer Loop（LangGraph Phase 3.5）**~~ — **已交付（2026-04-21）**：[`graph/graph_crew.py`](graph/graph_crew.py) `trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`；[`graph/graph_nodes.py`](graph/graph_nodes.py) deterministic reviewer + Slim LLM verdict + hard cap=2 + degrade warning；[`bigquery_writer.py`](bigquery_writer.py) `write_reviewer_log`、[`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) `GRAPH_LLM_TRADE_REVIEWER`／`REVIEWER_LOG_BQ`；[`test_reviewer_loop.py`](test_reviewer_loop.py)。**紅線**：reviewer 僅查 trade 邏輯、**不取代** `validate_report`／Telegram HTML 白名單。後續若要讓 reviewer gate 對主線排程生效，仍需另行評估 `USE_LANGGRAPH_ENGINE=1` 預設翻轉。
24. ~~**NotebookLM repo-side 主流程 scaffold**~~ — **已交付（2026-05-06）**：[`tools/notebooklm_tool.py`](tools/notebooklm_tool.py) 保留 `notebooklm_query()` 並新增多題 helper／citation parsing；[`schemas.py`](schemas.py) 補 `Citation`／`DeepFilingAnalysis`；[`graph/graph_nodes.py`](graph/graph_nodes.py) 補 `deep_filing_analysis_node`（`NOTEBOOKLM_ENABLED=0` 或缺 notebook id 時 no-op／`DATA_MISSING`）；[`brief_profiles.py`](brief_profiles.py) + [`templates/blocks/_deep_filing_block.j2`](templates/blocks/_deep_filing_block.j2)；[`bigquery_writer.py`](bigquery_writer.py) + [`docs/SQL/notebooklm_cost_log.sql`](docs/SQL/notebooklm_cost_log.sql)。**仍非 live client**：NotebookLM 官方／社群 client 尚未接，production 預設不渲染。
25. ~~**Agency Agents repo-side 主流程 scaffold**~~ — **已交付（2026-05-06）**：[`agents/agency/__init__.py`](agents/agency/__init__.py) template parser／fallback；[`schemas.py`](schemas.py) 補 `AgencyResearchOutput`／`AgencyDeliverable`；[`graph/graph_nodes.py`](graph/graph_nodes.py) 補 `agency_researcher_node`；[`crew.py`](crew.py) 在 `AGENCY_RESEARCH_ENABLED=1` 時 opt-in 注入 template 摘要；[`brief_profiles.py`](brief_profiles.py) + [`templates/blocks/_agency_finance_block.j2`](templates/blocks/_agency_finance_block.j2)。**仍待長線**：完整多 Agent 模板庫、Financial Analyst template 與 production KPI 復盤。
26. **Terminal Frontend Portal 五模組化** — [`docs/architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md)：`data-verification-ui/src/` 重構為 `app/layout/`（`Shell.tsx`＋`ModuleNav.tsx`）+ `modules/{daily-brief,investment-analysis,position-management,industry-trends,quant-trading}/` + `shared/{api,components,hooks,types}/`；`react-router-dom` 路由（`/` → `/briefs`；`/analysis`／`/positions`／`/industries`／`/quant`）；`shared/api/client.ts` axios 實例讀 `VITE_API_URL`、加 `X-Q-Silicon-Key`（localStorage `qsi_master_key`），401 跳轉 key-input 頁；**master key** 以 `QSILICON_MASTER_KEY` 單一環境變數為主（先不導入 JWT／多用戶，對齊隊列 **11**）；**後端** FastAPI `APIRouter` 逐 router 切片 PR（`/api/briefs`／`/api/analysis`／`/api/positions`／`/api/industries`／`/api/quant`／`/api/shared`），同步 [`DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；**模組邊界**：`modules/{a}/` 禁直接 import `modules/{b}/`（lint rule 或目錄約束）；**開發順序**：Shell + daily-brief（遷移既有 `/terminal`）→ position-management（複用 `paper_execution.py`／`execution_intents.py`）→ industry-trends → investment-analysis → quant-trading；每模組至少一條 Playwright smoke（mock API 可）；PWA 離線快取維持 API NetworkOnly。**依賴**：隊列 **9**（api.py 合約測試先行，避免 `APIRouter` 拆分靜默回歸）；隊列 **26** Shell＋daily-brief 完成後才啟動 Phase 3–5 模組。P2 / L。
27. **視覺化剩餘 backlog（V4／V5 細項）** — **2026-05-06 已補 V2/V6 repo-side 缺口**：`DeepFilingBlock`／`AgencyResearchBlock`、全區塊 `data-section`、DailyBriefReport JSON 本機持久化與可選 BQ、Streamlit snapshot provenance／price alignment helper。**Phase 1（repo，隊列 27）**：[`STAGING_CURRENT_AFFAIRS_SMOKE.md`](docs/STAGING_CURRENT_AFFAIRS_SMOKE.md) 已補 **環境核對表、步驟、完成標準、TODOS／CHANGELOG 回填剪貼範本**；[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) **Phase 1**、[`visualization_plan.md`](docs/architecture/visualization_plan.md) §3 對齊。**仍待（人類 staging）**：`BRIEF_CURRENT_AFFAIRS=1` 下依該檔跑通 PWA ↔ Telegram roundtable 端到端 smoke 並回填本條或同步狀態；可選預快取 `/today`／最新報告與離線 `as_of` 提示細節。P3 / S。
28. **12 週投資價值優化 Roadmap（repo-native）** — 從「通用研報 tool」推進到「個人化投資決策夥伴」，但只沿用既有主線，不另起平行系統；公開績效僅能引用可回放、可審計的 **paper-tracked** 訊號，且不接券商、不自動下單、不承諾收益。~~**28a Signal lifecycle + paper P&L**~~ **2026-05-13 repo 側已交付**：[`paper_lifecycle.py`](paper_lifecycle.py)、`GET /api/paper/lifecycle`、`GET /api/paper/pnl`、manual `POST /api/execution-intents`、[`PaperLifecycleHome.jsx`](data-verification-ui/src/modules/insights/pages/PaperLifecycleHome.jsx)；仍以 JSONL 為 source of truth；可選 **`PAPER_EXECUTION_AUDIT_TABLE`** 寫入紙上轉移／PATCH 稽核列（見 [`docs/SQL/paper_execution_audit.sql`](docs/SQL/paper_execution_audit.sql)）。~~**28b Quality-adjusted scoring + Blotter UI**~~ **2026-05-13 repo 側已交付**：[`signal_quality.py`](signal_quality.py) 以 review-time context 產生 quality score/grade/reasons，`GET /api/execution-intents` 與 paper lifecycle/P&L rows 皆帶 quality 欄位；[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx) 支援 quality badge/filter，[`PaperLifecycleHome.jsx`](data-verification-ui/src/modules/insights/pages/PaperLifecycleHome.jsx) 顯示 Quality KPI 與 Quality vs P&L。~~**28c Monthly transparency letter + portfolio upload/alignment**~~ **2026-05-13 repo 側已交付**：[`transparency_letter.py`](transparency_letter.py)、`GET /api/paper/transparency-letter` 以已平倉 paper 訊號生成 internal-only 月度透明信函、sample threshold、quality summary 與 portfolio symbol alignment（portfolio upload 仍沿用 Queue 38 CSV/import）。~~**28d Scenario engine + target optimizer（MVP）**~~ **2026-05-14 repo 側已交付**：[`scenario_optimizer.py`](scenario_optimizer.py)、`GET /api/scenario/suggestions`（`SCENARIO_OPTIMIZER_ENABLED=1`）、[`ScenarioPlannerHome.jsx`](data-verification-ui/src/modules/insights/pages/ScenarioPlannerHome.jsx) + `/insights?tab=scenario`；測試 [`tests/api/test_scenario_optimizer_api.py`](tests/api/test_scenario_optimizer_api.py)、E2E [`insights-scenario.spec.js`](data-verification-ui/e2e/insights-scenario.spec.js)。**仍待**：beta/launch 流程、更完整互動 optimizer；**原則**：僅預填建議、須人工確認、不下單。P1 / L。
29. **Portal Phase 2 — Command Bar + SSE 即時 Quote（週 1–2）** — **2026-05-11 切片已交付**：全局 Command Bar（`AAPL`／`AAPL <GO>`）、`GET /api/stream/war-room?watch_symbols=…` 之 **`symbol_quote`** 推送、PWA `localStorage.terminal_sse_watch`、E2E [`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)、[`test_api_stream_war_room.py`](test_api_stream_war_room.py) `_parse_sse_watch_symbols_param`。**2026-05-11（二）續切**：全域 [`GlobalGateBadge.jsx`](data-verification-ui/src/components/GlobalGateBadge.jsx) 於 Command Bar `trailing` 顯示最新日報 reviewer-loop verdict；Command Bar Recent chips（`terminal_recent_symbols` localStorage，cap 8）。**2026-05-14 已補**：`Ctrl/Cmd+K` 全域聚焦輸入（輸入框／contenteditable 內不攔截）、`MACRO`／`MRKT` board alias → `/dashboard`。**2026-05-14（續）**：既有 `POST /api/run-crew` + PWA **RUN** 4.5s 節流與 429 友善訊息。**2026-05-14（Phase 2）**：**`terminal-crew-status-hud`** 輪詢 **`GET /api/run-crew/status`**（RUN 提交中／`running` 時顯示 job／`started_at`）。**2026-05-16（權限契約落檔）**：[`docs/ADR_COMMAND_BAR_PERMISSIONS.md`](docs/ADR_COMMAND_BAR_PERMISSIONS.md) 將指令分類成 **N/R/W/S** 四類並寫明資料源紅線；後續任何新指令需在 PR description 對應 `_require_master_key` 路徑與治理連結。**仍待**：更完整「Bloomberg 感」互動切片需先過 ADR；**紅線**：不新增未審核即時付費資料依賴（治理文件見 [`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`](docs/REALTIME_DATA_SOURCES_GOVERNANCE.md)）。P1 / M。
30. ~~**M4（Portal）Position Management 完整管理（週 3–4）**~~ — **2026-05-13 repo 側已交付 Queue 28a/30 切片**：manual `POST /api/execution-intents`、既有 `PATCH`、Risk Metrics、Paper P&L 回放與 `/insights` 紙上生命週期 tab；legacy `GET /api/positions` 保留。**仍待**：若要恢復舊 M4 `/positions` 產品面，需另排非 canonical route 或整併到 `/insights`；真 OMS/下單仍 out of scope。P1 / M。
31. ~~**M5（Portal）Industry Trends 產業趨勢頁（週 5–6）**~~ — **2026-05-13 repo 側已交付**：`GET /api/industries/themes` additive `rotation`／`regime_score`／`risk_level`／`source`；[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 顯示 sector rotation 與深化 theme cards；Playwright [`industries-route.spec.js`](data-verification-ui/e2e/industries-route.spec.js) 覆蓋。**2026-05-14**：路由實作遷至 [`api_routers/industries.py`](api_routers/industries.py)（靜態卡資料 [`industry_themes_static.py`](api_routers/industry_themes_static.py)）。**2026-05-14（再補）**：[`IndustriesHome.jsx`](data-verification-ui/src/modules/industry-trends/pages/IndustriesHome.jsx) 顯示 `GET /api/brief-layouts` 庫存提示（對照 `BRIEF_LAYOUT_FILE`／`BRIEF_DYNAMIC_RENDER` 文件，不在此頁推斷 runtime）。**2026-05-14（儀表互連）**：`GET /api/brief-layouts` 增 **`runtime_hints`**（唯讀 `BRIEF_LAYOUT_FILE`／`BRIEF_DYNAMIC_RENDER`／`REPORT_PROFILE`）+ 產業頁顯示後端啟用態。**仍待**：更深層管線狀態與其他板塊聯動（若要做）。P2 / M。
32. ~~**M6（Portal）Investment Analysis 個股深度頁（週 7–8）**~~ — **2026-05-13 repo 側已交付**：[`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx) 在 `/insights?symbol=...` 顯示 quote/snapshot deep dive，Filing／NotebookLM／Agency 區塊僅在 payload 有資料時渲染；E2E [`insights-symbol-deep-dive.spec.js`](data-verification-ui/e2e/insights-symbol-deep-dive.spec.js)。**仍待**：live NotebookLM client 與 Agency 多模板 production KPI。P1 / L。
33. ~~**M7（Portal）Quant Trading 訊號列表 + 回測 UI（週 9–10）**~~ — **2026-05-13 repo 側已交付**：`GET /api/quant/backtest` 在 `QUANT_BACKTEST_ENABLED=1` 時改 paper-derived deterministic curve；[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) Backtest panel 顯示 return/drawdown/Sharpe/trade_count；測試 [`tests/api/test_quant_backtest_api.py`](tests/api/test_quant_backtest_api.py)、[`quant-backtest.spec.js`](data-verification-ui/e2e/quant-backtest.spec.js)。**2026-05-20 NEXT-2 續補**：`GET /api/quant/signals` 改 paper `execution_intents.jsonl` active rows 衍生，Quant tab 新增 Intraday Monitor（既有 quote polling、filter、row deep link），測試 [`test_api_quant_signals.py`](test_api_quant_signals.py)、[`quant-intraday-monitor.spec.js`](data-verification-ui/e2e/quant-intraday-monitor.spec.js)。**仍待**：更完整 Signal Table。P2 / L。
34. **Portal Phase 3 — 多視窗 + Alert + 個人化（週 11–12）** — **2026-05-13 local-first workspace 已深化**：[`WorkspacePanel.jsx`](data-verification-ui/src/components/WorkspacePanel.jsx) 掛入 shared monitor，支援 `qs_workspace_layout`、`qs_workspace_panels`、watchlist/recent symbols 匯出與 JSON 匯入，並顯示 portfolio/paper/columns/alerts digest 與 panel order controls；price alert panel 既有。**2026-05-14 已補**：預覽條垂直 divider drag、`qs_workspace_size_weights_v1` 依 sm/md breakpoint 持久化並納入 workspace JSON 匯出鍵；**唯讀** `GET /api/push/price-alerts/digest` + Workspace 顯示 pending／symbols／`as_of`。**2026-05-14（Phase 2）**：Workspace **`storage` 事件 + `qsi_workspace_changed` 同頁廣播** 跨分頁同步 layout／panels／size weights；Playwright [`workspace-cross-tab.spec.js`](data-verification-ui/e2e/workspace-cross-tab.spec.js)。**2026-05-16（T4b × 34 語意對齊）**：[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md) §「通知事件語意」收斂為 `price_alert` 主通道 + 共用 `triggered_at` 去重，digest／意圖／War Room 不外推；對接 [`push-digest-tick.yml`](.github/workflows/push-digest-tick.yml) 與 `GET /api/push/price-alerts/digest`。**仍待**：若新增推送類別，依該檔流程走 staging `test-send` + 治理審核。P2 / L。
35. **`GRAPH_LLM_REVIEWER=1` 正式推出計畫** — [`config.py`](config.py) 已於 **2026-05-09** 將 `USE_LANGGRAPH_ENGINE` 預設翻轉至 `"1"`；**2026-05-13 repo 側 runbook 已補**：[`docs/REVIEWER_PRODUCTION_ROLLOUT.md`](docs/REVIEWER_PRODUCTION_ROLLOUT.md)。**2026-05-14**：[`scripts/verify_reviewer_rollout_env.py`](scripts/verify_reviewer_rollout_env.py) 新增可選 **`--probe-api-base`**（對 staging origin 發 `GET /api/reports/qsrec-stats` 做 JSON shape 檢查）。仍需 staging 連跑 3 日、檢查 `reviewer_log` BQ、`GET /api/reports/qsrec-stats?days=7`、`pytest test_reviewer_loop.py -m smoke` 與 production cutover 記錄後才可勾選。**紅線**：reviewer 只查 trade 邏輯、不取代 `validate_report`、Telegram HTML 白名單依舊。P1 / S。
36. ~~**E2E 測試 — 五模組首批 smoke（2026-05-09 交付批次）**~~ — **2026-05-14 repo 側已補齊**：[`App.jsx`](data-verification-ui/src/App.jsx) 掛載 **`/analysis`**、**`/industries`**、**`/archive`**（Archive 仍非底部 5 板 nav 一員，但可供 E2E／深連結）；Playwright [`queue36-modules.spec.js`](data-verification-ui/e2e/queue36-modules.spec.js) 覆蓋 ① `AnalysisHome` + mock `GET /api/reports/qsrec-stats`、② `QuantHome`（`/insights?tab=signals`）+ mock `gate-status` 三日、③ `IndustriesHome` + structured `industry_trends`、④ Archive Profile Picker + `?profile=lite`／`localStorage`；[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 補 `qsrec-stats`／`gate-status`／`reports` 列表三日／structured `blocks+metadata`／`GET /api/analysis/:sym`（NVDA quote/snapshot 維持既有 deep-dive 契約）；[`global-gate-badge.spec.js`](data-verification-ui/e2e/global-gate-badge.spec.js)「無報告」案例改以 **route fulfill 空列表** 避免與 queue36 mock 衝突。**T5b**：`GET /api/execution-intents/gate-index`（唯讀 gate×intent 索引）+ [`tests/api/test_gate_intent_index_api.py`](tests/api/test_gate_intent_index_api.py)。**⑤** `npm run build` + `npm run test:e2e` 全綠。P2 / M。
37. ~~**5 板塊 Terminal — Phase 0：路由整合 + 5 板塊框架（刪廢棄路由）**~~ — **2026-05-13 repo 側已交付**：[`App.jsx`](data-verification-ui/src/App.jsx) 已改為 5 canonical routes（`/news`、`/dashboard`、`/insights`、`/columns`、`/portfolio`）；`/briefs`／`/terminal` 保留相容 redirect → `/insights`；[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx)、[`ModuleNav.jsx`](data-verification-ui/src/app/layout/ModuleNav.jsx)、[`BottomNav.jsx`](data-verification-ui/src/components/BottomNav.jsx) 已改 5 板塊；新增薄 wrapper 模組（`news` 空狀態、`dashboard` 承接 Today、`insights` tabs 承接 DailyBrief/Analysis/Quant、`columns` 承接 Industries、`portfolio` 承接 Positions）。E2E 已遷移並新增 [`five-routes-smoke.spec.js`](data-verification-ui/e2e/five-routes-smoke.spec.js)；本切片**未**實作 38–43 的新後端/API/CSV/Firestore/Track Record。P1 / M。
38. ~~**5 板塊 Terminal — Phase 1：Portfolio Tracker（手動 + CSV）**~~ — **2026-05-13 repo 側已交付**：[`portfolio_holdings.py`](portfolio_holdings.py) JSONL storage（atomic rewrite；`PORTFOLIO_HOLDINGS_FILE` override）、[`api_routers/portfolio.py`](api_routers/portfolio.py) CRUD + CSV import + `/pnl`；[`modules/portfolio/pages/PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) KPI、持倉表、手機卡片、新增 modal、CSV 匯入／拖放／匯出、刪除、toast/error；[`components/Watchlist.jsx`](data-verification-ui/src/components/Watchlist.jsx) localStorage watchlist。測試錨點：[`tests/api/test_portfolio_router.py`](tests/api/test_portfolio_router.py)、[`portfolio-route.spec.js`](data-verification-ui/e2e/portfolio-route.spec.js)。P1 / M。
39. ~~**5 板塊 Terminal — Phase 2：數據儀表板**~~ — **2026-05-13 repo 側已交付**：[`api_routers/macro.py`](api_routers/macro.py) `GET /api/macro/snapshot` 回傳 8 指標（`yields_10y`、`spread_2s10s`、`dxy`、`vix`、`btc`、`soxx_spy_ratio`、`ai_momentum`、`next_fed_cpi`）、7 點 spark、source/as_of、60 秒 cache、逐指標降級；[`modules/dashboard/pages/DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) macro cards + [`Sparkline.jsx`](data-verification-ui/src/components/Sparkline.jsx) + [`CatalystCalendar.jsx`](data-verification-ui/src/components/CatalystCalendar.jsx) + regime breakdown，並保留 BTC price-alignment strip。測試錨點：[`tests/api/test_macro_router.py`](tests/api/test_macro_router.py)、[`dashboard-route.spec.js`](data-verification-ui/e2e/dashboard-route.spec.js)。P1 / M。
40. ~~**5 板塊 Terminal — Phase 3：科技即時報（tech-pulse Firestore 接線）**~~ — **2026-05-13 repo 側已交付**：[`api_routers/news.py`](api_routers/news.py) 已掛載 `GET /api/news/digest?date=…&limit=…`、`GET /api/news/deep/{item_id}`、`GET /api/news/themes`，lazy-init Firestore client，支援 `TECH_PULSE_FIRESTORE_COLLECTION`（預設 `tech_pulse_memory_items`）與 optional `TECH_PULSE_FIRESTORE_PROJECT`；無 headline/source 的 doc 不回傳。[`modules/news/pages/NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx) 已接 digest list、AI／半導體／加密／宏觀 filter、每則來源顯示、今日主軸與 deep brief side panel。測試錨點：[`tests/api/test_news_router.py`](tests/api/test_news_router.py)、[`news-route.spec.js`](data-verification-ui/e2e/news-route.spec.js)。P1 / L。
41. ~~**5 板塊 Terminal — Phase 4：投資觀點 + Track Record**~~ — **2026-05-13 repo 側已交付**：[`track_record.py`](track_record.py) 與 [`api_routers/track_record.py`](api_routers/track_record.py) 已掛載 `GET /api/track-record/summary`、`GET /api/track-record/closed`、`GET /api/track-record/by-tag?tag=AI`，以 `execution_intents.jsonl` 最新 `PAPER_CLOSED` rows 計算 W/L、hit rate、avg return、Sharpe 近似、max drawdown 與 equity curve，並在 closed rows 回傳 `source`／`source_id`。[`modules/insights/pages/TrackRecordHome.jsx`](data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) 已接 KPI、累積曲線、closed table、AI/CRYPTO/WIN/LOSS tag slice；[`scripts/mark_recommendations.py`](scripts/mark_recommendations.py) + [`docs/SQL/recommendation_outcomes.sql`](docs/SQL/recommendation_outcomes.sql) 提供 optional `RECOMMENDATION_OUTCOMES_TABLE` BQ sink。紅線保留：paper-only、不下單、不承諾收益。測試錨點：[`tests/api/test_track_record_router.py`](tests/api/test_track_record_router.py)、[`insights-track-record.spec.js`](data-verification-ui/e2e/insights-track-record.spec.js)。P1 / L。
42. ~~**5 板塊 Terminal — Phase 5：科技專欄（Deep Brief 串接）**~~ — **2026-05-13 repo 側已交付**：[`api_routers/news.py`](api_routers/news.py) 新增 `GET /api/news/deep?pillar=ai|semiconductor|crypto&limit=...`；[`modules/columns/pages/ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 已接 AI／半導體／Crypto toggle、Deep Brief card stream、related themes、side panel、閱讀時間／來源／ticker chip → `/insights?symbol=X`。測試錨點：[`tests/api/test_news_router.py`](tests/api/test_news_router.py)、[`industries-route.spec.js`](data-verification-ui/e2e/industries-route.spec.js)。P2 / M。
43. ~~**5 板塊 Terminal — Phase 6：跨板塊完善（Command Bar、Watchlist、Push Alert、手機密度）**~~ — **2026-05-13 repo 側已交付**：[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) 支援 5 板塊跳轉、symbol lookup → `/insights?symbol=...` 與 Recent chips；[`GlobalWatchlistDock.jsx`](data-verification-ui/src/components/GlobalWatchlistDock.jsx) 提供跨板塊 shared Watchlist + Price Alerts；[`price_alerts.py`](price_alerts.py) + [`api_routers/price_alerts.py`](api_routers/price_alerts.py) 提供 JSONL alert queue 與 quote threshold check；[`theme/terminal.css`](data-verification-ui/src/theme/terminal.css) 套入 terminal palette，互動元素同步補 44px touch target。測試錨點：[`tests/api/test_price_alerts_router.py`](tests/api/test_price_alerts_router.py)、[`queue43-cross-board.spec.js`](data-verification-ui/e2e/queue43-cross-board.spec.js)。P2 / L。
44. **Terminal Master Plan §0 Phase 4 — 讀者層×工作台層 IA** — 見上節 [「隊列 44」](#terminal-master-plan-phase4-queue-44)。**2026-05-16 repo 首波**：`portalPhase4.js`（Gate 0 預設）、**44a** 讀者 intro／CTA、**44b** 三工作台導引條、**44d** Command Bar placeholder 分路；**2026-05-16（續）／44c**：`PORTAL_PHASE4_CTA` 文案表 + `newsContextHref`／`columnsContextHref` + `?focus=` 過濾、`SymbolDeepDive` 雙向 CTA、`InsightsHome` 反向 CTA、`news/columns-focus-badge`，`fusionDirection=bidirectional`。E2E **`phase4-ia-portal.spec.js`** 已含 44c 兩條斷言。**2026-05-16 收尾**：Gate 0 ✅ 簽核（五項決議鎖入表格）、`BLOOMBERG_ALIGNMENT` §4 已勾帳（§4e）；**44b 第一波** dashboard tab 拆分／portfolio Watchlist dock 化已交付並由 [`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js) 覆蓋；**44d** placeholder 分路已交付並由 [`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js) `/columns` reader 文案斷言覆蓋。**2026-05-14 續**：**44a 工程簽核** — 依 [`DESIGN.md`](DESIGN.md)「Portal Phase 4」90s 腳本錨點 + `cd data-verification-ui && npm run build && npm run test:e2e` 全綠（維護者產品人測簽名可於上節補一行日期）；**44b 第二波** 高密度區塊清單 + **`/portfolio?tab=`** 收斂 + **P2 Skip link** 已入庫（見隊列 44 內新段落與 `skip-link.spec.js`）。**2026-05-21**：NEXT-4 純文件盤點 [`docs/PHASE4_44B_DENSITY_AUDIT.md`](docs/PHASE4_44B_DENSITY_AUDIT.md) 已補 25 列維護者 A/B/C 勾選表；下一步 44b 實作仍等待 maintainer pick（隊列 62）。**2026-08-30 ITER-P4-44A**：`/insights` 首屏改為今日建議，說明／CTA／健康晶片摺疊（CHANGELOG **2026-08-30**）。P2 / M。

45. **7 領域 Finance Terminal 進化路線（plan `finance-terminal-repo-1-cheeky-pike.md`）** — **P3／P1／P2-mock／P4／P5-mock 全部交付（2026-05-16）**：
    - **P3**：[`api_routers/earnings.py`](api_routers/earnings.py) + [`EarningsInsightHome.jsx`](data-verification-ui/src/modules/insights/pages/EarningsInsightHome.jsx)（`/insights?tab=earnings`）
    - **P1**：[`PortfolioRiskPanel.jsx`](data-verification-ui/src/components/PortfolioRiskPanel.jsx)（TP/SL+ATR14+一鍵 PENDING_REVIEW）
    - **P2-mock**：`GET /api/macro/compute-memory` + [`ComputeMemoryPanel.jsx`](data-verification-ui/src/components/ComputeMemoryPanel.jsx)（HBM/DRAM／Capex／GPU spot）
    - **P4**：news router `commentary_zh/en` passthrough（無 LLM）+ [`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 中/EN toggle
    - **P5-mock**：`GET /api/macro/onchain` + [`OnchainMetricsPanel.jsx`](data-verification-ui/src/components/OnchainMetricsPanel.jsx)（BTC 估值／交易所淨流／永續資費）
    - **驗證**：16/16 E2E + 38/38 backend tests 全綠。
    - **P2-live PR-0**（governance only，2026-05-16）：`docs/REALTIME_DATA_SOURCES_GOVERNANCE.md` §2 + §6 登錄 SEC EDGAR／CoreWeave／TrendForce 三來源。
    - **P2-live PR-A**（2026-05-16）：[`tools/sec_edgar_capex.py`](tools/sec_edgar_capex.py) + `COMPUTE_MEMORY_CAPEX_LIVE` flag；EDGAR 失敗退 fixture；`live_block_status` 三狀態；11 backend tests + 3 compute-memory tests 綠。
    - **P2-live PR-B**（2026-05-16）：[`tools/coreweave_gpu_spot.py`](tools/coreweave_gpu_spot.py) + `COMPUTE_MEMORY_GPU_LIVE` flag；CoreWeave HTML parse 失敗整批退 fixture；7 backend tests + 2 compute-memory tests 綠。
    - **P5-live PR-0**（governance only，2026-05-16）：§2 + §7 登錄 Binance public futures／Glassnode／CryptoQuant 三來源。
    - **P5-live PR-C**（2026-05-16）：[`tools/binance_funding_rate.py`](tools/binance_funding_rate.py) + `ONCHAIN_FUNDING_LIVE` flag；Binance public futures premiumIndex 抓 BTC/ETH 8h funding 並 annualize；8 backend tests + 3 onchain tests 綠。
    - **剩 backlog（付費源 · 2026-05-20 刻意延後）**：MVRV-Z／exchange flow **live**（Glassnode／CryptoQuant）／HBM **live**（TrendForce）— **改由隊列 52–56 免費／freemium 路線承接**（見 [§ 免費資料擴充](#free-data-expansion-queue-52)）；44b 進階收斂仍見隊列 44／[`CODEX_NEXT_BATCH`](docs/CODEX_NEXT_BATCH.md) NEXT-4。P1 / M。

<a id="free-data-expansion-queue-52"></a>

## 免費資料擴充 — Bloomberg 廣度（零付費訂閱 · 隊列 52–56）

> **背景**：維護者評估 Glassnode／CryptoQuant／TrendForce 訂閱過貴；**不**為「像 BBG」購買專有 feed。本路線以 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](docs/REALTIME_DATA_SOURCES_GOVERNANCE.md) **free／freemium** 為界，把**管線與 tools 已有**、**Portal 未露出**的指標接到 read-only API + Dashboard／Insights，每欄位 **`source` + `as_of`**，失敗 **`DATA_MISSING`／`N/A`**，**禁止 LLM 補數字**。
>
> **四軸對照**：**A**＝加密鏈上／情緒（隊列 **53**）｜**B**＝半導體／算力（**54**）｜**C**＝宏觀總經（**55**）｜**D**＝財報／基本面（**56**）。橫切 **F0**（**52**）先於四軸。
>
> **與其他隊列**：**52-F0-1** 對齊 CODEX **NEXT-5**；**53-FA-3** 可與 **NEXT-2** Quant intraday 同 PR 或緊鄰；**不**取代隊列 18–21 營運 Push。

### Phase F0 — 橫切底座（隊列 52）

| 切片 | 目標 | 主要產出 | 驗收（最小） |
|------|------|----------|--------------|
| ~~**F0-1**~~ | `api.py` 契約安全網 | **2026-05-20 已交付**：新增 [`tests/api/test_api_py_contract.py`](tests/api/test_api_py_contract.py)（≥8 條 `api.py` inline route） | `pytest tests/api/test_api_py_contract.py -q` 綠；全 `tests/api/` 驗證見本次紀錄 |
| ~~**F0-2**~~ | 免費源治理登錄 | **2026-05-21 已交付**：[`REALTIME_DATA_SOURCES_GOVERNANCE.md`](docs/REALTIME_DATA_SOURCES_GOVERNANCE.md) §2／§8 補 CoinGecko public/Demo API、Alternative.me Fear & Greed、Blockchain.com charts、DefiLlama public API（pending）；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 補治理註記 | 文件 + ENV 註記 |
| **F0-3** | 共用 fetch 契約 | 新指標一律 `tools/*.py` + `_get_cache`／`_set_cache`（或抽 `tools/market_free.py`），**禁止**在 JSX 直接打外部 URL；2026-05-21 contract 已先寫入治理文件，程式抽象待首個新 source 實作時落地 | 每源 ≥1 pytest |
| ~~**F0-4**~~ | `DASHBOARD_CONTRACT` 一節 | **2026-05-21 已交付**：[`DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) 新增「免費資料擴充區塊（隊列 52 F0）」欄位語意（onchain valuation／exchange-flow honesty／compute-memory／macro series／earnings）與降級契約 | 文件契約已就緒；API JSON 待各 phase 實作時逐項對齊 |

**紅線**：F0 **不**改 `main.py` pipeline、**不**接付費 key 為前提的功能。

---

### Phase FA — 加密鏈上／情緒（軸 **A** · 隊列 53）

**現況**：[`GET /api/macro/onchain`](api_routers/macro.py) — **funding** 已可 `ONCHAIN_FUNDING_LIVE`（Binance public）；**valuation**／**exchange_flow** 仍 mock（佔位 Glassnode／CryptoQuant）。日報管線已用 **alternative.me** F&G、**CoinGecko**（[`tools_legacy.py`](tools_legacy.py)）。

| 切片 | 目標 | DO | DO NOT |
|------|------|-----|--------|
| **FA-1** | 估值區塊 free live | 新 `tools/coingecko_metrics.py`（或薄封裝）拉 BTC market_chart／global；**Fear & Greed** 走 `alternative.me`；併入 `get_onchain_metrics()` `valuation` block，`source`／`as_of`／`ONCHAIN_VALUATION_LIVE` flag | 不假裝 MVRV-Z；不標 CryptoQuant 淨流 |
| ~~**FA-2**~~ | 淨流區塊誠實降級 | **2026-05-21 已交付**：API 回 `exchange_flow.enabled=false` + `reason=no_free_equivalent` + `live_block_status.exchange_flow=disabled`；UI 顯示 **「CEX 淨流：無免費同級來源」**，不再顯示 mock CEX row | 不用 mock 數字冒充 live 淨流 |
| **FA-3** | Portal 整合 | [`OnchainMetricsPanel.jsx`](data-verification-ui/src/components/OnchainMetricsPanel.jsx) 顯示 `live_block_status` 三態；[`dashboard-onchain.spec.js`](data-verification-ui/e2e/dashboard-onchain.spec.js) 擴充；可選 **Insights › Quant** 摘要列 | 不 15s 輪詢 CoinGecko（遵守 rate limit + cache） |
| **FA-4** | 可選廣度 +1 | 治理審核後接 **DefiLlama**（TVL／協議）**或** Blockchain.info（活躍地址）單一 block | 不一次加多源 |

**驗收**：`pytest tests/api/test_onchain_api.py tests/api/test_binance_funding_rate.py -q` + 相關新 test 綠；`npm run test:e2e` 含 onchain spec 綠。

---

### Phase FB — 半導體／算力（軸 **B** · 隊列 54）

**現況**：[`GET /api/macro/compute-memory`](api_routers/macro.py) — SEC EDGAR capex、CoreWeave GPU **工具已交付**；預設 fixture，需 **`SEC_EDGAR_CONTACT_EMAIL`** + **`COMPUTE_MEMORY_CAPEX_LIVE=1`**／**`COMPUTE_MEMORY_GPU_LIVE=1`**（見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）。

| 切片 | 目標 | DO | DO NOT |
|------|------|-----|--------|
| **FB-1** | 營運開 live | 文件化 staging checklist：填 `SEC_EDGAR_CONTACT_EMAIL`、開兩個 `*_LIVE=1`、確認 `live_block_status` | 不買 TrendForce |
| **FB-2** | Dashboard 露出強化 | [`ComputeMemoryPanel.jsx`](data-verification-ui/src/components/ComputeMemoryPanel.jsx) 每區塊 `source`／`as_of`／失敗態；[`dashboard-compute-memory.spec.js`](data-verification-ui/e2e/dashboard-compute-memory.spec.js) 覆蓋 live badge | 不把 HBM 標成 live |
| **FB-3** | 專欄／觀點 CTA | `/columns` 半導體 tab 或 `/insights` 加 **「算力成本」** 深連結 → `/dashboard?tab=depth` | 不新增付費 DRAM 價 |
| **FB-4** | 快取與降級 | capex／GPU fetch 失敗 **整批** 回 fixture（沿用既有 all-or-nothing 模式） | 不讓 LLM 寫 capex 數字 |

**驗收**：`pytest tests/api/test_compute_memory_api.py tests/api/test_sec_edgar_capex.py tests/api/test_coreweave_gpu_spot.py -q`；E2E compute-memory 綠。

---

### Phase FC — 宏觀總經（軸 **C** · 隊列 55）

**現況**：[`GET /api/macro/snapshot`](api_routers/macro.py) 8 指標 + spark；**FRED**、**FMP**（catalyst）在 ENV 已列，FMP 為可選 catalyst。

| 切片 | 目標 | DO | DO NOT |
|------|------|-----|--------|
| **FC-1** | FRED 加深 | `tools/fred_macro.py`（或擴 `macro_context_tool`）拉 2s10s、實質利率等序列；併入 snapshot 或新 `GET /api/macro/fred-series?ids=...` | 無 `FRED_API_KEY` 時靜默降級 |
| **FC-2** | FMP catalyst | 有 `FMP_API_KEY` 時 [`CatalystCalendar.jsx`](data-verification-ui/src/components/CatalystCalendar.jsx) 顯示來源；無 key 顯示說明 | 不捏造 Fed／CPI 日期 |
| **FC-3** | Regime／離線提示 | 延續 `qsi_offline_macro_as_of_hint`；macro 卡逐指標 `source` | 不混用 BQ KPI 與 yfinance 同一欄 |
| **FC-4** | 可選 yfinance 備援 | 治理審核後 **Polygon.io free tier** 僅作 quote fallback（5 req/min），文件已列 fallback | 不作為主來源 |

**驗收**：`pytest tests/api/test_macro_router.py -q`；[`dashboard-route.spec.js`](data-verification-ui/e2e/dashboard-route.spec.js) 綠。

---

### Phase FD — 財報／基本面（軸 **D** · 隊列 56）

**現況**：[`api_routers/earnings.py`](api_routers/earnings.py) `upcoming` + [`EarningsInsightHome.jsx`](data-verification-ui/src/modules/insights/pages/EarningsInsightHome.jsx)；[`GET /api/analysis/{symbol}`](api.py) bundle；**Financial Datasets** freemium（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）。

| 切片 | 目標 | DO | DO NOT |
|------|------|-----|--------|
| **FD-1** | Earnings 首屏 | [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 頂部 **7 日財報雷達** strip（`useEarningsUpcoming`）；row → `/insights?tab=earnings` 或 `?symbol=` | 不承諾 EPS consensus |
| **FD-2** | FD 基本面帶 | 有 `FINANCIAL_DATASETS_API_KEY` 時 `analysis` bundle 帶 `fundamentals` 摘要；[`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx) 有資料才渲染 | 無 key 不顯示假表格 |
| **FD-3** | 與日報互指 | 財報列連到 `/report/{date}` 或 watchlist pillar badge（重用 `earnings_watchlist`） | 不開 sell-side 完整模型表（另立專案） |
| **FD-4** | E2E | 擴 [`insights-symbol-deep-dive.spec.js`](data-verification-ui/e2e/insights-symbol-deep-dive.spec.js) 或新 `insights-earnings-radar.spec.js` | — |

**驗收**：`pytest tests/api/test_earnings_router.py` [`test_api_analysis_bundle.py`](test_api_analysis_bundle.py) -q`；Insights 相關 E2E 綠。

---

### 隊列 52–56 一覽（勾選用）

52. **免費資料擴充 — Phase F0 橫切底座** — **F0-1 / NEXT-5 已交付（2026-05-20）**；**F0-2／F0-4 已交付（2026-05-21）**：治理登錄 + ENV 註記 + `DASHBOARD_CONTRACT` 免費擴充區塊。剩 **F0-3**：首個新 source 實作時落 `tools/*.py` + cache 契約與 pytest。**依賴**：無。P1 / S。

53. **免費資料擴充 — Phase FA 加密鏈上／情緒（軸 A）** — **FA-2 已交付（2026-05-21）**；剩 **FA-1／FA-3／FA-4**。**刻意不做** CryptoQuant／Glassnode 付費 MVRV／CEX 淨流；CEX 淨流已明確 disabled。**依賴**：隊列 **52** F0-3（首個新 source fetch 契約）。P1 / M。

54. **免費資料擴充 — Phase FB 半導體／算力（軸 B）** — 見上表 **FB-1～FB-4**；以 **開 ENV live** + UI 為主，**零訂閱**。**依賴**：隊列 **52**。**營運**：`SEC_EDGAR_CONTACT_EMAIL` 必填。P1 / M。

55. **免費資料擴充 — Phase FC 宏觀總經（軸 C）** — 見上表 **FC-1～FC-4**；**FRED_API_KEY**／**FMP_API_KEY** 可選。**依賴**：隊列 **52**。**不**把 macro 變行情牆。P2 / M。

56. **免費資料擴充 — Phase FD 財報／基本面（軸 D）** — 見上表 **FD-1～FD-4**；**FINANCIAL_DATASETS_API_KEY** 可選。**依賴**：隊列 **52**；與隊列 **45-P3** earnings 頁互補（不重寫 router）。P2 / M。

**NOT in scope（本路線）**：Glassnode／CryptoQuant／TrendForce 訂閱、全市場 screener、tick 行情牆、MDI 多視窗、真實下單。

---

<a id="session-2026-05-20-execution-order"></a>

## Session 2026-05-20 — 總執行順序（Bloomberg 對齊）

> **產品策略（維護者 · 一行）**：**工作流脊骨優先**（可審計監控路徑、Command Bar、Gate 可追溯、工作台 **N≤3**），再以 **free／freemium** 拉高資料廣度（隊列 52–56）；**刻意不採** Glassnode／CryptoQuant／TrendForce 付費訂閱。對齊 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)（工作流＋可審計，非複製 BBG UI／專有 feed）。

| 序 | 隊列／切片 | 主軸 | 說明 |
|:--:|------------|------|------|
| 1 | **57** ≈ **52-F0**／CODEX **NEXT-5** | 契約＋F0 | `api.py` 契約測試；免費源治理；`tools` cache 契約；`DASHBOARD_CONTRACT` 一節 |
| 2 | **58**／**NEXT-1** | a11y／CSS | 全站 44px 掃描 + `index.css` dead CSS 小批刪；FE-6 刻意延後項 |
| 3 | **59**／**NEXT-3** | 工作流 | Settings **Gate failure detail drawer**（展開 `issues_preview`／blocking） |
| 4 | **53**（FA）＋~~**60**／**NEXT-2**~~ | 資料＋Quant | 鏈上 free live；Quant **Intraday Monitor** 已交付（paper + 既有 quote） |
| 5 | ~~**61**／**NEXT-4**~~ | 文件 | **44b 高密度盤點表**已交付（維護者勾選後才寫程式） |
| 6 | **62** | 工作流 | **44b 進階收斂實作**（依 61 產出；Insights／News 等 tab 收斂） |
| 7 | **54 → 55 → 56** | 資料 | FB 開 ENV live → FC 宏觀 → FD 財報 strip |
| 8 | **63–67** | 工作流＋閉環 | Command Bar 下一刀；a11y 橫切；OHLC+QSREC 疊圖；Track Record↔Monitor；告警→DeepDive |
| 9 | **68–70** | 研究／Gate | earnings insight live；NotebookLM／Agency live；`STRICT_INSTITUTIONAL` 生產策略 |
| 10 | **71** | 流程 | design spec + `writing-plans` 實作計畫（免費資料路線） |

**交錯**：57 與 52 可同一 PR；58 可與 61（純文件）並行；62 **依賴** 61 勾選結果。**紅線**：同 [§ 免費資料擴充](#free-data-expansion-queue-52) 與 [`CODEX_NEXT_BATCH.md`](docs/CODEX_NEXT_BATCH.md)。

---

<a id="codex-fe6-closeout-queue-57"></a>

## Codex／FE-6 收尾（隊列 57–61）

Handoff 規格：[`docs/CODEX_NEXT_BATCH.md`](docs/CODEX_NEXT_BATCH.md)。**建議順序**：57 → 58 → 59 → 60 → 61。

57. ~~**CODEX NEXT-5 — `api.py` 契約測試（≈ 隊列 52 F0-1）**~~ — **2026-05-20 已交付**：新增 [`tests/api/test_api_py_contract.py`](tests/api/test_api_py_contract.py) 覆蓋 ≥8 條 `api.py` inline route；未改 API 語意。驗證：`pytest tests/api/test_api_py_contract.py tests/api/test_api_contract_smoke.py -q` 30 passed；`pytest tests/api/ -q` 140 passed。**剩餘 F0**：52 F0-2～F0-4。P1 / S。

58. ~~**CODEX NEXT-1 — Touch target 掃描 + dead CSS 審計**~~ — **2026-05-20 已交付**：新增 [`e2e/touch-target.spec.js`](data-verification-ui/e2e/touch-target.spec.js)，375px／1280px 量測 Command Bar 主要控制與 shared monitor toggle ≥44px；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx)、[`GlobalWatchlistDock.jsx`](data-verification-ui/src/components/GlobalWatchlistDock.jsx) 補小屏 44px 觸控高度。`index.css` dead-CSS audit 僅做 scoped 搜尋；未刪大批全域 CSS。驗證：`npm run lint`、`npm run build`、`npm run test:e2e` 84 passed。P2 / S。

59. ~~**CODEX NEXT-3 — Gate failure detail drawer**~~ — **2026-05-20 已交付**：[`Settings.jsx`](data-verification-ui/src/pages/Settings.jsx) Gate 失敗列表 row 可點開 drawer／modal，顯示完整 `issues_preview`、blocking／warning／issue 計數、profile、attempt、timestamp、`used_fallback`；沿用 **`GET /api/gate-failures`**，未改 `main.py` Gate 或 BQ schema。驗收：[`e2e/settings-page.spec.js`](data-verification-ui/e2e/settings-page.spec.js) 新增 detail drawer flow。P1 / S。

60. ~~**CODEX NEXT-2 — Quant Intraday Monitor（隊列 33 續）**~~ — **2026-05-20 已交付**：[`api.py`](api.py) `GET /api/quant/signals` 讀 paper `execution_intents.jsonl` active rows（`PENDING_REVIEW`／`APPROVED_FOR_PAPER`／`PAPER_SUBMITTED`／`PAPER_FILLED`），回 `source`／`count`／`symbol`／`status`／`reference_*`；無 active rows 時保留 placeholder fallback。[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 新增 Intraday Monitor，使用既有 `useSymbolQuote({ livePoll: true })` 顯示報價、filter 與 row → `/insights?symbol=...`；[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 與 [`quant-intraday-monitor.spec.js`](data-verification-ui/e2e/quant-intraday-monitor.spec.js) 補 e2e 覆蓋。**未做**：新付費行情源、自動交易、日報 pipeline 改動。驗證：`pytest test_api_quant_signals.py -q` 8 passed；`npm run test:e2e -- quant-intraday-monitor.spec.js` 1 passed（完整驗證見 commit 紀錄）。P1 / M。

61. ~~**CODEX NEXT-4 — 44b 高密度盤點（僅文件）**~~ — **2026-05-21 已交付**：新增 [`docs/PHASE4_44B_DENSITY_AUDIT.md`](docs/PHASE4_44B_DENSITY_AUDIT.md)，覆蓋 `/news`、`/columns`、`/insights`、`/dashboard`、`/portfolio` 與 global dock 共 25 個區塊；每列含 DOM／`data-testid` 錨點、密度標籤、首屏可見性、建議 tab／dock／keep、N≤3 路徑影響與維護者 A/B/C 勾選欄。**未動 React／API**。**隊列 62** 仍需等待 maintainer pick 後才開實作。P2 / S。

---

<a id="workflow-spine-queue-62"></a>

## 工作流脊骨（隊列 62–64）

62. **Phase 4 IA — 44b 進階收斂（實作）** — 依 **隊列 61** 盤點表與 Gate 0 **N=3**；候選：[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 多 tab 再收斂、[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx) 首屏密度、[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) 與 side panel 分工。**驗收**：擴充 [`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js)；人測路徑 ≤3 點。**依賴**：**61**（維護者勾選）。P1 / M。

63. **隊列 29 續 — Command Bar「Bloomberg 感」下一刀** — 在 [`docs/ADR_COMMAND_BAR_PERMISSIONS.md`](docs/ADR_COMMAND_BAR_PERMISSIONS.md) 邊界內擴 [`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx)：例 board 別名、recent 語意、與 **隊列 65–67** 深連結（symbol／告警）；**不**新增 W 類未審核後端指令。**驗收**：[`command-bar-route.spec.js`](data-verification-ui/e2e/command-bar-route.spec.js)。P1 / M。

64. **a11y 橫切（modal／landmark／focus trap）** — 補 **隊列 58** 未涵蓋項：Gate drawer（59）、Settings modal、Command Bar 面板之 `role`／`aria-*`／focus trap；[`DESIGN.md`](DESIGN.md) 與 §4f 對帳。**可併** 59 或接在 62 後。P2 / S。

---

<a id="terminal-closed-loop-queue-65"></a>

## Terminal 產品閉環（隊列 65–67）

> 對齊進度表 KPI：**QSREC→監控→告警→紙上交易**（[`§ 進度分析表`](#progress-vs-wall-st-bloomberg)）；工作台路徑仍遵守 **N≤3**。

65. **OHLC + QSREC 疊圖** — 在 [`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx) 或 [`SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx) 疊加當日／近期 **QSREC** 進場標記（來自 `GET /api/execution-intents` 或 gate-index，**僅 paper**）；**禁止** LLM 標價。**驗收**：E2E mock 至少 1 marker。P1 / M。

66. **Track Record ↔ Monitor 互指** — [`TrackRecordHome.jsx`](data-verification-ui/src/modules/insights/pages/TrackRecordHome.jsx) closed row → `/portfolio?tab=monitor` 或 `/insights?symbol=`；[`WatchlistMonitor.jsx`](data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx) 顯示該 symbol 是否有 closed W/L（讀既有 track-record API）。**驗收**：[`insights-track-record.spec.js`](data-verification-ui/e2e/insights-track-record.spec.js) 擴 1 條。P2 / M。

67. **價格告警 → SymbolDeepDive（N≤3）** — [`PriceAlertToaster.jsx`](data-verification-ui/src/components/PriceAlertToaster.jsx)／digest 點擊 → `/insights?symbol=`（帶 `?from=alert` 可選）；路徑 **告警 → 標的狀態 →（可選）新聞／專欄** ≤3 點；對齊 [`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js) `maxWorkbenchPathClicks`。P1 / S。

---

<a id="research-gate-queue-68"></a>

## 研究深化與機構 Gate（隊列 68–70）

68. **Earnings insight live（隊列 45-P3 續）** — [`api_routers/earnings.py`](api_routers/earnings.py) `GET /api/earnings/insight/{symbol}` 由 scaffold `enabled: false` 改 **可選 live**（僅在有審計來源＋ENV 時）；[`EarningsInsightHome.jsx`](data-verification-ui/src/modules/insights/pages/EarningsInsightHome.jsx) 有資料才渲染。**DO NOT**：假 EPS consensus。P2 / M。

69. **NotebookLM／Agency live client（隊列 24–25／32 續）** — 在治理與成本上限下接 [`tools/notebooklm_tool.py`](tools/notebooklm_tool.py)／[`agents/agency/`](agents/agency/) live；預設仍關；staging 小流量驗證後才開 production 旗標。**紅線**：不取代 `validate_report`。P2 / L。

70. **`STRICT_INSTITUTIONAL_PHASE_A/B/C` 生產策略** — 文件化 staging→production 翻轉條件（[`report_html_gates.py`](report_html_gates.py)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；可選 BQ 儀表：通過率 vs 降級率；**不**在未量測前強制 production 全開。P2 / S。

---

<a id="planning-process-queue-71"></a>

## 規劃流程（隊列 71）

71. **免費資料路線 — design spec + 實作計畫** — 撰寫 `docs/superpowers/specs/2026-05-20-bloomberg-free-data-design.md`（四軸 A/B/C/D、ENV、降級、與 52–56 切片對照）；再以 `writing-plans` 產出逐步實作計畫（**不**取代本檔隊列勾選）。**依賴**：無（可與 57 並行）。P2 / S。

---

46. ~~**Frontend UX Overhaul — Mobile + Desktop（FE-1 ~ FE-6）｜FE-1：Responsive App Shell（Mobile Bottom Tab + Desktop Side Nav 共存）**~~ — **2026-05-20 已交付（差距補完，主體沿用既有 BottomNav + SideNav）**：核對現況時發現 FE-1 主體早期已隨 5 板塊改版交付（[`data-verification-ui/src/components/BottomNav.jsx`](data-verification-ui/src/components/BottomNav.jsx) 5 板塊 + 設定、`.bottom-nav { display:none }` at `md+`；[`data-verification-ui/src/app/layout/SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) `.side-nav { display:none }` 手機、`display:flex` 768px+；BottomNav 與 SideNav 共用同一組 5 routes + `/settings`）；本切片補 **差距**：[`data-verification-ui/src/index.css`](data-verification-ui/src/index.css) 新增 `--bottom-tab-height`（alias `--nav-h`）／`--sidebar-width: 220px`／`--sidebar-width-xl: 240px`，並將 `.side-nav` width hardcode 改用 CSS 變數；新增 [`data-verification-ui/e2e/responsive-app-shell.spec.js`](data-verification-ui/e2e/responsive-app-shell.spec.js) 涵蓋 mobile 375px（BottomNav 顯示／SideNav 隱）、desktop 1280px（反之）與 CSS 變數存在性。**未實作（與 5 板塊衝突，刻意不做）**：規格原文「三 Tab：日報 / 監控 / 設定 + `/briefs` / `/monitor` 新路由」與隊列 37–43 5 板塊收斂衝突，沿用現有 5 板塊不改路由；`BottomTabBar.jsx` 不另建以避免與 `BottomNav.jsx` 重複。CHANGELOG **2026-05-20** `### PWA（隊列 46 · FE-1 Responsive App Shell 差距補完）`。P1 / M。

    **FE-1（原規劃，保留備查）**：建立同時支援手機與桌面的 App Shell，以 CSS breakpoint 決定導覽模式，不拆分 codebase — 見 TODOS.md 本節。
    - 新增 [`data-verification-ui/src/app/layout/BottomTabBar.jsx`](data-verification-ui/src/app/layout/BottomTabBar.jsx)（三 Tab：日報 / 監控 / 設定）；`md:hidden`（桌面隱藏）；手機固定底部，高度 56px。
    - 修改 [`data-verification-ui/src/app/layout/SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx)：`hidden md:flex`（手機隱藏，桌面 240px 側欄）。
    - [`data-verification-ui/src/App.jsx`](data-verification-ui/src/App.jsx) route 統一：`/briefs`（日報）、`/monitor`（監控）、`/settings`（設定）；BottomTab 與 SideNav 共用同一 route，不各自維護。
    - [`data-verification-ui/src/index.css`](data-verification-ui/src/index.css) 補 CSS variables：`--bottom-tab-height: 56px`（手機 body padding-bottom）、`--sidebar-width: 240px`（桌面 main content offset）。
    - 桌面主內容區維持現有 `max-width: 1120px` 置中，手機全寬。
    - 驗收：`cd data-verification-ui && npm run test:e2e` mobile viewport（375px）+ desktop viewport（1280px）smoke。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 46 · FE-1 Responsive App Shell）`。P1 / M。

47. ~~**Frontend UX Overhaul — FE-2：Daily Brief 頁重構（可折疊卡片 + Profile 切換 + Ticker 橫條）**~~ — **2026-05-20 已交付（差距補完，聚焦 `StructuredReportView`）**：FE-2 規格原把目標放在 [`data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx`](data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx)，但該檔實際是 Terminal 工作區（symbol cards 容器）。真正的「每日戰報頁」是 [`/report/:date` → `pages/Report.jsx`](data-verification-ui/src/pages/Report.jsx) 渲染的 [`components/report/StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx)；ProfileSwitcher 已存在於 [`BriefProfileBar.jsx`](data-verification-ui/src/components/report/BriefProfileBar.jsx)（`full / lite / crypto-only`）。本切片補差距：新增 [`components/report/BriefSectionCard.jsx`](data-verification-ui/src/components/report/BriefSectionCard.jsx) chevron 折疊（`qs_brief_card_collapse_v1` localStorage 按 blockId 持久化）、[`components/report/TickerStrip.jsx`](data-verification-ui/src/components/report/TickerStrip.jsx) 頁頂主代號條（預設 BTC/ETH/SPY/NVDA/MSFT/TSM；手機 `overflow-x` scroll、768px+ `flex-wrap: wrap`；走既有 `useSymbolQuote`）、[`components/report/GateBadge.jsx`](data-verification-ui/src/components/report/GateBadge.jsx) 緊湊 `Gate ✓` ／ `Gate ✗ (N)` 徽章；改 [`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx) 插入 TickerStrip、GateBadge，並以 `<BriefSectionCard>` 包覆每個 `<BlockSection>`；[`index.css`](data-verification-ui/src/index.css) 補 `.brief-section-card`／`.ticker-strip`／`.gate-badge` 樣式；新增 [`e2e/daily-brief-collapse.spec.js`](data-verification-ui/e2e/daily-brief-collapse.spec.js)（ticker 渲染、折疊／展開切換、桌面 `flex-wrap: wrap`）。**刻意未實作**：規格「桌面雙欄」對敘事報告可讀性不利，沿用單欄；ProfileSwitcher 已有 `BriefProfileBar`，不另建。CHANGELOG **2026-05-20** `### PWA（隊列 47 · FE-2 Daily Brief 重構差距補完）`。P1 / M。

    **FE-2（原規劃，保留備查）**：手機與桌面共用同一組件，版型自動響應；卡片可折疊、Ticker 橫條與 Profile 切換條 — 見 TODOS.md 本節。
    - [`data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx`](data-verification-ui/src/modules/daily-brief/pages/DailyBriefPage.jsx) 拆出 `<BriefSectionCard>`（標題 + chevron + 折疊 body）；手機單欄全寬，桌面可選雙欄（`md:grid md:grid-cols-2`，儀表板 + 新聞並列）。
    - 頁頂 `<TickerStrip>`：手機橫向 scroll，桌面固定顯示全部代號（wrap 換行）；資料來自 `GET /api/symbols/{symbol}/quote`，symbols 讀 [`assets_config.json`](assets_config.json)。
    - Header `<GateBadge>`：gate_passed 狀態來自 `GET /api/reports/{report_date}/html`。
    - `<ProfileSwitcher>` 橫條：full / lite / crypto-only，切換後 re-fetch 對應 profile；手機 scroll 橫條，桌面 inline button group。
    - 新增組件：[`data-verification-ui/src/modules/daily-brief/components/BriefSectionCard.jsx`](data-verification-ui/src/modules/daily-brief/components/BriefSectionCard.jsx)、[`TickerStrip.jsx`](data-verification-ui/src/modules/daily-brief/components/TickerStrip.jsx)、[`GateBadge.jsx`](data-verification-ui/src/modules/daily-brief/components/GateBadge.jsx)、[`ProfileSwitcher.jsx`](data-verification-ui/src/modules/daily-brief/components/ProfileSwitcher.jsx)。
    - E2E：[`data-verification-ui/e2e/daily-brief-collapse.spec.js`](data-verification-ui/e2e/daily-brief-collapse.spec.js)（mobile + desktop viewport 各自驗收）。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 47 · FE-2 Daily Brief 重構）`。P1 / M。

48. ~~**Frontend UX Overhaul — FE-3：Monitor 頁（Watchlist + 搜尋 + 即時報價）**~~ — **2026-05-20 已交付（差距補完，掛入 Portfolio › Monitor tab）**：規格的 `/monitor` 獨立路由與 5 板塊收斂衝突，沿用既有路由不另立 route；改為在 [`PortfolioHome.jsx`](data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx) 新增 `Monitor` tab（`/portfolio?tab=monitor`）承載。新增 [`modules/portfolio/components/WatchlistMonitor.jsx`](data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx)：共用既有 `qsi_watchlist` localStorage（避免 spec 提的 `wl_symbols` 與現況分裂），逐 row 以 `useSymbolQuote(sym, { livePoll: true })` 拉即時報價（沿用 `VITE_TERMINAL_POLL_MS`，預設 45s）；row 顯示 symbol / 最新價 / 漲跌幅 badge（up/dn/flat 色），row 點擊 navigate `/insights?symbol=…`（既有 `SymbolDeepDive` 即為「symbol 詳情」）；附 client-side `搜尋 watchlist` 篩選框、Add／Remove。[`index.css`](data-verification-ui/src/index.css) 末段加 `.watchlist-monitor`／__header/__toolbar/__filter/__add-input/__add-btn/__list/__row/__open/__symbol/__price/__change（up/down/flat）/__remove。**刻意未實作**：規格的桌面 split-pane（左清單 / 右 SymbolCandleChart + snapshot）— `/insights?symbol=…` 已是現成詳情頁、且 split-pane 需新增容器、與 1120px max-width 桌面 layout 衝突；改以「點擊 row → /insights?symbol=」收斂；亦未使用 `assets_config.json` 預載（不覆蓋使用者 watchlist）。新增 [`e2e/monitor-watchlist.spec.js`](data-verification-ui/e2e/monitor-watchlist.spec.js) 兩案：BTC row 報價非 dash + client-side 篩選；row click 跳轉 `/insights?symbol=NVDA`。驗證：`cd data-verification-ui && npm run lint && npm run build` 綠；`npm run test:e2e` 全綠（73/73，含本次新加 2 案）。CHANGELOG **2026-05-20** `### PWA（隊列 48 · FE-3 Monitor tab 差距補完）`。P1 / M。

    **FE-3（原規劃，保留備查）**：手機列表式，桌面可選 split-pane（左 watchlist / 右 symbol 詳情） — 見 TODOS.md 本節。
    - 新增 [`data-verification-ui/src/modules/monitor/pages/MonitorPage.jsx`](data-verification-ui/src/modules/monitor/pages/MonitorPage.jsx)。
    - `<WatchlistRow>`：symbol / 公司名 / price / 漲跌幅 badge（up/dn 色碼）。
    - 搜尋框 client-side filter（不重新 fetch）。
    - 桌面增加 `<SymbolDetailPanel>`（右側 pane）：點擊 WatchlistRow 後顯示 `SymbolCandleChart` + snapshot，複用現有 [`data-verification-ui/src/components/SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx)；手機則 navigate 至 [`data-verification-ui/src/modules/monitor/pages/SymbolDetailPage.jsx`](data-verification-ui/src/modules/monitor/pages/SymbolDetailPage.jsx)。
    - 輪詢 `useSymbolQuote` hook，間隔沿用 `VITE_TERMINAL_POLL_MS`（預設 45000ms）。
    - Watchlist symbols 初始讀 [`assets_config.json`](assets_config.json)；使用者自訂存 localStorage（key: `wl_symbols`）。
    - E2E：[`data-verification-ui/e2e/monitor-watchlist.spec.js`](data-verification-ui/e2e/monitor-watchlist.spec.js)（search filter + split-pane visible on desktop）。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 48 · FE-3 Monitor 頁）`。P1 / M。

49. ~~**Frontend UX Overhaul — FE-4：Settings 頁集中化**~~ — **2026-05-20 已交付（差距補完，沿用既有 `/settings`）**：規格的 `SettingsPage.jsx` 新檔與既有 [`pages/Settings.jsx`](data-verification-ui/src/pages/Settings.jsx) 重複；改在既有檔頂部新增 `settings-grid`（mobile 單欄、`min-width: 768px` 後 `grid-template-columns: repeat(3, 1fr)`），承載 FE-4 規格三大新增區段：① **Gate 通過率（近 7 天）** 走既有 `useQsrecStats(7)` → `GET /api/reports/qsrec-stats?days=7`，顯示 `pass_rate_pct` + total_days / degraded / fail；② **盤中輪詢頻率** 三檔（15s／45s／120s）+ 預設按鈕，狀態存 `localStorage["qs_terminal_poll_ms_override"]`，`aria-pressed` 對應 active；③ **Gate 失敗記錄（近 7 天）** 新 endpoint **`GET /api/gate-failures?days=7`**（[`api.py`](api.py)，讀 BQ `gate_failure_log` ORDER BY ts DESC LIMIT 20 + [`fixtures/gate_failure_log_fixture.json`](fixtures/gate_failure_log_fixture.json) fallback；`days` 1–30 邊界、回 `entries[]`／`count`／`source`），前端 [`useGateFailures`](data-verification-ui/src/hooks/useApi.js) hook，顯示前 5 row（timestamp / profile / blocking / warn / issues_preview）。[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 補 `/api/gate-failures` mock。**刻意未實作**：Telegram bot 連線狀態（無對應 endpoint，跳過避免假狀態）、新建模組路徑 `src/modules/settings/`（既有 `pages/Settings.jsx` 已是 canonical 路徑，避免分裂）。新增 [`tests/api/test_gate_failures_api.py`](tests/api/test_gate_failures_api.py)（3 案：default shape、fixture fallback、days bounds 422）、[`e2e/settings-page.spec.js`](data-verification-ui/e2e/settings-page.spec.js)（grid 渲染、80% 通過率、poll toggle persist／clear、2 個 mock gate failures row；桌面 1280px grid 3 欄）。驗證：`pytest tests/api/test_gate_failures_api.py` 3 passed；`cd data-verification-ui && npm run lint && npm run build` 綠；`npm run test:e2e` 全綠（75/75）。CHANGELOG **2026-05-20** `### API（/api/gate-failures）` + `### PWA（隊列 49 · FE-4 Settings 集中化差距補完）`。P2 / M。

    **FE-4（原規劃，保留備查）**：手機與桌面共用，桌面以 sections 並列，手機單欄堆疊 — 見 TODOS.md 本節。
    - 新增 [`data-verification-ui/src/modules/settings/pages/SettingsPage.jsx`](data-verification-ui/src/modules/settings/pages/SettingsPage.jsx)。
    - Status 區（唯讀）：Telegram Bot 連線狀態 / BQ 專案 / Gate 近 7 天通過率。
    - Toggle 區（儲存 localStorage）：推播通知（`WEB_PUSH_*`）/ 盤中輪詢頻率（15s/45s/120s）。
    - Gate 失敗記錄列表：`GET /api/gate-failures?days=7`；若此 endpoint 不存在，同步於 [`api.py`](api.py) 新增，讀 BQ `gate_failure_log`。
    - 桌面三欄 grid（`md:grid-cols-3`）：狀態 / 設定 / 記錄；手機單欄堆疊。
    - E2E：[`data-verification-ui/e2e/settings-page.spec.js`](data-verification-ui/e2e/settings-page.spec.js)（smoke：toggle renders + gate list visible）。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 49 · FE-4 Settings 集中化）` 與必要時 `### API（/api/gate-failures）`。P2 / M。

50. ~~**Frontend UX Overhaul — FE-5：Desktop Power Features（Command Bar + 鍵盤快捷鍵）**~~ — **2026-05-20 已交付（差距補完，沿用既有 `TerminalCommandBar`）**：規格的新 `CommandBar.jsx` 會與既有 [`components/TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx)（隊列 29 已含 `Cmd+K` 聚焦、symbol search → `/insights?symbol=…`、board route、RUN 節流）重複，且既有 Command Bar 是手機 + 桌面共用入口（移除會回退）；本切片改以 **鍵盤快捷鍵 registry** 與 **SideNav hint tooltip** 補差距：新增 [`hooks/useKeyboardShortcuts.js`](data-verification-ui/src/hooks/useKeyboardShortcuts.js)（chord：`G→B` 觀點 `/insights`、`G→M` 監控 `/portfolio?tab=monitor`、`G→S` 設定 `/settings`；1500ms 內第二鍵；輸入框／contenteditable 不攔截；`Ctrl/Meta/Alt` 不攔截；`window.innerWidth < 768` 早返不掛 listener，手機完全 no-op；任意非註冊鍵清除 armed 狀態），在 [`Shell.jsx`](data-verification-ui/src/app/layout/Shell.jsx) 掛一次全域 listener；[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) footer 補 `.side-nav__hint` 顯示 `⌘K · G B · G M · G S` kbd 鏈、`title` tooltip；[`index.css`](data-verification-ui/src/index.css) 補 `.side-nav__hint` + `kbd` 樣式。**刻意未實作**：規格的 Profile 快速切換／Gate log 快速查看（既有 `BriefProfileBar` 與 `GlobalGateBadge` 已分別提供入口，不再疊一份）、`/monitor?symbol=…` 路徑（沿用 FE-3 收斂的 `/portfolio?tab=monitor`、`/insights?symbol=` 為 symbol 詳情）、另立 `CommandBar.jsx`（與 TerminalCommandBar 重複）。新增 [`e2e/command-bar.spec.js`](data-verification-ui/e2e/command-bar.spec.js) 五案（1280px viewport）：`Cmd+K` 聚焦 Command Bar、`G→B` → `/insights`、`G→M` → `/portfolio?tab=monitor`、SideNav `side-nav-shortcut-hint` 顯示、輸入框內打 `GB` 不觸發跳轉。驗證：`cd data-verification-ui && npm run lint && npm run build` 綠；`npm run test:e2e` 全綠（80/80，含本次新增 5 案）。CHANGELOG **2026-05-20** `### PWA（隊列 50 · FE-5 Command Bar + Shortcuts 差距補完）`。P2 / M。

    **FE-5（原規劃，保留備查）**：桌面專屬體驗提升，手機不顯示 — 見 TODOS.md 本節。
    - 新增 [`data-verification-ui/src/components/CommandBar.jsx`](data-verification-ui/src/components/CommandBar.jsx)（`hidden md:block`）：`Cmd+K` 開啟，支援代號搜尋跳轉（`/monitor?symbol=NVDA`）、Profile 快速切換、Gate log 快速查看。
    - 鍵盤快捷鍵 registry（[`data-verification-ui/src/hooks/useKeyboardShortcuts.js`](data-verification-ui/src/hooks/useKeyboardShortcuts.js)）：`G B` → 日報、`G M` → 監控、`G S` → 設定（仿 GitHub / Linear 模式）。
    - [`data-verification-ui/src/app/layout/SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) 桌面版新增 keyboard hint tooltip（`⌘K`）。
    - 不影響手機：所有 event listener 在 `useEffect` 內加 `if (window.innerWidth < 768) return`。
    - E2E：[`data-verification-ui/e2e/command-bar.spec.js`](data-verification-ui/e2e/command-bar.spec.js)（desktop only：Cmd+K opens + symbol search navigates）。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 50 · FE-5 Command Bar + Shortcuts）`。P2 / M。

51. ~~**Frontend UX Overhaul — FE-6：Mobile 觸控優化 + PWA Polish + 跨裝置驗收**~~ — **2026-05-20 已交付（PWA polish 收尾）**：新增 [`components/OfflineBanner.jsx`](data-verification-ui/src/components/OfflineBanner.jsx) 共用組件（listen `online/offline` event，`navigator.onLine === false` 時渲染 `today-offline-banner`），分別掛入 [`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx)（每日戰報頁，`SymbolFocusBar` 後、`TickerStrip` 前）與 [`WatchlistMonitor.jsx`](data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx)（`watchlist-monitor-offline-banner`）；對齊 [`service-worker.js`](data-verification-ui/src/service-worker.js) `/api` NetworkOnly 策略。BottomNav `.nav-item.active .nav-icon { transform: scale(1.1) }` + label fade（opacity 0.85 → 1）動畫（[`index.css`](data-verification-ui/src/index.css)）。更新 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) **§4f「PWA 行動裝置 + 桌面體驗（FE-1～FE-6 收尾）」**驗收表，覆蓋 BottomNav／SideNav 共存、CSS 變數、Daily Brief 折疊 + Ticker + Gate badge、Watchlist Monitor + live 報價、Settings 集中化、桌面鍵盤捷徑、離線提示、BottomNav active 動畫、44px 觸控標準與對應 E2E 錨點。新增 [`e2e/offline-banner.spec.js`](data-verification-ui/e2e/offline-banner.spec.js) 兩案（mobile 375px 戰報頁 + `/portfolio?tab=monitor`，`context.setOffline(true)` 觸發 banner、`false` 收回）。**2026-05-20 NEXT-1 續補**：新增 [`e2e/touch-target.spec.js`](data-verification-ui/e2e/touch-target.spec.js) 量測 mobile/desktop Command Bar 與 shared monitor toggle ≥44px；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) 與 [`GlobalWatchlistDock.jsx`](data-verification-ui/src/components/GlobalWatchlistDock.jsx) 修正小屏 40px/36px 控制；`index.css` dead-CSS audit 僅做 scoped 搜尋，未刪大批全域 CSS。驗證：`cd data-verification-ui && npm run lint && npm run build` 綠；`npm run test:e2e` 全綠（84/84，含 NEXT-1 新增 2 案）。CHANGELOG **2026-05-20** `### PWA（隊列 51 · FE-6 PWA Polish + 離線橫幅 + 跨裝置驗收）` + `### Docs（BLOOMBERG_ALIGNMENT §4f）` + `### PWA（NEXT-1 · touch target sweep）`。P2 / M。

    **FE-6（原規劃，保留備查）**：對齊 [`DESIGN.md`](DESIGN.md) 的 44px 觸控標準，確保手機與桌面都通過 E2E — 見 TODOS.md 本節。
    - 全頁掃描 touch target < 44px 的可互動元素，補 `min-height: 44px`。
    - BottomTabBar active 狀態動畫（icon scale 1.1 + label fade）。
    - 離線橫幅：DailyBriefPage 與 MonitorPage 在 `navigator.onLine === false` 時顯示 `today-offline-banner`（對齊 [`data-verification-ui/src/service-worker.js`](data-verification-ui/src/service-worker.js) NetworkOnly /api 策略）。
    - [`data-verification-ui/src/index.css`](data-verification-ui/src/index.css) 清理 dead CSS（以 Find All References 確認無組件引用後移除）。
    - `cd data-verification-ui && npm run build && npm run test:e2e`（mobile 375px + desktop 1280px）全綠。
    - 更新 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) 「PWA 行動裝置 + 桌面體驗」驗收欄。
    - CHANGELOG 對齊：完成後寫入 `### PWA（隊列 51 · FE-6 Mobile 觸控 + PWA Polish）`。P2 / M。

---

<a id="terminal-post-mid-tier-t1-t5"></a>

## Terminal／戰情室 — 後中段路線（T1–T5，每切片對應檔案）

> **語意**：M1–M5 已交付（見上節與 [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)）。以下為 **持續 improve** 的建議切片；**不綁日曆天數**，以可 review 的 PR 為單位。完成後寫入 [`CHANGELOG.md`](CHANGELOG.md) 並更新本節或改「✓」。

### Phase T1 — 穩定與可觀測

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T1a** | 戰情室／Terminal **錯誤態矩陣**（重試、降級、避免輪詢風暴） | [`data-verification-ui/src/modules/insights/pages/InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)、[`data-verification-ui/src/hooks/useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx) |
| **T1b** | **觀測**：API 失敗率／延遲與 `data_provenance` 敘事對齊（文件或輕量 log） | [`api.py`](api.py)、[`war_room_stream.py`](war_room_stream.py)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`README.md`](README.md) |
| **T1c** | **E2E 擴面**：mock 多 ticker 或 `price_alignment` 分支（**2026-04-16**：Today **`aligned=false`** 橫幅 spec + mock `e2e_btc_misaligned`） | [`data-verification-ui/e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)、[`data-verification-ui/e2e/today-btc-mismatch-banner.spec.js`](data-verification-ui/e2e/today-btc-mismatch-banner.spec.js)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml) |

### Phase T2 — 資料與一致性（Bloomberg §6 口徑）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T2a** | **跨路由／跨來源**數字口徑寫入契約（何時以 snapshot OHLC、何時以 quote、何時 N/A） | [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| **T2b** | **`price_alignment.aligned === false`** 時 Today／Terminal **UI 提示**（非靜默） | [`symbol_snapshot_service.py`](symbol_snapshot_service.py)、[`data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/e2e/`](data-verification-ui/e2e/) |
| **T2c** | **Streamlit ↔ PWA** 同形 snapshot 路徑迴歸說明／輕測 | [`dashboard.py`](dashboard.py)、[`symbol_snapshot_service.py`](symbol_snapshot_service.py)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（`SYMBOL_SNAPSHOT_HTTP_BASE`）、[`README.md`](README.md) |

### Phase T3 — 互動與效率

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T3a** | **Workspace／關注**：匯入匯出、模板、快捷操作（產品定義內） | [`data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`data-verification-ui/src/context/SymbolFocusContext.jsx`](data-verification-ui/src/context/SymbolFocusContext.jsx)、[`data-verification-ui/src/components/SymbolFocusBar.jsx`](data-verification-ui/src/components/SymbolFocusBar.jsx) |
| **T3b** | **意圖表**：篩選、排序、欄位契約 | [`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`api.py`](api.py)（若需 query 參數）、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| **T3c** | **輪詢／快取**：減少重複 snapshot、調整 stale／interval | [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx`](data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（`VITE_TERMINAL_POLL_MS` 等） |

### Phase T4 — 通知與閉環（合規後）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T4a** | ~~**Web Push 分階 2**~~ **已交付（2026-04-15）**：Redis、VAPID、`pywebpush`、可選 BQ、管理 test-send | [`web_push_store.py`](web_push_store.py)、[`api.py`](api.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)、[`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql) |
| **T4b** | **通知事件語意**（與 war-room／gate  digest 對齊，避免噪音） | [`war_room_stream.py`](war_room_stream.py)、[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)、[`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)、[`bigquery_writer.py`](bigquery_writer.py)（若寫 BQ 訂閱／事件表） |

### Phase T5 — 與日報／意圖敘事閉環（長線）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T5a** | **report_links**／當日報告在 Terminal 的**可發現深連結** | [`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/pages/Report.jsx`](data-verification-ui/src/pages/Report.jsx)、[`api.py`](api.py)（`GET /api/reports/{date}`）、[`symbol_snapshot_service.py`](symbol_snapshot_service.py) |
| **T5b** | **意圖狀態 ↔ gate 失敗** 讀向索引（僅讀、不冒充 OMS） | [`execution_intents.py`](execution_intents.py)、`GET /api/execution-intents/gate-index`（[`api.py`](api.py)）、[`tests/api/test_gate_intent_index_api.py`](tests/api/test_gate_intent_index_api.py)、[`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md) |

**建議執行順序**（**主線**須依序；**並線**＝文件／規格可與主線平行；**交錯**＝不阻塞主線 PR 的穿插切片）：

| 類型 | 說明 |
|------|------|
| **主線** | **T1** 完成（T1a／T1b／T1c 同 Phase 內可交錯 PR）→ **T2** → **T3**。 |
| **並線** | **T4** 的規格／合規 checklist／事件語意（文件為主）可自 **T1 起**與主線**並行撰寫**；**T4 實作**（訂閱持久化、真推送等）須待**合規／產品拍板**，建議排在 **T3 之後**，或與 **T5b** 同波若觀測已就緒。 |
| **交錯** | **T5** 與 **T2–T4** 可穿插：**T5a**（報告深連結）宜在 **T2a**（數字口徑契約）之後或與 T2a 同一波交付；**T5b**（gate × 意圖讀向）宜在 **T1b**（觀測）與 **T4b**（通知語意草案）有初稿後再做，與 **T3** 無衝突時可並行。 |

**一句話**：先 **穩 UI／觀測（T1）**，再 **定口徑與測試（T2）**，再做 **互動與效能（T3）**；**推送（T4）** 規格早開、實作晚合；**日報閉環（T5）** 對齊契約後交錯落地。

> **2026-04-14 進度備註（非 exhaustive）**：T1a／T1b／T1c、T2a／T2b／T2c、T3a／T3b／T3c 已有**可 review 初版**（見上「已交付摘要」列與 CHANGELOG）；**T4a 程式碼**已齊（**2026-04-15** CHANGELOG）；**T4b** 仍為事件語意草案（digest／排程須產品拍板）；**mock** 下已補 **NVDA** E2E；**2026-04-16** 補 **Today BTC `price_alignment` 分歧** Playwright（`today-btc-mismatch-banner`）；**實盤** 對照請跑 [`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py) 並可選 **`PRICE_PROBE_WRITE_BQ`** 寫入觀測表。
>
> **2026-04-21 更新**：**T1a** 已補齊「首次失敗 vs 背景 refetch 失敗」差異行為，Today／War Room／Terminal／ExecutionIntents 皆改為**已有成功資料時保留內容、只加 degraded banner + retry**；**T1c** mock API／Playwright 已擴到 **snapshot fail**／**quote fail**／**`aligned=null`**／**多 ticker 單卡失敗**；**T2b** Today BTC strip 與 Terminal 卡的 **`price_alignment`** 文案已收斂為 **一致 / mismatch / N/A（後端未確認）** 三態。後續主線集中在 **T1b / T2a / T2c** 的觀測與契約補齊。
>
> **同日補充**：`T1b` 已補 `/api/*` request log、`elapsed_ms`、`price_alignment` 三態與 `data_provenance` 的觀測說明；`T2a/T2c` 已補 **Streamlit ↔ PWA 同形約束**，並新增 `dashboard/snapshot_payload.py` + [`test_dashboard_snapshot_payload.py`](test_dashboard_snapshot_payload.py) 作為 `SYMBOL_SNAPSHOT_HTTP_BASE` / `build_symbol_snapshot` 雙路徑回歸錨點。下一步主線可往 **T2c 實盤對照** 或 **T3b 意圖表欄位契約** 繼續推。
>
> **同日再補**：`T3b` 已補 execution-intents **欄位契約**：後端 list / patch 皆固定回傳 blotter shape（含 `status_updated_at`、`thesis_one_liner`、`reference_*`、`paper_*`、`gate_issue_hints` 空陣列預設），前端 [`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx) 也已顯示 **category / regime / updated_at / thesis / paper fill/exit**。
>
> **T3c 續補（2026-04-21）**：輪詢 / 快取已進一步收斂到 **query sync policy**：[`useApi.js`](data-verification-ui/src/hooks/useApi.js) 將 Terminal live query 的 `staleTime`／`refetchInterval`／retry 策略抽成共用 helper；`PATCH /api/execution-intents/{signal_id}` 成功時先寫回 react-query cache，再只讓**活躍**的 `execution-intents`／`war-room` 即時 refetch，`metrics/latest`／`report`／`positions/open` 改為 **mark stale only**。[`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js) 則改成 **message 節流刷新、error 不觸發全頁 invalidate**，避免 SSE 斷線或 burst 事件造成 Today / Terminal 重複重抓。下一步主線可往 **T5b gate × intent 讀向索引** 前進。

---

## 長期與需拍板（索引，不在此逐條實作）

| 區塊 | 說明與文件 |
|------|------------|
| **波次 A–C** | 閾值、Critical env、Gate 人審、自適應門檻 — 上列隊列 **1–4** 已覆蓋主軸；其餘見 REPO_CONTINUATION_EXECUTION。 |
| **波次 D** | OSS HF／GraphQL、提案 Agent — [`Direction 2B`](#維護者意見執行順序不變)、[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)。 |
| **波次 E** | Company 四職能、War Room 深化、Web Push — [`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md)、[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。 |
| **波次 F — OSS 整合路線** | rtk／goose／fredapi、lightweight-charts、OMS／paper、回測管線 — **細項 checklist** 見 [`docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md`](docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md) 與 [演進藍圖](#演進藍圖精簡)（下節）；**非**全部已實作。 |
| **波次 G — 外部架構審閱 8 板塊** | 套件化、`pyproject.toml`、structlog／OTel、LLM Router、多語、Secret 託管、docker-compose.prod、Playwright、LangSmith 等 — **完整原表**已自本檔移除以避免重複；若要恢復長表請自 **git history** `TODOS.md` @ `4da94f7` 前後摘回或另開 `docs/TODOS_ARCHIVE_G_BLOCKS.md`（維護者決定）。 |
| **演進藍圖（精簡）** | Mock／Plugin 深化、Execution Layer、Intraday V2、LangGraph **完整**取代 Crew（目前 **部分**）、RAG「Chat with the Report」、語音晨報 — 詳見 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) § roadmap evolution、`graph/` 與 CHANGELOG **2026-04-09** 起。 |
| **階段 E 商業化** | Firebase、Stripe、多租戶 Telegram 等 — **暫緩**；見 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)、[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)。 |
| **真 OMS／RAG** | 獨立 daemon、intent 輪詢、錨定當日內文 RAG — 合規與產品表態後；見 [`execution_intents.py`](execution_intents.py)、`.qsilicon/execution_intents.jsonl` 現況。 |

<a id="演進藍圖精簡"></a>

### 演進藍圖（與 OSS 路線對照）

- **Phase 1–2**：工具模組化 [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md)；戰情室圖表見 OSS 訂閱取代研究稿 **Phase 2**。
- **Phase 3–4**：模擬盤、回測、聰明錢雷達 — **須**合規／ToS 評估；見研究稿 **Phase 3–4**。

---

## 新建議 backlog（精簡，與腳本對照）

<!-- CEO Review 2026-04-19: Q-Silicon Terminal plan -->
8. **Phase 0：`USE_LANGGRAPH_ENGINE` 預設改為 `1`** — 在 Reviewer Loop（Phase 2）落地前翻轉預設，使 reviewer gate 對主線管線生效。`main.py` + `ENV_TEMPLATE.txt`；`pytest -m smoke USE_LANGGRAPH_ENGINE=1` 必須全綠。P1 / S。
9. **api.py 端點合約測試** — Phase 3 APIRouter 拆分前，先為所有現有 `/api/*` 路由寫合約測試（request/response schema 斷言），確保 Streamlit 與 PWA 呼叫端在拆分後無靜默回歸。P2 / S。
10. **BQ `(date, profile)` composite index** — `llm_run_log` + `gate_failure_log` 的儀表板查詢熱路徑加複合索引；DDL 見 [`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)。P3 / S。
11. **Terminal portal httpOnly cookie 認證升級** — 目前 `QSILICON_MASTER_KEY` 存 localStorage（XSS 可讀），自用場景可接受；待多用戶部署決策後改為 httpOnly session cookie + `/api/auth/login`。P3 / M。依賴：多用戶產品決策。

1. Gate 內部儀表 — [`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)  
2. 結構化 dry-run — [`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)、[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)  
3. 美股備援觀測 — `EQUITY_BACKFILL_SCRATCHPAD_LOG`（見 CHANGELOG／`report_render`）  
4. Prompt 登記 — [`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)  
5. `asset_market` 展示規則 — [`schemas.py`](schemas.py)  
6. Mock smoke — [`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)  
7. 觀望 vs QSREC — [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)  

---

## OSS Scout 週報（自動）

> 每週搜尋 GitHub 熱門／指定 topic 之 repo；**適配理由、README 摘錄、低分說明**僅在當日研究稿與 JSON。**本節**只保留連結、摘要表與短勾選（避免 TODOS 被長標籤洗版）。詳稿：`docs/oss_candidates/YYYY-MM-DD-revision-plan-draft.md`。

- 每週產物：`docs/oss_candidates/YYYY-MM-DD-*.md` / `.json`；流程見 [`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)。
- **Spike 候選表**由週報 JSON 驅動；**不自動 merge** 至主程式。
- 區塊 **`OSS_SCOUT_AUTO_BEGIN` … `OSS_SCOUT_AUTO_END`** 由 [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 寫入 — **勿手改**。
- 執行：`python scripts/oss_weekly_pipeline.py`（需 `GITHUB_TOKEN`）；`OSS_WEEKLY_SKIP_TODOS=1` 可不寫入本節。

<!-- OSS_SCOUT_AUTO_BEGIN -->

### 2026-08-15

**本週 OSS 候選（2026-08-15）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-08-15-revision-plan-draft.md`](docs/oss_candidates/2026-08-15-revision-plan-draft.md)
- 機讀：[`2026-08-15-digest.json`](docs/oss_candidates/2026-08-15-digest.json)、[`2026-08-15-candidates.json`](docs/oss_candidates/2026-08-15-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 30239 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 30871 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 71867 |
| [`OpenByteInc/QuantDinger`](https://github.com/OpenByteInc/QuantDinger) | 5/5 · 建議優先評估 | 10684 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10566 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12185 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 18331 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 62903 |
| [`hummingbot/hummingbot`](https://github.com/hummingbot/hummingbot) | 5/5 · 建議優先評估 | 19466 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 10547 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 47418 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 13803 |
| [`stefan-jansen/machine-learning-for-trading`](https://github.com/stefan-jansen/machine-learning-for-trading) | 5/5 · 建議優先評估 | 20447 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 28773 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 13319 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `OpenByteInc/QuantDinger`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `hummingbot/hummingbot`
- [ ] `je-suis-tm/quant-trading`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `stefan-jansen/machine-learning-for-trading`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

### 2026-08-01

**本週 OSS 候選（2026-08-01）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-08-01-revision-plan-draft.md`](docs/oss_candidates/2026-08-01-revision-plan-draft.md)
- 機讀：[`2026-08-01-digest.json`](docs/oss_candidates/2026-08-01-digest.json)、[`2026-08-01-candidates.json`](docs/oss_candidates/2026-08-01-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 29384 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 29040 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 71244 |
| [`OpenByteInc/QuantDinger`](https://github.com/OpenByteInc/QuantDinger) | 5/5 · 建議優先評估 | 10161 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10446 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12158 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 18220 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 59730 |
| [`hummingbot/hummingbot`](https://github.com/hummingbot/hummingbot) | 5/5 · 建議優先評估 | 19291 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 10447 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 46901 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 13655 |
| [`stefan-jansen/machine-learning-for-trading`](https://github.com/stefan-jansen/machine-learning-for-trading) | 5/5 · 建議優先評估 | 20208 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 28357 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 11904 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `OpenByteInc/QuantDinger`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `hummingbot/hummingbot`
- [ ] `je-suis-tm/quant-trading`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `stefan-jansen/machine-learning-for-trading`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

### 2026-07-15

**本週 OSS 候選（2026-07-15）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-07-15-revision-plan-draft.md`](docs/oss_candidates/2026-07-15-revision-plan-draft.md)
- 機讀：[`2026-07-15-digest.json`](docs/oss_candidates/2026-07-15-digest.json)、[`2026-07-15-candidates.json`](docs/oss_candidates/2026-07-15-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 28439 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 23166 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 70590 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10332 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12123 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 18066 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 57284 |
| [`brokermr810/QuantDinger`](https://github.com/brokermr810/QuantDinger) | 5/5 · 建議優先評估 | 9618 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 10306 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 46252 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 13352 |
| [`stefan-jansen/machine-learning-for-trading`](https://github.com/stefan-jansen/machine-learning-for-trading) | 5/5 · 建議優先評估 | 19866 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 27868 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8688 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8554 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `brokermr810/QuantDinger`
- [ ] `je-suis-tm/quant-trading`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `stefan-jansen/machine-learning-for-trading`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

### 2026-07-01

**本週 OSS 候選（2026-07-01）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-07-01-revision-plan-draft.md`](docs/oss_candidates/2026-07-01-revision-plan-draft.md)
- 機讀：[`2026-07-01-digest.json`](docs/oss_candidates/2026-07-01-digest.json)、[`2026-07-01-candidates.json`](docs/oss_candidates/2026-07-01-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 27731 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 16068 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 69898 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10224 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12084 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 17901 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 52815 |
| [`brokermr810/QuantDinger`](https://github.com/brokermr810/QuantDinger) | 5/5 · 建議優先評估 | 9056 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 10225 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 45468 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 13190 |
| [`stefan-jansen/machine-learning-for-trading`](https://github.com/stefan-jansen/machine-learning-for-trading) | 5/5 · 建議優先評估 | 19464 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 27288 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8668 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8461 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `brokermr810/QuantDinger`
- [ ] `je-suis-tm/quant-trading`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `stefan-jansen/machine-learning-for-trading`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

---

### 2026-06-15

**本週 OSS 候選（2026-06-15）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-06-15-revision-plan-draft.md`](docs/oss_candidates/2026-06-15-revision-plan-draft.md)
- 機讀：[`2026-06-15-digest.json`](docs/oss_candidates/2026-06-15-digest.json)、[`2026-06-15-candidates.json`](docs/oss_candidates/2026-06-15-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 26802 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 12235 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 69183 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10117 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12038 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 17644 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 42601 |
| [`brokermr810/QuantDinger`](https://github.com/brokermr810/QuantDinger) | 5/5 · 建議優先評估 | 8051 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 10086 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 8045 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 44440 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12974 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 26784 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8646 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8371 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `brokermr810/QuantDinger`
- [ ] `je-suis-tm/quant-trading`
- [ ] `jesse-ai/jesse`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

---

---

### 2026-06-01

**本週 OSS 候選（2026-06-01）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-06-01-revision-plan-draft.md`](docs/oss_candidates/2026-06-01-revision-plan-draft.md)
- 機讀：[`2026-06-01-digest.json`](docs/oss_candidates/2026-06-01-digest.json)、[`2026-06-01-candidates.json`](docs/oss_candidates/2026-06-01-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 24886 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 9261 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 68364 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 10024 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 12006 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 17506 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 39722 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 9975 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 7968 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 43861 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12809 |
| [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | 5/5 · 建議優先評估 | 7739 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 26524 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8577 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8287 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `je-suis-tm/quant-trading`
- [ ] `jesse-ai/jesse`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `polakowo/vectorbt`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

---

---

---

### 2026-05-15

**本週 OSS 候選（2026-05-15）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-05-15-revision-plan-draft.md`](docs/oss_candidates/2026-05-15-revision-plan-draft.md)
- 機讀：[`2026-05-15-digest.json`](docs/oss_candidates/2026-05-15-digest.json)、[`2026-05-15-candidates.json`](docs/oss_candidates/2026-05-15-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 21176 |
| [`HKUDS/Vibe-Trading`](https://github.com/HKUDS/Vibe-Trading) | 5/5 · 建議優先評估 | 7353 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 67594 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 9933 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 11956 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 17340 |
| [`ZhuLinsen/daily_stock_analysis`](https://github.com/ZhuLinsen/daily_stock_analysis) | 5/5 · 建議優先評估 | 35978 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 9852 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 7890 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 42942 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12577 |
| [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | 5/5 · 建議優先評估 | 7543 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 26215 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8551 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8184 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `HKUDS/Vibe-Trading`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `ZhuLinsen/daily_stock_analysis`
- [ ] `je-suis-tm/quant-trading`
- [ ] `jesse-ai/jesse`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `polakowo/vectorbt`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

---

---

---

---

### 2026-05-01

**本週 OSS 候選（2026-05-01）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-05-01-revision-plan-draft.md`](docs/oss_candidates/2026-05-01-revision-plan-draft.md)
- 機讀：[`2026-05-01-digest.json`](docs/oss_candidates/2026-05-01-digest.json)、[`2026-05-01-candidates.json`](docs/oss_candidates/2026-05-01-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`Fincept-Corporation/FinceptTerminal`](https://github.com/Fincept-Corporation/FinceptTerminal) | 5/5 · 建議優先評估 | 18433 |
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 66818 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 9820 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 11921 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 17156 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 9760 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 7827 |
| [`lballabio/QuantLib`](https://github.com/lballabio/QuantLib) | 5/5 · 建議優先評估 | 7085 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 41657 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12455 |
| [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | 5/5 · 建議優先評估 | 7327 |
| [`ranaroussi/quantstats`](https://github.com/ranaroussi/quantstats) | 5/5 · 建議優先評估 | 7052 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 25930 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8534 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 8076 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `Fincept-Corporation/FinceptTerminal`
- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `je-suis-tm/quant-trading`
- [ ] `jesse-ai/jesse`
- [ ] `lballabio/QuantLib`
- [ ] `microsoft/qlib`
- [ ] `myhhub/stock`
- [ ] `polakowo/vectorbt`
- [ ] `ranaroussi/quantstats`
- [ ] `wilsonfreitas/awesome-quant`
- [ ] `firmai/financial-machine-learning`
- [ ] `paperswithbacktest/awesome-systematic-trading`


---

---

---

---

---

---

---

---

<!-- OSS_SCOUT_AUTO_END -->

---

## 修訂紀錄

- **2026-09-05（ITER-GO-LIVE-001）**：`GET /healthz` 廉價 liveness + 正式上線三條／Job≠Service／503 事實寫入 checklist。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-09-05** `### API/Ops（ITER-GO-LIVE-001）`。
- **2026-09-05（ITER-TR-LOOP-001）**：今日建議首屏「紙上對帳」（已解析標的 × 既有紙上／已結 API）。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-09-05** `### PWA（ITER-TR-LOOP-001）`。
- **2026-09-05（ITER-TR-AUDIT-001）**：實績頁紙上可審計摘要（期間／as_of／樣本／source、納入規則、上期追蹤 UNKNOWN-or-證據）。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-09-05** `### PWA/API（ITER-TR-AUDIT-001）`。
- **2026-08-30（隊列 44 · ITER-P4-44A）**：`/insights` 第一屏改為今日建議；工作台說明／CTA／資料健康摺疊。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-08-30** `### PWA（隊列 44 · ITER-P4-44A）`。
- **2026-08-15（Portal Vercel harden）**：[`vercel.json`](data-verification-ui/vercel.json) 停掉 `main` Git 自動 production；env／SSO 契約寫入 [`PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md) 與 README。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-08-15** `### Ops（Portal Vercel harden）`。
- **2026-05-20（Session 總表 · 隊列 57–71）**：補 [Session 總執行順序](#session-2026-05-20-execution-order)（工作流優先、不採付費訂閱）；CODEX **NEXT-1～5** 入列 **57–61**；工作流 **62–64**、閉環 **65–67**、研究／Gate **68–70**、規劃 **71**（design spec + writing-plans）。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-20** `### Docs（Session 總表 · 隊列 57–71）`。

- **2026-05-20（免費資料擴充 · 隊列 52–56）**：不採 Glassnode／CryptoQuant／TrendForce 付費訂閱；新增 [§ 免費資料擴充](#free-data-expansion-queue-52)（Phase F0→FA→FB→FC→FD 對應軸 A/B/C/D）與隊列 52–56；隊列 45 付費 live backlog 改「刻意延後」。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-20** `### Docs（免費資料擴充路線）`。

- **2026-05-17（Terminal Master Plan §3 對帳 · 純文件）**：[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 新增／補強 **§3 前端尚缺方向** 與 Portal ship 後 `CHANGELOG`／本檔對帳儀式；本檔檔首同步狀態新增 2026-05-17 對帳行，避免 §3 成為第二份 backlog。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-17** `### Docs（Terminal Master Plan §3 前端缺口盤點）`。
- **2026-05-17（隊列 26 · route-level lazy）**：[`PortalRoutes.jsx`](data-verification-ui/src/app/routes/PortalRoutes.jsx) 以 `React.lazy`+`Suspense` 分拆各路由頁；主入口 chunk 縮小、build 單檔 ~500 kB 警告已消除；`InsightsHome` 仍為最大 async chunk。`npm run lint`／`build`／`test:e2e`（65/65）綠。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-17** 隊列 26 小節；[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) §3.2／§3.6／修訂紀錄。
- **2026-05-17（隊列 26 · Router 抽出／邊界補強；隊列 29 · Command Bar 說明）**：[`App.jsx`](data-verification-ui/src/App.jsx) 只保留全域 providers 與 Router wiring；route table、legacy redirects、`SymbolQuerySync`、chrome 包裝移至 [`PortalRoutes.jsx`](data-verification-ui/src/app/routes/PortalRoutes.jsx)。[`eslint.config.js`](data-verification-ui/eslint.config.js) 擴大 `src/modules/*` 邊界清單；[`briefs-alias-route.spec.js`](data-verification-ui/e2e/briefs-alias-route.spec.js) 補 `/` redirect smoke；[`TerminalCommandBar.jsx`](data-verification-ui/src/components/TerminalCommandBar.jsx) 補 inline help，對齊 ADR 權限邊界且不新增 W 類後端指令。`npm run lint`、`npm run build`、`npm run test:e2e`（65/65）綠。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-17** `### PWA（隊列 26 · Router 抽出）`、`### PWA（隊列 29 · Command Bar 權限說明）`。
- **2026-05-16（CI — `pwa-deploy` setup-node 快取）**：根 `.gitignore` 之 `*.json` 曾排除 `data-verification-ui/package-lock.json`，GitHub Actions `cache-dependency-path` 無法解析；已加 `!data-verification-ui/package-lock.json` 並提交 lockfile。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16**「### CI（`pwa-deploy` — `setup-node` npm 快取）」。
- **2026-05-16（DESIGN — Phase 4 讀者層細節補齊 · 純文件）**：[`DESIGN.md`](DESIGN.md) 增 **「Portal Phase 4」**（首屏視線 ASCII、`?focus=` 四態、90s 產品腳本、Command Bar placeholder 策略、CTA／`PORTAL_PHASE4_CTA`、Skip link P2）；[`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) Phase 4 工程表增「設計契約」列；隊列 44 文件錨點與第 44 條「仍待」對齊人測簽名 vs 已入庫腳本。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### Docs（Portal Phase 4 — DESIGN.md 讀者層細節補齊）`。
- **2026-05-16（隊列 45 · P4／P5-mock — 翻譯短評層 + Crypto on-chain）**：news router `commentary_zh/en` passthrough（零 LLM 呼叫）+ ColumnsHome 中／EN toggle；`GET /api/macro/onchain` 讀 [`data/onchain_metrics_mock.json`](data/onchain_metrics_mock.json) 三區（BTC 估值／交易所淨流／永續資費）+ [`OnchainMetricsPanel.jsx`](data-verification-ui/src/components/OnchainMetricsPanel.jsx)；5 條 backend + 1 條 smoke + Playwright [`columns-bilingual.spec.js`](data-verification-ui/e2e/columns-bilingual.spec.js)／[`dashboard-onchain.spec.js`](data-verification-ui/e2e/dashboard-onchain.spec.js) 各 1/1 綠；完整回歸 16/16 + 38/38。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### Portal / API（隊列 45 · P4／P5-mock）`。
- **2026-05-16（隊列 45 · P2-mock — 算力／記憶體 dashboard）**：[`api_routers/macro.py`](api_routers/macro.py) 擴 `GET /api/macro/compute-memory`（讀 [`data/compute_memory_mock.json`](data/compute_memory_mock.json)；fixture/JSON 失敗回 enabled=false；`live` 需 fixture+`COMPUTE_MEMORY_LIVE=1` 雙條件）；[`ComputeMemoryPanel.jsx`](data-verification-ui/src/components/ComputeMemoryPanel.jsx) 掛 DashboardHome（HBM/DRAM／Capex／GPU spot 三區，mock badge + disclaimer）；6 條 backend tests + Playwright [`dashboard-compute-memory.spec.js`](data-verification-ui/e2e/dashboard-compute-memory.spec.js) 1/1 綠 + contract smoke 1 條。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### Portal / API（隊列 45 · P2-mock）`。
- **2026-05-16（隊列 45 · P1 — Portfolio TP/SL 計算機）**：[`PortfolioRiskPanel.jsx`](data-verification-ui/src/components/PortfolioRiskPanel.jsx) 掛 PortfolioHome；風險預算＝帳戶總值×% 持久化（`qsi_risk_budget_v1`）；ATR14 stop helper（純前端）；R:R／position size／notional／actual risk $；一鍵 PENDING_REVIEW；Playwright [`portfolio-tpsl.spec.js`](data-verification-ui/e2e/portfolio-tpsl.spec.js) 5/5 綠（含 ATR14；mock `/api/analysis/` 擴 OHLC 20 條）。後端零變更。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### PWA（隊列 45 · P1）`。
- **2026-05-16（隊列 45 · P3 — 財報 insight 專屬頁）**：新 [`api_routers/earnings.py`](api_routers/earnings.py) 兩條 read-only 端點（upcoming 1h cache、insight scaffold `enabled: false` 預設不偽造）；PWA [`EarningsInsightHome.jsx`](data-verification-ui/src/modules/insights/pages/EarningsInsightHome.jsx) + [`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 新 tab；hooks `useEarningsUpcoming` / `useEarningsInsight`；融合 CTA 重用 `portalPhase4.js`；tests 9 條 + contract smoke + Playwright 3 條全綠。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### Portal / API（隊列 45 · P3）`。
- **2026-05-16（Phase 4 收尾 · 純文件）**：[`TODOS.md`](TODOS.md) 隊列 44「Gate 0」段改為 ✅ 已簽核（五項決議鎖入表格、對應 `PORTAL_PHASE4_GATE0` 欄位）；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) 新增 **§4e Phase 4 IA 對 §4 驗收的影響**（#6–#15 勾帳 + Phase 4 IA 專屬驗收尺）。**剩餘**：44b 進階收斂仍待維護者指定哪幾塊算「高密度」。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### Docs（Phase 4 收尾）`。
- **2026-05-16（SSE 安全收尾）**：[`sse_token.py`](sse_token.py) 短期 token（mint／verify／GC，TTL 10–600s clamp，預設 60s）+ **`POST /api/stream/token`**（預設 404；須 `API_STREAM_AUTH_KEY`）；[`api.py`](api.py) `_sse_auth_ok` 接受 `stream_token`；event_gen 加入 `SSE_MAX_EVENTS_PER_SEC` 滑動 1 秒視窗節流（超量 `event: throttled`）；[`tests/api/test_sse_token.py`](tests/api/test_sse_token.py) + contract smoke `POST /api/stream/token` 404 斷言；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 補兩條變數。Phase 3 backlog（SSE token TTL／顯式限流）正式關帳；見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16** `### SSE 安全強化`。
- **2026-05-16（續 ②）— 44c 融合層**：[`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js) 新增 `PORTAL_PHASE4_CTA` 文案表 + `newsContextHref`／`columnsContextHref`／`ctaWithSymbol`、`fusionDirection=bidirectional`；[`InsightsHome.jsx`](data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) 反向 CTA；[`SymbolDeepDive.jsx`](data-verification-ui/src/modules/insights/pages/SymbolDeepDive.jsx) 雙向 CTA（`?focus={SYM}`）；[`NewsHome.jsx`](data-verification-ui/src/modules/news/pages/NewsHome.jsx)／[`ColumnsHome.jsx`](data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx) `?focus=` 過濾 + focus badge；E2E [`phase4-ia-portal.spec.js`](data-verification-ui/e2e/phase4-ia-portal.spec.js) 擴充 44c。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16**「### PWA（隊列 44 · 44c）」。
- **2026-05-16（續）**：隊列 **44** repo 首波 — [`portalPhase4.js`](data-verification-ui/src/constants/portalPhase4.js)、讀者／工作台導引條、Command Bar placeholder 分路、Playwright **`phase4-ia-portal.spec.js`**；見 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-16**「### PWA（隊列 44）」。
- **2026-05-16**：**`Terminal_Master_Plan` §0 Phase 4 實作規劃**（44a–44d、`TODOS` 隊列 44 專節）；**`TERMINAL_FRONTEND_PLAN` § Phase 4 IA**；**`CLAUDE.md`** 架構索引改 **Phase 0–4**；[`CHANGELOG.md`](CHANGELOG.md) **2026-05-16**。
- **2026-05-15**：**`Terminal_Master_Plan` §0 Phase 4** — 讀者層×工作台層 IA 收斂入檔；本檔檔首補交叉引用；[`CHANGELOG.md`](CHANGELOG.md) **2026-05-15** `### Docs`。
- **2026-05-14**：**隊列 28d MVP／34 workspace drag／29 Command Bar 快捷／Reviewer env 自檢／合約測試起點／隊列 36 E2E 全綠／T5b gate-index** — 見上「同步狀態（2026-05-14）」與 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-14** `### Portal / API`；「已交付摘要」列 **Queue 28d + … + Queue 36 E2E + T5b**。**續**：**Portal 架構 Phase 2**（Crew HUD、`workspaceSync` 跨分頁、Playwright）— `CHANGELOG`「PWA — Portal Phase 2」、[`README.md`](README.md) 導覽小節、`Terminal_Master_Plan` §0 Phase 2；「已交付摘要」列 **Portal Phase 2 產品切片**。
- **2026-05-13（八）**：**隊列 42–43 repo 側落地** — 科技專欄 Deep Brief list API、`/columns` 三支柱 UI、Command Bar 5 板塊跳轉 + symbol deep-link、shared Watchlist dock、JSONL price alert queue、terminal theme 與 Playwright smoke；同步 README／DASHBOARD_CONTRACT／ENV_TEMPLATE；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Columns + Cross-board Terminal`。
- **2026-05-13（七）**：**隊列 42–43 續作安排** — 本次僅更新 [`TODOS.md`](TODOS.md)，將下一輪拆成 **42a Deep Brief API contract**、**42b Columns UI**、**42c tests/docs**，以及 **43a Command Bar**、**43b Watchlist + Push Alert**、**43c Mobile density + terminal theme**；下一個 implementation target 為 **42a**，紅線維持不碰日報 pipeline／graph／Telegram、不新增未審核資料源、不自動下單。
- **2026-05-13（六）**：**Graph Reviewer／War Room telemetry 落地** — pre-reviewer market allowlist gate、reviewer yfinance ground-truth block、`node_complete` v1 SSE envelope、PWA Pipeline 終端；同步 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Graph Reviewer / War Room Telemetry` 與 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) SSE 契約。
- **2026-05-13（五）**：**隊列 41 repo 側落地** — Track Record v1（summary/closed/by-tag API、paper-only source-audited rows、optional recommendation_outcomes BQ sink、PWA `/insights` Track Record tab、Playwright smoke）；同步 README／DASHBOARD_CONTRACT；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Track Record`。
- **2026-05-13（四）**：**隊列 40 repo 側落地** — Tech News v1（Firestore digest/deep/themes API、來源缺失 item 過濾、PWA `/news` filter + source + side panel、Playwright `/news` smoke）；同步 README／DASHBOARD_CONTRACT；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Tech News`。
- **2026-05-13（三）**：**隊列 39 repo 側落地** — Macro Dashboard v1（`/api/macro/snapshot`、8 指標、60s cache、Catalyst Calendar、Regime breakdown、Sparkline、Playwright `/dashboard` smoke）；同步 README／DASHBOARD_CONTRACT；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Macro Dashboard`。
- **2026-05-13（二）**：**隊列 38 repo 側落地** — JSONL-backed Portfolio Tracker v1（CRUD、CSV import、P&L enrichment）、PWA `/portfolio` KPI + holdings UI + localStorage Watchlist、E2E mock/spec 與 API tests；同步 README／DASHBOARD_CONTRACT；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### Portfolio Tracker`。
- **2026-05-13**：**隊列 37 repo 側落地** — PWA route contract 收斂為 `/news`、`/dashboard`、`/insights`、`/columns`、`/portfolio`；`/briefs`／`/terminal` 相容 redirect；導覽、lint 模組邊界與 Playwright routes 同步；新增 `five-routes-smoke.spec.js`。對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-13** `### PWA`／`### Tests`。
- **2026-05-12**：**5 板塊 Tech Terminal 計畫入列「下一批隊列」** — 隊列新增 **37 Phase 0 路由整合**（刪 `/today`／`/archive`／`/charts`／`/trades`、5 板塊空框架）、**38 Portfolio Tracker**（手動 + CSV，JSONL storage，P&L MTM）、**39 數據儀表板**（`api_routers/macro.py`、8 指標 Sparkline）、**40 科技即時報**（tech-pulse Firestore 接線，`api_routers/news.py`）、**41 投資觀點 + Track Record**（`track_record.py`、夜間 mark-to-market job、`recommendation_outcomes` BQ）、**42 科技專欄**（Deep Brief pillar UI）、**43 跨板塊完善**（Command Bar、Watchlist、Push Alert、手機密度、terminal.css 主題）；隊列 26（原五模組化）、28（Roadmap）、29–34（Portal Phase 2–3）保留，隊列 37–43 為其後繼實作載體，重新對齊「5 板塊」用語模型；計畫全文見 [`docs/architecture/Terminal_Frontend_v2.md`](docs/architecture/Terminal_Frontend_v2.md)（待建）；tech-pulse repo 側合約文件見下方 tech-pulse TODO 區段。**紅線**：不接未審核付費資料源、不自動下單、不承諾收益、來源顯示強制（無幻覺原則）。
- **2026-05-07**：**Q-Silicon Terminal 12 週 Roadmap 入列「下一批隊列」** — 隊列新增 **29 Portal Phase 2**（Command Bar + SSE Quote）、**30 M4 Position Management**、**31 M5 Industry Trends**、**32 M6 Investment Analysis**、**33 M7 Quant Trading**、**34 Portal Phase 3**（多視窗 + Alert + 個人化）；願景對齊 [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) + [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)；本次僅文件，不入「已交付摘要」；紅線：不接未審核付費資料源、不自動下單、不承諾收益。
- **2026-05-02**：**12 週投資價值優化 Roadmap 文件對齊（尚未實作）** — [`README.md`](README.md) 新增「個人化投資決策夥伴 Roadmap」規劃說明；本檔「下一批隊列」新增 **28**（28a–28d：paper P&L、quality-adjusted scoring、monthly transparency / portfolio alignment、scenario / optimizer / beta launch）。本次僅同步 roadmap，不放入「已交付摘要」；公開績效仍須 paper-only、可審計，且不得弱化 `validate_report`、Telegram HTML 白名單與無數據幻覺紅線。對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-05-02** `### Docs`。
- **2026-04-21（Reviewer Loop）**：**LangGraph Phase 3.5 reviewer loop 已交付** — [`graph/graph_state.py`](graph/graph_state.py)、[`graph/graph_nodes.py`](graph/graph_nodes.py)、[`graph/graph_crew.py`](graph/graph_crew.py)、[`bigquery_writer.py`](bigquery_writer.py)、[`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`test_reviewer_loop.py`](test_reviewer_loop.py)；「已交付摘要」新增列，隊列 **23** 改 ~~刪線~~；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-21** `### Changed`／`### Tests`。
- **2026-04-20**：**`docs/architecture/` 研究稿入列「下一批隊列」** — 隊列新增 **23 Reviewer Loop**（[`REVIEWER_LOOP_DESIGN.md`](docs/architecture/REVIEWER_LOOP_DESIGN.md)）、**24 NotebookLM**（[`notebooklm_research.md`](docs/architecture/notebooklm_research.md) v1.1）、**25 Agency Agents**（[`agency_agents_research.md`](docs/architecture/agency_agents_research.md) v1.0）、**26 Terminal Frontend Portal 五模組化**（[`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md)）、**27 視覺化剩餘 backlog V2／V4／V5／V6**（[`visualization_plan.md`](docs/architecture/visualization_plan.md)）。優先序 Reviewer Loop → NotebookLM → Agency Agents（技術依賴鏈：後兩者共用 `python_validate_node` citation 檢查）。[`AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md) 為 context load 文件、[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 為總表索引，不入隊列（已由 [§ AI／架構文件看法](#ai-architecture-views) 引用）。
- **2026-04-18（六）**：**Terminal 總表與架構看法** — 新增 [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md)；[`docs/architecture/`](docs/architecture/)（`AI_CONTEXT`、`REVIEWER_LOOP_DESIGN`、`TERMINAL_FRONTEND_PLAN`）；本檔 [§ AI／架構文件看法](#ai-architecture-views)、導覽列 **Terminal 總表**；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`CLAUDE.md`](CLAUDE.md)、[`.cursorrules`](.cursorrules)；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Docs`；[`README.md`](README.md) 連結表。
- **2026-04-18（五）**：**視覺化計畫 Phase 6／7（PWA 保守離線 + Streamlit 戰情室 v4）** — [`data-verification-ui/src/service-worker.js`](data-verification-ui/src/service-worker.js)、[`docs/PWA_OFFLINE.md`](docs/PWA_OFFLINE.md)；[`dashboard/theme.py`](dashboard/theme.py)、[`dashboard.py`](dashboard.py)；「已交付摘要」新增列；**同步狀態**一句；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Added` **前二條**；[`README.md`](README.md) 戰情室表格／War Room／文件索引。
- **2026-04-18（四）**：**PWA 視覺化 V2（結構化本文原生渲染）** — [`structuredBlockContent.js`](data-verification-ui/src/components/report/structuredBlockContent.js)（**`DailyBriefReport`** → 區塊 **`kind`**）、[`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx)；「已交付摘要」**V2／V3 前置**列更新；**同步狀態**補 **2026-04-18** 一句；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Changed` **第二條**；[`README.md`](README.md) War Room 節補 **結構化日報**小節。
- **2026-04-18（三）**：**視覺化計劃延續（V2 錨點／AsOf + V3 前置）** — **`GET /api/brief-layouts`**、[`test_brief_layouts_api.py`](test_brief_layouts_api.py)；[`useBriefLayouts`](data-verification-ui/src/hooks/useApi.js)、[`BriefProfileBar`](data-verification-ui/src/components/report/BriefProfileBar.jsx)、[`reportProfiles.js`](data-verification-ui/src/components/report/reportProfiles.js)、[`StructuredReportView`](data-verification-ui/src/components/report/StructuredReportView.jsx) **`#block-*`**／**`AsOfChip`**、[`Report.jsx`](data-verification-ui/src/pages/Report.jsx) **`?profile=`**；「已交付摘要」**V2** 列改 **V2／V3 前置**；[`visualization_plan.md`](docs/architecture/visualization_plan.md)、[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Added`（合併條目）。
- **2026-04-18（二）**：**PWA 視覺化 V2 首批** — [`api.py`](api.py) `GET /api/reports/{date}/structured`、[`test_report_structured_api.py`](test_report_structured_api.py)；[`useStructuredReport`](data-verification-ui/src/hooks/useApi.js)、[`StructuredReportView`](data-verification-ui/src/components/report/StructuredReportView.jsx)、**`VITE_STRUCTURED_REPORT`**；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`visualization_plan.md`](docs/architecture/visualization_plan.md) V2 進度；「已交付摘要」增 **V2** 列；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Added`。
- **2026-04-18**：**CI Node 24** — [`.github/workflows/ci.yml`](.github/workflows/ci.yml)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml) `actions/setup-node@v5`、`node-version: "24"`；「已交付摘要」Terminal 契約列補述；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-18** `### Changed`。
- **2026-04-27（六）**：**日報模組化 Phase 5 完整切片 + 4d 動態組版** — [`current_affairs_crew.py`](current_affairs_crew.py)、[`main.py`](main.py)、[`report_render.py`](report_render.py)、[`report_html_gates.py`](report_html_gates.py)、[`schemas.py`](schemas.py)、[`config/brief_layouts/README.md`](config/brief_layouts/README.md)、[`example_full_reorder_header_exec.yaml`](config/brief_layouts/example_full_reorder_header_exec.yaml)、[`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)、[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)；[`test_dynamic_full_render.py`](test_dynamic_full_render.py)；隊列 **22**（Phase 5 ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md)；[`README.md`](README.md)、[`CLAUDE.md`](CLAUDE.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **2026-04-27（五）**：**日報模組化 Phase 5（安全切片）** — [`schemas.py`](schemas.py)、[`report_render.py`](report_render.py)、[`templates/blocks/_current_affairs_roundtable.j2`](templates/blocks/_current_affairs_roundtable.j2)、[`templates/profiles/telegram_full.j2`](templates/profiles/telegram_full.j2)、[`brief_profiles.py`](brief_profiles.py)、[`report_html_gates.py`](report_html_gates.py)、[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；[`test_current_affairs_schema.py`](test_current_affairs_schema.py)、[`test_current_affairs_render.py`](test_current_affairs_render.py)；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md)；[`README.md`](README.md)。
- **2026-04-14（九）**：**日報模組化 Phase 4d** — [`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 4d 章節與進度表；[`validation_rules.py`](validation_rules.py)／[`report_html_gates.py`](report_html_gates.py) `_check_profile_block_consistency`；[`main.py`](main.py) `_validate_report_profile_env`；[`config/brief_layouts/README.md`](config/brief_layouts/README.md)、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_critical_paths.py`](test_critical_paths.py)；隊列 **22**（Phase 4d ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-14** `### Changed`。
- **2026-04-29**：**日報投資者可讀性清理** — [`report_render.py`](report_render.py)、[`main.py`](main.py)、[`schemas.py`](schemas.py)、[`templates/blocks/_ai_section.j2`](templates/blocks/_ai_section.j2)、[`crew.py`](crew.py)；Polymarket 預設關閉、AI 可交易雷達、【財報雷達｜未來 7 天】、區塊②b 去重；[`test_report_render.py`](test_report_render.py)、[`test_main_pipeline_boundaries.py`](test_main_pipeline_boundaries.py)；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-29**。
- **2026-04-16**：**日報模組化 Phase 4c** — [`bigquery_writer.py`](bigquery_writer.py) `write_llm_run_log`／`write_gate_failure_log` **`profile`**；[`main.py`](main.py)；[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)；[`test_llm_run_log.py`](test_llm_run_log.py)、[`test_gate_failure_log.py`](test_gate_failure_log.py)；隊列 **22**（Phase 4c ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-16** `### Changed`／`### Docs`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 4c；[`README.md`](README.md)／[`CLAUDE.md`](CLAUDE.md)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **2026-04-27（四）**：**日報模組化 Phase 4b** — [`brief_profiles_layout.py`](brief_profiles_layout.py)、[`brief_profiles.py`](brief_profiles.py)、[`config/brief_layouts/`](config/brief_layouts/)、[`test_brief_profiles_layout.py`](test_brief_profiles_layout.py)；`requirements.txt`／`requirements-ci.txt` PyYAML；隊列 **22**（Phase 4b ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 4b；[`README.md`](README.md)／[`CLAUDE.md`](CLAUDE.md)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **2026-04-27（三）**：**日報模組化 Phase 4a** — [`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2)、[`brief_profiles.py`](brief_profiles.py)、[`report_html_gates.py`](report_html_gates.py) `crypto-only`；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_brief_profiles.py`](test_brief_profiles.py)；隊列 **22**（Phase 4a ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 4a；[`README.md`](README.md) 日報模組化節／模組表。
- **2026-04-16**：**README／TODOS／CHANGELOG 對齊補強** — [`README.md`](README.md)「日報模組化」節與 Phase 1–3 已落地現況一致；**同步狀態**括號日期與內文 **2026-04-27** 對齊；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Docs` 記載此修正。
- **2026-04-27（二）**：**日報 Gate Phase 3** — [`validate_report(..., profile=)`](report_html_gates.py)、[`main.py`](main.py)、[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)；隊列 **22**（Phase 3 ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 3；[`CLAUDE.md`](CLAUDE.md) Gate 小節。
- **2026-04-27**：**日報 Telegram Phase 2** — [`brief_profiles.py`](brief_profiles.py)、`REPORT_PROFILE`、`templates/profiles/`、`test_brief_profiles.py`；「同步狀態」「已交付摘要」、隊列 **22**（Phase 2 ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-27** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 2 切片註記已落地；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) `REPORT_PROFILE`。
- **2026-04-26（二）**：**日報 Telegram Phase 1** — `templates/blocks/`、`report_render` 共用 Jinja env／context、**byte-identical** smoke；「同步狀態」「已交付摘要」、隊列 **22**（Phase 1 ~~刪線~~）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-26** `### Changed`；[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 1 表補 **合併門檻**／`_footer_tail` 說明。
- **2026-04-26**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) 新增 **產品與交付原則**（過渡期／組織客製）；「同步狀態」與隊列 **22**、已交付摘要列對齊；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-26** `### Docs`。
- **2026-04-25**：**日報區塊模組化計畫** — [`modularization_plan.md`](docs/architecture/modularization_plan.md) 重排邏輯、五 Phase、短中長期；「已交付摘要」增列（**僅文件**）；「下一批隊列」增 **22**；[`README.md`](README.md) 連結表 + 小節；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-25** `### Docs`。**（續）** **`deploy.yml` `push.paths`** — 純 `.md`／文件 push **不**觸發自動 Deploy；手動 **Run workflow** 說明寫入 [`CLAUDE.md`](CLAUDE.md)、README、[`AGENTS.md`](AGENTS.md)、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)；CHANGELOG 同日 `### Docs` 增列。
- **2026-04-24**：**日報 Telegram 行動格式** — 「已交付摘要」更新 `report_render`／`report_quality_agent` 列；**同步狀態**一句；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-24** `### Changed`。
- **2026-04-16**：[`README.md`](README.md) 補 **日報品質代理**（`.env`：`REPORT_QUALITY_AGENT=1`、`REPORT_LLM_JUDGE_MODEL`／預設 **gpt-4o-mini**、`source .env`）；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-16** `### Docs`；本檔「已交付摘要」與**同步狀態**一句。
- **2026-04-15（二）**：新增 [git pull／讀 codebase 提醒](#pull-or-read-codebase-reminder) 與隊列 **18–21**（BQ DDL、Redis、VAPID、staging test-send）；[`CHANGELOG.md`](CHANGELOG.md) `### Docs`；[`CLAUDE.md`](CLAUDE.md) 導覽一句。
- **2026-04-15**：**T4a** — Redis、`pywebpush`、`POST /api/push/test-send`、可選 BQ persist／audit、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)；**實盤觀測** — [`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py) + [`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)；隊列 **11** ~~刪線~~；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-15**。
- **2026-04-14（八）**：**NVDA** mock 跨路由 Playwright；`price_alignment` 來源欄位 + `PRICE_ALIGNMENT_E2E_OVERRIDES`；Web Push **store 去重／IP rate limit**；`gate_issue_hints` **單字邊界**避免誤匹配。
- **2026-04-14（七）**：依建議順序 — **T1–T3** 主線首批落地（錯誤態／觀測 log／E2E 擴面）、**T2** 契約補 §4c、**T5a／T5b** 穿插（`report_links` 內部路由 + `gate_issue_hints`）；同步 CHANGELOG／`DASHBOARD_CONTRACT`／`ENV_TEMPLATE`／`PWA_WEB_PUSH`（T4b 草案）。
- **2026-04-14（六）**：T1–T5 區塊 — **建議執行順序**改為「主線／並線／交錯」表格與一句話總結（避免單句括號難讀）。
- **2026-04-14（五）**：新增 [Terminal／戰情室後中段路線（T1–T5）](#terminal-post-mid-tier-t1-t5) — 每切片對應主要檔案與建議執行順序；[`CHANGELOG.md`](CHANGELOG.md) `### Docs` 同步。
- **2026-04-14（四）**：**Playwright E2E** — 「下一批隊列」**12** ~~刪線~~；`SymbolCandleChart` lightweight-charts **v5**；`pwa-e2e` workflow；[`CHANGELOG.md`](CHANGELOG.md)／[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4b 補 UI 層。
- **2026-04-14（三）**：**可加強項落地** — snapshot **`price_alignment`**、deep metrics 細欄位、CI **npm cache**、Web Push **API／PWA 分階 1**；「下一批隊列」**10** 改 ~~分階 1~~ 並新增 **11–12**（分階 2、Playwright）；「已交付摘要」增列；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-14** 同日合併敘述；Bloomberg 錨點補 **snapshot price_alignment**。
- **2026-04-14（二）**：**Phase A–E 切片** — 「已交付摘要」增列；「下一批隊列」**1–9** ~~刪線~~；Bloomberg 進度表內部勾選 **12/15→13/15** 並註記條目 6／14 之 pytest／CI 錨點；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-14** `### Changed`／`### Docs`／`### Tests`。
- **2026-04-14**：**日報品質代理** — 「已交付摘要」增列；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-14** `### Added`；機器區塊標記 `<!-- REPORT_QUALITY_AGENT_TODOS_BEGIN/END -->`（低分時自動 bullet，**勿手改區塊內**；見 [`report_quality_agent.py`](report_quality_agent.py)）。
- **2026-04-12（二）**：新增 [進度分析表（華爾街級日報 · 財報週期 · Bloomberg 對齊）](#progress-vs-wall-st-bloomberg) — 維度粗評 1–5、Phase 0（15 條中 ≥12）錨點、建議內部 KPI；對齊 [`CHANGELOG.md`](CHANGELOG.md) 同日 `### Docs`。
- **2026-04-12（三）**：**Terminal 中段 M1** — 「已交付摘要」增列；「下一批隊列」增 **M2**；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** `### Added` 補 `data_provenance`、`execution-intents` API、[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引增該檔。
- **2026-04-12（四）**：[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md) 擴充 **M2–M5** 實作規格（DoD、檔案、API、測試、依賴圖、手動 checklist）；「下一批隊列」增 **M3–M5**、M2 補 roadmap 錨點；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** `### Docs` 合併敘述。
- **2026-04-12（五）**：**Terminal M2 PWA** — 「已交付摘要」增列；隊列 **12** 改 ~~刪線~~；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** 增 `### PWA`；README／`DASHBOARD_CONTRACT`／roadmap §3b 同步。
- **2026-04-12（六）**：**Terminal M3** — `GET /api/symbols/{symbol}/quote`、`fetch_symbol_quote`、`test_api_symbol_quote`、PWA `useSymbolQuote`／卡片頂欄；「已交付摘要」增列；隊列 **13** ~~刪線~~；CHANGELOG `### API（Terminal M3）`；roadmap §3c 標註已落地。
- **2026-04-12（七）**：**Terminal M4/M5** — SSE `GET /api/stream/war-room`、紙上 `paper_execution`／`POST /api/paper/execution-tick`／`scripts/paper_execution_tick.py`、意圖 `reference_*` 與 `PAPER_*` 狀態、PWA SSE／參考價欄；「已交付摘要」增列；隊列 **14–15** ~~刪線~~；CHANGELOG `### API（Terminal M4/M5）`；`ENV_TEMPLATE`／`DASHBOARD_CONTRACT`／roadmap §3d–3e。
- **2026-04-12（八）**：進度表 — Bloomberg **Phase 0 十五條內部勾選**（暫列 **12/15**、例外項見「硬指標錨點」）；「Terminal 式產品面」粗評 **2–3→3–4**／5；對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** `### Docs` 補登條。
- **2026-04-12**：「**已交付摘要**」補登兩列 — **日報組裝衛生**（`report_render`／`test_report_render`）與 **Crew／FD 規則**（`crew`、`tools_legacy`），對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-10** `### Pipeline`；**同步狀態**日期更新。[`CHANGELOG.md`](CHANGELOG.md) 增 **2026-04-12** `### Docs` 並於檔首明訂 **CHANGELOG ↔ TODOS** 維護契約；[`AGENTS.md`](AGENTS.md)、[`CLAUDE.md`](CLAUDE.md) 交接／導覽一句補強。另完成 Bloomberg 對齊首批落地（alignment doc、symbol snapshot API、PWA Terminal workspace、lightweight-charts K 線事件標註）。**後續小步**：`README` 補 **`/terminal`／`VITE_API_URL`**；`App.jsx` **`lazy`+`Suspense`** 載入 Terminal（CHANGELOG **2026-04-12** `### Changed`）。
- **2026-04-15（五／續）**：**日報 Opus 回饋落地** — `^GSPC`／Polymarket 關鍵字、Telegram 免責位移與 **🤖 區塊①**、crew HF／DXY 軟規則；「已交付摘要」增列；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-15** `### Added`／`### Changed`。
- **2026-04-23**：**全文改寫** — 宣告舊版「巨型可勾選 backlog」**未**等同全部實作；改為導覽 + **下一批隊列** + 長期索引；移除 G-1～G-8 全表與重複 Phase／OSS 細拆 checkbox（詳見 git 歷史）；OSS 週報契約與 `OSS_SCOUT_AUTO_*` 規則保留。
- **2026-04-22**：訂閱取代研究稿、CHANGELOG Docs — 見上「已交付摘要」連結。
- **2026-04-21 及更早**：見 git 歷史本檔與 [`CHANGELOG.md`](CHANGELOG.md)。
