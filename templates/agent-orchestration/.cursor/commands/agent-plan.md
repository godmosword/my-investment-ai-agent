# Agent Plan（規劃 + 審核）

**本 slash command 啟用 Agent Orchestration workflow**（一般對話不會自動套用）。

依 [`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md) 的 **`/agent-plan` 流程**執行。本指令**只規劃、不實作**（除非使用者明確要求跳過審核直接做）。

**Domain（Bootstrap、紅線、驗證矩陣）：** [`docs/AGENT-DOMAIN.md`](../../docs/AGENT-DOMAIN.md)

## 你要做的事

### 0. Bootstrap

- 讀 [`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md)（Meta）
- 讀 [`docs/AGENT-DOMAIN.md`](../../docs/AGENT-DOMAIN.md)（Bootstrap 表、紅線、驗證矩陣）
- 依 Domain「依任務加讀」表補充 context

### 1. Leader 撰寫 Draft Plan

- 使用 AGENT-WORKFLOW 的 **Plan 模板**（Goal、Scope、Task DAG、Files、Verification、Model routing、Risks）
- 每個子任務標註 **L0–L3** 與建議 **model slug**
- **Plan 產物：**
  - **Cursor Plan mode**：CreatePlan 產出的 plan 檔（優先）
  - **否則**：寫入 `/tmp/agent-plan-<unix_ts>.md`（`date +%s`）

### 2. 並行 Review（必做，各一輪）

- **架構／紅線**：Task `architect` 或 `code-reviewer`（`readonly: true`）— 範圍、架構、**AGENT-DOMAIN 紅線**、過度工程
- **工程**：Task + `gpt-5.5-medium`（或 codex，Claude Code 環境）— 可執行性、**Domain 驗證矩陣命令**、漏檔、測試
- 若 plan 違反 Domain 紅線 → 標 **CRITICAL**
- 兩路衝突或邊界模糊 → 可選 **Fable 5**（`claude-fable-5-thinking-medium`）第三意見

### 3. Leader 綜合

對照摘要表：

| 來源 | 關鍵意見 | 採納決定 |
|------|----------|----------|
| Leader | … | — |
| 架構審 | … | 採納 / 不採納 |
| 工程審 | … | 採納 / 不採納 |

產出 **Approved Plan**（含需使用者決策項）→ 覆寫 plan 檔 → 明確寫：**下一步請用 `/agent-action`**

### 4. 審稿缺席

子 agent 失敗 → 摘要表註明缺席；Leader 定稿但**不可省略** Domain 驗證矩陣中的必要項。

### 5. CRITICAL 與 Plan mode

- **CRITICAL**：若有 `review-user-choice.mdc`，用 **A/B/C**；僅 **A** 才改檔
- **Cursor Plan mode**：以系統 plan confirm 為準
- 非 Plan mode：全程自主，**不要**逐步詢問批准（CRITICAL 除外）

## 禁止

- 不要 commit / push
- 不要跳過 Review 直接實作（使用者說「直接做」除外）

## 輸出語言

依 [`docs/AGENT-DOMAIN.md`](../../docs/AGENT-DOMAIN.md) § 專案識別（技術 slug／路徑可保留英文）。
