# Project TODOs

## Autoresearch 7-Day Sprint Checklist

詳見 [autoresearch.plan.md](docs/autoresearch.plan.md)。衝刺規則：禁止自動合併 `main`、總預算 **30 USD**（soft 24）、第一 KPI **token 成本**。

### Sprint guardrails

- [ ] 禁止任何自動合併到 `main`（只允許 `experiment/*` + Draft PR）
- [ ] 總預算 hard cap = **30 USD**；soft cap = **24 USD**
- [ ] 第一優先 KPI = **token 成本**；硬約束優先：`ruff` + `pytest -m smoke` + fixture gate pass

### Day 1 — Baseline / 規格凍結

- [ ] 定義 METRIC：`lint_pass`、`smoke_pass`、`gate_fixture_pass`、`wall_time_sec`
- [ ] 定義 METRIC：`actual_input_tokens`、`actual_output_tokens`、`actual_cost_usd`、`stop_reason`
- [ ] 停機規則：`cost_used_usd >= daily_budget_cap`
- [ ] 停機規則：`iterations_without_improvement >= 5`
- [ ] 停機規則：`gate_fixture_pass != 1` 連續 2 次
- [ ] 停機規則：timeout 觸發
- [ ] 交付：衝刺規格補齊（可併入 `docs/AUTORESEARCH_SPRINT.md`）

### Day 2 — L0/L1 單入口 benchmark

- [ ] 單一入口（例：`scripts/bench_autoresearch.sh`）
- [ ] L0：`ruff check .`
- [ ] L1：`pytest -m smoke -q`
- [ ] stdout：`METRIC key=value`
- [ ] 同 commit 連跑 2 次一致；單次 **小於 10 分鐘**

### Day 3 — fixture gate 去噪

- [ ] 固定 `validate_report` / structured fixtures 納入 L1
- [ ] 同 commit + 同 fixture 連跑 3 次一致

### Day 4 — 治理與最小權限

- [ ] allowlist（首版 ≤5 路徑）；denylist（首輪不動核心 Gate 阻擋邏輯）
- [ ] 分支：`experiment/*` only
- [ ] 權限：可更新 `experiment/*`、可開/更新 Draft PR；**不可** push `main`、**不可** merge

### Day 5 — Human-in-the-loop

- [ ] 5–10 輪：提案 → bench → 保留/回滾；每輪記錄 metrics 與 `stop_reason`
- [ ] 至少 1 份實驗紀錄（JSONL 或 MD）

### Day 6 — workflow_dispatch

- [ ] 僅 `workflow_dispatch`；`max_iterations` + `timeout` + budget cap
- [ ] 輸出僅 `experiment/*` 或 Draft PR；手動跑通 1 次

### Day 7 — 驗收與 Retro

- [ ] 端到端：改碼提案 → Draft PR
- [ ] 驗收：L0/L1 小於 10 分鐘、Draft PR ≥1、停機規則生效、預算 ≤30 USD
- [ ] `sprint-retro` + 下輪 backlog

### Daily budget（參考）

- [ ] D1 0.5 / D2 1 / D3 1.5 / D4 1 / D5 6 / D6 8 / D7 6 USD；緩衝 6 USD

### End-of-day 檢查

- [ ] `cost_used_today <= daily_cap`
- [ ] `iterations_without_improvement < 5`
- [ ] `gate_fixture_pass` 未連續失敗 ≥2

---

## TODO: 新聞時間新鮮度機檢（Gate）

