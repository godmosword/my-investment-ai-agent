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

## TODO: 統一 API 回應 schema guard helper
- **What:** 在 `tools.py`（或小型 `api_schema.py`）新增最小共用函式，例如 `require_json_dict(resp) -> dict`、`require_list(obj, path)`、`log_schema_mismatch(source, expected, got)`，供 CoinGlass / NewsAPI / CryptoPanic 等關鍵路徑共用。
- **Why:** 多處 `.json().get("results", [])` 在 API 改版時會 silent degrade；集中 guard 可一致記錄與 fallback。
- **Pros:** DRY、可測試、之後擴到其他來源成本低。
- **Cons:** 若 guard 過嚴可能誤判邊緣回應；需搭配單元測試與實際 sample payload。
- **Context:** 與 review 決議「先三路徑 2A」銜接：第一階段可在各工具內嵌檢查；第二階段抽成 helper 並逐步遷移（本條目追蹤第二階段）。
- **Depends on / blocked by:** 先完成 CoinGlass / NewsAPI / CryptoPanic 三路徑的具體欄位契約與測試 fixture。

---

## TODO: tools.py God-file 分割（P1 — 下個 sprint）
- **What:** 將 `tools.py`（2,809 行）按資料來源類型分裝成 5 個模組：`tools_crypto.py`（CoinGlass、CryptoPanic、Fear&Greed、on-chain）、`tools_macro.py`（FRED、macro context、regime scorecard）、`tools_equities.py`（yfinance wrappers、ETF flow、FMP）、`tools_search.py`（Apify、NewsAPI、GNews）、`tools_quant.py`（ML quant、backtest helpers）。`tools.py` 保留 backward-compat re-export 層。
- **Why:** 每次新增或修改任何工具，都需 review 整個 2,809 行檔案，review diff 不精準，CI import 慢。隨功能成長問題會加劇。
- **Pros:** 模組邊界清晰、新工具歸屬直觀、diff 更小、可並行開發。
- **Cons:** 需要 L 工作量的機械式搬移；搬移中需保持 backward-compat re-export 層，避免 crew.py / main.py 的 import 爆炸。
- **Context:** `crew.py` 和 `main.py` 直接從 `tools` import 多個函式；分割後 `tools.py` 應成為純 re-export 層（`from tools_crypto import *` 等），不改動呼叫方。每個子模組應有對應的測試覆蓋回歸。
- **Effort:** L | **Priority:** P1
- **Depends on / blocked by:** 無前置依賴，可作為獨立 sprint 啟動。回滾策略：git revert + redeploy（無 DB 變更，5 分鐘內完成）。

## TODO: 盤中異常事件即時推送（P2）
- **What:** 獨立監控腳本（或 GitHub Actions cron job），每小時輪詢 BTC 和 VIX；當 BTC 單小時漲跌 ≥ 5% 或 VIX 突破 30 時，自動 POST 一則精簡警示到 Telegram，不等到隔天晨報。
- **Why:** 日報是隔天香摘，市場暴走時用戶需要即時訊號，否則決策視窗已過。
- **Pros:** 讓系統從「每日出版商」升級為「即時情報員」；yfinance 和 Telegram 基礎設施已有。
- **Cons:** 需要常駐進程或頻繁 cron，Cloud Run 每次冷啟動有成本；需設計「靜默期」避免重複推送同一事件。
- **Context:** `_quote_of()` 和 Telegram 推送邏輯已在 `main.py` / `telegram_sender.py`。建議先以 GitHub Actions 的 `schedule:` cron 實作（省去常駐進程），以 BigQuery 記錄已推送事件避免重複。
- **Effort:** M | **Priority:** P2
- **Depends on / blocked by:** 需先定義閾值（BTC ±5%、VIX>30 可用 env var 設定），以及靜默期設計（同一事件 N 小時內不重複推送）。

## TODO: LLM 費用與可靠性追蹤至 BigQuery（P2）
- **What:** 在 `_run_pipeline_once()` 執行結束後，將「使用了哪個 LLM（Grok/GPT/fallback）、retry 次數、是否用 fallback、Gate 是否通過」寫入 BigQuery 的 `llm_run_log` 資料表。
- **Why:** 目前無法量化 Grok vs GPT 的成本與可靠性差異，無法做出 data-driven 的 LLM 選擇決策。
- **Pros:** 一週後即可看到每個 LLM 的 Gate 通過率與 retry 頻率；為日後自動路由提供依據。
- **Cons:** 需先定義 `llm_run_log` 資料表 schema 並建表；token 用量需要 LLM SDK 回報，部分 SDK（如 LiteLLM through CrewAI）可能不直接暴露 token count。
- **Context:** `use_fallback_llm` 旗標已存在於 `_run_pipeline_once()` 簽名中；retry 計數在 `run_pipeline_with_retries()` 的 loop 變數可取得。初期可只記錄「哪個 LLM + retry 次數 + Gate 結果」，不依賴 token count。
- **Effort:** S | **Priority:** P2
- **Depends on / blocked by:** 需先在 BigQuery 建立 `llm_run_log` 資料表（可與 daily_metrics 同 dataset）。

## TODO: Gate 失敗自動學習（P3 — 遠期）
- **What:** 每次 `validate_report` 失敗，將失敗原因分類寫入 BigQuery 的 `gate_failure_log`。另設週期性腳本，分析近 N 天最高頻失敗類型，自動生成「請避免這些模式」的提示詞段落，供下次 crew prompt 附加。
- **Why:** Gate 修正目前全靠人手 commit（已有 8+ 次 gate-fix commits）。應讓系統自己從失敗中學習，降低每月 Gate 失敗率。
- **Pros:** 理論上可持續改善 LLM 輸出品質，減少人工維護成本。
- **Cons:** 需謹慎設計以防 prompt injection（gate 失敗訊息若含惡意格式可能污染 prompt）；自動生成的「避免提示詞」需要人工審核機制，否則可能產生反效果。
- **Context:** Gate 失敗資訊已在 `scratchpad.append_gate_result()` 記錄；`_persist_gate_validation_failure()` 也有本地 artifact 寫入。可從這兩個現有來源提取，進一步寫入 BQ。提示詞注入需設計沙箱格式（例如 XML 標記包裹）。
- **Effort:** L | **Priority:** P3
- **Depends on / blocked by:** 需先完成 `gate_failure_log` BQ 表設計 + prompt injection 防範規格；建議先做 P1/P2 項目再回頭設計這個。
