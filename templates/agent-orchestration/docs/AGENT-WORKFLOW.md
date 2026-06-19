# Agent 編排 Workflow（Meta）

本文件定義 **Meta layer**：誰規劃、誰審核、誰實作、誰驗證。  
**Domain**（Bootstrap、紅線、驗證矩陣、Ship）見同 repo 的 [`docs/AGENT-DOMAIN.md`](AGENT-DOMAIN.md)。

**入口指令（Cursor slash commands）：**

| 指令 | 用途 |
|------|------|
| **`/agent-plan`** | 規劃 + **架構／工程雙審**（預設不實作） |
| **`/agent-action`** | 依 Approved Plan **Task 派工** + Verify +（可選）Ship |

**啟用範圍：** 只有打出上述指令時才進入 Agent Orchestration 模式。一般 chat 不會自動拆任務、派子 agent。

規則精簡版： [`.cursor/rules/agent-orchestration.mdc`](../.cursor/rules/agent-orchestration.mdc)（`alwaysApply: false`）。

**與 gstack 分工：**

| 情境 | 用哪個 |
|------|--------|
| 大 feature、要自動多輪 plan 審核 | `/autoplan`（gstack skill） |
| 自訂 Plan + 雙審 + 可控切片 | **`/agent-plan`** |
| 已有 Approved Plan 要落地 | **`/agent-action`** |
| bump VERSION + CHANGELOG + push main | `/ship`（gstack skill） |

可攜模板來源：[`templates/agent-orchestration/`](../../templates/agent-orchestration/)（Q-Silicon monorepo 內）。

---

## 兩層架構

| 層級 | 文件 | 內容 |
|------|------|------|
| **Meta** | 本文件 | 模型分工、`/agent-plan` & `/agent-action`、路由、prompt 模板 |
| **Domain** | [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md) | Bootstrap、紅線、驗證矩陣、Ship、專案反模式 |

原則：**Meta 管「誰做」；Domain 管「做什麼、怎麼驗收」。**

---

## Bootstrap（Plan / Action 共通）

大任務或不熟模組時 **必讀**（具體路徑見 [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md) § Bootstrap）。

可見行為變更：依 Domain 的 **Docs sync** 段落更新 changelog／待辦／導航。

---

## CRITICAL 互動

遇 CRITICAL（資料遺失、安全漏洞、無法回復的破壞、需明確授權才改程式）：

1. 列出發現（一行問題、一行建議修復）
2. 每題固定選項：**A** 現在修／**B** 已知悉暫不修／**C** 誤判略過
3. **僅 A** 才改檔

格式：`CRITICAL-n` + Fix +「請回覆 **CRITICAL-n 選 A / B / C**」

（若 repo 有 `.cursor/rules/review-user-choice.mdc`，與其對齊。）

---

## 流程總覽

```
/agent-plan          /agent-action              （使用者要求時）
    │                     │
    ▼                     ▼
 Plan ──► Review ──► Approved Plan ──► Implement ──► Verify ──► Ship
(Leader) (Arch+Eng)                  (Task 派工)     (矩陣)    (可選)
```

| 階段 | 指令 | Leader | 子 agent |
|------|------|--------|----------|
| 規劃 | `/agent-plan` | 當前 session 主模型 | — |
| 審核 | `/agent-plan` | — | 架構 readonly + 工程並行 |
| 實作 | `/agent-action` | Leader 拆任務 | Cursor **Task** + model slug |
| 驗證 | `/agent-action` | Leader 整合後 | `shell`；必要時 reviewer |
| 交付 | `/agent-action` | Leader | commit/push **僅使用者明確要求** |

**Cursor Plan mode：** 以系統 plan confirm 為準（與「全程自主」並存時，Plan mode 優先）。

**Plan 產物路徑：**

- **Cursor**：CreatePlan 產出的 plan 檔，或 `.cursor/plans/*.plan.md`
- **Claude Code**：`/tmp/agent-plan-<unix_ts>.md`
- **`/agent-action`** 接受：plan 檔路徑、`@plan`、或使用者貼上的 Approved Plan

---

## `/agent-plan`（規劃 + 審核）

> 指令檔：[`.cursor/commands/agent-plan.md`](../.cursor/commands/agent-plan.md)

### 目標

產出 **Approved Plan**，供 `/agent-action` 執行。**預設不寫 code、不 commit。**

### 步驟

