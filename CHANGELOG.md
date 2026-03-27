# Changelog

本檔案記錄專案重要功能與行為變更。  
**工程待辦與完成度彙總**見 [`TODOS.md`](TODOS.md)；改版時請同步更新該檔對應項目狀態。

## 2026-03-28

### Added
- **[`tools_cache_http.py`](tools_cache_http.py)**：`tools.py` 拆出 in-memory cache、`_http_get`、JSON 回應解析；[`tools.py`](tools.py) 轉發 `_CACHE`／`_CACHE_MAX_SIZE`／`_get_http_session` 供測試與相容。
- **錨定報告日**：環境變數 **`PIPELINE_REPORT_DATE`** — [`main.py`](main.py) 注入 exclusion 開頭；[`report_html_gates.py`](report_html_gates.py) 新聞新鮮度以該日 HKT 日末為參考時刻。
- **工具呼叫下限**：**`MIN_TOOL_CALLS_PER_PIPELINE`** + [`scratchpad.raw_tool_invocation_count`](scratchpad.py)（每次 `traced_tool_execution` 遞增）。
- **執行摘要 Gate（可選）**：**`STRICT_EXEC_SUMMARY_HTML_GATE`** — 正文須含【執行摘要】且至少 2 條要點。
- **Telegram「查看歷史」**：**`TELEGRAM_REPORT_HISTORY_URL`** — [`telegram_sender.py`](telegram_sender.py) 首則文字 chunk 附 Inline url 按鈕。
- **Web Push API 預留**：[`api.py`](api.py) `POST /api/push/subscribe`（預設 501；**`WEB_PUSH_ENABLED=1`** 時 200 noop）；CORS 允許 POST。
- **週期回測 workflow**：[`.github/workflows/weekly-backtest.yml`](.github/workflows/weekly-backtest.yml)（手動；`backtest.py --optimize --write-signal-weights`，需 `GCP_SA_KEY`）。
- **測試**：[test_api_push.py](test_api_push.py)、[`test_validate_report.py`](test_validate_report.py) `TestStrictExecSummaryHtmlGate`。

### Changed
- **Gate 模組拆分**：[`report_html_gates.py`](report_html_gates.py) 承接原 `validate_report()`（HTML／環境變數／BigQuery）；結構化業務規則與 `ReportOutput`／`parse_report_output`／`assert_*` 收斂至 [`schemas.py`](schemas.py)（`DailyBriefReport` `@model_validator`）。已移除舊檔 `report_validator.py`、`report_output_validator.py`、`core/report_validation.py`、`check_report.py`。
- **[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml)**：關閉 **`schedule` cron**（預設不再每 2 小時自動跑），僅保留 **`workflow_dispatch`**；要恢復排程可取消 YAML 內註解。[`README.md`](README.md) 表格已對齊。
- **[`TODOS.md`](TODOS.md)**：勾選與「已落地」對齊現況；新增 **階段 E** 長期索引（對 [`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)）。
- **[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)**：`PIPELINE_REPORT_DATE`、選幣輪動 staging 小節。
- **[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)**：鏈上 Tab／QSREC 頻率、`/api/push/subscribe`。
- **[`docs/PHASE_F_BACKLOG.md`](docs/PHASE_F_BACKLOG.md)**、[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`README.md`](README.md)、[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`crew.py`](crew.py)（候選多樣性一句）、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（METRIC 擴充）。
- **測試**：[`test_critical_paths.py`](test_critical_paths.py)、[`test_pipeline_observability_smoke.py`](test_pipeline_observability_smoke.py) 對齊 `_http_get`／`tools_cache_http._HTTP_SESSION`。
- **Telegram 讀者版精簡**：[`templates/telegram_report.j2`](templates/telegram_report.j2) 移除頂部 Source 三行；交易卡改四行（計畫／執行／敘事），風控與情境僅留結構化／QSREC。[`main.py`](main.py) 將 Source observability 與 Q-Score 改為僅 `logger.info`，不另發品質卡訊息；移除管線 `_maybe_editor_polish_html`（[`report_editor.py`](report_editor.py) 仍可供測試）。
- **Schema 文體與隱私**：[`schemas.py`](schemas.py) 新增 `internal_reasoning`（`TradeRecommendation`／`ExecutableTradeLeg`／`NewsItem`）、`narrative` few-shot 範例、標籤／指令洩漏清洗；[`QSREC_JSON_EXCLUDE_FIELDS`](schemas.py) 使對外 QSREC JSON 不含思考區；[`report_render.py`](report_render.py) 對齊 `model_dump` exclude。
- **Crew**：[`crew.py`](crew.py) 新增【機構級寫作｜Bloomberg 式】與【思考區 vs 展示區】；刪除未使用 `_POLISH_RULE`；幣圈 risk 任務 `expected_output` 對齊辯論結尾格式。

## 2026-03-27

### Changed
- **[`TODOS.md`](TODOS.md)**：pull 後重整——合併三大戰略方向與週次建議、**維護者執行意見**、**選幣／選股過於固定**橫切診斷與待辦；校正已落地項（`gate_failure_log`、`HIT_STOP` exclusion、`oss_scout` 腳本等）避免重複開票。
- **GitHub Actions runner 磁碟**：[`ci.yml`](.github/workflows/ci.yml)、[`deploy.yml`](.github/workflows/deploy.yml)、[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 於重步驟前執行 **Free disk space**（移除預裝 dotnet／android／CodeQL 等）；CI／monitor 的 `pip install` 改 **`--no-cache-dir`** 降低峰值；deploy 在 `docker push` 後 **`docker builder prune` / `system prune`**。緩解 `No space left on device` 與 runner 無法寫 `_diag` log。
- **GitHub Actions 分鐘數**：[`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) 改為每 **2** 小時排程、`pip install -r` [`requirements-monitor.txt`](requirements-monitor.txt)（僅 yfinance／BQ／Telegram，略過 CrewAI 全量依賴）；新增 `concurrency` 避免重疊 run；runner 對齊 `ubuntu-22.04`。

