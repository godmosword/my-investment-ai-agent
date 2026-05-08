# Changelog

本檔案記錄專案重要功能與行為變更。  
**工程待辦與完成度彙總**見 [`TODOS.md`](TODOS.md)。**維護契約（CHANGELOG ↔ TODOS）**：凡記入本檔之 **使用者可見／行為變更** 條目，**必須**同步更新 [`TODOS.md`](TODOS.md)（**已交付摘要**、**下一批隊列**、**修訂紀錄**）之對應敘述；若僅於 TODOS 補登「已交付」備查，**須**有本檔同日或既有日期區塊之條目支撐，避免兩檔脫節。

## 2026-05-08

### Fixed
- **PWA — Quant 頁與 execution_intents 契約對齊**：[`QuantHome.jsx`](data-verification-ui/src/modules/quant-trading/pages/QuantHome.jsx) 改用 **`paper_fill_price`／`paper_exit_price`**、狀態 **`PAPER_CLOSED`**（保留 `paper_entry`／`CLOSED`／`EXITED` 等別名）；**StatusPill** 補 **`PAPER_SUBMITTED`／`PAPER_FILLED`／`PAPER_CLOSED`**；摘要欄 **`thesis_one_liner`**。
- **PWA — War Room SSE 單一連線**：[`useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js) 改 **`WarRoomSseProvider`** + **`useWarRoomSseStatus`**（URL 含 **`VITE_SSE_STREAM_KEY`**）；[`App.jsx`](data-verification-ui/src/App.jsx) 掛載 Provider；**移除** [`WarRoomSseBridge.jsx`](data-verification-ui/src/components/WarRoomSseBridge.jsx)；[`SideNav.jsx`](data-verification-ui/src/app/layout/SideNav.jsx) **`SseDot`** 改讀 context（禁止第二條 `EventSource`）。
- **PWA — SymbolCandleChart 生命週期**：[`SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx) 於 OHLC 由空→有時可建圖；chart 建立依賴 **`hasPriceData`／`hasVolume`**；移除不當 eslint disable。
- **PWA — `.metrics-grid` cascade**：[`index.css`](data-verification-ui/src/index.css) 將 **mobile base** 置於 **`@media (min-width: 768px)`** 之前，避免桌面 **四欄** 被覆蓋。
- **Crew 結構化 JSON（尾隨逗號）**：[`crew_output_parse.py`](crew_output_parse.py) 新增 **`repair_llm_json_text`**，於 **`kickoff_to_pydantic`** 內 **`model_validate_json`／`json.loads` 前**迭代移除 `}`／`]` 前的非法尾隨逗號（RFC 8259 不允許、LLM 常見），避免 **`AISection`／`CryptoSection`** 解析失敗觸發 **`GATE_EXECUTION_FAILED`** 與 **`STRICT_CONSISTENCY_GATE`** 擋推送。
- **Crew kickoff 內建 pydantic 解析失敗**：[`crew_output_parse.py`](crew_output_parse.py) 新增 **`kickoff_with_structured_fallback`** — 當 **`crew.kickoff()`** 因 **`output_pydantic`** 路徑先拋 **`ValidationError`（json_invalid）`** 時，從例外鏈取出原始 JSON 字串，再走 **`repair_llm_json_text` + `parse_pydantic_from_llm_json_text`**。[`crew.py`](crew.py) **Crypto／AI** 日報 Crew 改為以此包 **`kickoff`**。
- **QSREC `direction` 漏填**：[`schemas.py`](schemas.py) 於 **`TradeRecommendation`** 解析前補 **`direction`**（常見別名欄位、`entry`／`target`／`stop` 幾何）；**`CryptoSection`／`AISection`** 另以 **`trade_legs`** 同資產方向回填 **`qsrec`**，避免生產 **`qsrec.0.direction Field required`** 使 **`CryptoSection.model_validate`** 失敗而觸發 **`GATE_EXECUTION_FAILED`**。

### Tests
- [`test_crew_output_parse.py`](test_crew_output_parse.py) — `repair_llm_json_text`、`kickoff_to_pydantic` 對尾隨逗號 JSON 之回歸；**`parse_pydantic_from_llm_json_text`**、**`kickoff_with_structured_fallback`**（成功路徑／`ValidationError` 自救／不可恢復時 re-raise）。
- [`test_trade_recommendation_schema.py`](test_trade_recommendation_schema.py) — **`direction`** 由價位／`side` 別名推斷；**`CryptoSection.model_validate`** 由 **`trade_legs`** 回填 **`qsrec`**。

## 2026-05-05

### PWA（視覺化隊列 27／Portal 隊列 26 切片）
- **結構化區塊可選 `data-section`**：[`BlockSectionShell.jsx`](data-verification-ui/src/components/report/blocks/BlockSectionShell.jsx) 支援 **`data-section={block_id}`**；[`MetricsDashboardBlock.jsx`](data-verification-ui/src/components/report/blocks/MetricsDashboardBlock.jsx)／[`CurrentAffairsRoundtableBlock.jsx`](data-verification-ui/src/components/report/blocks/CurrentAffairsRoundtableBlock.jsx) 接上；roundtable 主題加 **`data-testid="current-affairs-roundtable-topic"`**。
- **E2E mock**：[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 最小 **`daily_brief_report`** 補 **`crypto.dashboard`** 與根層 **`current_affairs_roundtable`**；[`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js) 斷言 `section[data-section="crypto_dashboard"]` 與 roundtable testid。
- **Today 離線提示**：[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 監聽 **`online`／`offline`**，離線時顯示 **`data-testid="today-offline-banner"`**。
- **倉位頁最小切片**：[`PositionsHome.jsx`](data-verification-ui/src/modules/position-management/pages/PositionsHome.jsx) 接 [`useExecutionIntents`](data-verification-ui/src/hooks/useApi.js) 表格 + **`data-testid="positions-home"`**；新增 [`positions-route.spec.js`](data-verification-ui/e2e/positions-route.spec.js)。

### API（隊列 28a）
- **Paper 稽核可選 BQ**：[`paper_execution.py`](paper_execution.py) 在 `append_execution_intent_row` 成功後呼叫 [`bigquery_writer.write_paper_execution_audit_row`](bigquery_writer.py)（`PAPER_EXECUTION_AUDIT_TABLE` 空則略過；`SKIP_BIGQUERY=1` 仍略過）；DDL 範本 [`docs/SQL/paper_execution_audit.sql`](docs/SQL/paper_execution_audit.sql)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 註解；[`test_paper_execution.py`](test_paper_execution.py)。

### Tests
- **NotebookLM Phase 0–1**：[`test_notebooklm_tool.py`](test_notebooklm_tool.py) — `NOTEBOOKLM_ENABLED=0`／stub 快取路徑。
- **`validate_report` fixture 與新聞新鮮度**：[`test_validate_report.py`](test_validate_report.py) 之 `_make_report`／`_make_minimal_structured_report_dbr` 改以 **動態 UTC+8 括號時間戳**（`_fresh_news_timestamp_bracket`），在 **`STRICT_NEWS_FRESHNESS_GATE=1`** 下仍通過整合測試。
- **Playwright**：[`positions-route.spec.js`](data-verification-ui/e2e/positions-route.spec.js) 以 **`getByRole('cell', { name: 'SPY', exact: true })`** 避免與 intent id 列 **`e2e-spy-1`** 的 strict 雙重匹配。

### Docs
- [`visualization_plan.md`](docs/architecture/visualization_plan.md) §3：對齊本日 **V2 切片**、**V4 mock smoke**、**V5 Today 離線橫幅** 勾選與誠實註記（staging PWA↔Telegram、預快取仍待）。
- [`AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md) 現況錨點補 **CHANGELOG 2026-05-05** 對照。

### Ops
- **隊列 18–21 手順入庫**：[`docs/OPS_QUEUE_18_21_RUNBOOK.md`](docs/OPS_QUEUE_18_21_RUNBOOK.md) — BQ DDL／Redis／VAPID／staging `test-send` **仍須在 GCP／執行環境手動完成**；本條不視為雲端已自動閉環。

## 2026-05-06

### Changed
- **Architecture backlog repo-side 補完（預設關／空資料不渲染）**：視覺化補 [`DeepFilingBlock.jsx`](data-verification-ui/src/components/report/blocks/DeepFilingBlock.jsx)、[`AgencyResearchBlock.jsx`](data-verification-ui/src/components/report/blocks/AgencyResearchBlock.jsx)、全區塊 `data-section`、DailyBriefReport JSON 持久化（`.qsilicon/daily_brief_reports`／`DAILY_BRIEF_JSON_DIR`／可選 `DAILY_BRIEF_JSON_BQ_TABLE`）與 Streamlit snapshot 格式 helper；NotebookLM 補 `Citation`／`DeepFilingAnalysis`、`deep_filing_analysis_node`、`deep_filing_block`、多題 helper、[`docs/SQL/notebooklm_cost_log.sql`](docs/SQL/notebooklm_cost_log.sql)；Agency 補 template parser、`AgencyResearchOutput`、`agency_researcher_node`、Crew backstory opt-in 與 `agency_finance_block`；TradingView 補 [`tools/tradingview.py`](tools/tradingview.py)、mock fixture、Crew／LangGraph tool tail 與 sample setup [`tradingview_mcp_setup.md`](docs/architecture/tradingview_mcp_setup.md)。Production 預設輸出保持不漂移；NotebookLM live client 與外部 TradingView MCP server 仍需另行接入／安裝。

### Docs
- **Portal Phase 1 驗收對齊**：[`docs/architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 驗收清單曾依 **main** 標示待辦（`useApi` header、401 專頁、`/`→`/briefs`、eslint）；**程式已於 CHANGELOG 2026-05-04** `### PWA`／`### API` 交付，驗收清單已改勾選；[`TODOS.md`](TODOS.md) **同步狀態（2026-05-04／2026-05-06）** 對齊。
- **勘誤（無行為變更）**：**2026-05-04** `### Added` 第一條原先所列 `shared/api/client.js` **並不存在**；已改為指向 [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)，並於該條附設計稿 `shared/api/client` 之驗收錨點。
- **Architecture 狀態對齊**：[`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 新增並更新 10 檔狀態矩陣；[`AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md) 將 Reviewer Loop 改為第一版已落地／維護中；[`REVIEWER_LOOP_DESIGN.md`](docs/architecture/REVIEWER_LOOP_DESIGN.md) 將舊驗收清單改成歷史設計對照；[`notebooklm_research.md`](docs/architecture/notebooklm_research.md)、[`agency_agents_research.md`](docs/architecture/agency_agents_research.md)、[`tradingview_mcp_research.md`](docs/architecture/tradingview_mcp_research.md) 改列 repo-side scaffold 與 live／外部依賴邊界；[`README.md`](README.md)、[`TODOS.md`](TODOS.md) 同步索引。

### CI
- **GitHub Actions（deploy）**：[`deploy.yml`](.github/workflows/deploy.yml) `build-and-deploy` 將 **`docker/setup-buildx-action`** 固定至 **v4.0.0**（`4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd`）、**`docker/build-push-action`** 至 **v7.1.0**（`bcafcacb16a39f128d818304e6c9c0c18556b85f`），對齊 Actions **Node.js 24** 預設執行環境，消除 Node 20 淘汰警告；見 [GitHub Blog](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)。

## 2026-05-04

### PWA（Terminal Portal）
- **API 認證出口**：[`data-verification-ui/src/lib/siliconApiHeaders.js`](data-verification-ui/src/lib/siliconApiHeaders.js) 集中 `localStorage.qsi_master_key` 與 `VITE_QSILICON_KEY` → `X-Q-Silicon-Key`；[`useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`pushClient.js`](data-verification-ui/src/pushClient.js) 合併送出；401 時 dispatch `qsilicon:api-unauthorized` 並導向 [`/api-key`](data-verification-ui/src/pages/ApiKeyPage.jsx)（`VITE_E2E=1` 時不跳轉，避免 Playwright mock 中斷）。
- **路由**：`/` 改 `Navigate` 至 `/briefs`；原今日頁改 `/today`；BottomNav「今日」連 `/today`；[`vite.config.js`](data-verification-ui/vite.config.js) PWA `start_url` 改 `/briefs`；[`TerminalSymbolCard`](data-verification-ui/src/components/TerminalSymbolCard.jsx)「今日」連結改 `/today`；E2E 改 `goto("/today")`。
- **Shell**：`/api-key` 隱藏 `ModuleNav` 與 `BottomNav`。
- **ESLint**：[`data-verification-ui/eslint.config.js`](data-verification-ui/eslint.config.js) 以 `import/no-restricted-paths` 禁止五模組互 import；`package.json` 新增 `npm run lint`；`languageOptions.parserOptions.ecmaFeatures.jsx` 以解析 `.jsx`。

### API
- **可選主金鑰保護**：當 `QSILICON_MASTER_KEY` 非空時，除 **`GET /api/stream/war-room`** 外，所有 `/api/*` 須 Header `X-Q-Silicon-Key` 與環境變數值一致；[`test_api_master_key_middleware.py`](test_api_master_key_middleware.py)。

### Added
- **Portal Phase 1 路由與設定頁溯源**：PWA 新增 **`/briefs`**（與 **`/terminal`** 同頁）、Shell 五模組 stub、API 請求見 [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)（設計稿之單一 `shared/api/client` 見 [`docs/architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 驗收清單）；Settings 補 Portal／`VISUALIZER_BTC_SOURCE` 說明；E2E [`data-verification-ui/e2e/briefs-alias-route.spec.js`](data-verification-ui/e2e/briefs-alias-route.spec.js)。
- **研究管線 stub（預設關）**：[`tools/notebooklm_tool.py`](tools/notebooklm_tool.py)（`NOTEBOOKLM_ENABLED`、`_get_cache`／`_set_cache`）、[`agents/agency/`](agents/agency/) 與 [`agents/agency/investment_researcher.md`](agents/agency/investment_researcher.md)、[`agents/agency/__init__.py`](agents/agency/__init__.py) 之 `_load_agency_template`（`AGENCY_RESEARCH_ENABLED`）。

### Changed
- **FastAPI 增量路由**：`GET /healthz`、`GET /api/metrics/*` 遷至 [`api_routers/`](api_routers/)，[`api.py`](api.py) 以 `include_router` 掛載；共用 BQ helper 見 [`api_deps.py`](api_deps.py)。
- **Runbook 視覺化**：[`visualizer.py`](visualizer.py) 支援 `VISUALIZER_BTC_SOURCE=snapshot` 時以已驗證 `symbol_snapshot` 之 `price_series` 建 BTC close 序列（預設仍 `yfinance`）。

### Docs
- [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：對齊 `/briefs`、`api_routers`、NotebookLM／Agency／`VISUALIZER_BTC_SOURCE`／`VITE_QSILICON_KEY`。
- [`docs/architecture/AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md)：現況區改為對照 CHANGELOG 之模板；Session 任務改為可填模板。
- [`CLAUDE.md`](CLAUDE.md)：根目錄補 Q-Silicon 架構與指令索引（含 `docs/architecture/Terminal_Master_Plan.md`、`scripts/verify_graph_gate.sh`）。

## 2026-05-02

### Docs
- **12 週個人化投資決策夥伴 Roadmap（文件對齊，尚未實作）**：[`README.md`](README.md) 新增 roadmap 說明，將方向從通用研報延伸到 paper P&L、quality-adjusted scoring、portfolio alignment、scenario / target optimizer 與 beta / launch；[`TODOS.md`](TODOS.md) 新增隊列 **28** 與 28a–28d 可執行波次，並於修訂紀錄標註本次僅為 roadmap 對齊。紅線維持：不弱化 `validate_report`、Telegram HTML 白名單或無數據幻覺；v1 僅允許 **paper-tracked** performance，不接券商、不自動下單，公開績效須可回放與可審計。

## 2026-04-29

### Changed
- **日報投資者可讀性清理**：[`report_render.py`](report_render.py)、[`main.py`](main.py)、[`templates/blocks/_ai_section.j2`](templates/blocks/_ai_section.j2)、[`schemas.py`](schemas.py)、[`crew.py`](crew.py) — `PREDICTION_MARKETS_IN_BRIEF` production 預設改為關閉，未顯式設 `1` 時不 prewarm Polymarket、不注入／渲染【預測市場熱門】；AI 儀表板改為「可交易市場／基本面／財報錨點／需求代理」三段可交易雷達，模型熱度最多一行且須連到已列 ticker；新增 pipeline 注入之 **【財報雷達｜未來 7 天】** 事件預告（yfinance watchlist，無 EPS／營收共識 forecast）；區塊②b 會移除與儀表板／新聞／交易理由重複的主題摘要。文件同步 [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)、[`docs/BRIEF_BLOCK_REFERENCE.md`](docs/BRIEF_BLOCK_REFERENCE.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`CLAUDE.md`](CLAUDE.md)。

### Tests
- [`test_report_render.py`](test_report_render.py)、[`test_main_pipeline_boundaries.py`](test_main_pipeline_boundaries.py)：覆蓋 Polymarket 預設關閉／顯式開啟、prewarm 跳過、財報雷達無事件／排序截斷／渲染、AI 儀表板需求代理過濾、區塊②b 重複內容省略。

## 2026-04-21

### Changed
- **LangGraph Reviewer Loop（Phase 3.5）**：[`graph/graph_crew.py`](graph/graph_crew.py) 將 native trade picker 路徑改為 **`trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`**；[`graph/graph_nodes.py`](graph/graph_nodes.py) 新增 deterministic `python_validate_node`（schema／重複標的／資產 universe／`price_context`）、`llm_reviewer_node`（僅查 thesis/direction/news 邏輯矛盾）、`review_retry_node`、`degrade_node`，並把最終 execution intents 寫入延後到 pass/degrade 後；[`graph/graph_state.py`](graph/graph_state.py) 補 reviewer state。新增 `GRAPH_LLM_TRADE_REVIEWER`（預設關閉；需 `GRAPH_LLM_TRADE_PICKER=1`）與 `REVIEWER_LOG_BQ`；[`bigquery_writer.py`](bigquery_writer.py) 新增 `write_reviewer_log`，DDL 見 [`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)。Reviewer 不取代 `validate_report`，降級僅把 warning 併入既有 `signal_conflict_summary`。
- **Terminal T1/T2 狀態矩陣收斂**：[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js) 新增 **`isHardApiError`** 與 E2E flag query 組裝，將 **`snapshot`／`quote`** 的 mock 風險分支統一到前端 hook；[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)、[`WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)、[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 收斂 **首次失敗 vs 背景 refetch 失敗** 行為：已有成功資料時保留內容，只加 degraded banner 與統一 retry 文案；`quote` 失敗不再讓整張 Terminal 卡降成空白；Today BTC strip 與 Terminal 卡在 **`aligned=true / false / null`** 三態下文案一致，並明示 **N/A / 後端未確認**。
- **Playwright T1/T2 擴面**：[`data-verification-ui/e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 支援 **`e2e_snapshot_fail`**、**`e2e_quote_fail`**、**`e2e_btc_alignment_na`**；新增 [`terminal-state-matrix.spec.js`](data-verification-ui/e2e/terminal-state-matrix.spec.js) 覆蓋 **單卡 quote fail 仍保留 snapshot**、**單卡 snapshot fail 不影響其他卡**、**`aligned=null` 顯示 N/A**；[`today-btc-mismatch-banner.spec.js`](data-verification-ui/e2e/today-btc-mismatch-banner.spec.js) 增 **N/A** 路徑。
- **Terminal T1b / T2a / T2c 契約補齊**：新增 [`dashboard/snapshot_payload.py`](dashboard/snapshot_payload.py) 統一 Streamlit Symbol 快照的 HTTP / direct-builder 載入分支；[`dashboard.py`](dashboard.py) 改共用該 helper，作為 Streamlit ↔ FastAPI snapshot shape 的單一入口。[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md) 補 `/api/*` request log、`elapsed_ms`、`price_alignment true/false/null` 三態與 `data_provenance` 的觀測對齊；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) 補 **Streamlit ↔ PWA 同形約束**；[`README.md`](README.md) 補 `latest_metrics`（BigQuery）與 `quote`（yfinance）非同源提醒。
- **Terminal T3b（執行意圖欄位契約）**：[`execution_intents.py`](execution_intents.py) 新增 **`normalize_execution_intent_row`**，將 legacy / partial JSONL 列正規化為固定 blotter shape（`category` / `asset` / `direction` / `status` 大寫、`status_updated_at` 補回退、`reference_*` / `paper_*` 浮點欄位正規化）；[`api.py`](api.py) 為 `GET /api/execution-intents` / `PATCH /api/execution-intents/{signal_id}` 加上 **`ExecutionIntentRow`** response model，固定回應欄位含 **`gate_issue_hints`** 空陣列預設。[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx) 補 **分類 / regime**、**更新時間**、**thesis**、**paper fill/exit** 顯示，使 Terminal blotter 從最小操作面提升為可審核表格。
- **Terminal T3c（輪詢 / 快取收斂）**：[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js) 抽出共用 **terminal live query policy**（`staleTime`／`refetchInterval`／retry backoff），並新增 **`syncWarRoomRelatedQueries`**：`PATCH /api/execution-intents/{signal_id}` 成功時先寫回 react-query cache，再只對**活躍**的 `execution-intents`／`war-room` 做 refetch，`metrics/latest`／`report`／`positions/open` 改為 **mark stale only**。[`data-verification-ui/src/hooks/useWarRoomSse.js`](data-verification-ui/src/hooks/useWarRoomSse.js) 改為 **SSE message 節流刷新**、**SSE error 不再 invalidate 全頁 query**，避免 SSE 斷線或 burst 事件把 Today / Terminal 打成重複全量重抓。

### Docs
- [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)：新增 **Terminal / Today 顯示規則（T1/T2 收斂）**，明定 `snapshot`／`quote`／`price_alignment` 的顯示優先序、degraded 行為，以及 **BigQuery KPI 不得與 yfinance quote 混寫成同一來源**。
- [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)：補 execution-intents 欄位契約，將 `GET /api/execution-intents` / `PATCH /api/execution-intents/{signal_id}` 的固定回應 shape、`gate_issue_hints` 預設與 blotter 審核欄位寫死。
- [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)：補 **T3c 輪詢 / 快取規則**，寫死 mutation 與 SSE 的 query sync 邊界：`execution-intents` / `war-room` 可即時刷新，但 `metrics/latest` / `report` / `positions/open` 只標記 stale，不可每次事件都同步全頁重抓。

### Tests
- 新增 [`test_reviewer_loop.py`](test_reviewer_loop.py)：覆蓋 reviewer Python pass/fail、LLM pass/fail、hard-cap degrade、graph smoke、最終 execution intents 寫入與 `write_reviewer_log` row shape；[`test_graph_crew.py`](test_graph_crew.py) 補 reviewer state 初始值。
- [`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py)：新增 `price_alignment` 對 **`quote_error`** 與 **missing OHLC** 分支的後端測試，補齊前端新使用的 `aligned=null` / `quote_error` 語意錨點。
- 新增 [`test_dashboard_snapshot_payload.py`](test_dashboard_snapshot_payload.py)：驗證 Streamlit snapshot loader 在 **HTTP** 與 **direct builder** 兩條路徑下都回傳同形 payload，作為 `SYMBOL_SNAPSHOT_HTTP_BASE` / `build_symbol_snapshot` 契約回歸。
- [`test_execution_intents_api.py`](test_execution_intents_api.py)：新增 execution-intents **legacy row normalization** 與 **PATCH 回傳 blotter shape** 回歸，並調整 `gate_issue_hints` 空陣列預設。

## 2026-04-18

### Changed
- **PWA 視覺化 V1／V2 補完**：根目錄 [`DESIGN.md`](DESIGN.md)（品牌 tone、token 真相來源 `tokens.js`）；[`data-verification-ui/src/design/tokens.js`](data-verification-ui/src/design/tokens.js) 增 **`typography`／`spacing`／`radius`／`shadow`**。[`api.py`](api.py) — `GET /api/reports/{date}/structured` 自 **`DAILY_BRIEF_JSON_DIR`**、**`.qsilicon/daily_brief_reports/{date}.json`**、**`logs/run_YYYYMMDD_*/raw_data.json`** 載入 **`DailyBriefReport`**，回傳 **`structured_source`**、**`gate_summary`**（`validate_structured_report` + **`.qsilicon/last_gate_failure`**，`issues_by_block`／`issues_unmapped`）；[`test_report_structured_api.py`](test_report_structured_api.py) 擴充。[`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx) — 區塊級 **`AsOfChip`**／**`GateStatusBadge`**、Gate 失敗橫幅。契約／環境見 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；[`visualization_plan.md`](docs/architecture/visualization_plan.md)、[`TODOS.md`](TODOS.md) 對齊。
- **PWA V2 `exec_summary`／`market_mode` 專用區塊**：[`ExecSummaryBlock.jsx`](data-verification-ui/src/components/report/blocks/ExecSummaryBlock.jsx)／[`MarketModeBlock.jsx`](data-verification-ui/src/components/report/blocks/MarketModeBlock.jsx)、[`BlockSection.jsx`](data-verification-ui/src/components/report/BlockSection.jsx)；[`structuredBlockContent.js`](data-verification-ui/src/components/report/structuredBlockContent.js) **`exec_summary`**／**`market_mode`** 結構化 payload；[`legacyBlockContent.js`](data-verification-ui/src/components/report/legacyBlockContent.js) **`fallbackText`**。E2E mock [`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 最小 **`daily_brief_report`** + **`structured_body_available`**；[`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js)。
- **PWA 視覺化 V2（結構化本文原生渲染）**：[`structuredBlockContent.js`](data-verification-ui/src/components/report/structuredBlockContent.js) — **`structuredContentForBlock`**／**`blockContentForBlock`**（**`structured_body_available`** 且 **`daily_brief_report`** 存在時優先映射 **`DailyBriefReport`**；逐 `block_id` 產出 **`text`／`metrics`／`news_items`／`html`／`roundtable`／`institutional_split`／`trades`**；QSREC **`normalizeTradeRecommendation`**、可執行腿 **`executableLegToTradeShape`**；**`trades`** 支援 **`introHtml`**／**`low_confidence_disclaimer`**）；缺欄或 skip 時退回 [`legacyBlockContent.js`](data-verification-ui/src/components/report/legacyBlockContent.js)。[`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx) — 傳入 **`daily_brief_report`**，擴充區塊 JSX。見 [`visualization_plan.md`](docs/architecture/visualization_plan.md)、[`TODOS.md`](TODOS.md)。

### Added
- **Streamlit 戰情室 v4（分頁 + 主題模組 + 自動刷新）**：[`dashboard/theme.py`](dashboard/theme.py) — `COLORS`、`PLOTLY_TEMPLATE`、`dashboard_inline_css()`；[`dashboard.py`](dashboard.py) — **`st.tabs`**：`Overview`、`Profile / LLM`、`Gate（7 日）`、`Roundtable`；**`DASHBOARD_AUTO_REFRESH_SEC`**（預設 **300**，秒）搭配可選 **`streamlit-autorefresh`**；Profile 聚合 **`llm_run_log`**（近 30 日）；Gate 列出 **`gate_failure_log`**（近 7 日）；Roundtable 掃 **`DAILY_BRIEF_JSON_DIR`**／**`.qsilicon/daily_brief_reports`**／**`logs/run_YYYYMMDD_*/raw_data.json`** 中含 **`current_affairs_roundtable`** 之日報 JSON。
- **PWA 保守離線（Workbox runtimeCaching）**：[`data-verification-ui/src/service-worker.js`](data-verification-ui/src/service-worker.js) — **`workbox-routing`**／**`workbox-strategies`**；`/api` **NetworkOnly**（不快取 API）；navigate／同源靜態 **NetworkFirst**；[`package.json`](data-verification-ui/package.json) 相依；[`docs/PWA_OFFLINE.md`](docs/PWA_OFFLINE.md)。
- **PWA 視覺化 V2（結構化 Report — 首批）＋ V3 前置**：[`api.py`](api.py) — `GET /api/reports/{report_date}/structured`（`profile` query，對齊 [`brief_profiles`](brief_profiles.py)；回傳 **`block_ids`**、**`block_registry`**、**`legacy`**、可選 **`daily_brief_report`**／**`gate_summary`**）；[`test_report_structured_api.py`](test_report_structured_api.py)。**`GET /api/brief-layouts`**（列 `config/brief_layouts/*.yaml`）；[`test_brief_layouts_api.py`](test_brief_layouts_api.py)。PWA — [`useStructuredReport`](data-verification-ui/src/hooks/useApi.js)、可選 [`useBriefLayouts`](data-verification-ui/src/hooks/useApi.js)；[`StructuredReportView.jsx`](data-verification-ui/src/components/report/StructuredReportView.jsx)、[`legacyBlockContent.js`](data-verification-ui/src/components/report/legacyBlockContent.js) — 頁級 [`AsOfChip`](data-verification-ui/src/components/common/AsOfChip.jsx)、區塊 **`#block-*`**、hash 捲動、[`BriefProfileBar`](data-verification-ui/src/components/report/BriefProfileBar.jsx)、[`reportProfiles.js`](data-verification-ui/src/components/report/reportProfiles.js)；[`Report.jsx`](data-verification-ui/src/pages/Report.jsx) — **`VITE_STRUCTURED_REPORT=1`**、**`?profile=`** 與 structured 載入對齊（並修正誤用未宣告變數 **`useStructured`** 之 bug）。契約／環境見 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。後續見同日 **`### Changed`**「V1／V2 補完」。
- **PWA 視覺化 V1（Design Foundation）**：依 [`visualization_plan.md`](docs/architecture/visualization_plan.md) Phase V1／§5 — [`data-verification-ui/src/design/tokens.js`](data-verification-ui/src/design/tokens.js)（`palette`、`tailwindThemeExtend` → [`tailwind.config.js`](data-verification-ui/tailwind.config.js) `theme.extend`：`regime.*`、`qs.*`）；共用元件 [`AsOfChip`](data-verification-ui/src/components/common/AsOfChip.jsx)、[`ProvenancePopover`](data-verification-ui/src/components/common/ProvenancePopover.jsx)（自 [`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) 抽出）、[`ProfileBadge`](data-verification-ui/src/components/common/ProfileBadge.jsx)、[`GateStatusBadge`](data-verification-ui/src/components/common/GateStatusBadge.jsx)、[`SourceLink`](data-verification-ui/src/components/common/SourceLink.jsx)、[`MockBanner`](data-verification-ui/src/components/common/MockBanner.jsx)；[`formatAsOfZh.js`](data-verification-ui/src/utils/formatAsOfZh.js)。[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 頁首指標更新改 **`AsOfChip`**（來源：`BigQuery · daily_metrics`／mock）；Terminal 卡 **as-of／資料溯源** 改共用元件。開發專用 **`/design`**（[`DesignShowcase.jsx`](data-verification-ui/src/pages/DesignShowcase.jsx)、[`App.jsx`](data-verification-ui/src/App.jsx) 僅 `import.meta.env.DEV`）。契約補述見 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「PWA 設計 tokens」。

### Changed
- **CI：`setup-node` v5／Node.js 24**：[`.github/workflows/ci.yml`](.github/workflows/ci.yml)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml) — `actions/setup-node@v5`、`node-version: "24"`，對齊 GitHub Actions 將 **Node 20** 自 runner 移除之時程（官方建議升級 action／執行環境）；消除 `setup-node@v4` 仍以 Node 20 執行 action 本體之棄用警示。

### Docs
- **架構計畫檔集中至 `docs/architecture/`**：[`visualization_plan.md`](docs/architecture/visualization_plan.md)、[`modularization_plan.md`](docs/architecture/modularization_plan.md) 自 repo 根目錄迁入；[`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 自 [`docs/`](docs/) 迁入；站內連結（[`README.md`](README.md)、[`CLAUDE.md`](CLAUDE.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`dashboard.py`](dashboard.py) docstring、[`config/brief_layouts/README.md`](config/brief_layouts/README.md) 等）對齊新路徑。
- **Terminal 總表與架構看法**：[`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) — 整合 [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)、[`docs/architecture/`](docs/architecture/)（[`AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md)、[`REVIEWER_LOOP_DESIGN.md`](docs/architecture/REVIEWER_LOOP_DESIGN.md)、[`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md)）與維護者／AI 看法；[`TODOS.md`](TODOS.md) 增 [§ AI／架構文件看法](TODOS.md#ai-architecture-views)；[`README.md`](README.md) 連結表；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md) 含 **`architecture/`** 列（同日／近期）。
- **計畫文件收斂**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) — **Phase 1–5**（含 **4d**、**5**〔時事多觀點〕，預設 `BRIEF_CURRENT_AFFAIRS=0`）之**完整落地敘述**已分散於本檔 **2026-04-14**（Phase 4d）、**2026-04-16**（Phase 4c）、**2026-04-26**（Phase 1）、**2026-04-27**（Phase 2–5／4a–4b／Gate Phase 3）；計畫正文改為 **維護導覽**（byte-identical／`REPORT_PROFILE`／YAML 語意），避免與 CHANGELOG 重複。**[`visualization_plan.md`](docs/architecture/visualization_plan.md)** — **已交付**之 V1、結構化 Report 主線（V2）、Profile／Archive 局部（V3）、Drawer／markers／Roundtable 元件／**Streamlit 戰情室 v4**（原 V6 主線）、**Workbox 保守離線**，見同日 **`### Added`**／**`### Changed`**；**未完成 backlog**（V2 區塊元件補齊、V3 layout 預覽、V5 SSE／Push 深連結／`/settings` 等）見計畫檔 **「剩餘 Backlog」**。

## 2026-04-16

### Changed
- **日報模組化 Phase 4c（BigQuery `profile`）**：[`bigquery_writer.py`](bigquery_writer.py) — `write_llm_run_log`／`write_gate_failure_log` 之 schema 與插入列新增 **`profile`**（與 [`brief_profiles.get_active_profile()`](brief_profiles.py)、[`validate_report`](report_html_gates.py) 回傳 **`profile`** 對齊）；既有表沿用缺欄 **`update_table` 補 schema** 路徑。[`main.py`](main.py) — `write_llm_run_log(..., profile=(last_validation or {}).get("profile"))`、`write_gate_failure_log(..., profile=result.get("profile"))`。手動 DDL 範例〔[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)〕。測試：[`test_llm_run_log.py`](test_llm_run_log.py)、[`test_gate_failure_log.py`](test_gate_failure_log.py)。**`SKIP_BIGQUERY=1`** 時仍 early return，行為不變。

### Docs
- [`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase **4c** 標註 **已落地**；[`README.md`](README.md) 日報模組化節（Phase 4c 已交付）；[`TODOS.md`](TODOS.md) 隊列 **22**／已交付摘要／修訂紀錄；[`CLAUDE.md`](CLAUDE.md) 觀測小節；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) — `GATE_FAILURE_BQ_LOG` 旁註記 **`llm_run_log`／`gate_failure_log` 含 `profile` 欄**。

## 2026-04-27

### Docs
- [`README.md`](README.md)：**日報模組化**小節與已落地 Phase 1–3 對齊（不再寫「模板與 `main.py` 尚未重構」）；[`TODOS.md`](TODOS.md) **同步狀態**標頭日期與內文一致。

### Changed
- **日報模組化 Phase 5（5a–5d + 5b + 4d 動態組版）**：[`schemas.py`](schemas.py) — `RoundtableVoice`、`CurrentAffairsRoundtable`、`DailyBriefReport.current_affairs_roundtable`、`dashboard_semantic_keys_for_roundtable`；[`current_affairs_crew.py`](current_affairs_crew.py) — **無 tools** 單 task 產出 roundtable；[`main.py`](main.py) — 雙軌後與 `source_observability_lines` **並行**、`assemble_daily_brief_report` 注入 **`source_observability_block`** 與 **`current_affairs_roundtable`**、可選 **`BRIEF_CURRENT_AFFAIRS_JSON`**、`validate_report(..., structured_report=)`；[`report_render.py`](report_render.py) — `BRIEF_DYNAMIC_RENDER=1` 時 YAML 驅動 **`full`** macro 串接（預設關閉＝**byte-identical**）；[`report_html_gates.py`](report_html_gates.py) — `STRICT_CURRENT_AFFAIRS_ROUNDTABLE_GATE` 結構化交叉檢、`STRICT_LITE_EXEC_SUMMARY_PASS6_GATE`；[`config/brief_layouts/README.md`](config/brief_layouts/README.md)、[`example_full_reorder_header_exec.yaml`](config/brief_layouts/example_full_reorder_header_exec.yaml)；[`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)、[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`modularization_plan.md`](docs/architecture/modularization_plan.md)、[`CLAUDE.md`](CLAUDE.md)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) `BRIEF_DYNAMIC_RENDER` 等；測試 [`test_dynamic_full_render.py`](test_dynamic_full_render.py)、[`test_current_affairs_render.py`](test_current_affairs_render.py) 擴充。
- **日報模組化 Phase 4b（`BRIEF_LAYOUT_FILE` YAML layout）**：[`brief_profiles_layout.py`](brief_profiles_layout.py) — `yaml.safe_load`、`applies_to_profile` 不符則忽略、`blocks` 須為內建 profile 之**同集合重排**（`BLOCK_IDS` 白名單、缺檔／讀檔失敗回退內建）；[`brief_profiles.py`](brief_profiles.py) — `profile_block_ids()` 經上述 merge。[`config/brief_layouts/README.md`](config/brief_layouts/README.md)、[`config/brief_layouts/example_lite_reorder.yaml`](config/brief_layouts/example_lite_reorder.yaml)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) `BRIEF_LAYOUT_FILE`；依賴 [`requirements.txt`](requirements.txt)／[`requirements-ci.txt`](requirements-ci.txt) **PyYAML**。[`test_brief_profiles_layout.py`](test_brief_profiles_layout.py)（`pytest -m smoke` 含一則）。**Phase 4c**（BQ `profile`）見 CHANGELOG **2026-04-16**、[`modularization_plan.md`](docs/architecture/modularization_plan.md)。
- **日報模組化 Phase 4a（`REPORT_PROFILE=crypto-only`）**：[`templates/profiles/telegram_crypto_only.j2`](templates/profiles/telegram_crypto_only.j2) — 共同前段 + 加密區塊①–④ + 尾段（無昨日建議／AI 全段／機構速讀）；[`brief_profiles.py`](brief_profiles.py) — `_PROFILE_TEMPLATE["crypto-only"]`、移除 `telegram_profile_template_relpath` 之 Phase 4 占位 `ValueError`；[`report_html_gates.py`](report_html_gates.py) — `profile=crypto-only` 時略過機構 Phase A/B/C HTML、不要求 AI 段落／美股精準操作、新聞六則改為加密段 **≥3 則** 與 `news_six_relaxed` 對齊、報告長度下限 **2000** chars、美股 QSREC pick／rotation／rolling／AI 基本面 citation 僅在 **非 crypto-only** 或無 EQUITY 列時套用；`_check_profile_block_consistency` 擋 **full HTML 誤標 crypto-only**。[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_brief_profiles.py`](test_brief_profiles.py) `telegram_profile_template_relpath("crypto-only")`。**Phase 4c**（BQ `profile`）見 CHANGELOG **2026-04-16**、[`modularization_plan.md`](docs/architecture/modularization_plan.md)。
- **日報 Gate Phase 3（`validate_report(..., profile=)`）**：[`report_html_gates.py`](report_html_gates.py) — `profile=lite` 時放寬「四區塊」相關 HTML 前提（儀表板／加密+AI 全段／呢喃／新聞 6 則／UTC+8／新聞新鮮度／傳聞分級／投資解讀數字錨／AI 基本面 citation 等）；**`STRICT_INSTITUTIONAL_PHASE_A/B/C_GATE=1` 在 lite 不檢查機構 HTML**（模板無該區）。`_check_profile_block_consistency` 防止 **full HTML 誤標 `profile=lite`**。回傳 dict 增 **`profile`**。[`main.py`](main.py)：`render_telegram_daily_brief`、`validate_report`、`_validate_report_candidate` 傳 **`get_active_profile()`**。[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)；[`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py) 支援 `REPORT_PROFILE`。**`profile=full` 與舊簽名等價**（預設仍 `full`）。
- **日報 Telegram 模板 Phase 2（`REPORT_PROFILE`、profiles、`brief_profiles`）**：新增 [`brief_profiles.py`](brief_profiles.py) — `BLOCK_IDS`、`PROFILES`（`full`／`lite`／`crypto-only` 佔位）、`BLOCK_REGISTRY`、`get_active_profile()`／`telegram_profile_template_relpath()`；[`templates/profiles/telegram_full.j2`](templates/profiles/telegram_full.j2)（等同 Phase 1 完整組裝）、[`templates/profiles/telegram_lite.j2`](templates/profiles/telegram_lite.j2)（精簡版型）；[`templates/blocks/_crypto_trades_only.j2`](templates/blocks/_crypto_trades_only.j2)、[`templates/blocks/_ai_trades_only.j2`](templates/blocks/_ai_trades_only.j2) 供 `lite` 重用區塊④。[`templates/telegram_report.j2`](templates/telegram_report.j2) 改為 `{% include "profiles/telegram_full.j2" %}`。[`report_render.render_telegram_daily_brief`](report_render.py) 支援 **`profile=`** 並讀 **`REPORT_PROFILE`**（預設 `full`）。**等價**：`full` 仍對 [`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) **byte-identical**（`test_telegram_template_modularization` + [`test_brief_profiles.py`](test_brief_profiles.py)）。環境變數見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。

## 2026-04-26

### Changed
- **日報 Telegram 模板 Phase 1（macro 化，輸出等價）**：[`templates/telegram_report.j2`](templates/telegram_report.j2) 改為匯入 [`templates/blocks/`](templates/blocks/)（`_header`、`_exec_summary`、`_previous_recs`、`_market_mode`、`_macro_framework`、`_prediction_markets`、`_crypto_section`、`_ai_section`、`_institutional_view`、**`_footer_tail`** — 尾段含 partial tier／low_confidence／source health／QSREC，**逐字對齊**凍結基線）；[`report_render.py`](report_render.py) 新增 **`build_telegram_jinja_env`**、**`telegram_render_context`** 供渲染與測試共用。**合併門檻**：[`test_telegram_template_modularization.py`](test_telegram_template_modularization.py)（`pytest -m smoke`）對 [`tests/fixtures/telegram_report_phase0_monolithic.j2`](tests/fixtures/telegram_report_phase0_monolithic.j2) **byte-identical**。

### Docs
- **日報區塊模組化 — 產品與交付原則**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) 新增 **產品與交付原則** 一節 — **過渡期** production 固定 **`full`／等價門檻**、新版型僅 staging／手動、**單一資料管線**不變；**完成後** 以 `REPORT_PROFILE`、`BLOCK_REGISTRY`、可選 YAML、profile-aware Gate、BQ `profile` 支援 **組織級客製**。閱讀地圖編號順延。（本條為計畫文件；**同日 `### Changed`** 為 Phase 1 模板實作。）

## 2026-04-25

### Docs
- **日報區塊模組化計畫（重排與五 Phase）**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) — **短期／中期／長期**目標表；**Phase 1** 模板原子化（可切片 PR 1a–1f）、**Phase 2** `brief_profiles`／`BLOCK_REGISTRY`／`REPORT_PROFILE`／`lite`、**Phase 3** profile-aware `validate_report` 與區塊一致性、**Phase 4** `crypto-only`／可選 YAML layout／BQ `profile`、**Phase 5** 【時事多觀點】Podcast 型文字區塊；閱讀地圖與附錄（Grok、一區塊一 Agent、Gemini 原子化／Registry 對齊）。**僅文件**；管線與 `templates/telegram_report.j2` **尚未**依計畫改動。
- **Deploy 何時會跑**：[`deploy.yml`](.github/workflows/deploy.yml) 對 `main` 的 **`push` 設有 `paths` 篩選**（見 workflow 註解「純文件不觸發」）；純文件 ship 後若需 Cloud Run 映像更新，請 **Actions → Deploy — Cloud Run Job → Run workflow**。已補 [`CLAUDE.md`](CLAUDE.md)、[`README.md`](README.md)、[`AGENTS.md`](AGENTS.md)、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)。

## 2026-04-24

### Changed
- **日報 Telegram 行動閱讀格式（HTML 白名單內）**：[`report_render.py`](report_render.py) — Jinja 濾鏡 **`tg_emphasize_numbers`**（價格／百分比等 token 以 `<b>` 強調）、**`tg_soft_wrap_mobile`**（長行依 `，。；｜` 等軟斷行，約 70 字）；執行摘要 **`_format_exec_summary_for_mobile`**（降噪 emoji、軟換行，接於 `_scrub_exec_summary_history_slogans` 之後）。[`templates/telegram_report.j2`](templates/telegram_report.j2) — 執行摘要與宏觀／預測市場／呢喃／本日選擇理由等區塊套用上述濾鏡；**不**引入 `<pre>`／`<br>` 等契約外標籤。[`report_quality_agent.py`](report_quality_agent.py) — **`_formatting_quality_hints`**（超長行、emoji 噪音、分隔線過多）併入改善項與 summary payload。[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) — 新增 **§8 低風險格式規則**、Phase A/B/C rollout 與驗收指標。

## 2026-04-23

### Changed
- **日報評估對齊（Polymarket API／宏觀錨點／LangGraph）**：[`tools_legacy.py`](tools_legacy.py) `fetch_polymarket_hot_highlight_lines` 支援 **`PREDICTION_MARKETS_TAG_IDS`**／**`PREDICTION_MARKETS_EXCLUDE_TAG_IDS`**（Gamma `tag_id`／`exclude_tag_id`）、`order=volume_24hr`，tag 篩選不足 3 條時合併無 tag 成交量後援；`macro_context_tool` 快取改 **`latest_v4_gspc_spy`** 並新增 **`fetch_spy_etf_last_close_anchor`**（SPY ETF 與 ^GSPC 指數分離敘述）；[`graph/graph_nodes.py`](graph/graph_nodes.py) `trade_picker_node` 與 native **`final_formatter_node`** 系統提示加入 **上下文刪減**（對齊 crew 因果紀律）；[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) §7b 與 **Telegram HTML 白名單**產品約定（不採 `<tg-spoiler>`）；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；測試 [`test_prediction_markets_tool.py`](test_prediction_markets_tool.py)、[`test_spy_etf_anchor.py`](test_spy_etf_anchor.py)。

## 2026-04-16

### Tests
- **PWA E2E（Bloomberg §6 Today）**：[`data-verification-ui/e2e/today-btc-mismatch-banner.spec.js`](data-verification-ui/e2e/today-btc-mismatch-banner.spec.js) — `localStorage.e2e_btc_misaligned=1` 時 mock 回 `price_alignment.aligned=false`，斷言 [`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx) **`today-btc-price-mismatch-banner`**；[`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs) 支援 **`?e2e_btc_misaligned=1`**（BTC snapshot／quote）；[`useApi.js`](data-verification-ui/src/hooks/useApi.js) 僅 **`VITE_E2E=1`** 建置時附加該 query（不影響一般 preview／prod）。

### Docs
- [`README.md`](README.md)：新增 **日報品質代理（可選）** 小節 — `.env` 設 `REPORT_QUALITY_AGENT=1`、`REPORT_LLM_JUDGE_MODEL` 預設 **gpt-4o-mini**、載入方式與勿亂開 `GIT_PUSH` 提醒；README 日期敘述改為指向 CHANGELOG。

## 2026-04-15

### Added
- **日報資料可信度（Opus 回饋 A／B）**：`^GSPC` 收盤錨（[`tools_legacy.py`](tools_legacy.py) `fetch_gspc_last_close_anchor`、`macro_context_tool`）、[`report_render.py`](report_render.py) `equity_valuation_framing` SPX 後處理、可選 [`report_html_gates.py`](report_html_gates.py) `STRICT_SPX_LEVEL_SANITY_GATE`；Polymarket 選題 **`PREDICTION_MARKETS_KEYWORDS`／`PREDICTION_MARKETS_DENYLIST`**（[`tools_legacy.py`](tools_legacy.py) `fetch_polymarket_hot_highlight_lines`）；測試 [`test_report_render.py`](test_report_render.py)、[`test_prediction_markets_tool.py`](test_prediction_markets_tool.py)；[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) §7b。
- **實盤 BQ vs yfinance 觀測 CLI**：[`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py)（stdout JSON：`build_symbol_snapshot`、`price_alignment`、可選 **`PRICE_PROBE_WRITE_BQ`**）；建表 DDL [`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)；`config.PRICE_PROBE_LOG_TABLE` 預設留空由 env 覆寫。
- **Web Push T4a（Redis、VAPID、pywebpush、BQ）**：[`web_push_store.py`](web_push_store.py) — `WEB_PUSH_REDIS_URL`（HASH 存完整 subscription、**Redis INCR** 分散式 rate limit）、可選 **`WEB_PUSH_BQ_PERSIST`**／**`WEB_PUSH_BQ_AUDIT`**；[`api.py`](api.py) `POST /api/push/test-send`（**`X-Web-Push-Admin-Key`**）；[`scripts/vapid_generate.py`](scripts/vapid_generate.py)；DDL [`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql)；[`test_web_push_redis.py`](test_web_push_redis.py)（fakeredis）；依賴 **`redis`／`pywebpush`／`py-vapid`**（[`requirements.txt`](requirements.txt)）、CI **`fakeredis`+`redis`**（[`requirements-ci.txt`](requirements-ci.txt)）。

### Changed
- **日報 Telegram（Opus 回饋落地 C／D）**：[`templates/telegram_report.j2`](templates/telegram_report.j2) — 機構免責 `<blockquote>` 改渲染於 **【機構速讀｜命題與情境】** 標題**之前**（不再緊接標題後）；AI 儀表板抬頭改 **🤖 區塊①** 以利與加密段區分；區塊④多腿之間 **`────────` 改為空行** 以減分隔線噪音。[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) 區塊順序表同步。[`crew.py`](crew.py) — `_BRIEF_V2_RULE` 增讀者版標題一條；`_TOOL_TRUTH_RULE`／`_NEWS_FMT` — HF／OpenRouter 具體數字須一句鏈接 yfinance／FD watchlist，否則省略數字；單標的微結構新聞禁以 **DXY** 為唯一主因；`_FINAL_TEMPLATE_AI` 範例同步。[`tools_legacy.py`](tools_legacy.py) `ai_momentum_tool` docstring 對齊主編紀律。
- [`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4b：對齊 T4a／price probe。

### Docs
- [`TODOS.md`](TODOS.md)：新增 **git pull／讀 codebase 提醒**（錨點 `#pull-or-read-codebase-reminder`）與隊列 **18–21**（BQ DDL、Redis、VAPID、staging `test-send`）；[`CLAUDE.md`](CLAUDE.md) 導覽連結至該錨點。

### Tests
- [`test_web_push_redis.py`](test_web_push_redis.py)

## 2026-04-14

### Changed
- **日報模組化 Phase 4d（Phase 1–4 補強）**：[`validation_rules.py`](validation_rules.py) 新增 **`HAS_CRYPTO_DASHBOARD_BANNER_RE`**、lite 雙邊區塊④標題錨點正則；[`report_html_gates.py`](report_html_gates.py) **`_check_profile_block_consistency`** 改以結構錨點檢查（lite：須同時含加密／美股 **區塊④** 標題、擋完整加密儀表板標題區／AI 全段／機構／上期；crypto-only：須含加密儀表板標題區、**不得**含 **AI 美股區塊④**），修正 **lite HTML 誤標 `profile=crypto-only` 仍通過** 之洞。[`main.py`](main.py) 新增 **`_validate_report_profile_env()`**（於 **`_validate_required_keys` 之後**）對非法 **`REPORT_PROFILE`** early-fail。[`config/brief_layouts/README.md`](config/brief_layouts/README.md) 明示 **`BRIEF_LAYOUT_FILE`／`profile_block_ids()` 目前不驅動** [`report_render.render_telegram_daily_brief`](report_render.py) 之 Jinja 區塊順序；動態組版見 [`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 4d 後續項。[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) 補 **`profile`** 欄首次寫入／手動 DDL 提醒。[`modularization_plan.md`](docs/architecture/modularization_plan.md) 進度表與 Phase 4 納入 **4d**。[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_critical_paths.py`](test_critical_paths.py)。

### Added
- **日報品質代理（可選）**：[`report_quality_agent.py`](report_quality_agent.py) — `REPORT_QUALITY_AGENT=1` 時在 `validate_report` 乾淨通過或 warn-pass 交付後，以 LLM rubric（沿用 `llm_quality_judge`）與可選 `domain_quality_check` 計算複合分；低於 `REPORT_QUALITY_AGENT_COMPOSITE_MIN` 時將改善項寫入 [`TODOS.md`](TODOS.md) 內 `REPORT_QUALITY_AGENT_TODOS_*` 機器區塊；[`scratchpad.py`](scratchpad.py) 新增 `quality_agent_result` 事件；[`main.py`](main.py) 在三處成功交付路徑掛勾。可選 `REPORT_QUALITY_AGENT_GIT_PUSH` + `REPORT_QUALITY_AGENT_GIT_ALLOW` 於寫入後 `git commit`／`push`（預設關閉）。環境變數見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **Symbol snapshot 價格對齊探測**：[`symbol_snapshot_service.py`](symbol_snapshot_service.py) 回應含 `price_alignment` 與 `data_provenance.price_alignment`（OHLC 尾端 vs `fetch_symbol_quote`）；[`api.py`](api.py) `SymbolSnapshot` 增欄位。
- **Web Push 分階**：[`web_push_store.py`](web_push_store.py)；`WEB_PUSH_ENABLED=1` 時 `POST /api/push/subscribe` 可 log-only 或 `WEB_PUSH_STORE=1` 程序內暫存；[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)；PWA [`pushClient.js`](data-verification-ui/src/pushClient.js) + [`main.jsx`](data-verification-ui/src/main.jsx) 可選註冊（`VITE_WEB_PUSH_*`）。
- **PWA Playwright E2E（Bloomberg §6 UI）**：[`data-verification-ui/e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`playwright.config.js`](data-verification-ui/playwright.config.js)、[`e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)；[`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)（今日頁非 demo 時顯示與 Terminal 同源 BTC 價）；[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)。
- **Terminal 後中段（T1–T3／T5 穿插）**：[`execution_intents.py`](execution_intents.py) `latest_execution_intents` 支援 **`status`／`category`／`sort_by`**；[`api.py`](api.py) `GET /api/execution-intents` 對應 query、`gate_issue_hints` 唯讀富化（本機 gate artifact）、**`API_HTTP_REQUEST_LOG`** 可選 `/api/*` 延遲日誌；PWA [`useApi.js`](data-verification-ui/src/hooks/useApi.js) 輪詢 **微錯開**（`VITE_TERMINAL_QUERY_COALESCE`）、Terminal 相關 query **5xx exponential backoff**；[`Today.jsx`](data-verification-ui/src/pages/Today.jsx)／[`PositionHealthStrip.jsx`](data-verification-ui/src/components/PositionHealthStrip.jsx)／[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)／[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)／[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)（錯誤重試、`price_alignment` 警告、意圖篩選排序、工作區 JSON 匯入／匯出、**Alt+Shift+E／I**、`report_links` **`Link`** +「今日戰情室」）；Playwright [`e2e/terminal-spy-mismatch.spec.js`](data-verification-ui/e2e/terminal-spy-mismatch.spec.js)；mock API 支援 **SPY** 未對齊分支。
- **Terminal 下一輪（E2E／契約／Web Push guard）**：[`symbol_snapshot_service.py`](symbol_snapshot_service.py) — `price_alignment` 增 **`ohlc_source`／`quote_source`／`daily_metrics_source`／`routes`**；可選 **`PRICE_ALIGNMENT_E2E_OVERRIDES`**（JSON）；[`web_push_store.py`](web_push_store.py) — endpoint **去重**、**`WEB_PUSH_SUBSCRIBE_RATE_PER_MIN`**（client IP）、**`WEB_PUSH_STORE_MAX_SUBSCRIPTIONS`**；[`api.py`](api.py) `push_subscribe` 傳 **client_ip**；`gate_issue_hints` 改 **單字邊界**比對；Playwright [`e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)；mock API **NVDA** 路由；[`test_api_push.py`](test_api_push.py) 去重／rate limit；[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py) E2E override；[`test_execution_intents_api.py`](test_execution_intents_api.py) 誤匹配迴歸。

### Changed
- [`main.py`](main.py)：`scratchpad.begin_run` 的 `init.meta` 附帶 `pipeline_config`（`PIPELINE_STRICT_ENV`、`ADAPTIVE_GATE_*`、`GRAPH_DEEP_RESEARCH_TOOL_LLM`、`WEB_PUSH_*`、`effective_pick_rotation_override_min_gap` 等非機密快照）；`_validate_env_types` 納入自適應門檻相關數值 env 校驗。
- [`graph/graph_nodes.py`](graph/graph_nodes.py)：`GRAPH_DEEP_RESEARCH_TOOL_LLM=1` 時 deep research 寫入 scratchpad `graph_deep_research_metrics`（輪次、工具次數、耗時、**unknown_tool_hits**／**tool_invoke_errors**／**finish_kind**）。
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)：新增 Node 20、**Terminal contract**（[`scripts/ci_terminal_contract_check.sh`](scripts/ci_terminal_contract_check.sh)）、**npm cache**（`data-verification-ui/package.json`）。
- [`data-verification-ui/src/components/WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)／[`Today.jsx`](data-verification-ui/src/pages/Today.jsx)：War Room 錯誤態 **重試** 與成功態 **重新整理**。
- [`api.py`](api.py)：`POST /api/push/subscribe` 分階行為（見上）；`WEB_PUSH_ENABLED=1` 時回 `stored`／`endpoint_fp` 等 meta。
- [`data-verification-ui/src/components/SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx)：**lightweight-charts v5** 改用 `chart.addSeries(CandlestickSeries, …)`（修復 Terminal K 線白屏）。
- [`data-verification-ui/vite.config.js`](data-verification-ui/vite.config.js)：`VITE_E2E=1` 建置時略過 **VitePWA**（避免 Service Worker 干擾 Playwright）。
- [`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)：`VITE_E2E=1` 時跳過 workspace 之 localStorage 還原／寫入；`?e2e_btc=1` 僅 BTC；`?e2e_symbols=BTC,SPY` 覆寫 E2E seed；工作區 grid 增 `data-testid`／`data-active-symbols`。
- [`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)：`terminal-quote-last-{SYMBOL}` **data-testid**。

### Docs
- [`TODOS.md`](TODOS.md)：新增 **Terminal／戰情室後中段路線（T1–T5）** — 每切片對應主要檔案與建議執行順序（持續 improve 規劃）；後續補 **主線／並線／交錯** 執行順序表。
- 新增 [`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)（含 **T4b** 通知語意草案）；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4b 補條目 6／14 之 pytest／CI／**Playwright** 錨點與 **snapshot price_alignment**；**§4c** 補 snapshot vs quote 口徑表；[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md)、[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md)、[`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md) 對齊 scratchpad／CI 觀測；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 同步 Web Push／snapshot 欄位、`execution-intents` query、`API_HTTP_REQUEST_LOG`、`VITE_TERMINAL_QUERY_COALESCE`。
- [`README.md`](README.md)：MIT／Python／CI **badges**（shields.io 靜態連結至 `.github/workflows/ci.yml`）、LICENSE 對齊一句、CI 小節註記 **npm cache**、PWA **`npm run test:e2e`**；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引增 ADR 索引與 PWA Web Push。
- **視覺化階段 A**：新增 [`visualization_plan.md`](docs/architecture/visualization_plan.md)（階段 A–D：契約／Terminal／Telegram 附圖／長線）；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) 新增「**視覺化與數字段語意**」— `price_series`（OHLC）、`/quote`、`latest_metrics`（BQ）、`price_alignment` 讀圖規則；[`dashboard.py`](dashboard.py) Symbol 快照 expander 內 **ℹ️ 數字口徑** 與載入成功後 **`price_alignment`** 提示；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引列 `docs/architecture/visualization_plan.md`。

### Tests
- 新增 [`test_report_quality_agent.py`](test_report_quality_agent.py)（複合分、TODOS 區塊、整體流程 mock）。
- 新增 [`test_terminal_numeric_consistency.py`](test_terminal_numeric_consistency.py)（quote vs OHLC 同源 yfinance）。
- 新增 [`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)（mock bind_tools 路徑驗證 scratchpad metrics）。
- 新增 [`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)（`hypothesis` + `boundary`：`schemas._cap_internal_field`）。
- 新增 [`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py)（snapshot `price_alignment` 與 `_align_snapshot_price`）。
- 更新 [`test_api_symbols_snapshot.py`](test_api_symbols_snapshot.py)、[`test_api_push.py`](test_api_push.py)（Web Push 分階契約）。
- Playwright：[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)（`npm run test:e2e`，Chromium）。
- 更新 [`test_execution_intents_api.py`](test_execution_intents_api.py)（`sort_by` 400、`status`／`category` 篩選、`gate_issue_hints`、war-room 富化、**子字串誤匹配**）。
- Playwright：[`e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)。

## 2026-04-12

### Added
- **Bloomberg 對齊文件**：新增 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)（能力映射、紅線、15 條驗收清單、分階切片），並回鏈 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) / [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) / [`TODOS.md`](TODOS.md)。
- **Symbol Snapshot API**：[`api.py`](api.py) 新增 `GET /api/symbols/{symbol}/snapshot`（`latest_metrics`、`history`、`price_series`、`event_markers`、`report_links`）。
- **PWA Terminal Workspace**：新增 [`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/components/SymbolCandleChart.jsx`](data-verification-ui/src/components/SymbolCandleChart.jsx)；支援 watchlist 本地持久化、拖曳重排、symbol 深度卡。
- **Terminal 中段（M1）**：Symbol 快照回應新增 **`data_provenance`**（[`symbol_snapshot_service.py`](symbol_snapshot_service.py) — OHLC／`daily_metrics`／`recommendations` 之來源、as_of、BQ 表 id）；[`api.py`](api.py) 新增 `GET /api/execution-intents`、`GET /api/execution-intents/allowed-statuses`、`PATCH /api/execution-intents/{signal_id}`（append-only 狀態轉移，**不下單**）；[`execution_intents.py`](execution_intents.py) 支援去重列表與 `status_updated_at`／`status_note`。
- **文件**：[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)（中段定義、切片 M1–M5、驗收語意）。

### Changed
- [`report_render.py`](report_render.py)：`assemble_daily_brief_report` 在 MA 儀表列注入後，**以【今日市場模式】評分卡為準**同步 **BTC RSI** 儀表列之 `status_emoji`（✅／❌／⬜）；並將敘事／新聞／交易卡內 **緊鄰 MA20／MA50** 之美元價（與儀表板僅微小差異者）正規化為儀表板同一格式，避免可審計口徑分裂。
- [`api.py`](api.py)：`report_links.href` 改為前端報告路由 `/report/{date}`，並保留 `api_href` 指向 `/api/reports/{date}`；`_fetch_symbol_ohlc` 新增短 TTL 快取降低 yfinance 重複查詢。
- [`api.py`](api.py)：CORS `allow_methods` 含 **`PATCH`**（意圖狀態 API）。
- [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)：新增 `useSymbolSnapshot`（後續 M2 擴充 `livePoll`／`useMutation` 見 `### PWA`）。
- [`data-verification-ui/src/App.jsx`](data-verification-ui/src/App.jsx)、[`data-verification-ui/src/components/BottomNav.jsx`](data-verification-ui/src/components/BottomNav.jsx)：新增 `/terminal` 路由與導覽入口。
- [`data-verification-ui/package.json`](data-verification-ui/package.json)：新增 `lightweight-charts` 依賴。
- [`data-verification-ui/src/App.jsx`](data-verification-ui/src/App.jsx)：`/terminal` 改 **`React.lazy` + `Suspense`**，將 Terminal 頁與 `lightweight-charts` 拆成**獨立 async chunk**（首屏 bundle 減重）。

### Tests
- [`test_report_render.py`](test_report_render.py)：評分卡 ↔ 儀表板 **BTC RSI emoji**；**MA20 鄰近 $** 敘事對齊儀表板；QSREC smoke 於 `validate_report` 前 **patch `STRICT_NEWS_FRESHNESS_GATE=0`**，避免本機啟用新鮮度 gate 時與固定 **03/22** 樣本新聞耦合（專項見 [`test_news_freshness.py`](test_news_freshness.py)）。
- 新增 [`test_api_symbols_snapshot.py`](test_api_symbols_snapshot.py)（成功、symbol 格式錯誤、BigQuery 失敗）。
- 新增 [`test_execution_intents_api.py`](test_execution_intents_api.py)（allowed-statuses、列表去重、`PATCH` 成功／404）。
- 驗證：`python3 -m pytest test_api_symbols_snapshot.py test_api_push.py test_execution_intents_api.py test_api_symbol_quote.py`。
- 驗證：`cd data-verification-ui && npm run build`（build success）。

### Docs
- **維護契約**：本檔檔首增訂 **CHANGELOG ↔ [`TODOS.md`](TODOS.md) 雙向對齊** 規則；[`AGENTS.md`](AGENTS.md) Handoff、[`CLAUDE.md`](CLAUDE.md) 導覽一句補強。
- **[`TODOS.md`](TODOS.md)**：與 **2026-04-10** `### Pipeline` 對齊之「已交付摘要」兩列（日報組裝衛生、`crew`／FD 規則）及修訂紀錄／同步狀態 — 見該檔 **2026-04-12** 修訂條；**新增** [進度分析表（華爾街級日報 · 財報週期 · Bloomberg 對齊）](TODOS.md#progress-vs-wall-st-bloomberg)（維度 1–5 粗評、Phase 0 驗收錨點、建議內部 KPI）；檔首導覽補錨點連結；下一批隊列增 **Terminal M3–M5**，M2 鏈結至 roadmap 錨點。
- **[`TODOS.md`](TODOS.md)**（進度表補登）：依 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4 做 **Phase 0 十五條內部勾選**，暫列 **12/15** 通過並註記例外項；「Terminal 式產品面」粗評回寫為 **3–4**／5（對齊 M1–M5 已交付敘述）。
- **[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)**：擴充 **M2–M5** 可執行規劃 — 各階 **DoD**、建議修改檔案、API 形狀、測試與依賴圖（§3b–§3e、§6–§7）；環境變數表補 **`VITE_TERMINAL_POLL_MS`**、M4/M5 預留項。
- **[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)**：`snapshot` 之 **`data_provenance`**；`execution-intents` 三路由契約表；PWA **`/terminal`** 輪詢與 **`VITE_TERMINAL_POLL_MS`**。
- **[`README.md`](README.md)**：`/terminal`、`VITE_API_URL`、**`VITE_TERMINAL_POLL_MS`**（`/terminal` 輪詢）與 [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) 索引；「War Room PWA 與 API」小節補前後端連線說明。
- **[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)**：§3b 標註 M2 **已落地**檔案鏈。

### PWA（Terminal 中段 M2）

- **[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)**：`getTerminalRefetchIntervalMs`（`VITE_TERMINAL_POLL_MS`，預設 45s）；`useSymbolSnapshot`／`useExecutionIntents`／`useWarRoomLatest` 支援 **`livePoll`** 輪詢；`usePatchExecutionIntent`（`PATCH` + invalidate intents／war-room）。
- **[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)**：`/terminal` 意圖表、狀態按鈕、備註輸入、全域 PATCH 錯誤提示。
- **[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)**：`data_provenance` 摺疊區；snapshot **livePoll**。
- **[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)**：掛載意圖表。
- **[`index.css`](data-verification-ui/src/index.css)**：provenance／blotter 樣式。

### Tests

- 驗證：`cd data-verification-ui && npm run build`。

### API（Terminal M3）

- **[`api.py`](api.py)**：`GET /api/symbols/{symbol}/quote` — yfinance **日線最後收盤**、可選 **1D %**、`data_provenance.price`；無報價時 **503**。
- **[`symbol_snapshot_service.py`](symbol_snapshot_service.py)**：`fetch_symbol_quote`（**45s** in-process TTL 快取、每 symbol 上限）。
- **[`test_api_symbol_quote.py`](test_api_symbol_quote.py)**：成功（mock）、503、400。
- **PWA**：[`useSymbolQuote`](data-verification-ui/src/hooks/useApi.js)；[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) 頂欄最新收盤；[`index.css`](data-verification-ui/src/index.css) 樣式。
- **Docs**：[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md) §3c、[`README.md`](README.md) War Room 小節。

### Tests（M3）

- 驗證：`python3 -m pytest test_api_symbol_quote.py`；`cd data-verification-ui && npm run build`。

### API（Terminal M4 / M5）

- **[`api.py`](api.py)**：`GET /api/stream/war-room`（SSE，`TERMINAL_SSE_ENABLED=1`；可選 `API_STREAM_AUTH_KEY`、`TERMINAL_SSE_POLL_SEC`）；`POST /api/paper/execution-tick`（`PAPER_TICK_HTTP_ENABLED=1`、可選 `PAPER_TICK_API_KEY`）。
- **[`war_room_stream.py`](war_room_stream.py)**：`bump_war_room_stream_version`／`get_war_room_stream_version`（intent 寫入時 bump）。
- **[`execution_intents.py`](execution_intents.py)**：`PAPER_*` 狀態、`CLIENT_PATCHABLE_STATUSES`、PATCH body **`reference_*`**、`append_execution_intent_row`、`intent_store_mtime`。
- **[`paper_execution.py`](paper_execution.py)**、`[scripts/paper_execution_tick.py](scripts/paper_execution_tick.py)`：紙上模擬 tick（`fetch_symbol_quote` vs `reference_*`）。
- **測試**：[test_api_stream_war_room.py](test_api_stream_war_room.py)、[test_war_room_stream.py](test_war_room_stream.py)、[test_paper_execution.py](test_paper_execution.py)；`test_execution_intents_api.py` 擴充。
- **PWA**：[ExecutionIntentsBlotter.jsx](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)（`client_patchable` 按鈕、參考價、可選 `VITE_SSE_ENABLED`）；[useApi.js](data-verification-ui/src/hooks/useApi.js) PATCH body 擴充。
- **Docs / env**：[ENV_TEMPLATE.txt](ENV_TEMPLATE.txt)、[docs/DASHBOARD_CONTRACT.md](docs/DASHBOARD_CONTRACT.md)、[docs/TERMINAL_MID_TIER_ROADMAP.md](docs/TERMINAL_MID_TIER_ROADMAP.md)、[README.md](README.md)、[TODOS.md](TODOS.md)。

### Tests（M4/M5）

- 驗證：`python3 -m pytest test_api_stream_war_room.py test_war_room_stream.py test_paper_execution.py test_execution_intents_api.py`；`cd data-verification-ui && npm run build`。

## 2026-04-10

### Pipeline
- [`report_render.py`](report_render.py)：組裝衛生——儀表板 BTC 現價 **>50k** 且三情境列同時含 **BTC／比特幣** 與 **突破** 時，將誤植 **`7.6k`→`76k`**；儀表板分區注入前 **剔除** label 等於 IB 區塊標題且 **value 空白** 之佔位列，並 **去重連續相同** `is_section_header`。
- [`crew.py`](crew.py)：加密新聞 `investment_takeaway` 禁止無標題／摘要／工具依據之 **垃圾債／HY／spread** 等信用市場跳喻；**FinancialDatasets** 營收相關 MetricLine `label` 須含 **annual／quarterly／FY／年份／季報** 等期間字樣。
- [`tools_legacy.py`](tools_legacy.py)：`financial_datasets_tool` 摘要尾註提醒營收 label 帶 **fiscal／口徑** 以利核對異常大數。

### Bloomberg 對齊 Phase 2（Workspace v2／跨頁 Symbol／Streamlit 快照）
- **PWA**：[`SymbolFocusContext.jsx`](data-verification-ui/src/context/SymbolFocusContext.jsx)、[`SymbolFocusBar.jsx`](data-verification-ui/src/components/SymbolFocusBar.jsx)；[`App.jsx`](data-verification-ui/src/App.jsx) 以 `SymbolFocusProvider` 包覆路由；Today／Charts／Trades／Archive／Report／Terminal 掛載關注條（`localStorage` `qs_symbol_focus_v1`）。
- **Terminal 工作區 v2**：[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx) 多分組（`qs_terminal_workspace_v2`）、自 v1 遷移、一鍵模板（Crypto／大盤／AI 鏈）、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)「設為全域關注」。
- **後端／儀表板**：[`symbol_snapshot_service.py`](symbol_snapshot_service.py) 集中 snapshot 組裝；[`api.py`](api.py) 改呼叫該模組；[`dashboard.py`](dashboard.py) 唯讀 Symbol 快照區（`SYMBOL_SNAPSHOT_HTTP_BASE` 可改打 API，否則 BQ 直建同形 payload）；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 補 `SYMBOL_SNAPSHOT_HTTP_BASE`／`DASHBOARD_SYMBOL_FOCUS`。

## 2026-04-23

### Docs
- **[`TODOS.md`](TODOS.md)**：**改寫為導覽型** — 明確區分「已交付摘要」「下一批隊列」「長期索引」；舊版 G-1～G-8 全表與重複 Phase／OSS 細拆 checkbox **自本檔移除**（細項未宣告為已全部實作；完整舊表可自 git 歷史還原）。保留 **`OSS_SCOUT_AUTO_BEGIN`／`END`** 供 [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 合併週報。

## 2026-04-22

### Added
- [`graph/graph_tools.py`](graph/graph_tools.py)：`fetch_onchain_metrics_btc`（`onchain_metrics_tool`）納入 `RESEARCH_TOOLS`。
- 社群／授權骨架：根目錄 [`LICENSE`](LICENSE)（MIT）、[`CONTRIBUTING.md`](CONTRIBUTING.md)、[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)；[`README.md`](README.md) 表格連結。
- PWA：[`data-verification-ui/src/components/WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)（execution intent 狀態篩選）並由 [`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 引用。

### Changed
- [`report_render.py`](report_render.py)：`strip_usd_for_template` Jinja 濾鏡 `strip_usd`；[`templates/telegram_report.j2`](templates/telegram_report.j2) 交易卡價位欄改走該濾鏡，避免 `$` 重複。
- [`schemas.py`](schemas.py)：`ExecutableTradeLeg` 對 `rr`、`max_drawdown_pct`、`expected_win_rate`、`signal_score` 去除前導 `$`。
- [`graph/graph_nodes.py`](graph/graph_nodes.py)：`deep_research_node` 決定性路徑額外附帶 `deep_prediction_probe`（`prediction_markets_tool` 快照）。
- [`TODOS.md`](TODOS.md)：標註 Pri 8／LG-2／LG-3／PWA War Room／G-7 部分完成；**移除台股 Pri 9 作為現行優先項**（台股顯示不在本輪範圍）。

### Tests
- [`test_report_render_filters.py`](test_report_render_filters.py)、[`test_graph_tools_extended.py`](test_graph_tools_extended.py)、[`test_graph_crew.py`](test_graph_crew.py)（`test_deep_research_deterministic_includes_prediction_probe`）。

### Docs
- [`docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md`](docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md)：訂閱取代十點堆疊手動研究稿（威脅建模、Phase 對照）。
- [`docs/oss_candidates/2026-04-22-candidates.json`](docs/oss_candidates/2026-04-22-candidates.json)、[`docs/oss_candidates/2026-04-22-digest.json`](docs/oss_candidates/2026-04-22-digest.json)：手動研究稿對應機讀檔，供審閱與後續工具鏈對接。
- [`TODOS.md`](TODOS.md)：同步狀態更新至 2026-04-22；補「訂閱取代手動研究」檔首導覽、OSS Integration 對照行、手動小節 JSON 連結；波次 G 增 G-1～G-8 子錨點；Pri 8 改為「備查」語意。

## 2026-04-21

### Changed
- [`main.py`](main.py)：`_postprocess_report_for_resilience` 於 Telegram HTML 安全清洗前，將 LLM 贅字 **「美國政府政府」** 正為 **「美國政府」**。
- [`crew.py`](crew.py)：**`_DATA_RULES`** 補〔新聞 4–6〕與 **36 小時**／**`STRICT_NEWS_FRESHNESS_GATE`** 銜接及主錨點須落在 AI 區塊①；**`_NEWS_FMT`** 明定 SOL／ETH／BNB 美元現價須對齊加密區塊① `<code>`（**`STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE`** 精神）；**`_TRADE_JSON_RULE`** 補 **QSREC 同標延續**（`repeat_days≤2`、連持建議填 1、`selection_score≥75`）與 **Gate 警示**對齊說明。
- [`tracker.py`](tracker.py)：**「上期建議追蹤」** BigQuery 查詢帶出 **`category`**；若 **EQUITY** 建議日距今 **≤2 日**且 **|PnL|>35%**，或 **CRYPTO** **≤1 日**且 **|PnL|>55%**，略過該列顯示並 **`logger.warning`**（降低髒進場價／單位錯誤洗版）；**`_infer_previous_rec_category`** 於舊列無 `category` 時依代號推斷 CRYPTO／EQUITY。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：`test_main_postprocess_scrubs_duplicate_government_typo`。
- [`test_tracker.py`](test_tracker.py)：`TestPreviousRecPnlPlausibility`。

### Docs
- [`TODOS.md`](TODOS.md)：新增 **波次 G** 與外部架構審閱 backlog（8 板塊，G-1～G-8 可勾選項，對齊 Pri／OSS／演進藍圖）；檔首導覽與修訂紀錄更新。

## 2026-04-20

### Added
- **`prediction_markets_tool`**（[`tools_legacy.py`](tools_legacy.py)）：Polymarket **Gamma** `GET /events` 熱門二元市場（Yes 隱含機率、24h 成交量級）；`_get_cache`／`_set_cache`；`MOCK_APIS=1` 時回固定三行。
- **`CryptoSection.prediction_market_highlight_lines`**：[`report_render.assemble_daily_brief_report`](report_render.py) 以 `fetch_polymarket_hot_highlight_lines` 注入（`PREDICTION_MARKETS_IN_BRIEF` 關閉可跳過）；[`templates/telegram_report.j2`](templates/telegram_report.j2) 宏觀後獨立 **【預測市場熱門】**。
- **Crew／LangGraph**：研究員與主編掛載 `prediction_markets_tool`；`graph_nodes` `raw_data["prediction_markets"]`；[`graph/graph_tools.py`](graph/graph_tools.py) `fetch_prediction_market_hot_events`。
- **main** `prewarm` 預熱 `prediction_markets`。
- [`test_prediction_markets_tool.py`](test_prediction_markets_tool.py)。

### Docs
- [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。

## 2026-04-19

### Changed
- **日報 Telegram 排版（投行掃讀）**：[`templates/telegram_report.j2`](templates/telegram_report.j2) — 執行摘要後加「掃讀順序」；**市場模式／宏觀／加密①–④／AI①–④** 前置；**投資命題與 Phase A–C** 移至文末 **【機構速讀｜命題與情境】**；**SourceHealth** 區塊回到 **QSREC 前**；區塊④前加管線生成之 **部位摘要** 行。
- [`report_render.py`](report_render.py)：`instrument_sections_for_ib_layout` — 儀表板依關鍵字插入分區小標（`MetricLine.is_section_header`）；組裝時注入 `crypto_block4_recommendation_line`／`ai_block4_recommendation_line`。
- [`schemas.py`](schemas.py)：`MetricLine.is_section_header`；`thesis_supporting_points`／`thesis_contrary_points` 改 **2–3 條**（結構化 + Phase A HTML Gate 對齊）。
- [`report_html_gates.py`](report_html_gates.py)：Phase A HTML — 支持／反駁 **2–3 條**。
- [`crew.py`](crew.py)、[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)：與新版順序與儀表板分區說明對齊。

## 2026-04-18

### Changed
- [`report_html_gates.py`](report_html_gates.py)：動態選幣 `_CRYPTO_PICK_KW` 納入**技術盤面**（RSI、均線、MA20/50、超買／超賣、多頭排列等）與**宏觀／估值讀值**（DXY、VIX、美債、殖利率、利差、SOFR、NVT、Dominance），使「本日選擇理由」可僅以儀表板對齊之讀值敘事滿足 ≥2 線索；錯誤提示文案同步更新。
- [`crew.py`](crew.py)：`GATE_VALIDATE_PICK_RULE` 加密段與上列對齊。
- [`test_validate_report.py`](test_validate_report.py)：模糊理由改為長句無關鍵詞；新增 RSI+DXY 通過案例。

## 2026-04-17

### Added
- [`assets_universe.py`](assets_universe.py)：自 [`assets_config.json`](assets_config.json) 讀取 **core_equity**／**extended_equity**（相容舊版僅 `equity`：前兩檔為 core、其餘 extended），供工具與 prompt 共用。

### Changed
- [`assets_config.json`](assets_config.json)：改為分層欄位；**extended** 納入 **GOOG**、**AVGO**、**TSM**（與既有 GOOGL 並存）。
- [`tools_legacy.py`](tools_legacy.py)：`financial_datasets_tool` 之 `watchlist`／空 query 改為批次合併宇宙；`ai_sector_market_tool` yfinance 籃＝SMH／SOXX／合併美股＋SPY（cache key 隨籃變更）。
- [`crew.py`](crew.py)：AI 儀表板規則改述為 **core ≥2 行 FD／extended ≤3 行**，yfinance 可複述符號表由設定檔驅動。
- [`report_render.py`](report_render.py)：`FinancialDatasets` 錨點對照改掃描合併宇宙（支援 GOOG／AVGO／TSM 等）。
- [`tracker.py`](tracker.py)：`GOOG`／`AVGO`／`TSM` 進場價 sanity 區間。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`CLAUDE.md`](CLAUDE.md)：`ASSETS_CONFIG_PATH` 與檔案角色說明。

### Tests
- [`test_assets_universe.py`](test_assets_universe.py)、[`test_financial_datasets_tool.py`](test_financial_datasets_tool.py)、[`test_ai_sector_market_tool.py`](test_ai_sector_market_tool.py)。

## 2026-04-16

### Changed
- **LangGraph `news_scraper_node`**：[`graph/graph_nodes.py`](graph/graph_nodes.py) 對多來源新聞改以 **`ThreadPoolExecutor`** 並行呼叫既有工具，再依原先來源順序合併與 dedupe（上限 6 則），縮短牆鐘時間。
- **`trade_picker`**：`_get_trade_picker_llm` 改為 **`lru_cache(maxsize=1)`** 單例，避免同程序多次 graph invoke 重複建構客戶端。

### Docs
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：補 **`GRAPH_LLM_TRADE_PICKER`**；更新 **`LANGGRAPH_SKIP_FORMATTER_CREW`** 註解（對齊 news／trade 節點組裝）。

### Tests / Tooling
- [`pytest.ini`](pytest.ini)：設定 **`asyncio_default_fixture_loop_scope = function`**，消除 pytest-asyncio 預設 loop scope 棄用警告。

## 2026-04-15

### Changed
- **Deploy／Cloud Run**：[`deploy.yml`](.github/workflows/deploy.yml) 於 `gcloud run jobs deploy` 加上 **`--update-env-vars=USE_LANGGRAPH_ENGINE`**，值取自 GitHub **Environments → production** 變數 `USE_LANGGRAPH_ENGINE`（未設則 `0`）。[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) 補操作說明。

## 2026-04-14

### Changed
- **LangGraph Final_Formatter**：[`graph/graph_nodes.py`](graph/graph_nodes.py) 於 **`LANGGRAPH_SKIP_FORMATTER_CREW=1`** 時改走 **native**（slim 結構化 LLM + 決定性組裝 `CryptoSection`／`AISection`），不再回傳 stub；legacy 路徑將 Bull/Bear/Arbiter 摘要經 **`langgraph_debate_context`** 注入 [`crew.py`](crew.py) Formatter Crew。新增 [`graph/graph_formatter_schemas.py`](graph/graph_formatter_schemas.py)（`CryptoFormatterNarrative`／`AIFormatterNarrative`）；`regime` 可由 `agreed_regime` 或 `regime_scorecard` 字串回退；`score_suffix` 正則支援全形括號。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：`LANGGRAPH_SKIP_FORMATTER_CREW` 註解對齊上述語意與 API 需求。
- **日報組裝衛生層**：[`report_render.py`](report_render.py) `assemble_daily_brief_report` — **neutral** 時軟化「同步做多偏好／跨資產偏多」等措辭；刪除**泛化**事件日曆列（礦企季報／Fed 談話模板句）；**呢喃**補齊「（未確認）」；AI 新聞 **beat/miss** 若標題／摘要無共識對照語則軟化；美股 **trigger** 同理且**僅以新聞 context** 判斷對照語（避免「超預期」誤觸「預期」）；**editor_consensus** 之 `$TICKER` 若不在當輪 legs／QSREC 則改寫為敘事參考。
- [`schemas.py`](schemas.py)：`ChatterItem` 驗證後若仍缺「（未確認）」則於可信度前補齊。
- [`crew.py`](crew.py)：`neutral` 措辭與 **editor_consensus** 點名規則與上列對齊。

### Tests
- [`test_graph_crew.py`](test_graph_crew.py)：Formatter mock、native assemble、`run_langgraph_category` 路徑覆蓋。
- [`test_report_render.py`](test_report_render.py)：上述組裝衛生層單元測試。

## 2026-04-13

### Changed
- [`crew.py`](crew.py)：新增 **【華爾街級財報分析】** 寫作規則（結論→工具數字證據→倍數／指引含義；禁臆造共識 EPS／beat-miss；主編共識與區塊④須回溯季報讀值），並注入 `_CREW_RULE_BLOCK` 與 Crypto／AI **結構化最終主編** prompt。
- [`earnings_focus.py`](earnings_focus.py)：【財報聚焦日】exclusion 對齊同一敘事骨架。
- [`crew.py`](crew.py)、[`earnings_focus.py`](earnings_focus.py)：**beat／miss** 僅允許於新聞 **title/summary** 已含「共識／預期／Street…」等對照語時使用；**FY／前瞻指引**僅能複述同則新聞字面，否則僅能寫「待法說／IR」。

## 2026-04-12

### Changed
- [`earnings_watchlist.py`](earnings_watchlist.py)：`MEGA_CAP_TECH_EARNINGS_TICKERS` 新增 **AI 伺服器／ODM**（`SMCI`、`DELL`、`HPE`）、**資料中心網路**（`ANET`、`CSCO`）、**矽光子／光通訊供應鏈**（`LITE`、`COHR`、`FN`）。
- [`README.md`](README.md)：watchlist 列表同步。

## 2026-04-11

### Changed
- [`earnings_watchlist.py`](earnings_watchlist.py)：擴充 **AI／雲端／半導體** 財報 watchlist（`INTC`、`MRVL`、`QCOM`、`MU`、`ORCL`、`CRM`、`NOW`、`SNOW`、`PLTR`、`CRWD`、`NET` 等；來源為公開市場常見分類（非排名、非即時選股）。
- [`earnings_focus.py`](earnings_focus.py)：**週五**錨定日亦注入 **【下週財報預告】**（與週六／日相同，指向下一曆週 Mon–Sun）。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README.md`](README.md)：同步「週五亦預告」與擴充後代號列表。

### Tests
- [`test_earnings_watchlist.py`](test_earnings_watchlist.py)、[`test_earnings_focus.py`](test_earnings_focus.py)：週五範圍與預告文案。

## 2026-04-10

### Added
- [`earnings_watchlist.py`](earnings_watchlist.py)：共用 **mega-cap／AI 財報 watchlist**、`pipeline_anchor_date`、錨定**曆週**（Mon–Sun）掃描、週末→**下週一～日**範圍輔助。

### Changed
- [`tools_legacy.py`](tools_legacy.py) `macro_context_tool`：本週財報改為 **錨定週**（`PIPELINE_REPORT_DATE` 或 UTC 當日所在週）內之 watchlist 排程；並附 **盤前／盤後**說明行（yfinance 多僅公告日）。
- [`earnings_focus.py`](earnings_focus.py)：**週六／週日錨定日**一律注入 **【下週財報預告】**（下一完整曆週）；【財報聚焦日】補 **盤前／盤後**與「已發／待發」規則。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README.md`](README.md)、[`CLAUDE.md`](CLAUDE.md)：文件補齊 watchlist 列表與週末行為。

### Tests
- [`test_earnings_watchlist.py`](test_earnings_watchlist.py)（smoke）：曆週與週末 Mon–Sun 範圍。
- [`test_earnings_focus.py`](test_earnings_focus.py)：週末預告、盤前盤後字樣。

### Added（LangGraph／War Room／PWA）
- [`execution_intents.py`](execution_intents.py)：`trade_picker_node` 於回傳前 **`append_execution_intents`** 寫入 **`.qsilicon/execution_intents.jsonl`**（僅記錄意圖，**不下單**）。
- **FastAPI**：[`api.py`](api.py) **`GET /api/war-room/latest`** — 彙總 gate failure 摘要、scratchpad 摘要、**`latest_execution_intents`**。
- **PWA**：[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js) **`useWarRoomLatest`**；[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) War Room 區塊。

### Changed（LangGraph Formatter／工具埠）
- [`graph/graph_formatter_schemas.py`](graph/graph_formatter_schemas.py)：**`FormatterInputPacket`**／**`FormatterNewsInput`**／**`FormatterTradeIntentInput`**；native **`final_formatter_node`** 以 **`packet_json`** 為 prompt 唯一結構化輸入（見 [`graph/graph_nodes.py`](graph/graph_nodes.py)）。
- [`tools/market.py`](tools/market.py)：**`ToolRegistryPort`**、**`build_tool_registry`**；graph **`data_gatherer_node`**、**`news_scraper`** 並行 fetch、**`deep_research_node`** 探針經 registry（**`MOCK_APIS`**／`market.json` **snapshots**／**news**）。
- **`news_scraper_node`**：來源 **`source`** 正規化並附 **`source_whitelisted_for_freshness`**（對齊新聞新鮮度 Gate）。

### Tests
- [`test_graph_crew.py`](test_graph_crew.py)、[`test_api_push.py`](test_api_push.py)：Formatter 封包、war-room API、news 白名單等。

### Docs
- [`TODOS.md`](TODOS.md)：本輪後續未完、**OSS 開源生態整合計畫**（Phase 1–4）、未勾選項速覽波次 **F**。

## 2026-04-09

### Added
- **財報聚焦日（可選）**：[`earnings_focus.py`](earnings_focus.py) 於 **`EARNINGS_FOCUS_MODE=1`** 或 **`auto`** 時，依 yfinance 日曆偵測錨定日是否為 watchlist（NVDA、MSFT、AAPL 等）**財報公告日**，並在 [`main.py`](main.py) 注入 **【財報聚焦日】** exclusion，要求 AI 段對命中標的呼叫 **`financial_datasets_tool('TICKER:quarterly')`**、新聞與交易須錨定工具讀值。見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **LangGraph 深度查證工具橋接**：[`graph/graph_tools.py`](graph/graph_tools.py) 以 `langchain_core.tools.tool` 包裝 `coinglass_data_tool`、`financial_datasets_tool`、`newsapi_tool`，匯出 `RESEARCH_TOOLS` 供 `bind_tools` 使用。

### Changed
- [`graph/graph_nodes.py`](graph/graph_nodes.py)：`deep_research_node` 將查證結果寫入 `raw_data['deep_dive_round_N']`；可選 **`GRAPH_DEEP_RESEARCH_TOOL_LLM=1`**（且 `GRAPH_ENABLE_TOOL_CALLS=1`）時以 `bind_tools` 多輪執行真實工具並附 `ToolMessage`；預設仍走決定性 probe（CI／無金鑰安全）。Arbiter（LLM）規則 1 改為要求「非常明確的 API 查詢關鍵字或指令」。
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)：補 `GRAPH_DEEP_RESEARCH_TOOL_LLM`、`EARNINGS_FOCUS_MODE` 註解。
- [`report_render.py`](report_render.py)：`assemble_daily_brief_report` 新增 **`_postprocess_brief_data_hygiene`**：中和未驗證之 **BTC 減半／840,000** 日曆列；**三情境**去重行首 `·`；宏觀寫 **Contango** 時將敘事失效之 **Backwardation** 改寫為現貨 VIX 門檻；**加密儀表板** FinancialDatasets `N/A` 時自 **AI 儀表板**補 NVDA/MSFT 錨點；剪除新聞 **investment_takeaway** 與日曆名目金額無關硬湊；**crypto_cycle**／**exec_summary** 弱化減半與無來源「歷史顯示」句。
- [`schemas.py`](schemas.py)：`ChatterItem` 在已有可信度標記但缺 **主流媒體二次驗證** 時自動補「否」。
- [`crew.py`](crew.py)：`exec_summary` 禁無來源統計口號；Phase A/B/C 規則補 **減半禁寫**、**VIX 期限結構一致**、**scenario_probability_notes** 勿重複行首 `·`、日曆金額勿剪貼進無關新聞解讀。

### Tests
- [`test_graph_crew.py`](test_graph_crew.py)：深度迴圈路徑斷言 `raw_data` 含 `deep_dive_round_1`。
- [`test_report_render.py`](test_report_render.py)：組裝衛生（減半日曆、三情境 bullet、VIX 同步、FD 補齊、新聞剪貼、週期／執行摘要 scrub、Chatter MSM 補齊）。
- [`test_earnings_focus.py`](test_earnings_focus.py)（smoke）：exclusion 區塊與 `maybe_prepend` 行為。

### Docs
- [`README.md`](README.md)：重寫為精簡導覽（情境表、Mermaid、`graph/` 與 **`graph_tools`／`RESEARCH_TOOLS`**、`GRAPH_DEEP_RESEARCH_TOOL_LLM` 對照表、驗證／CI 索引）；**預設分支 `main`**、直推觸發 deploy 見 [`AGENTS.md`](AGENTS.md)；環境摘錄補 **`EARNINGS_FOCUS_MODE`**。
- [`CLAUDE.md`](CLAUDE.md)：模組表補 [`earnings_focus.py`](earnings_focus.py)。
- [`TODOS.md`](TODOS.md)：檔首同步 **2026-04-09**；補 **LangGraph 路徑**未勾選項；**演進藍圖 Phase 3** 標註骨架與 deep research 工具橋接已部分落地；Pri 表與模板工程債敘述收斂。

## 2026-04-08

### Added
- **華爾街級 Phase C**：`CryptoSection` 新增 `crypto_cycle_valuation_notes`、`equity_valuation_framing`、`event_calendar_lines`；`ExecutableTradeLeg.liquidity_execution_note`；模板增【加密週期與估值錨】【美股估值與修正框架】【近端事件日曆】及交易卡「流動性／執行」。`STRICT_INSTITUTIONAL_PHASE_C_GATE=1` 啟用 HTML／結構化 Gate。`crew.py` 新增 `_INSTITUTIONAL_PHASE_C_RULE`。
- **華爾街級 Phase B**：`CryptoSection` 新增 `portfolio_framing_summary`、`scenario_probability_notes`（三行樂觀/基準/悲觀＋機率合計 100%）；`NewsItem.pricing_note`（「未定價／增量資訊」「大致已定價」「已高度反應」）；模板於命題區後渲染【組合與曝險框架】【三情境機率】，新聞列印 `<i>市場定價</i>：<code>…</code>`。`STRICT_INSTITUTIONAL_PHASE_B_GATE=1` 時 HTML 與結構化雙檢（`report_html_gates._institutional_phase_b_html_ok`、`schemas._institutional_phase_b_structured_issues`）。`crew.py` 新增 `_INSTITUTIONAL_PHASE_B_RULE`。
- **新聞新鮮度預設視窗**：`NEWS_FRESHNESS_WINDOW_HOURS` 預設由 48 改 **36**（與 `_DATA_RULES` 一致）；`ENV_TEMPLATE.txt` 註解同步。
- **華爾街級 Phase A（機構讀者）**：`CryptoSection` 新增 `investment_thesis_one_liner`、`thesis_supporting_points`（3）、`thesis_contrary_points`（3）、`key_assumptions_lines`（2–4）、`narrative_invalidation_summary`；`DailyBriefReport.institutional_disclaimer_html` 於 `assemble_daily_brief_report` 注入固定 Telegram 白名單免責（`report_render._INSTITUTIONAL_DISCLAIMER_HTML`）；`templates/telegram_report.j2` 渲染免責與命題區塊（**2026-04-15** 起免責改置 **【機構速讀】** 前，見同日 `### Changed`）。
- **可選 Gate**：`STRICT_INSTITUTIONAL_PHASE_A_GATE=1` 時 `validate_report` 檢查 HTML 區塊；同開關下 `DailyBriefReport` 結構化驗證要求上述欄位（`schemas._institutional_phase_a_structured_issues`）。見 `ENV_TEMPLATE.txt`。
- **Crew**：`crew.py` 新增 `_INSTITUTIONAL_PHASE_A_RULE` 並掛入加密結構化最終提示。
- **切片 4 量測基線**：[`main.py`](main.py) 新增可選 `SHADOW_BENCHMARK_LOG=1` 與 `SHADOW_BENCHMARK_PATH`，會將 `crewai_dual_crew`／`langgraph_dual_crew`／`company_growth_context` 的耗時與新聞量寫入 JSONL，供 company crew 與 LangGraph shadow 成本評估（不影響主流程）。

### Changed
- [`README.md`](README.md)：全文重寫與重排（專案紅線、情境表、**雙軌研究引擎** Mermaid、**LangGraph**／`graph/`、`USE_LANGGRAPH_ENGINE`、機構 Phase A/B/C 可選 Gate 與 `ENV_TEMPLATE` 索引）；精簡重複段落並對齊現行模組、CI 與 PWA 說明。
- [`report_render.py`](report_render.py)：`assemble_daily_brief_report` 組裝時將 **QSREC** 每筆可選 `regime` **強制對齊** `crypto.market.regime`（消除與【今日市場模式】主判定不一致的 warning）；並在主判定為 `neutral`／`risk_on` 時，修正 `us_equity_allocation_note` 內誤寫的 `（risk_off）` 括號為「對齊主判定：…」。
- [`crew.py`](crew.py)：收斂 **AI 儀表板**（FinancialDatasets 以 NVDA+MSFT 為 anchor、其餘檔位上限行數；開源動能至多 2 行）；**AI 產業新聞**禁以加密／VIX 作主線、新聞新鮮度改 **36h**；QSREC 提示 **省略 `regime` 欄**（由管線對齊）。
- **Gate digest 人審稿**：[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py) 新增 `gate_code` 分布摘要，並支援 `GATE_FAILURE_DIGEST_OUT` 直接輸出 Markdown 檔；保持「僅摘要、不自動改 prompt」邊界。
- **Mock smoke 進 CI**：[`ci.yml`](.github/workflows/ci.yml) 在 quick tier 新增 `./scripts/run_mock_smoke.sh`，確保 `MOCK_APIS=1` 路徑在 PR/可呼叫 CI 皆有驗證。

### Tests
- [`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)：新增 `assemble` 對 QSREC regime 與美股部位框之 smoke 覆蓋。
- [`test_validate_report.py`](test_validate_report.py)：`TestStrictInstitutionalPhaseAHtmlGate`、`TestStrictInstitutionalPhaseBHtmlGate`、`TestStrictInstitutionalPhaseBStructuredGate`、`TestStrictInstitutionalPhaseCHtmlGate`、`TestStrictInstitutionalPhaseCStructuredGate`；`_make_report` 可選 Phase B/C；`_make_minimal_structured_report_dbr` 含 `pricing_note` 與可選 Phase C 欄位。
- [`test_smoke_pipeline.py`](test_smoke_pipeline.py)、[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)：最小報告字串補 Phase A+B+C、市場定價行與流動性註記；新聞括號時間改動態（`STRICT_NEWS_FRESHNESS_GATE=1` 時 smoke 仍過）。
- [`test_report_render.py`](test_report_render.py)、[`test_news_freshness.py`](test_news_freshness.py)：樣本新聞 `pricing_note`；新鮮度測試視窗 36h；render 測試含 Phase C 欄位與 `liquidity_execution_note`。
- [`conftest.py`](conftest.py)：BigQuery stub 補 `QueryJobConfig`（pick rotation／參數化查詢路徑不再因 stub 缺類別失敗）。

## 2026-04-07

### Added
- [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md)：將「依目前 repo 架構可延續方向」落成執行版路線圖（Trust/Gate、tools 平台化、Product Shell、Multi-Agent、deploy cache、Phase 2–4 決策門檻），含 30/60/90 節奏與各 track 驗收條件。

### Changed
- [`TODOS.md`](TODOS.md)：檔首新增「執行版路線圖」連結，便於維護者從彙總待辦直接跳轉到可執行規劃。
- [`README.md`](README.md)：索引與「下一步讀哪裡」補上 [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) 入口，讓新進開發者可直接看到可執行路線。
- **戰報 Gate／敘事一致性**：[`report_html_gates.py`](report_html_gates.py) 主判定為 `neutral`／`risk_on` 時，**美股部位框**行內括號誤標 `（risk_off）` 列入 `_risk_off_narrative_violations`；`has_mixed_regime` 僅看正文 **mode／budget** 標籤（不含僅 QSREC JSON 分歧）；動態選幣理由強關鍵詞補 **期貨／衍生品／CME／恐慌／貪婪／恐懼貪婪**；QSREC 單筆 `regime` 與【今日市場模式】主判定不一致時列入 `_qsrec_consistency_issues`。
- **Crew 提示詞對齊**：[`crew.py`](crew.py) 美股部位框括號須與主判定一致；執行摘要避免在 `neutral`／`risk_on` 使用僅適用 `risk_off` 的語氣；Gate 預檢選幣理由關鍵詞池與 Gate 一致。
- **Phase 3 LangGraph 骨架落地**：新增 [`graph/graph_state.py`](graph/graph_state.py)、[`graph/graph_nodes.py`](graph/graph_nodes.py)、[`graph/graph_crew.py`](graph/graph_crew.py) 與 [`graph/__init__.py`](graph/__init__.py)，實作 StateGraph（Gather → Bull/Bear 並行 → Arbiter 條件路由 → Deep Research 迴圈 → Final Formatter）；[`main.py`](main.py) 新增 `USE_LANGGRAPH_ENGINE` 分支（預設關閉，與既有 CrewAI 並存）；[`config.py`](config.py)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`requirements*.txt`](requirements.txt) 同步新增切換與相依設定。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：`TestValidateReport` 新增／收斂 **risk_off 敘事**、**CME／期貨選幣理由**、**QSREC regime 與主判定**、**mixed regime 忽略僅 QSREC 分歧** 等案例。
- [`test_graph_crew.py`](test_graph_crew.py)：新增 `raw_data` reducer 不突變合併、LangGraph `compile()/invoke()` smoke、`research_depth` 迴圈上限守衛測試。

## 2026-04-04

### Added
- **可選嚴格核對**：[`report_html_gates.py`](report_html_gates.py) `STRICT_INVESTMENT_DASHBOARD_NUMERIC_GATE=1` 時，加密／AI 每則 `<i>投資解讀</i>` 之數字錨點須與同段 `<b>區塊①</b>` 儀表板內 `<code>` 讀值可對照；**觀望模式**略過；該 issue 為 **blocking**。見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。
- **BTC 均線儀表列**：[`report_render.py`](report_render.py) `assemble_daily_brief_report` 在儀表板尚未含 MA20/MA50 列時，以 yfinance 日線注入 **`BTC MA20（日線）`／`BTC MA50（日線）`**（`SKIP_BTC_MA_DASHBOARD_INJECT=1` 或 `MOCK_APIS=1` 時略過）。
- **呢喃 MSM Gate（可選）**：`STRICT_CHATTER_MSM_VERIFY_GATE=1` 時，區塊③含「可信度」之 `·` 條目須含「主流媒體二次驗證」；blocking。
- **演進計畫落地（信任／觀測／分叉）**：[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) 定稿、[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) 補實驗表；[`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) 在 `ADAPTIVE_GATE_THRESHOLDS=1` 時可自 BigQuery `gate_failure_log` 讀取 rotation 相關失敗占比並 **bump** `PICK_ROTATION_OVERRIDE_MIN_GAP`（`ADAPTIVE_GATE_BQ_READ=0` 關閉 BQ 讀取）；[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)；[`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)＋[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)；[`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)；[`report_render.py`](report_render.py) 備援觸發時可寫 scratchpad `equity_price_backfill`（`EQUITY_BACKFILL_SCRATCHPAD_LOG`）；[`schemas.py`](schemas.py) 可選 `asset_market`、`AISection` 觀望 vs EQUITY QSREC **warning**；[`docs/PWA_WEB_PUSH_NEXT.md`](docs/PWA_WEB_PUSH_NEXT.md)、[`docs/TW_EQUITY_DISPLAY.md`](docs/TW_EQUITY_DISPLAY.md)。`ENV_TEMPLATE.txt` 補自適應與 scratchpad 變數。

### Fixed
- **投資解讀量化 Gate 誤判**：[`validation_rules.py`](validation_rules.py) 之 `NUMERIC_INVESTMENT_*` 改為 `投資解讀\s*[：:]`，對齊 [`templates/telegram_report.j2`](templates/telegram_report.j2) 的 `<i>投資解讀</i>：`（strip HTML 後標籤與冒號間有空格時仍視為有效錨點）。

### Changed
- **待辦決策文件**（[`TODOS.md`](TODOS.md)）：新增「未完成項四維評分與新建議（2026-04）」— Pri 1–9 與波次／Phase 濃縮評分表、建議實作順序、七條新建議 backlog（Gate 內部儀表、結構化預檢 dry-run、備援可觀測性、Prompt 登記簿、`asset_market`、mock-smoke 腳本、觀望 vs QSREC 一致性）。[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) 檔首補對照連結。
- [`crew.py`](crew.py) `_NEWS_FMT`／`_CHATTER_FMT`／`_EXEC_SUMMARY_RULE`／`_HEDGE_FUND_BRIEF_RULE`／`_DASHBOARD_FMT`：AI 新聞投資解讀禁跨段主錨點（BTC/VIX/SPY 等）；加密新聞 MA 須對儀表 MA 列；呢喃禁 `MSM` 英文簡寫；執行摘要去重；交易失效條件須對已列讀數。
- [`templates/telegram_report.j2`](templates/telegram_report.j2)：`position_pct`、`trigger` 顯示前 **strip `$`**（Pri 8）。
- [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)：補 digest script／儀表連結與 `PROMPT_CHANGELOG` 登記說明。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：`TestStrictInvestmentDashboardNumericGate`、`TestChatterMsmVerifyGate`；`TestInvestmentNumericAndUnactionableTrade` 補 `<i>投資解讀</i>：` 間距仍過量化 Gate。
- [`test_report_render.py`](test_report_render.py)：`test_ensure_btc_ma_dashboard_rows_inserts_after_btc_spot`。
- [`test_adaptive_gate_thresholds.py`](test_adaptive_gate_thresholds.py)：BQ bump／ceiling；預設 `ADAPTIVE_GATE_BQ_READ=0` 之 smoke。
- [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)：觀望 vs EQUITY QSREC warning。
- [`test_validate_report_dry_run_smoke.py`](test_validate_report_dry_run_smoke.py)：Gate 骨架與 `validate_report` 對齊。

## 2026-04-03

### Added
- **美股 trade_legs 價位備援**（[`report_render.py`](report_render.py)）：`assemble_daily_brief_report` 在 `MOCK_APIS` 未開啟且未設 `SKIP_EQUITY_YF_BACKFILL=1` 時，以 [`tracker.py`](tracker.py) `yfinance` 批次補 **現價／進場**；若 **目標／停損** 皆缺且 R:R、最大回撤可解析，依風險比例機械推算（LONG／SHORT 對稱）。例外時記錄 warning 並略過備援。
- **加密儀表板爆倉缺數提示**：全文儀表板未出現「爆倉」或「清算」時自動追加一行 ⬜ **備註**（引導以費率／OI／多空比代理觀察）。

### Fixed
- **validate_report**：投資解讀「當日量化」改為先 **strip HTML** 再比對（[`validation_rules.py`](validation_rules.py) `plain_text_for_investment_numeric_gate`）；數字樣式允許 **負號**（如資金費率 -0.0008%）。**不可執行交易** Regex 涵蓋 **`現價：<code>$N/A</code>`**、全形 `｜` 分隔（[`validation_rules.py`](validation_rules.py) `UNACTIONABLE_TRADE_RE`）；[`report_postprocess_legacy.py`](report_postprocess_legacy.py) 移除不可執行區塊時對齊同一規則。
- **結構化 QSREC／STRICT_CONSISTENCY**：[`schemas.py`](schemas.py) `TradeRecommendation` 於 `score_gap` 缺漏且已有 `selection_score` 與 `alt_candidate_score` 時，在模型解析前自動補 **score_gap = selection_score − alt_candidate_score**（與 crew 分差契約一致，非捏造），避免 `DailyBriefReport` 業務驗證僅因漏填 gap 失敗而觸發 **GATE_EXECUTION_FAILED**。

### Changed
- **讀者面向日報**：[`validation_rules.py`](validation_rules.py) 同標延續前綴改為 **「連日維持與昨日相同建議標的」**（仍命中 `_REPEAT_PICK_REASON_RE`），移除 **pipeline／BQ** 內部字樣；[`report_render.py`](report_render.py) 組裝時對空白 **`trade_legs.position_pct`** 依 regime＋星級補齊（[`tracker.py`](tracker.py) `default_position_pct_for_leg`）；**美股兩檔及以上**再依單筆上限壓縮並按 **合計上限**（neutral 10%／risk_on 15%／risk_off 4%，見 `equity_combined_cap_percent`）等比縮放；[`schemas.py`](schemas.py) 呢喃 **（未確認）** 且 **可信度：A** 時自動降 **B**；[`crew.py`](crew.py) **【讀者面一致】**、呢喃 A 級、新聞跨域；`_NEWS_FMT` 補跨板塊一句；**投資解讀 Gate／美股交易卡價位／24h 爆倉儀表板** 規則補強（與上述備援與 Regex 對齊）。
- **Telegram 模板質感**（[`templates/telegram_report.j2`](templates/telegram_report.j2)）：標題後統一分隔線；執行摘要標題顯式 **【執行摘要】**（對齊 `STRICT_EXEC_SUMMARY_HTML_GATE`）；**【今日市場模式】** regime 以 `<code>` 凸顯；區塊編號粗體、主敘事／新聞「投資解讀／主編共識」以 `<i>` 標示；加密段與 **🤖 AI 市場** 之間補 **────────────**（利於 `_crypto_report_prefix` 邊界）；多腿交易之間 **────────** 換氣。
- **讀者面語氣／分域／選股廣度**（[`crew.py`](crew.py)）：執行摘要補「語氣與節奏」「分域敘事」（禁止無因果混寫加密與美股）；避險基金規則補「精緻度」；研究員候選多樣性補產業／市值廣度；AI 區塊④動態選股補 (d) 兩檔廣度。
- **OSS Scout → TODOS**：[`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) `_build_todos_block` 改為**連結＋摘要表＋短勾選**（不再嵌入 `fit_rationale` 長標籤）；[`templates/oss_weekly_plan.md.j2`](templates/oss_weekly_plan.md.j2) 底部新增 **維護者勾選追蹤**；[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md) 與 [`TODOS.md`](TODOS.md) 靜態說明對齊；[`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md) 補同區塊（與下輪管線輸出一致）。

### Tests
- [`test_validate_report.py`](test_validate_report.py)：投資解讀 HTML 包裝＋負數費率仍過量化 Gate；`現價：<code>$N/A</code>` 觸發不可執行交易擋單。
- [`test_report_render.py`](test_report_render.py)：爆倉備註追加、美股 N/A 價位 assemble 備援與目標／停損合成。
- [`test_report_render_boundaries.py`](test_report_render_boundaries.py)：`position_pct` 解析／補填、`tracker` regime 上限與星級 clamp、美股多腿合計縮放（neutral／risk_on／risk_off）、非法百分比與 `ChatterItem` 可信度邊界。
- [`test_report_render.py`](test_report_render.py)：呢喃 A→B、`assemble` 補 **position_pct**、美股兩檔合計縮放與單筆 clamp；[`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)：`normalize_leading_repeat_pick_phrase` 前綴字串。
- [`test_oss_weekly.py`](test_oss_weekly.py)：`test_build_todos_block_compact_table_and_short_checkboxes`。
- [`test_trade_recommendation_schema.py`](test_trade_recommendation_schema.py)：`test_score_gap_derived_when_omitted_but_scores_present`。

## 2026-04-02

### Added
- **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)**：`workflow_dispatch` 手動觸發（`test_tier` quick／full）；`callable` job 以 `CI_TEST_TIER` 統一讀取 dispatch 與 `workflow_call` 輸入。

### Fixed
- **CI smoke**：將 [`tests/fixtures/mock_data/market.json`](tests/fixtures/mock_data/market.json) 納入版控（先前 CHANGELOG 已列但檔案未提交），修復 `test_market_fixture_loads_when_mock_on`。

### Maintenance
- [`tools/__init__.py`](tools/__init__.py)：`vars(tools_legacy)` 鏡射（取代 `dir()`）；[`api_schema.py`](api_schema.py)、[`validation_rules.py`](validation_rules.py) 註解對齊 `tools_legacy`／`tools`。
- [`TODOS.md`](TODOS.md)：檔首同步 **2026-04-02**；修訂紀錄合併 **2026-03-29** 雙條；補 OSS 自動區塊勿手改提示。

## 2026-03-29

### Changed
- **Tools 套件化 Phase 1（Office Hours Alt B）**：根目錄 monolith 更名為 [`tools_legacy.py`](tools_legacy.py)；新增 [`tools/`](tools/) 套件（[`tools/base.py`](tools/base.py) `MOCK_APIS`／`load_mock_json`、[`tools/market.py`](tools/market.py) `market_fixture_dict`；[`tools/__init__.py`](tools/__init__.py) 自 `tools_legacy` re-export 維持 `import tools` 相容）。說明與分階見 [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md)；[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`CLAUDE.md`](CLAUDE.md)、[`README.md`](README.md) 已對齊。
- **Hugging Face／`ai_momentum_tool`**（[`tools_legacy.py`](tools_legacy.py)）：`_hf_fetch_models(..., prefer_downloads=...)` 預設 **trendingScore → likes → downloads**（弱化下載榜主導），`prefer_downloads=True` 時下載優先；`ai_momentum_tool` 依 `metric` 是否含 `download` 選擇排序；快取鍵區分分支；HF／OpenRouter 標題補「敘事參考／非股價」避免誤讀為股價。
- **FinancialDatasets 儀表指引**：[`tools_legacy.py`](tools_legacy.py) `_fd_summarize_ticker` 要求 watchlist 每檔 **至少三行** MetricLine（營收、同比%、FCF 等），避免基本面濃縮成單行。
- **Crew AI 區塊①**（[`crew.py`](crew.py)）：研究員掛載 **`ai_sector_market_tool`**；`_TOOL_TRUTH_RULE`／`_NEWS_FMT`／`_DASHBOARD_FMT`／`_AI_LAYOUT_RULE`／`build_ai_structured_final_prompt` 與並行任務「必呼叫」對齊建議順序：**yfinance 族群（SMH／SOXX／NVDA／MSFT／GOOGL／SPY）→ FinancialDatasets（每檔≥3 行）→ ai_momentum**。

### Added
- **AI／半導體族群市場工具**：[`tools_legacy.py`](tools_legacy.py) `ai_sector_market_tool`（yfinance 日線批次；上列一籃標的之收盤與 1D／約 5 交易日報酬；`_get_cache`／`_set_cache`、經 [`tools/__init__.py`](tools/__init__.py) re-export）。
- [`tests/fixtures/mock_data/market.json`](tests/fixtures/mock_data/market.json) — mock 市場片段（`MOCK_APIS=1` 時由 `market_fixture_dict` 載入）。

### Tests
- [`test_ai_sector_market_tool.py`](test_ai_sector_market_tool.py)：`ai_sector_market` yfinance 輸出格式；`_hf_fetch_models` 首輪 `sort`（`conftest` yfinance stub 下以 `patch.object(..., create=True)` 掛 `download`）。
- [`test_tools_package_phase1.py`](test_tools_package_phase1.py)（`@pytest.mark.smoke`）。

### Docs / env
- [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) — `MOCK_APIS` 專節。

## 2026-04-01

### Fixed
- **本日選擇理由雙抬頭**：LLM 若以「重複選用理由：／重複選股理由：／重複持有理由：」開頭，`assemble_daily_brief_report` 會依與昨日 BQ QSREC 是否相同，改寫為 **「連日維持（同昨日 BQ QSREC）；…」** 或僅剥除冗餘前綴（[`validation_rules.py`](validation_rules.py) `normalize_leading_repeat_pick_phrase`、[`report_render.py`](report_render.py) `_normalize_pick_reason_repeat_headers`）。
- **呢喃可信度補填**：[`schemas.py`](schemas.py) `ChatterItem` 與 [`crew.py`](crew.py) `_ensure_chatter_credibility` 改補 **「｜可信度：…｜主流媒體二次驗證：否」**，不再向讀者顯示「（自動補填）」。

### Tests
- [`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)、[`test_report_render.py`](test_report_render.py)：上述行為之單元／assemble 迴歸。

### Maintenance
- **[`TODOS.md`](TODOS.md)**：已落地與檔首同步狀態補 **2026-04-01** 條目。
- **OSS Scout（2026-04-01）**：`OSS_SCOUT_AUTO_*` 候選表更新；研究稿 [`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md)。

## 2026-03-31

### Changed
- **近 30 天績效週報**（[`tracker.py`](tracker.py) `generate_performance_summary`）：附 **指標說明**／**回撤說明**（加權平均、Expectancy、PF、複利淨值 Max DD 與單筆最差之區別）；**Regime 分層**對 `unknown` 與少於 10 筆分組加註樣本解讀，並附一句解讀建議。
- **同標延續補註**（[`report_render.py`](report_render.py)）：自動前綴改為 **「連日維持（同昨日 BQ QSREC）…」**，避免 Telegram 模板「本日選擇理由：」與「重複選用理由：」雙重抬頭；仍符合 [`report_html_gates.py`](report_html_gates.py) `_REPEAT_PICK_REASON_RE`。
- **Crew 寫作規則**（[`crew.py`](crew.py)）：儀表板規格補 **NVT 與 RSI 並存時**之尺度區分；呢喃格式統一 **（未確認）｜來源｜可信度｜二次驗證** 欄位順序；`_DATA_RULES`／`_TOOL_TRUTH_RULE`／`_QUOTE_RULE` 三合一注入改為常數 `_CREW_RULE_BLOCK`（語意不變）。
- **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)**：預設**略過** job 內「Free disk space on runner」（節省約 1–3 分鐘；映像 build 若因 runner 磁碟不足失敗，可暫時還原該步驟）。

### Fixed
- **結構化日報驗證**：`crypto.risk_budget_summary` 若僅中文、未含 `risk_on`／`risk_off`／`neutral` 等 canonical token，[`report_render.py`](report_render.py) 於 `_coerce_sections_for_gate` 依 `market.regime` 自動前綴補齊，避免 `DailyBriefReport` 拋「加密今日風險預算未包含主 regime token」；[`validation_rules.py`](validation_rules.py) 新增 `ensure_crypto_risk_budget_regime_token`；[`test_gate_coercions_smoke.py`](test_gate_coercions_smoke.py)／[`test_report_render.py`](test_report_render.py) 補測。

### Maintenance
- **[`TODOS.md`](TODOS.md)**：移除已完成 `[x]` 主列表（細節改以本檔 2026-03-28～31 與「已落地（備查）」為準）；新增 **OSS Scout 週報** `<!-- OSS_SCOUT_AUTO_BEGIN -->`／`<!-- OSS_SCOUT_AUTO_END -->`，與 [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 合併邏輯對齊。

### Docs
- **LLM 成本／延遲（營運槓桿）**：[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 新增專節；[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) 對照說明（關閉 editor／judge、`PIPELINE_SKIP_SENTIMENT_SCORE`、`MODEL_*` 降階等）；Runbook **Deploy 併發**敘述與 [`deploy.yml`](.github/workflows/deploy.yml) `cancel-in-progress: true` 對齊。

## 2026-03-30

### Changed
- **日報品質（無幻覺管線）**：[`report_render.py`](report_render.py) 在與昨日 BQ QSREC 標的相同且允許覆核時，若理由缺輪動認可片語則自動前綴補註（`AUTO_REPEAT_PICK_DISCLAIMER`，預設開；見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；初版用語為「重複選用理由：…」，**2026-03-31** 改為「連日維持…」以降低與模板「本日選擇理由：」重複感（見該日 **Changed**）。另：[`tracker.py`](tracker.py) 上期追蹤略過明顯占位進場價／合理區間外；[`tools_legacy.py`](tools_legacy.py) 資金費率絕對值小於 0.01% 時顯示六位小數並標「近零」；[`crew.py`](crew.py)／[`templates/telegram_report.j2`](templates/telegram_report.j2) 對齊執行摘要跨資產框定、減少與儀表板數字重複、區塊②b 改「主題式觀點摘要」敘述。

### Fixed
- **Deploy 觸發 CI 全跳過**：[`.github/workflows/ci.yml`](.github/workflows/ci.yml) 可重用流程內 `github.event_name` 繼承呼叫端（如 `push`）而非 `workflow_call`；`callable` job 改為 `if: github.event_name != 'pull_request'`，使 [`deploy.yml`](.github/workflows/deploy.yml)／[`nightly-ci.yml`](.github/workflows/nightly-ci.yml) 的 `uses:` 會實際執行 lint／pytest。

### Security
- **Git 歷史淨化**：已以 `git filter-repo` 自全部本地分支之歷史移除 `.env.example`，再提交僅含占位符之範本；`main` 與既有本地分支已 **force-push** 至 `origin`。**所有協作者須刪除舊 clone 並重新 clone**（舊 commit SHA 已全部作廢）。建議在 GitHub 啟用 Secret scanning／Push protection。

### Added
- **可選研究工具註記**：[last30days-skill](https://github.com/mvanhorn/last30days-skill) 與日報管線信任邊界、pilot 快照、併入層級 A+B 預設與路徑 C 之 ADR 前置條件 — [`docs/research/LAST30DAYS_SKILL.md`](docs/research/LAST30DAYS_SKILL.md)、[`docs/research/README.md`](docs/research/README.md)；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引與 §9 連結。
- **CI 輕量依賴**：[`requirements-ci.txt`](requirements-ci.txt) — Actions 上 `ruff`／`pytest` 無需安裝 CrewAI／Streamlit／sentence-transformers 等（與 [`conftest.py`](conftest.py) stub 對齊；smoke + full 338 項已驗證）。
- **Nightly 全測**：[`.github/workflows/nightly-ci.yml`](.github/workflows/nightly-ci.yml) — 每日 02:00 UTC（可 `workflow_dispatch`）呼叫 `ci.yml` 且 `test_tier: full`。

### Changed
- **[`.github/workflows/ci.yml`](.github/workflows/ci.yml)**：`pull_request` 略過僅 `docs/**`、`data-verification-ui/**`；`workflow_call` 新增輸入 `test_tier`（`quick`／`full`）；預設 `pip install -r requirements-ci.txt`；PR smoke 不再跑大型釋放磁碟步驟。
- **[`.github/workflows/deploy.yml`](.github/workflows/deploy.yml)**：`test` job 以 `test_tier: quick` 呼叫 CI；`concurrency.cancel-in-progress: true`；Docker 改 `docker/build-push-action` + GHA cache；`paths` 納入 `requirements-ci.txt`。
- **[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)**：cron 改為每月 **1 與 15 日** 06:00 UTC（較原每週一省分鐘）。
- **[`README.md`](README.md)**、[`AGENTS.md`](AGENTS.md)、[`CLAUDE.md`](CLAUDE.md)：同步 CI／nightly／`requirements-ci.txt` 說明。

## 2026-03-29

### Added
- **邊界條件測試**：[`docs/BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md)；pytest markers `boundary`／`slow`（[`pytest.ini`](pytest.ini)）；[`test_tools_http_contract.py`](test_tools_http_contract.py)、[`test_report_html_gates_boundaries.py`](test_report_html_gates_boundaries.py)、[`test_main_pipeline_boundaries.py`](test_main_pipeline_boundaries.py)、[`test_boundary_hypothesis.py`](test_boundary_hypothesis.py)（Hypothesis 僅針對 `sanitize_telegram_html`）；離線戰報 near-miss fixtures（`near_miss_equity_pick_short`、`near_miss_five_tagged_news`）。CI 依賴補 [`hypothesis`](requirements-ci.txt)。
- **開源前檢查**：[docs/OPEN_SOURCE_CHECKLIST.md](docs/OPEN_SOURCE_CHECKLIST.md) 補齊 **本機清場清單**、`git filter-repo` 清 `.env.example` 歷史與 **清歷史後驗證**（gitleaks／TruffleHog）；並提醒除 XAI／OpenAI／Gemini／Telegram 外，曾出現在歷史中的其他 provider 亦須輪替。
- **Glassbox PWA（[`data-verification-ui/`](data-verification-ui/)）**：
  - 儀表板視覺：深底＋青綠／電紫層次、卡片與 metric 漸層、底欄毛玻璃（[`src/index.css`](data-verification-ui/src/index.css)）。
  - **`VITE_GLASSBOX_MOCK=1`**：今日戰情室與圖表頁示範資料（[`src/utils/mockToday.js`](data-verification-ui/src/utils/mockToday.js)、[`mockPerformance.js`](data-verification-ui/src/utils/mockPerformance.js)）。
  - **API 全失敗 fallback**：未設 mock 時，[`Today.jsx`](data-verification-ui/src/pages/Today.jsx) 在三支 API 皆錯且 loading 結束後自動載入示範 KPI／OPEN／QSREC。
  - **TradeCard**「展開 AI 決策邏輯」與 **Charts** 績效區骨架屏；靜態草圖 [`design/tradecard-ai-disclosure-mockup.html`](data-verification-ui/design/tradecard-ai-disclosure-mockup.html)。
- **CI**：[`.gitignore`](.gitignore) 例外 **`tests/fixtures/reports/**/expected_validation.json`**；補齊各 case 之 **`expected_validation.json`**（[`test_validate_report_fixtures.py`](test_validate_report_fixtures.py)）。
- **OSS 週期管線**：[`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py)（搜尋 → [`oss_repo_digest.py`](scripts/oss_repo_digest.py) → [`templates/oss_weekly_plan.md.j2`](templates/oss_weekly_plan.md.j2)）；[`scripts/oss_suitability.py`](scripts/oss_suitability.py) 啟發式適配度；合併勾選清單至 **`TODOS.md`**「OSS Scout 週報」區塊。
- **測試**：[test_oss_weekly.py](test_oss_weekly.py)。

### Changed
- **Gate 阻擋語意**：[report_html_gates.py](report_html_gates.py) 將「資料缺失標記過多」納入 `_BLOCKING_PREFIXES`，使 `blocking_issues` 與 `main.run_pipeline_with_retries` 分數型重試語意一致（`valid=False` 時一併視為結構阻擋）。
- **美股選股理由 Gate**：[report_html_gates.py](report_html_gates.py) `_EQUITY_PICK_KW` 以事件驅動語彙為主（核電、SMR、擴產、供電、液冷、良率等），並剔除易泛化之 IPO／產能／基礎設施／能源／電力等詞，避免惰性敘事繞過；[test_validate_report.py](test_validate_report.py) 迴歸對齊。
- **Telegram 模板**：[templates/telegram_report.j2](templates/telegram_report.j2) 進場／目標／停損欄位防禦性去除 AI 帶入的 `$`；失效欄位補 `replace('若', '')` 與既有「若／則失效。／。。」清洗，避免雙錢號與重複句讀。
- **Glassbox PWA**：導入 **Tailwind CSS**（[`tailwind.config.js`](data-verification-ui/tailwind.config.js) `preflight: false` + [`postcss.config.js`](data-verification-ui/postcss.config.js)、[`src/index.css`](data-verification-ui/src/index.css) `@tailwind utilities`）；[`TradeCard.jsx`](data-verification-ui/src/components/TradeCard.jsx) 改為玻璃擬態卡片、三欄價格網格、`isExpanded` 手風琴（觸發／失效／敘事）與防禦性 `N/A`；[`package.json`](data-verification-ui/package.json) 新增 `tailwindcss`／`postcss`／`autoprefixer`。
- **[`README.md`](README.md)**：War Room PWA 小節擴充為「最簡 mock／接 BQ／proxy 與 `VITE_API_URL`」分節；新手表新增 Glassbox 列。
- **[`crew.py`](crew.py)**：Crypto／AI 研究員預設拆成多個 **`async_execution=True`** 子任務（CrewAI 於 `Process.sequential` 內並行後收斂至審計與主編）；**`CREW_DISABLE_ASYNC_RESEARCH=1`** 回退單一 Grok 巨任務（見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）。[`main.py`](main.py) 雙 Crew 仍為既有 `ThreadPoolExecutor` 並行。
  - **Crypto**：`tasks` 順序 **`crypto_data_task` → `crypto_macro_task` → `crypto_news_task`**；宏觀任務僅經濟日曆／相關係數／估值錨／COT／灰階／歷史類比；**`sentiment_score_tool`**（或 `PIPELINE_SKIP_SENTIMENT_SCORE` 對應說明）改列**新聞子任務**可選區；新聞子任務另要求短呢喃與固定 `expected_output` 字串。
  - **AI**：**`ai_data_task`**（動能＋`financial_datasets` watchlist）與 **`ai_news_task`**（雙次 `market_search` + `newsapi`／`rss`／`gnews`／`rumor_scanner`）邊界分離；`review_task`／`final_report_task` 的 `context` 對齊兩（或三）個前驅輸出。
- **[`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)**：`SCOUT_SORT`、`SCOUT_PER_PAGE`、`--out-json`；預設 sort **stars**。
- **[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)**：每週一 UTC cron、`contents: write` push、artifact；`pip install jinja2`。
- **[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)**、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`TODOS.md`](TODOS.md) Direction 2B。

## 2026-03-28

### Added
- **[`tools_cache_http.py`](tools_cache_http.py)**：自舊 monolith 拆出 in-memory cache、`_http_get`、JSON 回應解析；[`tools_legacy.py`](tools_legacy.py)（經 `tools` 套件）轉發 `_CACHE`／`_CACHE_MAX_SIZE`／`_get_http_session` 供測試與相容。
- **錨定報告日**：環境變數 **`PIPELINE_REPORT_DATE`** — [`main.py`](main.py) 注入 exclusion 開頭；[`report_html_gates.py`](report_html_gates.py) 新聞新鮮度以該日 HKT 日末為參考時刻。
- **工具呼叫下限**：**`MIN_TOOL_CALLS_PER_PIPELINE`** + [`scratchpad.raw_tool_invocation_count`](scratchpad.py)（每次 `traced_tool_execution` 遞增）。
- **執行摘要 Gate（可選）**：**`STRICT_EXEC_SUMMARY_HTML_GATE`** — 正文須含【執行摘要】且至少 2 條要點。
- **Telegram「查看歷史」**：**`TELEGRAM_REPORT_HISTORY_URL`** — [`telegram_sender.py`](telegram_sender.py) 首則文字 chunk 附 Inline url 按鈕。
- **Web Push API 預留**：[`api.py`](api.py) `POST /api/push/subscribe`（預設 501；**`WEB_PUSH_ENABLED=1`** 時 200 noop）；CORS 允許 POST。
- **週期回測 workflow**：[`.github/workflows/weekly-backtest.yml`](.github/workflows/weekly-backtest.yml)（手動；`backtest.py --optimize --write-signal-weights`，需 `GCP_SA_KEY`）。
- **測試**：[test_api_push.py](test_api_push.py)、[`test_validate_report.py`](test_validate_report.py) `TestStrictExecSummaryHtmlGate`。

### Changed
- **產報效能預設**（[`main.py`](main.py)／[`crew.py`](crew.py)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）：`CREW_FUTURE_TIMEOUT_SEC` 預設 **2400**（40m）、`PIPELINE_HARD_DEADLINE_SEC` **13200**（3h40m，對齊 4h Cloud Run）；`BACKOFF_BASE_SEC` 預設 **25**；Gemini `max_retries` **4**。可選 **`PIPELINE_SKIP_SENTIMENT_SCORE=1`** 略過 `sentiment_score_tool` 以縮短加密段。
- **Gate 模組拆分**：[`report_html_gates.py`](report_html_gates.py) 承接原 `validate_report()`（HTML／環境變數／BigQuery）；結構化業務規則與 `ReportOutput`／`parse_report_output`／`assert_*` 收斂至 [`schemas.py`](schemas.py)（`DailyBriefReport` `@model_validator`）。已移除舊檔 `report_validator.py`、`report_output_validator.py`、`core/report_validation.py`、`check_report.py`。
- **[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)**：關閉 **`schedule` cron**（預設不再每 2 小時自動跑），僅保留 **`workflow_dispatch`**；要恢復排程可取消 YAML 內註解。[`README.md`](README.md) 表格已對齊。
- **[`TODOS.md`](TODOS.md)**：勾選與「已落地」對齊現況；新增 **階段 E** 長期索引（對 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)）。
- **[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)**：`PIPELINE_REPORT_DATE`、選幣輪動 staging 小節。
- **[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)**：鏈上 Tab／QSREC 頻率、`/api/push/subscribe`。
- **[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)**、[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`README.md`](README.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`crew.py`](crew.py)（候選多樣性一句）、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（METRIC 擴充）。
- **測試**：[`test_critical_paths.py`](test_critical_paths.py)、[`test_pipeline_observability_smoke.py`](test_pipeline_observability_smoke.py) 對齊 `_http_get`／`tools_cache_http._HTTP_SESSION`。
- **Telegram 讀者版精簡**：[`templates/telegram_report.j2`](templates/telegram_report.j2) 移除頂部 Source 三行；交易卡改四行（計畫／執行／敘事），風控與情境僅留結構化／QSREC。[`main.py`](main.py) 將 Source observability 與 Q-Score 改為僅 `logger.info`，不另發品質卡訊息；移除管線 `_maybe_editor_polish_html`（[`report_editor.py`](report_editor.py) 仍可供測試）。
- **Schema 文體與隱私**：[`schemas.py`](schemas.py) 新增 `internal_reasoning`（`TradeRecommendation`／`ExecutableTradeLeg`／`NewsItem`）、`narrative` few-shot 範例、標籤／指令洩漏清洗；[`QSREC_JSON_EXCLUDE_FIELDS`](schemas.py) 使對外 QSREC JSON 不含思考區；[`report_render.py`](report_render.py) 對齊 `model_dump` exclude。
- **Crew**：[`crew.py`](crew.py) 新增【機構級寫作｜Bloomberg 式】與【思考區 vs 展示區】；刪除未使用 `_POLISH_RULE`；幣圈 risk 任務 `expected_output` 對齊辯論結尾格式。

## 2026-03-27

### Changed
- **[`TODOS.md`](TODOS.md)**：pull 後重整——合併三大戰略方向與週次建議、**維護者執行意見**、**選幣／選股過於固定**橫切診斷與待辦；校正已落地項（`gate_failure_log`、`HIT_STOP` exclusion、`oss_scout` 腳本等）避免重複開票。
- **GitHub Actions runner 磁碟**：[`ci.yml`](.github/workflows/ci.yml)、[`deploy.yml`](.github/workflows/deploy.yml)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 於重步驟前執行 **Free disk space**（移除預裝 dotnet／android／CodeQL 等）；CI／monitor 的 `pip install` 改 **`--no-cache-dir`** 降低峰值；deploy 在 `docker push` 後 **`docker builder prune` / `system prune`**。緩解 `No space left on device` 與 runner 無法寫 `_diag` log。
- **GitHub Actions 分鐘數**：[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 改為每 **2** 小時排程、`pip install -r` [`requirements-monitor.txt`](requirements-monitor.txt)（僅 yfinance／BQ／Telegram，略過 CrewAI 全量依賴）；新增 `concurrency` 避免重疊 run；runner 對齊 `ubuntu-22.04`。

## 2026-03-26

### Added
- **啟動硬擋 `PIPELINE_STRICT_ENV`**：[`main._validate_critical_env_strict`](main.py) — `1` 且未 `SKIP_TELEGRAM`／`SKIP_BIGQUERY` 時分別要求 Telegram 與 GCP 專案＋憑證；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README`](README.md) 已註記。`NEWS_FRESHNESS_WINDOW_HOURS` 納入 [`_validate_env_types`](main.py) 數字校驗。
- **新聞新鮮度專項測試**：[`test_news_freshness.py`](test_news_freshness.py)；[`test_critical_paths.py`](test_critical_paths.py) 補 `_validate_critical_env_strict` 與錯誤 `NEWS_FRESHNESS_WINDOW_HOURS`。
- **Autoresearch／bench／營運文件**：[`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（尾端官方 `METRIC` 行 + 防偽註解）、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。
- **Backlog 規格補齊**：[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)、[`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md)；Scout 輔助腳本 [`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)（`GITHUB_TOKEN` 可選）。
- **Gate 失敗結構化日誌（自我改善資料基底）**：[`bigquery_writer.write_gate_failure_log`](bigquery_writer.py) 寫入 `{PROJECT}.market_data.gate_failure_log`（attempt、blocking/warning 計數、`bucket_counts_json`、`fingerprint`、`issues_preview` 等）；[`main.py`](main.py) 於 `run_pipeline_with_retries` 內每次 `validate_report` 有 `issues` 時呼叫。環境變數 **`GATE_FAILURE_BQ_LOG`**（預設開）、`SKIP_BIGQUERY=1` 時略過。測試：[`test_gate_failure_log.py`](test_gate_failure_log.py)。

### Changed
- **[`README.md`](README.md)**：重寫為較易掃描結構（開頭需求對照表、更新 mermaid、模組表含 editor／gate log／signal_weights／company crew、環境變數與觀測摘錄、`GATE_FAILURE_BQ_LOG`、輔助腳本與分組文件索引）；主線不依賴 X 與 `.cursorrules` 對齊。
- **`_check_news_freshness` 白名單行比對**：同時辨識 `YYYY-MM-DD HH:MM`／`YYYY/MM/DD`／`MM/DD` 等行內時間格式，避免戰報用 ISO 日期時 `NEWS_FRESHNESS_SOURCE_WHITELIST` 永不命中（[`report_html_gates.py`](report_html_gates.py)）。
- **Crew 管線**：自加密／AI 研究員 Agent 移除 `x_search_tool` 與相關 task 指令；與 [`.cursorrules`](.cursorrules)「廢棄 X/Twitter」一致，並減少每輪工具 schema 與 prompt token。
- **`main._prewarm_tool_caches`**：不再預熱 X 搜尋；啟動預熱並行數減 2。
- **`report_editor`**：精簡 system／user 指令字數，紅線與主編角色不變，降低潤稿 API 輸入 token。

### Removed
- **`_log_api_key_inventory`**：`TWITTER_BEARER_TOKEN` 列（管線不再使用；`tools.x_search_tool` 仍可供手動呼叫）。

## 2026-03-25

### Changed
- **[`TODOS.md`](TODOS.md)**：重整為全 repo 唯一待辦彙總——區分「已完成並驗證」「Backlog（BL-01…）」「ROADMAP 完成度矩陣」及靜態 repo 掃描紀錄；合併原條目、Autoresearch 計劃缺口與路線圖延伸項。

## 2026-03-21

### Fixed
- **`validate_report` / Gate**：新聞時區比對前剥除新聞行上 `<code>` 等行內 HTML，並接受 **HKT／香港時間** 等寫法；宏觀 **SOFR** 列若 SOFR 與匹配之 `%` 之間出現 **VIX／恐慌指數** 敘述則略過（避免將 VIX% 誤判為利率）；**美債** 行支援 **無冒號** 的 `10Y 報 x%` 格式；傳聞可信度增列 **信賴度／呢喃…可信度／置信分級／來源：…(B級)** 等模式。
- **戰報內容／版面**：後處理 **`_auto_prefix_missing_news_tags`** 對【核心新聞】之 `[日期 時間 UTC+8]` 行與【AI 產業新聞】之「標題 + 摘要：」自動補 **〔新聞 N〕**，避免計數永遠不足 6 則；**無 BigQuery 上期資料時仍剥除** LLM 捏造之【上期建議追蹤】；**`load_previous_recs_block`** 改為 `report_date + canon_asset + direction` 去重（同標的同向多筆只留一列）。

### Added
- **選幣／選股理由驗證**：`validate_report` 檢查加密與美股區「本日選擇理由」是否含足夠關鍵線索（催化/鏈上 vs 財報/新聞等）或退階說明，並是否點名 QSREC 內該類所有標的。交易觀望時略過；`STRICT_PICK_JUSTIFICATION=0` 關閉。
- **選幣／選股與昨日輪動**（`STRICT_PICK_ROTATION`，預設開）：若今日 QSREC 與昨日 BQ `RECOMMENDATIONS_TABLE` 之 **canonical 標的集合**完全相同且非空，理由須含 **重複選用理由** 等片語，否則驗證失敗；無 BQ／昨日無資料／查詢失敗則略過。`crew.py` 動態選幣／選股段落已註明此行為。
- **新聞 Gate 分級**：`validate_report` 將 **交易觀望**（`trade_watch_mode`）與 **新聞資料不足分段**（`partial_news_ok`）解耦；後者須 3~5 則〔新聞 N〕、〔新聞 1~3〕齊備、UTC+8 全過、且文內宣告不補虛構 + 【新聞資料狀態】或 `[REPORT_TIER:PARTIAL_NEWS]`（後處理在 3~5 則時自動注入）。環境變數 **`ALLOW_PARTIAL_NEWS_GATE`**（預設 `1`）可關閉分段。僅 **觀望模式** 等才放寬 R:R／勝率／投資解讀量化；僅分段不再因「出現新聞資料狀態」就放寬交易欄位。

### Changed
- **`tracker`**：`check_and_update_positions` 與 `load_previous_recs_block` 對多筆建議 **合併 Yahoo symbol 後批次 `yf.download`**，仍缺價之 symbol 再單檔 fallback，降低追蹤價格時的 HTTP 次數與限流風險。
- **`config.py` / `crew.py`**：LiteLLM 模型字串集中於 `config`（`MODEL_GROK`、`MODEL_GPT`、`MODEL_GEMINI`、`MODEL_CLAUDE`），可依環境變數覆寫；`OPENAI_MODEL` 仍為 GPT 慣用別名（優先於 `MODEL_GPT`）。
- **上期建議追蹤**：BigQuery 以 **canonical asset**（`$`/空白/`-` 正規化）做 `PARTITION BY`；`save_recommendations` 同日同標的只保留最後一筆；合併戰報後 **`main._inject_canonical_prev_recs_block`** 以 BQ 權威 HTML **覆寫** LLM 產出之【上期建議追蹤】，避免模型自行膨脹多列。
- **`validate_report`（STRICT_CONSISTENCY_GATE）**：宏觀異常僅在含 **美債** 之行解析 10Y/2Y；**SOFR** 僅解析關鍵字鄰近之利率 **%**（避免同列 VIX／敘事 % 誤判）。新聞時區接受 **GMT+8、全形加號、MM/DD/YYYY、可選秒數**，並在 **`【新聞資料狀態】` 行起**截斷後再比對〔新聞〕；計數前仍剔除【新聞資料狀態】等噪音行。傳聞可信度接受 **來源：B級**、**`可信度 72/100`**、**`等級：B`**、**`Grade: B`** 等。`_normalize_news_timezone_utc8` 與新聞時區規則對齊。
- **`crew`**：配對比值 LONG 與建倉敘事一致；AI 區強制〔新聞 4〕～〔新聞 6〕+ UTC+8；產業鏈呢喃需含可信度；加密區註明上期區塊後端可覆寫。

## 2026-03-20

### Changed
- **上期建議追蹤**（`tracker.load_previous_recs_block`）：同一 `report_date + asset` 以 `ROW_NUMBER` 去重，優先 `OPEN`、否則最新 `created_at`，避免同日多筆 QSREC 造成同標的多空重複列。
- **`validate_report`**：要求全篇至少 6 個 `〔新聞 N〕`；主 regime 為 neutral/risk_on 時禁止交易／風險預算段誤用「依 risk_off」等敘述；AI 儀表板區掃描常見幻覺欄位字串；美債 10Y/2Y 與「利差 %」口徑一致性檢查（約 10Y−2Y）。
- **後處理**：若注入後仍缺任一 `SourceHealth`/`SourceErrors`/`SourceQuota`，會再清一次殘行並重新注入完整區塊。
- **`crew`**：新聞強制 `〔新聞 1〕`…`〔新聞 6〕`（AI 區為 4–6）；AI 儀表板禁字清單加強；倉位示例避免 neutral 時寫「risk_off」。

## 2026-03-15

### Changed（GitHub Actions）
- **CI**（`ci.yml`）：`pull_request` 仍全跑；`push main` 僅在 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow 等路徑變更時跑 Lint+Test。
- **部署**（`deploy.yml`）：**移除** `push` 自動觸發，改為僅 **`workflow_dispatch`**（Actions → Run workflow）；執行時仍先 `workflow_call` `ci.yml` 再建映像與 Cloud Run Job 部署。
- `README.md`：同步說明「push 不自動部署、手動 Deploy workflow」。

## 2026-03-08

### Added
- 新增來源可觀測欄位：`SourceHealth`、`SourceErrors`、`SourceQuota`，並納入報告後處理與驗證規則。
- 新增來源健康分數機制（NewsAPI/GNews/Apify），支援 7 天半衰期，讓來源排序偏向近期穩定表現。
- 新增來源錯誤分類統計：`429`、`400`、`timeout`、`5xx`、`other`。
- 新增來源配額控管與成本保護：可設定每日上限，且依健康分數動態收斂可用配額。

### Changed
- `market_search_tool` 由固定 fallback 順序改為「健康分數驅動的動態來源優先序」。
- 報告 resilience 後處理強化：若缺少來源可觀測欄位，會自動注入固定區塊。
- `README.md` 更新為目前 agent 模型、工具組合、資料源策略與新環境變數。

### Persistence
- 來源健康狀態持久化升級：
  - 本地：`.source_health.json`
  - 雲端：BigQuery `source_health_stats`（可透過 `DISABLE_SOURCE_HEALTH_BQ=1` 關閉）

### Validation
- 已完成語法檢查、既有單元測試與 lint 檢查，未引入新錯誤。
