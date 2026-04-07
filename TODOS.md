# Q-Silicon — 工程與產品待辦（彙總）

**唯一彙總**：改版請同步 [`CHANGELOG.md`](CHANGELOG.md)；路線願景對照 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)。  
**執行版路線圖**：見 [`docs/REPO_CONTINUATION_EXECUTION.md`](docs/REPO_CONTINUATION_EXECUTION.md)（2026 Q2）。
**同步狀態**（2026-04-07）：**已完成項**已自下方章節移除，細節以 [`CHANGELOG.md`](CHANGELOG.md)（2026-03-28～31、**2026-03-29**、**2026-04-01**～**03**）與「**已落地（備查）**」為準；本檔僅保留 **未勾選 `[ ]`** 與索引。未完成項之**四維評分與新建議**見 [未完成項四維評分與新建議（2026-04）](#未完成項四維評分與新建議2026-04)。長期項見 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。**演進藍圖（Mock／Plugin／執行層／LangGraph 等）**見 [演進藍圖 — 技術路線](#roadmap-technical-saas-execution-brain)。

---

## 維護者意見（執行順序與取捨）

1. **先穩「選標多樣性 + Gate 可信」再堆功能**：Direction **1A／2A** 與「選幣選股過於固定」直接影響信任。**1B 商業化暫緩** → 階段 E；對齊 [`ROADMAP_VISION`](docs/ROADMAP_VISION.md)。
2. **Direction 2B**：[`oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 寫入 `docs/oss_candidates/` 並合併勾選項至下方 **OSS Scout 週報（自動）**（不自動 merge 程式）。排程見 [`.github/workflows/weekly-scout.yml`](.github/workflows/weekly-scout.yml)。
3. **Direction 3**：試點 [`crew_company.py`](crew_company.py)；擴四職能前先量測 **`CREW_FUTURE_TIMEOUT_SEC`** 與 token。
4. **P0「全 API hard fail」**：與 `[DATA_MISSING]` 假設衝突；務實做法：**[`PIPELINE_STRICT_ENV`](main.py)** + 金鑰盤點，僅排程／生產強制。

---

## 未勾選項總覽與建議執行波次

以下為仍為 `[ ]` 的項目（不含 **OSS Scout 週報** 自動表，由 workflow 維護）。

| 波次 | 建議時機 | 項目（對照下方章節） |
|------|----------|----------------------|
| **A — 營運／產品決策** | 先開 1–2 週實驗 | **閾值實驗** [`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md)；**Critical env** [`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) |
| **B — 日報契約與品質** | 與 A 並行 | 契約與後處理已落地（CHANGELOG **2026-03-28**～**31**）；持續收斂見「已落地」 |
| **C — 觀測與自適應** | 需穩定 `gate_failure_log` | **Gate 提示人審** [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)；自適應 BQ 接線 [`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py) |
| **D — OSS 深化** | 人力可負荷 | **2B** HuggingFace／GraphQL、**整合提案 Agent** |
| **E — Company／前端** | 長期 | **3** 四職能、Arbiter、War Room；**1A** PWA Web Push 持久化 |

### Priority 排序（僅未完成）

| Pri | 項目 | 類型 | 說明 |
|-----|------|------|------|
| **1** | 橫切 **閾值實驗** | 營運 | [`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md) |
| **2** | P0 **Critical env 策略定稿** | 產品＋工程 | [`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md) |
| **3** | P3 **Gate 失敗 → 提示（人審）** | 營運＋工程 | [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md) |
| **4** | 1A **PWA Web Push 持久化** | 前端 | 不阻塞日報主線 |
| **5** | 2B **HuggingFace／GraphQL** | 工程 | 人力可負荷時 |
| **6** | 2B **整合提案 Agent** | 工程 | 建議在 (5) 之後 |
| **7** | Direction **3**（四職能、Arbiter、War Room） | 長期 | [`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md) |
| **8** | Jinja **trade leg `$` 審計** | 工程 | `position_pct`、`rr`、`max_drawdown_pct` 等尚未 `replace('$', '')`；見 [`templates/telegram_report.j2`](templates/telegram_report.j2) |
| **9** | Template **台股代號 `$` 前綴** | 工程 | render 層 `_format_asset_display`；見 [`templates/telegram_report.j2`](templates/telegram_report.j2) |
| *—* | *1B 商業化* | *長期* | *階段 E* |

<a id="未完成項四維評分與新建議2026-04"></a>

## 未完成項四維評分與新建議（2026-04）

> 下列為未完成項之**決策用評分**（非程式 Gate）。維度皆為 **1–5**；**成本**越高數字越大。綜合：**高影響、低成本、高信任、高策略契合**者優先；商業化與執行屬高成本、策略暫緩則排後。策略契合指與本檔 [維護者意見](#維護者意見執行順序與取捨)、[`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)（先穩選標＋Gate）之對齊。**信任／紅線**指與無數據幻覺、`validate_report`、`main.py` 雙線程安全、Telegram HTML 白名單之一致性（5＝強化紅線）。

### Priority 表（Pri 1–9）四維評分

| 項目 | 影響力 | 成本 | 信任／紅線 | 策略契合 | 簡評 |
|------|:------:|:----:|:----------:|:--------:|------|
| **1 閾值實驗** | 4 | 2 | 4 | 5 | 低成本驗證選標是否仍過於固定；與維護者排序一致。 |
| **2 Critical env 定稿** | 4 | 2 | 5 | 5 | 生產穩定性與金鑰契約；文件＋環境矩陣可落地。 |
| **3 Gate 失敗人審提示** | 4 | 3 | 5 | 4 | 閉合 `gate_failure_log`→人行為；嚴禁無審核自動改 prompt。 |
| **4 PWA Web Push 持久化** | 2 | 3 | 4 | 3 | 體驗加分，不阻塞日報主線。 |
| **5 HF／GraphQL 擴充** | 3 | 4 | 3 | 3 | 擴資料覆蓋但易引入非工具數字風險，須嚴格掛工具／mock。 |
| **6 整合提案 Agent** | 3 | 5 | 3 | 2 | 自動開 PR 之安全與 review 負載大；宜在 (5) 與 Scout 流程穩定後。 |
| **7 Direction 3 四職能＋War Room** | 3 | 5 | 3 | 2 | token／timeout 風險大；擴四職能前先量測 `CREW_FUTURE_TIMEOUT_SEC`。 |
| **8 Jinja trade leg `$` 審計** | 3 | 2 | 4 | 4 | 小工程債；[`templates/telegram_report.j2`](templates/telegram_report.j2) 顯示一致性。 |
| **9 台股 `$` 前綴** | 2 | 2 | 4 | 3 | 區域化顯示；若無台股標的可降優先。 |

### 波次與演進區塊（濃縮評分）

| 區塊 | 影響力 | 成本 | 信任／紅線 | 策略契合 | 備註 |
|------|:------:|:----:|:----------:|:--------:|------|
| **C 自適應門檻 BQ 接線**（[`adaptive_gate_thresholds.py`](adaptive_gate_thresholds.py)） | 4 | 3 | 4 | 4 | 骨架已落地；接上穩定 `gate_failure_log` 後 ROI 高。 |
| **階段 E 商業化（整包）** | 變現 5 | 5 | 2 | 1 | 本檔暫緩；與「先信任後變現」衝突時讓路。 |
| **Phase 1 Mock／Plugin／Compose** | 4 | 4 | 4 | 4 | 與 [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md)、[`TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md) 一致。 |
| **Phase 2 Execution／Monitor V2** | 3 | 5 | 2 | 2 | 執行層涉合規與實盤風險；須產品表態與「研究日報」定位。 |
| **Phase 3 LangGraph／Debate** | 3 | 5 | 3 | 2 | 保留 [`crew.py`](crew.py) 退路與工具邊界。 |
| **Phase 4 Glassbox／RAG／語音** | 2–3 | 4–5 | 3 | 2 | RAG 若未嚴格錨定當日報告內文易牴觸無幻覺原則。 |
| **OSS 週報 spike 勾選（15 repo）** | 2 | 4 | 4 | 3 | 人力決策清單；逐項評估即可。 |

### 建議實作順序（與上表一致）

1. Pri **2**＋**1**（Critical env 定稿與 staging 閾值實驗並行）  
2. Pri **8**（短衝刺）  
3. 波次 **C**（自適應 BQ 接線）＋ Pri **3**（Gate 人審提示；觀測閉環）  
4. Pri **4**、**9**（視是否要 Push／台股）  
5. **5→6**、**7**、**Phase 2+**（資源與產品決策明確後）

### 新建議 backlog（七項已落地骨架；細節持續迭代）

1. **Gate 儀表板（內部）**：指引 [`docs/GATE_INTERNAL_DASHBOARD.md`](docs/GATE_INTERNAL_DASHBOARD.md)；CLI 草稿 [`scripts/gate_failure_hint_digest.py`](scripts/gate_failure_hint_digest.py)。  
2. **結構化預檢 dry-run**：[`scripts/validate_report_dry_run.py`](scripts/validate_report_dry_run.py)＋骨架 [`scripts/report_skeleton_validate.py`](scripts/report_skeleton_validate.py)；smoke [`test_validate_report_dry_run_smoke.py`](test_validate_report_dry_run_smoke.py)。  
3. **美股價位備援可觀測性**：[`report_render.py`](report_render.py) 觸發備援時寫 scratchpad `equity_price_backfill`（`EQUITY_BACKFILL_SCRATCHPAD_LOG`）。  
4. **Prompt 變更登記簿**：[`docs/PROMPT_CHANGELOG.md`](docs/PROMPT_CHANGELOG.md)。  
5. **資產市場枚舉**：[`schemas.py`](schemas.py) `ExecutableTradeLeg.asset_market`／`TradeRecommendation.asset_market`；模板行為見 [`docs/TW_EQUITY_DISPLAY.md`](docs/TW_EQUITY_DISPLAY.md)。  
6. **Contributor mock-smoke**：[`scripts/run_mock_smoke.sh`](scripts/run_mock_smoke.sh)。  
7. **觀望 vs QSREC**：[`schemas.py`](schemas.py) `AISection._warn_watch_mode_vs_equity_qsrec`（warning）；測試 [`test_aisection_watch_warning.py`](test_aisection_watch_warning.py)。

---

## 橫切：選幣／選股「仍然很固定」— 診斷與改善項

**機制摘要**（仍適用）：[`fetch_exclusion_context`](bigquery_writer.py)、[`report_html_gates`](report_html_gates.py) `STRICT_PICK_ROTATION`、HIT_STOP 注入、研究員工具覆蓋 — 已完成項見「已落地」。

**待辦**

- [ ] **閾值實驗**：staging 調高 `PICK_ROTATION_OVERRIDE_MIN_GAP` 或暫緊 `PICK_REPEAT_MIN_SELECTION_SCORE`（[`docs/STAGING_THRESHOLD_EXPERIMENT.md`](docs/STAGING_THRESHOLD_EXPERIMENT.md)）。

---

## P0 — 防止管線崩潰與資料品質

- [ ] **Critical env 策略定稿**：[`PIPELINE_STRICT_ENV`](main.py)；[`docs/CRITICAL_ENV_POLICY.md`](docs/CRITICAL_ENV_POLICY.md)。

---

## P1 — 日報品質（已落地細節 → CHANGELOG）

（後處理 band-aid、軟 Gate、新聞錨定日、工具呼叫下限等 — **2026-03-28** CHANGELOG 與「已落地」。）

---

## P2 — 自動化與工程債（已落地細節 → CHANGELOG）

（回測權重、`tools_cache_http`、bench、離線 fixtures — **2026-03-28** CHANGELOG 與「已落地」。）

---

## P3 — 長期

- [ ] **Gate 失敗 → 提示注入（人審）** — [`docs/GATE_FAILURE_HINT_WORKFLOW.md`](docs/GATE_FAILURE_HINT_WORKFLOW.md)；**嚴禁**無審核自動改 prompt。

（自適應門檻骨架、`MIN_TOOL_CALLS_PER_CREW` — 已落地，見「已落地」。）

---

## Direction 1A — 視覺化

**已落地**：Panel 4 funding、Dashboard 鏈上 Tab、Telegram 歷史連結、API Web Push 預留 — 見「已落地」與 CHANGELOG。

**未完成**

- [ ] **PWA Web Push 持久化**（Service Worker 等）。

---

## Direction 1B — 商業化（暫緩）

見 **階段 E — 商業化**。

---

## Direction 2A — 績效反饋閉環

**已落地**：回測權重 workflow、HIT_STOP 敘事、自適應門檻骨架 — 見「已落地」與 CHANGELOG。

---

## Direction 2B — OSS Scout Agent

| 狀態 | 項目 |
|------|------|
| [ ] | **HuggingFace／GraphQL** 擴充、過濾規則。 |
| [ ] | **整合提案 Agent**：clone → 分析 → diff → smoke → 開 PR（不自動 merge）。 |

**已落地**：[`oss_scout_candidates.py`](scripts/oss_scout_candidates.py)、[`weekly-scout.yml`](.github/workflows/weekly-scout.yml)、[`oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 合併週報至本檔 — 見「已落地」。

---

## Direction 3 — Multi-Agent（新創規模）

| 狀態 | 項目 |
|------|------|
| [ ] | **Product / Growth / Finance / Engineering** 四職能 crew。 |
| [ ] | **Arbiter** 跨部門一致性 + 風險預算。 |
| [ ] | **Company War Room**（PWA 唯讀）；可選 `main.py` 入口。 |

**已落地**：`COMPANY_CREW_ENABLED` 試點 — 見「已落地」。

---

## 已落地（備查，不再重複開票）

**2026-03-31**：自本檔主體移除之 `[x]` 項目（rotation 語意／crew 多樣性／HIT_STOP／儀表板、P0 DATA_MISSING+schema、P1 後處理／Gate／錨定日／工具下限、P2 回測／cache_http／bench／fixtures、P3 adaptive 骨架／per-crew tool 下限、Direction 1A 表列、2A 表列、2B 腳本+workflow、3 試點）— **詳見 [`CHANGELOG.md`](CHANGELOG.md) 2026-03-28～31** 與下列連結。

- API schema guard：[`api_schema.py`](api_schema.py)、[`test_api_schema.py`](test_api_schema.py)。
- 盤中監控：[`monitor_intraday.py`](monitor_intraday.py)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)（[`requirements-monitor.txt`](requirements-monitor.txt)；cron 預設關閉）。
- LLM run log → BQ：[`bigquery_writer.write_llm_run_log`](bigquery_writer.py)、[`main.py`](main.py)。
- **Gate 失敗結構化 log**：`write_gate_failure_log`、`GATE_FAILURE_BQ_LOG`、[`test_gate_failure_log.py`](test_gate_failure_log.py)；SQL [`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。
- 新聞新鮮度：[`report_html_gates.py`](report_html_gates.py)、[`test_news_freshness.py`](test_news_freshness.py)。
- 啟動硬擋：`PIPELINE_STRICT_ENV`、[`_validate_critical_env_strict`](main.py)。
- 權重：[`signal_weights_store.py`](signal_weights_store.py)、[`scripts/write_ml_weights.py`](scripts/write_ml_weights.py)、`WEIGHTS_CONTEXT_ENABLED`。
- Exclusion：[`fetch_exclusion_context`](bigquery_writer.py)（近 3 日、HIT_STOP、rotation、權重摘要）。
- **錨定報告日**、Telegram 歷史、Web Push 預留、tools 快取拆分、離線 Gate fixtures、後處理 band-aid — `ENV_TEMPLATE.txt`、CHANGELOG **2026-03-28**。
- **日報品質（2026-03-30）**：同標補註（初版「重複選用理由」）、tracker 進場價過濾、資金費率近零、crew／模板 — CHANGELOG **2026-03-30**。
- **日報品質（2026-03-31）**：`crypto.risk_budget_summary` 缺 regime token 時 assemble 補 canonical；近 30 天績效週報附指標／回撤說明與 regime 小樣本註記；同標補註改 **「連日維持…」** 避免雙重抬頭；crew 補 NVT vs RSI、呢喃欄位順序；[`test_tracker.py`](test_tracker.py) 績效摘要 mock — CHANGELOG **2026-03-31**。
- **日報品質（2026-04-01）**：`pick_reason` 若以「重複選用／選股／持有理由：」開頭則 assemble 改寫或剥除（對齊昨日 BQ QSREC）；呢喃自動補可信度改 **「｜可信度：…｜主流媒體二次驗證：否」** — CHANGELOG **2026-04-01**。
- 文件：[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)。

---

## 階段 E — 長期里程碑（啟動索引）

與商業／人力綁定，非本 sprint 必交；[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。

### 階段 E — 商業化（長期／暫緩）

| 狀態 | 項目 |
|------|------|
| [ ] | **Firebase Auth** + FastAPI `Depends`。 |
| [ ] | **Stripe** Checkout + Webhook。 |
| [ ] | **API tier**、rate limit；[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)。 |
| [ ] | **多租戶 Telegram**。 |
| [ ] | **Landing page** + Checkout 導流。 |

---

<a id="roadmap-technical-saas-execution-brain"></a>

## 演進藍圖 — 技術路線（開源 SaaS × 執行層 × 次世代大腦）

由「日報管線」邁向「開源 SaaS」與「交易大腦」。時程僅供參考；衝突時以 [**維護者意見**](#維護者意見執行順序與取捨) 與 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md) 為準。精簡版：[ROADMAP_VISION](docs/ROADMAP_VISION.md#roadmap-evolution-condensed)、[PHASE_F_BACKLOG](docs/PHASE_F_BACKLOG.md#roadmap-phases-1-4-condensed)。

### Phase 1：開源生態與容錯基礎設施（0–1 個月）

- [ ] **Mock-Driven Development** — **部分**：`MOCK_APIS`、`tools/base`、`market_fixture_dict`、[`tests/fixtures/mock_data/`](tests/fixtures/mock_data/) 已接線；`tools` 套件 re-export [`tools_legacy`](tools_legacy.py)；`api.py` 短路與各 `@tool` mock 分支仍待擴充 — [`docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md`](docs/ADR_OFFICE_HOURS_TOOLS_PLATFORM.md)。
- [ ] **Tool Plugin System** — [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、`plugins/`。
- [ ] **Docker Compose 全端** — [`docker-compose.yml`](docker-compose.yml)、FastAPI + Vite + Redis。

### Phase 2：跨越「訊號」到「執行」（1–3 個月）

- [ ] **Execution Layer** — `execution_engine.py`、CCXT／Alpaca／IB、BQ → TWAP／VWAP。
- [ ] **Intraday Monitor V2** — WebSocket、觸價 Telegram（HTML 白名單）。

### Phase 3：次世代大腦（3–6 個月）

- [ ] **LangGraph 等** — 重構 [`crew.py`](crew.py)；保留 `CREW_DISABLE_ASYNC_RESEARCH` 退路。
- [ ] **Multi-Agent Debate** — Bull／Bear、多輪、收斂至主編。

### Phase 4：觀測儀表與 IP（6 個月以上）

- [ ] **Glassbox 圖表** — lightweight-charts、Entry／Target／Stop。
- [ ] **RAG「Chat with the Report」**。
- [ ] **語音晨報** — TTS、Telegram 語音推播。

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

- **2026-04-04（晚）**：演進計畫實作 — Critical env／閾值實驗文件定稿；`adaptive_gate_thresholds` BQ 接線；Gate digest／dry-run／mock-smoke／scratchpad 備援觀測；`asset_market`、觀望 vs QSREC warning；PWA／台股說明文件。見 [`CHANGELOG.md`](CHANGELOG.md) **2026-04-04 Added**。
- **2026-04-04**：新增 **[未完成項四維評分與新建議（2026-04）](#未完成項四維評分與新建議2026-04)**（Pri 1–9、波次／Phase 濃縮表、建議順序、七條新建議 backlog）；檔首索引連結；[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md) 補對照段落。
- **2026-04-03**：**OSS Scout 自動區**改為連結＋表＋短勾選（`fit_rationale` 只在研究稿／JSON）；研究稿模板補「維護者勾選追蹤」— CHANGELOG **2026-04-03**。
- **2026-04-02**：檔首同步含 CHANGELOG **2026-04-02**（CI `workflow_dispatch`、`market.json` fixture、tools 套件鏡射）；**勿手改** `<!-- OSS_SCOUT_AUTO_BEGIN -->`～`END` 區塊（由 workflow 覆寫）。
- **2026-04-01**：已落地補 **pick_reason 重複抬頭正規化**、呢喃補填讀者面；**OSS Scout 週報** 更新候選＋研究稿 [`docs/oss_candidates/2026-04-01-revision-plan-draft.md`](docs/oss_candidates/2026-04-01-revision-plan-draft.md)；檔首同步含 CHANGELOG **2026-04-01**。
- **2026-03-31**：**TODOS 精簡** — 移除已完成 `[x]` 主表（細節改以 CHANGELOG／「已落地」為準）；補 **OSS Scout 週報** `OSS_SCOUT_AUTO_BEGIN/END` 與 [`oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 契約對齊。**同日對齊 CHANGELOG 2026-03-31**：已落地條目補績效註解／risk_budget coerce／連日維持補註等；檔首與波次 B 日期區間更新為～31。
- **2026-03-29**：**演進藍圖**（Phase 1–4；精簡版 → [`ROADMAP_VISION`](docs/ROADMAP_VISION.md#roadmap-evolution-condensed)、[`PHASE_F_BACKLOG`](docs/PHASE_F_BACKLOG.md#roadmap-phases-1-4-condensed)）＋ **OSS Scout 週期**（`oss_weekly_pipeline.py`、`weekly-scout.yml`）。
- **2026-03-28**：**已完成項 → CHANGELOG**；商業化暫緩；Priority／fixtures／波次表。
