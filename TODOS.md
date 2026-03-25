# Project TODOs

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
