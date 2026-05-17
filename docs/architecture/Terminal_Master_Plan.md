# Terminal 總表（中段落地 · 長線 Portal）

**目的**：用**單一導覽頁**銜接「已交付的中段能力」與「五模組 Q-Silicon Terminal」長線規劃，並收斂 [`docs/architecture/`](.) 內架構文件之**維護者／AI 看法**（與實作對照時請以程式與 CHANGELOG 為準）。

| 層級 | 文件 | 角色 |
|------|------|------|
| 中段（已落地為主） | [`TERMINAL_MID_TIER_ROADMAP.md`](../TERMINAL_MID_TIER_ROADMAP.md) | M1–M5：溯源、輪詢／SSE、quote、紙上 tick；對齊 [`BLOOMBERG_ALIGNMENT.md`](../BLOOMBERG_ALIGNMENT.md) |
| 長線（規劃／協作 context） | [`AI_CONTEXT.md`](AI_CONTEXT.md) | 與 AI 協作準則、工程紅線、五模組願景、`qsilicon/` 邊界 |
| 長線（Graph） | [`REVIEWER_LOOP_DESIGN.md`](REVIEWER_LOOP_DESIGN.md) | `trade_picker` → reviewer：Python 先擋、LLM 只查邏輯；cap／降級／BQ |
| 長線（PWA／API） | [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) | `data-verification-ui` 模組化、FastAPI 路由分層、master key、MVP 順序 |
| 索引 | [`ADR_INDEX.md`](../ADR_INDEX.md) | ADR／設計稿；含 **`architecture/`** 列 |
| 根導覽 | [`CLAUDE.md`](../../CLAUDE.md) §5 | Terminal 長線規劃表格（與本檔並用） |

---

## 0. `architecture/` 文件狀態矩陣

> **判讀原則**：本目錄不是「全部已實作」清單；同時包含已落地導覽、協作 context、仍有 backlog 的產品計畫，以及尚未接主流程的研究稿。逐日行為變更仍以根目錄 [`CHANGELOG.md`](../../CHANGELOG.md) 與 [`TODOS.md`](../../TODOS.md) 為準。

| 文件 | 現況 | 實作對齊摘要 |
|------|------|--------------|
| [`modularization_plan.md`](modularization_plan.md) | ✅ 已落地／維護導覽 | 日報模組化 Phase 1–5 已落地；預設 `full` byte-identical；後續只保留維護紀律與非本 plan backlog。 |
| [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) | ✅ Portal Phase 1 已閉環 | Vite PWA、`/briefs`／`/terminal`、Shell、master key、401、eslint 模組邊界已對齊 2026-05-04／05／06。 |
| [`REVIEWER_LOOP_DESIGN.md`](REVIEWER_LOOP_DESIGN.md) | ✅ 第一版已落地 | `trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`、`write_reviewer_log`、`test_reviewer_loop.py` 已入庫。 |
| [`GRAPH_REVIEWER_CHANGE_CHECKLIST.md`](GRAPH_REVIEWER_CHANGE_CHECKLIST.md) | ✅ 維護檢查清單 | Reviewer／`graph/` 變更時的必跑測試與紅線，非新功能 backlog。 |
| [`visualization_plan.md`](visualization_plan.md) | 🟡 主要 repo backlog 已補，仍有 staging／離線細項 | 2026-05-06 補 `deep_filing_block`／`agency_finance_block` JSX、全區塊 `data-section`、DailyBriefReport JSON 持久化／可選 BQ、Streamlit snapshot provenance／price alignment helper；**Phase 1**：隊列 27 staging 執行稿／回填模板見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)；仍留預快取／離線細節。 |
| [`AI_CONTEXT.md`](AI_CONTEXT.md) | 🟡 協作 context | 行為準則與紅線有效；現況段需以 CHANGELOG 校正；`qsilicon/` 邊界仍屬長線方向。 |
| [`notebooklm_research.md`](notebooklm_research.md) | 🟡 Repo-side 主流程 scaffold 已接，live client 仍未接 | 新增 `DeepFilingAnalysis`／`Citation`、`deep_filing_analysis_node`、`deep_filing_block`、多題 helper、可選 BQ cost log；`notebooklm_query()` 仍是預設關閉／未接 live client stub。 |
| [`agency_agents_research.md`](agency_agents_research.md) | 🟡 Repo-side 主流程 scaffold 已接 | 新增 template parser、`AgencyResearchOutput`／`AgencyDeliverable`、`agency_researcher_node`、Crew backstory opt-in 注入、`agency_finance_block`；完整多 Agent 模板庫仍屬長線。 |
| [`tradingview_mcp_research.md`](tradingview_mcp_research.md) | 🟡 Repo-side bridge 已接，外部 MCP 未安裝 | 新增 `tools/tradingview.py`、mock fixture、Crew／LangGraph tool tail、sample setup；不修改 `~/.claude`、不安裝外部 MCP server。 |
| [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) | ✅ 狀態索引 + Phase 0–4 + §3 前端缺口盤點 | 本檔 §0 矩陣對齊各檔 ✅／🟡；**Phase 0** 判讀治理、**Phase 2** Portal 工作台切片、**Phase 3** M4／M5 閉環、**Phase 4** 讀者層×工作台層 IA 收斂；**§3** 為前端尚缺方向之滾動 CEO 盤點（權威仍以 `CHANGELOG`／`TODOS`／程式為準）；細節路由／元件契約見 [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) 與 `App.jsx`。 |

