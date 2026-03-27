# 選標輪動語意對照（QSREC / BigQuery / Gate）

## 兩層機制

| 機制 | 資料來源 | 觸發條件 | 目的 |
|------|-----------|----------|------|
| **近 3 日排除清單** | [`bigquery_writer.fetch_exclusion_context`](../bigquery_writer.py) 查 `RECOMMENDATIONS_TABLE` 近 3 日 `DISTINCT asset` | 注入 crew 提示區「過去 3 天已建議的標的」 | 引導 LLM **優先**選清單外標的；仍可在「重大催化」下重複，並需寫「重複選用理由」 |
| **昨日集合輪動 Gate** | [`report_validator._fetch_yesterday_qsrec_canonical_set`](../report_validator.py) 查 **昨日** 同日 `DISTINCT asset`（依 `category`） | 今日 QSREC canonical 集合與 **昨日完全相同** | **機檢**：須換標或通過同標覆核（`重複選用理由` + `score_gap` + `repeat_days`/`selection_score` 門檻） |

兩者語意不同：**3 日清單**是「近期出現過的代號集合」；**昨日 Gate**是「上一個交易日是否整包重複」。因此可能出现：標的未出現在「近 3 日」文案中（邊界日／查詢差異），但與昨日 QSREC 相同而觸發輪動 Gate。

## Rolling 視窗加嚴（可選）

環境變數（預設關閉）：

- `PICK_ROLLING_FREQ_GATE=1`：啟用滾動視窗內「同資產出現日數」檢查（非 `trade_watch` 時）。
- `PICK_ROLLING_WINDOW_DAYS`：視窗長度（日，預設 5）；統計區間為 **截至昨日** 的連續日曆日。
- `PICK_ROLLING_MAX_DISTINCT_DAYS`：視窗內同一 canonical asset 最多允許 **幾個相異 `report_date`**；超過則本日 QSREC 不得再含該 asset（查詢失敗時略過，避免誤擋）。

與 `STRICT_PICK_ROTATION` 並用時，先滿足昨日集合規則，再套用滾動頻率上限。

## Canonical 鍵

與 [`tracker.canonical_asset_key`](../tracker.py) 一致（大寫、去 `$`、比值正規化），與 BQ `asset` 欄位對齊。
