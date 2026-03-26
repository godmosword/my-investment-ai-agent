# Project TODOs

---

## 🚀 三大戰略方向（2026-03-26 新增）

> 執行時間軸：1A → 2A → 1B → 2B → Direction 3

### Direction 1A — 穩定視覺化輸出（Week 1–2）

- [ ] `visualizer.py` — 新增 Panel 4：BTC 資金費率（fundingRate）趨勢折線圖（CoinGlass API 已有）
- [ ] `dashboard.py` — 新增 Streamlit Tab 5：Sentiment Score；Tab 6：SOPR + Exchange Netflow 雙軸圖
- [ ] `telegram_sender.py` + `templates/telegram_report.j2` — 報告底部加「查看歷史」Inline Keyboard Button（`reply_markup`）
- [ ] `data-verification-ui/src/` — ServiceWorker Web Push 通知（BTC 異動 / 日報到達）

### Direction 1B — 商業化地基（Week 5–6）

- [ ] `auth.py` (新) — Firebase Auth JWT middleware（FastAPI `Depends`）
- [ ] `billing.py` (新) — Stripe Checkout + Webhook；FREE / PRO / INSTITUTIONAL 三級
- [ ] `api.py` — 依 tier 限制資料範圍：FREE=7天、PRO=全部、INSTITUTIONAL=直連 API key
- [ ] `telegram_sender.py` — PRO 用戶帶自己的 BOT_TOKEN + CHAT_ID（從 BQ `user_settings` 表讀取）
- [ ] `data-verification-ui/src/pages/Landing.jsx` (新) — Landing page：Hero + 方案比較表 + Stripe Checkout

### Direction 2A — 績效反饋閉環（Week 3–4）

- [ ] `backtest.py` — 新增 `--update-config` flag：回測後自動把最佳信號權重寫入 `config.py` `SIGNAL_WEIGHTS`
- [ ] `.github/workflows/weekly-backtest.yml` (新) — 週一 02:00 HKT 觸發 `python backtest.py --update-config`
- [ ] `crew.py` — Quant Strategist prompt 注入「過去 3 天 HIT_STOP 反饋」（`bigquery_writer._fetch_recent_stopped_out_trades` 已實作）
- [ ] `report_validator.py` — `_adaptive_threshold()`：若最近 7 天 Gate pass rate > 80% 自動提高情境字數門檻

### Direction 2B — OSS 自主整合 Scout Agent（Week 7–8）

- [ ] `agents/scout_agent.py` (新) — GitHub GraphQL + HuggingFace Hub 搜尋；過濾：Stars ↑500/月、MIT/Apache、Python、領域=crypto-analytics/LLM-finance
- [ ] `agents/integration_proposal_agent.py` (新) — clone → 分析 API → 生成整合 diff → 跑 smoke test → 自動開 PR（**不自動合併**）
- [ ] `.github/workflows/weekly-scout.yml` (新) — 週五 18:00 HKT 觸發

### Direction 3 — Multi-Agent 新創規模（Week 9–12）

- [ ] `agents/product_crew.py` (新) — PM Agent + UX Researcher Agent（每週功能優先排序 + 用戶痛點）
- [ ] `agents/growth_crew.py` (新) — Marketing Agent + Competitor Intel Agent（每週競品 + GTM 草稿）
- [ ] `agents/finance_crew.py` (新) — CFO Agent + Cost Optimizer Agent（每日 API 成本 + 月度 P&L 預測）
- [ ] `agents/engineering_crew.py` (新) — Tech Radar Agent + Code Review Agent（依賴更新建議 + Dependabot-style PR）
- [ ] `agents/arbiter_crew.py` (新) — 接收所有 Crew 輸出，產出全局風險預算 + 跨部門一致性檢查
- [ ] `company_report_render.py` (新) — 合併所有 Crew 輸出，渲染「新創公司日報」
- [ ] `main.py` — 新增 `--mode=company_daily` 支援 6 Crew 並行
- [ ] `data-verification-ui/` — Company War Room 頁面（各部門狀態 + 公司日報）

---


## 優先順序速覽（重估）

| 順序 | 項目 | 重要性 | 可行性 | 說明 |
|------|------|--------|--------|------|
| 1 | 啟動期 critical env | 高（維運／節省長跑成本） | 高 | 建議下一波主力 |
| 2 | 新聞新鮮度 | 高（敘事正確性） | 主體已完成 | 剩上線策略、測試、文件 |
| 3 | `tools.py` 分割 | 中（長期維護） | 中高、工時大 | 獨立 refactor PR 較佳 |
| 4 | Gate 失敗自動學習 | 中長期 | 低～中 | 遠期；可先只做 BQ log |

---

## TODO: 新聞新鮮度 Gate — 上線策略與測試（主體已實作）

