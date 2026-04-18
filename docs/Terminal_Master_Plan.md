# Terminal 總表（中段落地 · 長線 Portal）

**目的**：用**單一導覽頁**銜接「已交付的中段能力」與「五模組 Q-Silicon Terminal」長線規劃，並收斂 [`docs/architecture/`](architecture/) 三份設計稿的**維護者／AI 看法**（與實作對照時請以程式與 CHANGELOG 為準）。

| 層級 | 文件 | 角色 |
|------|------|------|
| 中段（已落地為主） | [`TERMINAL_MID_TIER_ROADMAP.md`](TERMINAL_MID_TIER_ROADMAP.md) | M1–M5：溯源、輪詢／SSE、quote、紙上 tick；對齊 [`BLOOMBERG_ALIGNMENT.md`](BLOOMBERG_ALIGNMENT.md) |
| 長線（規劃／協作 context） | [`architecture/AI_CONTEXT.md`](architecture/AI_CONTEXT.md) | 與 AI 協作準則、工程紅線、五模組願景、`qsilicon/` 邊界 |
| 長線（Graph） | [`architecture/REVIEWER_LOOP_DESIGN.md`](architecture/REVIEWER_LOOP_DESIGN.md) | `trade_picker` → reviewer：Python 先擋、LLM 只查邏輯；cap／降級／BQ |
| 長線（PWA／API） | [`architecture/TERMINAL_FRONTEND_PLAN.md`](architecture/TERMINAL_FRONTEND_PLAN.md) | `data-verification-ui` 模組化、FastAPI 路由分層、master key、MVP 順序 |
| 索引 | [`ADR_INDEX.md`](ADR_INDEX.md) | ADR／設計稿；含 **`architecture/`** 列 |
| 根導覽 | [`../CLAUDE.md`](../CLAUDE.md) §5 | Terminal 長線規劃表格（與本檔並用） |

---

## 1. 執行順序（維護者）

1. **穩住日報可信與 Gate**（與 Terminal 並行但不可讓步）：對齊 `TODOS.md`「維護者意見」與 `validate_report` 契約。
2. **中段產品節奏**：以 `TERMINAL_MID_TIER_ROADMAP` 已交付能力為錨；新增能力須有 API／PWA 契約測試或 Playwright 再擴張。
3. **長線 Portal**：依 `TERMINAL_FRONTEND_PLAN` 的 **Shell → daily-brief → position → …** 順序切片；避免一次重構 `api.py` 單體—**incremental `APIRouter`** 較可 review。

---

## 2. 對 `architecture/` 三檔的看法（AI／維護者）

以下為**設計層評論**，實作時請對照目前 `graph/`、`data-verification-ui/`、`api.py` 真實狀態。

### [`AI_CONTEXT.md`](architecture/AI_CONTEXT.md)

- **優點**：行為準則（先讀碼、trade-off 雙面、LLM 懷疑論）與**格式／邏輯分離**、Fail-Hard Gate、Slim Schema 紅線，與本 repo 的 `validate_report` 文化一致；五模組 Terminal 願景與「暫不拆 repo」務實。
- **建議**：檔內「現有代碼庫狀態」會隨時間漂移，新 session 應以 **CHANGELOG／TODOS 已交付摘要** 校正；「本次 Session 任務」區塊宜當**模板**，避免被誤當唯一 backlog。
- **風險**：`qsilicon/` 模組邊界若尚未全面落地，口頭「禁止跨模組 import」需搭配 CI 或目錄約束，否則易流於文件自律。

### [`REVIEWER_LOOP_DESIGN.md`](architecture/REVIEWER_LOOP_DESIGN.md)

- **優點**：**Layer 1 Python / Layer 2 LLM** 分工正確（成本、可重現性、幻覺標的）；Hard cap 與降級路徑符合日報延遲預算；BQ `reviewer_log` 利於事後調參。
- **建議**：設計稿附的「實作 Prompt」曾寫 **不得改 `schemas.py`**—若 `TradeIdea`／state 需共用欄位，應在 PR 中**明確修訂**該禁令，改為「延長式欄位 + 測試／Gate 更新」，避免 graph 與 schema 分叉。
- **風險**：Reviewer 僅查邏輯不查格式—需確保 **Telegram 出口仍只經** `validate_report`／模板，避免 reviewer 繞過 HTML 白名單。

### [`TERMINAL_FRONTEND_PLAN.md`](architecture/TERMINAL_FRONTEND_PLAN.md)

- **優點**：**延續 Vite PWA** 相对 Next 重寫更合現況；`modules/{name}` + `shared/` 與後端「模組經 API 溝通」對齊；master key 自用足夠。
- **建議**：路由表（如 `/` → `/briefs`）必須與**目前** `App.jsx`／`Router` 對齊後再動大改，避免與既有 `/terminal`、Report 深連結衝突；FastAPI 拆 `APIRouter` 宜 **逐 router PR**，並同步 [`ENV_TEMPLATE.txt`](../ENV_TEMPLATE.txt)／[`DASHBOARD_CONTRACT.md`](DASHBOARD_CONTRACT.md)。
- **風險**：五模組 stub 若一次加滿但無 E2E，易形成「壳大身薄」—每個模組至少保留 **一條 smoke 路徑**（mock API 亦可）。

---

## 修訂紀錄

- **2026-04-18**：初版 — 總表連結、`architecture/` 三檔看法；與 [`TODOS.md`](../TODOS.md)、[`CHANGELOG.md`](../CHANGELOG.md) 對齊。
