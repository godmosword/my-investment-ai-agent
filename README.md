# Q-Silicon Institutional Research AI Agent

機構級 **日報管線**：**Python + CrewAI + LiteLLM** 並行產出 **加密市場** 與 **前沿 AI（含美股基本面）** 研究 → **規則 Gate** → 可選 **潤稿／LLM 評分** → **Telegram HTML**；指標與日誌寫入 **BigQuery**；**Streamlit** 與 **PWA** 呈現戰情室。

| 你需要 | 說明 |
|--------|------|
| 跑完整管線 | 多組 LLM + 資料 API 金鑰（見下方「必填」）；單次約 **15–30+ 分鐘** |
| 本機乾跑 | `SKIP_TELEGRAM=1 SKIP_BIGQUERY=1` 仍須 **四個必填金鑰**（LLM + Apify） |
| 只看儀表板 | `streamlit run dashboard.py` — **可不設金鑰**（BQ 區塊降級） |

**紅線**：可驗證的價格、技術與宏觀數字須由 **工具層** 取得並注入 Context；LLM **不得捏造**客觀數據。日報主線 **不依賴 X/Twitter**（`.cursorrules`）。Telegram 僅允許白名單 HTML — 見 [`.cursorrules`](.cursorrules)、[`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)。

**索引**：[`TODOS.md`](TODOS.md)（待辦與 Backlog） · [`CHANGELOG.md`](CHANGELOG.md) · [`CLAUDE.md`](CLAUDE.md)（開發者導覽） · [`AGENTS.md`](AGENTS.md)（雲端／CoinGlass 備忘） · [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)（完整環境變數）

---

## 目次

1. [快速開始](#快速開始)  
2. [架構概覽](#架構概覽)  
3. [核心模組](#核心模組)  
4. [Agent 與模型](#agent-與模型)  
5. [環境變數](#環境變數)  
6. [驗證、Gate 與觀測](#驗證gate-與觀測)  
7. [開發與測試](#開發與測試)  
8. [目錄結構](#目錄結構)  
9. [Docker](#docker)  
10. [CI／Deploy](#cideploygithub-actions)  
11. [資料流](#資料流)  
12. [輔助腳本](#輔助腳本)  
13. [文件索引](#文件索引)  
14. [CoinGlass API v4](#coinglass-api-v4)  
15. [安全與維運](#安全與維運)  
16. [War Room PWA 與 API](#war-room-pwa-與-api)  
17. [gstack（選用）](#gstack選用)  

---

## 快速開始

```bash
pip install -r requirements.txt
cp ENV_TEMPLATE.txt .env   # 編輯填入金鑰
python main.py
```

| 情境 | 指令 |
|------|------|
| 乾跑（不推 Telegram、不寫 BQ） | `SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py` |
| 生產式啟動檢查 | `PIPELINE_STRICT_ENV=1` — 未 `SKIP_*` 時強制 Telegram／GCP 憑證齊備 |
| 除錯 | `LOG_LEVEL=DEBUG CREW_VERBOSE=1 python main.py` |
| 雙軌比對 | `REPORT_COMPARE_MODE=1 python main.py` → [`docs/REPORT_COMPARE_STAGING.md`](docs/REPORT_COMPARE_STAGING.md) |

**Streamlit 戰情室**

```bash
streamlit run dashboard.py --server.port 8501 --server.headless true
```

**Python**：Dockerfile 為 3.11-slim；本機 3.12 通常可運行。專案為**根目錄扁平** Python 腳本集合，無 `pyproject.toml`。

---

## 架構概覽

```mermaid
flowchart TB
  subgraph pre [啟動]
    Keys[必填金鑰檢查]
    Strict[可選 PIPELINE_STRICT_ENV]
    Types[數字型 env 校驗]
    Prewarm[並行 prewarm 工具快取]
  end
  subgraph crews [CrewAI 雙線程]
    Crypto[CryptoResearchCrew]
    AI[AIResearchCrew]
  end
  subgraph post [後段]
    Asm[assemble + render HTML]
    Ed[可選 EDITOR_AGENT]
    Val[validate_report / structured]
    Judge[可選 judge]
    Out[Telegram / BQ / scratchpad]
  end
  Keys --> Strict --> Types --> Prewarm
  Prewarm --> Crypto
  Prewarm --> AI
  Crypto --> Asm
  AI --> Asm
  Asm --> Ed --> Val --> Judge --> Out
```

---

## 核心模組

| 模組 | 職責 |
|------|------|
| [`main.py`](main.py) | 啟動檢查、prewarm、雙 Crew、`run_pipeline_with_retries`、Telegram、BQ、圖表 |
| [`crew.py`](crew.py) | 兩段 Crew、Agent/Task、LiteLLM fallback 鏈 |
| [`tools.py`](tools.py) | 搜尋、新聞、CoinGlass、鏈上、宏觀、Financial Datasets、量化等；快取與 traced 呼叫 |
| [`api_schema.py`](api_schema.py) | 工具 JSON 結構防呆 |
| [`schemas.py`](schemas.py) | `DailyBriefReport`、QSREC 等 Pydantic |
| [`report_render.py`](report_render.py) | 組裝與 Telegram HTML 渲染 |
| [`report_validator.py`](report_validator.py) | Gate：新聞、UTC+8、可選新鮮度、QSREC、輪動、一致性等 |
| [`report_editor.py`](report_editor.py) | 可選潤稿（`EDITOR_AGENT_ENABLED`） |
| [`report_judge.py`](report_judge.py) | 硬規則審核；可選 `REPORT_LLM_JUDGE` |
| [`scratchpad.py`](scratchpad.py) | Run 級 JSONL、工具上限／重複偵測 |
| [`telegram_sender.py`](telegram_sender.py) | HTML 清洗、分段推送、Gate 告警 |
| [`bigquery_writer.py`](bigquery_writer.py) | 指標、LLM run log、exclusion context、**`write_gate_failure_log`** |
| [`tracker.py`](tracker.py) | 持倉與上期建議 |
| [`signal_weights_store.py`](signal_weights_store.py) | ML 權重版本化；可選注入 context（`WEIGHTS_CONTEXT_ENABLED`） |
| [`crew_company.py`](crew_company.py) | 公司 Growth 敘事試點（`COMPANY_CREW_ENABLED`） |
| [`company_ops_schemas.py`](company_ops_schemas.py) | 公司戰情 Pydantic |
| [`dashboard.py`](dashboard.py) | Streamlit 戰情室 |
| [`api.py`](api.py) | FastAPI — PWA／戰情室資料 |
| [`monitor_intraday.py`](monitor_intraday.py) | 盤中監控（workflow 見 `.github`） |

---

## Agent 與模型

模型 ID 與表名在 [`config.py`](config.py)；覆寫見 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt)。兩段 Crew 皆為 **研究員 → 風險／辯論 → 策略主編**。

**CryptoResearchCrew**

| 角色 | LLM 槽 | env | API Key |
|------|--------|-----|---------|
| 加密研究員 | Grok（fallback 鏈） | `MODEL_GROK` | `XAI_API_KEY` |
| 風險審計 | Gemini | `MODEL_GEMINI` | `GEMINI_API_KEY` |
| 策略主編 | Gemini | `MODEL_GEMINI` | `GEMINI_API_KEY` |

**AIResearchCrew**

| 角色 | LLM 槽 | env | API Key |
|------|--------|-----|---------|
| AI 研究員 | Grok | `MODEL_GROK` | `XAI_API_KEY` |
| 市場辯論 | Gemini | `MODEL_GEMINI` | `GEMINI_API_KEY` |
| 策略主編 | Gemini | `MODEL_GEMINI` | `GEMINI_API_KEY` |

**備援**：`crew.py` 的 `_FALLBACK_CHAINS`；`ANTHROPIC_API_KEY` 啟用 Claude；凌晨降級可將兩槽改為 GPT（`MODEL_GPT` / `OPENAI_API_KEY`）。  
**其他呼叫**：情緒分數工具；`REPORT_LLM_JUDGE` 使用 OpenAI 等 — 見 `ENV_TEMPLATE`。  
**費用**：[`docs/COST_PER_MODEL.md`](docs/COST_PER_MODEL.md)

---

## 環境變數

### 啟動必填（缺則 `RuntimeError`）

`XAI_API_KEY`、`OPENAI_API_KEY`、`GEMINI_API_KEY`、`APIFY_API_TOKEN`。

### 選填類別（摘錄）

| 類別 | 代表變數 |
|------|-----------|
| LLM 備援 | `ANTHROPIC_API_KEY`、`OPENROUTER_API_KEY` |
| 新聞／搜尋 | `NEWSAPI_KEY`、`GNEWS_API_KEY`、`TAVILY_API_KEY` |
| 舊版 X 相關 | `TWITTER_BEARER_TOKEN` 等 — **管線主線不使用**；僅工具層遺留／手動情境 |
| 市場／鏈上 | `COINGLASS_API_KEY`、`CRYPTOPANIC_API_KEY`、`CRYPTOQUANT_API_KEY`、`FRED_API_KEY`、`GLASSNODE_API_KEY` |
| AI 基本面 | `FINANCIAL_DATASETS_API_KEY` |
| 推送／雲端 | `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`、`GCP_PROJECT_ID`、`GCP_SA_KEY` 或 `GOOGLE_APPLICATION_CREDENTIALS` |

**完整註解**以 [`ENV_TEMPLATE.txt`](ENV_TEMPLATE.txt) 為準。

### 管線、Gate、觀測（摘錄）

| 變數 | 說明 |
|------|------|
| `PIPELINE_STRICT_ENV` | `1` 時：未 skip 則硬擋 Telegram／GCP 憑證 |
| `SKIP_TELEGRAM` / `SKIP_BIGQUERY` | 乾跑常用 |
| `MAX_REPORT_RETRIES` | Gate 失敗重試（預設 2） |
| `CREW_FUTURE_TIMEOUT_SEC` | 雙 Crew 逾時（預設 2700） |
| `SCRATCHPAD_ENABLED` | JSONL 軌跡 |
| `MAX_TOOL_CALLS_PER_RUN` / `REPEATED_CALL_THRESHOLD` | 防工具跑飛 |
| `ALLOW_PARTIAL_NEWS_GATE` | 3–5 則新聞分段模式（預設開） |
| `STRICT_NEWS_FRESHNESS_GATE` / `NEWS_FRESHNESS_WINDOW_HOURS` / `NEWS_FRESHNESS_SOURCE_WHITELIST` | 可選新聞新鮮度 |
| `GATE_FAILURE_ARTIFACTS` | 失敗時寫 `.qsilicon/last_gate_failure/` |
| `GATE_FAILURE_BQ_LOG` | 結構化寫入 BQ `gate_failure_log`（預設開；`SKIP_BIGQUERY=1` 略過） |
| `REPORT_LLM_JUDGE` / `REPORT_LLM_JUDGE_BLOCKING` | 可選 LLM 評分 |
| `REPORT_COMPARE_MODE` | 雙軌觀測 |
| `EDITOR_AGENT_ENABLED` | 可選潤稿 |
| `WEIGHTS_CONTEXT_ENABLED` / `COMPANY_CREW_ENABLED` | 權重 context／公司敘事試點 |

啟動會列 **API key inventory**（不落密）；`VERIFY_API_KEYS=1` 可做輕量連線探測。

---

## 驗證、Gate 與觀測

| 層級 | 內容 |
|------|------|
| `validate_report` | HTML／敘事：`〔新聞 N〕`、`UTC+8`、partial news、`trade_watch` 與交易欄位放寬邊界等 |
| `validate_structured_report` | Pydantic、QSREC、`STRICT_PICK_*` 等 |
| `report_judge` | 硬 pattern；可選 LLM judge |
| 本機 artifact | `.qsilicon/last_gate_failure/`（見 `GATE_FAILURE_ARTIFACTS`） |
| BigQuery | `write_gate_failure_log` — 分類 bucket、`fingerprint`、issues 預覽等（見 `bigquery_writer.py`） |

細節以 `report_validator.py`、`main.py`、`docs/DAILY_BRIEF_V2.md` 為準。週聚合範例 SQL → [`docs/SQL/gate_failure_weekly_summary.sql`](docs/SQL/gate_failure_weekly_summary.sql)。

---

## 開發與測試

```bash
ruff check .
python3 -m pytest -m smoke -q   # 與 PR CI 對齊
python3 -m pytest -v            # 全量（root 下 test_*.py）
./scripts/bench_autoresearch.sh # ruff + smoke，尾端官方 METRIC 行（見腳本註解）
```

**習慣**：修 bug 先寫失敗測試再改到綠（見 [`CLAUDE.md`](CLAUDE.md)）。

---

## 目錄結構

```
.
├── main.py, crew.py, tools.py, config.py, schemas.py
├── report_*.py, telegram_sender.py, bigquery_writer.py, tracker.py
├── scratchpad.py, api.py, api_schema.py, dashboard.py
├── signal_weights_store.py, crew_company.py, company_ops_schemas.py
├── monitor_intraday.py, visualizer.py, backtest.py, backfill_data.py
├── core/report_validation.py
├── scripts/              # bench_autoresearch.sh, write_ml_weights.py, inject_test_data.py, oss_scout_candidates.py
├── docs/                 # 規格、runbook、SQL、路線圖
├── templates/            # telegram_report.j2
├── data-verification-ui/ # Vite + React PWA
├── .github/workflows/    # ci, deploy, scheduler, monitor-intraday
├── Dockerfile, docker-compose.yml
├── ENV_TEMPLATE.txt, TODOS.md, CHANGELOG.md, CLAUDE.md, AGENTS.md
└── .cursor/rules/        # Cursor 專案規則
```

---

## Docker

```bash
docker build -t q-silicon-agent .
docker run --env-file .env q-silicon-agent
```

亦可使用 `docker-compose.yml`（搭配 `--env-file .env`）。

---

## CI／Deploy（GitHub Actions）

| Workflow | 觸發 | 內容 |
|----------|------|------|
| [`ci.yml`](.github/workflows/ci.yml) | PR；`workflow_call` | PR：`ruff` + `pytest -m smoke`；被 deploy 呼叫時跑完整 `pytest -v` |
| [`deploy.yml`](.github/workflows/deploy.yml) | `push main`（paths 篩選）或手動 | CI 通過後 build／push 映像、`gcloud run jobs deploy`；`environment: production` |
| [`setup-scheduler.yml`](.github/workflows/setup-scheduler.yml) | 手動 | Cloud Scheduler |
| [`monitor-intraday.yml`](.github/workflows/monitor-intraday.yml) | cron／手動 | 盤中閾值 — 見 workflow 與 `monitor_intraday.py` |

生產人工閘門與 secrets 配置 → [`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md)。Cloud Run 為 **Job**（排程／手動），非長駐 HTTP。

