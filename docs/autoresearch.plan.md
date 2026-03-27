<!-- /autoplan restore point: /Users/godmosword.eth/.gstack/projects/godmosword-my-investment-ai-agent/main-autoplan-restore-20260326-203320.md -->
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

- Define metrics by L-tier:
  - **L0/L1 metrics** (available every run, no LLM calls):
    - `lint_pass` — 0/1 (ruff check .)
    - `smoke_pass` — 0/1 (pytest -m smoke)
    - `gate_fixture_pass` — 0/1 (validate_report on fixed fixture, no live API)
    - `wall_time_sec` — measured by bench harness
    - `stop_reason` — why this run ended (ok | budget_exceeded | plateau | regression | timeout)
  - **L2-only metrics** (available only when real LLM calls are made — NOT in D1–D5 bench loop):
    - `actual_input_tokens` — from LiteLLM callback / BQ write_llm_run_log
    - `actual_output_tokens` — same source
    - `actual_cost_usd` — same source
  - Note: The stop rule `cost_used_usd >= daily_budget_cap` applies to L2 runs only.
    L0/L1 runs track `wall_time_sec` and `iterations_without_improvement` instead.
- Define machine stop rules:
  - Stop when `cost_used_usd >= daily_budget_cap` (L2 only)
  - Stop when `iterations_without_improvement >= 5` vs `token_proxy` baseline (see Day 2 for token_proxy spec)
  - Stop IMMEDIATELY when `gate_fixture_pass != 1` (hard constraint — fixture tests are deterministic, one failure is real)
  - Stop on timeout

### Day 2: L0/L1 Benchmark Entry

- Create one benchmark entrypoint (for example `scripts/bench_autoresearch.sh`).
- Output unified lines: `METRIC key=value`.
- Keep runs deterministic and under 10 minutes.
- **Required env vars before running** (prevents `main.py` API-key checks at import time):
  - `SKIP_BIGQUERY=1 SKIP_TELEGRAM=1`
- **Add `token_proxy` metric** (optimization signal for iterations_without_improvement at L0/L1):
  - Computed as: `git diff HEAD~1 --shortstat | total_lines_changed + sum(template bytes) / 4`
  - `/ 4` is an ASCII bytes-to-tokens approximation; documented as not actual token count
  - **Edge case:** if `HEAD~1` does not exist (first commit on branch), `diff_lines = 0` — guard required: `git rev-parse HEAD~1 >/dev/null 2>&1 || diff_lines=0`
  - Lower is better; provides a local proxy for token cost without a real LLM call
- **`iterations_without_improvement >= 5` plateau rule:** tracked by the **calling agent loop**, NOT the bench script. The bench script runs one iteration and exits; it cannot track cross-run state. The agent loop reads `token_proxy` from successive JSONL entries and fires the plateau stop externally.
- Add `test_bench_autoresearch.py` with smoke-marked tests covering:
  - Output contains expected METRIC keys
  - `gate_fixture_pass=0` causes immediate nonzero exit
  - JSONL experiment log is written with required keys on success AND on gate failure (early exit)
  - Required env vars missing → clear error message
  - `stop_reason=ok` + exitcode=0 on happy path
  - `token_proxy` returns 0 (not error) when HEAD~1 is missing
  - `stop_reason=timeout` when `BENCH_TIMEOUT_SEC=0` is set

### Day 3: Fixture Gate Integration

- Integrate fixed `validate_report`/structured fixtures.
- Remove external market/API noise from loop.
- Verify same commit produces stable outcomes.

### Day 4: Governance and Allowlist

- Define allowlist paths (max 5 in first sprint).
  - File: `docs/AUTORESEARCH_ALLOWLIST.yaml`
  - **Schema:**
    ```yaml
    allowlist:
      - templates/
      - crew.py        # constants block only
      - docs/prompts/  # if extracted from crew.py
    denylist:
      - report_validator.py   # core Gate logic — never auto-mutate
      - telegram_sender.py    # HTML whitelist — security boundary
      - main.py               # pipeline entry — human review required
    ```
  - Candidates: `templates/`, `crew.py` constants block, `docs/prompts/` (if extracted)
