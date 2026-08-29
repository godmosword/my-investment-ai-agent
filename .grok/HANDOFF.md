# Handoff

Who gets the ball next.

This file is **team-level routing**. It does **not** contain the Director Transition Table.

Canonical relationship:

- `.grok/HANDOFF.md` — team-level routing
- `.grok/roles/Director.md` — what Director must do when control returns to Director

## Execution vs record

- `SendToAgent` **1:1** = execution / wake / IPC. This is the only valid invocation of the next owner.
- `HANDOFF:` = logical ownership record only. It does not wake anyone.
- `CC:` = visibility, non-owning. It does not wake anyone and does not transfer ownership.

The primary `HANDOFF:` owner **must** equal the `SendToAgent` 1:1 target.

Do **not**:

- use a Room `@mention` as invocation;
- `SendToAgent` the Engineering Room group id to wake a next owner;
- fan-out (multiple 1:1 wakes, or a group post) for the same transition;
- route a happy-path PASS through Director.

Happy-path does not route through Director.

## Single-owner HANDOFF

Every role turn may have exactly one primary `HANDOFF:` target.

`HANDOFF:` records who owns the next state. It is not the wake.

If QSI-Director only needs visibility, use:

```text
CC: @QSI-Director — status only, no action required
```

A CC is **non-owning**. Director must not interrupt or re-dispatch a valid happy-path handoff merely because Director was CC'd.

For a normal transition: emit exactly one `HANDOFF:`, execute exactly one `SendToAgent` 1:1 to that same owner, optional `CC:` to Director. A tool acknowledgement alone is **not** a completed handoff; the receiving Bot must actually wake and continue.

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

These are `ORCHESTRATION FAILURE`:

- zero primary owners (orphan handoff);
- more than one primary owner (ambiguous handoff);
- `HANDOFF:` exists but no `SendToAgent` 1:1 is executed when peer invocation is available;
- `HANDOFF:` owner ≠ `SendToAgent` 1:1 target;
- a `SendToAgent` tool acknowledgement is treated as completed handoff (the receiver must actually wake and continue);
- Room `@mention` used as invocation;
- group fan-out / `SendToAgent` to the room group as wake;
- happy-path routed through Director;
- Human Owner must send another message solely to wake, resume, or manually route the next Bot after a valid handoff.

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
Under L2A, Release still ends at `HOLD_FOR_HUMAN` for R3.

Not every Bot is required on every task.

## L2A

Current operating level is L1. `L2A_ACTIVATION_STATUS` = `BLOCKED_BY_RUNTIME_AUTO_REVIEW`. `MERGE_AUTONOMY` = `DISABLED_AT_CURRENT_RUNTIME`. While L1, `AUTO_MERGE_ELIGIBLE` is always `FALSE` and Human is the merger. Dormant L2A design stays in `.grok/TEAM_CHARTER.md` and must not self-restore. `HOLD_FOR_HUMAN` remains required for R3, production coupling, and any Human HOLD. It is not an orchestration failure.