### Phase 0 — `architecture/` 判讀與治理（已定案）

1. **權威順序（事實）**：已交付行為 → 根目錄 [`CHANGELOG.md`](../../CHANGELOG.md) → [`TODOS.md`](../../TODOS.md)（已交付摘要／隊列）→ 程式碼。**本節上方矩陣**為 `docs/architecture/` **單一索引**：✅＝已閉環或維護導覽；🟡＝仍有 backlog、staging 細項、或 **研究／optional scaffold**。
2. **研究稿 ≠ 產品承諾**：`notebooklm_research`／`agency_agents_research`／`tradingview_mcp_research` 等標 🟡 之檔案，**不**視為預設上線範圍。若要列入產品里程碑，須另有 **ENV／紅線（含資料源治理 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](../REALTIME_DATA_SOURCES_GOVERNANCE.md)）／驗收** 一句話，並落入 [`TODOS.md`](../../TODOS.md) 隊列（避免「讀架構＝全部要做」）。
3. **[`AI_CONTEXT.md`](AI_CONTEXT.md)**：承載協作紅線、工程原則與願景；**「現況／版本」細節**以 `CHANGELOG.md` 與程式為準，本檔與 `AI_CONTEXT` **不**承擔逐 commit 對帳。

### Phase 1 — 日報可信／隊列 27（staging 對照）

**Repo 側**：執行稿、環境核對表、**TODOS／CHANGELOG 回填模板**見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)。**不在 CI 自動執行**；通過與否由 staging 營運於 [`TODOS.md`](../../TODOS.md) 隊列 **27** 或同步狀態行關帳。**可選同日**：Reviewer rollout（隊列 35）見 [`REVIEWER_PRODUCTION_ROLLOUT.md`](../REVIEWER_PRODUCTION_ROLLOUT.md) 與 [`scripts/verify_reviewer_rollout_env.py`](../../scripts/verify_reviewer_rollout_env.py)，與本 smoke **非**硬性綁定。

### Phase 2 — Portal「產品面」可驗收切片（2026-05-14）

**定義**：讀者摸得到、且不破離線／即時資料紅線的增量；每塊以 Playwright 或既有契約測試封頂。

