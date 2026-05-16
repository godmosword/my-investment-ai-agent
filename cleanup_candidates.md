# Cleanup Candidates

These items were not removed in this pass because their confidence level is MEDIUM or LOW, or because they require workflow confirmation before cleanup.

## MEDIUM

- `data-verification-ui/src/pages/Today.jsx` — no active import or route found, but it is referenced in historical planning/docs and may still be useful as migration reference.
- `data-verification-ui/src/pages/Terminal.jsx` — no active import or route found, but legacy `/terminal` behavior is documented and currently redirects to `/insights`; confirm before deleting.
- `data-verification-ui/src/modules/position-management/pages/PositionsHome.jsx` — no active import or route found; likely superseded by `/portfolio` and quant/portfolio modules, but confirm with product history.
- `.claude/skills/`, `.claude/worktrees/`, `.gstack/`, `.agents/` — local tooling state; removable only after confirming the local workflow does not need them.

## LOW

- `data-verification-ui/src/shared/api/` — empty directory, but may be a planned architecture placeholder.
- CLI scripts under `scripts/` that are not imported by Python AST — many are command-line utilities referenced by docs or manual workflows, so do not delete from import analysis alone.
- `conftest.py` — pytest convention file; absence from import graph is expected.
- `docs/oss_candidates/*.json` — large generated research snapshots; consider future retention/size policy instead of immediate deletion.
