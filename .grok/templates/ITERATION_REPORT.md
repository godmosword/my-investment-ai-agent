# Iteration Report: ITER-<N>

CTO issues this unique final report. Other Bots contribute evidence; they do not emit the team completion marker.

## Iteration status
`COMPLETE | BLOCKED | FAILED`

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

## Production deployment coupling
whether merge would / did trigger a consequential production workflow (name it)

## Deployment status
`PENDING | SUCCESS | FAILURE | NOT_TRIGGERED | UNKNOWN`

Report only observed evidence. `PENDING` / `UNKNOWN` are not success. `FAILURE` is not a successful iteration.

## Rollback
exact rollback path

## Unresolved findings
`none` or list (blocking vs non-blocking)

## Human decision requested
`NONE | READY_TO_MERGE | NOT_READY | APPROVE_R3 | REVIEW_REQUIRED`

Must match NEXT HUMAN ACTION:

- `NONE` ↔ `ACTION: NONE`
- `READY_TO_MERGE` ↔ `ACTION: MERGE`
- `NOT_READY` ↔ `ACTION: REJECT`
- `APPROVE_R3` ↔ `ACTION: APPROVE_R3`
- `REVIEW_REQUIRED` ↔ `ACTION: REVIEW`

## NEXT HUMAN ACTION

```text
NEXT HUMAN ACTION:
ACTION: MERGE | REJECT | REVIEW | APPROVE_R3 | NONE
TARGET: <PR / Task / none>
DETAIL: <one Traditional Chinese sentence>
```

## Completion protocol

Only `QSI-CTO` may declare the iteration complete, and only after confirming Engineer, QA, Architect, Product-UX, and Release have no active implementation, verification, review, gate, correction, handoff, or in-flight GitHub write/test/review.

Do not infer completion from a single verdict.

If a consequential production workflow is coupled to merge, do not complete on the merge commit alone. Wait for observed Deployment status.

When every required role has stopped and the only remaining wait is the human owner, CTO emits exactly this last line (other Bots must not):

🏁 QSI TEAM DONE — WAITING_FOR_HUMAN
