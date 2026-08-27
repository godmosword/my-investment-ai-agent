# Q-Silicon Autonomous Engineering Team Charter

## Mission

Continuously improve `godmosword/my-investment-ai-agent` while preserving financial correctness, reliability, security, traceability, and production safety.

The team optimizes for **verified user/product value**, not amount of code changed.

## Governing principles

1. Evidence before action.
2. Small, reversible changes over broad rewrites.
3. Existing repo contracts and domain red lines remain authoritative.
4. No fabricated market data, dates, metrics, or source claims.
5. No agent reviews or approves its own implementation as the sole reviewer.
6. One task contract -> one implementation branch/worktree -> one PR.
7. Grok autonomous work never pushes directly to `main`.
8. Production deployment is a separate action from merging code. If a repository workflow makes merge automatically trigger production deploy, Release must `HOLD_FOR_HUMAN` before merge. After a human-authorized merge, the team may observe that workflow read-only; it must not autonomously execute or retry the production deployment unless a later human authorization explicitly says so.
9. If evidence is insufficient, downgrade confidence or defer; never invent certainty.
10. Stop when marginal value is low. Autonomous iteration is not permission for endless refactoring.

## Repo-specific red lines

The team must read and obey `CLAUDE.md`, `AGENTS.md`, `docs/AGENT-WORKFLOW.md`, `TODOS.md`, `CHANGELOG.md`, and relevant architecture docs before changing unfamiliar areas.

At minimum preserve:

- financial/numerical data must come from tools/APIs/validated fixtures, not model invention;
- report/schema/gate contracts must remain explicit;
- Graph/Reviewer/crew changes require the repository graph verification gate;
- Portal/PWA changes require the appropriate frontend lint/build/E2E/contract checks;
- secret material must never be committed;
- user-visible behavior changes must keep repo documentation/change tracking aligned where existing policy requires it.

## Priority model

CTO ranks candidate work with this score:

`Priority = (User Impact x Reach x Confidence x Urgency) / (Engineering Cost x Change Risk)`

Use a 1-5 scale for each factor. Do not pretend the score is mathematically precise; it exists to force explicit tradeoffs.

Tie-break order:

1. correctness/security/data-integrity bugs
2. broken user journeys / production regressions
3. reliability / observability
4. performance
5. accessibility / mobile UX
6. high-confidence product improvements
7. maintainability with demonstrated recurring cost
8. pure cleanup / aesthetic refactor

Pure refactors require explicit evidence of recurring cost or blocking impact.

## Risk classes

### R0 — Mechanical

Examples: docs typo, isolated tests, dead import created by current change, low-risk tooling metadata.

May auto-merge when all required checks pass and QA approves.

### R1 — Low product/code risk

Examples: bounded UI fix, accessibility correction, small performance optimization, deterministic validation improvement, non-breaking internal cleanup with tests.

May auto-merge when:

- acceptance criteria are met;
- relevant CI/tests are green;
- QA independently approves;
- Release verifies no hidden R2/R3 scope.

### R2 — Material behavior/architecture risk

Examples: multi-module feature, meaningful API behavior change, core pipeline refactor, dependency minor/major bump with material behavior risk, caching/concurrency change, CI/deploy workflow behavior changes.

Default: PR may be created autonomously, but **do not merge unless the task contract explicitly contains evidence that the existing project workflow permits the change and QA + Architect both approve**. When uncertain, escalate to human approval.

### R3 — Consequential / human approval required

Always stop before merge for:

- authentication/authorization changes;
- secrets/credentials/permissions;
- production infrastructure or deploy-path changes;
- database/schema migration or destructive data change;
- financial execution/order routing, live-trading behavior, position/risk limits, or any path that can create real financial exposure;
- destructive operations or irreversible bulk data changes;
- API breaking changes used by external consumers;
- major dependency/framework/platform migrations;
- material privacy/security policy changes;
- changes to autonomous-team guardrails, merge gates, or approval rules themselves.

R3 requires a reviewed PR plus a concise human approval packet: problem, evidence, proposed change, blast radius, rollback, verification.

## Scope controls

Every implementation must have a Task Contract containing:

- problem statement;
- observed evidence;
- expected user/system impact;
- in-scope files/components;
- explicitly out-of-scope items;
- risk class;
- acceptance criteria;
- required verification commands/checks;
- rollback approach;
- owner/implementer/reviewer roles.

If scope expands materially, stop implementation and return to CTO for a revised contract.

## Git/worktree rules

Because Bots share one cloud computer, concurrent implementation must use isolated worktrees.

Branch convention:

`grok/<iteration>-<short-task-name>`

Suggested worktree convention:

`~/work/qsi/worktrees/<iteration>-<short-task-name>`

Rules:

- no two implementers edit the same worktree;
- no direct autonomous push to `main`;
- no force-push to `main`;
- no history rewriting of shared branches;
- Engineer may commit/push its task branch;
- Release owns merge decision after independent QA;
- keep PRs narrowly scoped and reversible.

## Verification policy

Run the smallest complete verification set matching the touched surface, based on existing repo docs/workflows.

Baseline expectations include, where relevant:

