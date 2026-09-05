# Portal Ship Checklist

This checklist is for repo-side Portal readiness. It does not close cloud-only
ops items until a staging operator has run the matching environment checks and
recorded the date in `TODOS.md` / `CHANGELOG.md`.

## 2026-09-05 正式上線

Repo-side of criterion 2 only. This document does not deploy Cloud Run.

**Three criteria (all required):**

1. Production PWA is `pwa-deploy.yml` **prebuilt** (Human signs GitHub environment `production`).
2. API **Service** answers cheap liveness with HTTP **200** (`GET /healthz` → `{"ok": true, "service": "api"}`; no `QSILICON_MASTER_KEY`).
3. Phone `/insights` shows today's recommendation plus paper reconcile (data or an honest error, not a dead page).

**Job ≠ Service.** [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) deploys the Cloud Run **Job** (daily brief). This repo has **no** GitHub workflow that deploys the HTTP API **Service**. The Service is a manual / legacy deploy.

**2026-09-05 production fact** (this PR does not heal it):

| Surface | Result |
|---------|--------|
| PWA `https://my-investment-ai-agent.vercel.app/insights` | HTTP **200** (static shell) |
| Service `https://my-investment-ai-agent-api-yp2y6wuioa-de.a.run.app` `/docs`, `/openapi.json`, `/api/reports`, `/api/track-record/summary`, `/api/paper/lifecycle` | **503** (Google HTML) |
| Same origin `GET /healthz` | **404** |

Human: Cloud Console → Cloud Run → **my-investment-ai-agent-api** (`asia-east1`) → current revision + logs. After a healthy revision that includes this `/healthz`, criterion 2 can be re-probed at the Service URL. Landing this PR does **not** make the live 503 Service recover.

**smoke:prod** (probe after Human redeploy, or to record current failure):

```bash
cd data-verification-ui
BASE_URL=https://my-investment-ai-agent.vercel.app \
API_BASE=https://my-investment-ai-agent-api-yp2y6wuioa-de.a.run.app \
npm run smoke:prod
```

## API Smoke

Run against local API or staging API:

```bash
# Liveness: prefer /docs or /openapi.json (Cloud Run edge may return 404 for /healthz)
curl -fsS "$API_BASE/docs" || curl -fsS "$API_BASE/openapi.json"
curl -fsS "$API_BASE/api/execution-intents?limit=5"
curl -fsS "$API_BASE/api/execution-intents/allowed-statuses"
curl -fsS "$API_BASE/api/execution-intents/gate-index"
curl -fsS "$API_BASE/api/symbols/BTC/quote"
curl -fsS "$API_BASE/api/run-crew/status"
curl -fsS "$API_BASE/api/push/price-alerts/digest"
curl -fsS "$API_BASE/api/industries/themes"
SCENARIO_OPTIMIZER_ENABLED=1 curl -fsS "$API_BASE/api/scenario/suggestions"
```

Expected:

- Quote responses include `data_provenance.price.ttl_seconds=45`.
- Crew status includes `age_seconds`, `is_stale`, and `stale_after_seconds`.
- Scenario suggestions may return 404 unless `SCENARIO_OPTIMIZER_ENABLED=1`.
- Execution-intent PATCH remains append-only and does not place orders.

## PWA Smoke

Run:

```bash
cd data-verification-ui
npm run lint
npm run build
npm run test:e2e
```

Manual route pass:

- Open `/news`, `/dashboard`, `/insights`, `/columns`, `/portfolio`.
- Confirm Command Bar shows `terminal-crew-status-hud`.
- Confirm Workspace layout/panels sync across same-origin tabs via `qsi_workspace_changed`.
- Confirm symbol cards show snapshot/quote provenance and degrade cleanly on quote failure.
- PATCH one non-production execution intent in staging and confirm the UI updates without a full-page refetch.

## Data Backing

- [ ] `/settings` data-health panel shows every board ready or pending with a setup hint.
- [ ] Options has either `enabled:false` pending UI or live GEX rows from BigQuery.
- [ ] Portfolio persistence mode is explicit in API payload and production env.
- [ ] News/Columns show source + freshness metadata.
- [ ] Track Record source is explicit: BigQuery or JSONL fallback.

## Staging-Only Signoff

Do not mark these complete from repo tests alone:

- BQ audit table exists and receives optional `PAPER_EXECUTION_AUDIT_TABLE` rows.
- Redis/Web Push/VAPID secrets are configured outside git.
- Real `POST /api/push/test-send` succeeds with a stored browser subscription.
- Reviewer production rollout completes the three-day staging watch in `REVIEWER_PRODUCTION_ROLLOUT.md`.

Use:

```bash
python3 scripts/verify_ops_queue_18_21.py --strict
python3 scripts/verify_reviewer_rollout_env.py --strict --probe-api-base "$API_BASE"
```

Then update `TODOS.md` and `CHANGELOG.md` with the staging dates.

## Vercel PWA Deploy (CI)

Production URL: [https://my-investment-ai-agent.vercel.app](https://my-investment-ai-agent.vercel.app). Project `my-investment-ai-agent`. Dashboard: **Root Directory** = `data-verification-ui`, **Framework** = Vite, **Output Directory** = `dist`.

When GitHub secrets are configured (`VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_TOKEN`, **`VITE_API_URL`** required, optional `VITE_TECH_PULSE_URL`), workflow `.github/workflows/pwa-deploy.yml` runs lint/E2E in `verify`, then in `deploy-vercel`:

1. `npm run build` — local fail-fast (`data-verification-ui/dist/index.html` must exist).
2. **Deploy step runs from repo root** (Vercel dashboard **Root Directory** = `data-verification-ui`; do not run `vercel` CLI from inside `data-verification-ui/` or paths double-stack).
3. `vercel pull` → `vercel build` → check `.vercel/output/` → `vercel deploy --prebuilt --prod` (pinned `vercel@54.14.2`).

The artifact uploaded to Vercel is **`.vercel/output`** from `vercel build`, not the earlier `dist/` folder copied as-is. Remote builders must **not** re-run `vite build`.

**Production path (single writer)**: [`data-verification-ui/vercel.json`](../data-verification-ui/vercel.json) sets `git.deploymentEnabled.main=false` so Vercel Git Integration **must not** create production deployments from `main`. Production is **only** `pwa-deploy.yml` prebuilt. After a frontend-related `main` push, the latest production deployment `source` must be `cli` / prebuilt — **not** `git`. Chore-only commits (for example oss-scout) must not ship a new production alias.

**Preview**: unspecified branches still deploy via Git Integration (PR previews). Those remote `vite build`s read **Vercel Preview env**, not GitHub Actions secrets.

### Env contract (`VITE_*`)

| Variable | Production | Preview | Notes |
|----------|------------|---------|-------|
| `VITE_API_URL` | **Required.** GitHub Actions secret is the source of truth (injected into `vercel build`). | **Required** on Vercel Dashboard → Preview. | Cloud Run **Service** origin, no trailing slash. Empty production value fails the deploy step. |
| `VITE_TECH_PULSE_URL` | Optional GitHub secret | Optional Preview env | Insights earnings outbound link |
| `VITE_WEB_PUSH_REGISTER` / `VITE_WEB_PUSH_VAPID_PUBLIC_KEY` | Leave off this slice | Leave off | Queue 18–21 (Redis + VAPID). Do not enable until those cloud gates are signed off. |
| `VITE_SSE_*` / `VITE_STRUCTURED_REPORT` | Keep current | Keep current | Do not add new flags in this harden slice |

Dashboard **Production** `VITE_*` should match GitHub secrets as a fallback only — not the source of truth. If `vercel pull` also downloads dashboard env, GitHub secrets still win for the CI prebuilt bundle.

Backend `WEB_PUSH_PORTAL_URL` (Cloud Run Job, not Vercel) may be `https://my-investment-ai-agent.vercel.app`. A future custom domain must also be added to Cloud Run `CORS_ORIGINS` (`CORS_ORIGIN_REGEX` only covers `*.vercel.app`).

### Access / PWA (Dashboard — human)

Vercel Authentication (SSO) was observed as **on** for `all_except_custom_domains` (no custom domain). A 2026-08-15 unauthenticated GET of the production alias still returned the PWA HTML (200). Keep Production SSO **off** (or confirm it stays off) so phone PWA install and `npm run smoke:prod` are not blocked later; API auth remains `QSILICON_MASTER_KEY` + `/api-key`.

Recommended (Dashboard only; not a repo toggle):

- **Preview:** keep SSO so PR URLs stay private.
- **Production:** turn **off** Vercel Authentication; keep API auth as `QSILICON_MASTER_KEY` + Portal `/api-key`.
- **Custom domain:** out of this slice. If added later, set Cloud Run `CORS_ORIGINS` to that origin.

**Skip vs fail**:

- Missing `VERCEL_*` → deploy step **exits 0** with warning (CI green until secrets exist).
- `VERCEL_*` present but **`VITE_API_URL` empty** → deploy step **fails** (avoid shipping a bundle with missing API banner).

Cloud Run **FastAPI** must allow Vercel origins via `CORS_ORIGIN_REGEX` (default `https://.*\.vercel\.app`). Note: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) deploys the **Cloud Run Job** (daily pipeline), not the HTTP API Service — see **Production API base URL** below.

