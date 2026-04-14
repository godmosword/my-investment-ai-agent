# Critical env 策略（定稿）

對齊 [`TODOS.md`](../TODOS.md) P0「Critical env 策略定稿」與 Priority **2**。  
**目標**：排程／生產啟動行為可預期；與 `[DATA_MISSING]` 工具層語意不衝突。

## 現況（程式契約）

| 機制 | 位置 | 行為 |
|------|------|------|
| **必要 LLM／搜尋鍵** | [`main.py`](../main.py) `_validate_required_keys` | 缺任一即 **RuntimeError**，管線不啟動 |
| **可選 Telegram** | 同上＋`_validate_critical_env_strict` | 未設 `SKIP_TELEGRAM` 時缺鍵僅 **warning**，推送略過 |
| **可選 BigQuery** | 同上 | 未設 `SKIP_BIGQUERY` 時缺 `GCP_PROJECT_ID` 或憑證僅 **warning** |
| **嚴格模式** | `_validate_critical_env_strict` | `PIPELINE_STRICT_ENV=1` 且未 `SKIP_TELEGRAM` → 必須 `TELEGRAM_BOT_TOKEN`＋`TELEGRAM_CHAT_ID`；未 `SKIP_BIGQUERY` → 必須 `GCP_PROJECT_ID` 與（`GCP_SA_KEY` 或 `GOOGLE_APPLICATION_CREDENTIALS`） |
| **數值 env** | `_validate_env_types` | 列管變數須為數字，否則啟動失敗（含 `PICK_ROTATION_*`、`CREW_FUTURE_TIMEOUT_SEC` 等） |
| **金鑰盤點（不洩密）** | `_log_api_key_inventory` | 啟動時 INFO：必要鍵 OK／MISS；建議鍵 MISS 僅影響工具備援 |

## 建議分級（產品／維運對照）

| 層級 | 範例變數 | 建議行為 |
|------|----------|----------|
| **L0 編排／推送** | `TELEGRAM_*`、`GCP_*`（當 BQ／推送未 SKIP） | **生產／排程**建議 `PIPELINE_STRICT_ENV=1`，與上表嚴格模式一致 |
| **L1 日報 LLM** | `XAI_*`、`OPENAI_*`、`GEMINI_*`、`APIFY_*` | 已由 `_validate_required_keys` **硬擋** |
| **L2 資料 enrich** | `NEWSAPI_KEY`、`COINGLASS_API_KEY`、`FMP_*`… | **維持**工具層 `[DATA_MISSING:…]`；以 Gate／儀表板把關，啟動不強制 |

若未來要對 **L2 子集**在生產 **hard fail**，須另開產品票：明列白名單、降級行為與與 `[DATA_MISSING]` 的相容策略。

## 環境矩陣（快速勾選）

| 場景 | `PIPELINE_STRICT_ENV` | `SKIP_TELEGRAM` | `SKIP_BIGQUERY` | 預期 |
|------|:---------------------:|:---------------:|:---------------:|------|
| 本機乾跑／CI smoke | 0 | 1 | 1 | 不驗 TG／BQ；仍要 L1 四鍵（除非測試 stub） |
| Staging 完整推播 | 1 | 0 | 0 | TG＋GCP 必填 |
| 僅測 crew、不寫 BQ | 0 | * | 1 | BQ 可略；TG 視需求 |
| 生產排程（建議） | 1 | 0 | 0 | 與 staging 同 |

## 維運檢查清單（上線前）

- [ ] 排程／Runner 已設 `PIPELINE_STRICT_ENV=1`（若要走正式推播＋BQ）
- [ ] `GCP_SA_KEY` 或 workload identity 已配置，且表權限符合 [`DEPLOY_RUNBOOK.md`](DEPLOY_RUNBOOK.md)
- [ ] `GATE_FAILURE_BQ_LOG` 如需關閉，已確認不需週聚合／自適應門檻
- [ ] 機密僅存在 Secret／Environment，未寫入 repo

## 修訂紀錄

- **2026-04-14**：對齊 [`main.py`](../main.py) `_validate_env_types` — 自適應門檻相關數值變數（`ADAPTIVE_GATE_BQ_LOOKBACK_DAYS` 等）納入啟動校驗；scratchpad `init.meta.pipeline_config` 寫入非機密旗標與 `effective_pick_rotation_override_min_gap`（便於 staging／稽核）。
- **2026-04-04**：由「草案」升級為定稿；補程式對照表、環境矩陣、維運檢查清單。
