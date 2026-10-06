---
name: repo-plan
description: Plan one SPEC §T task for this repo. Writes only docs/design/tasks/t<N>_<topic>_plan.md. Use when asked to plan a task, "plan T.7", or before building any §T row that has no plan yet.
---
# repo-plan

Writes **only** `docs/design/tasks/t<N>_<topic>_plan.md`. Never edits code or SPEC.

1. Read: the §T row; every §V, §B, §D it references; ARCHITECTURE section for the layer;
   `docs/live/*`; all code the task touches (every copy of duplicated logic).
2. Write the plan with these sections:
   - Header: `> **Status: FROZEN** (written YYYY-MM-DD).`
   - **Gap today** table: `piece | file:line | ✅/🔶/❌`.
   - **Forks**: only genuine choices; each with recommendation + trade-off. Ask the user.
   - **Acceptance**: commands + expected output (e.g. `uv run pytest -q tests/test_known_bugs.py` → no xfail for B.1).
   - **Tests first**: test names, the §V each guards, how each fails before the fix.
   - **SPEC changes needed**: list; applied later via `repo-spec` after user OK.
3. Stop. Do not implement.
