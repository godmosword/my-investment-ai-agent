# 單次日報 · 各模型 API 費用估算

依目前 `crew.py` 的 Agent 配置，估算**產生一次日報**時，每個模型/供應商的 API 花費（單次、未重試）。定價為 2025–2026 參考值，實際以各廠帳單為準。

---

## 1. 目前 Agent 與模型對應

| Agent | 模型 | 對應 Task |
|-------|------|-----------|
| 加密市場情報研究員 | **Grok**（xai/grok-4-1-fast-reasoning） | crypto_task |
| 首席幣圈風險審計員 | **GPT**（openai/gpt-4o-mini） | review_task（Crypto） |
| 機構策略主編（加密市場） | **Gemini**（gemini-3.1-pro-preview） | final_report_task（Crypto） |
| 前沿 AI 市場研究員 | **GPT**（openai/gpt-4o-mini） | ai_task |
| 首席 AI 市場辯論員 | **Grok**（xai/grok-4-1-fast-reasoning） | review_task（AI） |
| 機構策略主編（AI 市場） | **Gemini**（gemini-3.1-pro-preview） | final_report_task（AI） |

另：`sentiment_score_tool` 依金鑰依序嘗試 **Gemini 2.5 Flash → gpt-4o-mini → Claude Haiku**，單次約 2.5k in / 0.2k out，費用可忽略。

---

## 2. 單次產報 Token 粗估（按模型）

以下為一次完整跑完 Crypto + AI 兩份戰報、未重試的合理區間。

| 模型 | 使用區塊 | Input（約） | Output（約） |
|------|----------|-------------|--------------|
| **Grok** | crypto_task + AI review_task | ~43,000 | ~12,000 |
| **GPT** | Crypto review_task + AI ai_task | ~42,000 | ~12,000 |
| **Gemini** | Crypto final_report + AI final_report | ~53,000 | ~18,000 |

---

## 3. 各廠定價與單次日報費用（USD）

### 3.1 定價參考（每 1M tokens）

| 供應商 | 模型 | Input（/1M） | Output（/1M） | 來源 |
|--------|------|--------------|--------------|------|
| **OpenAI** | gpt-4o-mini | $0.15 | $0.60 | [OpenAI Pricing](https://openai.com/api/pricing) |
| **Google** | gemini-3.1-pro-preview | $2.00 | $12.00 | [Gemini Pricing](https://ai.google.dev/gemini-api/docs/pricing)（≤200K 區間） |
| **xAI** | grok-4-1-fast-reasoning | $0.20 | $0.50 | [xAI / pricepertoken](https://pricepertoken.com/pricing-page/model/xai-grok-4.1-fast) 等級 |

### 3.2 單次日報每模型花費（未重試）

| 模型 | 計算式 | **單次日報約（USD）** |
|------|--------|------------------------|
| **OpenAI（gpt-4o-mini）** | 0.042×0.15 + 0.012×0.60 | **≈ $0.014** |
| **Gemini（3.1 Pro Preview）** | 0.053×2 + 0.018×12 | **≈ $0.32** |
| **Grok（4.1 Fast）** | 0.043×0.20 + 0.012×0.50 | **≈ $0.015** |

---

## 4. 單次日報總成本與占比（未重試）

| 項目 | 約 USD/次 | 占比（約） |
|------|-----------|------------|
| OpenAI（gpt-4o-mini） | ~$0.01 | ~3% |
| Gemini（3.1 Pro Preview） | ~$0.32 | ~92% |
| Grok（4.1 Fast） | ~$0.02 | ~5% |
| **合計（LLM 僅）** | **~$0.35** | 100% |

說明：**不含** Apify、NewsAPI、Tavily、X API、CoinGlass 等資料 API；若觸發產報重試，總 token 與費用約為 2～3 倍。

---

## 5. 重試與變動

- **MAX_REPORT_RETRIES=2**：最壞 3 次完整產報 → 各模型費用約 ×3（例如 Gemini 單次 ~$0.32 → 最壞 ~$0.96）。
- **OPENAI_MODEL**：若改為 gpt-4o、gpt-5.2 等較貴模型，OpenAI 那欄會明顯上升；其餘不變。
- **定價異動**：各廠可能調價，請以官網與帳單為準。

---

## 6. 若改用 GPT-5.2（OPENAI_MODEL=openai/gpt-5.2-2025-12-11）

GPT-5.2 定價依來源有兩種區間（每 1M tokens，USD）：

| 區間 | Input | Output | 單次日報 OpenAI 約（42k in / 12k out） |
|------|-------|--------|----------------------------------------|
| 較低 | $0.875 | $7.00 | **≈ $0.12** |
| 較高 | $1.75 | $14.00 | **≈ $0.24** |

計算式（較高）：`0.042×1.75 + 0.012×14 ≈ $0.24`  
此時**單次日報 LLM 總計**約：**$0.24（OpenAI）+ $0.32（Gemini）+ $0.02（Grok）≈ $0.58**（未重試）。

與目前 gpt-4o-mini 相比：OpenAI 從 ~$0.01 增至 ~$0.12～$0.24，總成本由 ~$0.35 增至 ~$0.46～$0.58。

---

**總結**：單次日報（未重試）LLM 總花費約 **$0.35**（預設 gpt-4o-mini）；若改為 **GPT-5.2** 則約 **$0.46～$0.58**。Gemini 3.1 Pro Preview 仍佔多數（兩位機構策略主編）。
