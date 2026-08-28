# Grok Team Routines

These routines are operating specifications. Configure them in Grok Bot only after Iteration 0 is reviewed.

## Routine A — Daily Engineering Scan

Owner: `QSI-CTO`

Recommended cadence: once per day on weekdays.

Instruction:

> Rescan `godmosword/my-investment-ai-agent` for evidence-backed correctness, reliability, UX, performance, accessibility, test/CI, and maintainability issues. Read current `main`, open PRs/issues, relevant CI state, `TODOS.md`, `CHANGELOG.md`, and architecture status docs. Ask QSI-Architect, QSI-Product-UX, and QSI-QA to independently challenge the top candidates. Rank candidates using `.grok/TEAM_CHARTER.md`. If no candidate clears the value/risk threshold, report NO_ACTION and stop. Otherwise create at most one bounded Task Contract and hand it to QSI-Engineer. Never code yourself and never authorize R3 merge.

Expected output: candidate table + selected Task Contract or `NO_ACTION`.

## Routine B — PR Verification Watch

Owner: `QSI-QA`

Recommended trigger: whenever a Grok-owned PR is ready for review; if event triggers are unavailable, check on a modest recurring cadence.

Instruction:

> Find Grok-owned PRs awaiting verification. For each, read its Task Contract and actual diff. Independently run the touched-surface verification required by repo docs and the contract. Distinguish pre-existing baseline failures from task-induced regressions. Post `QA VERDICT: PASS|FAIL|BLOCKED` with checks actually executed and evidence. Do not edit implementation and then approve yourself.

## Routine C — Release Gate

Owner: `QSI-Release`

Recommended trigger: after QA PASS and required architecture review.

Instruction:

> Evaluate each Grok-owned PR that has QA PASS. Verify final scope, PR head SHA, CI/checks, unresolved material review comments, Architect verdict when required, final risk class, rollback, and whether merge causes a consequential deployment side effect. Merge only qualifying R0/R1 or explicitly permitted R2 work under `.grok/TEAM_CHARTER.md`. For R3 or consequential uncertainty, post `HOLD_FOR_HUMAN` and stop. Never deploy production as an implicit follow-up.

## Routine D — Weekly Architecture / Debt Review

Owner: `QSI-Architect`

Recommended cadence: weekly.

Instruction:

> Inspect the current repository for repeated architectural pain backed by evidence: recurring regressions, duplicated high-risk logic, fragile contracts, dependency or concurrency hazards, stale architecture assumptions, and testing blind spots. Do not recommend cleanup for aesthetics. Return at most five findings with evidence, recurring cost, smaller alternatives, risk class, and whether the finding should enter CTO candidate scoring. Do not implement.

## Routine E — Weekly Product / UX Review

Owner: `QSI-Product-UX`

Recommended cadence: weekly.

Instruction:

> Inspect authorized Portal/PWA behavior and current repo implementation for broken or confusing user flows, mobile issues, accessibility gaps, latency/perceived-performance problems, and product inconsistencies. Do not invent analytics or user feedback. Return at most five evidence-backed findings with observable acceptance criteria and expected user value. Do not implement.

## Routine F — Weekly Executive Digest

Owner: `QSI-CTO`

Recommended cadence: weekly, after architecture/product reviews.

Instruction:

> Summarize the last week of autonomous engineering: iterations attempted, merged PRs, held/rejected work, regressions found, verification evidence, repeated lessons, current risk register, and top three next candidates. Keep it concise. Explicitly list every item needing human approval. Do not start implementation from this digest; run the normal SCAN/CHALLENGE/CONTRACT flow first.

## Routine safety

All routines must follow these rules:

- No routine may weaken `.grok/TEAM_CHARTER.md`.
- No routine may directly push to `main`.
- No routine may perform a production deployment autonomously.
- No routine may retry a consequential production deployment. Observation of a workflow is not authorization to rerun it.
- No routine may treat `PR merged` as `iteration successfully completed`. Pre-merge `HOLD_FOR_HUMAN` must report Deployment status `NOT_STARTED`; never `PENDING`, `NOT_TRIGGERED`, or `UNKNOWN`. After merge, if a consequential production workflow can trigger, observe and report (`PENDING` / `SUCCESS` / `FAILURE` / `NOT_TRIGGERED` / `UNKNOWN`) per `.grok/TEAM_CHARTER.md`. `PENDING`, `UNKNOWN`, `FAILURE`, and expected-workflow `NOT_TRIGGERED` cannot close successfully; report evidence and STOP for the human instead of looping. Only observed `SUCCESS` (plus every other required gate) may close a production-coupled iteration. Idle `NOT_TRIGGERED` when no consequential workflow was expected is a post-merge label only and does not by itself block close after human-authorized merge.
- No routine may emit `🏁 QSI TEAM DONE — WAITING_FOR_HUMAN`. Only `QSI-CTO` issues that exact marker, and only under TEAM COMPLETION PROTOCOL. The marker means the team is stopped and waiting; it does not mean Iteration status `COMPLETE`.
- No routine may change secrets, permissions, live financial execution, destructive data/schema, or autonomy guardrails without human approval.
- When a retry occurs, re-read current repo/PR state rather than blindly repeating an old action.
- Never run an endless retry loop. Follow the retry/stop limits in `.grok/ITERATION_PROTOCOL.md`.
