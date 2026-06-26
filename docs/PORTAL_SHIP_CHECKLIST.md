# Portal Ship Checklist

This checklist is for repo-side Portal readiness. It does not close cloud-only
ops items until a staging operator has run the matching environment checks and
recorded the date in `TODOS.md` / `CHANGELOG.md`.

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

When GitHub secrets are configured (`VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_TOKEN`, **`VITE_API_URL`** required, optional `VITE_TECH_PULSE_URL`), workflow `.github/workflows/pwa-deploy.yml` runs lint/E2E in `verify`, then in `deploy-vercel`:

1. `npm run build` — local fail-fast (`data-verification-ui/dist/index.html` must exist).
2. **Deploy step runs from repo root** (Vercel dashboard **Root Directory** = `data-verification-ui`; do not run `vercel` CLI from inside `data-verification-ui/` or paths double-stack).
3. `vercel pull` → `vercel build` → check `.vercel/output/` → `vercel deploy --prebuilt --prod` (pinned `vercel@54.14.2`).

The artifact uploaded to Vercel is **`.vercel/output`** from `vercel build`, not the earlier `dist/` folder copied as-is. Remote builders must **not** re-run `vite build`.

**Env contract (CI)**: GitHub Actions **secrets** (`VITE_API_URL`, `VITE_TECH_PULSE_URL`) are injected into the deploy step environment for `vercel build`. If `vercel pull` also downloads Vercel dashboard env, treat **GitHub secrets as source of truth** for production API URLs unless you intentionally manage them only in Vercel.

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
