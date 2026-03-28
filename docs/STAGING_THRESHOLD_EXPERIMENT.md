# Staging：選幣／選股 Gate 閾值實驗

對齊 [`TODOS.md`](../TODOS.md) 橫切「閾值實驗」與 Priority **1**。

## 建議操作

1. 在 **staging**（非生產頻道）單變因調整，每次只改一項：
   - `PICK_ROTATION_OVERRIDE_MIN_GAP`（預設 12）
   - `PICK_REPEAT_MIN_SELECTION_SCORE`（預設 75）
2. 跑完整管線或至少雙 crew，記錄：
   - `validate_report` 是否通過
   - [`gate_failure_log`](../docs/SQL/gate_failure_weekly_summary.sql) 或本機 `.qsilicon/last_gate_failure/`（若啟用）
   - 主觀：日報是否仍「可讀、可執行、標的多樣性可接受」
3. 維持 3–5 個交易日再換下一組參數，避免單日雜訊。

## 與自適應門檻的銜接

[`adaptive_gate_thresholds.py`](../adaptive_gate_thresholds.py) 預留 `ADAPTIVE_GATE_THRESHOLDS=1`；實驗數據可作為日後 BQ 聚合調整的標的。