1. **Bootstrap**（[`AGENT-DOMAIN.md`](AGENT-DOMAIN.md)）
2. **Leader 撰寫 Draft Plan**（見 [Plan 模板](#plan-模板)）
3. **並行 Review（必做，各一輪）**
   - **架構／紅線**：Task `architect` 或 `code-reviewer`（`readonly: true`）— 範圍、架構、Domain 紅線、過度工程
   - **工程**：Task + `gpt-5.5-medium` 或 codex — 可執行性、驗證命令、漏檔、測試
   - **Fable 5**（`claude-fable-5-thinking-medium`）：**備選** — 僅兩路衝突或邊界模糊時
4. **Leader 綜合** → **Approved Plan** → 提示 **`/agent-action`**

Plan 若弱化 Domain 紅線 → 審稿標 **CRITICAL**。

### 審稿缺席

子 agent 失敗 → 摘要表註明缺席；Leader 仍須保留 Domain 驗證矩陣中的必要項。

---

## `/agent-action`（拆分 + 實作）

> 指令檔：[`.cursor/commands/agent-action.md`](../.cursor/commands/agent-action.md)

### 前置

- 已有 **Approved Plan**
- 無 plan → 簡短說明缺什麼，建議 `/agent-plan`

### 步驟

1. 讀 Approved Plan（Task DAG、Model routing）
2. **Cursor Task 派工**（見 [複雜度分級](#複雜度分級-l0l3)）
3. Leader **整合**（最小 diff；**禁止**多 agent 同檔）
4. **Verify**（[`AGENT-DOMAIN.md`](AGENT-DOMAIN.md) § 驗證矩陣）
5. 整合後 **code-reviewer**／語言 reviewer（依變更語言）
6. 可見行為變更 → Domain § Docs sync
7. **Ship**（僅使用者要求）：只 stage 相關檔；預設不 commit/push

### 派工規則

- ✅ 可並行：不同檔案／目錄
- ❌ 禁止：多 agent 同時改同一檔
- 改動 &lt;10 行且無架構影響 → Leader 直接做
- 遵守 Domain § **Protected paths / models**（若有）

### Cursor vs Claude Code 委派

| 環境 | 實作委派 |
|------|----------|
| **Cursor** | **Task** 子 agent（`explore`、`generalPurpose`、`shell`、reviewer 等） |
| **Claude Code** | Plan 審可用 codex；實作以 Leader 為主，**勿**指望子 process 直接改 IDE 工作區 |

---

## 模型 slug 對照表

Task 的 `model` **只能**用 Cursor 允許的 slug：

| UI / 口語 | slug | 主要用途 |
|-----------|------|----------|
| Composer 2.5 | `composer-2.5-fast` | Leader、Plan、整合 |
| Opus 4.8 Thinking Medium | `claude-opus-4-8-thinking-medium` | Plan 架構審、L3 |
| GPT 5.5 Medium | `gpt-5.5-medium` | Plan 工程審、TS/React diff review |
| Sonnet 4.6 Thinking Medium | `claude-4.6-sonnet-medium-thinking` | L2、文案 |
| Grok 4.3 | `grok-4.3` | explore |
| Grok Build 0.1 | `grok-build-0.1` | shell、批次命令 |
| Fable 5 | `claude-fable-5-thinking-medium` | 備選 Plan 第三意見 |

slug 不可用時：**不要**替換；Leader 代做並告知使用者。

---

## 複雜度分級（L0–L3）

| 級別 | 特徵 | `/agent-action` |
|------|------|-----------------|
| **L3** | 跨模組、schema、高風險 | Leader 或 Opus 4.8 |
| **L2** | 多檔、模式固定 | Sonnet 4.6 或 Composer |
| **L1** | 單檔 routine | explore 後 Leader 改 |
| **L0** | 純命令 | `shell` 或 Grok Build |

### 任務類型路由

| 任務類型 | 首選 |
|----------|------|
| Plan 撰寫 | Leader |
| Plan 架構審 | `architect` readonly 或 Opus |
| Plan 工程審 | GPT 5.5 / codex |
| 探索 codebase | Task `explore` |
| 高風險核心路徑 | Leader 或 Opus；跑 Domain 對應 gate |
| 前端／UI | Sonnet 4.6 或 Composer；跑 lint + e2e（若 Domain 有） |
| verify / CI 命令 | `shell` |
| git commit | **Leader only** |

---

## Plan 模板

```markdown
## Goal
（一句話）

## Scope / Out of scope
- In: ...
- Out: ...

## Task DAG
- [ ] T1（L2, claude-4.6-sonnet-medium-thinking）— 依賴：無 — 可並行：T2
- [ ] T2（L0, shell）— 依賴：T1

## Files likely touched
- path/to/file

## Verification
- （從 AGENT-DOMAIN 驗證矩陣挑選具體命令）

## Model routing
| ID | 任務 | Level | Model slug | Subagent |

## Risks & rollback
- ...

---
## Review summary
- 架構審：...
- 工程審：...
- Fable 5（若有）：...
- **Approved / 待決策：** ...
```

---

## 子任務 Prompt 模板（Task 派工）

```markdown
## Goal
（單一可驗收目標）

## Context
- Repo: <project-name>
- Approved Plan task ID: T1
- Related files: ...
- Domain: docs/AGENT-DOMAIN.md

## Constraints
- 最小 diff；遵守 AGENT-DOMAIN 紅線
- （面向使用者的產出語言，見 Domain）

## Do NOT
- commit / push（除非 Leader 明確授權）
- 修改：...（範圍外）

## Verification
- ...

## Deliverable
- 改了哪些檔、摘要、未解問題
```

---

## Ship 政策（預設 Meta）

| 情境 | 行為 |
|------|------|
| 預設 | **不** commit / push |
| 使用者說「commit」 | 只 stage 本次相關檔；禁止 `git add -A` |
| 使用者說「ship／push main」 | scoped tests 全綠後依 **Domain § Ship** |
| bump VERSION + 完整 ship | gstack **`/ship`** |

專案若直推 main、PR 流程、或 branch protection，寫在 [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md)。

---

## 反模式（Meta）

| 反模式 | 為什麼 |
|--------|--------|
| 用 `/agent-action` 從零規劃大功能 | 缺審核、scope 漂移 |
| 用 `/agent-plan` 卻偷偷實作 | 指令語意混淆 |
| 多 agent 改同一檔 | 衝突 |
| `git add -A` | 混 WIP |
| 跳過 Domain 驗證矩陣 | 回歸 |

專案特有反模式見 [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md)。

---

## 相關文件

- [`.cursor/commands/agent-plan.md`](../.cursor/commands/agent-plan.md)
- [`.cursor/commands/agent-action.md`](../.cursor/commands/agent-action.md)
- [`.cursor/rules/agent-orchestration.mdc`](../.cursor/rules/agent-orchestration.mdc)
- [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md)

---

## 修訂紀錄

| 日期 | 說明 |
|------|------|
| 2026-06-16 | 可攜 Meta 初版（Domain 外置至 AGENT-DOMAIN.md） |