## 2026-03-26

### Added
- **啟動硬擋 `PIPELINE_STRICT_ENV`**：[`main._validate_critical_env_strict`](main.py) — `1` 且未 `SKIP_TELEGRAM`／`SKIP_BIGQUERY` 時分別要求 Telegram 與 GCP 專案＋憑證；[`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)、[`README`](README.md) 已註記。`NEWS_FRESHNESS_WINDOW_HOURS` 納入 [`_validate_env_types`](main.py) 數字校驗。
- **新聞新鮮度專項測試**：[`test_news_freshness.py`](test_news_freshness.py)；[`test_critical_paths.py`](test_critical_paths.py) 補 `_validate_critical_env_strict` 與錯誤 `NEWS_FRESHNESS_WINDOW_HOURS`。
- **Autoresearch／bench／營運文件**：[`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh)（尾端官方 `METRIC` 行 + 防偽註解）、[`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)、[`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)、[`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。
- **Backlog 規格補齊**：[`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md)、[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md)、[`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md)；Scout 輔助腳本 [`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py)（`GITHUB_TOKEN` 可選）。
- **Gate 失敗結構化日誌（自我改善資料基底）**：[`bigquery_writer.write_gate_failure_log`](bigquery_writer.py) 寫入 `{PROJECT}.market_data.gate_failure_log`（attempt、blocking/warning 計數、`bucket_counts_json`、`fingerprint`、`issues_preview` 等）；[`main.py`](main.py) 於 `run_pipeline_with_retries` 內每次 `validate_report` 有 `issues` 時呼叫。環境變數 **`GATE_FAILURE_BQ_LOG`**（預設開）、`SKIP_BIGQUERY=1` 時略過。測試：[`test_gate_failure_log.py`](test_gate_failure_log.py)。

### Changed
- **[`README.md`](README.md)**：重寫為較易掃描結構（開頭需求對照表、更新 mermaid、模組表含 editor／gate log／signal_weights／company crew、環境變數與觀測摘錄、`GATE_FAILURE_BQ_LOG`、輔助腳本與分組文件索引）；主線不依賴 X 與 `.cursorrules` 對齊。
- **`_check_news_freshness` 白名單行比對**：同時辨識 `YYYY-MM-DD HH:MM`／`YYYY/MM/DD`／`MM/DD` 等行內時間格式，避免戰報用 ISO 日期時 `NEWS_FRESHNESS_SOURCE_WHITELIST` 永不命中（[`report_html_gates.py`](report_html_gates.py)）。
- **Crew 管線**：自加密／AI 研究員 Agent 移除 `x_search_tool` 與相關 task 指令；與 [`.cursorrules`](.cursorrules)「廢棄 X/Twitter」一致，並減少每輪工具 schema 與 prompt token。
- **`main._prewarm_tool_caches`**：不再預熱 X 搜尋；啟動預熱並行數減 2。
- **`report_editor`**：精簡 system／user 指令字數，紅線與主編角色不變，降低潤稿 API 輸入 token。

