# Q-Silicon 開發 Context

> 本檔案為與 AI 助手（Claude / Cursor / Gemini 等）協作時的 context load。
> 每次新 session 起始時，請將本檔內容貼入或 reference。
>
> **`docs/architecture/` 判讀（Phase 0）**：「研究 vs 已交付」與矩陣 ✅／🟡 收斂規則見 [`Terminal_Master_Plan.md`](Terminal_Master_Plan.md) **§0** 與其下 **Phase 0** 小節；本檔不重複維護版本年表。**Phase 1（隊列 27）** staging 執行稿見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](../STAGING_CURRENT_AFFAIRS_SMOKE.md)（人類關帳；非 CI）。

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

## 現有代碼庫狀態（請對照 CHANGELOG／實際檔案，勿僅依本段）

> **維護方式**：以 `CHANGELOG.md`、最近一次 merge 與 `git log` 為準；本節僅列**穩定錨點**，細節日期會漂移。

- **主 repo**：Q-Silicon investment-ai-agent（Python + LangGraph 管線 + PWA）
- **核心管線**：`main.py` 雙 ThreadPoolExecutor（Crypto / AI）
- **引擎**：LangGraph 為主；CrewAI legacy 逐步收斂
- **輸出**：Telegram HTML（`validate_report`／`report_html_gates.py` 白名單）
- **前端**：`data-verification-ui/`（Vite PWA；Portal 模組路由含 `/briefs`、`/terminal`）
- **Portal API 錨點（對齊 CHANGELOG 2026-05-04／2026-05-05／2026-05-06）**：PWA 取數一律走 [`data-verification-ui/src/hooks/useApi.js`](../../data-verification-ui/src/hooks/useApi.js) + [`lib/siliconApiHeaders.js`](../../data-verification-ui/src/lib/siliconApiHeaders.js)（`X-Q-Silicon-Key`）；後端 HTTP 路由以 [`api_routers/`](../../api_routers/) 增量掛載、[`api.py`](../../api.py) `include_router` 組裝。架構驗收清單見 [`TERMINAL_FRONTEND_PLAN.md`](TERMINAL_FRONTEND_PLAN.md) §驗收清單。**2026-05-05**：結構化報告區塊可選 **`data-section`**（`visualization_plan` §3）；`/positions` 最小頁接 **`/api/execution-intents`**；paper tick 可選 **BQ 稽核列**（`PAPER_EXECUTION_AUDIT_TABLE`，見根目錄 `CHANGELOG` **2026-05-05**）。
- **Profile**：`full` / `lite` / `crypto-only`（`REPORT_PROFILE`、`BRIEF_LAYOUT_FILE`）

---

## 已落地／維護中（Phase 3.5）

- **`final_formatter_node`**：已用 `CryptoFormatterNarrative` Slim Schema
  + `_assemble_crypto_section` Python 組裝取代 CrewAI formatter 路徑。
- **Reviewer Loop**：第一版已於 **2026-04-21** 落地於 LangGraph native trade picker 路徑：
  `trade_picker → python_validate → llm_reviewer → retry/degrade → final_formatter`。
  Reviewer 僅查核 trade 邏輯矛盾與幻覺標的，**不查格式**、不取代
  `validate_report`／Telegram HTML Gate；後續變更依
  [`REVIEWER_LOOP_DESIGN.md`](REVIEWER_LOOP_DESIGN.md) 與
  [`GRAPH_REVIEWER_CHANGE_CHECKLIST.md`](GRAPH_REVIEWER_CHANGE_CHECKLIST.md)
  的 flag／測試維護。

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

> **模板**：每次開工在此填入當日可驗收切片；完成後刪除或勾選。長線 backlog 以 `TODOS.md`／`Terminal_Master_Plan.md` 為準。

- （例）___________
- （例）___________

---
