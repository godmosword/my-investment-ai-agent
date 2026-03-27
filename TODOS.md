# Project TODOs

---

## 🔥 日報實戰等級升級（2026-03-27 更新）

> 執行優先級：P0（防崩潰）→ P1（品質提升）→ P2（自動化）→ P3（長期）
> 探索發現 10 類結構性弱點，按「對日報品質的直接影響」排序。

### P0 — 防止管線崩潰與資料缺失（立即）

- [ ] **env fail-fast 擴充** — `main.py`（`_validate_required_keys()`）：依 `SKIP_*` 條件式，擴充至 13+ API key 檢查（CoinGlass、CryptoPanic、FRED、Telegram、BQ SA key 等）。啟動時缺 key 即 hard fail。
- [ ] **DATA_MISSING 計數 Gate** — `report_validator.py`、`validation_rules.py`：新增 `_check_data_missing_count()`，`[DATA_MISSING:...]` 超過 3 次直接 block（目前是 warning-only）。
- [ ] **schema 必填欄位收緊** — `schemas.py`：`bull_scenario`、`base_scenario`、`bear_scenario`、`narrative` 從 `Optional` 改為必填。已有 `@field_validator` auto-truncation 兜底。

### P1 — 直接提升日報品質（本 Sprint）

- [ ] **移除 post-processing band-aids** — `report_render.py`（`_post_process_html_for_gate()`）：分析 7 個 regex 補丁的根因，修復移到 agent prompt / schema validator，刪除至少 5/7 個。
- [ ] **軟 Gate 升級為硬 Gate** — `report_validator.py`：審計 ~20 個 warning-only 條件，升級：(a) 情境分析腿數不足、(b) 執行摘要缺失、(c) 工具覆蓋率 < 3/5 為 blocking。
- [ ] **新聞新鮮度 Gate 補測試 + 預設開啟** — `report_validator.py`、新增 `test_news_freshness.py`：補齊 5 場景測試（新鮮/過舊/無時間戳/跨日/白名單），穩定後 `STRICT_NEWS_FRESHNESS_GATE` 預設改 `1`。
- [ ] **工具呼叫保底機制** — `crew.py`（agent prompt）、`report_validator.py`：(a) prompt 明確列出必須呼叫的工具清單；(b) Gate 新增 `_check_tool_coverage()`，5 核心工具命中 < 3 則 block。

### P2 — 自動化與自我改進（下個 Sprint）

- [ ] **backtest --update-config** — `backtest.py`、`config.py`：新增 `--update-config` CLI flag，回測完自動寫最佳信號權重到 `SIGNAL_WEIGHTS` dict。
- [ ] **weekly-backtest.yml** — `.github/workflows/weekly-backtest.yml`（新）：每週一 02:00 HKT cron 觸發，結果 commit 回 main。
- [ ] **Gate 失敗結構化 log** — `bigquery_writer.py`、`report_validator.py`：失敗時寫結構化 JSON（類型、prefix、時間戳）到 BQ `gate_failure_log` 表。**不自動改 prompt**。
- [ ] **tools.py 模組分割** — `tools.py` → `tools/crypto.py`、`tools/macro.py`、`tools/equities.py`、`tools/search.py`、`tools/quant.py`；`tools/__init__.py` re-export。4011 行 god-file。

### P3 — 長期改進（Backlog）

- [ ] **Gate 失敗自動學習 prompt 注入** — `crew.py`、`bigquery_writer.py`：分析 `gate_failure_log` 高頻類型，生成「避免模式」段落。需人工審核。依賴 P2 Gate log。
- [ ] **_adaptive_threshold() Gate 自動調節** — `report_validator.py`：統計 7 天 pass rate > 80% 自動提高門檻。依賴 P2 Gate log。
- [ ] **agent tool-use 強制驗證** — `crew.py`：kickoff() 後檢查 tool call 記錄，crypto_researcher 未呼叫任何 tool 則觸發 retry。

---

## 🚀 三大戰略方向（2026-03-26 新增，保留）

> 中長期方向，優先級低於上方 P0-P3。執行時間軸：1A → 2A → 1B → 2B → Direction 3

### Direction 1A — 穩定視覺化輸出

- [ ] `visualizer.py` — 新增 Panel 4：BTC 資金費率（fundingRate）趨勢折線圖（CoinGlass API 已有）
- [ ] `dashboard.py` — 新增 Streamlit Tab 5：Sentiment Score；Tab 6：SOPR + Exchange Netflow 雙軸圖
- [ ] `telegram_sender.py` + `templates/telegram_report.j2` — 報告底部加「查看歷史」Inline Keyboard Button（`reply_markup`）
- [ ] `data-verification-ui/src/` — ServiceWorker Web Push 通知（BTC 異動 / 日報到達）