- Define protected paths (no core gate mutation in first sprint).
- Enforce least privilege for automation:
  - can update `experiment/*`
  - can open/update Draft PR
  - cannot push `main`
  - cannot merge PR
- **Also D4: Define CI workflow security model** for Day 6 (do not leave for D6 discovery):
  - **WARNING: GitHub PATs are repo-scoped, not branch-scoped.** A PAT with `contents: write` can push to any branch the repo allows — including `main`. PAT scope alone does NOT enforce "zero commits to main."
  - **Required control:** Branch protection on `main` (require PR + 1 approval, block direct push) — this is enforceable by GitHub and already should be set.
  - **Preferred approach for D6 workflow:** Use GitHub Actions built-in `GITHUB_TOKEN` with `permissions: contents: write` scoped to the workflow, plus a job **environment named `experiment`** with **required reviewer = repo owner**. This is the human-in-the-loop enforcement point. The branch-push restriction comes from branch protection, not the token.
  - **Alternative:** GitHub App with `contents: write` on `experiment/*` refs only (more complex but fully branch-scoped).

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
- **Zero unexpected commits to `main` from any experiment flow run** (enforced by branch protection rules — NOT by PAT scope; PATs are repo-scoped, not branch-scoped).
- At least one successful Draft PR from experiment flow.
- Budget and stop rules are enforced.
- Same commit + same fixture run 3 times gives consistent outcomes (small timing variance allowed).

## Budget Guardrails

- Soft cap: 24 USD
- Hard cap: 30 USD

## What Already Exists (reuse these)

| Sub-problem | Existing code | Notes |
|-------------|--------------|-------|
| L0 lint | `ruff check .` in `ci.yml` | Copy pattern directly |
| L1 smoke | `pytest -m smoke -q` (33 tests) | Reuse as-is |
| Fixture gate | `test_validate_report.py` + `report_validator.py` | Must set SKIP_* env vars |
| JSONL logging | `scratchpad.py` → `.qsilicon/scratchpad/` | Follow same pattern for `.qsilicon/experiments/` |
| Token/cost tracking | `bigquery_writer.write_llm_run_log` | L2 only; not for L0/L1 bench loop |
| Experiment log dir | N/A — `.qsilicon/experiments/` to be created | Consistent with existing `.qsilicon/scratchpad/` |

## NOT in scope (this sprint)

- BQ experiment table → do local JSONL first (post-sprint)
- Streamlit experiment dashboard (post-sprint)
- Scheduled nightly trigger / Stage 3 automation (post-sprint)
- Gate failure auto-learning (P3 TODOS)
- L3 full pipeline golden run (post-sprint)
- GitHub App token integration (optional alternative to GITHUB_TOKEN approach)

## Reference

- https://github.com/karpathy/autoresearch

