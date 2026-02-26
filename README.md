# Q-Silicon Institutional Research AI Agent 🛸

一個完全自動化、企業級的 **四核 AI 投資研究智庫**。
結合最新的大型語言模型與即時數據 API，每天為您產出具備「社群情緒」、「鏈上流向」與「風險批判」的加密貨幣與前沿 AI 科技戰報。

## 🧠 四大天王核心架構 (原生 API + OpenRouter 混合驅動)
本系統採用 CrewAI 框架，配置四位專職 Agent，嚴格鎖定 2026 年最強模型陣容：

1. **xAI grok-4-1-fast-reasoning (幣圈偵察)**：直連原生 API。掃描幣圈動態與 X (Twitter) 社群 FOMO/FUD 情緒，並結合 FRED 宏觀數據。
2. **OpenAI gpt-5.2-pro-2025-12-11 (科技研究)**：直連原生 API。追蹤全球最新 AI 模型發布、GPU 算力租賃價格與開源工具。
3. **Anthropic claude-sonnet-4.6 (首席風控)**：經由 OpenRouter 調用。負責毒舌審計，揭露市場炒作與清算風險。
4. **Google gemini-3.1-pro-preview (機構主編)**：直連原生 API。整合 CoinGlass 與 CryptoQuant 鏈上數據，負責最終的動態過濾排版定稿。

## 🛠️ 環境變數 (Environment Variables)
在執行前，請確保設置以下環境變數（可寫入 `.env` 檔案，或設定在 GitHub Secrets / Docker 中）：

### 🔑 LLM 模型金鑰 (必填)
| 變數名稱 | 用途說明 |
| -------- | -------- |
| `XAI_API_KEY` | 驅動 Grok 進行幣圈與宏觀流動性分析 |
| `OPENAI_API_KEY` | 驅動 GPT-5.2-Pro 進行 AI 科技前沿分析 |
| `OPENROUTER_API_KEY` | 呼叫 Claude 進行風險審計批判 |
| `GEMINI_API_KEY` | 驅動 Gemini 進行戰報精準排版 |

### 📊 數據與搜尋 API (必填/選填)
| 變數名稱 | 用途說明 |
| -------- | -------- |
| `TAVILY_API_KEY` | 搜尋即時新聞與 AI 算力經濟學數據 (必填) |
| `X_BEARER_TOKEN` | 獲取 Twitter 社群討論原聲 (必填) |
| `COINGLASS_API_KEY` | 獲取合約未平倉量與清算數據 (必填) |
| `CRYPTOQUANT_API_KEY`| 獲取交易所淨流入/流出實體數據 (必填) |
| `FRED_API_KEY` | 獲取 M2/DXY 等精準宏觀經濟指標 (選填，無則降級使用 Tavily)
