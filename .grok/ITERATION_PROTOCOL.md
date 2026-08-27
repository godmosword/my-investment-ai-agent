# Autonomous Iteration Protocol

## Overview

One iteration should optimize one primary problem. Parallel evidence gathering is encouraged; parallel implementation is allowed only for clearly independent task contracts.

Default loop:

`SCAN -> CHALLENGE -> SELECT -> CONTRACT -> IMPLEMENT -> VERIFY -> REVIEW -> RELEASE -> LEARN`

## 0. SCAN — CTO

Read current repository state before selecting work:

- latest commits and open PRs/issues;
- `TODOS.md`, `CHANGELOG.md`, architecture status docs;
- CI status and any known red baseline;
- recent production/UX regressions if evidenced in repo or authorized monitoring;
- stale or contradictory documentation that could mislead implementation.

Produce a candidate table with: evidence, user/system impact, confidence, rough cost, risk class, and priority score.

Do not code during SCAN.

## 1. CHALLENGE — Architect + Product/UX + QA

Run independent reviews in parallel.

Architect challenges:

- Is this actually a root cause?
- Does the proposal violate architecture or financial-data contracts?
- Is the apparent debt merely aesthetic?
- Is there a smaller fix?

Product/UX challenges:

- Is the issue user-visible or operationally meaningful?
- Is the expected benefit observable?
- For Portal/PWA, does it improve a real flow instead of visual churn?

QA challenges:

- Can the failure/benefit be reproduced or measured?
- What regression tests/checks are required?
- Is the current baseline already broken?

Each reviewer returns `SUPPORT`, `MODIFY`, or `REJECT` with evidence.

## 2. SELECT — CTO

Choose at most three tasks, normally one implementation task per iteration.

Selection criteria:

- high priority score;
- evidence exists;
- acceptance criteria are independently verifiable;
- scope is bounded;
- risk fits current autonomy level.

Never choose a task solely because it is easy for an LLM.

## 3. CONTRACT — CTO

Create a Task Contract before code changes.

Template:

```markdown
# Task Contract: ITER-<N>-<slug>

## Problem
<what is wrong>

## Evidence
<files/tests/logs/reproduction>

## Expected impact
<user/system benefit>

## Scope
- in: ...
- out: ...

## Risk
R0 | R1 | R2 | R3

## Acceptance criteria
- [ ] observable criterion 1
- [ ] observable criterion 2

## Verification
- command/check 1
- command/check 2

## Rollback
<how to undo safely>

## Roles
Engineer: QSI-Engineer
QA: QSI-QA
Architect: required/not required
Release: QSI-Release
```

## 4. IMPLEMENT — Engineer

Before coding:

1. refresh `main`;
2. create isolated branch/worktree;
3. read the task contract and touched-area docs;
4. reproduce the issue where possible;
5. state implementation plan in the task thread.

Implementation rules:

- minimum diff;
- no adjacent cleanup unless required by the task;
- tests should reproduce/fence the behavior where practical;
- no invented market/financial data;
- no scope expansion without CTO revision;
- commit messages should explain the behavioral intent.

Engineer then opens/updates a PR containing:

- problem/evidence;
- change summary;
- risk class;
- tests actually run;
- known limitations;
- rollback note.

## 5. VERIFY — QA

QA must verify independently from the task branch/PR, not rely on Engineer's summary.

QA checks:

- changed-file scope;
- acceptance criteria;
- relevant repo verification matrix;
- regression risk;
- data/financial invariants;
- obvious secret/security leakage;
- docs/changelog requirements when applicable.

Verdict format:

```text
QA VERDICT: PASS | FAIL | BLOCKED
Acceptance: x/y
Checks run: ...
Regression findings: ...
Required fixes: ...
```

FAIL returns to Engineer. BLOCKED returns to CTO.

## 6. REVIEW — Architect when required

Architect review is mandatory for R2, core financial pipelines, API/schema contracts, Graph/Reviewer/crew, concurrency/caching, and meaningful architecture changes.

Verdict:

`APPROVE`, `REQUEST_CHANGES`, or `ESCALATE_R3`.

Architect does not approve based on style preference; findings must connect to correctness, maintainability cost, safety, or architecture contracts.

## 7. RELEASE — Release Manager

Release re-checks:

- current PR head SHA and scope;
- QA verdict;
- required Architect verdict;
- CI/check status;
- unresolved review threads;
- final risk class;
- whether merge would trigger a production deployment or other consequential side effect.

Outcome:

- `MERGE` for qualifying R0/R1 or permitted R2 **only when** merge is not coupled to a consequential production workflow and the Task Contract / human authorization allows merge;
- `HOLD_FOR_HUMAN` for R3, for any merge that would automatically trigger production deploy (for example `pwa-deploy.yml` or `deploy.yml`), and for uncertain consequential actions;
- `RETURN_TO_ENGINEER` for failed gates;
- `DEFER` if value/risk changed.

A green QA/Architect/Product/CI set does not override `HOLD_FOR_HUMAN` when production coupling exists. Release must not silently bypass a failed required check. Release must not autonomously deploy production, and must not retry a consequential production workflow.

If the human owner later authorizes merge, Release may merge that PR. That authorization is not a license to run or retry production deploy. Release/CTO then **observe** the coupled workflow and report its observed status (`PENDING` / `SUCCESS` / `FAILURE` / `NOT_TRIGGERED` / `UNKNOWN`) per `.grok/TEAM_CHARTER.md`.

## 8. LEARN — CTO + Release

After the release outcome, capture only useful learning:

- Was the original hypothesis correct?
- Did the verification strategy catch anything unexpected?
- Did scope/cost differ materially from estimate?
- Should a recurring lesson become a repo rule/test? Only promote repeated, evidenced lessons.

Do not treat `PR merged` as iteration success when a consequential production workflow is in play. Observe that workflow:

- `PENDING` or `UNKNOWN`: report the evidence actually seen, do **not** emit `🏁 QSI TEAM DONE — WAITING_FOR_HUMAN`, do **not** assume success, STOP for the human. No retry loop.
- `FAILURE`: do not report the iteration as successful; include human action and rollback assessment.
- `SUCCESS`: a production-coupled iteration may then close under TEAM COMPLETION PROTOCOL.
- `NOT_TRIGGERED`: record it; do not invent a deploy.

Only `QSI-CTO` may declare the iteration complete, and only after confirming every required role has stopped (see `.grok/TEAM_CHARTER.md` TEAM COMPLETION PROTOCOL). Other Bots must not output the completion marker string.

The unique final report follows `.grok/templates/ITERATION_REPORT.md`. `Human decision requested` must match `NEXT HUMAN ACTION`.

Then rescan repository state before starting the next iteration. Do not start the next iteration without explicit human authorization when the current cycle used HOLD_FOR_HUMAN or is waiting on deployment observation.

## Iteration concurrency

Allowed:

- Architect/Product/QA evidence gathering in parallel;
- implementation of two independent R0/R1 tasks in separate worktrees if they touch disjoint files and CTO explicitly authorizes both.

Disallowed:

- multiple agents editing the same file concurrently;
- QA modifying implementation then being the sole approver;
- Release merging while required checks/reviews are still pending;
- autonomous concurrency on R3 changes.

## Failure/retry limits

- One ordinary correction cycle after QA FAIL.
- A second failure requires CTO reassessment of root cause/scope.
- After two implementation failures, stop that task and report BLOCKED rather than continuing indefinitely.