### Removed
- **`_log_api_key_inventory`**：`TWITTER_BEARER_TOKEN` 列（管線不再使用；`tools.x_search_tool` 仍可供手動呼叫）。

## 2026-03-25

### Changed
- **[`TODOS.md`](TODOS.md)**：重整為全 repo 唯一待辦彙總——區分「已完成並驗證」「Backlog（BL-01…）」「ROADMAP 完成度矩陣」及靜態 repo 掃描紀錄；合併原條目、Autoresearch 計劃缺口與路線圖延伸項。

## 2026-03-21

### Fixed
- **`validate_report` / Gate**：新聞時區比對前剥除新聞行上 `<code>` 等行內 HTML，並接受 **HKT／香港時間** 等寫法；宏觀 **SOFR** 列若 SOFR 與匹配之 `%` 之間出現 **VIX／恐慌指數** 敘述則略過（避免將 VIX% 誤判為利率）；**美債** 行支援 **無冒號** 的 `10Y 報 x%` 格式；傳聞可信度增列 **信賴度／呢喃…可信度／置信分級／來源：…(B級)** 等模式。
- **戰報內容／版面**：後處理 **`_auto_prefix_missing_news_tags`** 對【核心新聞】之 `[日期 時間 UTC+8]` 行與【AI 產業新聞】之「標題 + 摘要：」自動補 **〔新聞 N〕**，避免計數永遠不足 6 則；**無 BigQuery 上期資料時仍剥除** LLM 捏造之【上期建議追蹤】；**`load_previous_recs_block`** 改為 `report_date + canon_asset + direction` 去重（同標的同向多筆只留一列）。

### Added
- **選幣／選股理由驗證**：`validate_report` 檢查加密與美股區「本日選擇理由」是否含足夠關鍵線索（催化/鏈上 vs 財報/新聞等）或退階說明，並是否點名 QSREC 內該類所有標的。交易觀望時略過；`STRICT_PICK_JUSTIFICATION=0` 關閉。
- **選幣／選股與昨日輪動**（`STRICT_PICK_ROTATION`，預設開）：若今日 QSREC 與昨日 BQ `RECOMMENDATIONS_TABLE` 之 **canonical 標的集合**完全相同且非空，理由須含 **重複選用理由** 等片語，否則驗證失敗；無 BQ／昨日無資料／查詢失敗則略過。`crew.py` 動態選幣／選股段落已註明此行為。
- **新聞 Gate 分級**：`validate_report` 將 **交易觀望**（`trade_watch_mode`）與 **新聞資料不足分段**（`partial_news_ok`）解耦；後者須 3~5 則〔新聞 N〕、〔新聞 1~3〕齊備、UTC+8 全過、且文內宣告不補虛構 + 【新聞資料狀態】或 `[REPORT_TIER:PARTIAL_NEWS]`（後處理在 3~5 則時自動注入）。環境變數 **`ALLOW_PARTIAL_NEWS_GATE`**（預設 `1`）可關閉分段。僅 **觀望模式** 等才放寬 R:R／勝率／投資解讀量化；僅分段不再因「出現新聞資料狀態」就放寬交易欄位。

