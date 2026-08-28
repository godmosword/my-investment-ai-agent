# Iteration Report: ITER-<N>

Director issues this unique **STOP / PAUSE / FINAL** report. Other Bots contribute evidence; they do not emit the team completion marker.

Do **not** issue this report while `Release gate verdict = RETURN_TO_ENGINEER` and Engineer still has an authorized correction cycle. That interval stays TEAM STATUS `RUNNING` (no marker, no unique report). Do not add a fifth Iteration status for correction-in-flight.

The marker means the team is stopped and waiting for the human. It is **not** Iteration status `COMPLETE`.

## Iteration status
`COMPLETE | BLOCKED | FAILED | WAITING_FOR_HUMAN`

- `WAITING_FOR_HUMAN` — autonomous team paused; waiting for the human owner (including R3 / production-coupled `HOLD_FOR_HUMAN` before merge with Deployment status `NOT_STARTED`, and post-merge deploy `PENDING` / `UNKNOWN` / expected-workflow `NOT_TRIGGERED`). Not success.
- `COMPLETE` — close conditions met. Emitting the marker is never sufficient.
- `BLOCKED` — cannot proceed without a change the team is not authorized to make.
- `FAILED` — iteration did not succeed (including observed production-workflow `FAILURE`).

If the human later authorizes merge, resume **this** iteration. Do not open a new iteration for that resume.

## Task
- Task Contract:
- Title:

## PR
- URL / number:
- State: `OPEN | MERGED | CLOSED`

## Head SHA
`<sha>`

## Merge commit
`<sha | none>`

## Changed files
- exact list or concise summary

## Final risk
`R0 | R1 | R2 | R3`

`CURRENT_AUTONOMY_LEVEL`: L1 (open PR only; Bots do not merge `main`)

## Checks actually run
- `<command/check>` -> `PASS | FAIL | BLOCKED` (only checks that actually ran)

## QA
`PASS | FAIL | BLOCKED`

## Roles assigned
Director, Engineer, QA, plus Architect / Product-UX / Release as required or `N/A`. Do not list a reviewer as pending if they were `N/A`.

## Architect
`APPROVE | REQUEST_CHANGES | ESCALATE_R3 | N/A`

Record `N/A` when routing did not invite Architect. Do not wait on an N/A reviewer.

## Product
`SUPPORT | MODIFY | REJECT | N/A`

Record `N/A` when the work is not user-facing Portal / PWA / UX / a11y. Do not ping Product for that case.

## CI/checks
observed CI/check state; do not claim a skipped workflow as PASS

## Release gate verdict
`MERGE | HOLD_FOR_HUMAN | RETURN_TO_ENGINEER | DEFER`

Required on this STOP / PAUSE / FINAL report. Do not infer it from deployment status, Human decision requested, or later merge outcome. Do not rewrite a historical `HOLD_FOR_HUMAN` to `MERGE` after the human later authorizes merge.

## Release evidence
concise evidence for that gate verdict

## Human merge authorization
`NOT_REQUIRED | NOT_GRANTED | GRANTED | REJECTED`

Independent of Release gate verdict.

## Merge outcome
`NOT_MERGED | MERGED | CLOSED`

Independent of Release gate verdict. Record observed state only; do not invent a merge.

## Production deployment coupling
whether merge would / did trigger a consequential production workflow (name it), or none

## Deployment status
`NOT_STARTED | PENDING | SUCCESS | FAILURE | NOT_TRIGGERED | UNKNOWN`

Report only observed evidence.

- `NOT_STARTED` — pre-merge, including `HOLD_FOR_HUMAN`. Merge has not happened; no production workflow has started. Required on every pre-merge hold. Do **not** use `PENDING`, `NOT_TRIGGERED`, or `UNKNOWN` before merge.
- `PENDING` / `UNKNOWN`: post-merge only; cannot `COMPLETE`.
- `FAILURE`: post-merge; cannot `COMPLETE` successfully.
- expected-workflow `NOT_TRIGGERED`: post-merge; cannot `COMPLETE` successfully; remains unresolved; human review required.
- idle `NOT_TRIGGERED` (no consequential workflow expected): post-merge only; does not by itself block `COMPLETE` after human-authorized merge.
- `SUCCESS`: post-merge; may `COMPLETE` when every other required gate is done.

## Rollback
exact rollback path

## Unresolved findings
`none` or list (blocking vs non-blocking)

## Learning
`<evidence-backed learning | none>`

One line. Aligns with ITERATION_PROTOCOL LEARN. Do not restore a long learning template.

## Human decision requested
`NONE | READY_TO_MERGE | NOT_READY | APPROVE_R3 | REVIEW_REQUIRED | REJECT`

Must match NEXT HUMAN ACTION:

- `NONE` ↔ `ACTION: NONE`
- `READY_TO_MERGE` ↔ `ACTION: MERGE`
- `NOT_READY` ↔ `ACTION: WAIT`
- `APPROVE_R3` ↔ `ACTION: APPROVE_R3`
- `REVIEW_REQUIRED` ↔ `ACTION: REVIEW`
- `REJECT` ↔ `ACTION: REJECT`

`NOT_READY` is wait/incomplete, **not** a request to reject. `RETURN_TO_ENGINEER` is a Release gate verdict, not a human action, and not a reason to emit this report while correction is still authorized.

## NEXT HUMAN ACTION

```text
NEXT HUMAN ACTION:
ACTION: MERGE | REJECT | REVIEW | APPROVE_R3 | WAIT | NONE
TARGET: <PR / Task / none>
DETAIL: <one Traditional Chinese sentence>
```

## Completion protocol

Only `QSI-Director` may emit the marker, and only after confirming assigned roles have stopped: Engineer, QA, and any Architect / Product-UX / Release that were not `N/A`.

Do not infer team-paused or iteration-complete from a single verdict.

Only `QSI-Director` may set Iteration status `COMPLETE`, and only when close conditions in `.grok/TEAM_CHARTER.md` are met. The marker is never sufficient for `COMPLETE`.

When every required role has stopped and the only remaining wait is the human owner, Director emits exactly this last line (other Bots must not):

🏁 QSI TEAM DONE — WAITING_FOR_HUMAN