---

## 資料流

```
BQ 昨日摘要 / 上期 QSREC（+ 可選權重／公司敘事 context）
        ↓
雙 Crew 並行 → Pydantic 區塊
        ↓
assemble → render → [可選 editor] → validate → [judge]
        ↓
Telegram（HTML）· BQ metrics · gate_failure_log · scratchpad
        ↓
Streamlit / PWA / api.py
```

---

## 輔助腳本

| 路徑 | 說明 |
|------|------|
| [`scripts/bench_autoresearch.sh`](scripts/bench_autoresearch.sh) | Lint + smoke + `METRIC` 輸出 |
| [`scripts/write_ml_weights.py`](scripts/write_ml_weights.py) | ML 權重寫入 store |
| [`scripts/inject_test_data.py`](scripts/inject_test_data.py) | BQ 測試資料 |
| [`scripts/oss_scout_candidates.py`](scripts/oss_scout_candidates.py) | GitHub Search 候選（Scout 輔助） |
| `python backtest.py` | 回測（BQ + CoinGecko） |
| `python backfill_data.py` | 歷史指標回填 BQ |

---

## 文件索引

| 類型 | 文件 |
|------|------|
| 工程狀態 | [`TODOS.md`](TODOS.md)、[`CHANGELOG.md`](CHANGELOG.md) |
| 開發導覽 | [`CLAUDE.md`](CLAUDE.md)、[`AGENTS.md`](AGENTS.md) |
| 日報規格 | [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md) |
| 儀表／API 契約 | [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md) |
| 部署 | [`docs/DEPLOY_RUNBOOK.md`](docs/DEPLOY_RUNBOOK.md) |
| 路線／商業化 | [`docs/ROADMAP_VISION.md`](docs/ROADMAP_VISION.md)、[`docs/COMMERCE_PLAYBOOK.md`](docs/COMMERCE_PLAYBOOK.md)、[`docs/COMMERCE_NEXT_STEPS.md`](docs/COMMERCE_NEXT_STEPS.md) |
| Autoresearch | [`docs/AUTORESEARCH_LOOP.md`](docs/AUTORESEARCH_LOOP.md)、[`docs/autoresearch.plan.md`](docs/autoresearch.plan.md) |
| 工具拆分計畫 | [`docs/TOOLS_MODULARIZATION_PLAN.md`](docs/TOOLS_MODULARIZATION_PLAN.md) |
| 公司 Crew 路線 | [`docs/COMPANY_CREW_ROADMAP.md`](docs/COMPANY_CREW_ROADMAP.md) |
| 其他 | [`docs/COST_PER_MODEL.md`](docs/COST_PER_MODEL.md)、[`docs/REPORT_COMPARE_STAGING.md`](docs/REPORT_COMPARE_STAGING.md)、[`docs/oss_candidates/README.md`](docs/oss_candidates/README.md)、[`docs/MCP_ASK_USER_QUESTION.md`](docs/MCP_ASK_USER_QUESTION.md)、[`docs/ADOPTION_DEXTER_CONCEPTS.md`](docs/ADOPTION_DEXTER_CONCEPTS.md) |

