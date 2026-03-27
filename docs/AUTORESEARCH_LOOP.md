# Autoresearch 迴圈（規格摘要）

對齊 [`autoresearch.plan.md`](autoresearch.plan.md) 與 Backlog **BL-04**、**BL-05**、**BL-07**。

## 角色與產物

| 階段 | 行為 | 產物 |
|------|------|------|
| 變更提案 | Agent／人類修改 prompt、validator、工具參數 | Git diff |
| 驗證 | `ruff`、`-m smoke`、（可選）完整 `pytest`、`python main.py` 乾跑 | 通過／失敗 |
| 記錄 | scratchpad、（可選）`runs.jsonl` 或 CI artifact | 可重現 trace |

## 狀態機（建議）

1. **proposed**：有 diff，尚未跑過目標測試集。  
2. **bench_ok**：[`scripts/bench_autoresearch.sh`](../scripts/bench_autoresearch.sh) 或同等管線通過。  
3. **merged**：經 code review 合併主線。  
4. **revert**：指標退步或 Gate 回歸 → 回滾 diff，回到上一穩定 `bench_ok`。

「plateau」判讀：連續 N 次 run（例如 `runs.jsonl` 內）Gate 失敗 bucket 分佈與分數無顯著改善 → 停止同方向微調，改換假設或擴充資料源（見 plan 書 UNRESOLVED）。

## 與本 repo 的接點

- 戰報品質：**`report_validator.validate_report`**、`.qsilicon/last_gate_failure/`、`GATE_FAILURE_BQ_LOG`。  
- 輕量 bench：**`scripts/bench_autoresearch.sh`**（僅輸出尾端 `METRIC key=value` 作為官方指標）。  
- 完整管線：需金鑰，不納入預設 bench。

## 未解議題

細節仍以 [`autoresearch.plan.md`](autoresearch.plan.md) 的 **UNRESOLVED** 為準；本檔不複製長篇討論，只固定「誰驗證、何時可合併、如何回滾」。
