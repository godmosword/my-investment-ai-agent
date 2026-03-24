# Q-Silicon Institutional Research AI Agent

以 CrewAI 驅動的**四核 AI 投資研究智庫**，每日自動產出加密貨幣與前沿 AI 雙市場戰報，結合即時數據與多模型辯論，最終只輸出**主編共識**與儀表板，推送 Telegram、寫入 BigQuery，並由 Streamlit 戰情室呈現。

---

## 功能總覽

### 四大專職 Agent

| Agent（`crew.py` role） | 模型識別碼 | 職責 | 工具 |
|------------------------|-----------|------|------|
| 🛸 加密市場情報研究員 | `xai/grok-4-1-fast-reasoning` | 幣圈新聞（3 則）、X 推文（5 則）、宏觀/鏈上/衍生品彙整 | `market_search_tool`, `newsapi_tool`, `gnews_tool`, `rss_feed_tool`, `x_search_tool`, `coinglass_data_tool`, `onchain_metrics_tool`, `fear_greed_tool`, `etf_flow_tool`, `econ_calendar_tool`, `sentiment_score_tool` |
| 🤖 前沿 AI 市場研究員 | `openai/gpt-4o-mini`（可設 `OPENAI_MODEL` 覆寫） | AI 產業新聞、MCP/Agent 推文、模型熱度與風險敘事 | `market_search_tool`, `newsapi_tool`, `gnews_tool`, `rss_feed_tool`, `x_search_tool`, `ai_momentum_tool`, `rumor_scanner_tool` |
| 🛡️ 首席幣圈風險審計員 | `openai/gpt-4o-mini`（可設 `OPENAI_MODEL` 覆寫） | 反向辯論、regime scorecard、宏觀風險審計 | `regime_scorecard_tool`, `macro_context_tool` |
| 💎 機構策略主編 | `openai/gpt-4o-mini`（可設 `OPENAI_MODEL` 覆寫） | 整合研究成果、排版雙市場戰報、風控欄位與 QSREC 載荷定稿 | `coinglass_data_tool`, `ml_quant_tool`, `multi_timeframe_tool` |

設計原則：**背景充分辯論，報告只呈現乾淨共識與即時數據**。戰報中不顯示 Grok/GPT/Claude 個別觀點，僅保留每則新聞與推文下的 **💎 主編共識**。

### 數據來源

| 來源 | 用途 |
|------|------|
| NewsAPI / GNews / RSS / Apify | 新聞多來源 fallback（含重試、查詢降級、健康分數排序） |
| Tavily | 傳聞掃描與補充搜尋 |
| X API | 社群推文與敘事熱度 |
| CoinGlass | 未平倉、資金費率、清算、多空比、選擇權概覽（**v4 API**；部分端點依方案，失敗時見 Binance 等備援） |
| CryptoQuant | 交易所淨流入/流出、MVRV Z-Score（若訂閱支援） |
| FRED | M2；DXY 改由 Tavily 即時報價 |
| yfinance | VIX、SPY/QQQ 成交額 proxy、IBIT 報價 |
| BigQuery | 巨鯨鏈上、每日指標儲存與排除重複上下文 |

### 輸出

- **日報 V2 版面／敘事規格**：見 [`docs/DAILY_BRIEF_V2.md`](docs/DAILY_BRIEF_V2.md)（今日主敘事、AI 段風險銜接、QSREC 方向唯一、N/A 黏連修復）。
- **gstack（slash skills）**：見根目錄 [`gstack.md`](gstack.md)；Claude Code 導覽亦見 [`CLAUDE.md`](CLAUDE.md) 末段。
- **Telegram**：HTML 分段推送，retry + 純文字 fallback，僅允許白名單標籤。
- **BigQuery**：從戰報萃取 DXY、ETF 資金流、平均風險分數、MVRV Z-Score、Grok/GPT 摘要寫入 `daily_metrics`。
- **Streamlit 戰情室（v3 視覺）**：暗色漸層介面、KPI 卡片、風險 Gauge（Risk ON / Neutral / Risk OFF 三態對齊）、趨勢圖（統一 Plotly hover／圖例）、巨鯨圖、Agent 摘要。

