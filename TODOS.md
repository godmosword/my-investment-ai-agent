# Q-Silicon — 工程與產品待辦（導覽）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md) · **Terminal 總表** → [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) · **路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) · **Bloomberg 對齊驗收** → [`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) · [**進度分析表（日報／財報／Terminal 對齊）**](#progress-vs-wall-st-bloomberg) · **執行路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md) · **長期里程碑索引** → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) · [**git pull／讀 codebase 時先看**](#pull-or-read-codebase-reminder)

**同步狀態（2026-05-04）**：**Portal Phase 1** 對 [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 驗收清單已閉環：`siliconApiHeaders.js` + [`useApi.js`](data-verification-ui/src/hooks/useApi.js)／[`pushClient.js`](data-verification-ui/src/pushClient.js) 送 `X-Q-Silicon-Key`；401→[`/api-key`](data-verification-ui/src/pages/ApiKeyPage.jsx)（`VITE_E2E=1` 不跳）；**`/`→`/briefs`**、**Today→`/today`**、BottomNav；[`eslint.config.js`](data-verification-ui/eslint.config.js) 模組邊界；後端可選 **`QSILICON_MASTER_KEY`**（`/api/stream/war-room` 豁免，見 [`test_api_master_key_middleware.py`](test_api_master_key_middleware.py)）。隊列 **26** 設計稿之 `shared/api/client.ts` 仍以驗收清單註記為「設計錨點」；實作路徑見上。

**同步狀態（2026-05-06）**：**文件對齊** — [`TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) 曾列待辦之 API／401／`/`／eslint 項 **已於 2026-05-04 程式交付**（見 CHANGELOG **2026-05-04** `### PWA`／`### API`）；本行保留為歷史錨點。

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
  - 例外：15（新增即時資料面仍以公開/現有來源為主，尚無「已審核清單」型治理文件）；**6** 已補 API **`price_alignment`** + Playwright **UI 對照**（[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)）。  
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

**總表**（中段路線 + 三檔完整評論）：[`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md)。

| 檔案 | 看法摘要 |
|------|-----------|
| [`architecture/AI_CONTEXT.md`](docs/architecture/AI_CONTEXT.md) | 行為準則與工程紅線與本 repo 一致；「現況」區會漂移—以 CHANGELOG／程式為準；`qsilicon/` 模組邊界宜搭配 CI／目錄約束。 |
| [`architecture/REVIEWER_LOOP_DESIGN.md`](docs/architecture/REVIEWER_LOOP_DESIGN.md) | Python 先行 + LLM 查邏輯矛盾是正解；若共用 schema 需擴充，應修訂設計稿「禁改 schemas」並補測試；Reviewer **不取代** `validate_report`／Telegram HTML 白名單。 |
| [`architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md) | 延續 Vite 務實；路由與現有 `App.jsx`／`/terminal` 對齊後再大搬；FastAPI 拆 `APIRouter` 宜切片 PR；五模組忌一次空殼無 E2E。 |

詳見總表 §2。

---

## 已交付摘要（備查，非 exhaustive）

以下為 **已進 main 管線／產品** 之摘要；**逐日條目**以 CHANGELOG 為準。**維護契約**：與 [`CHANGELOG.md`](CHANGELOG.md) **雙向對齊** — 改版寫入 CHANGELOG 時同步更新本檔；本檔補登「已交付」須對應 CHANGELOG 既有或同日條目（見 CHANGELOG 檔首說明）。

| 主題 | 代表檔案／行為 |
|------|----------------|
| **視覺化階段計畫（2026-04-14）** | [`visualization_plan.md`](docs/architecture/visualization_plan.md) 階段 A–D；**階段 A**：[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「視覺化與數字段語意」、[`dashboard.py`](dashboard.py) Symbol 快照口徑／`price_alignment` UI；CHANGELOG **2026-04-14** § 視覺化階段 A |
| **Portal Phase 1 + FastAPI 增量路由 + Runbook／研究 stub（2026-05-04）** | PWA **`/briefs`**（與 **`/terminal`** 同頁）、Shell、API 出口現於 [`useApi.js`](data-verification-ui/src/hooks/useApi.js)（`shared/api/client` 見架構驗收清單 **2026-05-06**）；Settings 溯源文案；[`api_routers/`](api_routers/)、[`api_deps.py`](api_deps.py)；[`visualizer.py`](visualizer.py) `VISUALIZER_BTC_SOURCE`；[`tools/notebooklm_tool.py`](tools/notebooklm_tool.py)、[`agents/agency/`](agents/agency/)（預設 env 關）；E2E [`briefs-alias-route.spec.js`](data-verification-ui/e2e/briefs-alias-route.spec.js)；Graph／Reviewer 變更見 [`GRAPH_REVIEWER_CHANGE_CHECKLIST.md`](docs/architecture/GRAPH_REVIEWER_CHANGE_CHECKLIST.md)、[`scripts/verify_graph_gate.sh`](scripts/verify_graph_gate.sh)；CHANGELOG **2026-05-04** |
| **PWA 視覺化 V1**（Design Foundation） | [`visualization_plan.md`](docs/architecture/visualization_plan.md) Phase **V1** — [`DESIGN.md`](DESIGN.md)、[`data-verification-ui/src/design/tokens.js`](data-verification-ui/src/design/tokens.js)（含 typography／spacing／radius）、[`tailwind.config.js`](data-verification-ui/tailwind.config.js)、[`components/common/`](data-verification-ui/src/components/common/)（`AsOfChip`、`ProvenancePopover`、…）、dev **`/design`**；[`Today.jsx`](data-verification-ui/src/pages/Today.jsx)／[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx) 已接入；CHANGELOG **2026-04-18**；契約 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)「PWA 設計 tokens」。 |
| **PWA 視覺化 V2／V3 前置**（結構化 Report + profile／錨點／layout 清單 + **逐區塊原生映射** + **`exec_summary`／`market_mode` 專用區塊**） | 同上 API／PWA 主線；另 [`ExecSummaryBlock.jsx`](data-verification-ui/src/components/report/blocks/ExecSummaryBlock.jsx)、[`MarketModeBlock.jsx`](data-verification-ui/src/components/report/blocks/MarketModeBlock.jsx)、[`BlockSection.jsx`](data-verification-ui/src/components/report/BlockSection.jsx)；E2E mock [`mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`structured-report-route.spec.js`](data-verification-ui/e2e/structured-report-route.spec.js)；CHANGELOG **2026-04-18**。**仍待／加強**：可選 **BQ 持久化**與營運搜尋路徑（[`visualization_plan.md`](docs/architecture/visualization_plan.md)）。 |
| **Streamlit 戰情室 v4 + PWA Phase 6 離線**（視覺化計畫 Phase 7／6） | [`dashboard/theme.py`](dashboard/theme.py)、[`dashboard.py`](dashboard.py)（**`st.tabs`**、**`DASHBOARD_AUTO_REFRESH_SEC`**、`render_profile_tab`／`render_gate_tab`／`render_roundtable_tab`）；[`data-verification-ui/src/service-worker.js`](data-verification-ui/src/service-worker.js)（Workbox **`/api` NetworkOnly** 等）、[`docs/PWA_OFFLINE.md`](docs/PWA_OFFLINE.md)；CHANGELOG **2026-04-18** `### Added` **前二條**；[`README.md`](README.md) 戰情室／War Room 節。 |
| **日報區塊模組化** | **文件**：[`modularization_plan.md`](docs/architecture/modularization_plan.md) Phase 1–5、**[產品與交付原則](docs/architecture/modularization_plan.md#產品與交付原則)**。**Phase 1（2026-04-26）**：[`templates/blocks/`](templates/blocks/) + **`_footer_tail`**；smoke [`test_telegram_template_modularization.py`](test_telegram_template_modularization.py)。**Phase 2（2026-04-27）**：[`brief_profiles.py`](brief_profiles.py)、[`templates/profiles/`](templates/profiles/)、`REPORT_PROFILE`；[`report_render.py`](report_render.py)；[`test_brief_profiles.py`](test_brief_profiles.py)。**Phase 3（2026-04-27）**：[`report_html_gates.validate_report`](report_html_gates.py) `profile=`、`lite` 放寬、`_check_profile_block_consistency`；[`main.py`](main.py)；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)。**Phase 4a（2026-04-27）**：`crypto-only` 模板 + Gate／一致性（同上測試擴充）。**Phase 4b（2026-04-27）**：[`config/brief_layouts/`](config/brief_layouts/)、`BRIEF_LAYOUT_FILE`、[`brief_profiles_layout.py`](brief_profiles_layout.py)。**Phase 4c（2026-04-16）**：BQ `llm_run_log`／`gate_failure_log` **`profile`**（[`bigquery_writer.py`](bigquery_writer.py)、[`main.py`](main.py)、[`docs/SQL/bq_brief_profile_columns.sql`](docs/SQL/bq_brief_profile_columns.sql)）。**Phase 4d（2026-04-14）**：[`modularization_plan.md#phase-4d`](docs/architecture/modularization_plan.md#phase-4d) — 一致性錨點、[`main._validate_report_profile_env`](main.py)、YAML／BQ 文件；[`test_validate_report_profile_phase3.py`](test_validate_report_profile_phase3.py)、[`test_critical_paths.py`](test_critical_paths.py)。**Phase 5（2026-04-27）**：[`schemas.py`](schemas.py)、[`current_affairs_crew.py`](current_affairs_crew.py)、[`main.py`](main.py)、[`report_render.py`](report_render.py)（`BRIEF_DYNAMIC_RENDER`）、[`report_html_gates.py`](report_html_gates.py)（`STRICT_*`／Lite Pass6）、[`docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md`](docs/ADR_CURRENT_AFFAIRS_ROUNDTABLE.md)；[`test_current_affairs_schema.py`](test_current_affairs_schema.py)、[`test_current_affairs_render.py`](test_current_affairs_render.py)、[`test_dynamic_full_render.py`](test_dynamic_full_render.py) |
| 雙軌 Crew + 可選 LangGraph | [`main.py`](main.py)、[`graph/`](graph/)、`USE_LANGGRAPH_ENGINE`、`GRAPH_*` |
| LangGraph 工具橋接與深度查證 | [`graph/graph_tools.py`](graph/graph_tools.py)、`RESEARCH_TOOLS`、`deep_research_node` |
| **LangGraph Reviewer Loop（Phase 3.5）** | [`graph/graph_nodes.py`](graph/graph_nodes.py) `python_validate_node`／`llm_reviewer_node`／`review_retry_node`／`degrade_node`；[`graph/graph_crew.py`](graph/graph_crew.py) wiring；[`bigquery_writer.py`](bigquery_writer.py) `write_reviewer_log` + [`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)；`GRAPH_LLM_TRADE_REVIEWER`、`REVIEWER_LOG_BQ`；[`test_reviewer_loop.py`](test_reviewer_loop.py)。Reviewer 僅查 trade 邏輯，**不取代** `validate_report`／Telegram HTML 白名單。 |
| 日報 HTML／Gate／schema | [`report_html_gates.py`](report_html_gates.py)、[`schemas.py`](schemas.py)、[`report_render.py`](report_render.py)（**2026-04-24** 行動閱讀濾鏡與執行摘要後處理）、[`templates/telegram_report.j2`](templates/telegram_report.j2) |
| 日報投資者可讀性清理（2026-04-29） | [`report_render.py`](report_render.py)、[`main.py`](main.py)、[`schemas.py`](schemas.py)、[`templates/blocks/_ai_section.j2`](templates/blocks/_ai_section.j2)、[`crew.py`](crew.py)：Polymarket production 預設關閉；AI 儀表板改「可交易市場／基本面／財報錨點／需求代理」；新增【財報雷達｜未來 7 天】事件預告（無 EPS／營收 forecast）；區塊②b 去除重複摘要。見 CHANGELOG **2026-04-29**。 |
| 日報品質代理（複合分／TODOS 後續） | [`report_quality_agent.py`](report_quality_agent.py)（**2026-04-24** 格式品質 hints）、[`main.py`](main.py)（成功交付後掛勾）、`REPORT_QUALITY_AGENT*`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）；scratchpad `quality_agent_result`；[`README.md`](README.md) **快速開始**旁「日報品質代理」啟用步驟（**2026-04-16**） |
| Phase A–E 觀測與 Terminal 契約 | [`main.py`](main.py) scratchpad `init.meta.pipeline_config`；[`graph/graph_nodes.py`](graph/graph_nodes.py) `graph_deep_research_metrics`（含 `finish_kind` 等）；[`scripts/ci_terminal_contract_check.sh`](scripts/ci_terminal_contract_check.sh)、[`.github/workflows/ci.yml`](.github/workflows/ci.yml)（含 **npm cache**、**Node 24**／`setup-node@v5` — CHANGELOG **2026-04-18**）；[`test_terminal_numeric_consistency.py`](test_terminal_numeric_consistency.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py)、[`test_graph_deep_research_metrics.py`](test_graph_deep_research_metrics.py)、[`test_schemas_cap_internal_field.py`](test_schemas_cap_internal_field.py)；PWA [`WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)；[`docs/ADR_INDEX.md`](docs/ADR_INDEX.md)、[`README.md`](README.md) badges |
| Snapshot 價格對齊／Web Push 分階 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment`；[`api.py`](api.py) `SymbolSnapshot`；[`web_push_store.py`](web_push_store.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`data-verification-ui/src/pushClient.js`](data-verification-ui/src/pushClient.js) |
| **實盤 BQ vs yfinance 觀測**（2026-04-15） | [`scripts/symbol_price_probe.py`](scripts/symbol_price_probe.py)、[`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)、`PRICE_PROBE_*`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)） |
| **Web Push T4a（Redis／VAPID／pywebpush／BQ）**（2026-04-15） | [`web_push_store.py`](web_push_store.py)、[`api.py`](api.py) `POST /api/push/test-send`、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)、[`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql)、[`test_web_push_redis.py`](test_web_push_redis.py) |
| Playwright E2E（Bloomberg §6 UI） | [`data-verification-ui/e2e/`](data-verification-ui/e2e/)（`cross-page-btc-price`、`today-btc-mismatch-banner`、`terminal-spy-mismatch`）、[`data-verification-ui/playwright.config.js`](data-verification-ui/playwright.config.js)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；[`TodayBtcSnapshotStrip.jsx`](data-verification-ui/src/components/TodayBtcSnapshotStrip.jsx)；mock **`e2e_btc_misaligned`**（CHANGELOG **2026-04-16**） |
| Terminal 後中段 **T1–T3**／**T5** 首次切片（2026-04-14） | [`execution_intents.py`](execution_intents.py)（`status`／`category`／`sort_by`）；[`api.py`](api.py)（`API_HTTP_REQUEST_LOG`、`gate_issue_hints` 富化、`GET /api/execution-intents` query）；[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)（輪詢 coalesce、5xx backoff）；PWA [`Today.jsx`](data-verification-ui/src/pages/Today.jsx)、[`PositionHealthStrip.jsx`](data-verification-ui/src/components/PositionHealthStrip.jsx)、[`TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)；[`docs/BLOOMBERG_ALIGNMENT.md`](docs/BLOOMBERG_ALIGNMENT.md) §4c、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)（T4b 草案）；[`test_execution_intents_api.py`](test_execution_intents_api.py) |
| Terminal 下一輪（2026-04-14）— E2E／T5b／T4a 小步 | [`symbol_snapshot_service.py`](symbol_snapshot_service.py) `price_alignment` 來源欄位 + `PRICE_ALIGNMENT_E2E_OVERRIDES`；[`web_push_store.py`](web_push_store.py) endpoint 去重、**`WEB_PUSH_SUBSCRIBE_RATE_PER_MIN`**、**`WEB_PUSH_STORE_MAX_SUBSCRIPTIONS`**；[`api.py`](api.py) `push_subscribe` 傳 **client_ip**；[`data-verification-ui/e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)；[`test_api_push.py`](test_api_push.py)、[`test_symbol_snapshot_alignment.py`](test_symbol_snapshot_alignment.py) |
| 日報組裝衛生（三情境、儀表板分區） | [`report_render.py`](report_render.py)：BTC 現價 **>50k** 且情境列含 **突破** 時 **`7.6k`→`76k`**；**`instrument_sections`** 前剔除與 IB 區塊標題同名之**空白佔位列**、**連續重複** `is_section_header`；**評分卡 ↔ 儀表板** BTC RSI `status_emoji` 同步、MA20/MA50 鄰近 **$** 敘事對齊儀表板（CHANGELOG **2026-04-12**）；[`test_report_render.py`](test_report_render.py)（含 **2026-04-10** 情境／分區測試） |
| Crew 新聞／工具敘述邊界 | [`crew.py`](crew.py)：加密 **1–3** `investment_takeaway` 禁止無據 **垃圾債／HY／spread** 跳喻；**FinancialDatasets** 營收相關 MetricLine **`label` 須含期間口徑**（annual／quarterly／FY／年份等）；[`tools_legacy.py`](tools_legacy.py) `_fd_summarize_ticker` 尾註提醒 **fiscal／口徑**（CHANGELOG **2026-04-10**） |
| 模板 `$` 與交易卡顯示 | `strip_usd` 濾鏡、`ExecutableTradeLeg` 欄位正規化（CHANGELOG **2026-04-22**） |
| **日報 Opus 回饋落地（SPX 錨／Polymarket 過濾／Telegram 版面／HF·DXY 敘事）**（2026-04-15） | [`tools_legacy.py`](tools_legacy.py) `fetch_gspc_last_close_anchor`、`fetch_spy_etf_last_close_anchor`、`macro_context_tool`（**v4** ^GSPC+SPY ETF 行）、`fetch_polymarket_hot_highlight_lines`（`PREDICTION_MARKETS_KEYWORDS`／`DENYLIST`／**`TAG_IDS`／`EXCLUDE_TAG_IDS`**、Gamma `volume_24hr`）；[`report_render.py`](report_render.py)、[`report_html_gates.py`](report_html_gates.py) `STRICT_SPX_LEVEL_SANITY_GATE`；[`templates/telegram_report.j2`](templates/telegram_report.j2) 免責位移、**🤖 區塊①**；[`crew.py`](crew.py) `_BRIEF_V2_RULE`／HF watchlist 鏈路／單標禁 DXY 唯一主因；[`graph/graph_nodes.py`](graph/graph_nodes.py) LangGraph **上下文刪減**（trade_picker／final_formatter）；[`test_report_render.py`](test_report_render.py)、[`test_prediction_markets_tool.py`](test_prediction_markets_tool.py)、[`test_spy_etf_anchor.py`](test_spy_etf_anchor.py)；[`CHANGELOG.md`](CHANGELOG.md) **2026-04-15**、**2026-04-23** |
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

**提醒**：**`git pull` 後或讀 codebase 前**請看 [§ git pull／讀 codebase 時請先看](#pull-or-read-codebase-reminder) 與隊列 **18–21**（雲端尚未自動完成的 T4a／觀測表與金鑰）。

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
11. ~~**PWA Web Push（分階 2 — 生產級）**~~ — **已交付（2026-04-15）**：Redis（`WEB_PUSH_REDIS_URL`）、**分散式** rate limit（Redis INCR）、可選 **BQ** persist／audit（`WEB_PUSH_BQ_*`）、**`pywebpush`** + `POST /api/push/test-send`（`WEB_PUSH_ADMIN_KEY`）、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)；見 [`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)。**仍待營運**：建表／配 Redis／合規審閱訊息模板與排程 digest（T4b）。
12. ~~**Terminal E2E（Playwright）**~~ — **已交付（2026-04-14）**：[`data-verification-ui/e2e/cross-page-btc-price.spec.js`](data-verification-ui/e2e/cross-page-btc-price.spec.js)、[`e2e/terminal-spy-mismatch.spec.js`](data-verification-ui/e2e/terminal-spy-mismatch.spec.js)、[`e2e/nvda-cross-route-banner.spec.js`](data-verification-ui/e2e/nvda-cross-route-banner.spec.js)（mock **BQ vs OHLC/quote 分歧** UI 迴歸）、[`e2e/mock-api-server.mjs`](data-verification-ui/e2e/mock-api-server.mjs)、[`e2e/run-ci.sh`](data-verification-ui/e2e/run-ci.sh)、[`.github/workflows/pwa-e2e.yml`](.github/workflows/pwa-e2e.yml)；`SymbolCandleChart` 修正 **lightweight-charts v5** `addSeries(CandlestickSeries)`（避免 Terminal 卡白屏）。
13. ~~**Bloomberg 對齊 Phase 2**~~ — **已交付（2026-04-10 CHANGELOG）**：Terminal v2 分組／模板、跨頁 Symbol Context（`SymbolFocusBar` + `TerminalSymbolCard` 設為全域關注）、Streamlit 與 `symbol_snapshot_service`／可選 HTTP 對齊 snapshot 形狀。
14. ~~**Terminal 中段 M2**~~ — **已交付**：見「已交付摘要」列與 CHANGELOG **2026-04-12** `### PWA`；規格見 [`docs/TERMINAL_MID_TIER_ROADMAP.md` — M2](docs/TERMINAL_MID_TIER_ROADMAP.md#m2-terminal-pwa)。
15. ~~**Terminal 中段 M3**~~ — **已交付**：見「已交付摘要」與 CHANGELOG **2026-04-12** `### API（Terminal M3）`；規格 [M3](docs/TERMINAL_MID_TIER_ROADMAP.md#m3-symbol-quote)。
16. ~~**Terminal 中段 M4**~~ — **已交付**：見「已交付摘要」與 [`docs/TERMINAL_MID_TIER_ROADMAP.md` M4](docs/TERMINAL_MID_TIER_ROADMAP.md#m4-realtime-stream)。
17. ~~**Terminal 中段 M5**~~ — **已交付**：見「已交付摘要」與 [M5](docs/TERMINAL_MID_TIER_ROADMAP.md#m5-paper-execution)。
18. **營運：BigQuery DDL（Web Push + price probe）** — 在專案 BQ 執行 [`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql) 與 [`docs/SQL/price_probe_log.sql`](docs/SQL/price_probe_log.sql)；設定 **`WEB_PUSH_SUBSCRIPTIONS_TABLE`**／**`WEB_PUSH_AUDIT_TABLE`**（可選）／**`PRICE_PROBE_LOG_TABLE`**（寫入觀測時）。完成後可勾掉並註記日期。
19. **營運：Redis + `WEB_PUSH_REDIS_URL`** — 接上後端可連之 Redis；與 **18** 一併驗證 `POST /api/push/subscribe` 回 `backend: redis`。
20. **營運：VAPID 金鑰** — `python3 scripts/vapid_generate.py`；public → PWA env、private → 後端 only；勿提交私鑰。
21. **營運：staging 小流量 `test-send`** — `WEB_PUSH_ADMIN_KEY` + `POST /api/push/test-send`；確認瀏覽器能收再放量。
22. **日報區塊模組化（實作）** — ~~**Phase 1**~~ **已交付（2026-04-26）**；~~**Phase 2**~~ **已交付（2026-04-27）**；~~**Phase 3**（`validate_report(..., profile=)`、`lite`／機構 Gate、`main.py` 傳 profile、一致性檢查）~~ **已交付（2026-04-27）**；~~**Phase 4a**（`crypto-only` 模板 + Gate）~~ **已交付（2026-04-27）**；~~**Phase 4b**（`BRIEF_LAYOUT_FILE` YAML、`profile_block_ids` merge）~~ **已交付（2026-04-27）**；~~**Phase 4c**（BQ `profile`）~~ **已交付（2026-04-16）**；~~**Phase 4d**（Phase 1–4 補強：一致性錨點、啟動 `REPORT_PROFILE` 檢、YAML／BQ 文件）~~ **已交付（2026-04-14）** — 見 CHANGELOG **2026-04-14** `### Changed` 與 [`modularization_plan.md` Phase 4d](docs/architecture/modularization_plan.md#phase-4d)。~~**Phase 4d 動態組版**~~ **已交付（2026-04-27）** — `BRIEF_DYNAMIC_RENDER` + YAML 範例 [`config/brief_layouts/example_full_reorder_header_exec.yaml`](config/brief_layouts/example_full_reorder_header_exec.yaml)。~~**Phase 5（5a–5d + 5b）**~~ **已交付（2026-04-27）** — 見 CHANGELOG **2026-04-27** `### Changed` 與 [`modularization_plan.md` Phase 5](docs/architecture/modularization_plan.md#phase-5時事多觀點區塊podcast-型態文字)。**運營／staging**：`BRIEF_CURRENT_AFFAIRS=1`、可選 `BRIEF_CURRENT_AFFAIRS_JSON`、動態組版前 smoke。原則見 **[產品與交付原則](docs/architecture/modularization_plan.md#產品與交付原則)**（過渡期 **production 固定 `full`／等價**、`lite`／`crypto-only` 先 staging）。
23. ~~**Reviewer Loop（LangGraph Phase 3.5）**~~ — **已交付（2026-04-21）**：[`graph/graph_crew.py`](graph/graph_crew.py) `trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`；[`graph/graph_nodes.py`](graph/graph_nodes.py) deterministic reviewer + Slim LLM verdict + hard cap=2 + degrade warning；[`bigquery_writer.py`](bigquery_writer.py) `write_reviewer_log`、[`docs/SQL/reviewer_log.sql`](docs/SQL/reviewer_log.sql)；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) `GRAPH_LLM_TRADE_REVIEWER`／`REVIEWER_LOG_BQ`；[`test_reviewer_loop.py`](test_reviewer_loop.py)。**紅線**：reviewer 僅查 trade 邏輯、**不取代** `validate_report`／Telegram HTML 白名單。後續若要讓 reviewer gate 對主線排程生效，仍需另行評估 `USE_LANGGRAPH_ENGINE=1` 預設翻轉。
24. **NotebookLM 整合（Phase 0–5）** — [`docs/architecture/notebooklm_research.md`](docs/architecture/notebooklm_research.md)：**Phase 0** `notebooklm-client` 相容性 smoke + `storage_state.json` 納入 `.gitignore`；**Phase 1** `tools/notebooklm_tool.py`（遵 [`ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) `BaseTool`）+ `_get_cache`／`_set_cache`（key 含 `notebook_last_modified_ts`）+ flag `NOTEBOOKLM_ENABLED=0`／`NOTEBOOKLM_API_KEY`／`NOTEBOOKLM_COST_DAILY_CAP_USD=2.0`／`NOTEBOOKLM_TIMEOUT_SEC=60`；**Phase 2** `graph/graph_nodes.py` `FILING_KEYWORDS` 分類 + `deep_filing_analysis_node` + 擴充 `python_validate_node` 第 7 條（每題 `citations[i]` ≥ 1 且 `excerpt` 非空）；**Phase 3** 8 問殺手題 prompt + `DeepFilingAnalysis` Pydantic（`Citation{page,section,excerpt}`、`answers[1..8]`、`citations[1..8]`、`red_flags`）+ 港／A／美 3 家新股 POC + BQ `notebooklm_cost_log`（含 `profile` 欄，對齊 Phase 4c）；**Phase 4** `brief_profiles.py` `deep_filing_block` + `templates/blocks/` macro（僅 `<b>`／`<code>`／`<blockquote>`）+ `CLAUDE.md`／`AGENTS.md` 指引；**Phase 5** production 監控 + 每週成本／準確度復盤。**KPI**：單家招股書 ≤ $0.6、citation 覆蓋率 100%、`validate_report` 通過率 100%、研究時長 ≥ 80% 縮短、chat 響應 ≤ 60s。**紅線**：NotebookLM 為事實引擎；Claude synthesis 數字須能回溯至 citation excerpt（第 7 條硬檢）。**依賴**：隊列 **23**（Reviewer Loop）。P1 / L。
25. **Agency Agents 整合（Phase 0–6）** — [`docs/architecture/agency_agents_research.md`](docs/architecture/agency_agents_research.md)：**Phase 0** fork [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)（MIT）讀完 Finance Division；**Phase 1** 建 `agents/agency/` + `__init__.py` `_load_agency_template()` helper + `investment_researcher.md`（§6 草案：Core Mission、Critical Rules、5 項 deliverables、Workflow、Success Metrics）；**Phase 2** `crew.py` 3 個 agent 的 `backstory` 升級為 template 動態載入（先試幣圈研究員／AI 研究員／主編）；**Phase 3** `graph/graph_nodes.py` `agency_researcher_node`（`AGENCY_RESEARCH_KEYWORDS`：盡調/equity/earnings/IPO/S-1/10-K/valuation/公司研究）+ `AgencyResearchOutput` schema + `python_validate_node` 第 8 條（deliverable citations ≥ 1、risk_register ≥ 2）；**Phase 4** `brief_profiles.py` `agency_finance_block` + macro + `CLAUDE.md` 指引；**Phase 5** `financial_analyst.md` template + 三層 pipeline POC（**TrendRadar → Agency Investment Researcher → NotebookLM**，共用 `AgencyResearchOutput.deliverables`）；**Phase 6** confidence 覆蓋率月度復盤。**Flags**：`AGENCY_RESEARCH_ENABLED=0`／`AGENCY_TEMPLATE_DIR=agents/agency/`／`AGENCY_FALLBACK_TO_DEFAULT=1`。**KPI**：citation 覆蓋率 100%、risk_register ≥ 3 條/次、confidence=high ≥ 60%、`python_validate_node` 第 8 條通過率 ≥ 95%。**依賴**：Phase 3 需隊列 **24**（NotebookLM Phase 1）先落地以共用 citation 驗證路徑；`REPORT_COMPARE_MODE=1` 驗收 backstory 升級 diff。P2 / L。
26. **Terminal Frontend Portal 五模組化** — [`docs/architecture/TERMINAL_FRONTEND_PLAN.md`](docs/architecture/TERMINAL_FRONTEND_PLAN.md)：`data-verification-ui/src/` 重構為 `app/layout/`（`Shell.tsx`＋`ModuleNav.tsx`）+ `modules/{daily-brief,investment-analysis,position-management,industry-trends,quant-trading}/` + `shared/{api,components,hooks,types}/`；`react-router-dom` 路由（`/` → `/briefs`；`/analysis`／`/positions`／`/industries`／`/quant`）；`shared/api/client.ts` axios 實例讀 `VITE_API_URL`、加 `X-Q-Silicon-Key`（localStorage `qsi_master_key`），401 跳轉 key-input 頁；**master key** 以 `QSILICON_MASTER_KEY` 單一環境變數為主（先不導入 JWT／多用戶，對齊隊列 **11**）；**後端** FastAPI `APIRouter` 逐 router 切片 PR（`/api/briefs`／`/api/analysis`／`/api/positions`／`/api/industries`／`/api/quant`／`/api/shared`），同步 [`DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)／[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)；**模組邊界**：`modules/{a}/` 禁直接 import `modules/{b}/`（lint rule 或目錄約束）；**開發順序**：Shell + daily-brief（遷移既有 `/terminal`）→ position-management（複用 `paper_execution.py`／`execution_intents.py`）→ industry-trends → investment-analysis → quant-trading；每模組至少一條 Playwright smoke（mock API 可）；PWA 離線快取維持 API NetworkOnly。**依賴**：隊列 **9**（api.py 合約測試先行，避免 `APIRouter` 拆分靜默回歸）；隊列 **26** Shell＋daily-brief 完成後才啟動 Phase 3–5 模組。P2 / L。
27. **視覺化剩餘 backlog（V2／V4／V5／V6）** — [`docs/architecture/visualization_plan.md`](docs/architecture/visualization_plan.md) §3：**V2** 其餘 `block_id` 專用 JSX 元件依 `BLOCK_REGISTRY` 逐步取代 placeholder／legacy 路徑；可選 BQ 集中儲存 `DailyBriefReport` JSON 供營運稽核；**V4** `BRIEF_CURRENT_AFFAIRS=1` staging 下 **PWA ↔ Telegram** roundtable voice 順序與呈現端到端 smoke；Streamlit Gate／Roundtable 與 PWA 像素級差異逐項列 issue；**V5** 可選預快取 `/today`／最新報告、`as_of` 離線提示（現行 API NetworkOnly 保守策略）；**V6** Symbol 快照區與 `TerminalSymbolCard` **同構**（provenance／格式）、regime／KPI Streamlit ↔ PWA theme v4 細節對齊。P3 / M（多切片，可穿插 Terminal T1–T5）。
28. **12 週投資價值優化 Roadmap（repo-native，尚未實作）** — 從「通用研報 tool」推進到「個人化投資決策夥伴」，但只沿用既有主線，不另起平行系統；公開績效僅能引用可回放、可審計的 **paper-tracked** 訊號，且不接券商、不自動下單、不承諾收益。**28a Signal lifecycle + paper P&L**：以 [`execution_intents.py`](execution_intents.py)／[`paper_execution.py`](paper_execution.py) 為唯一訊號生命週期，補齊日報 QSREC → intent → paper fill/close → P&L／alpha 推導與可選 BQ 記錄。**28b Quality-adjusted scoring + Blotter UI**：以 `validate_report`、[`report_quality_agent.py`](report_quality_agent.py) composite、QSREC confidence 與 regime 產生 quality-adjusted score，先顯示於 [`ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)／War Room，不新增不可用 API 承諾。**28c Monthly transparency letter + portfolio upload/alignment**：用已平倉 paper 訊號生成內部月度透明信函，未達足夠樣本前不公開；portfolio alignment v1 採 CSV／local store deterministic scoring，不導入完整帳號系統。**28d Scenario engine + target optimizer + beta/launch**：做情境壓測與 target/stop 建議，但 optimizer 只預填建議、仍須人工確認；ProductHunt／公開文章需等 paper data、beta feedback 與合規文案可審計後再排。P1 / L。

---

<a id="terminal-post-mid-tier-t1-t5"></a>

## Terminal／戰情室 — 後中段路線（T1–T5，每切片對應檔案）

> **語意**：M1–M5 已交付（見上節與 [`docs/TERMINAL_MID_TIER_ROADMAP.md`](docs/TERMINAL_MID_TIER_ROADMAP.md)）。以下為 **持續 improve** 的建議切片；**不綁日曆天數**，以可 review 的 PR 為單位。完成後寫入 [`CHANGELOG.md`](CHANGELOG.md) 並更新本節或改「✓」。

### Phase T1 — 穩定與可觀測

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T1a** | 戰情室／Terminal **錯誤態矩陣**（重試、降級、避免輪詢風暴） | [`data-verification-ui/src/pages/Today.jsx`](data-verification-ui/src/pages/Today.jsx)、[`data-verification-ui/src/components/WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx)、[`data-verification-ui/src/components/TerminalSymbolCard.jsx`](data-verification-ui/src/components/TerminalSymbolCard.jsx)、[`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx) |
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
| **T3a** | **Workspace／關注**：匯入匯出、模板、快捷操作（產品定義內） | [`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)、[`data-verification-ui/src/context/SymbolFocusContext.jsx`](data-verification-ui/src/context/SymbolFocusContext.jsx)、[`data-verification-ui/src/components/SymbolFocusBar.jsx`](data-verification-ui/src/components/SymbolFocusBar.jsx) |
| **T3b** | **意圖表**：篩選、排序、欄位契約 | [`data-verification-ui/src/components/ExecutionIntentsBlotter.jsx`](data-verification-ui/src/components/ExecutionIntentsBlotter.jsx)、[`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`api.py`](api.py)（若需 query 參數）、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| **T3c** | **輪詢／快取**：減少重複 snapshot、調整 stale／interval | [`data-verification-ui/src/hooks/useApi.js`](data-verification-ui/src/hooks/useApi.js)、[`data-verification-ui/src/pages/Terminal.jsx`](data-verification-ui/src/pages/Terminal.jsx)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（`VITE_TERMINAL_POLL_MS` 等） |

### Phase T4 — 通知與閉環（合規後）

| 切片 | 目標 | 主要檔案（起點） |
|------|------|------------------|
| **T4a** | ~~**Web Push 分階 2**~~ **已交付（2026-04-15）**：Redis、VAPID、`pywebpush`、可選 BQ、管理 test-send | [`web_push_store.py`](web_push_store.py)、[`api.py`](api.py)、[`docs/PWA_WEB_PUSH.md`](docs/PWA_WEB_PUSH.md)、[`scripts/vapid_generate.py`](scripts/vapid_generate.py)、[`docs/SQL/web_push_subscriptions.sql`](docs/SQL/web_push_subscriptions.sql) |
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

### 2026-04-15

**本週 OSS 候選（2026-04-15）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-04-15-revision-plan-draft.md`](docs/oss_candidates/2026-04-15-revision-plan-draft.md)
- 機讀：[`2026-04-15-digest.json`](docs/oss_candidates/2026-04-15-digest.json)、[`2026-04-15-candidates.json`](docs/oss_candidates/2026-04-15-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 65896 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 9699 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 11865 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 16949 |
| [`cantaro86/Financial-Models-Numerical-Methods`](https://github.com/cantaro86/Financial-Models-Numerical-Methods) | 5/5 · 建議優先評估 | 6743 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 9666 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 7667 |
| [`lballabio/QuantLib`](https://github.com/lballabio/QuantLib) | 5/5 · 建議優先評估 | 7004 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 40738 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12255 |
| [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | 5/5 · 建議優先評估 | 7178 |
| [`ranaroussi/quantstats`](https://github.com/ranaroussi/quantstats) | 5/5 · 建議優先評估 | 6959 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 25536 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8504 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 7926 |

**Spike／PR 勾選**（僅 repo 名；理由見研究稿）：

- [ ] `OpenBB-finance/OpenBB`
- [ ] `StockSharp/StockSharp`
- [ ] `TA-Lib/ta-lib-python`
- [ ] `UFund-Me/Qbot`
- [ ] `cantaro86/Financial-Models-Numerical-Methods`
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

<!-- OSS_SCOUT_AUTO_END -->

---

## 修訂紀錄

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
