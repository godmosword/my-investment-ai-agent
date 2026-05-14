# Portal Ship Checklist

This checklist is for repo-side Portal readiness. It does not close cloud-only
ops items until a staging operator has run the matching environment checks and
recorded the date in `TODOS.md` / `CHANGELOG.md`.

## API Smoke

Run against local API or staging API:

```bash
curl -fsS "$API_BASE/healthz"
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
