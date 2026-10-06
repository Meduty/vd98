---
name: repo-build
description: Implement exactly one SPEC §T task in this repo, test-first, and flip its status. Use for "build T.7", "implement next task", "fix B.1".
---
# repo-build

One §T row per run. Follow the per-task loop in `AGENTS.md`; this is the checklist.

1. Branch: `git switch main && git pull && git switch -c <type>/t<N>-<topic>`.
2. Plan exists in `docs/design/tasks/`? If not, run `repo-plan` first.
3. For each behaviour: write the failing test (named after its §V), run it, show it failing.
   Known bug → delete its `xfail` marker in `tests/test_known_bugs.py` (that is the failing test).
4. Implement the smallest change. Core stays GUI-free; Api returns `{error}`.
5. Failure → classify: my bug · spec wrong · unspecified edge. Last two → `repo-backprop`.
6. Gates, output pasted:
   `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
7. e2e per `docs/live/e2e_testing.md` for what you touched (read the PNG).
8. Same commit: code + tests + SPEC §T status (+§B row closed) via `repo-spec`, ARCHITECTURE, `docs/live/*`.
9. `git add -- <paths>`; `git diff --cached --stat` shows only this task.
10. `scripts/review.sh`; verify each finding in code; fix → re-test → re-review.
11. Commit (why, not what), push, `gh pr create` citing the §T row and pasting test output.
