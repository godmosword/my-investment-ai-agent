# Q-Silicon — 工程與產品待辦（導覽）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md) · **路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) · **Bloomberg 對齊驗收** → [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) · [**進度分析表（日報／財報／Terminal 對齊）**](#progress-vs-wall-st-bloomberg) · **執行路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) · **長期里程碑索引** → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)

**同步狀態（2026-04-12）**：本檔於 **2026-04-23 改寫**；**2026-04-14（八）** 下一輪：**NVDA mock 跨路由 E2E**、`price_alignment` **來源欄位**與 **`PRICE_ALIGNMENT_E2E_OVERRIDES`**、**Web Push store 去重／IP rate limit**、**gate_issue_hints 單字邊界**（見 CHANGELOG **2026-04-14**）；**2026-04-14（七）** 依建議順序落地 **Terminal 主線 T1–T3** 首批實作並穿插 **T4b（通知語意草案）**／**T5a／T5b**（見 CHANGELOG **2026-04-14** 與下節 T1–T5 錨點）；**2026-04-14（六）** 精煉 T1–T5 **建議執行順序**（主線／並線／交錯表）；**2026-04-14（五）** 新增 [**Terminal／戰情室後中段路線（T1–T5）**](#terminal-post-mid-tier-t1-t5)（每切片對應檔案）；**2026-04-14（四）** Playwright E2E；**2026-04-14（三）** 可加強項；**2026-04-14（二）** Phase A–E；**2026-04-14** 日報品質代理；**2026-04-12** [**CHANGELOG 2026-04-10** Pipeline](CHANGELOG.md)。先前版本中數百條可勾選項（G-1～G-8 全表、OSS Phase 1–4 細拆、演進 Phase 1–4、商業化階段 E、週報 spike 清單等）**並未在程式庫中全部實作**；為避免「待辦檔＝永遠勾不滿的巨型清單」與正文重複，改為 **導覽 + 下一批隊列 + 外部文件索引**。細項論述與威脅建模仍見 `docs/` 與 `docs/oss_candidates/`。**紅線**見 [`.cursorrules`](.cursorrules) 與 [`CLAUDE.md`](CLAUDE.md)（無數據幻覺、Telegram HTML 白名單、`main.py` 雙線程安全、`validate_report` 契約）。

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
  - 例外：15（新增即時資料面仍以公開/現有來源為主，尚無「已審核清單」型治理文件）；**6** 已補 API **`price_alignment`** + Playwright **UI 對照**（[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)）。  
- **建議內部 KPI（可自訂盤點）**：(1) Phase 0 通過條數／15；(2) 生產是否固定開 `STRICT_INSTITUTIONAL_PHASE_A/B/C`；(3) 財報聚焦觸發率／工具命中率（log／BQ）；(4) 儀表板與敘事含 **as_of／來源** 覆蓋率（對齊 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)）；(5) QSREC→監控→告警／紙上交易閉環程度。

