# Agent Orchestration 可攜模板

把 **`/agent-plan`** 與 **`/agent-action`** 接到任意 Cursor 專案。  
**Meta**（誰規劃、誰審、誰派工）在各 repo 相同；**Domain**（紅線、Bootstrap、驗證命令）各專案填一頁 [`docs/AGENT-DOMAIN.md`](docs/AGENT-DOMAIN.template.md)。

Q-Silicon 參考實作（domain 內嵌版）：[`docs/AGENT-WORKFLOW.md`](../../docs/AGENT-WORKFLOW.md)（本 repo 根目錄）。

---

## 5 分鐘接入

### 1. 複製檔案

在**目標 repo 根目錄**執行（目錄須已存在；新 repo 請先 `mkdir` 或 `git init`）：

```bash
/path/to/investment-ai-agent/templates/agent-orchestration/bootstrap.sh /path/to/your-repo
```

或手動複製：

| 來源（本目錄） | 目標 repo |
|----------------|-----------|
| `.cursor/commands/agent-plan.md` | `.cursor/commands/agent-plan.md` |
| `.cursor/commands/agent-action.md` | `.cursor/commands/agent-action.md` |
| `.cursor/rules/agent-orchestration.mdc` | `.cursor/rules/agent-orchestration.mdc` |
| `docs/AGENT-WORKFLOW.md` | `docs/AGENT-WORKFLOW.md` |
| `docs/AGENT-DOMAIN.template.md` | `docs/AGENT-DOMAIN.md`（**填完再 commit**） |

### 2. 填寫 Domain 一頁

編輯目標 repo 的 **`docs/AGENT-DOMAIN.md`**（由 template 複製而來）：

- 專案名稱、技術棧
- **Bootstrap** 必讀檔（通常 `README.md`、架構 doc、待辦）
- **紅線**（Plan 違反 → CRITICAL）
- **驗證矩陣**（觸及面 → 最小命令，對齊 CI）
- **Ship 政策**（預設不 push、是否直推 main）
- （可選）禁止廉價模型改哪些路徑

填完範例見 [`docs/AGENT-DOMAIN.example.q-silicon.md`](docs/AGENT-DOMAIN.example.q-silicon.md)。

### 3. 驗證

1. 用 Cursor **重新開啟**該 repo 工作區
2. 聊天輸入 `/agent-plan` — 應出現在 slash 選單
3. 試一則小任務：Plan → Approved Plan → `/agent-action`

### 4. （可選）導航

在專案 `README.md` 或 `CLAUDE.md` 加一行：

```markdown
- Agent 編排：`docs/AGENT-WORKFLOW.md` · Domain：`docs/AGENT-DOMAIN.md`
```

---

## 兩層分工

| 層 | 檔案 | 誰維護 |
|----|------|--------|
| **Meta** | `docs/AGENT-WORKFLOW.md` + `.cursor/commands/*` | 自本 template 升級時再 sync |
| **Domain** | `docs/AGENT-DOMAIN.md` | **各專案維護者** |

Meta 更新：從 Q-Silicon repo 重新跑 `bootstrap.sh`（會覆寫 Meta 檔；**不覆寫**已存在的 `AGENT-DOMAIN.md`）。

---

## 與 gstack 分工

| 情境 | 用 |
|------|-----|
| 自動多輪 plan 審核 | gstack `/autoplan` |
| 自訂 Plan + 雙審 | **`/agent-plan`** |
| 已有 Approved Plan | **`/agent-action`** |
| VERSION + CHANGELOG + push | gstack `/ship` |

---

## CRITICAL 互動

若專案已有 [`.cursor/rules/review-user-choice.mdc`](../../.cursor/rules/review-user-choice.mdc)，Plan/Action 會對齊 **A/B/C** 格式。沒有也可運作，但建議複製該 rule 以一致 UX。

---

## 修訂

| 日期 | 說明 |
|------|------|
| 2026-06-16 | 初版可攜模板 + bootstrap 腳本 |
