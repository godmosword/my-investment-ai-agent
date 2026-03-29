# 生產部署 Runbook（BL-06）

## GitHub Actions

- Workflow：[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)。  
- `deploy` job 已使用 `environment: production`（**DONE-C1**）。
- **Deploy 併發**：[`deploy.yml`](../.github/workflows/deploy.yml) 對 `main` 使用 **`concurrency.cancel-in-progress: true`**：較新的 push 會取消進行中的 deploy，只跑**最後一次**完整流程，節省 Actions 分鐘（與 CHANGELOG 2026-03-30 一致）。若需「排隊全跑完」可改回 `cancel-in-progress: false`。
- **Runner 磁碟**：deploy job 內「Free disk space」預設 **`if: false`** 以縮短數分鐘；若 Docker build 因磁碟滿失敗，暫改該步驟為 `if: true` 後重跑 workflow。
- **Cloud Run Job `task-timeout`**：`deploy.yml` 內 `gcloud run jobs deploy --task-timeout`（秒）。日報管線若出現 *Terminating task because it has reached the maximum timeout of 3600 seconds* 類訊息，代表執行超過當前上限；請提高該值（目前預設 **14400**，即 4 小時）後重新部署。亦可於 GCP Console → Cloud Run → Job → 編輯 → **Task timeout** 調整。

## 營運必做（人工閘門）

1. 在 GitHub **Settings → Environments → production** 設定 **Required reviewers**（至少一人核准才會跑 deploy secrets／步驟）。  
2. 確認 production secrets 與主線文件一致：`ENV_TEMPLATE.txt`、`README` 環境變數表。  
3. 建議在排程／Cloud Run 等執行環境設 **`PIPELINE_STRICT_ENV=1`**，強制未 `SKIP_*` 時具備 Telegram 與 BigQuery 憑證（見 `main._validate_critical_env_strict`）。
4. 新聞新鮮度：生產環境建議 **`STRICT_NEWS_FRESHNESS_GATE=1`**（必要時搭配 `NEWS_FRESHNESS_WINDOW_HOURS`／白名單）；細節見 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 與 [`docs/CRITICAL_ENV_POLICY.md`](CRITICAL_ENV_POLICY.md)。
5. **錨定報告日**（可選）：補跑／跨日邊界時設 **`PIPELINE_REPORT_DATE=YYYY-MM-DD`**，新聞新鮮度以該日 HKT 日末為參考，並注入 crew context（見 `main._run_pipeline_once`）。

## LLM 成本與延遲（Secret／環境變數）

對照 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)「省 LLM token／延遲」專節。生產常用槓桿：

- **維持關閉**（預設即可）：`REPORT_LLM_JUDGE`、`EDITOR_AGENT_ENABLED`、`COMPANY_CREW_ENABLED`。
- **可選省一輪工具链**：`PIPELINE_SKIP_SENTIMENT_SCORE=1`（加密段不呼叫 `sentiment_score_tool`；情緒改由 fear_greed 與新聞語意綜述）。
- **降費**：以 `MODEL_GROK`／`MODEL_GEMINI` 等改較便宜、仍通過 Gate 的模型 ID（須 A/B 觀察失敗率與戰報品質）。
- **勿預設**：`CREW_DISABLE_ASYNC_RESEARCH=1` 不當成省錢開關；總 token 未必下降。

## 選幣輪動（staging 實驗）

- 語意見 [`PICK_ROTATION_SEMANTICS.md`](PICK_ROTATION_SEMANTICS.md)。  
- 建議在 staging 逐步開啟 **`PICK_ROLLING_FREQ_GATE=1`** 並調 `PICK_ROLLING_WINDOW_DAYS`／`PICK_ROLLING_MAX_DISTINCT_DAYS`，搭配 BigQuery `gate_failure_log` 觀察失敗率。

## 部署後煙測

- 管線：觀察當日是否收到 Telegram、BigQuery `market_data` 相關表是否有新列。  
- Gate：`GATE_FAILURE_BQ_LOG=1` 時檢查 [`docs/SQL/gate_failure_weekly_summary.sql`](SQL/gate_failure_weekly_summary.sql) 同邏輯之查詢是否異常飆升。

## 回滾

- 優先：**revert** 觸發 deploy 的 commit，重新跑 workflow。  
- 若僅設定錯誤：修正 Environment secrets / 變數後 **re-run** failed job。
