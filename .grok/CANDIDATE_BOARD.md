# Grok candidate board

Living discovery artifact. Director / Architect / Product-UX write here. Engineer does not invent rows.

Human standing authorization **B** (2026-09-08): at most **one** `R0`/`R1` implementation per ISO week (UTC) from this board. Merge stays Human. See `.grok/TEAM_CHARTER.md` § Standing weekly quota.

## Standing quota

```text
STANDING_WEEKLY_QUOTA: ENABLED
QUOTA_SIZE: 1
QUOTA_WINDOW: ISO_WEEK_UTC
QUOTA_RISK: R0|R1
QUOTA_MIN_PRIORITY: 8
ROUTINE_IMPLEMENTATION_AUTONOMY: DISABLED
```

Director updates these three lines when the week rolls or a slot is consumed:

```text
CURRENT_WINDOW: 2026-W37
QUOTA_USED: 1
QUOTA_CONSUMED_ID: TR-LOOP-FALSE-NEG
```

`CURRENT_WINDOW` is ISO week `YYYY-Www` in UTC. `QUOTA_USED` is `0` or `1`. `QUOTA_CONSUMED_ID` is a board `id` or `none`.

A qualifying row must be `READY`, risk `R0` or `R1`, score ≥ `QUOTA_MIN_PRIORITY`, not on the ban list, no production coupling, and must not touch `.grok/**`, `.github/workflows/**`, auth/secrets, or deploy path.

If a Human mission is already `IN_FLIGHT`, do not consume the quota. Human may say `PAUSE_WEEKLY_QUOTA` to set `STANDING_WEEKLY_QUOTA: DISABLED`.

## Board

Keep at most **7** `NEW`/`READY`/`AUTHORIZED`/`IN_FLIGHT` rows. Archive `DONE`/`REJECTED`/`DEFERRED` below. Do not add a copy-pack row that is not on the remaining-surfaces list.

| id | title | evidence | impact | risk | score | status |
|---|---|---|---|---|---|---|
| TR-LOOP-FALSE-NEG | 紙上對帳假陰性：分頁截斷與未知 status 標成無紙上記錄 | `data-verification-ui/src/modules/daily-brief/pages/PaperReconcileStrip.jsx` `useTrackRecordClosed(50)` / `useExecutionIntents(100)`; `paperReconcile.js` fallback `kind: none` | 已結或未知列被說成沒有 | R1 | 60 | IN_FLIGHT |
| CI-QUICK-BASELINE | `CI / quick` 既有 ruff 紅仍合併；需隔離 baseline 與任務回歸 | #185–#187 `quick` failure; PR #185 notes ~659 ruff | 綠燈假象；任務回歸難辨 | R1 | 8 | READY |
| HONESTY-PORTFOLIO-EMDASH | `/portfolio` 缺值仍用 em dash，未走 UNKNOWN | `PortfolioHome.jsx`; `WatchlistMonitor.jsx` | 缺值假裝中性 | R1 | 16 | READY |
| HONESTY-ANALYSIS-DEEPDIVE | `/analysis` 仍英文 Deep Dive + em dash | `AnalysisHome.jsx` | 與 Insights DeepDive 繁中不一致 | R1 | 12 | READY |
| HONESTY-DATA-HEALTH-LABELS | `/api/data-health` item label 仍英文 | `api_routers/health.py` `data_health()` | 晶片狀態已繁中、列名未翻 | R1 | 10 | READY |

## Archive

| id | title | status | note |
|---|---|---|---|
| DOCS-44BP-SYNC | CHANGELOG／TODOS 補記 P4-44B～44P；澄清與隊列 62 不同名 | DONE | 2026-09-08 本治理切片 |

## Ban list

Do **not** add or select:

- 單一字串／單一 chip 繁中，且沒有新的誠實缺陷
- 下一包「P4-44Q+」文案工廠（未列於 remaining surfaces）
- 無回歸證據的重構、重排、美化
- 只因 LLM 好做而選的任務
- 假裝正式 Cloud Run Service 已康復（Job ≠ Service；`/healthz` 未部署仍 404／503）
- 改 `.grok/**` 章程／配額／禁做清單（R3；需新的 Human 授權）
- 改 `.github/workflows/**`、deploy path、secrets、live trading

## Remaining honesty surfaces

Quota may pick **one** listed surface per week. Do not invent a new surface.

- `data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx` — em dash
- `data-verification-ui/src/modules/portfolio/components/WatchlistMonitor.jsx` — em dash
- `data-verification-ui/src/modules/industry-trends/pages/IndustriesHome.jsx` — em dash
- `data-verification-ui/src/pages/Settings.jsx` — em dash
- `data-verification-ui/src/modules/investment-analysis/pages/AnalysisHome.jsx` — `Deep Dive` + em dash
- `data-verification-ui/src/utils/regime.js` — `— 未知`
- `api_routers/health.py` — `/api/data-health` English item labels

P4-44B～44P（2026-09-03～09-05）已覆蓋 Insights／DeepDive／指令列／情境／警示／實績／資料健康 **status chip**。那些面不要再開文案包。

## Scan sources (required)

Director must read these before rewriting the board. Do **not** scan only `TODOS.md` 檔首.

1. `origin/main` last 14 days of commits/PRs
2. CI: task-induced red vs known baseline (`quick` / ruff)
3. `CHANGELOG.md` ↔ `TODOS.md` alignment
4. This board, ban list, remaining surfaces
5. Ship facts in `docs/PORTAL_SHIP_CHECKLIST.md` (Job ≠ Service)
6. Charter priority: correctness / data honesty → broken journeys → reliability/CI → performance → a11y → product → evidenced maintenance cost