---

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|
| 1 | CEO | Approve Approach A → B sub-progression for sprint structure | P6: bias toward action | Design doc already recommends this; no reason to override | Full B upfront (too much infra before value) |
| 2 | CEO | Add `token_proxy` metric to L0/L1 harness (wire existing BQ token data concept to proxy) | P2: boil lakes | Primary KPI (token cost) can't be measured at L0/L1 without a proxy — Codex P1 finding | No proxy at L0/L1 (leaves optimization signal empty) |
| 3 | CEO | Defer BQ experiment table to post-sprint (local JSONL first) | P3: pragmatic | Local JSONL is faster to ship, same data; BQ can be added later | BQ from day 1 (adds infra before value is proven) |
| 4 | CEO | Add "zero unexpected main commits" to acceptance criteria | P1: completeness | Governance guarantee must be verifiable, not just stated | Omit (leaves gap in acceptance checklist) |
| 5 | CEO | Move PAT scope definition to D4 deliverable, not D6 | P1: completeness | D6 is too late to discover security model gaps — Codex P1 finding | Leave for D6 (risk of blocked D6 delivery) |
| 6 | CEO | Annotate metrics by L-tier (L0/L1 vs L2-only) in Day 1 spec | P5: explicit over clever | L0/L1 can't emit `actual_cost_usd` — spec was ambiguous | Keep all 8 metrics undifferentiated (false expectation) |
| 7 | Eng | Stop on FIRST `gate_fixture_pass=0`, not second consecutive | P5: explicit; Codex confirmed | Fixture tests are deterministic — one failure is real, not transient | "2 consecutive" rule (allows one known-bad iteration to proceed) |
| 8 | Eng | Add `token_proxy` spec to Day 2 deliverables | P5: explicit | `iterations_without_improvement` is uncomputable without a per-tier objective — Codex P1 finding | No proxy (plateau rule never fires at L0/L1) |
| 9 | Eng | Replace PAT branch-scope assumption with GITHUB_TOKEN + branch protection | P5: explicit; Codex confirmed | PATs are repo-scoped, not branch-scoped — stated security model was false | Keep PAT approach (unenforceable) |
| 10 | Eng | Add `test_bench_autoresearch.py` as new test file | P1: completeness | Bench harness has no tests; stop rules, JSONL writer, allowlist all need coverage | Defer tests (leaves governance claims unverifiable) |
| 11 | Eng | Use GITHUB_TOKEN with `permissions: contents: write` + job environment, not custom PAT | P3: pragmatic | Built-in token + branch protection is simpler and enforceable | Custom PAT or GitHub App (more complex for same guarantee) |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | clean (prior) | 4 auto-fixed: L-tier metric annotation, PAT scope→D4, acceptance criteria, deferred scope |
| Codex Review (standard) | `/plan-eng-review` outside voice | Independent 2nd opinion | 1 | issues_found | 10 findings: SKIP_* import coupling, ambiguous fixture gate surface, token_proxy junk, PAT scope, deploy.yml blast radius, Draft PR permission gap, allowlist wrong surface, sequencing, keep/revert missing |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | issues_open | 7 issues: 3 arch (token_proxy guard, plateau ownership, D6 env gate), 2 code quality (DRY, allowlist schema), 4 test gaps; 7 accepted fixes |
| Claude Adversarial | outside voice (subagent) | Structural blind spots | 1 | issues_found | 10 findings: KPI incoherent, loop never built, allowlist conflicts with KPI, no revert mechanism, deploy.yml |
| Codex Adversarial | adversarial | Attack vectors | 1 | issues_found | 8 attack vectors: metrics gaming, fixture bypass, JSONL injection, allowlist sandbox false, plateau desync, worst-case: capital allocation degradation |
| Claude Adversarial (codebase) | adversarial + code read | Grounded attack vectors | 1 | issues_found | 8 vectors: whitespace inflation, fixture reverse-engineering, runs.jsonl tampering, scratchpad guard bypass, allowlist unenforced, SKIP_BIGQUERY kills observability, plateau persistence gap, deploy.yml production blast |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | SKIPPED (no UI scope) | — |

**CROSS-MODEL CONSENSUS:** All reviewers agree on 5 critical issues: (1) token_proxy is gameable and strategically misaligned, (2) the gate is a formatting check not a semantic safety net, (3) allowlist has no technical enforcement, (4) deploy.yml auto-deploy is the highest blast-radius failure mode, (5) the proposal/loop mechanism is entirely unspecified.

**UNRESOLVED:** 3 new TODOs added to TODOS.md (loop spec, deploy.yml gate, METRIC integrity). Plan updated with 7 accepted fixes.

**VERDICT:** ISSUES_OPEN — critical structural gaps identified. Plan is implementable for D1–D3 (bench harness) but D4–D7 (governance + loop) need the loop spec TODO resolved first.
