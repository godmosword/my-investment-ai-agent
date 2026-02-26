# Q-Silicon Institutional Research AI Agent 🛸

一個完全自動化、企業級的 **四核 AI 投資研究智庫**。  
結合最新大型語言模型與即時數據 API，每天產出具備「社群情緒」、「鏈上流向」與「風險批判」的加密貨幣 & 前沿 AI 科技戰報，並可一鍵推送至 Telegram。

---

## 🚀 功能總覽

- **四大專職 Agent (CrewAI 架構)**  
  - Grok：幣圈 + 宏觀流動性偵察  
  - GPT：前沿 AI 科技與算力經濟研究  
  - Claude：首席風控與邏輯審計  
  - Gemini：機構級主編與報告排版  

- **外部數據整合**
  - Tavily：即時新聞 & AI 算力經濟學
  - X API：社群情緒與敘事熱度
  - CoinGlass：合約未平倉 / 清算數據
  - CryptoQuant：交易所淨流入 / 流出
  - FRED：M2 / DXY 等宏觀指標
  - BigQuery：自建巨鯨鏈上數據查詢 (`crypto_whale_alert` 等)

- **輸出管道**
  - 自動生成完整日報 (`Q-Silicon Institutional Research Daily Brief`)
  - 透過 Telegram Bot 分段推送（支援 Markdown）

---

## 🛠️ 環境變數設定

在執行前，請確保已設好以下環境變數（可寫入 `.env`，或在 Docker / Cloud Run / GitHub Secrets 中設定）。

### 🔑 LLM 模型金鑰（必填）

| 變數名稱 | 用途說明 |
| -------- | -------- |
| `XAI_API_KEY` | 驅動 Grok 進行幣圈與宏觀流動性分析 |
| `OPENAI_API_KEY` | 驅動 GPT 進行 AI 科技前沿分析 |
| `OPENROUTER_API_KEY` | 經由 OpenRouter 呼叫 Claude 進行風險審計批判 |
| `GEMINI_API_KEY` | 驅動 Gemini 進行戰報精準排版 |

### 📊 數據與搜尋 API

| 變數名稱 | 用途說明 |
| -------- | -------- |
| `TAVILY_API_KEY` | 搜尋即時新聞與 AI 算力經濟學數據 |
| `X_BEARER_TOKEN` | 讀取 X (Twitter) 社群討論原聲 |
| `COINGLASS_API_KEY` | 合約未平倉量、清算與 OI 數據 |
| `CRYPTOQUANT_API_KEY` | 交易所淨流入 / 流出實體數據 |
| `FRED_API_KEY` | M2 / DXY 等宏觀經濟指標（若未設定，會自動降級使用 Tavily） |

### 💬 Telegram 推送（選填但強烈建議）

| 變數名稱 | 用途說明 |
| -------- | -------- |
| `TELEGRAM_BOT_TOKEN` | 你的 Telegram Bot Token |
| `TELEGRAM_CHAT_ID` | 要推送戰報的 Chat / Channel ID |

若未設定 Telegram 相關變數，系統仍會照常完成分析，只是 **不會推送訊息**。

---

## 🧑‍💻 本地開發與執行

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

請確保根目錄有 `.env`，內容至少包含上面列出的必要金鑰。

### 2. 本地執行

```bash
python main.py
```

流程：
- 實例化 `QSiliconResearchCrew`
- 依序執行四個 Task（幣圈、AI、風控審計、主編定稿）
- 生成日報字串
- 若有 Telegram 設定，會自動分段推送到指定 Chat

---

## 🐳 使用 Docker / Docker Compose

### 1. 直接用 Docker 執行

```bash
docker build -t q-silicon-agent .
docker run --env-file .env q-silicon-agent
```

### 2. 使用 `docker-compose.yml`

專案已提供 `docker-compose.yml`，可直接：

```bash
docker-compose --env-file .env up --build
```

請在 `.env` 中填好所有必要金鑰與 Telegram 參數。

---

## ☁️ 部署到 Google Cloud Run Job（CI/CD）

本專案預設目標是 **Cloud Run Job**（非 HTTP Service），適合排程或手動觸發的研究任務。

### 1. 建立 Artifact Registry 與 Service Account

- 建立 Artifact Registry（如：`cloud-run-source-deploy`）
- 建立具備以下權限的 Service Account：
  - Artifact Registry Writer
  - Cloud Run Admin / Developer
  - BigQuery 資料存取（若使用 BigQuery 工具）

將該 Service Account 的 JSON 金鑰存成 GitHub Secret：`GCP_SA_KEY`。

### 2. GitHub Actions 環境變數與 Secrets

`/.github/workflows/deploy.yml` 使用以下 Secrets / env：

- `GCP_PROJECT_ID`：GCP 專案 ID  
- `CLOUD_RUN_SERVICE`：Cloud Run Job 名稱（同時作為 image name）  
- `GAR_REPOSITORY`：Artifact Registry repository 名稱  
- `GCP_SA_KEY`：Service Account JSON（金鑰內容）  

Workflow 會：

1. Checkout 原始碼並安裝 Python 依賴  
2. 使用 `google-github-actions/auth` + `setup-gcloud` 登入 GCP  
3. Build Docker image 並推送至 Artifact Registry  
4. 透過：

```bash
gcloud run jobs deploy "${CLOUD_RUN_SERVICE}" \
  --image "$IMAGE_URI" \
  --region "asia-east1" \
  --quiet
```

部署為 Cloud Run Job。之後你可以在 GCP Console 或排程器中觸發該 Job。

> ⚠️ 注意：本專案不會在容器內啟動 8080 HTTP 服務，因此 **務必使用 Cloud Run Job，而不是 Cloud Run Service**，否則會遇到 `PORT=8080` 健康檢查失敗的錯誤。

---

## 🧩 BigQuery 工具說明

`main.py` 中的 `BigQueryAnalyticsTool` 會：

- 使用 `google-cloud-bigquery` 官方套件
- 連線到你設定的 GCP 專案（預設程式碼為 `my-investment-ai-agent`，請依實際專案 ID 調整）
- 查詢如 `market_data.btc_whale_transactions` 這類自建資料表
- 回傳過去 24 小時內的巨鯨轉帳統計（`crypto_whale_alert`）

請確保：

- 專案中已有對應的 BigQuery Dataset / Table  
- Cloud Run 使用的 Service Account 具備 BigQuery 讀取權限  

---

## 🧭 架構總結

- **核心程式**：`main.py`（定義所有 Tools、Agents、Tasks 與 Telegram 推送）
- **容器化**：`Dockerfile`（以 `python:3.11-slim` 為基底）
- **本地 / Docker 啟動**：`docker-compose.yml`（掛載環境變數）
- **CI/CD**：`.github/workflows/deploy.yml` → 部署到 Cloud Run Job

如需進一步客製化（例如新增 Agent / Task、增強報告格式、改成多語系輸出），可以直接修改 `QSiliconResearchCrew` 內的 Agent 與 Task 定義。 
