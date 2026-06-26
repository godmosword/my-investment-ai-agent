# Frontend Data and Design Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the Portal frontend to a production-ready state by filling the missing database/data-pipeline backing for existing views and tightening the reader/workbench design system without changing the five-board information architecture.

**Architecture:** Keep the current Vite + React PWA, FastAPI `APIRouter` pattern, BigQuery/Firestore/data-file separation, and `useApi.js` query layer. Each improvement must expose a stable API envelope with explicit `enabled`, `reason`, `source`, and `as_of` fields where data can be missing, so the UI can render pending/empty/data states without fabricating numbers.

**Tech Stack:** React, Vite, TanStack Query, Playwright, FastAPI, BigQuery, Firestore, local JSONL stores, GitHub Actions, Cloud Run Job, Secret Manager.

---

## Current-State Findings

The Portal already has the five-board shell in `data-verification-ui/src/app/routes/PortalRoutes.jsx` and `SideNav.jsx`: `/news`, `/dashboard`, `/insights`, `/columns`, `/portfolio`, plus legacy redirects into `/insights`. `InsightsHome.jsx` already includes the Options tab and lazy-loads `OptionsFlowHome.jsx`, so the old `docs/OPTIONS_FRONTEND_DESIGN.md` status line saying React is not implemented is stale.

The frontend is broad enough that the next unlock is not another shell-only page. The missing work is data backing, data-health visibility, and a tighter hierarchy for dense workbench screens.

### Frontend Data Coverage Matrix

| Frontend Area | Current API / Source | Database State | Gap | Priority |
|---|---|---:|---|---:|
| `/news` reader layer | `GET /api/news/digest`, `/deep`, `/themes` from Firestore `TECH_PULSE_FIRESTORE_COLLECTION` | Firestore-backed, no repo DDL | Needs freshness/provenance/audit health surfaced; no dataset contract doc for ingestion fields | P1 |
| `/columns` reader layer | `useNewsDeepList`, `useIndustryThemes` | Firestore + static themes | Needs column/editorial taxonomy and empty-state clarity when Firestore is unavailable | P2 |
| `/dashboard` macro | `GET /api/macro/snapshot`, `/compute-memory`, `/onchain` | Mostly live yfinance/FMP + fixture fallback; no BQ history table for dashboard snapshots | Needs a dashboard data-health panel and optional snapshot history table if trend/audit matters | P2 |
| `/insights?tab=options` | `GET /api/options/summary`, `/gex/{sym}`, `/flow/{sym}` | DDL exists: `options_*`; Cloud Run now skips missing `POLYGON_API_KEY` | Needs Secret Manager key, BQ tables, scheduled tick, and updated docs reflecting React already exists | P0 |
| `/insights?tab=paper`, `/portfolio` | JSONL stores: `execution_intents.jsonl`, `portfolio_holdings.jsonl`; optional `paper_execution_audit` | Optional BQ audit DDL exists; holdings are not durable in Cloud Run unless mounted/persisted elsewhere | Needs production persistence decision for holdings and execution intents | P0 |
| `/insights?tab=track-record` | Derived from `execution_intents.jsonl`; optional `recommendation_outcomes` writer | DDL exists for `recommendation_outcomes` | Needs scheduled mark-to-market and read API backed by BQ when available | P1 |
| `/settings` ops surface | `GET /api/gate-failures`, `qsrec-stats`, SW status | `llm_run_log`, `gate_failure_log`, reviewer log | Needs unified frontend data-health overview across all boards | P0 |
| Web Push/price alerts | JSONL/Redis + optional BQ `web_push_subscriptions` | DDL exists | Needs frontend permission/failed-state flow after production secrets are configured | P2 |

## Design Direction

Use the existing Phase 4 rule: one Portal, two densities.

Reader pages (`/news`, `/columns`) should stay article-first: source, time, concise thesis, topic/ticker links. Do not turn their first viewport into a quote wall.

Workbench pages (`/insights`, `/dashboard`, `/portfolio`) should show one primary question per screen: "what changed?", "what does it mean for the symbol?", "what position is affected?", then tuck secondary dense tables into tabs, panels, or docked summaries.

Every data-heavy panel must have the same three states:

| State | Required UI | Required API Envelope |
|---|---|---|
| Pending dependency | Calm setup card with exact missing dependency | `enabled:false`, `reason`, `hint`, `source` |
| Enabled but empty | Empty state that says what job/table must run next | `enabled:true`, empty array/object, optional `reason:"no_data_yet"` |
| Data | Values, `as_of`, source/provenance, stale/fresh indicator | `enabled:true`, payload, `as_of`, `source` |

## Implementation Tasks

### Task 1: Portal Data Health Overview

**Files:**
- Modify: `api_routers/health.py`
- Modify: `api.py`
- Modify: `data-verification-ui/src/hooks/useApi.js`
- Modify: `data-verification-ui/src/pages/Settings.jsx`
- Test: `tests/api/test_api_contract_smoke.py`
- Test: `data-verification-ui/e2e/settings-page.spec.js`

- [ ] **Step 1: Add a failing API contract test**

Add this test to `tests/api/test_api_contract_smoke.py`:

```python
def test_data_health_contract(client):
    res = client.get("/api/data-health")
    assert res.status_code == 200
    body = res.json()
    assert body["enabled"] is True
    assert isinstance(body["items"], list)
    ids = {item["id"] for item in body["items"]}
    assert {"options", "portfolio", "news", "reports"}.issubset(ids)
    for item in body["items"]:
        assert {"id", "label", "status", "source", "hint"}.issubset(item)
```

Run: `pytest tests/api/test_api_contract_smoke.py::test_data_health_contract -q`
Expected: FAIL with `404` or route missing.

- [ ] **Step 2: Implement `GET /api/data-health`**

In `api_routers/health.py`, add a route that checks configuration, not live external calls:

```python
import os
from typing import Any

from config import (
    GATE_FAILURE_LOG_TABLE,
    LLM_RUN_LOG_TABLE,
    OPTIONS_GEX_HISTORY_TABLE,
    OPTIONS_UNUSUAL_TRADES_TABLE,
    RECOMMENDATIONS_TABLE,
)


def _configured(value: str | None) -> bool:
    return bool(str(value or "").strip())


def _item(id: str, label: str, ok: bool, source: str, hint: str) -> dict[str, Any]:
    return {
        "id": id,
        "label": label,
        "status": "ready" if ok else "pending",
        "source": source,
        "hint": hint if not ok else "",
    }


@router.get("/api/data-health")
def data_health() -> dict[str, Any]:
    options_ok = _configured(OPTIONS_GEX_HISTORY_TABLE) and _configured(OPTIONS_UNUSUAL_TRADES_TABLE)
    return {
        "enabled": True,
        "items": [
            _item("reports", "Daily Brief / Gate", _configured(LLM_RUN_LOG_TABLE) and _configured(GATE_FAILURE_LOG_TABLE), "BigQuery", "Set LLM_RUN_LOG_TABLE and GATE_FAILURE_LOG_TABLE defaults via GCP_PROJECT_ID."),
            _item("recommendations", "Recommendations", _configured(RECOMMENDATIONS_TABLE), "BigQuery", "Set GCP_PROJECT_ID so trade_recommendations resolves."),
            _item("options", "Options Flow + GEX", options_ok, "BigQuery + Polygon", "Create POLYGON_API_KEY, run options DDL, set OPTIONS_GEX_HISTORY_TABLE and OPTIONS_UNUSUAL_TRADES_TABLE."),
            _item("portfolio", "Portfolio Holdings", _configured(os.getenv("PORTFOLIO_HOLDINGS_FILE")), "JSONL", "Set PORTFOLIO_HOLDINGS_FILE to a durable mounted path or migrate to BigQuery."),
            _item("news", "Tech News", _configured(os.getenv("TECH_PULSE_FIRESTORE_COLLECTION") or "tech_pulse_items"), "Firestore", "Ensure TECH_PULSE_FIRESTORE_PROJECT/COLLECTION and ingestion job are configured."),
        ],
    }
```

Run: `pytest tests/api/test_api_contract_smoke.py::test_data_health_contract -q`
Expected: PASS.

- [ ] **Step 3: Add frontend hook and Settings panel**

In `data-verification-ui/src/hooks/useApi.js`, add:

```js
export function useDataHealth() {
  return useQuery({
    queryKey: ["data-health"],
    queryFn: () => apiFetch("/api/data-health"),
    staleTime: 60 * 1000,
    retry: 1,
  });
}
```

