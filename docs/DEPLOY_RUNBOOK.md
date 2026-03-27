# 生產部署 Runbook（BL-06）

## GitHub Actions

- Workflow：[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)。  
- `deploy` job 已使用 `environment: production`（**DONE-C1**）。

## 營運必做（人工閘門）

1. 在 GitHub **Settings → Environments → production** 設定 **Required reviewers**（至少一人核准才會跑 deploy secrets／步驟）。  
2. 確認 production secrets 與主線文件一致：`ENV_TEMPLATE.txt`、`README` 環境變數表。  
3. 建議在排程／Cloud Run 等執行環境設 **`PIPELINE_STRICT_ENV=1`**，強制未 `SKIP_*` 時具備 Telegram 與 BigQuery 憑證（見 `main._validate_critical_env_strict`）。

## 部署後煙測

- 管線：觀察當日是否收到 Telegram、BigQuery `market_data` 相關表是否有新列。  
- Gate：`GATE_FAILURE_BQ_LOG=1` 時檢查 [`docs/SQL/gate_failure_weekly_summary.sql`](SQL/gate_failure_weekly_summary.sql) 同邏輯之查詢是否異常飆升。

## 回滾

- 優先：**revert** 觸發 deploy 的 commit，重新跑 workflow。  
- 若僅設定錯誤：修正 Environment secrets / 變數後 **re-run** failed job。