### 穩定性

- **驗證與重試**：`validate_report()` 檢查新聞/推文數量、market_regime、儀表板關鍵字；不合格則重試（預設最多 3 次）。
- **Gate 擋報時如何除錯**：`STRICT_CONSISTENCY_GATE=1` 時不發正式戰報，但會 (1) 發 Telegram **Gate 告警**（含 `issues_count`、本機 artifacts 路徑）；(2) 預設再發 **1+ 則純文字訊息**列出 `validate_report` **完整 issues**（`GATE_ALERT_FULL_ISSUES=0` 可關閉）；(3) 寫入 **`.qsilicon/last_gate_failure/`**：`draft_report.txt`（當次草稿全文）、`issues.txt`、`validation_summary.json`（`GATE_FAILURE_ARTIFACTS=0` 可關閉；目錄可用 `GATE_FAILURE_ARTIFACT_DIR` 自訂）。
- **新聞 Gate 分級（資料不足）**：
  - **標準**：全篇 6 則 `〔新聞 1〕`…`〔新聞 6〕`（幣圈 3 + AI 3），且已標之新聞皆須 `[… UTC+8]`。
  - **新聞資料不足分段**（`partial_news_ok`）：允許 **3～5 則** 標籤新聞，但必須 **〔新聞 1〕～〔新聞 3〕** 皆存在、**UTC+8 全過**、文內有 **「資料不足保護／不補虛構新聞」** 並有 **【新聞資料狀態】**（後處理在 3～5 則時會加註 `[REPORT_TIER:PARTIAL_NEWS]`）。**不**放寬 R:R／勝率等交易欄位。
  - **交易觀望**（`trade_watch_mode`）：出現「觀望模式／暫不開新倉／暫不提供股票進出場」等才放寬 **R:R、最大回撤、勝率、Signal Score、投資解讀量化** 等檢查。
  - 環境變數 **`ALLOW_PARTIAL_NEWS_GATE=0`**：關閉分段，永遠要求 6 則新聞標籤。
- **選幣／選股理由驗證**（`STRICT_PICK_JUSTIFICATION`，預設開啟）：加密／美股區的 **「本日選擇理由」** 須達標——足夠的催化或鏈上（幣）／基本面或新聞（股）線索，或明確 **退階**（大型幣、權值、ETF）說明，且理由中須 **點名 QSREC 內該類別所有標的**（含比值兩腿）。不符時 `validate_report` 失敗並觸發重試。交易觀望模式下略過。設 **`STRICT_PICK_JUSTIFICATION=0`** 可關閉。
- **選標量化評分**（`STRICT_PICK_SCORING`，預設開啟）：QSREC 每筆必須提供 `selection_score`、`catalyst_score`、`flow_score`、`technical_score`、`risk_fit_score`、`execution_score`（皆 0~100），並提供 `alt_candidate_score` 與 `score_gap`（應等於 `selection_score-alt_candidate_score`）。缺漏或不一致將驗證失敗。
- **與昨日 QSREC 輪動**（`STRICT_PICK_ROTATION`，預設開啟）：當 BigQuery **昨日**已寫入之 QSREC，其 **canonical 標的集合**與 **今日**該類（加密／美股）**完全相同**時，需通過同標覆核：理由含 **「重複選用理由」**，且 `score_gap` 達門檻（`PICK_ROTATION_OVERRIDE_MIN_GAP`，預設 12）。設 `ALLOW_REPEAT_PICK_OVERRIDE=0` 可改為「完全禁止同標延續（強制至少換一檔/一腿）」。**SKIP_BIGQUERY**、查詢失敗或昨日無資料時 **不擋**。設 **`STRICT_PICK_ROTATION=0`** 可關閉。
- **同標延續品質錨點**：當日若走同標覆核，QSREC 至少 1 筆需同時滿足 `repeat_days <= PICK_REPEAT_DAYS_MAX`（預設 2）與 `selection_score >= PICK_REPEAT_MIN_SELECTION_SCORE`（預設 75），避免低品質連續續抱。
- **503 退避**：偵測 503/Unavailable 時指數退避重試（可配置次數與基數）。
- **LLM**：各模型 `max_retries` 3～5、`timeout` 120～180 秒。
- **來源健康分數**：`market_search_tool` 會根據 `newsapi/gnews/apify` 近期成功率動態排序來源，並採 7 天半衰期避免舊資料長期主導。
- **來源可觀測欄位**：戰報固定輸出 `SourceHealth`、`SourceErrors`、`SourceQuota`，便於監控資料品質與成本。
- **持久化策略**：來源健康狀態同時寫入本地 `.source_health.json` 與 BigQuery（可關閉）。
- **成本保護**：依健康分數動態收斂每日來源配額，並限制 Apify 使用量避免過度消耗付費額度。
- **Phase 3 雙軌驗證（觀測用）**：`REPORT_COMPARE_MODE=1` 時在每次 `validate_report` 後比對 `core.report_validation` 候選路徑與 legacy 快照；**正式推送仍以 legacy 為準**。詳見 [`docs/REPORT_COMPARE_STAGING.md`](docs/REPORT_COMPARE_STAGING.md)。