In `Settings.jsx`, render a compact table/card list after existing gate status:

```jsx
const dataHealth = useDataHealth();
const healthItems = dataHealth.data?.items ?? [];
```

Show `ready` as a subdued green chip and `pending` as amber with `hint`.

- [ ] **Step 4: Add E2E coverage**

Extend `data-verification-ui/e2e/mock-api-server.mjs` with `/api/data-health`, then assert in `settings-page.spec.js` that `data-testid="data-health-panel"` renders `Options Flow + GEX` and a pending/ready chip.

Run: `cd data-verification-ui && npm run test:e2e -- settings-page.spec.js`
Expected: PASS.

### Task 2: Options Flow Live Readiness

**Files:**
- Modify: `docs/OPTIONS_FRONTEND_DESIGN.md`
- Modify: `docs/DEPLOY_RUNBOOK.md`
- Modify: `ENV_TEMPLATE.txt`
- Modify: `data-verification-ui/e2e/options-flow-route.spec.js`
- Modify: `data-verification-ui/e2e/mock-api-server.mjs`
- Test: `pytest tests/api/test_options_router.py -q`
- Test: `cd data-verification-ui && npm run test:e2e -- options-flow-route.spec.js`

- [ ] **Step 1: Update stale design status**

Change `docs/OPTIONS_FRONTEND_DESIGN.md` status from "尚未實作 React" to "React 已有 Insights tab；待 live secret / BQ / scheduled tick". Keep the existing red line that frontend does not calculate GEX.

- [ ] **Step 2: Document required provisioning**

Add a runbook section:

```bash
gcloud secrets create POLYGON_API_KEY --replication-policy=automatic
printf '%s' "$POLYGON_API_KEY" | gcloud secrets versions add POLYGON_API_KEY --data-file=-
bq query --use_legacy_sql=false < docs/SQL/options_snapshots.sql
bq query --use_legacy_sql=false < docs/SQL/options_unusual_trades.sql
bq query --use_legacy_sql=false < docs/SQL/options_gex_history.sql
bq query --use_legacy_sql=false < docs/SQL/options_gex_by_strike.sql
```

Also document that deploy no longer fails when `POLYGON_API_KEY` is missing; it emits a warning and leaves Options pending.

- [ ] **Step 3: Verify API pending/data states**

Run: `pytest tests/api/test_options_router.py -q`
Expected: PASS and cover pending envelope plus data envelope.

- [ ] **Step 4: Verify frontend Options tab states**

Ensure `options-flow-route.spec.js` covers:

```js
await page.goto("/insights?tab=options");
await expect(page.getByTestId("options-pending")).toBeVisible();
```

and the data state with `options-gex-panel`, `options-watchlist`, `unusual-flow-table`, and `GammaBarChart` when mock API returns `per_strike`.

Run: `cd data-verification-ui && npm run test:e2e -- options-flow-route.spec.js`
Expected: PASS.

### Task 3: Durable Portfolio and Track Record Data

**Files:**
- Create: `docs/SQL/portfolio_holdings.sql`
- Modify: `portfolio_holdings.py`
- Modify: `api_routers/portfolio.py`
- Modify: `track_record.py`
- Modify: `api_routers/track_record.py`
- Modify: `data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx`
- Test: `tests/api/test_portfolio_router.py`
- Test: `tests/api/test_track_record_router.py`
- Test: `data-verification-ui/e2e/portfolio-route.spec.js`
- Test: `data-verification-ui/e2e/insights-track-record.spec.js`

- [ ] **Step 1: Decide persistence mode**

Use `PORTFOLIO_STORE_BACKEND=jsonl|bigquery`, default `jsonl` for local compatibility. Production should use `bigquery` only after `PORTFOLIO_HOLDINGS_TABLE` is set.

- [ ] **Step 2: Add DDL**

Create `docs/SQL/portfolio_holdings.sql`:

```sql
CREATE TABLE IF NOT EXISTS `PROJECT.market_data.portfolio_holdings` (
  id STRING NOT NULL,
  symbol STRING NOT NULL,
  shares FLOAT64 NOT NULL,
  cost_basis FLOAT64 NOT NULL,
  opened_at DATE,
  notes STRING,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP
)
CLUSTER BY symbol
OPTIONS (
  description = "Q-Silicon portfolio holdings for Portal Portfolio board"
);
```

