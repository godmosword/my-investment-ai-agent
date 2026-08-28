# Grok Autonomous Engineering Team

This directory defines the repo-side operating contract for a Grok Bot team that continuously improves **Q-Silicon / my-investment-ai-agent**.

The goal is not "many agents editing code." The goal is a controlled software organization:

`observe -> prioritize -> plan -> implement -> verify -> review -> merge -> observe`

## Source of truth

For normal repository behavior, keep following the existing project docs (`CLAUDE.md`, `AGENTS.md`, `docs/AGENT-WORKFLOW.md`, architecture docs, CI workflows).

For work explicitly started by the Grok Autonomous Engineering Team, `.grok/TEAM_CHARTER.md` adds stricter autonomy rules. In particular, **Grok autonomous cycles never push directly to `main`** even though the repository's human-maintainer workflow may allow that.

## Roster

Create these six Grok Bots using the profile text in `.grok/roles/`:

1. `QSI-Director` — sole human-facing lead and active orchestration owner; does not implement. (`QSI-CTO` is a deprecated alias; see `.grok/roles/CTO.md`.)
2. `QSI-Architect` — architecture, correctness, technical-debt and risk review; read-only by default.
3. `QSI-Product-UX` — product behavior, Portal/PWA UX, accessibility and user-value review; read-only by default.
4. `QSI-Engineer` — implementation owner; works only on assigned task contracts and isolated branches/worktrees.
5. `QSI-QA` — independent verification, regression review and merge recommendation; does not approve its own implementation.
6. `QSI-Release` — final merge/release gate and iteration ledger.

Put all six Bots in one group chat named **Q-Silicon Engineering Room** so handoffs remain visible.

Routing: `.grok/HANDOFF.md`. Director contract and Transition Table: `.grok/roles/Director.md`.

## First-time Grok Bot setup

Grok Bots on one user account share the same cloud computer, filesystem and sign-ins. Clone this repository once on the shared computer and use isolated Git worktrees for concurrent tasks.

Recommended layout:

```text
~/work/qsi/main
~/work/qsi/worktrees/task-<id>
```

Bootstrap:

```bash
mkdir -p ~/work/qsi/worktrees
git clone https://github.com/godmosword/my-investment-ai-agent.git ~/work/qsi/main
cd ~/work/qsi/main
git fetch --all --prune
```

Never store secrets in the repository. Use existing environment/secret-management conventions and keep production credentials out of autonomous test paths.

## Create the Bots

For each role:

1. Grok Bot -> New -> Create new agent.
2. Use the `Name`, `Job`, and `Profile description` from the matching file in `.grok/roles/`.
3. Give the Bot access only to tools required for its role.
4. Add it to **Q-Silicon Engineering Room**.
5. Send the role's `First message` once.

## Start the team

Send this to `QSI-Director` after all six Bots exist:

> Bootstrap Autonomous Engineering Team v1 for `godmosword/my-investment-ai-agent`. Read `.grok/TEAM_CHARTER.md`, `.grok/ITERATION_PROTOCOL.md`, `.grok/HANDOFF.md`, `.grok/roles/Director.md`, `.grok/ROUTINES.md`, and the repository's `CLAUDE.md`, `AGENTS.md`, `docs/AGENT-WORKFLOW.md`, `TODOS.md`, `CHANGELOG.md`, and relevant architecture docs. Confirm the team roster and repository state. Run Iteration 0 as an evidence-only baseline: do not change code. Produce the initial repo health map, risk register, and the top three candidate improvements ranked by the charter. Invite Architect / Product-UX / QA only when routing requires them. Publish one approved first task contract. Do not merge anything during Iteration 0.

After Iteration 0 is satisfactory, use the routine specifications in `.grok/ROUTINES.md`.

## Autonomy target

The current operating level is **`CURRENT_AUTONOMY_LEVEL` L1**, matching `.grok/TEAM_CHARTER.md`:

- Human-invoked work may plan, contract, implement, verify, and open a PR;
- Bots must not merge `main`;
- Routines must not dispatch Engineer to implement;
- Recording `SERVER_SIDE_MAIN_PROTECTION VERIFIED` does **not** automatically raise autonomy.

R3 always needs explicit human approval. Production-coupled merge remains `HOLD_FOR_HUMAN`. Production deployment is never an implicit side effect of a merge.

Do not treat L1 as L2/L3. Broader autonomy is not enabled by this file.
