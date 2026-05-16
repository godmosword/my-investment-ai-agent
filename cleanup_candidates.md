# Cleanup Candidates

These items were not removed in this pass because their confidence level is MEDIUM or LOW, or because they require workflow confirmation before cleanup.

## MEDIUM

- `.claude/skills/`, `.claude/worktrees/`, `.gstack/`, `.agents/` — local tooling state; removable only after confirming the local workflow does not need them.

## LOW

- `data-verification-ui/src/shared/api/` — empty directory, but may be a planned architecture placeholder.
- CLI scripts under `scripts/` that are not imported by Python AST — many are command-line utilities referenced by docs or manual workflows, so do not delete from import analysis alone.
- `conftest.py` — pytest convention file; absence from import graph is expected.
- `docs/oss_candidates/*.json` — large generated research snapshots; consider future retention/size policy instead of immediate deletion.

## Resolved

- 2026-05-16 — Removed `pages/Today.jsx` (+ `utils/mockToday.js`), `pages/Terminal.jsx` (deprecated re-export shim), `modules/position-management/pages/PositionsHome.jsx` (+ empty parent dirs). Build verified green.
