# Q-Silicon Autoresearch Sprint Plan (7 Days)

## Scope

- Build a controlled autoresearch-style loop for this repo.
- Keep execution at L0/L1 by default; L2 is optional and capped.
- Never auto-merge to `main`; only `experiment/*` branches + Draft PR.

## Locked Decisions

- No auto-merge to `main` during sprint.
- Total sprint budget cap: 30 USD.
- Primary KPI: token cost reduction.
- Hard constraints always first: `ruff` + smoke tests + fixture gate pass.

## Daily Plan

### Day 1: Baseline and Rules

- Define metrics:
  - `lint_pass`
  - `smoke_pass`
  - `gate_fixture_pass`
  - `wall_time_sec`
  - `actual_input_tokens`
  - `actual_output_tokens`
  - `actual_cost_usd`
  - `stop_reason`
- Define machine stop rules:
  - Stop when `cost_used_usd >= daily_budget_cap`
  - Stop when `iterations_without_improvement >= 5`
  - Stop when `gate_fixture_pass != 1` for 2 consecutive runs
  - Stop on timeout

### Day 2: L0/L1 Benchmark Entry

- Create one benchmark entrypoint (for example `scripts/bench_autoresearch.sh`).
- Output unified lines: `METRIC key=value`.
- Keep runs deterministic and under 10 minutes.

### Day 3: Fixture Gate Integration

- Integrate fixed `validate_report`/structured fixtures.
- Remove external market/API noise from loop.
- Verify same commit produces stable outcomes.

### Day 4: Governance and Allowlist

- Define allowlist paths (max 5 in first sprint).
- Define protected paths (no core gate mutation in first sprint).
- Enforce least privilege for automation:
  - can update `experiment/*`
  - can open/update Draft PR
  - cannot push `main`
  - cannot merge PR

### Day 5: Human-in-the-loop Iterations

- Run proposal -> benchmark -> keep/revert loop for 5-10 small iterations.
- Store experiment logs (JSONL or markdown).

### Day 6: Manual CI Experiment Workflow

- Add workflow with `workflow_dispatch` only.
- Enforce `max_iterations`, `timeout`, and budget caps.
- Output only to `experiment/*` or Draft PR.

### Day 7: End-to-end Validation and Retro

- Run one end-to-end flow from change proposal to Draft PR.
- Validate acceptance checklist.
- Produce sprint retro and next-sprint backlog.

## Acceptance Criteria

- L0/L1 benchmark returns deterministic pass/fail + metrics in under 10 minutes.
- No direct or automatic changes to `main`.
- At least one successful Draft PR from experiment flow.
- Budget and stop rules are enforced.
- Same commit + same fixture run 3 times gives consistent outcomes (small timing variance allowed).

## Budget Guardrails

- Soft cap: 24 USD
- Hard cap: 30 USD

## Reference

- https://github.com/karpathy/autoresearch
