# Q-Silicon Institutional Research AI Agent

一個完全自動化、企業級的 **四核 AI 投資研究智庫**。
結合最新大型語言模型與即時數據 API，每天自動產出具備「社群情緒」、「鏈上流向」與「風險批判」的加密貨幣 & 前沿 AI 科技戰報，並推送至 Telegram、同步寫入 BigQuery，供 Streamlit 戰情室即時呈現。

---

## 功能總覽

### 四大專職 Agent（CrewAI 架構）

| Agent | 模型 | 職責 |
|---|---|---|
| 幣圈研究員 | Grok | 幣圈新聞、宏觀 M2/DXY、巨鯨鏈上、傳聞掃描 |
| AI 研究員 | GPT | 前沿 AI 科技、GPU 租賃成本、模型排名、產業爭議 |
| 風控審計員 | Claude | 跨區塊可信度審計、敘事操縱識別、market_regime 判定 |
| 機構主編 | Gemini | 整合數據儀表板、排版定稿、Telegram HTML 格式輸出 |

### 外部數據整合

| 來源 | 用途 |
|---|---|
| Tavily | 即時新聞搜尋 & AI 算力經濟學 |
| X API | 社群情緒與敘事熱度（原始推文擷取） |
| CoinGlass | 合約未平倉量 / 清算 / OI 數據 |
| CryptoQuant | 交易所淨流入 / 流出 |
| FRED | M2 / DXY 等宏觀經濟指標 |
| BigQuery | 自建巨鯨鏈上數據 & 每日指標儲存 |

### 輸出管道

- **Telegram 推送**：自動分段推送日報，支援 HTML 格式，含 retry 與純文字 fallback
- **BigQuery 指標寫入**：每次戰報自動萃取 DXY、ETF 資金流、風險分數、B200 租賃價、Agent 情報摘要
- **Streamlit 戰情室**：即時 KPI 卡片（含日環比 delta）、風險 Gauge 儀表盤、趨勢圖、Agent 觀點

### 穩定性機制

- **戰報驗證 & 自動重試**：`validate_report` 檢查新聞數、推文數、market_regime、儀表板數據，不合格自動重試（最多 3 次）
- **LLM 容錯**：所有模型設定 `max_retries`（3~5 次）與 `timeout`（120~180 秒）
- **Telegram 容錯**：HTML 推送失敗自動降級為純文字，訊息過長自動分段（4000 字元切割，避免截斷 HTML 標籤）

---

## 專案結構

```
.
├── main.py                  # 入口：編排、驗證、指標萃取、Telegram 推送
├── crew.py                  # CrewAI Agent & Task 定義、LLM 配置
├── tools.py                 # 自訂工具（BigQuery、CoinGlass、CryptoQuant、FRED、X、Tavily）
├── dashboard.py             # Streamlit 戰情室（KPI、Gauge、趨勢圖、Agent 摘要）
├── inject_test_data.py      # BigQuery 測試資料注入腳本
├── Dockerfile               # 容器化（python:3.11-slim、非 root 用戶）
├── docker-compose.yml       # 本地 Docker 啟動
├── deploy.sh                # 快速 git push 腳本
├── requirements.txt         # Python 依賴（含最低版本鎖定）
├── .github/
│   └── workflows/
│       ├── deploy.yml           # CI/CD：Build → Push → Cloud Run Job 部署
│       └── setup-scheduler.yml  # 一次性：建立 Cloud Scheduler 每日排程
└── .gitignore
```

---

## 環境變數設定

在執行前，請確保已設好以下環境變數（可寫入 `.env`，或在 GCP Secret Manager / GitHub Secrets 中設定）。

### LLM 模型金鑰（必填）

| 變數名稱 | 用途說明 |
|---|---|
| `XAI_API_KEY` | 驅動 Grok 進行幣圈與宏觀流動性分析 |
| `OPENAI_API_KEY` | 驅動 GPT 進行 AI 科技前沿分析 |
| `OPENROUTER_API_KEY` | 經由 OpenRouter 呼叫 Claude 進行風險審計 |
| `GEMINI_API_KEY` | 驅動 Gemini 進行戰報精準排版 |

### 數據與搜尋 API

| 變數名稱 | 用途說明 |
|---|---|
| `TAVILY_API_KEY` | 搜尋即時新聞與 AI 算力經濟學數據 |
| `X_BEARER_TOKEN` | 讀取 X (Twitter) 社群討論原聲 |
| `COINGLASS_API_KEY` | 合約未平倉量、清算與 OI 數據 |
| `CRYPTOQUANT_API_KEY` | 交易所淨流入 / 流出實體數據 |
| `FRED_API_KEY` | M2 / DXY 等宏觀經濟指標 |

### Telegram 推送（選填但強烈建議）

| 變數名稱 | 用途說明 |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 要推送戰報的 Chat / Channel ID |

若未設定 Telegram 相關變數，系統仍會照常完成分析，只是不會推送訊息。

---

## 本地開發與執行

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

請確保根目錄有 `.env`，內容至少包含上面列出的必要金鑰。

### 2. 執行戰報

```bash
python main.py
```

