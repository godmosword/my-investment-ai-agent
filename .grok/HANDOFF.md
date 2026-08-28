# Handoff

Who gets the ball next.

This file is **team-level routing**. It does **not** contain the Director Transition Table.

Canonical relationship:

- `.grok/HANDOFF.md` — team-level routing
- `.grok/roles/Director.md` — what Director must do when control returns to Director

## Single-owner HANDOFF

Every role turn may have exactly one primary `HANDOFF:` target.

`HANDOFF:` means this role owns the next state transition.

If QSI-Director only needs visibility, use:

```text
CC: @QSI-Director — status only, no action required
```

A CC is **non-owning**. Director must not interrupt or re-dispatch a valid happy-path handoff merely because Director was CC'd.

Examples:

QA PASS on R3 governance requiring Architect:

```text
HANDOFF: @QSI-Architect
CC: @QSI-Director — status only, no action required
```

Architect APPROVE:

```text
HANDOFF: @QSI-Release
CC: @QSI-Director — status only, no action required
```

Release `HOLD_FOR_HUMAN`:

```text
HANDOFF: @QSI-Director
```

A valid role turn must have exactly one of:

1. `HANDOFF: @<one next owner>`
2. HUMAN ACTION REQUIRED
3. a valid terminal state

Zero primary owners = orphan handoff.
More than one primary owner = ambiguous handoff.
Both are `ORCHESTRATION FAILURE`.

## Happy path

Human
→ QSI-Director
→ QSI-Engineer
→ QSI-QA
→ required reviewer if any
→ QSI-Release
→ QSI-Director
→ Human

Favor **direct role-to-role** handoff. Do **not** bounce every PASS through Director.

Exceptions, blockers, scope drift, and risk escalation return to Director. When control returns to Director, follow `.grok/roles/Director.md`.

## By risk / surface

### Normal R0 / R1

QSI-Director
→ QSI-Engineer
→ QSI-QA
→ QSI-Release
→ QSI-Director
→ Human

No mandatory pre-contract Architect / Product-UX / QA challenge. Post-implementation QA verification is mandatory.

### R1 user-facing Portal / PWA

Director
→ Engineer
→ QA
→ Product-UX
→ Release
→ Director
→ Human

### R2 architecture-sensitive

Director
→ Architect pre-contract
→ Engineer
→ QA
→ required review
→ Release
→ Director
→ Human

R2 architecture / API / schema / pipeline / cache / concurrency: Architect is required before the Task Contract.

### R3

Human approval when required by the consequential action / guardrail.
Architect participates when relevant.
Under L1, Release still ends at `HOLD_FOR_HUMAN`.

Not every Bot is required on every task.

## L1

Bots must not merge `main`. Human Owner is the only merger.
`HOLD_FOR_HUMAN` is the expected final autonomous handoff before a Human decision. It is not an orchestration failure.
