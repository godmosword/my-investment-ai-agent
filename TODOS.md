# Q-Silicon — 工程與產品待辦（彙總）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md)。**路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)。**執行版路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md)（2026 Q2）。

**同步狀態（2026-04-21）**：本檔僅列 **`[ ]` 未完成** 與維護者排序；**已交付行為**以 CHANGELOG 與下方「已落地（備查）」為準。四維評分表與新建議 backlog 仍適用，見 [未完成項四維評分（2026-04）](#未完成項四維評分與新建議2026-04)。長期里程碑 → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。演進藍圖（Mock／Plugin／LangGraph 等）→ [演進藍圖](#演進藍圖--技術路線)。**本輪未完** → [本輪後續／未完（2026-04-10）](#本輪後續未完2026-04-10)。**開源對接細項** → [OSS 開源生態整合計畫](#oss-開源生態整合計畫oss-integration-roadmap)。**外部架構審閱（機構級建議彙整）** → [8 板塊 backlog](#外部架構審閱-backlog8-板塊2026-04)（與波次 **G**、OSS／演進藍圖交叉對照，**不取代**檔首維護者排序與紅線）。

---

## 維護者意見（執行順序）

1. **先穩「選標多樣性 + Gate 可信」再堆功能** — Direction **1A／2A**；**1B 商業化暫緩** → 階段 E。
2. **Direction 2B** — [`scripts/oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 寫入 `docs/oss_candidates/`；排程 [`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)。**勿手改**下方 `OSS_SCOUT_AUTO_*` 區塊。
3. **Direction 3** — [`crew_company.py`](crew_company.py) 試點；擴四職能前先量測 **`CREW_FUTURE_TIMEOUT_SEC`**。
4. **P0「全 API hard fail」** — 務實做法：**[`PIPELINE_STRICT_ENV`](main.py)** + 金鑰盤點；生產／排程強制。

---

## 未勾選項速覽

| 波次 | 項目（詳見下方章節） |
|------|----------------------|
| **A** | 閾值實驗、Critical env 定稿 |
| **B** | 日報契約持續收斂（細節見 CHANGELOG） |
| **C** | Gate 人審提示、自適應門檻 BQ 接線 |
| **D** | OSS：HF／GraphQL、整合提案 Agent |
| **E** | Company 四職能、War Room、PWA Web Push |
| **F** | [OSS 開源生態整合計畫](#oss-開源生態整合計畫oss-integration-roadmap)（rtk／goose／fredapi、戰情室圖表、OMS 模擬盤、回測） |
| **G** | [外部架構審閱 backlog](#外部架構審閱-backlog8-板塊2026-04)（套件化、觀測、成本、產品化、安全、部署、開源經營、測試與前瞻） |

### Priority（未完成，1＝最優先）

| Pri | 項目 | 說明 |
|-----|------|------|
| **1** | 閾值實驗 | [`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) |
| **2** | Critical env 定稿 | [`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) |
| **3** | Gate 失敗 → 人審提示 | [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)（禁自動改 prompt） |
| **4** | PWA Web Push 持久化 | 不阻塞日報主線 |
| **5** | HuggingFace／GraphQL | Direction 2B |
| **6** | 整合提案 Agent | 建議在 (5) 之後 |
| **7** | Direction 3 四職能 + War Room | [`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md) |
| **8** | 模板／QSREC 顯示審計 | ~~進行中~~ **已收斂（2026-04-21）**：`strip_usd` 濾鏡 + `ExecutableTradeLeg` 對 `rr` 等欄位去 `$`；見 [`templates/telegram_report.j2`](templates/telegram_report.j2)、[`schemas.py`](schemas.py) |

### LangGraph 路徑（可選引擎）

| Pri | 項目 | 說明 |
|-----|------|------|
| **LG-1** | 生產觀測 | `GRAPH_DEEP_RESEARCH_TOOL_LLM=1` 下成本、延遲、失敗率；是否與 `GRAPH_LLM_DEBATE` 預設組合文件化 |
| **LG-2** | 工具覆蓋 | ~~待評估~~ **已擴充（2026-04-21）**：[`graph/graph_tools.py`](graph/graph_tools.py) 納入 `fetch_onchain_metrics_btc`（`onchain_metrics_tool`） |
| **LG-3** | 測試 | ~~mock tool_calls~~ **部分落地（2026-04-21）**：`deep_research` 決定性路徑 + `RESEARCH_TOOLS` 覆蓋測試（`test_graph_crew.py`、`test_graph_tools_extended.py`）；完整 mock LLM multi-round 仍待補 |

<a id="本輪後續未完2026-04-10"></a>

### 本輪後續／未完（2026-04-10）

> **已落地（本輪對齊，細節見 CHANGELOG）**：LangGraph native `final_formatter` 以結構化 **`FormatterInputPacket` JSON** 為 prompt 唯一輸入；`trade_picker` 經 [`execution_intents.py`](execution_intents.py) 追加 **`.qsilicon/execution_intents.jsonl`**（不下單）；FastAPI [`GET /api/war-room/latest`](api.py)；PWA **Today** 讀 war-room（[`data-verification-ui/`](data-verification-ui/)）；graph 工具窄介面／`MOCK_APIS` fixture 路徑。

- [x] **PWA War Room 元件（首期）**：[`WarRoomCard.jsx`](data-verification-ui/src/components/WarRoomCard.jsx) + intent 狀態篩選；進一步視覺拋光／錯誤態 UX 仍待迭代
- [ ] **RAG／Glassbox**：「Chat with the Report」須錨定當日報告內文（與 [演進 Phase 4](#演進藍圖--技術路線) 一致；嚴守工具數字紅線）
- [ ] **真 OMS／執行層**：獨立 daemon、BQ／SQLite 輪詢 `PENDING` intent、風控與合規表態（目前僅 jsonl 骨架；見下方 [OSS Phase 3](#phase-3-模擬盤與訂單管理系統-oms--paper-trading)）
- [ ] **觀測**：`GRAPH_DEEP_RESEARCH_TOOL_LLM=1` 下成本、延遲、**cache／重試命中率**（對齊 **LG-1**、與下方 **rtk** 節流）

<a id="未完成項四維評分與新建議2026-04"></a>

## 未完成項四維評分與新建議（2026-04）

維度 **1–5**（成本越高數字越大）。**信任／紅線**＝與無幻覺、`validate_report`、`main.py` 雙線程、Telegram HTML 白名單之一致性。

### Pri 1–9 簡表

| 項目 | 影響 | 成本 | 信任 | 策略契合 | 簡評 |
|------|:---:|:---:|:---:|:---:|------|
| 1 閾值實驗 | 4 | 2 | 4 | 5 | 驗證選標是否過於固定 |
| 2 Critical env | 4 | 2 | 5 | 5 | 生產契約 |
| 3 Gate 人審 | 4 | 3 | 5 | 4 | 閉合 `gate_failure_log` |
| 4 Web Push | 2 | 3 | 4 | 3 | 體驗加分 |
| 5 HF／GraphQL | 3 | 4 | 3 | 3 | 須嚴格掛工具 |
| 6 提案 Agent | 3 | 5 | 3 | 2 | 安全與 review 負載 |
| 7 Direction 3 | 3 | 5 | 3 | 2 | token／timeout |
| 8 模板審計 | 3 | 2 | 4 | 4 | 顯示一致性（已落地 strip_usd + schema 去 `$`） |

### 波次／Phase 濃縮

| 區塊 | 備註 |
|------|------|
| 自適應門檻 BQ | [`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) 骨架已備 |
| Phase 1 Mock／Plugin | [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) |
| Phase 2 Execution | 合規與產品表態後 |
| Phase 3 LangGraph | **部分落地**：`graph/`、`USE_LANGGRAPH_ENGINE`、deep research **`RESEARCH_TOOLS`**（CHANGELOG **2026-04-09**）；完整取代 `crew.py` 仍為長期項 |
| Phase 4 Glassbox／RAG | RAG 須錨定當日報告內文 |

### 建議順序

1. Pri **2** + **1** → 2. Pri **8**（已完成首輪）→ 3. 波次 **C** + Pri **3** → 4. Pri **4** → 5. **5→6**、**7** 與 Phase 2+（依資源）

### 新建議 backlog（骨架已備；持續迭代）

1. Gate 內部儀表 — [`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)  
2. 結構化 dry-run — [`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)、[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)  
3. 美股備援觀測 — `EQUITY_BACKFILL_SCRATCHPAD_LOG`  
4. Prompt 登記 — [`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)  
5. `asset_market` 展示規則細化 — [`schemas.py`](schemas.py)（台股專項已自維護清單移除）  
6. Mock smoke — [`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)  
7. 觀望 vs QSREC — [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)

<a id="外部架構審閱-backlog8-板塊2026-04"></a>

## 外部架構審閱 backlog（8 板塊，2026-04）

來源：針對 [**Q-Silicon Institutional Research AI Agent**](https://github.com/godmosword/my-investment-ai-agent) 之機構級書面審閱；以下拆成**可勾選工程項**，並**對齊**本檔既有章節（維護者排序、紅線、[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[OSS 計畫](#oss-開源生態整合計畫oss-integration-roadmap)、[演進藍圖](#演進藍圖--技術路線)、[`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)）。**建議執行序（審閱方）**：先 **1→2→5**（組織、可靠性、安全）約 1 週；再 **3→4**（成本、產品化）2–4 週；長期 **6→7→8**。

### G-1 — 代碼組織與可維護性（對齊波次 B／工具模組化 ADR）

- [ ] **標準套件目錄**：評估 `src/` + `agent/`、`pipeline/`、`report/`、`storage/`、`ui/` 等拆分（現為根目錄 flat scripts；遷移須對齊 `pytest`、`Dockerfile`、`main` 進入點）
- [ ] **`pyproject.toml`**：`uv` 或 `poetry` 鎖依版本；`ruff` 擴規則（如 `I`、`UP`、`SIM`、`RET`）；**型別** `pyright` 或 `mypy`（漸進 strict，避免一次性全紅）
- [ ] **設定集中**：`pydantic-settings` v2（`SettingsConfigDict`）統一 env 驗證；與現有 [`config.py`](config.py)、[`main.py`](main.py) `_validate_env_types` **漸進合併**，避免破壞 `PIPELINE_STRICT_ENV`

### G-2 — 可靠性、觀測性與錯誤處理（對齊 P3、LG-1、`gate_failure_log`）

- [ ] **結構化日誌**：`structlog`（或等價）統一 tool／LLM／gate 事件格式
- [ ] **分散式追蹤**：OpenTelemetry，`trace_id` 貫穿 tool call、LLM、validate_report（與現有 BQ log 互補）
- [ ] **錯誤匯聚**：Sentry 或 GCP Error Reporting；Gate 失敗可選自動開 issue／通知（與 [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md) 協調）
- [ ] **Circuit breaker**：`pybreaker` 或自寫，套於 CoinGlass／Tavily／Financial Datasets 等外連（與 **無幻覺** 一致：斷路時回傳 `[DATA_MISSING:…]` 或 N/A，禁止 LLM 補數字）
- [ ] **全局限流**：`aiolimiter`（或既有 retry 之上）+ 設定如 `MAX_CONCURRENT_TOOLS`（對齊 `main.py` ThreadPoolExecutor 安全）
- [ ] **降級路徑**：validate 全失敗時「簡易模式」（例：僅雙軌研究員、略過審計／編輯）— **須產品表態** 與 Telegram 讀者標示，避免與正式日報混淆

### G-3 — 成本優化與 LLM 管理（對齊 OSS Phase 1 rtk、[`docs/COST_PER_MODEL.md`](docs/COST_PER_MODEL.md)）

- [ ] **LLM Router**：依 `task` + `budget_level` 選模型（接 LiteLLM／現有 `MODEL_*` env）
- [ ] **Prompt 快取**：LiteLLM caching（Redis 或 DiskCache）；與 **rtk** 節流代理實驗並列評估
- [ ] **Graph deep research 預算**：token／tool-call 硬上限（呼應 `GRAPH_DEEP_RESEARCH_TOOL_LLM`）
- [ ] **Formatter 分層**：預設輕量模型、僅 `PIPELINE_STRICT_ENV=1` 等機構模式用高階模型（對齊 crew／graph formatter）
- [ ] **Metrics**：`prometheus_client` 暴露 `llm_tokens_total`、`cost_usd_total`（可選 sidecar；不影響預設無 K8s 部署）

### G-4 — 功能擴展與產品化（對齊階段 E、Direction 3）

- [ ] **區域／供應鏈宇宙擴充**（非台股專線）：擴充 `assets_universe` + 資料源；須另開產品範圍與資料授權評估
- [ ] **Flash Brief**：`monitor_intraday` 升級 WebSocket／SSE（FastAPI），條件觸發（波動、財報前窗口）— **頻率與 API 成本** 須 Gate
- [ ] **多語輸出**：`report_render` 路徑加英／繁／簡（翻譯 API 或離線；**HTML 白名單**不變）
- [ ] **Backtest 2.0**：`vectorbt`／`backtrader` 等 + Sharpe／MDD／WinRate 寫入 BQ（與 [OSS Phase 4](#phase-4策略強化與機構級回測strategy-enhancement--backtesting) 合併評估）
- [ ] **Human-in-the-Loop**：Gradio／Chainlit + Telegram reply 觸發局部重產（與 [`report_editor.py`](report_editor.py) 整合）
- [ ] **Macro 第三軌**：專責 FRED／IMF 等之 `MacroAgent` 或節點（與 [fredapi](#phase-1基礎建設與降本增效infrastructure--cost-reduction)、現有 macro 工具 **單一數字來源**）

### G-5 — 安全性、合規與 Secret（對齊 P0、紅線）

- [ ] **Secret 託管**：GCP Secret Manager 或 Infisical；本機仍可用 `.env`（[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)）
- [ ] **CI Secret 掃描**：GitHub Actions 強制 `gitleaks`（已有 [`.gitleaks.toml`](.gitleaks.toml) 則補 workflow）
- [ ] **免責與法遵**：[`templates/telegram_report.j2`](templates/telegram_report.j2) 固定投資人免責段落（與 **STRICT_INSTITUTIONAL_PHASE_A** 等現有 `blockquote` 不衝突為原則）
- [ ] **BQ 最小權限**：寫入用 SA 僅必要 dataset／表（見 [`bigquery_writer.py`](bigquery_writer.py) 部署說明）
- [ ] **PII／GDPR 預研**：若未來訂閱制／多租戶，資料分類與保留策略

### G-6 — 部署與擴展性（對齊 [`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、演進 Phase 1）

- [ ] **`docker-compose.prod.yml`**：Redis + Prometheus + Grafana（可選；與現有 [`Dockerfile`](Dockerfile) 並存）
- [ ] **Nightly 效能基準**：workflow 將管線耗時、token 摘要寫 BQ 或 artifact（與 [`nightly-ci.yml`](.github/workflows/nightly-ci.yml) 協調）
- [ ] **排程基礎設施**：Cloud Run + Scheduler vs GKE + Argo **評估文件**（成本／維運）
- [ ] **多租戶執行**：Celery／佇列化 `main` 路徑（與 [階段 E — 商業化](#階段-e--長期里程碑) 綁定；**資產宇宙隔離**）

### G-7 — 文件、社群與開源經營

- [ ] **README**：Badges（Python、CI、License）、1 分鐘 Demo 連結（Loom 等）
- [x] **`CONTRIBUTING.md`** + **`CODE_OF_CONDUCT.md`** + **`LICENSE`（MIT）**（2026-04-21）
- [ ] **License**：README 與根目錄 `LICENSE` 同步聲明（可補 badge）
- [ ] **ADR 索引**：`docs/` 內 ADR 匯總頁或 GitHub Wiki 導覽
- [ ] **對外內容**：技術文章／串文（零幻覺管線、雙軌 Gate 等）— 與產品節奏協調

### G-8 — 測試與技術前瞻

- [ ] **Property-based**：`hypothesis` 擴充 [`schemas.py`](schemas.py)／邊界契約（與 `pytest -m boundary`、[`docs/BOUNDARY_TEST_MATRIX.md`](docs/BOUNDARY_TEST_MATRIX.md)）
- [ ] **E2E**：Playwright 跑 Streamlit + PWA 關鍵路徑（與 [`data-verification-ui/`](data-verification-ui/)）
- [ ] **LLM 可觀測**：LangSmith 或 LangFuse（與 G-2 OTel **擇一或分層**）
- [ ] **前瞻**：新模型（如 Grok 世代）tool-use 評估；多模態（圖表 + vision）**僅在工具輸出影像／URL 可驗證時** 納入，避免違反數字紅線

---

## 橫切：選幣／選股仍偏固定

- [ ] **閾值實驗**：staging 調整 `PICK_ROTATION_OVERRIDE_MIN_GAP` 等 — [`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md)

---

## P0 — 管線穩定性

- [ ] **Critical env 策略定稿** — [`PIPELINE_STRICT_ENV`](main.py)、[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md)

---

## P1 — 日報品質

（多數規則與後處理已落地 — 見 CHANGELOG **2026-03-28** 起。）

---

## P2 — 自動化與工程債

（cache 拆分、bench、fixtures — 見 CHANGELOG。）

---

## P3 — 觀測與自適應

- [ ] **Gate 失敗 → 提示（人審）** — [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)

---

## Direction 1A — 視覺化

- [ ] **PWA Web Push 持久化**（Service Worker 等）

---

## Direction 1B — 商業化（暫緩）

見 **階段 E**。

---

## Direction 2A — 績效反饋

（回測權重、HIT_STOP、自適應骨架 — 已落地，見「已落地」。）

---

## Direction 2B — OSS Scout

| 狀態 | 項目 |
|------|------|
| [ ] | HuggingFace／GraphQL 擴充 |
| [ ] | 整合提案 Agent（不自動 merge） |

---

## Direction 3 — Multi-Agent

| 狀態 | 項目 |
|------|------|
| [ ] | 四職能 crew |
| [ ] | 跨部門 Arbiter + 風險預算 |
| [ ] | Company War Room（PWA） |

**已試點**：`COMPANY_CREW_ENABLED` — CHANGELOG。

---

## 已落地（備查）

**2026-04-09**：LangGraph **`graph/graph_tools.py`**、`RESEARCH_TOOLS`、**`GRAPH_DEEP_RESEARCH_TOOL_LLM`**、**`deep_dive_round_*`** raw_data — CHANGELOG 當日 **Added／Changed**。

**2026-03-31 前主表已移除之 `[x]`** — 詳見 CHANGELOG **2026-03-28～31** 與下列：

- API guard：[`api_schema.py`](api_schema.py)  
- 盤中監控：[`monitor_intraday.py`](monitor_intraday.py)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)  
- LLM log／Gate failure BQ：[`bigquery_writer.py`](bigquery_writer.py)、[`test_gate_failure_log.py`](test_gate_failure_log.py)  
- 新聞新鮮度、錨定日、Telegram 歷史、tools 快取拆分、離線 fixtures — `ENV_TEMPLATE.txt` + CHANGELOG  
- 文件：[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)

---

## 階段 E — 長期里程碑

索引：[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。

### 商業化（暫緩）

| 狀態 | 項目 |
|------|------|
| [ ] | Firebase Auth + FastAPI `Depends` |
| [ ] | Stripe Checkout + Webhook |
| [ ] | API tier、rate limit — [`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md) |
| [ ] | 多租戶 Telegram |
| [ ] | Landing + Checkout 導流 |

---

<a id="roadmap-technical-saas-execution-brain"></a>

## 演進藍圖 — 技術路線

精簡版：[ROADMAP_VISION](docs/ROADMAP_VISION.md#roadmap-evolution-condensed)、[PHASE_F_BACKLOG](docs/PHASE_F_BACKLOG.md#roadmap-phases-1-4-condensed)。**時程敘述僅供對照產品文件；工程排程以維護者意見為準。**

### Phase 1：開源生態與容錯

- [ ] **Mock-Driven Development** — **部分**：`MOCK_APIS`、`tools/base`、`market_fixture_dict`、fixtures 已接線  
- [ ] **Tool Plugin System** — [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)  
- [ ] **Docker Compose 全端** — [`docker-compose.yml`](docker-compose.yml)

### Phase 2：訊號 → 執行

- [ ] **Execution Layer** — 合規與定位確認後  
- [ ] **Intraday Monitor V2**

### Phase 3：次世代大腦

- [ ] **LangGraph 完整取代 crew 主路徑** — **部分**：`graph/`、`USE_LANGGRAPH_ENGINE`、debate／arbiter／deep research（含 **工具橋接**，CHANGELOG **2026-04-09**）；保留 Crew 退路  
- [ ] **Multi-Agent Debate 產品化** — 與成本／timeout 治理綁定

### Phase 4：觀測與 IP

- [ ] **Glassbox 圖表深化**  
- [ ] **RAG「Chat with the Report」**（須錨定當日內文）  
- [ ] **語音晨報**

---

<a id="oss-開源生態整合計畫oss-integration-roadmap"></a>

## OSS 開源生態整合計畫（OSS Integration Roadmap）

基於「降本增效、解耦架構、走向自動化交易」原則，將頂級開源專案對接至 Q-Silicon 投研管線。**與上方 [演進藍圖](#演進藍圖--技術路線) 互補**：此節為**可勾選執行細項**；排程仍以檔首維護者意見與紅線為準。

### Phase 1：基礎建設與降本增效（Infrastructure & Cost Reduction）

**目標**：降低開發與 API 成本，強化主編（Arbiter）的客觀數據感知力。

- [ ] **導入 Token 節流代理（`rtk`）**
  - [ ] 部署本地 `rtk`（Rust Proxy）服務
  - [ ] 修改 [`config.py`](config.py) 與 LiteLLM 呼叫層，將流量導向代理
  - [ ] 驗證多空 Agent 辯論重試時的 Cache 命中率（預期節省 60–90% Token）
- [ ] **零成本本地開發 Agent（`goose`）**
  - [ ] 安裝 `goose` 作為本機開發選項（對照付費 CLI 流程）
  - [ ] 建立專屬 `.gooserules` 或 Prompt，對齊 Q-Silicon LangGraph／紅線
- [ ] **彭博級總經數據接入（`fredapi`）**
  - [ ] 安裝 `fredapi` 套件
  - [ ] 重構 [`macro_context_tool`](tools_legacy.py)（目前於 `tools_legacy.py`；可拆分至 `tools/` 模組），串接 FRED（可輔以 `fredapi`）：CPI、失業率、美債殖利率等（**數字僅來自 API／工具**，禁止 LLM 捏造）
  - [ ] 確保 `arbiter_node` 與 `deep_research_node` 能穩定調用並解讀上述數據

### Phase 2：戰情室視覺化升級（War Room Visualization Upgrade）

**目標**：將結構化報告轉為機構級實時監控面板。

- [ ] **整合輕量級 K 線圖表（`lightweight-charts`）**
  - [ ] 在 [`data-verification-ui/`](data-verification-ui/) 安裝 `lightweight-charts`
  - [ ] 開發 `ChartComponent.jsx`，讀取 SQLite／BigQuery 歷史報價（權限與快取策略另定）
  - [ ] 將 LangGraph `bull_arguments`／`bear_arguments` 渲染為 K 線圖互動標註（Markers）
- [ ] **終端實時監控介面（參考 `polyrec`）**
  - [ ] 評估 Terminal UI 框架（如 `rich` 或 `textual`）
  - [ ] 升級 [`monitor_intraday.py`](monitor_intraday.py)：CLI 實時監控資金費率、訂單簿深度等

### Phase 3：模擬盤與訂單管理系統（OMS & Paper Trading）

**目標**：零實盤資金風險下驗證執行層與選幣／選股邏輯。

- [ ] **獨立 OMS 執行引擎（參考 `polybot` 解耦思維）**
  - [ ] 新增 `execution_engine.py`（純 Python Daemon，**不含 LLM**）
  - [ ] SQLite／BigQuery 輪詢，監聽狀態為 `PENDING` 的交易意圖（Intent）
  - [ ] 嚴格風控：部位上限、最大回撤鎖定等
- [ ] **AI 專屬模擬盤（參考 `polymarket-paper-trader`）**
  - [ ] `PaperTraderClient`：模擬 CCXT／Alpaca 下單 API
  - [ ] 手續費（Fee）與滑價（Slippage）模型
  - [ ] `trade_picker_node` 虛擬資金（如 USD 100,000）前向測試（Forward Testing）

### Phase 4：策略強化與機構級回測（Strategy Enhancement & Backtesting）

**目標**：導入高品質 Alpha 訊號與可信量化回測管線。

- [ ] **「聰明錢／巨鯨跟單」雷達**
  - [ ] 爬蟲或 API：Nansen／Arkham 標籤或特定鏈上合約監控（**合規與 ToS 先行**）
  - [ ] 整合至 [`onchain_metrics_tool`](tools_legacy.py)（或拆分後的 `tools/` 模組）
  - [ ] 調整 LangGraph Prompt：對「聰明錢買入」等訊號權重（仍須錨定工具輸出）
- [ ] **策略邏輯逆向工程（借鑒 `Polymarket-Trading-Bot`）**
  - [ ] 解析動能、套利、均值回歸等策略邏輯
  - [ ] 翻譯為自然語言 **Strategy Guidelines**，作為 Context 餵給 `trade_picker_node`
- [ ] **專業級策略回測管線（`prediction-market-backtesting`／Nautilus 等）**
  - [ ] 研究並整合基於 **NautilusTrader**（或選定引擎）至 [`backtest.py`](backtest.py)
  - [ ] 將 BigQuery AI 決策日誌匯出並轉為相容格式
  - [ ] 產出含 Sharpe、Max Drawdown 等之回測報告

---

## OSS Scout 週報（自動）

> 每週搜尋 GitHub 熱門／指定 topic 之 repo；**適配理由、README 摘錄、低分說明**僅在當日研究稿與 JSON。**本節**只保留連結、摘要表與短勾選（避免 TODOS 被長標籤洗版）。詳稿：`docs/oss_candidates/YYYY-MM-DD-revision-plan-draft.md`。

<!-- OSS_SCOUT_AUTO_BEGIN -->

### 2026-04-01

**本週 OSS 候選（2026-04-01）** — 依適配度排序；**細節只讀研究稿**（**不自動合併**）。

- 研究稿：[`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md)
- 機讀：[`2026-04-01-digest.json`](docs/oss_candidates/2026-04-01-digest.json)、[`2026-04-01-candidates.json`](docs/oss_candidates/2026-04-01-candidates.json)

| Repo | 適配 | ★ |
|:-----|:----:|--:|
| [`OpenBB-finance/OpenBB`](https://github.com/OpenBB-finance/OpenBB) | 5/5 · 建議優先評估 | 64841 |
| [`StockSharp/StockSharp`](https://github.com/StockSharp/StockSharp) | 5/5 · 建議優先評估 | 9508 |
| [`TA-Lib/ta-lib-python`](https://github.com/TA-Lib/ta-lib-python) | 5/5 · 建議優先評估 | 11822 |
| [`UFund-Me/Qbot`](https://github.com/UFund-Me/Qbot) | 5/5 · 建議優先評估 | 16803 |
| [`cantaro86/Financial-Models-Numerical-Methods`](https://github.com/cantaro86/Financial-Models-Numerical-Methods) | 5/5 · 建議優先評估 | 6732 |
| [`je-suis-tm/quant-trading`](https://github.com/je-suis-tm/quant-trading) | 5/5 · 建議優先評估 | 9566 |
| [`jesse-ai/jesse`](https://github.com/jesse-ai/jesse) | 5/5 · 建議優先評估 | 7613 |
| [`lballabio/QuantLib`](https://github.com/lballabio/QuantLib) | 5/5 · 建議優先評估 | 6932 |
| [`microsoft/qlib`](https://github.com/microsoft/qlib) | 5/5 · 建議優先評估 | 39646 |
| [`myhhub/stock`](https://github.com/myhhub/stock) | 5/5 · 建議優先評估 | 12112 |
| [`polakowo/vectorbt`](https://github.com/polakowo/vectorbt) | 5/5 · 建議優先評估 | 7037 |
| [`ranaroussi/quantstats`](https://github.com/ranaroussi/quantstats) | 5/5 · 建議優先評估 | 6914 |
| [`wilsonfreitas/awesome-quant`](https://github.com/wilsonfreitas/awesome-quant) | 5/5 · 建議優先評估 | 25254 |
| [`firmai/financial-machine-learning`](https://github.com/firmai/financial-machine-learning) | 4/5 · 高適配 | 8467 |
| [`paperswithbacktest/awesome-systematic-trading`](https://github.com/paperswithbacktest/awesome-systematic-trading) | 4/5 · 高適配 | 7570 |

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

- **2026-04-21**：新增 [外部架構審閱 backlog（8 板塊）](#外部架構審閱-backlog8-板塊2026-04)（G-1～G-8 可勾選項，對齊波次 B／P0–P3、OSS、演進藍圖）；檔首導覽與**未勾選項速覽**增波次 **G**。
- **2026-04-10**：新增 [本輪後續／未完（2026-04-10）](#本輪後續未完2026-04-10)；新增 [OSS 開源生態整合計畫](#oss-開源生態整合計畫oss-integration-roadmap)（Phase 1–4 可勾選細項）；檔首同步日期與錨點；**未勾選項速覽**增波次 **F**。
- **2026-04-09**：**全文重寫**（精簡章節、檔首同步、**LangGraph 路徑** LG-1～3、**Phase 3** 標註部分落地、Pri 8 改為模板／欄位審計表述）；**已落地**補 **2026-04-09** 工具橋接。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-09 Docs**。
- **2026-04-04（晚）**：演進計畫 — Critical env、閾值實驗、`adaptive_gate_thresholds`、Gate digest、dry-run、mock-smoke、scratchpad、`asset_market`、觀望 vs QSREC — CHANGELOG **2026-04-04**。
- **2026-04-04**：四維評分與新建議 backlog — 見上表；[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) 對照。
- **2026-04-03**：OSS Scout 自動區格式 — CHANGELOG **2026-04-03**。
- **2026-04-02**：**勿手改** `OSS_SCOUT_AUTO_BEGIN`～`END`。
- **2026-04-01**：OSS 候選更新 — 研究稿 `docs/oss_candidates/2026-04-01-revision-plan-draft.md`。
- **2026-03-31**：TODOS 精簡、OSS 週報契約 — CHANGELOG **2026-03-31**。
- **2026-03-29**：演進藍圖、OSS 週期 — CHANGELOG **2026-03-29**。
- **2026-03-28**：已完成項遷移 CHANGELOG — 商業化暫緩。