**一句話**：**可驗證日報＋ Gate** 軸線偏中上；**類 Terminal 資料壟斷＋即時互動＋執行層** 軸線仍早中段，差距主要在資料深度、產品互動與執行閉環，而非「有無 LLM 寫報告」。

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
| 日報品質代理（複合分／TODOS 後續） | [`report_quality_agent.py`](report_quality_agent.py)、[`main.py`](main.py)（成功交付後掛勾）、`REPORT_QUALITY_AGENT*`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；scratchpad `quality_agent_result` |
| Phase A–E 觀測與 Terminal 契約 | [`main.py`](main.py) scratchpad `init.meta.pipeline_config`；[`graph/graph_nodes.py`](graph/graph_nodes.py) `graph_deep_research_metrics`（含 `finish_kind` 等）；[`scripts/ci_terminal_contract_check.sh`](scripts/ci_terminal_contract_check.sh)、[`.github/workflows/ci.yml`](.github/workflows/ci.yml)（含 **npm cache**）；[`test_terminal_numeric_consistency.py`](test_terminal_numeric_consistency.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py)、[`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)、[`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)；PWA [`WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`README.md`](README.md) badges |
| Snapshot 價格對齊／Web Push 分階 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment`；[`api.py`](api.py) `SymbolSnapshot`；[`web_push_store.py`](web_push_store.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`data-verification-ui/src/pushClient.js`](data-verification-ui/src/pushClient.js) |
| Playwright E2E（Bloomberg §6 UI） | [`data-verification-ui/e2e/`](data-verification-ui/e2e/)（`cross-page-btc-price`、`terminal-spy-mismatch`）、[`data-verification-ui/playwright.config.js`](data-verification-ui/playwright.config.js)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；[`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx) |
| Terminal 後中段 **T1–T3**／**T5** 首次切片（2026-04-14） | [`execution_intents.py`](execution_intents.py)（`status`／`category`／`sort_by`）；[`api.py`](api.py)（`API_HTTP_REQUEST_LOG`、`gate_issue_hints` 富化、`GET /api/execution-intents` query）；[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)（輪詢 coalesce、5xx backoff）；PWA [`Today.jsx`](data-verification-ui/src/pages/Today.jsx)、[`PositionHealthStrip.jsx`](data-verification-ui/src/components/PositionHealthStrip.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4c、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)（T4b 草案）；[`test_execution_intents_api.py`](test_execution_intents_api.py) |
| Terminal 下一輪（2026-04-14）— E2E／T5b／T4a 小步 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment` 來源欄位 + `PRICE_ALIGNMENT_E2E_OVERRIDES`；[`web_push_store.py`](web_push_store.py) endpoint 去重、**`WEB_PUSH_SUBSCRIBE_RATE_PER_MIN`**、**`WEB_PUSH_STORE_MAX_SUBSCRIPTIONS`**；[`api.py`](api.py) `push_subscribe` 傳 **client_ip**；[`data-verification-ui/e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)；[`test_api_push.py`](test_api_push.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py) |
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
| Terminal 中段 M3（quote API + 卡片 last） | [`api.py`](api.py) `GET /api/symbols/{symbol}/quote`；[`symbol_snapshot_service.fetch_symbol_quote`](symbol_snapshot_service.py)；[`test_api_symbol_quote.py`](test_api_symbol_quote.py)；PWA [`useSymbolQuote`](data-verification-ui/src/hooks/useApi.js)、[`TerminalSymbolCard`](data-verification-ui/src/components/TerminalSymbolCard.jsx)；[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)；CHANGELOG **2026-04-12** `### API（Terminal M3）` |
| Terminal 中段 M4（SSE war-room） | [`api.py`](api.py) `GET /api/stream/war-room`；[`war_room_stream.py`](war_room_stream.py)；PWA `VITE_SSE_ENABLED`／[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)；`ENV_TEMPLATE` `TERMINAL_SSE_*`／`API_STREAM_AUTH_KEY`；[`test_api_stream_war_room.py`](test_api_stream_war_room.py) |
| Terminal 中段 M5（紙上 tick） | [`paper_execution.py`](paper_execution.py)、[`scripts/paper_execution_tick.py`](scripts/paper_execution_tick.py)、`POST /api/paper/execution-tick`；意圖 **`reference_*`**／**`PAPER_*`** 狀態；[`test_paper_execution.py`](test_paper_execution.py)；`ENV_TEMPLATE` `PAPER_TICK_*` |
| 開源社群骨架 | [`LICENSE`](LICENSE)、[`CONTRIBUTING.md`](CONTRIBUTING.md)、[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) |
| 訂閱取代堆疊 — **研究稿**（非已實作） | [`docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md`](docs/oss_candidates/2026-04-22-revision-plan-subscription-stack.md) |

---

## 下一批隊列（建議接續實作，邊界清楚）

依維護者順序與工程可切性排列；**完成後**把對應句寫進 CHANGELOG，並在本節刪行或改「✓」。

1. ~~**P0 Critical env 定稿**~~ — **已交付（2026-04-14）**：[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) 修訂；[`main.py`](main.py) `_validate_env_types` 納入 `ADAPTIVE_*` 數值校驗；scratchpad `pipeline_config`。
2. ~~**橫切閾值實驗**~~ — **已交付（2026-04-14）**：[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) 補 scratchpad 實驗紀錄欄位。
3. ~~**P3 Gate 失敗 → 人審提示**~~ — **已交付（2026-04-14）**：[`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md) 補 CI 錨點（digest 腳本／BQ 流程既有）。
4. ~~**自適應門檻 BQ 接線**~~ — **已確認落地**：[`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) + [`report_html_gates.py`](report_html_gates.py)；**2026-04-14** 補啟動數值校驗與 scratchpad 可觀測性。
5. ~~**LG-3 補齊**~~ — **已交付（2026-04-14）**：[`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)（`smoke`，mock `bind_tools`）。
6. ~~**LG-1 觀測**~~ — **已交付（2026-04-14）**：`graph_deep_research_metrics` scratchpad 事件；`pipeline_config` 旗標快照。
7. ~~**G-7 小項**~~ — **已交付（2026-04-14）**：[`README.md`](README.md) badges + LICENSE 對齊句；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)；[`CLAUDE.md`](CLAUDE.md) 索引。
8. ~~**G-8 漸進**~~ — **已交付（2026-04-14）**：[`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)（`boundary` + `hypothesis`）。
9. ~~**PWA War Room 二期**~~ — **已交付（最小切片，2026-04-14）**：[`WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx) 錯誤態重試／成功態重新整理；視覺拋光仍可在後續波次加強。
10. ~~**PWA Web Push（分階 1）**~~ — **已交付（2026-04-14）**：[`web_push_store.py`](web_push_store.py)、`WEB_PUSH_ENABLED`／`WEB_PUSH_STORE`、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、PWA [`pushClient.js`](data-verification-ui/src/pushClient.js)（`VITE_WEB_PUSH_*`）。**未完成（分階 2）**見隊列 **11**。
11. **PWA Web Push（分階 2 — 生產級）** — VAPID、訂閱儲存（Redis／BQ）、發送管線與合規審核（[`Direction 1A`](#維護者意見執行順序不變)）；不阻塞日報主線。
12. ~~**Terminal E2E（Playwright）**~~ — **已交付（2026-04-14）**：[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)、[`e2e/terminal-spy-mismatch.spec.js`](data-verification-ui/e2e/terminal-spy-mismatch.spec.js)、[`e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)（mock **BQ vs OHLC/quote 分歧** UI 迴歸）、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；`SymbolCandleChart` 修正 **lightweight-charts v5** `addSeries(CandlestickSeries)`（避免 Terminal 卡白屏）。
13. ~~**Bloomberg 對齊 Phase 2**~~ — **已交付（2026-04-10 CHANGELOG）**：Terminal v2 分組／模板、跨頁 Symbol Context（`SymbolFocusBar` + `TerminalSymbolCard` 設為全域關注）、Streamlit 與 `symbol_snapshot_service`／可選 HTTP 對齊 snapshot 形狀。
14. ~~**Terminal 中段 M2**~~ — **已交付**：見「已交付摘要」列與 CHANGELOG **2026-04-12** `### PWA`；規格見 [`docs/TERMINAL_MID_TIER_ROADMAP.md` — M2](docs/TERMINAL_MID_TIER_ROADMAP.md#m2-terminal-pwa)。
15. ~~**Terminal 中段 M3**~~ — **已交付**：見「已交付摘要」與 CHANGELOG **2026-04-12** `### API（Terminal M3）`；規格 [M3](docs/TERMINAL_MID_TIER_ROADMAP.md#m3-symbol-quote)。
16. ~~**Terminal 中段 M4**~~ — **已交付**：見「已交付摘要」與 [`docs/TERMINAL_MID_TIER_ROADMAP.md` M4](docs/TERMINAL_MID_TIER_ROADMAP.md#m4-realtime-stream)。
17. ~~**Terminal 中段 M5**~~ — **已交付**：見「已交付摘要」與 [M5](docs/TERMINAL_MID_TIER_ROADMAP.md#m5-paper-execution)。

---

<a id="terminal-post-mid-tier-t1-t5"></a>

## Terminal／戰情室 — 後中段路線（T1–T5，每切片對應檔案）

> **語意**：M1–M5 已交付（見上節與 [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)）。以下為 **持續 improve** 的建議切片；**不綁日曆天數**，以可 review 的 PR 為單位。完成後寫入 [`CHANGELOG.md`](CHANGELOG.md) 並更新本節或改「✓」。

### Phase T1 — 穩定與可觀測

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T1a** | 戰情室／Terminal **錯誤態矩陣**（重試、降級、避免輪詢風暴） | [`data-verification-ui/src/pages/Today.jsx`](data-verification-ui/src/pages/Today.jsx)、[`data-verification-ui/src/components/WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx) |
| **T1b** | **觀測**：API 失敗率／延遲與 `data_provenance` 敘事對齊（文件或輕量 log） | [`api.py`](api.py)、[`war_room_stream.py`](war_room_stream.py)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`README.md`](README.md) |
| **T1c** | **E2E 擴面**：mock 多 ticker 或 `price_alignment` 分支 | [`data-verification-ui/e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)（新增 spec）、[`data-verification-ui/e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml) |

### Phase T2 — 資料與一致性（Bloomberg §6 口徑）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T2a** | **跨路由／跨來源**數字口徑寫入契約（何時以 snapshot OHLC、何時以 quote、何時 N/A） | [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| **T2b** | **`price_alignment.aligned === false`** 時 Today／Terminal **UI 提示**（非靜默） | [`symbol_snapshot_service.py`](symbol_snapshot_service.py)、[`data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/e2e/`](data-verification-ui/e2e/) |
| **T2c** | **Streamlit ↔ PWA** 同形 snapshot 路徑迴歸說明／輕測 | [`dashboard.py`](dashboard.py)、[`symbol_snapshot_service.py`](symbol_snapshot_service.py)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（`SYMBOL_SNAPSHOT_HTTP_BASE`）、[`README.md`](README.md) |

### Phase T3 — 互動與效率

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T3a** | **Workspace／關注**：匯入匯出、模板、快捷操作（產品定義內） | [`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)、[`data-verification-ui/src/context/SymbolFocusContext.jsx`](data-verification-ui/src/context/SymbolFocusContext.jsx)、[`data-verification-ui/src/components/SymbolFocusBar.jsx`](data-verification-ui/src/components/SymbolFocusBar.jsx) |
| **T3b** | **意圖表**：篩選、排序、欄位契約 | [`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`api.py`](api.py)（若需 query 參數）、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| **T3c** | **輪詢／快取**：減少重複 snapshot、調整 stale／interval | [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（`VITE_TERMINAL_POLL_MS` 等） |

### Phase T4 — 通知與閉環（合規後）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T4a** | **Web Push 分階 2**（VAPID、持久化、rate limit、去重） | [`web_push_store.py`](web_push_store.py)、[`api.py`](api.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`data-verification-ui/src/pushClient.js`](data-verification-ui/src/pushClient.js)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) |
| **T4b** | **通知事件語意**（與 war-room／gate  digest 對齊，避免噪音） | [`war_room_stream.py`](war_room_stream.py)、[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)、[`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)、[`bigquery_writer.py`](bigquery_writer.py)（若寫 BQ 訂閱／事件表） |

### Phase T5 — 與日報／意圖敘事閉環（長線）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T5a** | **report_links**／當日報告在 Terminal 的**可發現深連結** | [`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/pages/Report.jsx`](data-verification-ui/src/pages/Report.jsx)、[`api.py`](api.py)（`GET /api/reports/{date}`）、[`symbol_snapshot_service.py`](symbol_snapshot_service.py) |
| **T5b** | **意圖狀態 ↔ gate 失敗** 讀向索引（僅讀、不冒充 OMS） | [`execution_intents.py`](execution_intents.py)、[`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)、[`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md) |

**建議執行順序**（**主線**須依序；**並線**＝文件／規格可與主線平行；**交錯**＝不阻塞主線 PR 的穿插切片）：

| 類型 | 說明 |
|------|------|
| **主線** | **T1** 完成（T1a／T1b／T1c 同 Phase 內可交錯 PR）→ **T2** → **T3**。 |
| **並線** | **T4** 的規格／合規 checklist／事件語意（文件為主）可自 **T1 起**與主線**並行撰寫**；**T4 實作**（訂閱持久化、真推送等）須待**合規／產品拍板**，建議排在 **T3 之後**，或與 **T5b** 同波若觀測已就緒。 |
| **交錯** | **T5** 與 **T2–T4** 可穿插：**T5a**（報告深連結）宜在 **T2a**（數字口徑契約）之後或與 T2a 同一波交付；**T5b**（gate × 意圖讀向）宜在 **T1b**（觀測）與 **T4b**（通知語意草案）有初稿後再做，與 **T3** 無衝突時可並行。 |

**一句話**：先 **穩 UI／觀測（T1）**，再 **定口徑與測試（T2）**，再做 **互動與效能（T3）**；**推送（T4）** 規格早開、實作晚合；**日報閉環（T5）** 對齊契約後交錯落地。

> **2026-04-14 進度備註（非 exhaustive）**：T1a／T1b／T1c、T2a／T2b／T2c、T3a／T3b／T3c 已有**可 review 初版**（見上「已交付摘要」列與 CHANGELOG）；T4a／T4b **實作**仍待合規拍板（T4b 目前為 `docs/PWA_WEB_PUSH.md` 草案）；**mock** 下已補 **NVDA「儀表＝BQ vs yfinance 分歧」** E2E；**實盤** BQ 與 yfinance 數值仍可能因市場時間／快取而不同步，需另開觀測或對照腳本。

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
- **2026-04-23**：**全文改寫** — 宣告舊版「巨型可勾選 backlog」**未**等同全部實作；改為導覽 + **下一批隊列** + 長期索引；移除 G-1～G-8 全表與重複 Phase／OSS 細拆 checkbox（詳見 git 歷史）；OSS 週報契約與 `OSS_SCOUT_AUTO_*` 規則保留。
- **2026-04-22**：訂閱取代研究稿、CHANGELOG Docs — 見上「已交付摘要」連結。
- **2026-04-21 及更早**：見 git 歷史本檔與 [`CHANGELOG.md`](CHANGELOG.md)。
