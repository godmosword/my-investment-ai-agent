# REPORT_COMPARE_MODE — Staging 蒐集 dual-run

## 目的

在 **不切換正式輸出**（Telegram / BigQuery / `report_valid` 仍以 `main.validate_report` 為準）的前提下，讓候選路徑 `core.report_validation.validate_report_candidate` 與 legacy 並跑，並在日誌中記錄 snapshot 差異。

## 本機 / 手動跑一次

```bash
export REPORT_COMPARE_MODE=1
python main.py
```

日誌關鍵字：

- `REPORT_COMPARE: legacy vs candidate snapshots identical.`
- `REPORT_COMPARE: mismatch legacy vs candidate | ...`（若有差異）

## Cloud Run Job（建議）

在 Secret Manager 或 Job 環境變數中為 **staging / Canary Job** 單獨加上：

- `REPORT_COMPARE_MODE=1`

正式 production Job **不要**長期開啟（避免雙倍 `validate_report` 成本；候選與 legacy 目前仍等價時，log 僅多一次相同計算）。

等 `core/report_validation.py` 改為獨立實作後，再對 staging 長開 compare，蒐集一週 `mismatch` 比例後決定切流。

## 切流條件（建議）

1. staging 連續 N 天 `mismatch` 為 0 或僅允許清單內預期差異。
2. 完整 pytest（非僅 smoke）全綠。
3. 人為抽樣 3～5 份真實戰報目視 OK。

## 相關程式

- `main._log_validation_dual_run` — 每次 `validate_report` 後觸發比對。
- `report_pipeline_compare.py` — snapshot / diff 邏輯。
- `core/report_validation.py` — 候選入口（目前 delegate 至 `main.validate_report`）。
