# Q-Silicon — 工程與產品待辦（導覽）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md) · **路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) · **Bloomberg 對齊驗收** → [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) · **執行路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) · **長期里程碑索引** → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)

**同步狀態（2026-04-12）**：本檔於 **2026-04-23 改寫**；**2026-04-12** 於「已交付摘要」補登 [**CHANGELOG 2026-04-10** Pipeline](CHANGELOG.md)（日報組裝衛生、`crew`／FD 規則）。先前版本中數百條可勾選項（G-1～G-8 全表、OSS Phase 1–4 細拆、演進 Phase 1–4、商業化階段 E、週報 spike 清單等）**並未在程式庫中全部實作**；為避免「待辦檔＝永遠勾不滿的巨型清單」與正文重複，改為 **導覽 + 下一批隊列 + 外部文件索引**。細項論述與威脅建模仍見 `docs/` 與 `docs/oss_candidates/`。**紅線**見 [`.cursorrules`](.cursorrules) 與 [`CLAUDE.md`](CLAUDE.md)（無數據幻覺、Telegram HTML 白名單、`main.py` 雙線程安全、`validate_report` 契約）。

---

## 維護者意見（執行順序，不變）

1. **先穩「選標多樣性 + Gate 可信」** — Direction **1A／2A**；**1B 商業化暫緩** → 階段 E。
2. **Direction 2B** — [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) → `docs/oss_candidates/`；[`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)。**勿手改** `OSS_SCOUT_AUTO_BEGIN`～`OSS_SCOUT_AUTO_END` 區塊。
3. **Direction 3** — [`crew_company.py`](crew_company.py)；擴四職能前先量測 **`CREW_FUTURE_TIMEOUT_SEC`**。
4. **P0** — [`PIPELINE_STRICT_ENV`](main.py) + 金鑰盤點；生產／排程強制。

---

## 已交付摘要（備查，非 exhaustive）

以下為 **已進 main 管線／產品** 之摘要；**逐日條目**以 CHANGELOG 為準。**維護契約**：與 [`CHANGELOG.md`](CHANGELOG.md) **雙向對齊** — 改版寫入 CHANGELOG 時同步更新本檔；本檔補登「已交付」須對應 CHANGELOG 既有或同日條目（見 CHANGELOG 檔首說明）。

| 主題 | 代表檔案／行為 |
|------|----------------|
| 雙軌 Crew + 可選 LangGraph | [`main.py`](main.py)、[`graph/`](graph/)、`USE_LANGGRAPH_ENGINE`、`GRAPH_*` |
| LangGraph 工具橋接與深度查證 | [`graph/graph_tools.py`](graph/graph_tools.py)、`RESEARCH_TOOLS`、`deep_research_node` |
| 日報 HTML／Gate／schema | [`report_html_gates.py`](report_html_gates.py)、[`schemas.py`](schemas.py)、[`report_render.py`](report_render.py)、[`templates/telegram_report.j2`](templates/telegram_report.j2) |
| 日報組裝衛生（三情境、儀表板分區） | [`report_render.py`](report_render.py)：BTC 現價 **>50k** 且情境列含 **突破** 時 **`7.6k`→`76k`**；**`instrument_sections`** 前剔除與 IB 區塊標題同名之**空白佔位列**、**連續重複** `is_section_header`；[`test_report_render.py`](test_report_render.py)（CHANGELOG **2026-04-10**） |
| Crew 新聞／工具敘述邊界 | [`crew.py`](crew.py)：加密 **1–3** `investment_takeaway` 禁止無據 **垃圾債／HY／spread** 跳喻；**FinancialDatasets** 營收相關 MetricLine **`label` 須含期間口徑**（annual／quarterly／FY／年份等）；[`tools_legacy.py`](tools_legacy.py) `_fd_summarize_ticker` 尾註提醒 **fiscal／口徑**（CHANGELOG **2026-04-10**） |
| 模板 `$` 與交易卡顯示 | `strip_usd` 濾鏡、`ExecutableTradeLeg` 欄位正規化（CHANGELOG **2026-04-22**） |
| 預測市場熱門 | [`tools_legacy.py`](tools_legacy.py) `prediction_markets_tool`、組裝注入、Crew／Graph 掛載 |
| 財報焦點／watchlist | [`earnings_watchlist.py`](earnings_watchlist.py)、[`earnings_focus.py`](earnings_focus.py) |
| 資產宇宙 | [`assets_config.json`](assets_config.json)、[`assets_universe.py`](assets_universe.py) |
| PWA War Room（首期） | [`data-verification-ui/src/components/WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx) |
| Bloomberg 對齊（Phase 0–2） | Phase 0–1：[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)、[`api.py`](api.py) `GET /api/symbols/{symbol}/snapshot`、`symbol_snapshot_service`、`test_api_symbols_snapshot`、PWA Terminal／K 線。**Phase 2**：Terminal v2 分組／模板、[`SymbolFocusContext`](data-verification-ui/src/context/SymbolFocusContext.jsx)／[`SymbolFocusBar`](data-verification-ui/src/components/SymbolFocusBar.jsx)、Streamlit 快照區（`SYMBOL_SNAPSHOT_HTTP_BASE`／`DASHBOARD_SYMBOL_FOCUS`）；[`README.md`](README.md) **`/terminal`／`VITE_API_URL`**；[`App.jsx`](data-verification-ui/src/App.jsx) **`lazy` 載入 Terminal** |
| Terminal 中段 M1（資料溯源 + 執行意圖 API） | [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)；snapshot **`data_provenance`**（[`symbol_snapshot_service.py`](symbol_snapshot_service.py)）；`GET`／`PATCH` [`api.py`](api.py) **`/api/execution-intents`**；[`execution_intents.py`](execution_intents.py) 去重列表、`update_execution_intent_status`；[`test_execution_intents_api.py`](test_execution_intents_api.py)（CHANGELOG **2026-04-12**） |
| Terminal 中段 M2（PWA 輪詢 + 溯源 UI + 意圖 PATCH） | [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js) `livePoll`／`getTerminalRefetchIntervalMs`；[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)；`VITE_TERMINAL_POLL_MS`（README／`DASHBOARD_CONTRACT`）；CHANGELOG **2026-04-12** `### PWA` |
| 開源社群骨架 | [`LICENSE`](LICENSE)、[`CONTRIBUTING.md`](CONTRIBUTING.md)、[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| 訂閱取代堆疊 — **研究稿**（非已實作） | [`docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md`](docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md) |

---

## 下一批隊列（建議接續實作，邊界清楚）

依維護者順序與工程可切性排列；**完成後**把對應句寫進 CHANGELOG，並在本節刪行或改「✓」。

1. **P0 Critical env 定稿** — [`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) + `PIPELINE_STRICT_ENV` 契約對齊 [`main.py`](main.py)。
2. **橫切閾值實驗** — [`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md)（`PICK_ROTATION_*` 等 staging 實驗）。
3. **P3 Gate 失敗 → 人審提示** — [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)、[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)、`gate_failure_log` 閉環。
4. **自適應門檻 BQ 接線** — [`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) 骨架接實際查詢／門檻。
5. **LG-3 補齊** — LangGraph **mock LLM + tool_calls** 多輪整合測試（CI 不依真 API）。
6. **LG-1 觀測** — `GRAPH_DEEP_RESEARCH_TOOL_LLM=1` 成本／延遲／失敗率與 cache 命中率文件化或輕量 metrics。
7. **G-7 小項** — README **badges**、與 `LICENSE` 同步一句；`docs/` **ADR 索引**一頁。
8. **G-8 漸進** — `hypothesis` 擴充 [`schemas.py`](schemas.py)／邊界契約（見 [`docs/BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md)）。
9. **PWA War Room 二期** — 錯誤態 UX、視覺拋光（首期已交付）。
10. **PWA Web Push** — Service Worker／持久訂閱（[`Direction 1A`](#維護者意見執行順序不變) 對齊）；不阻塞日報主線。
11. ~~**Bloomberg 對齊 Phase 2**~~ — **已交付（2026-04-10 CHANGELOG）**：Terminal v2 分組／模板、跨頁 Symbol Context（`SymbolFocusBar` + `TerminalSymbolCard` 設為全域關注）、Streamlit 與 `symbol_snapshot_service`／可選 HTTP 對齊 snapshot 形狀。
12. ~~**Terminal 中段 M2**~~ — **已交付**：見「已交付摘要」列與 CHANGELOG **2026-04-12** `### PWA`；規格見 [`docs/TERMINAL_MID_TIER_ROADMAP.md` — M2](docs/TERMINAL_MID_TIER_ROADMAP.md#m2-terminal-pwa)。
13. **Terminal 中段 M3** — `GET /api/symbols/{symbol}/quote` + pytest + PWA last 價；見 [M3](docs/TERMINAL_MID_TIER_ROADMAP.md#m3-symbol-quote)。
14. **Terminal 中段 M4** — SSE（優先）或 WebSocket + 可選 stream auth；見 [M4](docs/TERMINAL_MID_TIER_ROADMAP.md#m4-realtime-stream)。
15. **Terminal 中段 M5** — 紙上 worker、狀態擴充、成交規則 MVP；見 [M5](docs/TERMINAL_MID_TIER_ROADMAP.md#m5-paper-execution)。

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

<!-- OSS_SCOUT_AUTO_END -->

---

## 修訂紀錄

- **2026-04-12（五）**：**Terminal M2 PWA** — 「已交付摘要」增列；隊列 **12** 改 ~~刪線~~；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** 增 `### PWA`；README／`DASHBOARD_CONTRACT`／roadmap §3b 同步。
- **2026-04-12（四）**：[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md) 擴充 **M2–M5** 實作規格（DoD、檔案、API、測試、依賴圖、手動 checklist）；「下一批隊列」增 **M3–M5**、M2 補 roadmap 錨點；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** `### Docs` 合併敘述。
- **2026-04-12（三）**：**Terminal 中段 M1** — 「已交付摘要」增列；「下一批隊列」增 **M2**；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-12** `### Added` 補 `data_provenance`、`execution-intents` API、[`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)；[`CLAUDE.md`](CLAUDE.md) `docs/` 索引增該檔。
- **2026-04-12**：「**已交付摘要**」補登兩列 — **日報組裝衛生**（`report_render`／`test_report_render`）與 **Crew／FD 規則**（`crew`、`tools_legacy`），對齊 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-10** `### Pipeline`；**同步狀態**日期更新。[`CHANGELOG.md`](CHANGELOG.md) 增 **2026-04-12** `### Docs` 並於檔首明訂 **CHANGELOG ↔ TODOS** 維護契約；[`AGENTS.md`](AGENTS.md)、[`CLAUDE.md`](CLAUDE.md) 交接／導覽一句補強。另完成 Bloomberg 對齊首批落地（alignment doc、symbol snapshot API、PWA Terminal workspace、lightweight-charts K 線事件標註）。**後續小步**：`README` 補 **`/terminal`／`VITE_API_URL`**；`App.jsx` **`lazy`+`Suspense`** 載入 Terminal（CHANGELOG **2026-04-12** `### Changed`）。
- **2026-04-23**：**全文改寫** — 宣告舊版「巨型可勾選 backlog」**未**等同全部實作；改為導覽 + **下一批隊列** + 長期索引；移除 G-1～G-8 全表與重複 Phase／OSS 細拆 checkbox（詳見 git 歷史）；OSS 週報契約與 `OSS_SCOUT_AUTO_*` 規則保留。
- **2026-04-22**：訂閱取代研究稿、CHANGELOG Docs — 見上「已交付摘要」連結。
- **2026-04-21 及更早**：見 git 歷史本檔與 [`CHANGELOG.md`](CHANGELOG.md)。
