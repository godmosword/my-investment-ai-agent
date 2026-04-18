# Q-Silicon 開發 Context

> 本檔案為與 AI 助手（Claude / Cursor / Gemini 等）協作時的 context load。
> 每次新 session 起始時，請將本檔內容貼入或 reference。

---

## 行為準則（Behavior Rules）

你是協助 Q-Silicon 平台開發的工程夥伴。請嚴格遵守以下準則：

1. **先看代碼再給建議**：若要修改或 refactor 現有模組，先用檔案讀取工具
   確認實際實作，不憑架構直覺猜測。
2. **不確定時明說**：不懂就說「需要確認」，不要用專業術語掩蓋不確定性。
3. **Trade-off 必須雙面列出**：提出方案時必須同時寫出成本、風險、
   替代方案，不只推銷單一解法。
4. **對 LLM-in-the-loop 保持懷疑**：新增 LLM 呼叫前先問「能否用
   deterministic Python 解決」，預設 deterministic 優先。
5. **不寫示範代碼就承諾**：不保證代碼正確性，除非已對照現有 schema、
   import、函式簽名。

---

## 工程紅線（Immutable Engineering Rules）

1. **格式與邏輯分離**：LLM 負責文字邏輯，Python 負責結構組裝。
   LLM 不得參與 JSON 修復或 HTML 排版。
2. **Fail-Hard Gate**：`report_html_gates.py` 等硬核檢查不通過直接報錯，
   不依賴 LLM 自我修復。
3. **Degradation Safety**：工具/API 呼叫必須有 timeout 與 exception
   handling，異常時回傳空值而非阻斷 Graph 主線程。Graph 必須走到 END。
4. **Slim Schema 原則**：LLM 輸出的 Pydantic model 只包含「必須由 LLM
   生成」的文字欄位；數字、價格、時間等客觀資料由 Python 從 `raw_data`
   填入，不給 LLM 生成空間。

---

## 現有代碼庫狀態（2026-04）

- **主 repo**：`my-investment-ai-agent`（Python 88.7%, 649+ commits）
- **核心管線**：`main.py` 雙 ThreadPoolExecutor 並行 Crypto / AI 兩軌
- **引擎**：CrewAI（legacy，逐步退役）+ LangGraph（主力，Phase 3 重構中）
- **輸出**：Telegram HTML + 可選 BigQuery
- **前端**：`data-verification-ui/`（React + Vite PWA，含 `/terminal` 路由）
- **Profile 系統**：`full` / `lite` / `crypto-only`，透過 `REPORT_PROFILE`
  與 `BRIEF_LAYOUT_FILE` 驅動（Phase 1–4d 已完成）

---

## 進行中（Phase 3.5）

- **`final_formatter_node`**：已用 `CryptoFormatterNarrative` Slim Schema
  + `_assemble_crypto_section` Python 組裝取代 CrewAI formatter 路徑。
- **Reviewer Loop**：`trade_picker_node` → `reviewer_node` 閉環開發中。
  Reviewer 僅查核「邏輯矛盾」與「幻覺標的」，**不查格式**。
  有 Hard Cap 與降級路徑。

---

## 下一階段方向（Q-Silicon Terminal）

目標是把現有日報演化為入口網站的一個板塊，逐步擴展為五模組平台：

```
Q-Silicon Terminal (Portal)
├── daily-brief         （現有 my-investment-ai-agent 演化）
├── investment-analysis （個股深度／財報／valuation）
├── position-management （倉位／風控／執行意圖）
├── industry-trends     （半導體／AI／地緣政治 thematic）
└── quant-trading       （訊號／回測／盤中監控）
```

### 架構原則

- **暫不拆分 repo**：全部在 `my-investment-ai-agent` 內演化。
- 代碼用 `qsilicon/` package 結構組織，為未來可能的拆分預鋪管線。
- 模組間**禁止互相 import**，僅透過 `qsilicon.core.*` 或 API 溝通。
- 共用層（auth、schemas、tools）集中在 `qsilicon.core`。
- Terminal Portal 是 thin frontend + API gateway，不塞業務邏輯。
- 先做自用；多用戶 / auth 是後期考量。

---

## 本次 Session 任務

<在此填入具體任務，例如：>

- [ ] 實作 `graph/graph_nodes.py` 的 `reviewer_node` 與反思路由
- [ ] 將 `templates/telegram_report.j2` 拆分為原子模板
- [ ] 建立 Terminal 前端骨架（五模組 placeholder）
- [ ] 其他：_______________
