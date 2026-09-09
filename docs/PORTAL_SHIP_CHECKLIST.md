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

**2026-09-09 API 契約（repo）**：`GET /api/reports` 檔案優先，不再因 BigQuery 掛掉而 503。這**不**修復正式 Cloud Run LB（程序沒在跑）。

**2026-09-09 P2（repo）**：同一 Vercel 專案 polyglot（[`vercel.json`](../vercel.json) `services`：PWA + `api:app`）。**尚未**讓正式 `/insights` 通 — 須 Human 改 Dashboard **Root Directory = `.`（空）**，確認 preview／production `GET /healthz` → `{"ok": true, "service": "api"}`，**然後**才清空 GitHub secret `VITE_API_URL`。順序反了會讓 SPA rewrite 把 `/api` 餵成 `index.html`。

**2026-09-05 production fact** (this PR does not heal it):

| Surface | Result |
|---------|--------|
| PWA `https://[REDACTED].vercel.app/insights` | HTTP **200** (static shell) |
| Service `https://[REDACTED]-api-yp2y6wuioa-de.a.run.app` `/docs`, `/openapi.json`, `/api/reports`, `/api/track-record/summary`, `/api/paper/lifecycle` | **503** (Google HTML) |
| Same origin `GET /healthz` | **404** |

Human: Cloud Console → Cloud Run → **[REDACTED]-api** (`asia-east1`) → current revision + logs. After a healthy revision that includes this `/healthz`, criterion 2 can be re-probed at the Service URL. Landing this PR does **not** make the live 503 Service recover.

**smoke:prod** (probe after Human redeploy, or to record current failure):

```bash
cd data-verification-ui
BASE_URL=https://[REDACTED].vercel.app \
API_BASE=https://[REDACTED]-api-yp2y6wuioa-de.a.run.app \
npm run smoke:prod
```

## API Smoke

Run against local API or staging API:

```bash
# Liveness (criterion 2): GET /healthz HTTP 200 + exact body {"ok": true, "service": "api"}.
# Do NOT treat /docs or /openapi.json as liveness — they can 200 while the Service is unhealthy.
curl -fsS "$API_BASE/healthz"
# expect exact JSON object: {"ok": true, "service": "api"}
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

Production URL: [https://[REDACTED].vercel.app](https://[REDACTED].vercel.app). Project `[REDACTED]`.

**Dashboard（Human，P2 切換）**：

1. **Root Directory** 從 `data-verification-ui` 改成 **`.`**（空／repo root）。未改之前，根目錄 [`vercel.json`](../vercel.json) 會被忽略，Git Integration preview 仍是純 Vite，同源 `/healthz` 仍 404。
2. Production + Preview env：可不設 `SKIP_BIGQUERY`（`VERCEL=1` 時 API 預設 skip）；若要打 BQ 才設 `SKIP_BIGQUERY=0` 並提供憑證。
3. 先用 **PR preview**（Root Directory 已是 `.` 之後）打 `GET {preview}/healthz`，本體必須是 `{"ok": true, "service": "api"}`。Hobby 若拒 `services`，**不要**改 Root Directory、不要清空 `VITE_API_URL`。
4. polyglot `/healthz` 200 之後，再清空 GitHub secret **`VITE_API_URL`**（以及 Dashboard 同名 env）。空值＝PWA 同源 `/api`。
5. 維持 Production SSO 建議關閉；`git.deploymentEnabled.main=false` 現在由**根** [`vercel.json`](../vercel.json) 負責（`data-verification-ui/vercel.json` 仍留一份，供 Root Directory 尚未切換時擋 Git production）。

When GitHub secrets are configured (`VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `VERCEL_TOKEN`, optional `VITE_API_URL` / `VITE_TECH_PULSE_URL`), workflow `.github/workflows/pwa-deploy.yml` runs lint/E2E in `verify`, then in `deploy-vercel`:

1. `npm run build` — local fail-fast (`data-verification-ui/dist/index.html` must exist).
2. **Deploy step runs from repo root** (after P2 switch, dashboard **Root Directory** = `.`; do not run `vercel` CLI from inside `data-verification-ui/` or paths double-stack).
3. `vercel pull` → `vercel build` → check `.vercel/output/` → `vercel deploy --prebuilt --prod` (pinned `vercel@59.13.1`).

The artifact uploaded to Vercel is **`.vercel/output`** from `vercel build`, not the earlier `dist/` folder copied as-is. Remote builders must **not** re-run `vite build`. After Root Directory = `.`, this prebuilt includes the FastAPI service (`pip install -r requirements-api.txt`).

**Production path (single writer)**: root [`vercel.json`](../vercel.json) sets `git.deploymentEnabled.main=false` so Vercel Git Integration **must not** create production deployments from `main`. Production is **only** `pwa-deploy.yml` prebuilt. After a frontend- or API-related `main` push, the latest production deployment `source` must be `cli` / prebuilt — **not** `git`.

**Preview**: unspecified branches still deploy via Git Integration (PR previews). After Root Directory = `.`, those builds use repo-root `services`. They read **Vercel Preview env**, not GitHub Actions secrets.

**Filesystem**: Vercel Functions are read-only except `/tmp`. Intent `PATCH` / jsonl writes do not persist across invocations — P3 (GHA commit-back) or Blob/KV. Missing daily JSON on the Function is an honest empty `[]` / 404, not a 503.

### Env contract (`VITE_*`)

| Variable | Production | Preview | Notes |
|----------|------------|---------|-------|
| `VITE_API_URL` | Optional after polyglot `/healthz` is live. Empty = same-origin `/api`. GitHub Actions secret is the source of truth (injected into `vercel build`). | Optional; empty = same-origin. | **Do not empty** while Root Directory is still `data-verification-ui` (SPA would serve HTML for `/api`). |
| `VITE_TECH_PULSE_URL` | Optional GitHub secret | Optional Preview env | Insights earnings outbound link |
| `VITE_WEB_PUSH_REGISTER` / `VITE_WEB_PUSH_VAPID_PUBLIC_KEY` | Leave off this slice | Leave off | Queue 18–21 (Redis + VAPID). Do not enable until those cloud gates are signed off. |
| `VITE_SSE_*` / `VITE_STRUCTURED_REPORT` | Keep current | Keep current | SSE on Vercel may hit Function duration limits; failure must be honest, not a fake stream. |

Dashboard **Production** `VITE_*` should match GitHub secrets as a fallback only — not the source of truth. If `vercel pull` also downloads dashboard env, GitHub secrets still win for the CI prebuilt bundle.

Backend `WEB_PUSH_PORTAL_URL` (Cloud Run Job, not Vercel) may be `https://[REDACTED].vercel.app`. A future custom domain must also be added to Cloud Run `CORS_ORIGINS` (`CORS_ORIGIN_REGEX` only covers `*.vercel.app`).

### Access / PWA (Dashboard — human)

Vercel Authentication (SSO) was observed as **on** for `all_except_custom_domains` (no custom domain). A 2026-08-15 unauthenticated GET of the production alias still returned the PWA HTML (200). Keep Production SSO **off** (or confirm it stays off) so phone PWA install and `npm run smoke:prod` are not blocked later; API auth remains `QSILICON_MASTER_KEY` + `/api-key`.

Recommended (Dashboard only; not a repo toggle):

- **Preview:** keep SSO so PR URLs stay private.
- **Production:** turn **off** Vercel Authentication; keep API auth as `QSILICON_MASTER_KEY` + Portal `/api-key`.
- **Custom domain:** out of this slice. If added later, set Cloud Run `CORS_ORIGINS` to that origin.

**Skip vs fail**:

- Missing `VERCEL_*` → deploy step **exits 0** with warning (CI green until secrets exist).
- `VERCEL_*` present but **`VITE_API_URL` empty** → deploy step **warns** and continues (same-origin bundle). Only ship that after polyglot `GET /healthz` is exact JSON.

Note: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) still deploys the **Cloud Run Job** (daily pipeline), not the HTTP API — P2 moves the API onto Vercel; P3 moves the Job.

### Production API base URL (`VITE_API_URL` / `API_BASE`)

After P2 cutover, PWA and `npm run smoke:prod` use the **same origin** as the Portal (`API_BASE` defaults to `BASE_URL`). Until Root Directory = `.` **and** `GET /healthz` is live, keep GitHub secret `VITE_API_URL` pointing at the old Cloud Run origin (or leave it set). Do not treat Cloud Run 503 as a Vercel config bug.

### Post-deploy smoke

```bash
cd data-verification-ui
BASE_URL=https://[REDACTED].vercel.app npm run smoke:prod
```

Static PWA routes must return 200; API liveness requires a reachable `API_BASE` where `GET /healthz` returns HTTP **200** and body exactly `{"ok": true, "service": "api"}` (optional quote with `SMOKE_QSILICON_KEY`). Do **not** treat `/docs` or `/openapi.json` as liveness — a docs/OpenAPI 200 must not hide a missing or wrong `/healthz`.

If static routes return **401** (Vercel Authentication), Production SSO is still on — turn it off per **Access / PWA** above, then re-run smoke.

After this harden lands, confirm the newest production deployment `source` is `cli` (prebuilt), not `git`. Baseline before ship: `dpl_jDcjxjyMgPmXq5j292LZBbUyTQBX` was `source=git` (oss-scout chore).

**2026-08-15 probe** (historical, pre-ship of this harden): five PWA routes returned **200** (real `Q-Silicon War Room` HTML, not a Vercel login page). Against Cloud Run Service `https://[REDACTED]-api-yp2y6wuioa-de.a.run.app`, `/docs` was 500, `/openapi.json` 503, `/healthz` 404 — that is the API Service, not the Vercel static config. Current contract: only `GET /healthz` with exact `{"ok": true, "service": "api"}` counts as API liveness. Re-run full `smoke:prod` after the next `pwa-deploy` prebuilt and after Human redeploys a healthy API Service revision.

### Prebuilt deploy troubleshooting

If deploy fails after `vercel build`:

1. Read the full failed step log (pull 401 vs build output path vs prebuilt deploy).
2. Re-run with `VERCEL_DEBUG=1` on the deploy step locally if reproducing.
3. Confirm dashboard: **Root Directory** = `.` for polyglot; `data-verification-ui` means root `vercel.json` is ignored.
4. If `services` is rejected (Hobby / CLI), do not empty `VITE_API_URL`; leave Root Directory as `data-verification-ui`.
5. Ensure `.vercel/` is not committed (listed in root `.gitignore`).

### CI timing and emergency deploy

- **Expected duration**: `verify` (lint + E2E) typically **1–15 minutes** on green runs; job hard cap **35 minutes** (Playwright `globalTimeout` 25m + `maxFailures: 8`).
- **Failure artifacts**: failed E2E uploads `playwright-report` and `e2e-results/junit.xml` (7-day retention).
- **Emergency deploy**: GitHub Actions → **PWA deploy** → **Run workflow** → enable **`skip_e2e`** to deploy without Playwright (lint only). Use only when E2E is blocked and production fix is urgent.
- **Duplicate E2E**: `pwa-e2e.yml` no longer runs on **main push**; main-path E2E is only in `pwa-deploy` `verify`. PRs still get `pwa-e2e.yml`.
- **Playwright browsers**: E2E jobs run in `mcr.microsoft.com/playwright:v1.59.1-jammy` (matches lockfile); no runtime `playwright install` on the runner (avoids post-download extract hang on runs #27770267116 / #27772957639).
