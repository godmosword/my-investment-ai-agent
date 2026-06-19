# Agent Domain Sheet — `<PROJECT_NAME>`

> **填寫說明：** 複製本檔為 `docs/AGENT-DOMAIN.md` 並刪除占位符。  
> `/agent-plan` 與 `/agent-action` 會讀此檔的 Bootstrap、紅線、驗證矩陣。  
> Meta 流程見 [`AGENT-WORKFLOW.md`](AGENT-WORKFLOW.md)。

---

## 專案識別

| 欄位 | 值 |
|------|-----|
| **專案名稱** | `<PROJECT_NAME>` |
| **主要技術棧** | `<e.g. Python FastAPI + React, Next.js, Go>` |
| **回應語言** | `<e.g. 繁體中文 / English>` |

---

## Bootstrap（Plan / Action 必讀）

大任務或不熟模組時依序讀：

| 優先 | 檔案 | 用途 |
|------|------|------|
| 1 | `<e.g. README.md>` | 建置、測試、CI 對齊 |
| 2 | `<e.g. CLAUDE.md / AGENTS.md / docs/ARCHITECTURE.md>` | 紅線、模組、慣例 |
| 3 | `<e.g. TODOS.md / CHANGELOG.md>` | 待辦與已 ship（**待辦檔首可能落後**，以 CHANGELOG／程式為準） |
| 4+ | `<依任務加讀>` | `<e.g. docs/api.md、frontend/README>` |

### 依任務加讀（範例，請改為本 repo 路徑）

| 任務類型 | 加讀 |
|----------|------|
| `<API>` | `<path/to/api docs or tests>` |
| `<Frontend>` | `<path/to/ui package>` |
| `<Infra / deploy>` | `<path/to/deploy checklist>` |

---

## 紅線（Plan 違反 → CRITICAL）

| 紅線 | 說明 |
|------|------|
| `<REDLINE_1>` | `<e.g. 禁止 LLM 捏造外部 API 數據>` |
| `<REDLINE_2>` | `<e.g. 認證／授權不可繞過>` |
| `<REDLINE_3>` | `<e.g. 不可跳過 schema / contract 驗證>` |

（無特殊紅線可留一行：「遵循 README 與常見安全實務」。）

---

## 驗證矩陣

依 **變更觸及面** 跑最小集合（未全綠不得宣稱完成）：

| 觸及 | 必跑（最小） |
|------|----------------|
| **全 repo 預設** | `<e.g. npm test / pytest -q / go test ./...>` |
| `<子系統 A>` | `<具體命令>` |
| `<子系統 B>` | `<具體命令>` |
| `<Lint / format>` | `<e.g. ruff check . / npm run lint>` |
| `<E2E>` | `<e.g. npm run test:e2e>` |
| `<Deploy smoke>` | `<e.g. curl health URL>` |

對齊 CI：`<e.g. .github/workflows/ci.yml 的 job 名稱>`。

---

## Protected paths / models（可選）

高風險路徑禁止派給廉價模型或 haiku；由 Leader 或 L3 處理：

| 路徑／領域 | 要求 |
|------------|------|
| `<e.g. auth/, payments/>` | Leader 或 Opus；必跑 `<gate command>` |
| `<e.g. 核心 schema>` | 禁止 haiku；必跑 `<test>` |

若無，填「無」或刪除本節。

---

## Docs sync（可見行為變更時）

| 變更類型 | 同步 |
|----------|------|
| 使用者可見行為 | `<CHANGELOG.md>` |
| 待辦／完成度 | `<TODOS.md 或等價>` |
| 指令／導航 | `<README.md / CLAUDE.md>` |

---

## Ship 政策

| 情境 | 行為 |
|------|------|
| 預設 | **不** commit / push |
| 使用者說「commit」 | 只 stage **本次相關檔**；禁止 `git add -A` |
| 使用者說「ship／push main」 | scoped tests 全綠後 `<e.g. git push origin main / 開 PR>` |
| branch protection | `<失敗時報錯，改人類處理>` |

---

## 專案反模式（可選）

| 反模式 | 為什麼 |
|--------|--------|
| `<e.g. 跳過 E2E>` | `<原因>` |

---

## 修訂紀錄

| 日期 | 說明 |
|------|------|
| `<YYYY-MM-DD>` | 初版 Domain sheet |