---

## 專案結構

```
.
├── docs/
│   ├── MCP_ASK_USER_QUESTION.md     # Cursor／Claude Code 掛載 AskUserQuestion 類 MCP（AUQ）步驟
│   └── ADOPTION_DEXTER_CONCEPTS.md  # Dexter 式概念分階導入計畫（Phase 0+1 與驗證）
├── scratchpad.py        # Phase 1：產報 run 之 JSONL 軌跡（init / gate_result / tool）
├── main.py              # 入口：重試產報、驗證、Telegram、BigQuery 指標寫入
├── crew.py              # CrewAI 四 Agent + 四 Task 定義與 LLM 配置
├── tools.py             # 自訂工具（Tavily、X、CoinGlass、CryptoQuant、FRED、yfinance、BigQuery）
├── config.py            # PROJECT_ID、METRICS_TABLE、WHALE_TABLE
├── dashboard.py         # Streamlit 戰情室
├── backtest.py          # ML 權重最佳化與回測（依賴 BigQuery + CoinGecko）
├── backfill_data.py     # 歷史指標回填 BigQuery
├── inject_test_data.py   # 測試資料注入
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── deploy.sh
├── .github/workflows/
│   ├── deploy.yml           # Push main（程式/Docker 等路徑）或手動 → Cloud Run Job（先跑 ci.yml）
│   └── setup-scheduler.yml  # 一次性建立 Cloud Scheduler 排程
└── AGENTS.md            # Cursor/IDE 用專案說明
```

---

## 環境變數

建議使用專案根目錄 `.env`（或部署時由 Secret Manager 注入）。

### LLM（必填）

| 變數 | 說明 |
|------|------|
| `XAI_API_KEY` | Grok（加密市場） |
| `OPENAI_API_KEY` | GPT（AI 市場）；預設模型為 `gpt-4o-mini`，可設 `OPENAI_MODEL=openai/gpt-4o` 等覆寫 |
| `OPENROUTER_API_KEY` | Claude（OpenRouter） |
| `GEMINI_API_KEY` | Gemini（主編定稿） |
| `OPENAI_MODEL` / `MODEL_GPT`、`MODEL_GROK`、`MODEL_GEMINI`、`MODEL_CLAUDE` | 選填：覆寫 `config.py` 內 LiteLLM 模型字串（預設維持現行 Grok／GPT mini／Gemini／Claude；見 `ENV_TEMPLATE.txt`） |

### 數據與搜尋

| 變數 | 說明 |
|------|------|
| `TAVILY_API_KEY` | 新聞、OpenRouter 排名、傳聞掃描 |
| `X_BEARER_TOKEN` | X 推文搜尋 |
| `COINGLASS_API_KEY` | 衍生品數據 |
| `CRYPTOQUANT_API_KEY` | 交易所流量、MVRV（可選） |
| `FRED_API_KEY` | M2 等宏觀指標 |

### CoinGlass API v4（對照與除錯）