### Production API base URL (`VITE_API_URL` / `API_BASE`)

PWA and `npm run smoke:prod` need the **FastAPI** origin (`uvicorn api:app`), typically a **Cloud Run Service** (not the Job):

```bash
gcloud config set project my-investment-ai-agent
gcloud run services list --region=asia-east1 --format='table(name,status.url)'
```

In [Cloud Console → Cloud Run → Services](https://console.cloud.google.com/run), copy the service **URL** (format `https://…-….a.run.app`). Set GitHub secret **`VITE_API_URL`** to that base (no trailing slash). If no Service exists yet, deploy API separately before expecting production Portal data calls or full `smoke:prod`.

### Post-deploy smoke

```bash
cd data-verification-ui
BASE_URL=https://my-investment-ai-agent.vercel.app \
API_BASE="https://YOUR-CLOUD-RUN-SERVICE.a.run.app" \
npm run smoke:prod
```

Static PWA routes must return 200; API checks require a reachable `API_BASE` (`/docs` or `/openapi.json` for liveness; optional quote with `SMOKE_QSILICON_KEY`). `/healthz` may 404 at the Cloud Run edge — use business endpoints if liveness probes fail.

If static routes return **401** (Vercel Authentication), Production SSO is still on — turn it off per **Access / PWA** above, then re-run smoke.

After this harden lands, confirm the newest production deployment `source` is `cli` (prebuilt), not `git`. Baseline before ship: `dpl_jDcjxjyMgPmXq5j292LZBbUyTQBX` was `source=git` (oss-scout chore).

**2026-08-15 probe** (pre-ship of this harden): five PWA routes returned **200** (real `Q-Silicon War Room` HTML, not a Vercel login page). `smoke:prod` API liveness against Cloud Run Service `https://my-investment-ai-agent-api-yp2y6wuioa-de.a.run.app` was **not** 200 (`/docs` 500, `/openapi.json` 503, `/healthz` 404) — that is the API Service, not the Vercel static config. Re-run full `smoke:prod` after the next `pwa-deploy` prebuilt and after API liveness is 200.

### Prebuilt deploy troubleshooting

If deploy fails after `vercel build`:

1. Read the full failed step log (pull 401 vs build output path vs prebuilt deploy).
2. Re-run with `VERCEL_DEBUG=1` on the deploy step locally if reproducing.
3. Confirm dashboard: **Root Directory** = `data-verification-ui`, **Framework** = Vite, **Output Directory** = `dist` — only change settings when logs show root/output mismatch.
4. Ensure `.vercel/` is not committed (listed in root `.gitignore`).

### CI timing and emergency deploy

- **Expected duration**: `verify` (lint + E2E) typically **1–15 minutes** on green runs; job hard cap **35 minutes** (Playwright `globalTimeout` 25m + `maxFailures: 8`).
- **Failure artifacts**: failed E2E uploads `playwright-report` and `e2e-results/junit.xml` (7-day retention).
- **Emergency deploy**: GitHub Actions → **PWA deploy** → **Run workflow** → enable **`skip_e2e`** to deploy without Playwright (lint only). Use only when E2E is blocked and production fix is urgent.
- **Duplicate E2E**: `pwa-e2e.yml` no longer runs on **main push**; main-path E2E is only in `pwa-deploy` `verify`. PRs still get `pwa-e2e.yml`.
- **Playwright browsers**: E2E jobs run in `mcr.microsoft.com/playwright:v1.59.1-jammy` (matches lockfile); no runtime `playwright install` on the runner (avoids post-download extract hang on runs #27770267116 / #27772957639).
