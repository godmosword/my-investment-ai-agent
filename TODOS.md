# Q-Silicon — 工程與產品待辦（彙總）

**唯一彙總**：改版請同步 [`CHANGELOG.md`](CHANGELOG.md)；路線願景對照 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)。  
**同步狀態**（2026-03-31）：**已完成項**已自下方章節移除，細節以 [`CHANGELOG.md`](CHANGELOG.md)（2026-03-28～**31**）與「**已落地（備查）**」為準；本檔僅保留 **未勾選 `[ ]`** 與索引。長期項見 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)。**演進藍圖（Mock／Plugin／執行層／LangGraph 等）**見 [演進藍圖 — 技術路線](#roadmap-technical-saas-execution-brain)。

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

- [ ] **Mock-Driven Development** — `MOCK_APIS`、`api.py`／`tools.py` 短路、[`tests/fixtures/mock_data/`](tests/fixtures/mock_data/)。
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

> 每週搜尋 GitHub 熱門／指定 topic 之 repo，拉取 README 與 **啟發式適配度**；**是否實作由維護者勾選**。詳稿見 `docs/oss_candidates/YYYY-MM-DD-revision-plan-draft.md`。

<!-- OSS_SCOUT_AUTO_BEGIN -->



<!-- OSS_SCOUT_AUTO_END -->

---

## 修訂紀錄

- **2026-03-31**：**TODOS 精簡** — 移除已完成 `[x]` 主表（細節改以 CHANGELOG／「已落地」為準）；補 **OSS Scout 週報** `OSS_SCOUT_AUTO_BEGIN/END` 與 [`oss_weekly_pipeline.py`](scripts/oss_weekly_pipeline.py) 契約對齊。**同日對齊 CHANGELOG 2026-03-31**：已落地條目補績效註解／risk_budget coerce／連日維持補註等；檔首與波次 B 日期區間更新為～31。
- **2026-03-29**：**演進藍圖** — Phase 1–4；精簡版寫入 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md#roadmap-evolution-condensed)、[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md#roadmap-phases-1-4-condensed)。
- **2026-03-29**：**OSS Scout 週期**：`oss_weekly_pipeline.py`、`weekly-scout.yml`。
- **2026-03-28**：**已完成項 → CHANGELOG**；商業化暫緩；Priority／fixtures／波次表。
