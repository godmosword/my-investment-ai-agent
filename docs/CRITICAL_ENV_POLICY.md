# Critical env 策略（草案）

對齊 [`TODOS.md`](../TODOS.md) P0「Critical env 策略定稿」與 Priority **5**。

## 現況

- [`main.py`](../main.py)：`PIPELINE_STRICT_ENV=1` 時，在未 `SKIP_TELEGRAM`／`SKIP_BIGQUERY` 前提下，強制 Telegram 與 GCP 相關變數。
- 資料源 API（NewsAPI、CoinGlass…）缺 key 時，工具層回傳 `[DATA_MISSING:…]`，**不**在啟動時一律 hard fail（與產品「缺資料仍產報」一致）。

## 建議分級（產品定稿用）

| 層級 | 範例 | 建議行為 |
|------|------|----------|
| **L0 編排／推送** | `TELEGRAM_*`、`GCP_SA_KEY`（當 BQ／推送開啟） | 生產 `PIPELINE_STRICT_ENV=1` 已涵蓋 |
| **L1 日報 LLM** | `XAI_*`、`GEMINI_*`、`OPENAI_*`… | 啟動已驗證；缺一則無法跑 crew |
| **L2 資料 enrich** | `NEWSAPI_KEY`、`COINGLASS_API_KEY`… | 維持工具層 N/A；以 Gate／儀表板把關 |

若未來要對 **L2 子集**在生產 hard fail，須另開產品票：明列白名單與降級行為（避免與 `[DATA_MISSING]` 衝突）。
