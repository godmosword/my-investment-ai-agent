# Lean Baseline

> 目的：在重構前先建立可量測基準，避免「感覺變快」但不可驗證。

## 1) 日報執行樣本（3 次）

| run_id | 日期 | wall_time_sec | 是否成功 | 失敗型態 | 可用性(1-5) | 備註 |
|---|---|---:|---|---|---:|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 2) 文檔分類（排除 `.agents/`）

| 檔案 | 分類(保留/合併/刪除) | 理由 |
|---|---|---|
| README.md | 保留 | 權威產品說明 |
| CLAUDE.md | 保留 | 權威開發規範 |
| TBD | TBD | TBD |

## 3) CI 基準（最近 5 次，不含 queue、不含手動重跑）

| workflow | job | duration_sec | commit |
|---|---|---:|---|
| CI | test/full | TBD | TBD |
| CI | test/full | TBD | TBD |
| CI | test/full | TBD | TBD |
| CI | test/full | TBD | TBD |
| CI | test/full | TBD | TBD |

## 4) 後續目標映射

- SC-1：文檔入口收斂（README + CLAUDE）
- SC-2：規則重複抽離
- SC-3：token 成本下降
- SC-4：PR 回饋時間下降
- SC-5/SC-6：輸出契約與 gate 正確性