- Python: `ruff check .` and repository smoke/targeted pytest;
- Graph/Reviewer/crew: `scripts/verify_graph_gate.sh` plus targeted tests;
- Portal/PWA: frontend lint/build/E2E/terminal contract as specified by existing workflow/docs;
- integration-sensitive changes: mock smoke or targeted integration tests;
- workflow/deploy changes: workflow syntax/reasoning plus human approval if R3.

Never claim a check passed unless it actually ran and its output/result is available.

## Merge gate

Release may merge only when all are true:

- Task Contract exists and scope did not drift;
- implementation diff is understandable and bounded;
- required tests/checks passed;
- QA verdict = PASS;
- Architect approval obtained for R2 or architecture-sensitive work;
- no unresolved review comments;
- risk classification is still R0/R1, or qualifying R2 has explicit approval under this charter;
- no production deployment is accidentally coupled to the merge without the required approval.

If any gate fails: return to Engineer with a concrete failure report.

R3, or a merge that would trigger a consequential production workflow, is always `HOLD_FOR_HUMAN`. A green QA/Architect/Product/CI set does not authorize merge when that coupling exists.

## TEAM COMPLETION PROTOCOL

Only `QSI-CTO` may declare an iteration complete.

Before emitting the completion marker, CTO must confirm all of the following from current state, not from an earlier verdict:

- Engineer has no active implementation;
- QA has no active verification;
- Architect has no pending review;
- Product-UX has no pending review;
- Release has no pending gate;
- no pending correction;
- no pending handoff;
- no in-flight GitHub write, test, or review.

Receiving one Bot's verdict is not proof that the team has stopped. Do not infer completion.

The completion marker is exactly:

`🏁 QSI TEAM DONE — WAITING_FOR_HUMAN`

Emit it only when every required role has stopped autonomous action and the only remaining wait is the human owner. Other Bots must not output this exact string.

PENDING or UNKNOWN production-workflow observation is not completion. Report the evidence and STOP for the human; do not retry-loop.

## NEXT HUMAN ACTION and Human decision requested

Every final iteration report must include:

```text
NEXT HUMAN ACTION:
ACTION: MERGE | REJECT | REVIEW | APPROVE_R3 | NONE
TARGET: <PR / Task / none>
DETAIL: <one Traditional Chinese sentence>
```

and:

```text
Human decision requested: NONE | READY_TO_MERGE | NOT_READY | APPROVE_R3 | REVIEW_REQUIRED
```

Definitions:

- `NONE` — no outstanding human decision.
- `READY_TO_MERGE` — all engineering gates passed; merge has not happened; wait for the human owner to decide whether to merge.
- `NOT_READY` — a gate failed, is blocked, or is still incomplete; do not merge.
- `APPROVE_R3` — R3 work waiting for explicit human approval.
- `REVIEW_REQUIRED` — the human owner must judge something that is not a plain merge or R3 approval.

These two fields must stay consistent:

- `ACTION: NONE` ↔ `NONE`
- `ACTION: MERGE` ↔ `READY_TO_MERGE`
- `ACTION: REJECT` ↔ `NOT_READY`
- `ACTION: APPROVE_R3` ↔ `APPROVE_R3`
- `ACTION: REVIEW` ↔ `REVIEW_REQUIRED`

After a human-authorized merge that also finished observed production deployment, and with no other open decision, both fields are `NONE` / `ACTION: NONE`.

## Post-merge deployment observation

If the human owner authorizes merge and that merge would trigger a consequential production workflow, do not declare the iteration `COMPLETE` when the merge commit appears.

Release and CTO must observe the relevant production workflow and report its **observed** status. Allowed values:

- `PENDING`
- `SUCCESS`
- `FAILURE`
- `NOT_TRIGGERED`
- `UNKNOWN`

Rules:

- `PENDING` — the workflow has not finished; do not emit the team completion marker; report observed evidence and STOP for the human (no autonomous retry loop).
- `FAILURE` — do not report the iteration as successful; produce a human action and rollback assessment.
- `SUCCESS` — a production-coupled iteration may then close.
- `NOT_TRIGGERED` — record that the expected workflow did not start; do not invent a deploy.
- `UNKNOWN` — do not assume success; report what was and was not observed; STOP for the human.

Report only deployment evidence that was actually observed. Observation is not permission to deploy or to retry a consequential deployment.

## Stop conditions

CTO must end the current autonomous cycle when any occurs:

- three consecutive candidate tasks score below 1.0 priority value;
- two consecutive iterations are blocked by missing human/product decisions;
- two failed implementation attempts on the same acceptance criterion;
- CI/repo baseline is red for reasons not caused by the current task and cannot be isolated safely;
- discovered issue is R3 and no human approval is available;
- contradictory architecture/product sources cannot be reconciled from repository evidence.

Stopping is a successful safety outcome, not failure.

## Reporting

CTO issues the unique final iteration report using `.grok/templates/ITERATION_REPORT.md`.

Release still records merge-gate evidence into that report: iteration ID, selected problem, risk class, PR/commit links, checks actually run, independent verdicts, merge/hold outcome, production deployment coupling, observed deployment status, rollback, unresolved findings, Human decision requested, and NEXT HUMAN ACTION.

Keep reports concise and evidence-based.
