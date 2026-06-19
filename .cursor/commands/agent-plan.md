# Agent Plan（規劃 + 審核）

**本 slash command 啟用 Agent Orchestration workflow**（一般對話不會自動套用）。

依 [`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md) 的 **`/agent-plan` 流程**執行。本指令**只規劃、不實作**（除非使用者明確要求跳過審核直接做）。

**Q-Silicon 以本 repo** [`.cursor/commands/`](.) **與 `docs/AGENT-WORKFLOW.md` 為準**（Claude Code 副本見 `~/.claude/commands/`）。

## 你要做的事

### 0. Bootstrap

- 讀 [`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md)（Meta）
- 讀 [`CLAUDE.md`](../../CLAUDE.md)、任務相關 [`TODOS.md`](../../TODOS.md)（**檔首狀態可能落後**，以 `CHANGELOG.md`／程式為準）
- Graph → `scripts/verify_graph_gate.sh`；Portal → `data-verification-ui/`；架構 → `docs/architecture/Terminal_Master_Plan.md`

### 1. Leader 撰寫 Draft Plan

- 使用 AGENT-WORKFLOW 的 **Plan 模板**（Goal、Scope、Task DAG、Files、Verification、Model routing、Risks）
- 每個子任務標註 **L0–L3** 與建議 **model slug**
- **Plan 產物：**
  - **Cursor Plan mode**：CreatePlan 產出的 plan 檔（優先）
  - **否則**：寫入 `/tmp/agent-plan-<unix_ts>.md`（`date +%s`）

### 2. 並行 Review（必做，各一輪）

- **架構／紅線**：Task `architect` 或 `code-reviewer`（`readonly: true`）— 範圍、架構、Q-Silicon 紅線（無數據幻覺、Gate、Telegram HTML）、過度工程
- **工程**：`codex exec -m gpt-5.5 -c model_reasoning_effort="medium"` 或 Task + `gpt-5.5-medium` — 可執行性、**驗證矩陣命令**、漏檔、測試
- 若 plan 讓 LLM 自行算價／弱化 Gate → 標 **CRITICAL**
- 兩路衝突或邊界模糊 → 可選 **Fable 5**（`claude-fable-5-thinking-medium`）第三意見

工程審 codex 範例（Claude Code 環境）：

```bash
codex exec -m gpt-5.5 -c model_reasoning_effort="medium" "你是 Q-Silicon 資深工程審查者。審查計劃的可行性、驗證命令（README/AGENT-WORKFLOW 矩陣）、漏檔、紅線違反。只審查、不改檔。計劃如下：

$(cat /tmp/agent-plan-<ts>.md)"
```

### 3. Leader 綜合

對照摘要表：

| 來源 | 關鍵意見 | 採納決定 |
|------|----------|----------|
| Leader | … | — |
| 架構審 | … | 採納 / 不採納 |
| 工程審 | … | 採納 / 不採納 |

產出 **Approved Plan**（含需使用者決策項）→ 覆寫 plan 檔 → 明確寫：**下一步請用 `/agent-action`**

### 4. 審稿缺席

Codex／子 agent 失敗 → 摘要表註明缺席；Leader 定稿但**不可省略** Graph gate／PWA E2E（若 scope 觸及）。

### 5. CRITICAL 與 Plan mode

- **CRITICAL**：依 [`review-user-choice.mdc`](../rules/review-user-choice.mdc) 用 **A/B/C**；僅 **A** 才改檔
- **Cursor Plan mode**：以系統 plan confirm 為準（與「全程自主」並存時 Plan mode 優先）
- 非 Plan mode：全程自主，**不要**逐步詢問批准（CRITICAL 除外）

## 禁止

- 不要 commit / push
- 不要跳過 Review 直接實作（使用者說「直接做」除外）

## 輸出語言

繁體中文（技術 slug／路徑可保留英文）。
