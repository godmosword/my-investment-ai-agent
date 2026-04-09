# Q-Silicon — 工程與產品待辦（彙總）

**變更紀錄** → [`CHANGELOG.md`](CHANGELOG.md)。**路線願景** → [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)。**執行版路線圖** → [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md)（2026 Q2）。

**同步狀態（2026-04-09）**：本檔僅列 **`[ ]` 未完成** 與維護者排序；**已交付行為**以 CHANGELOG 與下方「已落地（備查）」為準。四維評分表與新建議 backlog 仍適用，見 [未完成項四維評分（2026-04）](#未完成項四維評分與新建議2026-04)。長期里程碑 → [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。演進藍圖（Mock／Plugin／LangGraph 等）→ [演進藍圖](#演進藍圖--技術路線)。

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
| **8** | 模板／QSREC 顯示審計 | 若結構化輸出含 `$` 的 `rr`／`max_drawdown_pct` 等欄位進模板，需與既有 `replace('$','')` 規則一致（見 [`templates/telegram_report.j2`](templates/telegram_report.j2)） |
| **9** | 台股代號顯示 | render 層前綴／格式；[`docs/TW_EQUITY_DISPLAY.md`](docs/TW_EQUITY_DISPLAY.md) |

### LangGraph 路徑（可選引擎）

| Pri | 項目 | 說明 |
|-----|------|------|
| **LG-1** | 生產觀測 | `GRAPH_DEEP_RESEARCH_TOOL_LLM=1` 下成本、延遲、失敗率；是否與 `GRAPH_LLM_DEBATE` 預設組合文件化 |
| **LG-2** | 工具覆蓋 | [`graph/graph_tools.py`](graph/graph_tools.py) 是否擴充 `onchain_metrics_tool` 等（維持工具邊界與 cache 慣例） |
| **LG-3** | 測試 | mock LLM tool_calls 之整合測試（避免 CI 依賴真 API） |

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
| 8 模板審計 | 3 | 2 | 4 | 4 | 顯示一致性 |
| 9 台股顯示 | 2 | 2 | 4 | 3 | 區域化 |

### 波次／Phase 濃縮

| 區塊 | 備註 |
|------|------|
| 自適應門檻 BQ | [`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) 骨架已備 |
| Phase 1 Mock／Plugin | [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md) |
| Phase 2 Execution | 合規與產品表態後 |
| Phase 3 LangGraph | **部分落地**：`graph/`、`USE_LANGGRAPH_ENGINE`、deep research **`RESEARCH_TOOLS`**（CHANGELOG **2026-04-09**）；完整取代 `crew.py` 仍為長期項 |
| Phase 4 Glassbox／RAG | RAG 須錨定當日報告內文 |

### 建議順序

1. Pri **2** + **1** → 2. Pri **8**、**9**（視需求）→ 3. 波次 **C** + Pri **3** → 4. Pri **4** → 5. **5→6**、**7** 與 Phase 2+（依資源）

### 新建議 backlog（骨架已備；持續迭代）

1. Gate 內部儀表 — [`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)、[`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)  
2. 結構化 dry-run — [`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)、[`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)  
3. 美股備援觀測 — `EQUITY_BACKFILL_SCRATCHPAD_LOG`  
4. Prompt 登記 — [`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)  
5. `asset_market` — [`schemas.py`](schemas.py)、[`docs/TW_EQUITY_DISPLAY.md`](docs/TW_EQUITY_DISPLAY.md)  
6. Mock smoke — [`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)  
7. 觀望 vs QSREC — [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)

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

- **2026-04-09**：**全文重寫**（精簡章節、檔首同步、**LangGraph 路徑** LG-1～3、**Phase 3** 標註部分落地、Pri 8 改為模板／欄位審計表述）；**已落地**補 **2026-04-09** 工具橋接。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-09 Docs**。
- **2026-04-04（晚）**：演進計畫 — Critical env、閾值實驗、`adaptive_gate_thresholds`、Gate digest、dry-run、mock-smoke、scratchpad、`asset_market`、觀望 vs QSREC — CHANGELOG **2026-04-04**。
- **2026-04-04**：四維評分與新建議 backlog — 見上表；[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) 對照。
- **2026-04-03**：OSS Scout 自動區格式 — CHANGELOG **2026-04-03**。
- **2026-04-02**：**勿手改** `OSS_SCOUT_AUTO_BEGIN`～`END`。
- **2026-04-01**：OSS 候選更新 — 研究稿 `docs/oss_candidates/2026-04-01-revision-plan-draft.md`。
- **2026-03-31**：TODOS 精簡、OSS 週報契約 — CHANGELOG **2026-03-31**。
- **2026-03-29**：演進藍圖、OSS 週期 — CHANGELOG **2026-03-29**。
- **2026-03-28**：已完成項遷移 CHANGELOG — 商業化暫緩。