### Direction 1B — 商業化地基

- [ ] `auth.py` (新) — Firebase Auth JWT middleware（FastAPI `Depends`）
- [ ] `billing.py` (新) — Stripe Checkout + Webhook；FREE / PRO / INSTITUTIONAL 三級
- [ ] `api.py` — 依 tier 限制資料範圍：FREE=7天、PRO=全部、INSTITUTIONAL=直連 API key
- [ ] `telegram_sender.py` — PRO 用戶帶自己的 BOT_TOKEN + CHAT_ID（從 BQ `user_settings` 表讀取）
- [ ] `data-verification-ui/src/pages/Landing.jsx` (新) — Landing page：Hero + 方案比較表 + Stripe Checkout

### Direction 2A — 績效反饋閉環

- 已併入 P2（backtest --update-config + weekly workflow）
- [ ] `crew.py` — Quant Strategist prompt 注入「過去 3 天 HIT_STOP 反饋」（`bigquery_writer._fetch_recent_stopped_out_trades` 已實作）
- [ ] `report_validator.py` — `_adaptive_threshold()`（已列 P3）

### Direction 2B — OSS 自主整合 Scout Agent

- [ ] `agents/scout_agent.py` (新) — GitHub GraphQL + HuggingFace Hub 搜尋；過濾：Stars ↑500/月、MIT/Apache、Python、領域=crypto-analytics/LLM-finance
- [ ] `agents/integration_proposal_agent.py` (新) — clone → 分析 API → 生成整合 diff → 跑 smoke test → 自動開 PR（**不自動合併**）
- [ ] `.github/workflows/weekly-scout.yml` (新) — 週五 18:00 HKT 觸發

### Direction 3 — Multi-Agent 新創規模

- [ ] `agents/product_crew.py` (新) — PM Agent + UX Researcher Agent（每週功能優先排序 + 用戶痛點）
- [ ] `agents/growth_crew.py` (新) — Marketing Agent + Competitor Intel Agent（每週競品 + GTM 草稿）
- [ ] `agents/finance_crew.py` (新) — CFO Agent + Cost Optimizer Agent（每日 API 成本 + 月度 P&L 預測）
- [ ] `agents/engineering_crew.py` (新) — Tech Radar Agent + Code Review Agent（依賴更新建議 + Dependabot-style PR）
- [ ] `agents/arbiter_crew.py` (新) — 接收所有 Crew 輸出，產出全局風險預算 + 跨部門一致性檢查
- [ ] `company_report_render.py` (新) — 合併所有 Crew 輸出，渲染「新創公司日報」
- [ ] `main.py` — 新增 `--mode=company_daily` 支援 6 Crew 並行
- [ ] `data-verification-ui/` — Company War Room 頁面（各部門狀態 + 公司日報）

---

## 已落地（自 TODOS 移除細項，僅存檔備查）

- **統一 API schema guard：** [`api_schema.py`](api_schema.py)（`require_json_dict`、`require_list`、`log_schema_mismatch`）與 [`test_api_schema.py`](test_api_schema.py)。
- **盤中異常推送：** [`monitor_intraday.py`](monitor_intraday.py)、[`.github/workflows/monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)。
- **LLM run log → BigQuery：** [`bigquery_writer.py`](bigquery_writer.py) 內 `write_llm_run_log`、[`main.py`](main.py) 呼叫與 [`test_llm_run_log.py`](test_llm_run_log.py)。
- **新聞新鮮度 Gate（機檢邏輯）：** [`report_validator.py`](report_validator.py) 內 `_check_news_freshness` 等；預設關閉，見 P1 項目。
- **Q-Score 品質卡（A+B+C 方案）：** `report_judge.py`、`main.py`、`check_report.py` — PR #66-68。
- **Writing Editor Agent（第 4 agent）：** `crew.py` — `gpt-5.4-nano-2026-03-17` 潤稿角色，PR #68。
- **Gemini 3 Flash 切換：** `config.py` — Risk Critic + Quant Strategist 改用 `gemini-3-flash-preview`。
- **narrative auto-truncation：** `schemas.py` — `@field_validator` 取代 `max_length` 硬驗證。
- **Q-Score regex 修復：** `report_judge.py` — 工具偵測、腿數計算、HTML tag 處理。
