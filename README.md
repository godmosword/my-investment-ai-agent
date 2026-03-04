# Q-Silicon Institutional Research AI Agent

以 CrewAI 驅動的**四核 AI 投資研究智庫**，每日自動產出加密貨幣與前沿 AI 雙市場戰報，結合即時數據與多模型辯論，最終只輸出**主編共識**與儀表板，推送 Telegram、寫入 BigQuery，並由 Streamlit 戰情室呈現。

---

## 功能總覽

### 四大專職 Agent

| Agent | 模型 | 職責 |
|-------|------|------|
| 加密市場研究員 | Grok | 幣圈新聞、推文、宏觀 M2/DXY、鏈上 MVRV、衍生品、CryptoPanic / 傳聞掃描 |
| AI 市場研究員 | GPT | AI 基建（含電力/散熱/材料）、投資案、最新模型、OpenRouter 熱度排名、MCP/Agent 推文 |
| 跨域辯論員 | Claude | 數據即時性與事實查核、VIX/IBIT 風險審計、每則新聞/推文反向辯論、market_regime 判定 |
| 機構策略主編 | Gemini | 整合儀表板、將多空辯論濃縮為「主編共識」、Telegram HTML 定稿 |

設計原則：**背景充分辯論，報告只呈現乾淨共識與即時數據**。戰報中不顯示 Grok/GPT/Claude 個別觀點，僅保留每則新聞與推文下的 **💎 主編共識**。

### 數據來源

| 來源 | 用途 |
|------|------|
| Tavily | 即時新聞、OpenRouter 模型熱度排名、傳聞掃描 |
| X API | 社群推文與敘事熱度 |
| CoinGlass | 未平倉、資金費率、清算、多空比 |
| CryptoQuant | 交易所淨流入/流出、MVRV Z-Score（若訂閱支援） |
| FRED | M2；DXY 改由 Tavily 即時報價 |
| yfinance | VIX、SPY/QQQ 成交額 proxy、IBIT 報價 |
| BigQuery | 巨鯨鏈上、每日指標儲存與排除重複上下文 |

### 輸出

- **Telegram**：HTML 分段推送，retry + 純文字 fallback，僅允許白名單標籤。
- **BigQuery**：從戰報萃取 DXY、ETF 資金流、平均風險分數、MVRV Z-Score、Grok/GPT 摘要寫入 `daily_metrics`。
- **Streamlit 戰情室**：KPI 卡片、風險 Gauge、趨勢圖、巨鯨數據、Agent 摘要。

### 穩定性

- **驗證與重試**：`validate_report()` 檢查新聞/推文數量、market_regime、儀表板關鍵字；不合格則重試（預設最多 3 次）。
- **503 退避**：偵測 503/Unavailable 時指數退避重試（可配置次數與基數）。
- **LLM**：各模型 `max_retries` 3～5、`timeout` 120～180 秒。

---

## 專案結構

```
.
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
│   ├── deploy.yml           # CI/CD → Cloud Run Job
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
| `OPENAI_API_KEY` | GPT（AI 市場） |
| `OPENROUTER_API_KEY` | Claude（OpenRouter） |
| `GEMINI_API_KEY` | Gemini（主編定稿） |

### 數據與搜尋

| 變數 | 說明 |
|------|------|
| `TAVILY_API_KEY` | 新聞、OpenRouter 排名、傳聞掃描 |
| `X_BEARER_TOKEN` | X 推文搜尋 |
| `COINGLASS_API_KEY` | 衍生品數據 |
| `CRYPTOQUANT_API_KEY` | 交易所流量、MVRV（可選） |
| `FRED_API_KEY` | M2 等宏觀指標 |

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

### GCP（部署 / BigQuery）

| 變數 | 說明 |
|------|------|
| `GCP_PROJECT_ID` | 專案 ID（與 BigQuery 資料集用） |

---

## 快速開始

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

可選：`--server.port 8501 --server.headless true`。無 API 金鑰時亦可啟動，BigQuery 相關區塊會顯示 N/A 或友善提示。

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
- **CI/CD**：Push `main` 觸發 `deploy.yml`，建映像、推至 GAR、`gcloud run jobs deploy`，金鑰經 `--set-secrets` 注入。
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
