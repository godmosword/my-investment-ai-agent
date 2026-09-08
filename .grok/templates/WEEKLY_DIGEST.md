# Weekly digest: YYYY-Www

Owner: `QSI-Director` (Routine F). Write the filled digest in the Engineering Room. Update `.grok/CANDIDATE_BOARD.md` in the same turn. Do not implement from this file.

## Window
- ISO week (UTC):
- `STANDING_WEEKLY_QUOTA`: ENABLED | DISABLED
- `QUOTA_USED`: 0 | 1
- `QUOTA_CONSUMED_ID`:

## Merged this week
- (PR / iteration / one line)

## Held / rejected
- (item / reason)

## Regressions / baseline red
- (CI name / task-induced vs pre-existing)

## Top 3 for Human (or quota)

Each line: 做了會怎樣／不做會怎樣／風險。

1.
2.
3.

Human reply still works: `1 做  2 延後  3 不做`. If quota is unused and row 1 qualifies, Director may consume the weekly slot without a new Human sentence.

## Quota consumption (Director only)

If consuming the standing slot this turn:

```text
QUOTA CONSUMED
id: <board id>
risk: R0|R1
score: <n>
contract: ITER-<n>-<slug>
```

Then `HANDOFF: @QSI-Engineer` with a Task Contract. Merge remains Human.

If no row qualifies: `NO_ACTION` and stop.

## Human approvals still needed
- (R2 / R3 / deploy / PAUSE_WEEKLY_QUOTA / none)
