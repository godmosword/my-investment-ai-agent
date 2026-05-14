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
| [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) | ✅ 狀態索引 + Phase 0–2 | 本檔 §0 矩陣對齊各檔 ✅／🟡；§0 下 **Phase 0** 為架構目錄判讀治理；**Phase 2**（Portal 產品切片）見 §0 Phase 2 小節與 [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) 現況。 |

### Phase 0 — `architecture/` 判讀與治理（已定案）

1. **權威順序（事實）**：已交付行為 → 根目錄 [`CHANGELOG.md`](../../CHANGELOG.md) → [`TODOS.md`](../../TODOS.md)（已交付摘要／隊列）→ 程式碼。**本節上方矩陣**為 `docs/architecture/` **單一索引**：✅＝已閉環或維護導覽；🟡＝仍有 backlog、staging 細項、或 **研究／optional scaffold**。
2. **研究稿 ≠ 產品承諾**：`notebooklm_research`／`agency_agents_research`／`tradingview_mcp_research` 等標 🟡 之檔案，**不**視為預設上線範圍。若要列入產品里程碑，須另有 **ENV／紅線（含資料源治理 [`REALTIME_DATA_SOURCES_GOVERNANCE.md`](../REALTIME_DATA_SOURCES_GOVERNANCE.md)）／驗收** 一句話，並落入 [`TODOS.md`](../../TODOS.md) 隊列（避免「讀架構＝全部要做」）。
3. **[`AI_CONTEXT.md`](AI_CONTEXT.md)**：承載協作紅線、工程原則與願景；**「現況／版本」細節**以 `CHANGELOG.md` 與程式為準，本檔與 `AI_CONTEXT` **不**承擔逐 commit 對帳。

### Phase 1 — 日報可信／隊列 27（staging 對照）

**Repo 側**：執行稿、環境核對表、**TODOS／CHANGELOG 回填模板**見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)。**不在 CI 自動執行**；通過與否由 staging 營運於 [`TODOS.md`](../../TODOS.md) 隊列 **27** 或同步狀態行關帳。**可選同日**：Reviewer rollout（隊列 35）見 [`REVIEWER_PRODUCTION_ROLLOUT.md`](../REVIEWER_PRODUCTION_ROLLOUT.md) 與 [`scripts/verify_reviewer_rollout_env.py`](../../scripts/verify_reviewer_rollout_env.py)，與本 smoke **非**硬性綁定。

### Phase 2 — Portal「產品面」可驗收切片（2026-05-14）

**定義**：讀者摸得到、且不破離線／即時資料紅線的增量；每塊以 Playwright 或既有契約測試封頂。

**已落檔／落碼**：[`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) 現況行；Command Bar **`terminal-crew-status-hud`**（輪詢 **`GET /api/run-crew/status`**）；Workspace **`storage` + `qsi_workspace_changed`** 跨分頁同步（[`workspaceSync.js`](../../data-verification-ui/src/constants/workspaceSync.js)）；E2E [`workspace-cross-tab.spec.js`](../../data-verification-ui/e2e/workspace-cross-tab.spec.js)。**仍列 backlog**（`TODOS` 隊列 29／34）：權限細節、排程型 digest 等。

---

## 1. 執行順序（維護者）

1. **穩住日報可信與 Gate**（與 Terminal 並行但不可讓步）：對齊 `TODOS.md`「維護者意見」與 `validate_report` 契約。
2. **中段產品節奏**：以 `TERMINAL_MID_TIER_ROADMAP` 已交付能力為錨；新增能力須有 API／PWA 契約測試或 Playwright 再擴張。
3. **長線 Portal**：依 `TERMINAL_FRONTEND_PLAN` 的 **Shell → daily-brief → position → …** 順序切片；避免一次重構 `api.py` 單體—**incremental `APIRouter`** 較可 review。

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

- **優點**：**延續 Vite PWA** 相对 Next 重寫更合現況；`modules/{name}` + `shared/` 與後端「模組經 API 溝通」對齊；master key 自用足夠。
- **建議**：路由表（如 `/` → `/briefs`）必須與**目前** `App.jsx`／`Router` 對齊後再動大改，避免與既有 `/terminal`、Report 深連結衝突；FastAPI 拆 `APIRouter` 宜 **逐 router PR**，並同步 [`ENV_TEMPLATE.txt`](../../ENV_TEMPLATE.txt)／[`DASHBOARD_CONTRACT.md`](../DASHBOARD_CONTRACT.md)。
- **風險**：五模組 stub 若一次加滿但無 E2E，易形成「壳大身薄」—每個模組至少保留 **一條 smoke 路徑**（mock API 亦可）。

---

## 修訂紀錄

- **2026-05-14**：§0 下新增 **Phase 2**（Portal 產品切片：Crew HUD、Workspace 跨分頁）；本檔矩陣狀態欄改為 **Phase 0–2**。
- **2026-05-06**：新增並更新 `architecture/` 文件狀態矩陣；同日補上 NotebookLM／Agency／TradingView repo-side scaffold 與視覺化主要 repo backlog。
- **2026-04-18**：初版 — 總表連結、`architecture/` 三檔看法；與 [`TODOS.md`](../../TODOS.md)、[`CHANGELOG.md`](../../CHANGELOG.md) 對齊。
