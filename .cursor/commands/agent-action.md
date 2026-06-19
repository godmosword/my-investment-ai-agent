# Agent Action（拆分 + Task 派工 + 驗證）

**本 slash command 啟用 Agent Orchestration workflow**（一般對話不會自動套用）。

依 [`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md) 的 **`/agent-action` 流程**執行。本指令**負責實作與驗證**，不重做完整 Plan（除非計畫缺失或執行中 blocked）。

## 前置條件

- 已有 **Approved Plan**（來自 `/agent-plan`、Cursor plan 檔、`/tmp/agent-plan-*.md`，或使用者貼上的計畫）
- 若無計畫，先簡短列出缺什麼，建議 `/agent-plan`

## 你要做的事

### 0. Bootstrap

同 [`agent-plan.md`](agent-plan.md) §0；可見行為變更完成前對齊 `CHANGELOG.md` ↔ `TODOS.md`。

### 1. Leader 讀 Approved Plan

- 確認 Task DAG、依賴、Model routing 表

### 2. 拆任務並派工（Cursor Task）

依 Plan 的 **L0–L3** 與 AGENT-WORKFLOW 路由表，用 **Task** 派子 agent（**不要**用 `codex exec`／`claude -p` 子 process 做實作委派——子 process 無 Cursor 工具鏈）。

| 級別 | 判準 | Cursor 派工 |
|------|------|-------------|
| L3 架構／Graph／Reviewer | 跨模組、高風險 | Leader 或 Task + `architect` / Opus slug |
| L2 多檔實作 | 模式固定 | Task + `claude-4.6-sonnet-medium-thinking` 或 `composer-2.5-fast` |
| L1 單檔 | 範圍明確 | Task `explore` 後 Leader，或 Sonnet slug |
| L0 命令 | lint／test／腳本 | Task `shell` 或 `grok-build-0.1` |

**禁止：**

- 多 agent **同時改同一檔**
- **haiku** 或廉價模型改 `tools.py`、`crew.py`、`validate_report`、API 契約、戰報／Telegram 管線
- **gpt-5.4** 作為固定路由（已淘汰；Codex 僅 plan 審稿可選）

改動 <10 行且無架構影響 → Leader 直接做，不派子 agent。

每個子任務 prompt 必含：**Goal、Context paths、Constraints（含 Q-Silicon 紅線）、Do NOT、Verification、Deliverable**（見 AGENT-WORKFLOW 模板）。

### 3. Leader 整合

- 合併子 agent 結果、解衝突、**最小 diff**
- 對外介面行為不可改變（除非 Plan 明確要求）

### 4. Verify（必跑）

依 [`docs/AGENT-WORKFLOW.md` § 驗證矩陣](../../docs/AGENT-WORKFLOW.md#驗證矩陣) 與 Plan 列出的命令：

| 觸及 | 最小 |
|------|------|
| Python 通用 | `ruff check .` + `python3 -m pytest -m smoke -q` |
| Graph／Reviewer | `./scripts/verify_graph_gate.sh` |
| Portal | `cd data-verification-ui && npm run lint && npm run test:e2e` |
| API router | 相關 `tests/api/test_*.py` |
| 契約 | `./scripts/ci_terminal_contract_check.sh` |

未全綠不得宣稱完成；回報逐項對照。

### 5. Review diff

- Python → `python-reviewer`；TS/JS → `typescript-reviewer`；通用 → `code-reviewer`

### 6. 文件同步（若 scope 含可見行為／隊列／指令）

- 更新 `CHANGELOG.md` 與 `TODOS.md`；導航變更同步 `CLAUDE.md`／`README.md`

### 7. Ship（僅使用者要求）

- **預設不** commit / push
- 使用者說「commit」→ 只 stage **本次相關檔**；禁止 `git add -A`
- 使用者說「ship／push main」→ scoped tests 全綠後依 [`AGENTS.md`](../../AGENTS.md) 直推 main
- 完整 VERSION + CHANGELOG ship → gstack **`/ship`**

### 8. CRITICAL

依 [`review-user-choice.mdc`](../rules/review-user-choice.mdc)：**CRITICAL-n** + Fix + A/B/C；僅 **A** 改檔。

### 9. 委派缺席

Task／codex 失敗 → Leader 接手，分配表註明，不中斷流程。

## 禁止

- 不要無 Plan 擅自擴大 scope
- 不要跳過 Verify 就宣稱完成

## 輸出語言

繁體中文。
