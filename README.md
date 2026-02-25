# Q-Silicon Institutional Research AI Agent 🛸

一個完全自動化、企業級的 **四核 AI 投資研究智庫**。
結合最新的大型語言模型與即時數據 API，每天為您產出具備「社群情緒」、「鏈上流向」與「風險批判」的加密貨幣與前沿 AI 科技戰報。

## 🧠 四大天王核心架構 (Powered by OpenRouter)
本系統採用 CrewAI 框架，配置四位專職 Agent：
1. **Grok-4.1-fast (幣圈偵察)**：掃描幣圈動態與 X (Twitter) 社群 FOMO/FUD 情緒。
2. **GPT-5.3-codex (科技研究)**：追蹤全球最新 AI 模型發布與開源工具。
3. **Claude-Sonnet-4.6 (首席風控)**：負責毒舌審計，揭露市場炒作與清算風險。
4. **Gemini-3.1-pro (機構主編)**：整合 CoinGlass 與 CryptoQuant 鏈上數據，排版定稿。

## 🛠️ 環境變數 (Environment Variables)
在執行前，請確保設置以下環境變數（可寫入 `.env` 檔案或設定在 GitHub Secrets/GCP）：

| 變數名稱 | 用途說明 |
| -------- | -------- |
| `OPENROUTER_API_KEY` | 呼叫四大 LLM 模型的統一接口金鑰 |
| `TAVILY_API_KEY` | 搜尋 24 小時內即時新聞 |
| `X_BEARER_TOKEN` | 獲取 Twitter 社群討論原聲 |
| `COINGLASS_API_KEY` | 獲取合約未平倉量與清算數據 |
| `CRYPTOQUANT_API_KEY` | 獲取交易所淨流入/流出實體數據 |
| `TELEGRAM_BOT_TOKEN` | 您的 Telegram 機器人 Token |
| `TELEGRAM_CHAT_ID` | 接收戰報的目標對話 ID |

## 🚀 部署與執行

### 本地測試 (Local Testing)
1. 安裝依賴：`pip install -r requirements.txt`
2. 建立 `.env` 檔案並填入金鑰。
3. 執行指令：`python main.py`

### Docker 部署
```bash
docker compose up --build

}