- [ ] **Step 3: Add backend tests before implementation**

In `tests/api/test_portfolio_router.py`, add tests that set `PORTFOLIO_STORE_BACKEND=jsonl` and confirm current behavior still works. Add one skipped or monkeypatched BigQuery test that verifies the interface, not actual GCP.

Run: `pytest tests/api/test_portfolio_router.py -q`
Expected: existing tests pass; new BigQuery interface test fails until implementation.

- [ ] **Step 4: Implement backend strategy**

Keep JSONL functions intact. Add a small strategy layer:

```python
def _backend() -> str:
    raw = (os.getenv("PORTFOLIO_STORE_BACKEND") or "jsonl").strip().lower()
    return "bigquery" if raw == "bigquery" else "jsonl"
```

Only route to BigQuery when `PORTFOLIO_HOLDINGS_TABLE` exists; otherwise return a clear `enabled:false` envelope from a new read-only health method and keep write routes returning `503` with a setup hint.

- [ ] **Step 5: Add frontend source badge**

In `PortfolioHome.jsx`, show `source` and `as_of` when `/api/portfolio` returns them. If backend returns pending for BigQuery mode, show a setup card instead of an empty holdings table.

- [ ] **Step 6: Promote Track Record BQ read path**

Add optional read path from `RECOMMENDATION_OUTCOMES_TABLE`; fall back to `execution_intents.jsonl`. The response must include `source: "bigquery"` or `source: "execution_intents.jsonl"` so the UI can show provenance.

Run:

```bash
pytest tests/api/test_portfolio_router.py tests/api/test_track_record_router.py -q
cd data-verification-ui && npm run test:e2e -- portfolio-route.spec.js insights-track-record.spec.js
```

Expected: PASS.

### Task 4: News and Columns Data Governance

**Files:**
- Create: `docs/FIRESTORE_TECH_PULSE_CONTRACT.md`
- Modify: `api_routers/news.py`
- Modify: `data-verification-ui/src/modules/news/pages/NewsHome.jsx`
- Modify: `data-verification-ui/src/modules/columns/pages/ColumnsHome.jsx`
- Test: `tests/api/test_news_router.py`
- Test: `data-verification-ui/e2e/news-route.spec.js`
- Test: `data-verification-ui/e2e/columns-bilingual.spec.js`

- [ ] **Step 1: Document Firestore contract**

Create `docs/FIRESTORE_TECH_PULSE_CONTRACT.md` with required fields:

```markdown
# Firestore Tech Pulse Contract

Collection: `TECH_PULSE_FIRESTORE_COLLECTION`, default `tech_pulse_items`.

Required per document:
- `headline`
- `published_at`
- `source_name` or `source_domain`
- `gemini_take`

Recommended:
- `source_url`
- `pillar`
- `tags`
- `tickers`
- `confidence`
- `deep_brief`
- `thesis_breakdown`
- `language`
- `ingested_at`
```

Also define freshness levels: fresh under 36h, stale over 36h, unknown when missing timestamps.

- [ ] **Step 2: Add API freshness metadata**

Extend `_normalize_item` in `api_routers/news.py` to include:

```python
"freshness": "fresh" | "stale" | "unknown",
"missing_fields": [...],
```

Do not reject old documents; surface quality to the UI.

- [ ] **Step 3: Add tests**

In `tests/api/test_news_router.py`, fixture one complete item and one missing `source_url`/`published_at`; assert freshness and missing fields.

Run: `pytest tests/api/test_news_router.py -q`
Expected: PASS after implementation.

- [ ] **Step 4: Improve reader UI hierarchy**

In `NewsHome.jsx` and `ColumnsHome.jsx`, show a small source/freshness line. Stale/unknown should be visible but not alarming; missing source should use "來源待補" as today, plus a subdued data-quality chip.

Run:

```bash
cd data-verification-ui
npm run test:e2e -- news-route.spec.js columns-bilingual.spec.js
```

Expected: PASS.

### Task 5: Workbench Design Tightening

