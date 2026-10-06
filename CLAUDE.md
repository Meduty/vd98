@AGENTS.md

# Claude Code specifics

Everything in `AGENTS.md` applies. This file only adds what is specific to Claude Code.

## Guardrails that run on every tool call

- `.claude/hooks/guard.py` (PreToolUse) blocks bulk staging/committing and any tool call
  touching secret-looking paths. Exit 2 = blocked; the reason is on stderr.
  **If the hook or a permission rule blocks you, stop and ask the user. Do not work around it.**
- `.claude/settings.json` holds the allow/deny rules. Per-user overrides go in
  `.claude/settings.local.json` (gitignored).

## Path-scoped rules (load automatically when you touch matching files)

- `.claude/rules/core.md` — `src/vd98/{manager,urls,formats,settings}.py`
- `.claude/rules/ui.md` — `src/vd98/web/**`, `src/vd98/api.py`, `src/vd98/app.py`
- `.claude/rules/tests.md` — `tests/**`
- `.claude/rules/docs.md` — `SPEC.md`, `ARCHITECTURE.md`, `docs/**`

## Workflow skills (repo-local)

Named with a `repo-` prefix on purpose: personal skills called `spec`, `build`,
`backprop`, `check` take precedence over project skills with the same name, so
unprefixed copies here would never load.

| Skill | Does | Writes |
|---|---|---|
| `repo-plan` | plan one §T task | only `docs/design/tasks/t<N>_*_plan.md` |
| `repo-spec` | new / distil / amend / backprop SPEC | only `SPEC.md` |
| `repo-build` | implement one §T task, flip its status | code + tests + LIVING docs |
| `repo-backprop` | bug → §B → §V → failing test → fix | `SPEC.md`, `tests/`, code |
| `repo-check` | drift audit SPEC/ARCHITECTURE vs code | nothing (read-only) |

## Verification habits

- Show command output; never assert success without it.
- UI check: run `scripts/ui_snapshot.py`, then **Read the PNG**. The live window cannot be
  captured on this Wayland desktop.
- Use the session scratchpad for snapshots and smoke downloads, never the repo.
- Kill app processes by PID or full interpreter path; `pkill -f "python3 -m vd98"` also
  matches the agent's own shell (see `docs/journal/2026-10-06_agentic-setup.md`).
