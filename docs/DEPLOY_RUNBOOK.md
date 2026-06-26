# 生產部署 Runbook（BL-06）

## GitHub Actions

- Workflow：[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml)。  
- **`push` 觸發條件**：workflow 設有 **`paths`** 篩選（`*.py`、`Dockerfile`、`requirements*.txt` 等）；**僅 Markdown／計畫文件等變更 push 到 `main` 不會啟動**本 workflow（省 Actions 分鐘、避免無需重建映像）。仍要上線時：Repo → **Actions** → **Deploy — Cloud Run Job** → **Run workflow**（`workflow_dispatch`；仍會先跑可重用的 `ci.yml`）。
- `deploy` job 已使用 `environment: production`（**DONE-C1**）。
- **Deploy 併發**：[`deploy.yml`](../.github/workflows/deploy.yml) 對 `main` 使用 **`concurrency.cancel-in-progress: true`**：較新的 push 會取消進行中的 deploy，只跑**最後一次**完整流程，節省 Actions 分鐘（與 CHANGELOG 2026-03-30 一致）。若需「排隊全跑完」可改回 `cancel-in-progress: false`。
- **Runner 磁碟**：deploy job 內「Free disk space」預設 **`if: false`** 以縮短數分鐘；若 Docker build 因磁碟滿失敗，暫改該步驟為 `if: true` 後重跑 workflow。
- **Cloud Run Job `task-timeout`**：`deploy.yml` 內 `gcloud run jobs deploy --task-timeout`（秒）。日報管線若出現 *Terminating task because it has reached the maximum timeout of 3600 seconds* 類訊息，代表執行超過當前上限；請提高該值（目前預設 **14400**，即 4 小時）後重新部署。亦可於 GCP Console → Cloud Run → Job → 編輯 → **Task timeout** 調整。

## 營運必做（人工閘門）

1. 在 GitHub **Settings → Environments → `production`** 啟用 **Deployment protection rules** 裡的 **Required reviewers**（至少一名 reviewer），`build-and-deploy` job 才會在取用該環境的 secrets／variables 前**暫停並等待核准**。  
   - **常見誤解**：僅在 **Environment variables**（或 Secrets）填值**不會**自動啟用人審；若未勾選 **Required reviewers**，workflow 會**直接繼續跑**，不會出現核准畫面。  
   - **路徑**：Repo → **Settings** → **Environments** → 點 **production** → **Deployment protection rules** → 勾選 **Required reviewers** → 加入使用者或團隊 → **Save protection rules**。  
   - **組織倉庫**：若畫面上無法勾選，可能是 Org 層級停用或需 Org 管理員核准 **Environments** 政策。  
2. 確認 production secrets 與主線文件一致：`ENV_TEMPLATE.txt`、`README` 環境變數表。  
3. 建議在排程／Cloud Run 等執行環境設 **`PIPELINE_STRICT_ENV=1`**，強制未 `SKIP_*` 時具備 Telegram 與 BigQuery 憑證（見 `main._validate_critical_env_strict`）。
4. 新聞新鮮度：生產環境建議 **`STRICT_NEWS_FRESHNESS_GATE=1`**（必要時搭配 `NEWS_FRESHNESS_WINDOW_HOURS`／白名單）；細節見 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt) 與 [`docs/CRITICAL_ENV_POLICY.md`](CRITICAL_ENV_POLICY.md)。
5. **錨定報告日**（可選）：補跑／跨日邊界時設 **`PIPELINE_REPORT_DATE=YYYY-MM-DD`**，新聞新鮮度以該日 HKT 日末為參考，並注入 crew context（見 `main._run_pipeline_once`）。
6. **LangGraph 路徑**（可選）：`USE_LANGGRAPH_ENGINE=1` 時走 `graph/` 狀態機（見 `main.py`、`ENV_TEMPLATE.txt`）。**GitHub Actions → Cloud Run**：在 **Settings → Environments → `production` → Environment variables** 新增 **`USE_LANGGRAPH_ENGINE`** = **`1`**（未設則 deploy 寫入 **`0`**）；重新跑一次 **Deploy — Cloud Run Job** 後 Job 即帶該變數。亦可只在 **GCP Console → Cloud Run → Job → 編輯 → 變數** 手動新增（下次若 deploy 未帶 `--update-env-vars` 可能被覆寫；以本 repo 的 [`deploy.yml`](../.github/workflows/deploy.yml) 為準時，以 GitHub `production` 變數控制最一致）。回滾 CrewAI 主路徑：變數改 **`0`** 或刪除後將 deploy 預設寫回 0。

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
- **日報 `profile` 欄（Phase 4c／4d）**：`llm_run_log` 與 `gate_failure_log` 寫入含 **`profile`**（對齊 `REPORT_PROFILE`／`validate_report`）。若表為舊 schema 且尚未被管線 `update_table` 補欄，請於 BQ 執行 [`docs/SQL/bq_brief_profile_columns.sql`](SQL/bq_brief_profile_columns.sql) 之 `ALTER TABLE … ADD COLUMN profile STRING`（duplicate column 可略過）。