- **Status（已落地邏輯）：** [`report_validator.py`](report_validator.py) 已內建 `_check_news_freshness`、`_extract_news_timestamps`，並接入 `validate_report`。預設**關閉**；`STRICT_NEWS_FRESHNESS_GATE=1` 啟用。視窗預設 48h，可由 `NEWS_FRESHNESS_WINDOW_HOURS` 覆寫；來源白名單 `NEWS_FRESHNESS_SOURCE_WHITELIST`（逗號分隔，例如 `FRED,IMF`）。
- **Why（仍列待辦）：** 貿然預設開啟易拉高誤擋率；需與產品約定「報告時間基準」（生成時刻 vs 推送時刻，目前未傳 `report_dt` 時以當下時間為準）及哪些來源必須白名單。
- **Remaining:** 補齊測試（新鮮／過舊／無可解析時間戳／跨日邊界／白名單命中）；在 README、`ENV_TEMPLATE.txt` 與營運 runbook 寫清預設與 rollout；視需要把 `report_dt` 從管線傳入以對齊「報告時間基準」。

---

## TODO: 啟動期 critical env 完整驗證（fail-fast）— **建議下一波**

- **What:** 擴充 `_validate_required_keys()`（或新增 `_validate_critical_env()`），依執行路徑檢查：Telegram 推送所需 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`（若未 `SKIP_TELEGRAM`）、BigQuery 寫入所需 `GCP_SA_KEY` 或 `GOOGLE_APPLICATION_CREDENTIALS` / `PROJECT_ID`、以及管線實際會呼叫的 data API（見 `_log_api_key_inventory`「建議/備援」群組）。
- **Why:** 目前僅在啟動時驗證少數 LLM + Apify，其餘在執行中才失敗，浪費長跑管線時間且 log 分散。
- **Pros:** 早失敗、部署/排程可預期、減少「跑到一半才發現缺 key」的支援成本。
- **Cons:** 需釐清「可選功能」與「強制」邊界（例如 `SKIP_BIGQUERY`、`SKIP_TELEGRAM`）；過嚴會阻擋本機僅跑部分流程。
- **Context:** 入口在 [`main.py`](main.py) 的 `_validate_required_keys()` 與 `_log_api_key_inventory()`；Telegram/BQ 目前多為 **warning**，擴充時建議用既有 `SKIP_*` 做條件式必填表，並與 README / `ENV_TEMPLATE.txt` 對齊。
- **Depends on / blocked by:** 盤點 `main.py` 與 `tools.py` 在預設 prod 路徑下哪些 API 缺 key 會讓產出不可接受；訂「警告 vs 硬擋」矩陣。

---

## TODO: tools.py God-file 分割（P1 — 維護性）

- **What:** 將 `tools.py` 按資料來源類型分裝成多個模組（crypto / macro / equities / search / quant），`tools.py` 保留 backward-compat re-export 層。
- **Why:** 單檔過大（約 4k 行）時 review diff 不精準、維護成本高。
- **Pros:** 模組邊界清晰、diff 更小、可並行開發。
- **Cons:** 機械搬移工作量大；需避免循環 import、保持 re-export 以免 import 爆炸。
- **Effort:** L | **Priority:** P1（對當日報告品質無直接加分，適合專門 refactor sprint）

---

## TODO: Gate 失敗自動學習（P3 — 遠期）

- **What:** 每次 `validate_report` 失敗，將失敗原因分類寫入 BigQuery；週期性腳本分析高頻失敗類型，生成「請避免這些模式」提示詞段落供 crew 附加。
- **Why:** 降低長期 Gate 失敗率與人工維護成本。
- **Cons:** 需防 prompt injection；自動生成段落需人工審核機制。
- **Effort:** L | **Priority:** P3
- **Depends on / blocked by:** `gate_failure_log` BQ 表設計 + 防注入規格；建議 env fail-fast / tools 模組化穩定後再設計。**縮小第一步：** 僅寫結構化失敗 log 至 BQ，不自動改 prompt。

---

## 已落地（自 TODOS 移除細項，僅存檔備查）

- **統一 API schema guard：** [`api_schema.py`](api_schema.py)（`require_json_dict`、`require_list`、`log_schema_mismatch`）與 [`test_api_schema.py`](test_api_schema.py)。
- **盤中異常推送：** [`monitor_intraday.py`](monitor_intraday.py)、[`.github/workflows/monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)。
- **LLM run log → BigQuery：** [`bigquery_writer.py`](bigquery_writer.py) 內 `write_llm_run_log`、[`main.py`](main.py) 呼叫與 [`test_llm_run_log.py`](test_llm_run_log.py)。
- **新聞新鮮度 Gate（機檢邏輯）：** [`report_validator.py`](report_validator.py) 內 `_check_news_freshness` 等；預設關閉，見上方「剩餘：上線與測試」。
