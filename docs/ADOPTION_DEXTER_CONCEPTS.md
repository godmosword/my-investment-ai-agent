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

---

## Phase 3：防跑飛 / Step limit（規劃中）

| Done | 工具呼叫次數上限、重複參數偵測。 |
| 驗證 | 單元測試模擬連續相同呼叫；可選整合 smoke。 |
| 回滾 | 調高上限或 `0` 關閉。 |

---

## Phase 4：離線 Eval fixtures（規劃中）

| Done | `eval/` 或 `tests/fixtures/reports/` + runner。 |
| 驗證 | CI job 跑 eval；合併前不得降低通過率（可 artifact 比對）。 |
| 回滾 | 從 CI 移除 job。 |

---

## Phase 5：營運指標閉環（規劃中）

| Done | BQ 或日誌聚合：Gate 主因、重試次數、產報耗時。 |
| 驗證 | 排程查詢 + 異常 spike 告警。 |
| 回滾 | 停用查詢與告警。 |

---

*文件版本：與 repo 內 `scratchpad.py`、`main.py` 實作同步；若有衝突以程式為準。*
