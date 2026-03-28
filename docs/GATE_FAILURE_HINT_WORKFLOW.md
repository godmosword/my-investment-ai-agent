# Gate 失敗 → 提示草稿（人審流程）

對齊 [`TODOS.md`](../TODOS.md) P3「Gate 失敗 → 提示注入」；**嚴禁**未經人審自動改 [`crew.py`](../crew.py) prompt。

## 步驟

1. 從 BigQuery `gate_failure_log`（或本機 artifact）匯出近 7–14 日 `top_issues`／`gate_code` 聚合；範例見 [`docs/SQL/gate_failure_weekly_summary.sql`](SQL/gate_failure_weekly_summary.sql)。
2. 將**高頻 issue 文字**（去識別後）貼入內部文件或 LLM，產出「避免模式」**草稿**（bullet：不要再用哪些句式／要補哪些欄位）。
3. **人類審核**後，再手動更新 crew task 文字或 `validation_rules`／`report_html_gates` 註解。
4. 可選：在 PR 描述附「對照哪幾筆 gate_failure 樣本」，便於回溯。

## 自動化邊界

可寫排程只做到 **SQL → CSV／Slack 摘要**；**不要**讓排程直接改 repo 內 prompt。
