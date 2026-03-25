# Project TODOs

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
