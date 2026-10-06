> **Status: LIVING** — index of `docs/`. **Reconciled:** 2026-10-06.

# docs/

| Dir | Status | Rule |
|---|---|---|
| `live/` | LIVING | Must match code. Update in the same commit as the code it describes. |
| `design/tasks/` | FROZEN | One plan per §T task (`tN_topic_plan.md`). Never retrofit after the task lands. |
| `journal/` | FROZEN, append-only | Dated entries: why, process notes, agent errors. New file per entry. |
| `release/<ver>/` | FROZEN per release | `HANDOFF.md`: done, open, how to resume. |

## Header convention (first lines of every doc)

LIVING:

    > **Status: LIVING** — must match `<path>`.
    > **Scope:** <one line>. **Reconciled:** YYYY-MM-DD.

FROZEN:

    > **Status: FROZEN** (written YYYY-MM-DD).
    > Point-in-time record — verify against code before using.

## Current status

| Doc | Reconciled |
|---|---|
| `../../SPEC.md` | 2026-10-06 |
| `../../ARCHITECTURE.md` | 2026-10-06 |
| `e2e_testing.md` | 2026-10-06 |

Root docs `README.md` (user-facing) and `LICENSE` are not part of this convention.
