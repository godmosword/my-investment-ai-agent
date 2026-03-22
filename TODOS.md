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
