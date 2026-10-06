> **Status: FROZEN** (written 2026-10-06). Append-only history.

# 2026-10-06 — Agentic repo prep (T.5)

## Why

Repo was built in one session (2026-10-06) without a written contract beyond a
short SPEC. Before handing further work to agents across sessions, the rules
need to live in the repo in a form agents load and check against.

## What happened

- Baseline: lint clean, 45 tests green, but `ruff format --check` failed on 8
  files and CI had no format gate. Fixed as T.6 in a formatting-only commit.
- Three read-only researchers (core, UI, docs/build) produced ~30 findings.
  All bug claims were reproduced by probe or read in code before recording;
  10 became §B entries, 10 became §D questions. None fixed in this branch.

## Agent errors (for future sessions)

- Marked SPEC T.6 `done` before doing it; caught on re-read, reverted to
  `todo`, flipped only after the commit landed. Lesson: status flips go in the
  same commit as the work.
- `pkill -f "python3 -m vd98"` matched the agent's own shell command line and
  killed it (exit 144). Lesson: match on full interpreter path or use PIDs.
- `astral-sh/setup-uv@v10` does not exist as a floating tag; CI failed until
  pinned to `v10.2.0`. Lesson: check tags with `gh api repos/<o>/<r>/tags`.
- Reformat moved line numbers; SPEC §I cites went stale within one commit.
  Lesson: cite symbols first, re-verify cites by script after formatting.

## Guardrails added

See SPEC V.12–V.14, `.claude/hooks/guard.py`, `tests/test_layout.py`,
`tests/test_known_bugs.py`.
