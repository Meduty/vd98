> **Status: FROZEN** (written 2026-10-06).
> Point-in-time record — verify against code before using.

# 0.1.0 handoff

## Done

- App: queue, presets, cancel + cleanup, Win98 UI, sounds, settings (SPEC T.1–T.4).
- Agentic setup: SPEC/FORMAT/ARCHITECTURE, docs tree, agent config, guard hook (T.5).
- CI: lint, format, tests on push/PR (T.6).

## Open

- Bugs B.1–B.10 → tasks T.7–T.11 (SPEC §B, §T). Strict xfails in `tests/test_known_bugs.py` pin B.1, B.4, B.5, B.7 only. B.2, B.3, B.6 (manager) have no xfail yet — add them first in T.8. B.8–B.10 (UI JS) have no automated test harness.
- B.11–B.14 (guard / offline-UI holes from Codex review) fixed in T.5.
- Installer hardening T.12, CI pinning T.13.
- Design questions D.1–D.11 (D.11: guard is word-level, sandbox decision pending).

## How to resume

1. Read `AGENTS.md` (or `CLAUDE.md`), then SPEC §T for the next `todo` row.
2. Follow the per-task loop in `AGENTS.md`.
3. Verify with `docs/live/e2e_testing.md`.
