# 單次日報 OpenAI API 費用預估

本文件依目前 pipeline 的 **OpenAI（GPT）** 使用點與合理 token 假設，估算產生**一次**日報的 OpenAI 費用。不含 Grok / Gemini / OpenRouter / Apify 等其餘服務。

---

## 1. Pipeline 中哪裡用到 OpenAI？

目前僅 **2 個 Agent** 使用 OpenAI（其餘為 Grok / Gemini），詳見 `docs/COST_PER_MODEL.md`。

| 位置 | 用途 | 模型（`crew.py`） | 預估 LLM 輪數/次 |
|------|------|-------------------|-------------------|
| **Crypto 戰報** | 辯論與風險審計（review_task） | `MODEL_GPT` | 約 2～4 輪（regime_scorecard_tool、macro_context_tool） |
| **AI 戰報** | AI 情報收集（ai_task） | `MODEL_GPT` | 約 5～10 輪（多個搜尋/新聞/推文工具） |
| **選用** | `sentiment_score_tool`（情緒評分） | 候選含 `gpt-4o-mini` | 0～1 次（多數由 Gemini 先處理） |

註：機構策略主編（加密/AI）已改為 **Gemini 3.1 Pro Preview**，不再使用 OpenAI。

目前 `crew.py` 中**預設**為低成本模型，並可透過環境變數覆寫：

```text
MODEL_GPT = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")   # 預設
# 若要改用旗艦：export OPENAI_MODEL=openai/gpt-4o 或 openai/gpt-5.2-2025-12-11
```

實際計費以 OpenAI 帳單上該模型為準。

---

## 2. 單次完整產報的 Token 估計（僅 OpenAI GPT）

以下為**一次**完整跑完兩份戰報（Crypto + AI）、且**未觸發產報重試**的粗估：

| 區塊 | 輸入 token（約） | 輸出 token（約） |
|------|------------------|------------------|
| Crypto review_task | 12,000 | 4,500 |
| Crypto final_report_task | 32,000 | 10,000 |
| AI ai_task | 30,000 | 7,000 |
| AI final_report_task | 21,000 | 7,500 |
| **合計** | **~95,000** | **~29,000** |

取整：**約 10 萬 input、3 萬 output**  per run。  
若啟用重試（`MAX_REPORT_RETRIES=2`），最壞約 3 次完整產報 → 約 **30 萬 input、9 萬 output**。

`sentiment_score_tool` 若走 gpt-4o-mini：單次約 2.5k in / 0.2k out，相對主流程可忽略不計。

---

## 3. 依 OpenAI 官網定價的費用區間（2025–2026 參考）

以下價格來自 [OpenAI Pricing](https://openai.com/api/pricing) 的 **Chat Completions** 計費（每 1M tokens，USD）：

| 模型類型 | Input（/1M） | Output（/1M） | 單次日報（10 萬 in / 3 萬 out） |
|----------|--------------|--------------|-----------------------------------|
| **gpt-4o-mini**（預設，省錢） | $0.15 | $0.60 | 約 **$0.03** |
| **GPT-5 mini** | $0.25 | $2.00 | 約 **$0.09** |
| **GPT-5.4**（旗艦） | $2.50 | $15.00 | 約 **$0.70** |

計算式（單次、未重試）：

- **gpt-4o-mini**（目前預設）：`0.1 × 0.15 + 0.03 × 0.6 ≈ 0.015 + 0.018 = $0.03`
- GPT-5 mini：`0.1 × 0.25 + 0.03 × 2 ≈ 0.025 + 0.06 = $0.09`
- GPT-5.4：`0.1 × 2.5 + 0.03 × 15 ≈ 0.25 + 0.45 = $0.70`

若要改用較貴模型，設環境變數即可，例如：`OPENAI_MODEL=openai/gpt-4o` 或 `openai/gpt-5.2-2025-12-11`。

---

## 4. 重試與邊界情況

- **驗證失敗重試**：`main.py` 中 `MAX_REPORT_RETRIES` 預設為 2，即最多 3 次產報。若常因驗證或 503 重試，總 token 與費用會接近上述的 **2～3 倍**（例如單次 $0.09 → 約 $0.27、單次 $0.70 → 約 $2.10）。
- **僅 OpenAI 部分**：日報流程還使用 XAI(Grok)、Gemini、OpenRouter、Apify 等，總成本會高於此處僅 OpenAI 的估算。

---

## 5. 如何取得真實用量（建議）

- 在 **OpenAI 使用量 / 帳單頁** 依模型與時間篩選，對照單次執行日報的時段，即可得到該次實際 token 與費用。
- 若在程式內記錄每次呼叫的 `usage`（prompt_tokens / completion_tokens），可加總得到精確的單次 OpenAI token 數，再乘以官網該模型的單價即可。

---

**總結（僅 OpenAI API、單次日報、未重試）**  
- 粗估 token：約 **10 萬 input、3 萬 output**。  
- **預設 gpt-4o-mini**：約 **$0.03**；改為旗艦則約 **$0.09～$0.70**（以 `OPENAI_MODEL` 為準）。