## Options Flow + GEX 上線

Options 是可選資料源。若 Secret Manager 尚未建立 `POLYGON_API_KEY`，deploy workflow 會略過掛載並輸出 warning；Portal 的 `/insights?tab=options` 會顯示 pending 卡，不阻塞主日報部署。

啟用 live 資料時，依序完成：

```bash
gcloud secrets create POLYGON_API_KEY --replication-policy=automatic
printf '%s' "$POLYGON_API_KEY" | gcloud secrets versions add POLYGON_API_KEY --data-file=-
bq query --use_legacy_sql=false < docs/SQL/options_snapshots.sql
bq query --use_legacy_sql=false < docs/SQL/options_unusual_trades.sql
bq query --use_legacy_sql=false < docs/SQL/options_gex_history.sql
bq query --use_legacy_sql=false < docs/SQL/options_gex_by_strike.sql
```

接著在 Cloud Run Job/GitHub production variables 設：

```bash
OPTIONS_SNAPSHOTS_TABLE=PROJECT.market_data.options_snapshots
OPTIONS_UNUSUAL_TRADES_TABLE=PROJECT.market_data.options_unusual_trades
OPTIONS_GEX_HISTORY_TABLE=PROJECT.market_data.options_gex_history
OPTIONS_GEX_BY_STRIKE_TABLE=PROJECT.market_data.options_gex_by_strike
```

最後手動或排程執行 `scripts/options_flow_tick.py`，確認 `/api/options/summary` 從 `enabled:false` 轉為 `enabled:true` 且 `items` 有資料。

## Portfolio / Track Record 資料源

Portfolio 預設使用 JSONL（`PORTFOLIO_HOLDINGS_FILE`），適合本機與 staging。若要改用 BigQuery，先建立 [`docs/SQL/portfolio_holdings.sql`](SQL/portfolio_holdings.sql)，再設：

```bash
PORTFOLIO_STORE_BACKEND=bigquery
PORTFOLIO_HOLDINGS_TABLE=PROJECT.market_data.portfolio_holdings
```

若 backend 設為 `bigquery` 但未設 `PORTFOLIO_HOLDINGS_TABLE`，`/api/portfolio` 會回 pending envelope，寫入 routes 會回 503，不會落回不明資料源。

Track Record 讀取順序為：`RECOMMENDATION_OUTCOMES_TABLE` 有資料時使用 BigQuery；否則回退 `EXECUTION_INTENT_STORE` JSONL。BigQuery schema 見 [`docs/SQL/recommendation_outcomes.sql`](SQL/recommendation_outcomes.sql)。

## 回滾

- 優先：**revert** 觸發 deploy 的 commit，重新跑 workflow。  
- 若僅設定錯誤：修正 Environment secrets / 變數後 **re-run** failed job。
