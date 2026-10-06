> **Status: FROZEN** (written 2026-10-06).
> Point-in-time record — verify against code before using.

# T.5 — Agentic repo prep: plan

Source: user-supplied guide "Preparing a Repository for AI Agents", steps 1–9.
Branch: `chore/agentic-setup`.

## Interview (step 1) — answers

| Question | Answer |
|---|---|
| Agent tools | Claude Code + Codex CLI → `CLAUDE.md` + `AGENTS.md` |
| Secrets store | None needed now; guard hook + deny rules anyway |
| "Done" in running app | Offscreen UI render + real download smoke |
| Second-opinion model | OpenAI Codex (`codex` CLI) |
| Never move | Decided by agent (user delegated): `src/vd98/web/vendor/`, `vd98` script, `scripts/install-desktop.sh`, settings `APP_DIR` |
| Current state | ruff check clean; ruff format: 8 files unformatted; pytest 45 passed; uv build OK; CI green on main |

## Steps and acceptance

| Step | Output | Acceptance |
|---|---|---|
| 2 Secrets sweep | none found | `git ls-files` / history greps empty |
| 3 Research | 3 read-only reports | every claim re-checked by grep or probe |
| 4 SPEC | `SPEC.md`, `FORMAT.md` | 7 sections, each §V names guard |
| 5 Tests + CI | `tests/test_layout.py`, `tests/test_known_bugs.py`, format gate | guards mutation-checked; CI green |
| 6 Map | `ARCHITECTURE.md` | all `path:line` cites resolve (script) |
| 7 Docs | `docs/` tree | every doc has status header |
| 8 Agent config | `AGENTS.md`, `CLAUDE.md`, `.claude/` | guard hook blocks `git add -A` + secret reads (tests) |
| 9 Review | Codex review, fixes, PR | each finding answered fixed/dismissed |

## Deviations from guide

- Guide's one-time setup uses `git add -A`; contradicts its own hard rule. Explicit paths used.
- Known bugs recorded as strict `xfail` tests instead of characterization tests that assert the buggy output: keeps intended behaviour visible and fails loudly when fixed.