- **What:** 在 `validate_report` 新增新聞時間新鮮度檢查，預設要求 `〔新聞 N〕` 的時間戳需落在「報告時間前 48 小時內」，並提供來源例外白名單機制。
- **Why:** 目前 Gate 只驗證新聞格式與時區，仍可能放行過舊新聞，導致同日決策敘事與實際市場節奏脫節。
- **Pros:** 降低過期新聞造成的錯誤輪動、提升報告時效一致性、讓「本日選擇理由」更可被追溯驗證。
- **Cons:** 需處理時區、無時間戳來源、新聞聚合延遲等例外，若規則過嚴會提高誤擋率。
- **Context:** 目前戰報已強制 `UTC+8` 標記與 `〔新聞 N〕` 格式，但未硬檢「新鮮度」。建議沿用既有 `_has_news_timezone_utc8` 與新聞抽取流程，在同一管線新增時間窗判定，並以 env 控制（例如 `STRICT_NEWS_FRESHNESS_GATE`）逐步上線。
- **Depends on / blocked by:** 需先定義「報告時間基準」（生成時間 vs 推送時間）與「白名單來源」規格；再補齊對應測試案例（新鮮/過舊/無時間戳/跨日邊界）。

## TODO: 啟動期 critical env 完整驗證（fail-fast）

- **What:** 擴充 `_validate_required_keys()`（或新增 `_validate_critical_env()`），依執行路徑檢查：Telegram 推送所需 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`（若未 `SKIP_TELEGRAM`）、BigQuery 寫入所需 `GCP_SA_KEY` 或 `GOOGLE_APPLICATION_CREDENTIALS` / `PROJECT_ID`、以及管線實際會呼叫的 data API（見 `_log_api_key_inventory`「建議/備援」群組）。
- **Why:** 目前僅在啟動時驗證少數 LLM + Apify，其餘在執行中才失敗，浪費長跑管線時間且 log 分散。
- **Pros:** 早失敗、部署/排程可預期、減少「跑到一半才發現缺 key」的支援成本。
- **Cons:** 需釐清「可選功能」與「強制」邊界（例如 SKIP_BIGQUERY、SKIP_TELEGRAM）；過嚴會阻擋本機僅跑部分流程。
- **Context:** 入口在 `main.py` 的 `_validate_required_keys()` 與 `_log_api_key_inventory()`；建議用 env 旗標（既有 `SKIP_*`）做條件式必填表，並在 README / `ENV_TEMPLATE.txt` 對齊說明。
- **Depends on / blocked by:** 需先盤點 `main.py` 與 `tools.py` 哪些分支在預設 prod 一定會走到；再決定「警告 vs 硬擋」矩陣。

## TODO: tools.py God-file 分割（P1 — 下個 sprint）

- **What:** 將 `tools.py` 按資料來源類型分裝成多個模組（crypto / macro / equities / search / quant），`tools.py` 保留 backward-compat re-export 層。
- **Why:** 單檔過大時 review diff 不精準、維護成本高。
- **Pros:** 模組邊界清晰、diff 更小、可並行開發。
- **Cons:** 機械搬移工作量大；需保持 re-export 避免 import 爆炸。
- **Effort:** L | **Priority:** P1

## TODO: Gate 失敗自動學習（P3 — 遠期）

- **What:** 每次 `validate_report` 失敗，將失敗原因分類寫入 BigQuery；週期性腳本分析高頻失敗類型，生成「請避免這些模式」提示詞段落供 crew 附加。
- **Why:** 降低長期 Gate 失敗率與人工維護成本。
- **Cons:** 需防 prompt injection；自動生成段落需人工審核機制。
- **Effort:** L | **Priority:** P3
- **Depends on / blocked by:** `gate_failure_log` BQ 表設計 + 防注入規格；建議 P1/P2 後再設計。

---

## 已落地（自 TODOS 移除，僅存檔備查）

- **統一 API schema guard：** 已見 [`api_schema.py`](api_schema.py)（`require_json_dict`、`require_list`、`log_schema_mismatch`）與 [`test_api_schema.py`](test_api_schema.py)。
- **盤中異常推送：** 已見 [`monitor_intraday.py`](monitor_intraday.py)、[`.github/workflows/monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)（閾值與靜默期以程式與 workflow 為準）。
- **LLM run log → BigQuery：** 已見 [`bigquery_writer.py`](bigquery_writer.py) 內 `write_llm_run_log`、[`main.py`](main.py) 呼叫與 [`test_llm_run_log.py`](test_llm_run_log.py)。
