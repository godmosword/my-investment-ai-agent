# Agent 編排 Workflow（Q-Silicon）

本文件定義 **Meta layer**：誰規劃、誰審核、誰實作、誰驗證。  
Domain 具體模組與驗證命令見本文件 **§ Domain** 與 [`README.md`](../README.md) CI 段落。

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

Claude Code 使用者：指令副本亦在 `~/.claude/commands/`；**以本 repo** [`.cursor/commands/`](../.cursor/commands/) **與本文件為準**。

---

## 兩層架構

| 層級 | 文件 | 內容 |
|------|------|------|
| **Meta** | 本文件 | 模型分工、`/agent-plan` & `/agent-action`、路由、prompt 模板 |
| **Domain** | [`CLAUDE.md`](../CLAUDE.md)、[`Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md) | 模組表、Phase、紅線、具體驗證命令 |

原則：**Meta 管「誰做」；Domain 管「做什麼、怎麼驗收」。**

---

## Bootstrap（Plan / Action 共通）

大任務或不熟模組時 **必讀**：

1. [`CLAUDE.md`](../CLAUDE.md) — 紅線、模組、發佈慣例
2. [`TODOS.md`](../TODOS.md) — 隊列（**檔首同步狀態可能落後**，事實以 `CHANGELOG.md`／程式為準）
3. [`README.md`](../README.md) — 驗證命令、CI 對齊
4. 依任務加讀：
   - Graph／Reviewer → [`REVIEWER_LOOP_DESIGN.md`](architecture/REVIEWER_LOOP_DESIGN.md)、`scripts/verify_graph_gate.sh`
   - Portal／PWA → [`TERMINAL_FRONTEND_PLAN.md`](architecture/TERMINAL_FRONTEND_PLAN.md)、[`PORTAL_SHIP_CHECKLIST.md`](PORTAL_SHIP_CHECKLIST.md)
   - 架構優先順序 → [`Terminal_Master_Plan.md`](architecture/Terminal_Master_Plan.md)

可見行為變更：**`CHANGELOG.md` ↔ `TODOS.md` 雙向對齊**；指令／導航變更同步 `CLAUDE.md`／`README.md`。

---

## Q-Silicon 紅線（Plan 審核與 Action 約束）

| 紅線 | 說明 |
|------|------|
| **無數據幻覺** | 禁止 LLM 自行推導／捏造報價、指標、日期；實盤數據由 Python 抓取並注入 Context |
| **戰報 Telegram HTML** | 僅允許 `<b>` `<i>` `<u>` `<s>` `<code>` `<blockquote>` `<a>`；四大區塊順序固定 |
| **Tool 快取** | 新增 `tools.py` 等必須 `_get_cache` / `_set_cache` |
| **main.py 雙線程** | `ThreadPoolExecutor`（Crypto + AI）須執行緒安全 |
| **戰報語氣** | 機構簡報腔；禁止對專業讀者做「什麼是 VIX／RSI」式教學 |
| **Gate／Schema** | 不得以模糊敘述取代 `validate_report`／契約；Graph 變更須過 gate |

Plan 若弱化上述任一項 → 審稿標 **CRITICAL**。

---

## CRITICAL 互動（對齊 `.cursor/rules/review-user-choice.mdc`）

遇 CRITICAL（資料遺失、安全漏洞、無法回復的破壞、需明確授權才改程式）：

1. 列出發現（一行問題、一行建議修復）
2. 每題固定選項：**A** 現在修／**B** 已知悉暫不修／**C** 誤判略過
3. **僅 A** 才改檔

格式：`CRITICAL-n` + Fix +「請回覆 **CRITICAL-n 選 A / B / C**」

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
| 審核 | `/agent-plan` | — | 架構 readonly + 工程（codex／GPT）並行 |
| 實作 | `/agent-action` | Leader 拆任務 | Cursor **Task** + model slug |
| 驗證 | `/agent-action` | Leader 整合後 | `shell`；必要時 `code-reviewer` |
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

1. **Bootstrap**（見上）
2. **Leader 撰寫 Draft Plan**（見 [Plan 模板](#plan-模板)）
3. **並行 Review（必做，各一輪）**
   - **架構／紅線**：Task `architect` 或 `code-reviewer`（`readonly: true`）— 範圍、架構、紅線、過度工程
   - **工程**：`codex exec -m gpt-5.5` 或 Task + `gpt-5.5-medium` — 可執行性、驗證命令、漏檔、測試
   - **Fable 5**（`claude-fable-5-thinking-medium`）：**備選** — 僅兩路衝突或邊界模糊時
4. **Leader 綜合** → **Approved Plan** → 提示 **`/agent-action`**

### 審稿缺席

Codex 失敗 → 摘要表註明「工程審缺席」；Leader 仍須保留驗證矩陣（含 graph gate／E2E 若觸及）。

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
4. **Verify**（[驗證矩陣](#驗證矩陣)）
5. 整合後 **code-reviewer**／**python-reviewer**／**typescript-reviewer**（依語言）
6. 可見行為變更 → 更新 `CHANGELOG.md`／`TODOS.md`
7. **Ship**（僅使用者要求）：只 stage 相關檔；預設不 commit/push

### 派工規則

- ✅ 可並行：不同檔案／目錄
- ❌ 禁止：多 agent 同時改同一檔
- 改動 &lt;10 行且無架構影響 → Leader 直接做
- **禁止**用 haiku／廉價模型改 `tools.py`、`crew.py`、`validate_report`、API 契約、戰報管線

### Cursor vs Claude Code 委派

| 環境 | 實作委派 |
|------|----------|
| **Cursor** | **Task** 子 agent（`explore`、`generalPurpose`、`shell`、reviewer 等） |
| **Claude Code** | 可選 `codex exec` 審 plan；實作仍以 Leader 或 `claude -p` 為輔，**勿**指望子 process 直接改 IDE 工作區 |

---

## 模型 slug 對照表

Task 的 `model` **只能**用 Cursor 允許的 slug：

| UI / 口語 | slug | 主要用途 |
|-----------|------|----------|
| Composer 2.5 | `composer-2.5-fast` | Leader、Plan、整合 |
| Opus 4.8 Thinking Medium | `claude-opus-4-8-thinking-medium` | Plan 架構審、L3 |
| GPT 5.5 Medium | `gpt-5.5-medium` | Plan 工程審、TS/React diff review |
| Sonnet 4.6 Thinking Medium | `claude-4.6-sonnet-medium-thinking` | L2、戰報文案 |
| Grok 4.3 | `grok-4.3` | explore |
| Grok Build 0.1 | `grok-build-0.1` | shell、批次命令 |
| Fable 5 | `claude-fable-5-thinking-medium` | 備選 Plan 第三意見 |

slug 不可用時：**不要**替換；Leader 代做並告知使用者。

**已淘汰於本 repo 路由：** `gpt-5.4` 實作委派、**haiku** 改核心／金融路徑。

---

## 複雜度分級（L0–L3）

| 級別 | 特徵 | `/agent-action` |
|------|------|-------------------|
| **L3** | 跨模組、Graph/Reviewer、首次 schema | Leader 或 Opus 4.8 |
| **L2** | 多檔、模式固定 | Sonnet 4.6 或 Composer |
| **L1** | 單檔 routine | Sonnet 4.6 或 Grok 4.3 explore 後 Leader 改 |
| **L0** | 純命令 | `shell` 或 Grok Build |

### 任務類型路由

| 任務類型 | 首選 |
|----------|------|
| Plan 撰寫 | Leader |
| Plan 架構審 | `architect` readonly 或 Opus |
| Plan 工程審 | GPT 5.5 / codex |
| 探索 codebase | Task `explore` |
| Graph／Reviewer／crew | Leader 或 Opus；必跑 graph gate |
| Portal／PWA | Sonnet 4.6 或 Composer；必跑 lint + e2e |
| 戰報／Telegram HTML | Sonnet 4.6 或 Leader |
| verify / CI 命令 | `shell` |
| git commit | **Leader only** |

---

## 驗證矩陣

依 **變更觸及面** 跑最小集合（未全綠不得宣稱完成）：

| 觸及 | 必跑（最小） |
|------|----------------|
| Python 核心／通用 | `ruff check .` + `python3 -m pytest -m smoke -q` |
| Graph／Reviewer／`crew.py` 管線 | `./scripts/verify_graph_gate.sh` 或 `pytest test_reviewer_loop.py -q` |
| `api.py`／`api_routers/*` | 相關 `tests/api/test_*.py` + smoke |
| `data-verification-ui/*` | `cd data-verification-ui && npm run lint && npm run test:e2e` |
| 契約／quote OHLC | `./scripts/ci_terminal_contract_check.sh` |
| Portal ship | [`PORTAL_SHIP_CHECKLIST.md`](PORTAL_SHIP_CHECKLIST.md) |
| 營運 18–21 | `python3 scripts/verify_ops_queue_18_21.py` |

**API 健康檢查（prod smoke）：** 優先 `GET /docs` 或 `GET /openapi.json`（Cloud Run 邊界對 `/healthz` 可能 404）；業務 endpoint 見 PORTAL_SHIP_CHECKLIST。

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
- （從驗證矩陣挑選具體命令）

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
- Repo: investment-ai-agent（Q-Silicon）
- Approved Plan task ID: T1
- Related files: ...
- Domain: docs/AGENT-WORKFLOW.md、CLAUDE.md

## Constraints
- 最小 diff；Q-Silicon 紅線（無數據幻覺、Telegram HTML 白名單、Tool cache、main.py 執行緒安全）
- 繁體中文（面向使用者的產出）

## Do NOT
- commit / push（除非 Leader 明確授權）
- 讓 LLM 自行算價／日期
- 修改：...（範圍外）

## Verification
- ...

## Deliverable
- 改了哪些檔、摘要、未解問題
```

---

## Ship 政策

| 情境 | 行為 |
|------|------|
| 預設 | **不** commit / push |
| 使用者說「commit」 | 只 stage 本次相關檔；禁止 `git add -A` |
| 使用者說「ship／push main」 | scoped tests 全綠後依 [`AGENTS.md`](../AGENTS.md) 直推 main（無 PR 為預設）；branch protection 擋住則報錯改人類處理 |
| bump VERSION + 完整 ship 流程 | 用 gstack **`/ship`** |

---

## 反模式

| 反模式 | 為什麼 |
|--------|--------|
| 用 `/agent-action` 從零規劃大功能 | 缺審核、scope 漂移 |
| 用 `/agent-plan` 卻偷偷實作 | 指令語意混淆 |
| 多 agent 改同一檔 | 衝突 |
| haiku 改 tools/crew/API | 金融／Gate 風險 |
| `git add -A` | 混 WIP |
| 跳過 graph gate | 戰報品質／Reviewer 回歸 |
| prod smoke 只看 `/healthz` | Cloud Run 邊界已知 404 |

---

## 相關文件

- [`.cursor/commands/agent-plan.md`](../.cursor/commands/agent-plan.md)
- [`.cursor/commands/agent-action.md`](../.cursor/commands/agent-action.md)
- [`.cursor/rules/agent-orchestration.mdc`](../.cursor/rules/agent-orchestration.mdc)
- [`CLAUDE.md`](../CLAUDE.md)
- [`PORTAL_SHIP_CHECKLIST.md`](PORTAL_SHIP_CHECKLIST.md)

---

## 修訂紀錄

| 日期 | 說明 |
|------|------|
| 2026-06-16 | 初版（Q-Silicon domain；Cursor Task 路由；驗證矩陣；紅線；health 檢查） |
