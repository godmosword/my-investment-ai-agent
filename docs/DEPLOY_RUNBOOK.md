# 生產部署 Runbook（BL-06）

## GitHub Actions

- Workflow：[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)。  
- `deploy` job 已使用 `environment: production`（**DONE-C1**）。
- **Deploy 併發**：[`deploy.yml`](../.github/workflows/deploy.yml) 對 `main` 使用同一 `concurrency` group 且 **`cancel-in-progress: false`**，連續 push 會**排隊**完成，不會出現前一筆 `build-and-deploy` 被新 trigger 取消（日誌 *Canceling since a higher priority waiting request*）。
- **Cloud Run Job `task-timeout`**：`deploy.yml` 內 `gcloud run jobs deploy --task-timeout`（秒）。日報管線若出現 *Terminating task because it has reached the maximum timeout of 3600 seconds* 類訊息，代表執行超過當前上限；請提高該值（目前預設 **14400**，即 4 小時）後重新部署。亦可於 GCP Console → Cloud Run → Job → 編輯 → **Task timeout** 調整。

## 營運必做（人工閘門）

1. 在 GitHub **Settings → Environments → production** 設定 **Required reviewers**（至少一人核准才會跑 deploy secrets／步驟）。  
2. 確認 production secrets 與主線文件一致：`ENV_TEMPLATE.txt`、`README` 環境變數表。  
3. 建議在排程／Cloud Run 等執行環境設 **`PIPELINE_STRICT_ENV=1`**，強制未 `SKIP_*` 時具備 Telegram 與 BigQuery 憑證（見 `main._validate_critical_env_strict`）。
4. 新聞新鮮度：生產環境建議 **`STRICT_NEWS_FRESHNESS_GATE=1`**（必要時搭配 `NEWS_FRESHNESS_WINDOW_HOURS`／白名單）；細節見 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 與 [`docs/CRITICAL_ENV_POLICY.md`](CRITICAL_ENV_POLICY.md)。
5. **錨定報告日**（可選）：補跑／跨日邊界時設 **`PIPELINE_REPORT_DATE=YYYY-MM-DD`**，新聞新鮮度以該日 HKT 日末為參考，並注入 crew context（見 `main._run_pipeline_once`）。

## 選幣輪動（staging 實驗）

- 語意見 [`PICK_ROTATION_SEMANTICS.md`](PICK_ROTATION_SEMANTICS.md)。  
- 建議在 staging 逐步開啟 **`PICK_ROLLING_FREQ_GATE=1`** 並調 `PICK_ROLLING_WINDOW_DAYS`／`PICK_ROLLING_MAX_DISTINCT_DAYS`，搭配 BigQuery `gate_failure_log` 觀察失敗率。

## 部署後煙測

- 管線：觀察當日是否收到 Telegram、BigQuery `market_data` 相關表是否有新列。  
- Gate：`GATE_FAILURE_BQ_LOG=1` 時檢查 [`docs/SQL/gate_failure_weekly_summary.sql`](SQL/gate_failure_weekly_summary.sql) 同邏輯之查詢是否異常飆升。

## 回滾

- 優先：**revert** 觸發 deploy 的 commit，重新跑 workflow。  
- 若僅設定錯誤：修正 Environment secrets / 變數後 **re-run** failed job。
