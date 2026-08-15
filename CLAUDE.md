# Q-Silicon（本 repo）

與 **Karpathy 準則**（下方）並存；專案紅線、模組表、指令與架構索引見：

- [`TODOS.md`](TODOS.md) 隊列與維護者意見
- [`docs/architecture/Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) 執行順序與風險
- [`docs/architecture/`](docs/architecture/)（`AI_CONTEXT.md`、`REVIEWER_LOOP_DESIGN.md`、`TERMINAL_FRONTEND_PLAN.md` 等）；**架構目錄判讀**以 [`Terminal_Master_Plan.md`](docs/architecture/Terminal_Master_Plan.md) **§0 狀態矩陣 + Phase 0–4** 為準（研究稿非預設產品承諾，事實以 `CHANGELOG.md`／程式為準；**Phase 1** staging 執行稿見 [`STAGING_CURRENT_AFFAIRS_SMOKE.md`](docs/STAGING_CURRENT_AFFAIRS_SMOKE.md)；**Phase 4 IA** 讀者層×工作台層實作見 `TODOS` **隊列 44** 與 `TERMINAL_FRONTEND_PLAN` **§ Phase 4 IA**）
- 前端 Portal：`data-verification-ui/`（`/briefs` 與 `/terminal` 同掛日報模組；`npm run test:e2e`）。正式站 Vercel：[`docs/PORTAL_SHIP_CHECKLIST.md`](docs/PORTAL_SHIP_CHECKLIST.md)（`pwa-deploy.yml` prebuilt；`git.deploymentEnabled.main=false`）
- 後端：`api.py` 組裝；`api_routers/` incremental `APIRouter`（例：`metrics`、`health`）；改 Graph／Reviewer 請跑 `scripts/verify_graph_gate.sh` 或 `pytest test_reviewer_loop.py`
- **發佈（ship）**：維護者預設 **不上 PR**——相關測試通過後 **commit 並 `git push origin main`**。若遠端 `main` 設了 branch protection 無法直推，再改由人類處理合併／調整規則。

---

# Karpathy Coding Guidelines

Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.
