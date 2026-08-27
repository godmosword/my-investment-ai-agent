# Iteration Report: ITER-<N>

CTO issues this unique report. Other Bots contribute evidence; they do not emit the team completion marker.

The marker means the team is stopped and waiting for the human. It is **not** Iteration status `COMPLETE`.

## Iteration status
`COMPLETE | BLOCKED | FAILED | WAITING_FOR_HUMAN`

- `WAITING_FOR_HUMAN` — autonomous team paused; waiting for the human owner (including R3 / production-coupled `HOLD_FOR_HUMAN` before merge, and post-merge deploy `PENDING` / `UNKNOWN` / expected-workflow `NOT_TRIGGERED`). Not success.
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

## Checks actually run
- `<command/check>` -> `PASS | FAIL | BLOCKED` (only checks that actually ran)

## QA
`PASS | FAIL | BLOCKED`

## Architect
`APPROVE | REQUEST_CHANGES | ESCALATE_R3 | N/A`

## Product
`SUPPORT | MODIFY | REJECT | N/A`

## CI/checks
observed CI/check state; do not claim a skipped workflow as PASS

## Release verdict
`MERGE | HOLD_FOR_HUMAN | RETURN_TO_ENGINEER | DEFER`

Required. Do not infer this from deployment status or Human decision requested.

## Release evidence
concise evidence for that verdict

## Production deployment coupling
whether merge would / did trigger a consequential production workflow (name it), or none

## Deployment status
`PENDING | SUCCESS | FAILURE | NOT_TRIGGERED | UNKNOWN`

Report only observed evidence.

- `PENDING` / `UNKNOWN`: cannot `COMPLETE`.
- `FAILURE`: cannot `COMPLETE` successfully.
- expected-workflow `NOT_TRIGGERED`: cannot `COMPLETE` successfully; remains unresolved; human review required.
- idle `NOT_TRIGGERED` (no consequential workflow expected): does not by itself block `COMPLETE` after human-authorized merge.
- `SUCCESS`: may `COMPLETE` when every other required gate is done.

## Rollback
exact rollback path

## Unresolved findings
`none` or list (blocking vs non-blocking)

## Human decision requested
`NONE | READY_TO_MERGE | NOT_READY | APPROVE_R3 | REVIEW_REQUIRED | REJECT`

Must match NEXT HUMAN ACTION:

- `NONE` ↔ `ACTION: NONE`
- `READY_TO_MERGE` ↔ `ACTION: MERGE`
- `NOT_READY` ↔ `ACTION: WAIT`
- `APPROVE_R3` ↔ `ACTION: APPROVE_R3`
- `REVIEW_REQUIRED` ↔ `ACTION: REVIEW`
- `REJECT` ↔ `ACTION: REJECT`

`NOT_READY` is wait/incomplete, **not** a request to reject. `RETURN_TO_ENGINEER` is a Release verdict, not a human action.

## NEXT HUMAN ACTION

```text
NEXT HUMAN ACTION:
ACTION: MERGE | REJECT | REVIEW | APPROVE_R3 | WAIT | NONE
TARGET: <PR / Task / none>
DETAIL: <one Traditional Chinese sentence>
```

## Completion protocol

Only `QSI-CTO` may emit the marker, and only after confirming Engineer, QA, Architect, Product-UX, and Release have no active implementation, verification, review, gate, correction, handoff, or in-flight GitHub write/test/review.

Do not infer team-paused or iteration-complete from a single verdict.

Only `QSI-CTO` may set Iteration status `COMPLETE`, and only when close conditions in `.grok/TEAM_CHARTER.md` are met. The marker is never sufficient for `COMPLETE`.

When every required role has stopped and the only remaining wait is the human owner, CTO emits exactly this last line (other Bots must not):

🏁 QSI TEAM DONE — WAITING_FOR_HUMAN
