# Q-Silicon — 工程與產品待辦（彙總）

**唯一彙總**：改版請同步 [`CHANGELOG.md`](CHANGELOG.md)；路線願景對照 [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)。  
**同步狀態**（2026-03-27）：已與 `origin/main` 對齊後整理本檔。

---

## 維護者意見（執行順序與取捨）

1. **先穩「選標多樣性 + Gate 可信」再堆功能**：Direction **1A／2A** 與下方「選幣選股過於固定」直接影響使用者對日報的信任；**1B 付費牆**應在 API 契約與視覺化一致後再上，符合 [`ROADMAP_VISION`](docs/ROADMAP_VISION.md)「付費與日報解耦」。
2. **Direction 2B「自動開 PR」**：必須保留 **人類 merge**；現有 [`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py) 與 [`docs/oss_candidates/README.md`](docs/oss_candidates/README.md) 可當 Phase 0，再談 GraphQL／HF Hub 與提案 Agent。
3. **Direction 3**：已有 **Growth 試點** [`crew_company.py`](crew_company.py) + [`company_ops_schemas.py`](company_ops_schemas.py)；擴到四職能前建議先量測 **`CREW_FUTURE_TIMEOUT_SEC`** 與 token，避免管線常態逾時。
4. **P0「全 API hard fail」**：與「缺資料允許 `[DATA_MISSING]`」產品假設衝突；較務實的是 **維持 [`PIPELINE_STRICT_ENV`](main.py) + 金鑰盤點**，僅對 **排程／生產** 強制；其餘 key 維持工具層 N/A。

---

## 橫切：選幣／選股「仍然很固定」— 診斷與改善項

**現狀（機制已部分存在，仍易視覺上「每天同一檔」）**

| 機制 | 檔案／行為 | 為何仍顯固定 |
|------|------------|----------------|
| 近 3 日已推薦標的排除 | [`bigquery_writer.fetch_exclusion_context`](bigquery_writer.py) | LLM 仍可在「重大催化」敘事下 **重複選用**；與 `STRICT_PICK_ROTATION` 的「與昨日 BQ 集合完全相同」條件可能 **不同步**（昨日 vs 近 3 日） |
| 輪動 Gate | [`report_validator`](report_validator.py) `STRICT_PICK_ROTATION`、`ALLOW_REPEAT_PICK_OVERRIDE` | 同標延續若 **分數與 `alt_candidate` 敘事** 過鬆，易合法連莊 |
| 停損反思 | `fetch_exclusion_context` 已注入 **HIT_STOP** 文字 | 只在 **有 BQ 交易紀錄** 時有效；未與 **Quant 任務標題** 強綁定，模型可能略讀 |
| 工具覆蓋 | 研究員工具呼叫 | 若標的池過窄或 prompt 過度錨定 **BTC/ETH/NVDA**，輸出會收斂 |

**建議待辦（可勾選追蹤）**

- [ ] **對齊「排除清單」與 Rotation Gate 語意**：文件化「近 3 日曾出現於 QSREC 的 canonical asset」與「昨日 BQ 集合」差異；必要時 Gate 增 **rolling 5 日內同標出現次數上限**（僅在非 `trade_watch` 時生效，需測試）。
- [ ] **crew prompt**：加密／AI 主研究任務明確要求 **至少 2 個「非昨日主標」的候選比較段落**（不必進正文，可進 scratchpad 再濃縮），降低第一篇草稿就釘死單標。
- [ ] **Quant / 策略任務**：獨立一句 **「若 exclusion 含 HIT_STOP，本段必須回應是否調降該類資產權重」**（呼應已有資料、避免形式化）。
- [ ] **閾值實驗**：在 staging 調高 `PICK_ROTATION_OVERRIDE_MIN_GAP` 或暫緊 `PICK_REPEAT_MIN_SELECTION_SCORE`，觀察 Gate 失敗率與人工滿意度（與 Direction **2A** 自適應門檻合併評估）。
- [ ] **儀表板／PWA**：呈現「本日 QSREC vs 近 7 日出現頻率」小卡（Direction **1A**），讓「固定感」可視化而非只靠文字。

---

## P0 — 防止管線崩潰與資料品質（日報核心）

- [ ] **Critical env 策略定稿**：已具 [`PIPELINE_STRICT_ENV`](main.py)；是否再加「資料源 key 分級 hard fail」需產品決策（見上方意見）。
- [ ] **DATA_MISSING 計數 Gate** — `report_validator.py`：`[DATA_MISSING:...]` 超過門檻時 **blocking**（門檻建議可設 env）。
- [ ] **schema 必填收緊** — `schemas.py`：`bull/base/bear_scenario`、`narrative` 等由 Optional → 必填（保留 validator 截斷兜底）。

---

## P1 — 直接提升日報品質

- [ ] **後處理 band-aid 收斂** — `report_render.py` `_post_process_html_for_gate()`：根因上修到 prompt／validator，目標刪減多數 regex 補丁。
- [ ] **軟 Gate 升級** — `report_validator.py`：審計 warning-only，將情境腿數、執行摘要、工具覆蓋率等 **升格 blocking**（與 `trade_watch` 解耦）。
- [ ] **新聞新鮮度 rollout**：機檢與 [`test_news_freshness.py`](test_news_freshness.py) 已存在；剩 **營運預設** `STRICT_NEWS_FRESHNESS_GATE=1` 與可選 **固定 `report_dt`** 注入管線。
- [ ] **工具呼叫保底** — `crew.py` + Gate：`_check_tool_coverage()`（或同等）核心工具命中不足則 block。

---

## P2 — 自動化與工程債

- [ ] **回測 → 權重** — `backtest.py`：`--update-config` 或寫入 [`signal_weights_store`](signal_weights_store.py)（與 [`scripts/write_ml_weights.py`](scripts/write_ml_weights.py) 對齊）；**週期 workflow** 可選 [`weekly-backtest.yml`](.github/workflows/)（新）。
- [ ] **tools.py 模組化** — 見 [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)（執行拆分）。
- [ ] **Autoresearch／bench** — [`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（已存在者可改為「擴充 METRIC／plateau 儀表」待辦）。

---

## P3 — 長期

- [ ] **Gate 失敗 → 提示注入（人審）** — 分析 `gate_failure_log` 高頻類型，生成「避免模式」草稿；**嚴禁**無審核自動改 prompt。
- [ ] **`_adaptive_threshold()`** — 依 7 日 pass rate 等調整部分 Gate 門檻（依賴穩定 log 與分類）。
- [ ] **kickoff 後 tool-use 強制檢查** — 研究員零 tool call 則 retry（與 scratchpad 對齊）。

---

## Direction 1A — 視覺化（建議 Week 1–2）

| 狀態 | 項目 |
|------|------|
| [ ] | [`visualizer.py`](visualizer.py)：**Panel 4** — BTC 資金費率（funding）趨勢；資料源與 CoinGlass／既有工具對齊，禁止 LLM 手填。 |
| [ ] | [`dashboard.py`](dashboard.py)：**Tab** — Sentiment Score、SOPR、Exchange Netflow（與現有 KPI 區塊對齊 [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)）。 |
| [ ] | [`telegram_sender.py`](telegram_sender.py) + [`templates/telegram_report.j2`](templates/telegram_report.j2)：**「查看歷史」** InlineKeyboard／deep link（需定 URL 或 mini-app）。 |
| [ ] | [`data-verification-ui/`](data-verification-ui/)：**Web Push**（Service Worker）— 日報就緒／重大異動；與 [`api.py`](api.py) 訂閱設計需安全檢視。 |

---

## Direction 1B — 商業化（建議 Week 5–6）

| 狀態 | 項目 |
|------|------|
| [ ] | **Firebase Auth** + FastAPI `Depends`（新模組或 [`api.py`](api.py) 擴充）。 |
| [ ] | **Stripe** Checkout + Webhook；tier：FREE／PRO／INSTITUTIONAL。 |
| [ ] | **API tier**：歷史長度、rate limit；見 [`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)。 |
| [ ] | **多租戶 Telegram**（PRO 自帶 BOT_TOKEN／CHAT_ID，`user_settings` 或同等）。 |
| [ ] | **Landing page**（PWA 或獨立站）+ 方案表 + Checkout 導流。 |

---

## Direction 2A — 績效反饋閉環（建議 Week 3–4）

| 狀態 | 項目 |
|------|------|
| [ ] | **回測自動更新信號權重** — 見 P2；與 **HIT_STOP／勝率** 指標連動更佳。 |
| [ ] | **HIT_STOP → 策略敘事** — `fetch_exclusion_context` **已注入**停損摘要；補 **crew Quant 任務硬性回扣**（見橫切選標節）。 |
| [ ] | **Gate 自適應門檻** — 見 P3 `_adaptive_threshold()`。 |

---

## Direction 2B — OSS Scout Agent（建議 Week 7–8）

| 狀態 | 項目 |
|------|------|
| [x] | **輔助腳本**：[`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)（GitHub Search；`GITHUB_TOKEN` 可選）。 |
| [ ] | **HuggingFace／GraphQL** 擴充、過濾規則（Stars 成長、授權、領域）。 |
| [ ] | **整合提案 Agent**：clone → API 分析 → diff → smoke → **開 PR**（**不自動 merge**）。 |
| [ ] | **`.github/workflows/weekly-scout.yml`**（或手動 + calendar）— 與分鐘額度平衡。 |

---

## Direction 3 — 新創規模 Multi-Agent（建議 Week 9–12）

| 狀態 | 項目 |
|------|------|
| [x] | **試點**：[`crew_company.py`](crew_company.py) + [`company_ops_schemas.py`](company_ops_schemas.py) + `COMPANY_CREW_ENABLED`；Streamlit 公司戰情讀快照。 |
| [ ] | **Product / Growth / Finance / Engineering** 四職能 crew（可對齊 [`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md)）。 |
| [ ] | **Arbiter** 跨部門一致性 + 風險預算匯總。 |
| [ ] | **Company War Room**（PWA 唯讀頁 + 部門狀態）；可選 `main.py --mode=company_daily` 類入口（長期）。 |

---

## 已落地（備查，不再重複開票）

- API schema guard：[`api_schema.py`](api_schema.py)、[`test_api_schema.py`](test_api_schema.py)。
- 盤中監控：[`monitor_intraday.py`](monitor_intraday.py)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)（輕量依賴 [`requirements-monitor.txt`](requirements-monitor.txt)、降頻與磁碟優化）。
- LLM run log → BQ：[`bigquery_writer.write_llm_run_log`](bigquery_writer.py)、[`main.py`](main.py)。
- **Gate 失敗結構化 log**：`write_gate_failure_log`、`GATE_FAILURE_BQ_LOG`、[`test_gate_failure_log.py`](test_gate_failure_log.py)；範例 SQL [`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。
- 新聞新鮮度機檢 + 白名單 ISO 日期修正：[`report_validator.py`](report_validator.py)、[`test_news_freshness.py`](test_news_freshness.py)。
- 啟動硬擋：`PIPELINE_STRICT_ENV`、[`_validate_critical_env_strict`](main.py)、`NEWS_FRESHNESS_WINDOW_HOURS` 型別校驗。
- 權重版本化與 context：[`signal_weights_store.py`](signal_weights_store.py)、[`scripts/write_ml_weights.py`](scripts/write_ml_weights.py)、`WEIGHTS_CONTEXT_ENABLED`。
- Exclusion context：**近 3 日標的** + **HIT_STOP** + rotation 警示 + 權重摘要：[`fetch_exclusion_context`](bigquery_writer.py)。
- Q-Score／Editor／Gemini 切換、narrative validator 等：見 [`CHANGELOG.md`](CHANGELOG.md) 近期條目。
- 文件：[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)。

---

## 修訂紀錄

- **2026-03-27**：`git pull` 後合併使用者「三大戰略方向＋週次」、新增 **維護者意見**、**選幣／選股固定問題** 橫切節；校正與現況不符項（Gate log、HIT_STOP 注入、scout 腳本、已落地列表）。