**已落檔／落碼**：[`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) 現況行；Command Bar **`terminal-crew-status-hud`**（輪詢 **`GET /api/run-crew/status`**）；Workspace **`storage` + `qsi_workspace_changed`** 跨分頁同步（[`workspaceSync.js`](../../data-verification-ui/src/constants/workspaceSync.js)）；E2E [`workspace-cross-tab.spec.js`](../../data-verification-ui/e2e/workspace-cross-tab.spec.js)。**仍列 backlog**（`TODOS` 隊列 29／34）：權限細節、排程型 digest 等。

### Phase 3 — Backlog Go-Live（M4／M5 閉環；2026-05-14）

**定義**：以排程＋SSE 把後端 backlog 收成 production main 上的可驗收切片；研究稿（NotebookLM／Agency／TradingView）仍 🟡，**不在本階段**。

**已落碼（slices 1–5；CHANGELOG **2026-05-14** `### Backlog Go-Live`）**：
- **M5 自動紙上撮合**：[`.github/workflows/paper-execution-tick.yml`](../../.github/workflows/paper-execution-tick.yml)（每 15 分鐘）+ [`requirements-paper-tick.txt`](../../requirements-paper-tick.txt)；可選 `PAPER_EXECUTION_AUDIT_TABLE` 寫 BQ。
- **M4 push digest**：[`.github/workflows/push-digest-tick.yml`](../../.github/workflows/push-digest-tick.yml)（每 30 分鐘）；`PRICE_ALERTS_TELEGRAM_ENABLED=1` 啟用，`triggered_at` 自然去重。
- **M4 SSE price_alert**：[`war_room_stream.py`](../../war_room_stream.py) deque + `event: price_alert`；PWA [`PriceAlertToaster.jsx`](../../data-verification-ui/src/components/PriceAlertToaster.jsx) 訂閱 `PRICE_ALERT_SSE_EVENT`。
- **Contract smoke 擴充**：[`tests/api/test_api_contract_smoke.py`](../../tests/api/test_api_contract_smoke.py) +3 斷言（paper-tick 404、push-check shape、SSE 404）。

**SSE 安全收尾（2026-05-16 交付）**：`POST /api/stream/token`（[`sse_token.py`](../../sse_token.py)、`SSE_TOKEN_TTL_SECONDS`）、`SSE_MAX_EVENTS_PER_SEC` 每連線事件節流（超量 yield `event: throttled`）、[`tests/api/test_sse_token.py`](../../tests/api/test_sse_token.py)；明細見 CHANGELOG **2026-05-16** `### SSE 安全強化`。**仍列 backlog**：四模組 UI 之深化（4a–4d 模組本身已是 MVP，可用 hooks 為主）。

### Phase 4 — Portal 資訊架構：讀者層 × 工作台層（IA 收斂；Gate 0 已 REVIEW，2026-05-16）

**目的**：在**不弱化**「類 Bloomberg 工作台」能力的前提下，讓 **新聞（`/news`）** 與 **科技專欄（`/columns`）** 維持**讀者向**體驗；五板塊仍屬同一 Portal（`Shell` + `SideNav`／`ModuleNav`），差異以**資訊密度與語氣**分層，而非另起一套產品或整站 techy。

**與本檔其他節之對齊**：

| 對齊點 | 說明 |
|--------|------|
| **§0 Phase 0** | 本節為**產品／IA 收斂**；落地後仍遵守權威順序，行為變更回寫 [`CHANGELOG.md`](../../CHANGELOG.md)／[`TODOS.md`](../../TODOS.md)。 |
| **§0 Phase 2** | Command Bar、Workspace、Crew HUD 等**保留**；Phase 4 規劃**情境化**（讀者頁較輕的指令／搜尋語氣，工作台頁保留合理密度）。 |
| **§0 Phase 3** | M4／M5 排程、SSE `price_alert`、`PriceAlertToaster` 等**不**因讀者層而拆除；讀者層首屏**避免**預設塞滿儀表板式區塊。 |
| **§1 執行順序** | 與日報可信並行時**不**動 `validate_report`／Telegram HTML 紅線；以路由級切片、文案、導覽與（可選）E2E 擴充為主。 |
| **[`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md)** | 路由表、`modules/{name}`、驗收清單仍以該檔與 `data-verification-ui` 程式為準；**本節只鎖產品敘事與驗收尺**。 |
| **[`BLOOMBERG_ALIGNMENT.md`](../BLOOMBERG_ALIGNMENT.md)** | 延續「工作流可審計」與 §4 驗收習慣；**不**把新聞／專欄首屏做成報價牆或不可溯源數字堆疊。 |

**原則（通過／不通過尺）**：

1. **分層，不分裂**：同一套殼與導覽；差異在**路由與版面**，不開第二套 App。
2. **讀者層**：`/news`、`/columns` 以標題、摘要、**來源**、時間軸／策展為主；首屏避免預設多區高密度表格或代號前置。
3. **工作台層**：`/insights`、`/dashboard`、`/portfolio` 等保留狀態、表格、SSE、意圖／警報；同屏高密度區塊宜有**上限**，其餘收斂至 tab／`GlobalWatchlistDock`／Workspace。
4. **融合靠連結**：新聞／專欄內「相關標的／主題」→ 觀點或產業（**重用既有深連結**為優先）；反向連結可後續補。
5. **Command Bar**：讀者頁與工作台頁可採**不同提示語氣**（實作可分期）；金鑰、`401`→`/api-key` 等全站行為不變。
6. **紅線**：無數據幻覺、可溯源、[資料源治理](../REALTIME_DATA_SOURCES_GOVERNANCE.md)；離線／API 快取策略不因「像終端」放寬。

**建議分段（供 REVIEW；驗收以人測為主，可補 Playwright）**：

| 代號 | 焦點 | 代表路由 | 驗收提示（可改寫） |
|------|------|----------|-------------------|
| **A** | 讀者層打底（IA／留白／單一主任務） | `/news`、`/columns` | 非金融背景受測者約 5 分鐘內能說出頁面用途，無需先懂代號 |
| **B** | 工作台層精煉（一屏一主問題／密度上限） | `/insights`、`/dashboard`、`/portfolio` | 「警報 → 標的／狀態 → 新聞脈絡」路徑點擊次數有上限（**N** 由維護者訂，寫入 `TODOS` 或票） |
| **C** | 融合層（跨板塊人話 CTA／輕量主題 hub） | 跨路由 | 同一主題從新聞進與從觀點進**能互指**，且 CTA 文案一致 |

**刻意不做（與 §2 風險對齊）**：首階段不以多視窗 MDI 為目標；不把新聞首屏做成即時報價牆；不為融合引入未審核或不可溯源資料源。

**維護者 REVIEW 結果（2026-05-16 已簽核）**：工作台主戰場 = `/insights` + `/portfolio`（`/dashboard` 並列宏觀台、不佔主戰場名額）、讀者層首屏零表格 = 是、融合第一刀 = 雙向、終端感保留元素 = 5 項（Command Bar、mono symbol chips、macro spark grid、SSE WATCH、Workspace dock）、工作台關鍵路徑 N=3。權威值寫在 [`portalPhase4.js`](../../data-verification-ui/src/constants/portalPhase4.js) 之 `PORTAL_PHASE4_GATE0`。下一輪人測（44a 讀者層）之日期由維護者於 [`TODOS.md`](../../TODOS.md) 隊列 44 補登。

### Phase 4 — 實作規劃（滾動切片；對齊 `TODOS` 隊列 44）

**Gate 0（文件化即可開工）**：將上段「REVIEW 前先決」四點寫入 [`TODOS.md`](../../TODOS.md) 或票證（含 **N**＝工作台關鍵路徑點擊上限）；未定案前 **44b** 以「盤點＋標註過密區塊」為主，不重排大結構。

| 切片 | 對應 §0 表 | 主要產出（PWA） | 驗收（最小） | 依賴／備註 |
|------|------------|-----------------|-------------|------------|
| **44a** | **A** 讀者層 | [`NewsHome.jsx`](../../data-verification-ui/src/modules/news/pages/NewsHome.jsx)、[`ColumnsHome.jsx`](../../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx)：首屏單一主任務、來源／時間軸可掃讀、**避免首屏多區高密度表**；可選 **reader 語氣**副標（`data-testid` 供 E2E）。 | 擴充或新增 Playwright（`news-route`／`industries-route` 或專用 spec）+ 人測腳本（Master Plan **A** 列）；`npm run build` 綠。 | **原則上不開新 API**；若僅文案／排版，契約測試可不改。 |
| **44b** | **B** 工作台層 | [`InsightsHome.jsx`](../../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)、[`DashboardHome.jsx`](../../data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx)、[`PortfolioHome.jsx`](../../data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx)：每路由**一屏一主問題**；超過 **N** 個高密度區塊時收斂至 tab／[`GlobalWatchlistDock`](../../data-verification-ui/src/components/GlobalWatchlistDock.jsx)／[`WorkspacePanel`](../../data-verification-ui/src/components/WorkspacePanel.jsx)。 | 人測：警報→標的→（可選）回新聞／專欄 ≤ **N** 點擊；可選 E2E 記錄關鍵 `data-testid`。 | 與 **Phase 3** `PriceAlertToaster`／SSE **不衝突**；不減監控能力，只調**呈現層級**。 |
| **44c** | **C** 融合層 | 跨 [`NewsHome`](../../data-verification-ui/src/modules/news/pages/NewsHome.jsx)／[`ColumnsHome`](../../data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx)／[`InsightsHome`](../../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx)（或 `SymbolDeepDive`）：**固定人話 CTA**（文案表放 `constants` 或單一 `portalCta.js`）；單向或雙向依 Gate 0；可選輕量「主題／標的」hub（**重用** `?symbol=`、`?tab=`）。 | Playwright：至少一條「新聞／專欄 → 觀點」與（若做）反向；文案與 `href` 斷言一致。 | 與 [`BLOOMBERG_ALIGNMENT.md`](../BLOOMBERG_ALIGNMENT.md) §4 勾選表可並行記帳，**不**把讀者頁做成報價牆。 |
| **44d（可選）** | **§0 Phase 4 原則 5** | [`TerminalCommandBar.jsx`](../../data-verification-ui/src/components/TerminalCommandBar.jsx)：依 `useLocation().pathname` 切 **placeholder／title**（讀者頁偏搜尋／主題；工作台頁保留 `GO`／`RUN` 語意）；不改 401／節流邏輯。 | 擴充 `command-bar-route.spec.js` 或新路徑斷言。 | 可排在 **44c** 之後；單獨 PR 較易 review。 |

**與 §1 執行順序的落地順序**：建議 **44a → 44b → 44c**（必要時 **44d**）；每切片一 PR。詳細票證敘述見 [`TODOS.md`](../../TODOS.md) **隊列 44**。工程契約與模組邊界見 [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) **§ Phase 4 IA**。

---

## 1. 執行順序（維護者）

1. **穩住日報可信與 Gate**（與 Terminal 並行但不可讓步）：對齊 `TODOS.md`「維護者意見」與 `validate_report` 契約。
2. **中段產品節奏**：以 `TERMINAL_MID_TIER_ROADMAP` 已交付能力為錨；新增能力須有 API／PWA 契約測試或 Playwright 再擴張。
3. **長線 Portal**：依 `TERMINAL_FRONTEND_PLAN` 的 **Shell → daily-brief → position → …** 順序切片；避免一次重構 `api.py` 單體—**incremental `APIRouter`** 較可 review。
4. **讀者層 × 工作台層（§0 Phase 4）**：新聞／專欄與觀點／儀表／組合**同一 Portal、不同密度**；交付以路由級切片與跨板塊 CTA 為主，見上表 **A／B／C**。

---

## 2. 對長線三檔（`AI_CONTEXT`／`REVIEWER_LOOP_DESIGN`／`TERMINAL_FRONTEND_PLAN`）的看法（AI／維護者）

以下為**設計層評論**，實作時請對照目前 `graph/`、`data-verification-ui/`、`api.py` 真實狀態。

### [`AI_CONTEXT.md`](AI_CONTEXT.md)

- **優點**：行為準則（先讀碼、trade-off 雙面、LLM 懷疑論）與**格式／邏輯分離**、Fail-Hard Gate、Slim Schema 紅線，與本 repo 的 `validate_report` 文化一致；五模組 Terminal 願景與「暫不拆 repo」務實。
- **建議**：檔內「現有代碼庫狀態」會隨時間漂移，新 session 應以 **CHANGELOG／TODOS 已交付摘要** 校正；「本次 Session 任務」區塊宜當**模板**，避免被誤當唯一 backlog。
- **風險**：`qsilicon/` 模組邊界若尚未全面落地，口頭「禁止跨模組 import」需搭配 CI 或目錄約束，否則易流於文件自律。

### [`REVIEWER_LOOP_DESIGN.md`](REVIEWER_LOOP_DESIGN.md)

- **優點**：**Layer 1 Python / Layer 2 LLM** 分工正確（成本、可重現性、幻覺標的）；Hard cap 與降級路徑符合日報延遲預算；BQ `reviewer_log` 利於事後調參。
- **建議**：設計稿附的「實作 Prompt」曾寫 **不得改 `schemas.py`**—若 `TradeIdea`／state 需共用欄位，應在 PR 中**明確修訂**該禁令，改為「延長式欄位 + 測試／Gate 更新」，避免 graph 與 schema 分叉。
- **風險**：Reviewer 僅查邏輯不查格式—需確保 **Telegram 出口仍只經** `validate_report`／模板，避免 reviewer 繞過 HTML 白名單。

### [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md)

- **優點**：**延續 Vite PWA** 相對 Next 重寫更合現況；`modules/{name}` + `shared/` 與後端「模組經 API 溝通」對齊；master key 自用足夠。
- **建議**：路由表（如 `/` → `/insights`）必須與**目前** `App.jsx` 對齊後再動大改，避免與既有 `/briefs`／`/terminal` redirect、Report 深連結衝突；FastAPI 拆 `APIRouter` 宜 **逐 router PR**，並同步 [`ENV_TEMPLATE.txt`](../../ENV_TEMPLATE.txt)／[`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md)。
- **風險**：五模組 stub 若一次加滿但無 E2E，易形成「壳大身薄」—每個模組至少保留 **一條 smoke 路徑**（mock API 亦可）。

---

## 3. 前端尚缺方向（CEO 盤點；滾動追蹤）

> **判讀原則**：五板塊 Portal、Phase 2 Command Bar／Workspace、Phase 3 M4／M5、Phase 4 IA（隊列 44）**主線已齊**；本節描述的是 **「上線與規模化」「架構收斂」「付費／治理解鎖後的 live 層」** 等方向性缺口，**非**「畫面尚未存在」。逐項狀態以根目錄 [`CHANGELOG.md`](../../CHANGELOG.md)、[`TODOS.md`](../../TODOS.md)、[`PORTAL_SHIP_CHECKLIST.md`](../PORTAL_SHIP_CHECKLIST.md)、[`DESIGN.md`](../../DESIGN.md) 為準；本節約一季或重大 ship 後由維護者對帳修訂。
>
> **對帳儀式**：每次重大 Portal ship 後，至少回寫 [`CHANGELOG.md`](../../CHANGELOG.md) 與 [`TODOS.md`](../../TODOS.md)；若本節方向判斷被實作改變，補一條「§3 對帳」修訂紀錄。避免 §3 成為第二份 backlog，細項仍回到 `TODOS` 隊列承接。

### 3.1 交付與可觀測（使用者真在 production 用）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **真託管 + deploy 閉環** | PWA deploy 相關 workflow 若仍偏 verify／占位，需選定平台、secrets、rollback 敘事與 **post-deploy smoke** 自動化；實作時以 `.github/workflows/` 真實檔名為準。 | [`PORTAL_SHIP_CHECKLIST.md`](../PORTAL_SHIP_CHECKLIST.md)、`.github/workflows/` |
| **環境與行為一致** | `VITE_*`、API base、SW 更新路徑須在 staging／production **人手簽核**；不可僅以 repo 內 E2E 關帳營運風險。 | 同上清單、`ENV_TEMPLATE.txt` |
| **Web Push 與通知 UX** | BQ／Redis／VAPID／test-send 等多屬營運；前端須預留 **真訂閱／失敗態／權限流程**，避免「接得上、雲上未全跑通」。 | [`TODOS.md`](../../TODOS.md) 隊列 18–21 |

### 3.2 架構與長期可維護（目錄真相）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **五模組邊界落地** | 2026-05-17 repo-side 已把 `App.jsx` route table 抽至 `app/routes/PortalRoutes.jsx`，並將 `eslint.config.js` 模組邊界擴至現有 `src/modules/*` 路由模組；後續新增模組仍須照此清單維護。 | [`TODOS.md`](../../TODOS.md) **隊列 26**（P2／L）、[`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md)、[`CHANGELOG.md`](../../CHANGELOG.md) |
| **Router 抽出與 lint 邊界** | Router 抽出＋`React.lazy` route-level 已上線；續拆含 **`vite.config.js` `manualChunks`（react／react-dom／react-router）**、[`InsightsHome.jsx`](../../data-verification-ui/src/modules/insights/pages/InsightsHome.jsx) tab 子頁 `lazy`、`DailyBriefPage` 對 `TerminalSymbolCard`／`ExecutionIntentsBlotter` 再 `lazy`；[`TerminalSymbolCard.jsx`](../../data-verification-ui/src/components/TerminalSymbolCard.jsx) 內 **`SymbolCandleChart` `lazy`+`Suspense`**（圖表與殼層 async 已分離）。剩餘方向是 **shared API 分層**、**首屏預載** 與測試維護，不再把 `App.jsx` 視為主要膨脹點。 | 隊列 26、`PortalRoutes.jsx`、`vite.config.js`、`DailyBriefPage.jsx`、`TerminalSymbolCard.jsx` |

### 3.3 產品體感與「終端感」（在 ADR 與紅線內）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **Command Bar 下一刀** | 2026-05-17 已補讀者／工作台情境化 inline help，揭示既有指令與 `RUN` 金鑰／節流邊界；更完整「Bloomberg 感」互動仍須先過 [`ADR_COMMAND_BAR_PERMISSIONS.md`](../ADR_COMMAND_BAR_PERMISSIONS.md)，不得新增匿名 W 類指令。 | [`TODOS.md`](../../TODOS.md) 隊列 29、[`DESIGN.md`](../../DESIGN.md) Portal Phase 4、[`CHANGELOG.md`](../../CHANGELOG.md) |
| **44b 進階收斂** | Gate 0 已簽後，仍可由維護者指定「高密度區塊」清單再壓一輪 tab／dock／workspace 與 E2E。 | 隊列 44、§0 Phase 4 |

### 3.4 資料 live 化之後的前端（治理已預留，UI 等開關）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **隊列 45 backlog** | MVRV-Z、exchange flow live、HBM live 等依 **付費／第三方 API 決策** 解鎖；mock／fixture 已交付項目見 [`TODOS.md`](../../TODOS.md) 隊列 45 與 [`CHANGELOG.md`](../../CHANGELOG.md)，本列聚焦 live 或未開 flag 的商務＋後端決策，非缺元件類型。 | [`TODOS.md`](../../TODOS.md) 隊列 45、[`REALTIME_DATA_SOURCES_GOVERNANCE.md`](../REALTIME_DATA_SOURCES_GOVERNANCE.md) |

### 3.5 模組深度（畫面有，故事未完）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **Quant** | Intraday Monitor、更完整 Signal Table 等仍列 backlog。 | [`TODOS.md`](../../TODOS.md) M7 |
| **NotebookLM／Agency** | Repo-side scaffold 在；**live client**、production KPI 仍屬整合面，前端會多狀態與空態層級。 | §0 矩陣 `notebooklm_research`／`agency_agents_research` |
| **產業／管線儀表** | 更深層管線狀態與他板聯動仍待。 | [`TODOS.md`](../../TODOS.md) 隊列 31 |

### 3.6 效能、無障礙、國際化（專業產品最後一哩）

| 方向 | 說明 | 主要依據 |
|------|------|----------|
| **Bundle／code split** | 2026-05-17：`PortalRoutes.jsx` route-level **`lazy()`**；**`vite.config.js` `manualChunks`** 拆 vendor；**`InsightsHome`** 各 tab 子頁 **`lazy()`**；**`DailyBriefPage`** 對 **`TerminalSymbolCard`**／**`ExecutionIntentsBlotter`** 再 **`lazy()`**；**`TerminalSymbolCard`** 內 **`SymbolCandleChart`** **`lazy()`+`Suspense`**（`lightweight-charts` 獨立 async chunk）。後續可依 build 評估 **首屏預載**或 shared API 分層。 | `data-verification-ui` build 輸出、`vite.config`、`PortalRoutes.jsx`、`InsightsHome.jsx`、`DailyBriefPage.jsx`、`TerminalSymbolCard.jsx` |
| **a11y 橫切** | skip link 等單點之後，可盤點 **modal 焦點陷阱、landmark、對比／縮放、reduced-motion**（axe／人測清單即可，不必一次重構）。 | [`DESIGN.md`](../../DESIGN.md)、Playwright |
| **i18n** | 除非讀者群變雙語產品，否則可維持 **繁中／英文化 copy** 於元件與 `portalPhase4`，不必強上 i18n 框架。 | 產品判斷 |

### 3.7 刻意往後（文件已寫，不當「缺口債」）

| 方向 | 說明 |
|------|------|
| **Next.js／SSR** | 對外公開與 SEO 再評估遷移；自用 **Vite PWA** 已足，見 [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md)。 |

### 3.8 NOT in scope（紅線；勿誤列為前端 backlog）

- 真 OMS、自動下單、未治理的付費行情硬塞、放寬 **Telegram HTML 白名單** 或 **`validate_report`** 契約。

### 3.9 維護者若只拍三條優先權

1. **託管與 deploy 真接上**（否則前端能力難在雲上驗收）。
2. **隊列 26**（Router 抽出＋明文模組 import 邊界＋route-level `lazy`＋**`manualChunks` + Insights tab `lazy` + `DailyBriefPage` 子元件 `lazy` + `TerminalSymbolCard` 內圖表 `lazy`**）；下一輪若做，優先 **shared API 分層** 與 **首屏圖表預載**（產品可接受再補）。
3. **隊列 29 已完成 ADR 內第一刀**（inline help + 權限邊界）；下一輪若做，先補測再擴指令，不新增匿名 W 類指令。

---

## 修訂紀錄

- **2026-05-17（隊列 26 · route-level lazy）**：`PortalRoutes.jsx` 以 `React.lazy`+`Suspense` 分拆板塊與 Report 等頁；§3.2／§3.6／§3.9 對帳更新（主入口 chunk 縮小）。
- **2026-05-17（隊列 26 · bundle 續拆）**：`vite.config.js` `manualChunks`（react／react-dom／react-router）；`InsightsHome` 各 tab 子頁 `lazy` + `SymbolDeepDive` 條件 lazy；`DailyBriefPage` 對 `TerminalSymbolCard`／`ExecutionIntentsBlotter` `lazy`；§3.2／§3.6／§3.9 對帳更新（終端工作區殼層 chunk 縮小；圖表仍隨 `TerminalSymbolCard` 同 chunk，同日 **圖表子 chunk** 條目拆出）。
- **2026-05-17（隊列 26 · 圖表子 chunk）**：`TerminalSymbolCard.jsx` 內 `SymbolCandleChart` `lazy`+`Suspense`（`lightweight-charts` 與符號卡殼層 async 分離）；§3.2／§3.6／§3.9 對帳更新。
- **2026-05-17（隊列 26／29 repo-side 第一刀）**：§3.2 改列 Router 抽出、`PortalRoutes.jsx` 與完整 `src/modules/*` lint 邊界已完成；§3.3 改列 Command Bar inline help 已完成且仍受 ADR 權限邊界約束；§3.9 優先權改為剩餘方向（deploy、code split／shared API、受測指令擴充）。
- **2026-05-17（§3 對帳儀式）**：§3 增補 Portal ship 後的 `CHANGELOG`／`TODOS` 對帳規則；§3.1 改以 `.github/workflows/` 真實檔名為準；§3.4 澄清隊列 45 已交付 mock／fixture 與待解鎖 live／flag 的分工；修正 §2 `TERMINAL_FRONTEND_PLAN` 繁中用字。
- **2026-05-16（對帳）**：§0 Phase 3「仍列 backlog」改寫 — SSE 短期 token TTL／`SSE_MAX_EVENTS_PER_SEC` 已於 2026-05-16 交付，僅留四模組 UI 深化；§0 Phase 4 標題與「REVIEW 前可先決」段改為「Gate 0 已 REVIEW（2026-05-16）」並列入五項簽核值。
- **2026-05-16**：§0 Phase 4 增 **實作規劃**（44a–44d 表、Gate 0、`TODOS` 隊列 44）；§2 `TERMINAL_FRONTEND_PLAN` 建議句改與 **`App.jsx`** 路由現況對齊。
- **2026-05-15**：§0 下新增 **Phase 4**（Portal **讀者層 × 工作台層** IA 收斂：原則、A／B／C 分段、刻意不做、REVIEW 決策點）；本檔矩陣狀態欄改為 **Phase 0–4**；§1 執行順序增第 4 點對齊 Phase 4。
- **2026-05-17（§3 初版補登）**：新增 **§3 前端尚缺方向**（CEO 盤點：交付與可觀測、隊列 26 架構、Command Bar／ADR、live 切片、模組深化、效能／a11y、刻意往後與 NOT in scope；§0 矩陣本檔欄同步補「§3」）。實作狀態仍以 `CHANGELOG`／`TODOS`／程式為準。
- **2026-05-14（Phase 3）**：§0 下新增 **Phase 3 Backlog Go-Live**（M4 SSE 閉環、M5／M4 排程、contract smoke 擴充）；slices 1–5 commit SHA 見 CHANGELOG **2026-05-14** `### Backlog Go-Live`。
- **2026-05-14**：§0 下新增 **Phase 2**（Portal 產品切片：Crew HUD、Workspace 跨分頁）；本檔矩陣狀態欄改為 **Phase 0–2**。
- **2026-05-06**：新增並更新 `architecture/` 文件狀態矩陣；同日補上 NotebookLM／Agency／TradingView repo-side scaffold 與視覺化主要 repo backlog。
- **2026-04-18**：初版 — 總表連結、`architecture/` 三檔看法；與 [`TODOS.md`](../../TODOS.md)、[`CHANGELOG.md`](../../CHANGELOG.md) 對齊。