流程：
1. 實例化 `QSiliconResearchCrew`（`crew.py`）
2. 並行執行幣圈 + AI 研究 Task，再依序執行風控審計、主編定稿
3. `validate_report` 驗證內容品質，不合格自動重試
4. 透過 Telegram Bot 分段推送（含 HTML sanitization）
5. `extract_and_save_metrics` 萃取 DXY、ETF、風險分數、B200 價格、Agent 摘要寫入 BigQuery

### 3. 啟動戰情室

```bash
streamlit run dashboard.py
```

戰情室功能：
- 四張 KPI 卡片：市場模式、DXY、B200 租賃價、ETF 資金流（含日環比 delta）
- 風險 Gauge 儀表盤：0~5 三色區間（綠/黃/紅）+ 警戒線
- 趨勢圖：風險分數、DXY、ETF 資金流（支援 7/14/30/90 天切換）
- 巨鯨轉帳圖表 + 原始數據展開
- Agent 戰略觀點：動態讀取 Grok / GPT 最新情報摘要

---

## 使用 Docker

### 直接用 Docker 執行

```bash
docker build -t q-silicon-agent .
docker run --env-file .env q-silicon-agent
```

### 使用 docker-compose

```bash
docker-compose --env-file .env up --build
```

---

## 部署到 Google Cloud Run Job（CI/CD）

本專案部署為 **Cloud Run Job**（非 HTTP Service），適合排程或手動觸發。

### 前置準備

1. **建立 Artifact Registry**（如：`cloud-run-source-deploy`）

2. **建立 Service Account**（`github-deployer`），授予以下角色：
   - Artifact Registry Writer
   - Cloud Run Admin
   - BigQuery Data Editor

3. **啟用 Secret Manager API**（需用 Owner 帳號執行）：

```bash
gcloud services enable secretmanager.googleapis.com --project=YOUR_PROJECT_ID
```

4. **上傳金鑰到 Secret Manager**（需用 Owner 帳號執行）：

```bash
echo -n "YOUR_API_KEY_VALUE" | gcloud secrets create KEY_NAME \
  --data-file=- --replication-policy=automatic --project=YOUR_PROJECT_ID
```

5. **授權 Cloud Run 讀取 Secrets**：

```bash
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### GitHub Secrets 設定

| Secret 名稱 | 用途 |
|---|---|
| `GCP_PROJECT_ID` | GCP 專案 ID |
| `GCP_SA_KEY` | Service Account JSON 金鑰 |
| `CLOUD_RUN_SERVICE` | Cloud Run Job 名稱 |
| `GAR_REPOSITORY` | Artifact Registry repository 名稱 |
| `GCP_SCHEDULER_SA_EMAIL` | Cloud Scheduler 使用的 SA email（僅 scheduler 需要） |

### CI/CD 流程（`deploy.yml`）

Push 到 `main` 分支後自動觸發：

1. Checkout 原始碼
2. 使用 pinned SHA 的 GitHub Actions 登入 GCP（防供應鏈攻擊）
3. Build Docker image → Push 至 Artifact Registry
4. `gcloud run jobs deploy` 部署 Job，金鑰透過 `--set-secrets` 從 Secret Manager 注入

### 設定每日排程（`setup-scheduler.yml`）

手動觸發一次即可，建立 Cloud Scheduler 每日自動執行 Job：

- 預設時間：每日 09:00 台北時間（UTC 01:00）
- 可在觸發時自訂 cron 表達式

> **注意**：本專案不會啟動 HTTP 服務，務必使用 Cloud Run **Job**，不是 Cloud Run Service，否則會遇到健康檢查失敗。

---

## 資料管線

```
CrewAI 四核 Agent 產出戰報
        │
        ├──→ Telegram Bot 推送（HTML 分段）
        │
        └──→ strip_html → regex 萃取指標
                │
                ├── DXY（美元指數）
                ├── ETF 資金流（億）
                ├── 平均風險分數（RISK x/5）
                ├── B200 租賃價（$/hr）
                ├── Grok 幣圈情報摘要
                └── GPT AI 產業情報摘要
                        │
                        ▼
                BigQuery daily_metrics
                        │
                        ▼
                Streamlit 戰情室
                ├── KPI 卡片（含日環比 delta）
                ├── 風險 Gauge 儀表盤
                ├── 趨勢折線圖 / 柱狀圖
                └── Agent 戰略觀點（動態）
```

---

## 安全設計

| 項目 | 做法 |
|---|---|
| API 金鑰 | 透過 GCP Secret Manager 注入，不在 image 或 workflow 中明文存放 |
| CI 供應鏈 | GitHub Actions pinned 至 commit SHA，防止版本劫持 |
| 容器安全 | 非 root 用戶 (`appuser`) 執行 |
| HTML 輸出 | `sanitize_telegram_html` 白名單過濾，僅保留 Telegram 支援的標籤 |
| 錯誤訊息 | 工具錯誤回傳使用 `json.dumps`，防止 API key 外洩或 JSON 注入 |
| 敏感檔案 | `.gitignore` 排除 `.env`、`upload_secrets.sh`、Service Account JSON |
