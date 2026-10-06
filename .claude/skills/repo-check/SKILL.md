---
name: repo-check
description: Read-only drift audit of SPEC.md, ARCHITECTURE.md and docs/live against the code in this repo. Use for "check drift", "audit the spec", "does SPEC still match", or after a milestone.
---
# repo-check

Read-only. Writes nothing; suggests remedies (`repo-spec`, `repo-build`) but never runs them.

Checks, each with evidence (command output or `path:line`):
1. Every `path:line` cite in SPEC.md / ARCHITECTURE.md lands on the named symbol.
2. Every §I signature matches the code (`grep -n "def <name>"`).
3. Every §V guard exists: named test collects (`uv run pytest --collect-only -q <id>`), named hook file exists.
4. Every open §B row with an xfail still xfails; every closed row has no xfail left.
5. §T rows marked `done` have their files present; `doing` rows have a branch.
6. LIVING docs: Reconciled date ≥ last commit touching the code they "must match"
   (`git log -1 --format=%cs -- <path>`).
7. Frozen paths (C.11) exist; `tests/test_layout.py` passes.
8. Gates: `ruff check`, `ruff format --check`, `pytest -q`.

Report grouped by severity: 🔴 contract broken · 🟠 doc drift · 🟡 cosmetic. One line each.