### Changed
- **`tracker`**：`check_and_update_positions` 與 `load_previous_recs_block` 對多筆建議 **合併 Yahoo symbol 後批次 `yf.download`**，仍缺價之 symbol 再單檔 fallback，降低追蹤價格時的 HTTP 次數與限流風險。
- **`config.py` / `crew.py`**：LiteLLM 模型字串集中於 `config`（`MODEL_GROK`、`MODEL_GPT`、`MODEL_GEMINI`、`MODEL_CLAUDE`），可依環境變數覆寫；`OPENAI_MODEL` 仍為 GPT 慣用別名（優先於 `MODEL_GPT`）。
- **上期建議追蹤**：BigQuery 以 **canonical asset**（`$`/空白/`-` 正規化）做 `PARTITION BY`；`save_recommendations` 同日同標的只保留最後一筆；合併戰報後 **`main._inject_canonical_prev_recs_block`** 以 BQ 權威 HTML **覆寫** LLM 產出之【上期建議追蹤】，避免模型自行膨脹多列。
- **`validate_report`（STRICT_CONSISTENCY_GATE）**：宏觀異常僅在含 **美債** 之行解析 10Y/2Y；**SOFR** 僅解析關鍵字鄰近之利率 **%**（避免同列 VIX／敘事 % 誤判）。新聞時區接受 **GMT+8、全形加號、MM/DD/YYYY、可選秒數**，並在 **`【新聞資料狀態】` 行起**截斷後再比對〔新聞〕；計數前仍剔除【新聞資料狀態】等噪音行。傳聞可信度接受 **來源：B級**、**`可信度 72/100`**、**`等級：B`**、**`Grade: B`** 等。`_normalize_news_timezone_utc8` 與新聞時區規則對齊。
- **`crew`**：配對比值 LONG 與建倉敘事一致；AI 區強制〔新聞 4〕～〔新聞 6〕+ UTC+8；產業鏈呢喃需含可信度；加密區註明上期區塊後端可覆寫。

## 2026-03-20

### Changed
- **上期建議追蹤**（`tracker.load_previous_recs_block`）：同一 `report_date + asset` 以 `ROW_NUMBER` 去重，優先 `OPEN`、否則最新 `created_at`，避免同日多筆 QSREC 造成同標的多空重複列。
- **`validate_report`**：要求全篇至少 6 個 `〔新聞 N〕`；主 regime 為 neutral/risk_on 時禁止交易／風險預算段誤用「依 risk_off」等敘述；AI 儀表板區掃描常見幻覺欄位字串；美債 10Y/2Y 與「利差 %」口徑一致性檢查（約 10Y−2Y）。
- **後處理**：若注入後仍缺任一 `SourceHealth`/`SourceErrors`/`SourceQuota`，會再清一次殘行並重新注入完整區塊。
- **`crew`**：新聞強制 `〔新聞 1〕`…`〔新聞 6〕`（AI 區為 4–6）；AI 儀表板禁字清單加強；倉位示例避免 neutral 時寫「risk_off」。

## 2026-03-15

### Changed（GitHub Actions）
- **CI**（`ci.yml`）：`pull_request` 仍全跑；`push main` 僅在 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow 等路徑變更時跑 Lint+Test。
- **部署**（`deploy.yml`）：**移除** `push` 自動觸發，改為僅 **`workflow_dispatch`**（Actions → Run workflow）；執行時仍先 `workflow_call` `ci.yml` 再建映像與 Cloud Run Job 部署。
- `README.md`：同步說明「push 不自動部署、手動 Deploy workflow」。

## 2026-03-08

### Added
- 新增來源可觀測欄位：`SourceHealth`、`SourceErrors`、`SourceQuota`，並納入報告後處理與驗證規則。
- 新增來源健康分數機制（NewsAPI/GNews/Apify），支援 7 天半衰期，讓來源排序偏向近期穩定表現。
- 新增來源錯誤分類統計：`429`、`400`、`timeout`、`5xx`、`other`。
- 新增來源配額控管與成本保護：可設定每日上限，且依健康分數動態收斂可用配額。

### Changed
- `market_search_tool` 由固定 fallback 順序改為「健康分數驅動的動態來源優先序」。
- 報告 resilience 後處理強化：若缺少來源可觀測欄位，會自動注入固定區塊。
- `README.md` 更新為目前 agent 模型、工具組合、資料源策略與新環境變數。

### Persistence
- 來源健康狀態持久化升級：
  - 本地：`.source_health.json`
  - 雲端：BigQuery `source_health_stats`（可透過 `DISABLE_SOURCE_HEALTH_BQ=1` 關閉）

### Validation
- 已完成語法檢查、既有單元測試與 lint 檢查，未引入新錯誤。
