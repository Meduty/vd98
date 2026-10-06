# Video Downloader 98 — agent guide

Local Linux desktop app: paste a URL, get the video. yt-dlp engine, pywebview (Qt)
window, Windows 98 look via vendored 98.css. Single user, no server, no secrets.
**Source of truth: [SPEC.md](SPEC.md).** Code map: [ARCHITECTURE.md](ARCHITECTURE.md).
Read by Claude Code (via `CLAUDE.md`) and Codex CLI.

## Commands

    uv sync                                   # install (Python 3.12 via .python-version)
    uv run ruff check .                       # lint, must print "All checks passed!"
    uv run ruff format --check .              # format gate (CI enforces)
    uv run pytest -q                          # full suite, offline, < 1 s
    uv run vd98                               # launch the app
    QT_QPA_PLATFORM=offscreen uv run python scripts/ui_snapshot.py OUT.png   # UI check
    scripts/review.sh                         # Codex read-only review of branch vs main

## Definition of done

1. `ruff check`, `ruff format --check` clean AND `pytest -q` green — paste the tail of the output.
2. Behaviour change → a test that fails without the change (show it failing once).
3. Known bug fixed → remove its `xfail` in `tests/test_known_bugs.py`, close the §B row.
4. LIVING docs updated in the same commit: SPEC §T status (+ §I/§V if touched),
   ARCHITECTURE.md, `docs/live/*`.
5. Review pass before calling done: `scripts/review.sh`; verify each finding against code,
   answer each "fixed in <sha>" or "dismissed: <reason>".
6. UI touched → offscreen snapshot, open the PNG and look. Download path touched → real
   smoke. Both in `docs/live/e2e_testing.md`. Window chrome / sounds / dialogs → ask the user.

## Docs map

| Doc | Status | Holds |
|---|---|---|
| `SPEC.md` | LIVING | contract: §G goal, §C context, §I interfaces, §V invariants (each names its guard), §T tasks, §B bugs, §D deferred |
| `FORMAT.md` | LIVING | house style for SPEC (IDs only go up, one rule per entry) |
| `ARCHITECTURE.md` | LIVING | systems, patterns, "where do I find X", end-to-end walkthrough |
| `docs/live/` | LIVING | per-topic docs reconciled to code (`e2e_testing.md`) |
| `docs/design/tasks/` | FROZEN | one plan per §T task, never retrofitted |
| `docs/journal/` | FROZEN | dated entries: why, process notes, agent errors |
| `docs/release/<ver>/HANDOFF.md` | FROZEN | done / open / how to resume |

"Docs lie; code wins." Verify a doc claim by reading the code before building on it.

## Hard rules

- Branch before committing; never commit to `main` (protected: PR + green CI required).
- Never `git add -A`, `git add .`, `git add -u`, `git commit -a`. Stage explicit paths:
  `git add -- <files>`, then check `git diff --cached --stat` shows only this task.
- No secrets anywhere in the repo or agent context (SPEC V.12). The project has none; if one
  appears, stop and ask. Enforcement is per effect (V.16–V.19): Claude Code's OS sandbox denies
  shell reads of secret paths, deny rules cover the file tools, and `scripts/check_secrets.py`
  checks staged content in the pre-commit hook and in CI. Once per clone:
  `git config core.hooksPath .githooks`.
- A block from the sandbox, a permission rule or the hook means stop and ask the user. Changing
  `.claude/settings.json`, `.claude/hooks/**` or `.githooks/**` is the user's job; agents can't
  edit them.
- Never move or rename frozen paths (SPEC C.11): `src/vd98/web/vendor/`, the `vd98` script,
  `scripts/install-desktop.sh`, settings dir `video-downloader-98`.
- No shell in app code; `subprocess` with arg lists only (SPEC V.2).
- Remote strings (titles, errors, URLs) reach the DOM via `textContent` only (SPEC V.9).
- Tests stay offline: inject a fake `ydl_factory`, never hit the network in `tests/` (SPEC V.5).
- Don't lower the bar: no new `noqa`, `xfail`, `skip`, deleted asserts or relaxed gates
  without a SPEC §D entry explaining why.
- SPEC edits follow `FORMAT.md`: IDs only go up, retired entries struck through.
- Network/real-download checks write to a scratch dir, never the repo.

## Per-task loop (one SPEC §T row)

0. **Setup** — fresh branch from up-to-date `main`: `git switch main && git pull && git switch -c <type>/t<N>-<topic>`.
1. **Read** — §T row, every §V/§B/§D it touches, ARCHITECTURE section for the layer,
   `docs/live/*`, and all copies of the code you will change.
2. **Plan** — write `docs/design/tasks/t<N>_<topic>_plan.md`: gap table
   (piece | file:line | ✅/🔶/❌), genuine forks only (recommendation + trade-off),
   acceptance as commands + expected output, "SPEC changes needed". Get user OK on forks.
3. **Build** — failing test first, named after the §V it guards. Implement. On failure classify:
   my bug · spec wrong · unspecified edge → for the last two add §B row, link §V, strengthen guard.
   Stuck twice on tooling → read official docs, cite the URL.
4. **Verify** — paste gate output; run the e2e check that matches what you touched.
5. **Land** — update SPEC §T/ARCHITECTURE/docs/live in the same commit; stage explicit paths;
   review (`scripts/review.sh`), fix, re-test; commit message says why
   (bugs: `fix: backprop §B.n + §V.m: <cause>`); push; open PR citing the §T row with test
   output. Merge only with CI green, branch up to date, every comment answered.
   Found-not-fixed bugs → `gh issue create --label bug` and a §B row.
6. **Record** — after milestones, add a `docs/journal/YYYY-MM-DD_<topic>.md` entry
   (incl. agent errors) and run a drift check (SPEC vs code); no 🔴 findings.

## Layer notes

- **Core** (`src/vd98/{manager,urls,formats,settings}.py`): no GUI imports. State changes only
  through `DownloadManager._update` under the lock; callbacks outside the lock.
- **Bridge** (`src/vd98/api.py`): plain JSON-able returns, `{error}` instead of raising
  (SPEC V.11). Private attrs underscored so pywebview does not expose them.
  New method → add to SPEC §I and to `MOCK_API` in `scripts/ui_snapshot.py`.
- **UI** (`src/vd98/web/`): vanilla JS, no build step, no CDN (SPEC V.14). Poll, don't push.
