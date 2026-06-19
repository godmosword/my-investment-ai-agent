# Agent Domain Sheet — Q-Silicon（範例）

> 本檔為 **已填好的範例**，供其他專案對照。  
> Q-Silicon 正式 domain 亦內嵌於 [`docs/AGENT-WORKFLOW.md`](../../../docs/AGENT-WORKFLOW.md)；新專案請用 [`AGENT-DOMAIN.template.md`](AGENT-DOMAIN.template.md) 另建 `docs/AGENT-DOMAIN.md`。

---

## 專案識別

| 欄位 | 值 |
|------|-----|
| **專案名稱** | Q-Silicon（investment-ai-agent） |
| **主要技術棧** | Python FastAPI + LangGraph/Crew、React PWA（data-verification-ui） |
| **回應語言** | 繁體中文（戰報讀者版為機構簡報腔） |

---

## Bootstrap

| 優先 | 檔案 | 用途 |
|------|------|------|
| 1 | `CLAUDE.md` | 紅線、模組、發佈慣例 |
| 2 | `TODOS.md` | 隊列（檔首可能落後） |
| 3 | `README.md` | 驗證命令、CI |
| 4 | `CHANGELOG.md` | 已 ship 事實 |

### 依任務加讀

| 任務類型 | 加讀 |
|----------|------|
| Graph／Reviewer | `docs/architecture/REVIEWER_LOOP_DESIGN.md`、`scripts/verify_graph_gate.sh` |
| Portal／PWA | `docs/architecture/TERMINAL_FRONTEND_PLAN.md`、`docs/PORTAL_SHIP_CHECKLIST.md` |
| 架構優先順序 | `docs/architecture/Terminal_Master_Plan.md` |

---

## 紅線

| 紅線 | 說明 |
|------|------|
| **無數據幻覺** | 禁止 LLM 自行推導／捏造報價、指標、日期；實盤數據由 Python 抓取並注入 Context |
| **Telegram HTML** | 僅允許 `<b>` `<i>` `<u>` `<s>` `<code>` `<blockquote>` `<a>`；四大區塊順序固定 |
| **Tool 快取** | 新增 `tools.py` 等必須 `_get_cache` / `_set_cache` |
| **main.py 雙線程** | `ThreadPoolExecutor`（Crypto + AI）須執行緒安全 |
| **戰報語氣** | 機構簡報腔；禁止對專業讀者做「什麼是 VIX／RSI」式教學 |
| **Gate／Schema** | 不得以模糊敘述取代 `validate_report`／契約；Graph 變更須過 gate |

---

## 驗證矩陣

| 觸及 | 必跑（最小） |
|------|----------------|
| Python 核心／通用 | `ruff check .` + `python3 -m pytest -m smoke -q` |
| Graph／Reviewer／`crew.py` | `./scripts/verify_graph_gate.sh` 或 `pytest test_reviewer_loop.py -q` |
| `api.py`／`api_routers/*` | 相關 `tests/api/test_*.py` + smoke |
| `data-verification-ui/*` | `cd data-verification-ui && npm run lint && npm run test:e2e` |
| 契約／quote OHLC | `./scripts/ci_terminal_contract_check.sh` |
| Portal ship | `docs/PORTAL_SHIP_CHECKLIST.md` |
| 營運 18–21 | `python3 scripts/verify_ops_queue_18_21.py` |

**Prod API liveness：** 優先 `GET /docs` 或 `GET /openapi.json`（邊界 `/healthz` 可能 404）。

---

## Protected paths / models

| 路徑／領域 | 要求 |
|------------|------|
| `tools.py`、`crew.py`、`validate_report`、API 契約、戰報／Telegram 管線 | 禁止 haiku／gpt-5.4；Leader 或 L3 |
| Graph／Reviewer | 必跑 `scripts/verify_graph_gate.sh` |

---

## Docs sync

| 變更類型 | 同步 |
|----------|------|
| 可見行為 | `CHANGELOG.md` ↔ `TODOS.md` |
| 導航／指令 | `CLAUDE.md`／`README.md` |

---

## Ship 政策

| 情境 | 行為 |
|------|------|
| 預設 | 不 commit / push |
| commit | 只 stage 本次相關檔 |
| ship／push main | scoped tests 全綠後直推 `main`（見 `AGENTS.md`）；branch protection 擋住則報錯 |
| 完整 VERSION ship | gstack `/ship` |

---

## 專案反模式

| 反模式 | 為什麼 |
|--------|--------|
| 跳過 graph gate | 戰報／Reviewer 回歸 |
| prod smoke 只看 `/healthz` | Cloud Run 邊界已知 404 |
| haiku 改 tools/crew/API | 金融／Gate 風險 |