**Files:**
- Modify: `data-verification-ui/src/modules/dashboard/pages/DashboardHome.jsx`
- Modify: `data-verification-ui/src/modules/insights/pages/InsightsHome.jsx`
- Modify: `data-verification-ui/src/modules/portfolio/pages/PortfolioHome.jsx`
- Modify: `data-verification-ui/src/components/TerminalCommandBar.jsx`
- Modify: `data-verification-ui/src/index.css`
- Test: `data-verification-ui/e2e/phase4-ia-portal.spec.js`
- Test: `data-verification-ui/e2e/responsive-app-shell.spec.js`
- Test: `data-verification-ui/e2e/touch-target.spec.js`

- [ ] **Step 1: Define density rules in CSS tokens**

Add CSS variables/classes for:

```css
.workbench-primary-panel { min-height: 180px; }
.workbench-secondary-panel { opacity: 0.92; }
.reader-source-line { font-size: 11px; color: var(--muted); }
```

Keep card radius at the existing app style; do not introduce marketing-style hero sections.

- [ ] **Step 2: Audit first viewport**

For `/dashboard`, `/insights`, and `/portfolio`, list first-viewport panels and classify each as primary, secondary, or dock. Move dense secondary content behind existing tabs when it crowds the primary question.

- [ ] **Step 3: Add data-testid anchors**

Add stable test ids:

```jsx
data-testid="workbench-primary-question"
data-testid="workbench-data-health-chip"
data-testid="reader-source-line"
```

- [ ] **Step 4: Verify layout**

Run:

```bash
cd data-verification-ui
npm run test:e2e -- phase4-ia-portal.spec.js responsive-app-shell.spec.js touch-target.spec.js
```

Expected: PASS with no overlapping text and 44px touch targets preserved.

### Task 6: Ship Checklist and Cross-Route Verification

**Files:**
- Modify: `docs/PORTAL_SHIP_CHECKLIST.md`
- Modify: `docs/DASHBOARD_CONTRACT.md`
- Modify: `data-verification-ui/e2e/five-routes-smoke.spec.js`
- Test: `pytest -q`
- Test: `cd data-verification-ui && npm run lint && npm run build && npm run test:e2e`

- [ ] **Step 1: Update portal ship checklist**

Add a "data backing" section:

```markdown
- [ ] `/settings` data-health panel shows every board ready or pending with a setup hint.
- [ ] Options has either `enabled:false` pending UI or live GEX rows from BigQuery.
- [ ] Portfolio persistence mode is explicit in API payload and production env.
- [ ] News/Columns show source + freshness metadata.
- [ ] Track Record source is explicit: BigQuery or JSONL fallback.
```

- [ ] **Step 2: Update dashboard contract**

Document the data envelope convention:

```json
{
  "enabled": true,
  "source": "bigquery|firestore|jsonl|live_api|fixture",
  "as_of": "ISO-8601 or null",
  "reason": null
}
```

- [ ] **Step 3: Full verification**

Run:

```bash
pytest -q
cd data-verification-ui && npm run lint && npm run build && npm run test:e2e
```

Expected: Python tests pass, frontend lint/build pass, Playwright suite passes.

## Recommended Order

1. Task 1: Data health overview. It gives the operator one place to see what is missing.
2. Task 2: Options live readiness. The React UI exists; the missing part is provisioning and live BQ.
3. Task 3: Portfolio/Track Record persistence. This prevents Cloud Run statelessness from eating user-visible data.
4. Task 4: News/Columns governance. This protects reader trust.
5. Task 5: Workbench design tightening. Do it after the data states are visible.
6. Task 6: Ship checklist and full verification.

## Non-Goals

- Do not migrate to Next.js or SSR.
- Do not introduce broker execution, OMS, or automatic trading.
- Do not let the frontend compute GEX, returns, signal quality, or regime scores that Python already owns.
- Do not add new paid/live data sources without a governance note in `docs/REALTIME_DATA_SOURCES_GOVERNANCE.md`.
- Do not make `/news` or `/columns` first viewport a dense terminal dashboard.

## Self-Review

- Spec coverage: covers the requested frontend database gaps and design improvement plan, tied to current routes, APIs, and SQL files.
- Completion-language scan: no unresolved requirement markers; every task has file paths and verification commands.
- Scope check: large but decomposed into independently shippable tasks.
- Ambiguity check: persistence defaults and pending-state behavior are explicit.
