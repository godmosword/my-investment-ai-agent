# Cleanup Candidates

These items were not removed in this pass because their confidence level is MEDIUM or LOW, or because they require workflow confirmation before cleanup.

## MEDIUM

- `.claude/skills/`, `.claude/worktrees/`, `.gstack/`, `.agents/` — local tooling state; removable only after confirming the local workflow does not need them.

## LOW

- CLI scripts under `scripts/` that are not imported by Python AST — many are command-line utilities referenced by docs or manual workflows, so do not delete from import analysis alone.
- `conftest.py` — pytest convention file; absence from import graph is expected.
- `docs/oss_candidates/*.json` — large generated research snapshots; consider future retention/size policy instead of immediate deletion.

## Resolved

- 2026-05-16 — Removed `pages/Today.jsx` (+ `utils/mockToday.js`), `pages/Terminal.jsx` (deprecated re-export shim), `modules/position-management/pages/PositionsHome.jsx` (+ empty parent dirs). Build verified green.
- 2026-05-30 — Removed orphan PWA components `WarRoomCard.jsx`, `PositionHealthStrip.jsx`, `IntentUpdateModal.jsx`; removed unused `recharts` dependency and orphan CSS; moved `report_postprocess_legacy.py` → `tests/report_postprocess_legacy.py`; removed empty `core/` and `data-verification-ui/src/shared/` placeholders.
- 2026-05-30 — Unified `tests/api/conftest.py` + `tests/api/helpers.py` (shared `make_api_client` / `write_jsonl_rows`); rewired `TODOS.md`／`CHANGELOG.md` dead links to current PWA paths (`InsightsHome`、`DashboardHome`、`useWarRoomSse.js` 等).