---

## CoinGlass API v4

- Base：`https://open-api-v4.coinglass.com`；Header：`CG-API-KEY`
- 成功：`code` 為 `"0"` 或 `0`；`401` / `Upgrade plan` 多為訂閱不含該端點
- 部分指標有 **Binance 公開 API 備援**（`tools.py`）

本機 `curl` 自測須在**已載入金鑰的同一 shell**（範例見 [`AGENTS.md`](AGENTS.md)）。

---

## 安全與維運

- 金鑰僅經環境變數或 Secret Manager；`.env`、服務帳戶 JSON 勿提交（`.gitignore`）。
- Telegram 僅允許白名單標籤（`sanitize_telegram_html`）。
- Actions 建議 pinned 版本；容器建議非 root。

---

## War Room PWA 與 API

```
FastAPI (api.py)  ←→  BigQuery
        ↓
React PWA (data-verification-ui/)
```

**本機**：`uvicorn api:app --reload --port 8000`；前端 `cd data-verification-ui && npm install && npm run dev`（預設 proxy `/api` → `:8000`）。無 BQ 時 API 可能錯誤，UI 仍可開發。

**端點與 KPI 對齊** → [`docs/DASHBOARD_CONTRACT.md`](docs/DASHBOARD_CONTRACT.md)（含 `/api/metrics/latest`、`/api/reports/...`、`/healthz` 等）。

**生產**：`npm run build` 產 `dist/`；搭配 `CORS_ORIGINS`、`GCP_PROJECT_ID` 等。PWA 安裝：iOS「加入主畫面」、Android「安裝應用程式」。

---

## gstack（選用）

瀏覽器 QA、review、ship 等流程技能 — 見 [`AGENTS.md`](AGENTS.md)、[`gstack.md`](gstack.md)（若存在）。