與 [官方認證說明](https://docs.coinglass.com/reference/authentication) 對照：

| 項目 | 說明 |
|------|------|
| Base | `https://open-api-v4.coinglass.com`（`tools.py` 中 `_COINGLASS_BASE`） |
| Header | `CG-API-KEY: <金鑰>`，**不是**舊版 v2 的 `coinglassSecret` |
| 成功 | 回傳 JSON 中 `code` 為 `"0"` 或 `0` |
| 常見錯誤 | `code: "401"`, `msg: "Upgrade plan"` → 金鑰有效但**方案不含該端點**，請參考 [定價/方案](https://www.coinglass.com/pricing) |
| 日誌 | v4 非成功時會 `logger.warning` 打出 `code` / `msg` / metric，便於區分「權限」與「網路」 |
| 備援 | `coinglass_data_tool` 在 CoinGlass 失敗時對 **BTC** 使用 Binance 公開 API（資金費率、OI、多空比等） |
| `regime_scorecard_tool` | 24h 爆倉僅用 **v4** 清算歷史端點 + `CG-API-KEY`（無舊版 v2） |

**curl 自測**（須與 `source .env` 同一 shell，否則金鑰不會傳入）：

```bash
cd /path/to/investment-ai-agent && set -a && . ./.env && set +a
curl -s "https://open-api-v4.coinglass.com/api/futures/open-interest/aggregated-history?symbol=BTC&interval=1d&limit=1" \
  -H "accept: application/json" -H "CG-API-KEY: $COINGLASS_API_KEY" | python3 -m json.tool
```

### Telegram（選填）

| 變數 | 說明 |
|------|------|
| `TELEGRAM_BOT_TOKEN` | Bot Token |
| `TELEGRAM_CHAT_ID` | 推送目標 Chat/Channel ID |

未設定時仍會產報，僅不推送。

### 除錯與乾跑

| 變數 | 說明 |
|------|------|
| `LOG_LEVEL` | 如 `DEBUG` |
| `DEBUG` | `1` / `true` / `yes` 時強制 DEBUG 日誌 |
| `CREW_VERBOSE` | `1` 時 Agent 輸出 tool 呼叫與步驟（`crew.py`） |
| `SKIP_TELEGRAM` | `1` 不發送 Telegram（本地測試用） |
| `SKIP_BIGQUERY` | `1` 不寫入 BigQuery |
| `MAX_REPORT_RETRIES` | 驗證失敗後重試次數（預設 2） |
| `MAX_503_RETRIES` | 503 退避重試次數（預設 3） |
| `BACKOFF_BASE_SEC` | 退避基數秒數（預設 30） |
| `NEWSAPI_DAILY_CALL_LIMIT` | NewsAPI 每日呼叫上限（預設 120） |
| `GNEWS_DAILY_CALL_LIMIT` | GNews 每日呼叫上限（預設 120） |
| `APIFY_DAILY_CALL_LIMIT` | Apify 每日呼叫上限（預設 30） |
| `DISABLE_SOURCE_HEALTH_BQ` | `1` 時停用來源健康分數 BigQuery 同步（僅用本地檔） |
| `VERIFY_API_KEYS` | `1` / `true` 時於 `main.py` 啟動後對 NewsAPI、Apify 做輕量 HTTP 探測（其餘見啟動日誌 `API key inventory`） |

### GCP（部署 / BigQuery）

| 變數 | 說明 |
|------|------|
| `GCP_PROJECT_ID` | 專案 ID（與 BigQuery 資料集用） |

---

## 快速開始

### 開發工具設定（Claude Code / AI 協作）

本專案使用 [gstack](https://github.com/garrytan/gstack) 作為 Claude Code 技能集，提供網頁瀏覽與工程流程工具。

```bash
git clone https://github.com/garrytan/gstack.git ~/.claude/skills/gstack
cd ~/.claude/skills/gstack && ./setup
```

> **前置需求**：需安裝 [bun](https://bun.sh/)（`curl -fsSL https://bun.sh/install | bash`）。

### 安裝

```bash
pip install -r requirements.txt
```

根目錄建立 `.env`，至少填入上述 LLM 與數據 API 金鑰。

### 產出戰報

```bash
python main.py
```

流程：讀取昨日摘要（排除重複）→ 並行執行幣圈 + AI 研究 → Claude 辯論與事實查核 → Gemini 主編整合 → 驗證 → Telegram 推送 → 萃取指標寫入 BigQuery。單次約 15～30 分鐘屬正常。

### 戰情室

```bash
streamlit run dashboard.py
```

可選：`--server.port 8501 --server.headless true`。無 API 金鑰時亦可啟動，BigQuery 相關區塊會顯示 N/A 或友善提示。戰情室 v3 採 DM Sans／JetBrains Mono、圖表 `hovermode=x unified` 與 Gauge 色階與日報 regime 口徑一致。

### 乾跑（不推送、不寫庫）

```bash
SKIP_TELEGRAM=1 SKIP_BIGQUERY=1 python main.py
```

### 除錯（日誌 + Agent 步驟）

```bash
LOG_LEVEL=DEBUG CREW_VERBOSE=1 python main.py
```

驗證失敗時 DEBUG 會輸出報告前 500 字片段，方便排查。

---

## Docker

```bash
docker build -t q-silicon-agent .
docker run --env-file .env q-silicon-agent
```

或：

```bash
docker-compose --env-file .env up --build
```

---

## 部署（Cloud Run Job）

本專案以 **Cloud Run Job** 形式部署（排程或手動觸發），非 HTTP 服務。

- **前置**：Artifact Registry、Service Account（Artifact Registry Writer、Cloud Run Admin、BigQuery 權限）、Secret Manager 存放 API 金鑰。
- **CI**：**PR** 一律跑 `ci.yml`（Lint & Test）。Push `main` 僅在變更 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow 等路徑時跑 **同一** `ci.yml`；純文件 push 不跑 CI。
- **部署**：Push **`main`** 且變更與 **CI 相同 paths**（如 `**/*.py`、`requirements.txt`、`Dockerfile`、workflow）時會 **自動** 跑 **Deploy — Cloud Run Job**（先 `workflow_call` `ci.yml`，再建映像與 `gcloud run jobs deploy`）。純文件 push 不觸發部署。亦可隨時於 GitHub → **Actions** → **Deploy — Cloud Run Job** → **Run workflow** 手動部署。
- **排程**：手動執行一次 `setup-scheduler.yml` 建立 Cloud Scheduler（預設每日 09:00 台北時間）。

GitHub Secrets 建議：`GCP_PROJECT_ID`、`GCP_SA_KEY`、`CLOUD_RUN_SERVICE`、`GAR_REPOSITORY`；排程需 `GCP_SCHEDULER_SA_EMAIL`。

---

## 資料流

```
CrewAI 四核 Agent 產出戰報
        │
        ├──→ Telegram（HTML 分段）
        │
        └──→ 從戰報萃取指標
                ├── DXY、ETF 資金流、風險分數、MVRV Z-Score
                ├── grok_summary / gpt_summary（區塊摘要，若有）
                └── 寫入 BigQuery daily_metrics
                        │
                        ▼
                Streamlit 戰情室（KPI、Gauge、趨勢、巨鯨、摘要）
```

---

## 其他腳本

| 腳本 | 說明 |
|------|------|
| `python backtest.py` | ML 權重最佳化與回測，需 BigQuery 指標與 CoinGecko BTC 價格 |
| `python backfill_data.py` | 歷史 DXY/MVRV 等回填至 BigQuery，需 FRED / CryptoQuant 金鑰 |

---

## 安全與維運

- API 金鑰經環境變數或 GCP Secret Manager 注入，不寫入程式碼或映像。
- Telegram 輸出經 `sanitize_telegram_html` 白名單過濾。
- CI 使用 pinned 版 GitHub Actions，容器以非 root 用戶執行。
- `.gitignore` 排除 `.env`、Service Account JSON 等敏感檔。

更細的維運與已知問題見 **AGENTS.md**。

---

## Q-Silicon War Room PWA（手機版戰情室）

### 架構概覽

```
FastAPI 後端 (api.py)  ←─  BigQuery (daily_metrics + trade_recommendations)
        ↓
React PWA (data-verification-ui/)
        ↓ 安裝至手機主畫面
  📊 今日  /  📈 圖表  /  💼 交易  /  🗄 存檔
```

Telegram 繼續作為 **推播通知** 入口，PWA 作為 **閱讀與互動** 主平台（兩者互補，不互斥）。

---

### 本機啟動

**1. 啟動 FastAPI 後端**

```bash
# 安裝依賴（已含 fastapi + uvicorn）
pip install -r requirements.txt

# 啟動 API（需要 GCP credentials / BigQuery 連線）
uvicorn api:app --reload --port 8000
```

無 BigQuery 時 API 回傳 503，前端顯示 "無法連線至 API"，不影響開發。

**2. 啟動前端開發伺服器**

```bash
cd data-verification-ui
npm install
npm run dev
# → http://localhost:5173（自動 proxy /api → localhost:8000）
```

---

### 頁面功能說明

| 頁面 | 功能 |
|------|------|
| 📊 **今日** | 市場模式 badge（Risk ON/OFF/中性）、DXY/ETF流/MVRV/風險評分 KPI cards、Grok 幣圈情報、AI 產業摘要、今日 QSREC 建議卡片 |
| 📈 **圖表** | DXY / ETF 資金流 / MVRV Z-Score / 風險評分 互動折線圖，支援 30 / 60 / 90 天切換 |
| 💼 **交易** | 勝率 / 平均 R:R / 平均 P&L 統計、全部/持倉中/達標/停損篩選、QSREC 建議卡片含 **評分維度 bar chart + 三情境分析** |
| 🗄 **存檔** | 歷史報告清單（60 天），點入查看單日完整數據 + QSREC |

---

### 交易卡片進階功能（P4）

每張 QSREC 建議卡片可展開「**評分 & 情境分析**」：

**五維評分雷達（0–100）**

| 維度 | 說明 |
|------|------|
| 催化（Catalyst） | 新聞事件 / ETF / 監管催化強度 |
| 資金（Flow） | ETF 流入 / 鏈上淨流向 / 資金費率訊號 |
| 技術（Technical） | 多時框一致性、均線結構、RSI/OI |
| 風控（Risk Fit） | 與當日 regime 的倉位契合度 |
| 執行（Execution） | 流動性、進場區間實用性 |

**三情境分析**（信心 ≥ 3 星時填入）

| 情境 | 說明 |
|------|------|
| 🐂 Bull | 樂觀目標價 + 觸發條件 |
| ⚖️ Base | 基準預期 + 機率估算 |
| 🐻 Bear | 失效位 + 風險觸發條件 |

---

### 手機安裝（PWA）

**iOS（Safari）**

1. 瀏覽器開啟 PWA 網址
2. 點擊底部 **分享** 按鈕
3. 選擇「**加入主畫面**」
4. 確認後桌面出現「Q-Silicon War Room」app 圖示

**Android（Chrome）**

1. 瀏覽器開啟 PWA 網址
2. 瀏覽器提示「**安裝應用程式**」→ 點安裝
3. 或：選單 → 「**加入主畫面**」

安裝後以全螢幕深色介面開啟，無瀏覽器工具列。

---

### 部署（生產環境）

**前端 Build**

```bash
cd data-verification-ui
npm run build        # 輸出 dist/
# 部署至 Firebase Hosting / Vercel / Cloud Run (nginx)
```

**API 環境變數**

| 變數 | 說明 | 預設 |
|------|------|------|
| `GCP_PROJECT_ID` | BigQuery 專案 ID | `my-investment-ai-agent` |
| `CORS_ORIGINS` | 前端 origin 清單（逗號分隔） | `http://localhost:5173,...` |

```bash
# 生產啟動
uvicorn api:app --host 0.0.0.0 --port 8000 --workers 2
```

**API 端點一覽**

```
GET /api/metrics/latest          最新 KPI + 日環比
GET /api/metrics/history?days=30 歷史趨勢（7–180天）
GET /api/reports?limit=30        報告清單
GET /api/reports/{YYYY-MM-DD}    單日報告 + QSREC 建議
GET /api/trades?status=OPEN      交易建議（可篩 status/days）
GET /api/trades/performance      勝率/R:R/P&L 統計
GET /healthz                     健康檢查
```
