# Dexter 概念導入計畫（Q-Silicon）

參考開源專案 [virattt/dexter](https://github.com/virattt/dexter) 的「規劃、自驗、可追溯、防跑飛、評測」思路，在 **本專案 Python / CrewAI / `validate_report`** 架構內分階落地。**不得**讓 LLM 自行捏造客觀報價；數字仍須來自 `tools.py` 與既有注入 Context。

---

## Phase 0：基線與成功定義 ✅（本文件 + CI）

| 項目 | 說明 |
|------|------|
| **Done** | 本文件存在；團隊對各 Phase 的「完成」與「驗證」有共識。 |
| **驗證** | CI 通過 `ruff check .`（若已啟用）與 `pytest`（含 `test_validate_report.py`）。 |
| **回滾** | 無需回滾（僅文件）。 |

### 現有 Gate 速查（程式真實來源：`main.py`）

- `validate_report()`：新聞數、UTC+8、`market_regime`、儀表板、QSREC、SourceHealth、宏觀異常、傳聞可信度等。
- `STRICT_CONSISTENCY_GATE`：驗證失敗時是否仍允許推送（預設擋）。
- `STRICT_PICK_JUSTIFICATION` / `STRICT_PICK_ROTATION` / `STRICT_PICK_SCORING`：選幣選股與 QSREC 量化欄位。
- `ALLOW_PARTIAL_NEWS_GATE`、`SKIP_TELEGRAM`、`SKIP_BIGQUERY` 等：見 `ENV_TEMPLATE.txt`、`README.md`。
- 重試：`MAX_REPORT_RETRIES`、`MAX_503_RETRIES`、`BACKOFF_BASE_SEC`。

---

## Phase 1：Scratchpad（可追溯 JSONL）✅

| 項目 | 說明 |
|------|------|
| **Done** | 每次 `run_pipeline_with_retries` 建立一個 `.jsonl`；寫入 `init`、`gate_result`（每次 `validate_report`）、`run_end`；部分工具寫入 `tool_call` / `tool_result`。 |
| **驗證** | `pytest test_scratchpad.py`；檔案可逐行 `json.loads`。 |
| **回滾** | 環境變數 `SCRATCHPAD_ENABLED=0` 關閉寫入（工具與主流程變為 no-op）。 |

### 環境變數

- `SCRATCHPAD_ENABLED`：預設 `1`；`0` / `false` / `no` 關閉。
- `SCRATCHPAD_DIR`：預設 `.qsilicon/scratchpad`（相對專案根目錄）。

### 已掛勾工具（示例，可再擴充）

- `market_search_tool`、`coinglass_data_tool`、`macro_context_tool`（透過 `traced_tool_execution`）。

### 目錄與 Git

- 產物目錄：`.qsilicon/scratchpad/`（已列入 `.gitignore`，避免將工具回傳內容誤提交）。

---

## Phase 2：Pre-flight Checklist（規劃中）

| Done | 戰報或結構化區塊含可機器比對的勾選項，並與 `validate_report` 交叉驗證。 |
| 驗證 | pytest + 新增 Gate 規則測試。 |
| 回滾 | 環境變數關閉該段 Gate。 |

### 試做方向

| 子項 | 內容 | 預估工量 |
|------|------|----------|
| **2a** | 在戰報末尾或 `[QSREC_END]` 後加入 `[CHECKLIST]` 區塊：`□ 新聞6則 □ regime □ 儀表板 □ 風險預算 □ QSREC`，由 LLM 自行勾選；`validate_report` 同時比對 checklist 勾選與實際檢查結果，不一致記為 issue。 | 中 |
| **2b** | 主編 Task prompt 明確要求「產出前自我檢查」；不改戰報格式，僅強化 prompt，並在 scratchpad 的 `gate_result` 中附上 `checklist_self_report`（若後續擴充主編輸出結構）。 | 小 |
| **2c** | 先做 2b，觀察主編輸出穩定性後再決定是否引入 2a 格式。 | - |

### 評分（Phase 2 完成度）

| 分數 | 標準 |
|------|------|
| 0 | 未啟動 |
| 3 | 2b 完成：prompt 已加入自我檢查指引 |
| 6 | 2a 完成：戰報含 `[CHECKLIST]` 且 validate_report 能比對 |
| 10 | 2a + pytest 覆蓋 checklist 不一致情境，CI 通過 |

---

## Phase 3：防跑飛 / Step limit（規劃中）

| Done | 工具呼叫次數上限、重複參數偵測。 |
| 驗證 | 單元測試模擬連續相同呼叫；可選整合 smoke。 |
| 回滾 | 調高上限或 `0` 關閉。 |

### 試做方向

| 子項 | 內容 | 預估工量 |
|------|------|----------|
| **3a** | 在 `scratchpad` 或 CrewAI 執行層統計每 run 的 tool 呼叫次數；超過 `MAX_TOOL_CALLS_PER_RUN`（預設 80）時提早終止並寫入 `run_end` 原因。 | 中 |
| **3b** | 偵測連續 N 次（如 3 次）相同 tool + 相同參數 → 記為 `repeated_call`，可選：發送警告或強制結束。 | 中 |
| **3c** | 先做 3a（單純次數上限），驗證不影響正常產報後再加 3b。 | - |
| **3d** | 環境變數：`MAX_TOOL_CALLS_PER_RUN`、`REPEATED_CALL_THRESHOLD`（0=關閉重複偵測）。 | 小 |

### 評分（Phase 3 完成度）

| 分數 | 標準 |
|------|------|
| 0 | 未啟動 |
| 4 | 3a 完成：tool 呼叫次數統計 + 上限強制終止 |
| 7 | 3b 完成：重複參數偵測 + 可配置閾值 |
| 10 | 3a + 3b + pytest smoke 覆蓋超限與重複情境 |

---

## Phase 4：離線 Eval fixtures（4a–4c 已落地）

| Done | `eval/` 或 `tests/fixtures/reports/` + runner。 |
| 驗證 | CI job 跑 eval；合併前不得降低通過率（可 artifact 比對）。 |
| 回滾 | 從 CI 移除 job。 |

### 試做方向

| 子項 | 內容 | 預估工量 |
|------|------|----------|
| **4a** | 建立 `tests/fixtures/reports/`：含 `valid_full.txt`、`partial_news_ok.txt`、`trade_watch.txt`、`invalid_short.txt`、`invalid_mixed_regime.txt` 等 5–8 則固定戰報，每則附 `expected_validation.json`（valid、issues_count、關鍵 flags）。 | 中 |
| **4b** | 新增 `test_validate_report_fixtures.py`：遍歷 fixtures，對每則戰報呼叫 `validate_report`，assert 結果與 `expected_validation.json` 一致（或允許 issues 子集比對，依實作彈性）。 | 中 |
| **4c** | CI 在 `pytest` 時一併跑 fixtures；PR 合併前若任一 fixture 失敗則擋下。 | 小 |
| **4d** | 未來擴充：`eval/` 下放真實產出的脫敏戰報樣本，供手動回歸或 prompt 改版比對。 | 大 |

### 評分（Phase 4 完成度）

| 分數 | 標準 |
|------|------|
| 0 | 未啟動 |
| 4 | 4a 完成：至少 5 則 fixtures + expected_validation |
| 7 | 4a + 4b：pytest 全通過 |
| 10 | 4a + 4b + 4c：CI 整合，合併前強制檢查 |

---

## Phase 5：營運指標閉環（規劃中）

| Done | BQ 或日誌聚合：Gate 主因、重試次數、產報耗時。 |
| 驗證 | 排程查詢 + 異常 spike 告警。 |
| 回滾 | 停用查詢與告警。 |

### 試做方向

| 子項 | 內容 | 預估工量 |
|------|------|----------|
| **5a** | 擴充 scratchpad `run_end` / gate 寫入：記錄 `top_issues`、`retry_count`、`elapsed_sec`；或新增 `pipeline_metrics` 事件型態寫入 JSONL。 | 小 |
| **5b** | 在 BigQuery 新增 `pipeline_runs` 表（或沿用 `daily_metrics` 擴充欄位）：每 run 一筆，含 `run_id`、`valid`、`retries`、`top_gate_issue`、`duration_sec`、`timestamp`。 | 中 |
| **5c** | 於 Cloud Scheduler / cron 排程查詢：近 7 日 `valid=false` 比例、平均 retry、平均 duration；超過閾值時發送告警（Telegram 或 Email）。 | 大 |
| **5d** | 先做 5a（scratchpad 擴充），5b/5c 視維運需求決定優先級。 | - |

### 評分（Phase 5 完成度）

| 分數 | 標準 |
|------|------|
| 0 | 未啟動 |
| 3 | 5a 完成：scratchpad 已記錄 retry、elapsed、top_issues |
| 6 | 5b 完成：BQ 有 pipeline_runs 或等效寫入 |
| 10 | 5b + 5c：排程查詢 + 異常告警已上線 |

---

## 總體評分卡（試做進度）

| Phase | 說明 | 當前 | 目標 |
|-------|------|------|------|
| Phase 0 | 基線與成功定義 | 10 | 10 |
| Phase 1 | Scratchpad 可追溯 | 10 | 10 |
| Phase 2 | Pre-flight Checklist | 0 | 6 |
| Phase 3 | 防跑飛 / Step limit | 0 | 4 |
| Phase 4 | 離線 Eval fixtures | 10 | 10 |
| Phase 5 | 營運指標閉環 | 0 | 3 |
| **合計** | | **40/60** | **43/60** |

*建議試做順序：Phase 4（fixtures 立即可驗證 validate_report）→ Phase 2（checklist 強化品質）→ Phase 3（防跑飛）→ Phase 5（營運閉環）。*

---

*文件版本：與 repo 內 `scratchpad.py`、`main.py` 實作同步；若有衝突以程式為準。*
