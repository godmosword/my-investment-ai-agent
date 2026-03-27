# Critical env 策略（對齊 TODOS P0）

## 原則

- **全資料源 hard fail** 與產品假設「工具可回傳 `[DATA_MISSING]`／正文勿出現字面標記」衝突；實務上採 **分級**。
- **排程／生產**：建議 `PIPELINE_STRICT_ENV=1`（見 [`main.py`](../main.py) `_validate_critical_env_strict`），確保 Telegram／BigQuery 等關鍵路徑具憑證。
- **本機／CI**：可 `SKIP_BIGQUERY=1`、`SKIP_TELEGRAM=1` 等，不強制所有資料 API。

## 可選加嚴 Gate（預設關閉）

| 變數 | 說明 |
|------|------|
| `DATA_MISSING_COUNT_GATE_MAX` | 正文 `[DATA_MISSING:…]` 超過個數則擋推送 |
| `PICK_ROLLING_FREQ_GATE` + `PICK_ROLLING_MAX_DISTINCT_DAYS` | 滾動視窗同標頻率上限（見 [PICK_ROTATION_SEMANTICS.md](PICK_ROTATION_SEMANTICS.md)） |
| `STRICT_PAIR_TRADE_UNIT_GATE` | 配對交易單位機檢升格 blocking |
| `STRICT_MACRO_CONFLICT_GATE` | 宏觀 2Y/利差矛盾升格 blocking |
| `STRICT_TOOL_EVIDENCE_GATE` | 加密段工具關鍵詞密度檢查 |
| `STRICT_QSREC_SCENARIO_GATE` | QSREC `confidence≥3` 須填三情境欄位 |

完整列表見 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)。
