# SPEC — Video Downloader 98

> **Status: LIVING** — contract for `src/vd98/`. Style: [FORMAT.md](FORMAT.md). **Reconciled:** 2026-10-06.

## §G Goal

- G.1: Local Linux desktop app: paste URL → video/audio file on disk.
- G.2: Windows 98 look via vendored 98.css inside pywebview window.
- G.3: Queue, format presets, retro sounds. Single video per URL (no playlists).

## §C Context

- C.1: Python 3.12 (`.python-version`), uv + `uv_build` backend (`pyproject.toml`). Locked: yt-dlp 2026.8.19, pywebview 6.2.1, PyQt6 / PyQt6-WebEngine 6.11, pytest 9.1.1, ruff 0.16.10 (`uv.lock`).
- C.2: Engine = yt-dlp as Python lib. `ffmpeg` on PATH needed for merge + audio extract; absence → warning dialog only (`src/vd98/api.py` `Api.init`, `src/vd98/web/app.js` `start`).
- C.3: GUI = pywebview Qt backend, frameless window, `private_mode=True` (`src/vd98/app.py` `run`). UI = HTML/CSS/JS in `src/vd98/web/`, offline; 98.css v0.1.21 + MS Sans Serif webfonts vendored in `src/vd98/web/vendor/` with MIT notice `98.css.LICENSE`.
- C.4: Entry points: `vd98 = "vd98:main"` (`pyproject.toml`), `python -m vd98` (`src/vd98/__main__.py`).
- C.5: State: job list in memory; unfinished jobs (queued/downloading/processing/paused) also persisted to `$XDG_STATE_HOME/video-downloader-98/queue.json`, fallback `~/.local/state/…` (`src/vd98/queue_store.py` `state_path`), so they survive restarts (V.20). Settings: `$XDG_CONFIG_HOME/video-downloader-98/settings.json`, fallback `~/.config/…` (`src/vd98/settings.py` `config_path`). Keys: `download_dir`, `preset`, `sound`.
- C.6: Secrets: none. No tokens, keys, signing. Guard anyway (V.12).
- C.7: Privacy: no telemetry. Network only to URLs user submits (via yt-dlp).
- C.8: Platform: Linux only. Desktop launcher user-local via `scripts/install-desktop.sh`; bakes absolute uv + repo path.
- C.9: CI: GitHub Actions `.github/workflows/ci.yml` on push to any branch + PR: secret scan (branch's and `main`'s scanner) → `uv sync --locked` → `ruff check` → `ruff format --check` → `pytest -q`. Actions tag-pinned; uv version unpinned.
- C.10: Language: English UI + docs.
- C.11: Frozen paths (never move/rename): `src/vd98/web/vendor/`, script name `vd98`, `scripts/install-desktop.sh`, settings dir name `APP_DIR = "video-downloader-98"` (`src/vd98/settings.py`). Reason: license notice + `index.html` refs; installed launchers; README; user data location.
- C.12: Agents: Claude Code (`CLAUDE.md`, `.claude/`) + Codex CLI (`AGENTS.md`). Cross-model reviewer = Codex.

## §I Interfaces

Python core:
- I.1: `normalize_url(raw) -> str`, raises `InvalidURL(ValueError)` — `src/vd98/urls.py:12`.
- I.2: `preset_opts(key) -> dict` (fresh copy), raises `ValueError` on unknown key; `preset_list() -> [{key, label}]` — `src/vd98/formats.py:49`, `:61`.
- I.3: `settings.load(path=None) -> dict`; `settings.save(settings, path=None, base=None) -> dict` (invalid keys fall back to `base` or defaults, atomic tmp+replace) — `src/vd98/settings.py:45`, `:54`.
- I.4: `DownloadManager(ydl_factory=yt_dlp.YoutubeDL)` — `src/vd98/manager.py:88`. Starts one daemon worker in ctor. Methods: `add(url, preset, dest_dir) -> job` raises `ValueError` (:110); `cancel(id) -> bool` (:124); `cancel_all()` (:203); `remove(id) -> bool` terminal only (:207); `clear_finished()` (:215); `get(id) -> job|None` (:220); `jobs() -> [job]` (:225); `wait_idle(timeout) -> bool` (:229); attr `on_progress(job)` called outside lock.
- I.5: Job dict: `id, url, preset, dest_dir, title, status, percent, speed, eta, total_bytes, size_estimated, downloaded_bytes, filename, error` — `src/vd98/manager.py` `Job.public`. `eta` is the half-window estimate (V.22), falling back to yt-dlp's.
- I.4a: `DownloadManager(ydl_factory, clock=time.monotonic, store=None)`; `suspend(timeout) -> bool`, `restore() -> int`, `resume(id) -> bool`, `resume_all() -> int`; `cancel(id)` also accepts paused jobs (cleans their partials) — `src/vd98/manager.py`.

JS bridge `Api` (`src/vd98/api.py:19`, exposed as `window.pywebview.api`; JS caller in `src/vd98/web/app.js`):
- I.6: `add(url, preset) -> job | {error}` — caller `addUrl`.
- I.7: `cancel(id) -> bool`, `remove(id) -> bool`, `clear_finished() -> true`.
- I.8: `get_state() -> {jobs, settings}` — polled every 500 ms by `refresh`.
- I.9: `init() -> {jobs, settings, presets, ffmpeg, restored}` — caller `start`.
- I.10: `save_settings(patch) -> settings | {error}`; `choose_folder() -> settings | None`.
- I.11: `open_folder(path=None) -> bool` — `xdg-open` on dir (file → parent).
- I.12: `minimize()`, `maximize(on)`, `close()` (suspends all jobs keeping partials (V.21), destroys window); `about() -> {app, yt_dlp}`. Bad job ids to `cancel`/`remove`/`resume` → False (`Api._job_id`: ints and digit strings only). WM close → `_on_window_closing` (suspends, never cancels the close).
- I.13: `start_move() -> bool`, `start_resize(edge) -> bool` (`edge` ∈ `n s e w ne nw se sw`) — hand a title-bar drag / edge drag to the window manager via `WindowChrome` (`src/vd98/chrome.py`); False when no window or unknown edge. Callers: `#titlebar` and `.rs` handle `mousedown` in `src/vd98/web/app.js` `wire`.
- I.14: `resume(id) -> bool` (bad id → False), `resume_all() -> int`; `init()` adds `restored: int`; `close()` suspends instead of cancelling (V.21). Callers: `#resume` button, File → Resume All in `src/vd98/web/app.js`.

## §V Invariants

- V.1: Only http/https URLs reach yt-dlp. Non-http(s) scheme → `InvalidURL` before any job exists.
  Guard: `tests/test_urls.py::test_rejects_bad_urls`, `tests/test_manager.py::test_add_rejects_invalid_input`. (Gap: B.7.)
- V.2: No shell. `subprocess` only with arg list; only call site `xdg-open <existing dir>` in `Api.open_folder`.
  Guard: `tests/test_api.py::test_open_folder_rejects_missing_dir` (partial; no grep guard → T.9).
- V.3: One worker thread per `DownloadManager`; downloads strictly sequential.
  Guard: `tests/test_manager.py::test_sequential_single_worker`.
- V.4: Job status ∈ {queued, downloading, processing, paused, done, error, cancelled}. Terminal = {done, error, cancelled}; terminal status never changes. `paused` is not terminal: only `resume` (→ queued) or `cancel` (→ cancelled) leave it.
  Guard: `tests/test_manager.py::test_terminal_state_is_final`, `::test_terminal_set`, `tests/test_resume.py::test_paused_is_not_terminal`.
- V.5: Tests run offline: manager tested via fake `ydl_factory`; no network in `tests/`.
  Guard: unguarded (convention; `FakeYDL` in `tests/test_manager.py`).
- V.6: Missing/corrupt/invalid settings file → defaults; `load` never raises.
  Guard: `tests/test_settings.py::test_missing_file_gives_defaults`, `::test_corrupt_file_gives_defaults`, `::test_non_dict_gives_defaults`, `::test_invalid_values_replaced`. (Broken: B.1.)
- V.7: Unknown preset rejected before job exists.
  Guard: `tests/test_formats.py::test_unknown_preset_rejected`, `tests/test_manager.py::test_add_rejects_invalid_input`.
- V.8: Cancel removes partial files (`.part`, `.ytdl`) only inside job `dest_dir`.
  Guard: `tests/test_manager.py::test_cancel_running_download_removes_partial` (path-escape branch untested → T.9).
- V.9: Remote strings (title, error, url) rendered in UI via `textContent`/attributes only; no `innerHTML`.
  Guard: unguarded (comment `src/vd98/web/app.js:2`; grep guard → T.9).
- V.10: Cancelled queued job never runs.
  Guard: `tests/test_manager.py::test_cancel_queued_job_never_runs`.
- V.11: `Api` methods return `{error}` / falsy instead of raising for bad input (docstring `src/vd98/api.py:4`).
  Guard: `tests/test_api.py::test_add_returns_error_dict_for_bad_url`, `::test_save_settings_rejects_garbage`. (Broken: B.4.)
- V.12: No secret enters git or the agent's context: `.env*`, `.envrc`, `*.pem`, `*.key`, `*.p12`, `*.jks`, `*.keystore`, `secret/`, `secrets/` untracked + gitignored, and unreadable to the agent. Enforced per effect by V.16–V.19 (T.14), not by parsing command text (D.11).
  Guard: V.16–V.19 guards; `.gitignore`.
- V.13: Frozen paths C.11 exist at their path.
  Guard: `tests/test_layout.py::test_frozen_paths_exist`.
- V.14: UI works offline: no `http(s)://` resource loads in `src/vd98/web/*.html|*.css` outside vendor.
  Guard: `tests/test_layout.py::test_ui_has_no_remote_assets`.
- V.15: Frameless window moves and resizes through the window manager (`QWindow.startSystemMove` / `startSystemResize`), never `QWidget.move`; the Qt calls run on the GUI thread; every `data-edge` handle in `index.html` maps to a known edge.
  Guard: `tests/test_chrome.py::test_requests_from_worker_thread_run_on_gui_thread`, `::test_edge_names_match_ui_handles`, `::test_edges_for_known_names`. Real drag on Wayland: manual (`docs/live/e2e_testing.md`).
- V.16: Shell commands (and their child processes) cannot read secret paths: Claude Code OS sandbox on (`enabled`, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`) with `sandbox.filesystem.denyRead` for the V.12 names (`.claude/settings.json`). Known limit: a secret created inside the same command that reads it is not covered (Linux expands denyRead wildcards per command).
  Guard: `scripts/sandbox_probe.sh check` (human runs `setup`/`cleanup` outside the sandbox; `check` exits 2 if `setup` never ran): 14/15 BLOCKED on 2026-10-06 (incl. nested `secrets/`, `.envrc` and an SSH key name), the leak being the same-command case above; a file created in an earlier command is BLOCKED.
- V.17: No commit adds a secret, however it was staged: the staged content is scanned by name and for credential-shaped strings (`scripts/check_secrets.py --staged` via `.githooks/pre-commit`, `core.hooksPath=.githooks`); CI scans every tracked file (`--all`) on every pushed branch and PR, with the branch's scanner and with `main`'s. Limits, stated plainly: the scan is pattern-based (known token formats, private-key headers, secret file names), so a generic `password = …` in an ordinary file passes; the workflow lives in the branch, so a branch that edits or deletes it skips its own CI scan, and `main` is protected only because its branch protection requires the CI check to pass before merge; a secret on a pushed branch is on GitHub before CI runs. Skipping the local hook (`--no-verify`, `-n`, `-c`/`GIT_CONFIG_*`/`git config core.hooksPath`) is nudged (V.19), not prevented. Reports name the file, never the content.
  Guard: `tests/test_check_secrets.py` (incl. `git add -f` of an ignored key file, no-content-in-report, whole repo clean).
- V.18: File tools (Read/Edit/Write/Grep/Glob/NotebookEdit) on secret paths are refused: permission deny rules in `**/` (any depth) and `/` (project-relative) form, never `./` (cwd-relative), plus the path check in `.claude/hooks/guard.py`, which also resolves symlinks. The agent cannot edit `.claude/settings.json`, `.claude/hooks/**`, `.githooks/**` (deny rules; sandbox protected paths for shell writes).
  Guard: `tests/test_guard.py::test_file_tools_on_secret_paths_blocked`, `::test_file_tools_on_ordinary_paths_allowed`, `::test_symlink_to_secret_file_blocked`; shell writes: `os.access(…, W_OK)` is False for those three paths inside the sandbox (checked 2026-10-06).
- V.19: `git add -A|--all|-u|.|:/` and `git commit -a|--all` are nudged toward explicit paths by the hook. A workflow hint with no exemptions, not a security boundary (V.17 is).
  Guard: `tests/test_guard.py::test_bulk_staging_nudged`, `::test_explicit_staging_allowed`, `::test_shell_secret_reads_are_the_sandboxes_job`.
- V.20: Unfinished jobs survive an app restart: every status change saves them (`QueueStore`, atomic); on start they come back as `paused` and nothing runs until the user resumes. A missing, corrupt or partly invalid queue file yields only the valid entries, never an exception (same rules as V.1, V.7 for url/preset).
  Guard: `tests/test_queue_store.py`, `tests/test_resume.py::test_restore_then_resume_finishes_and_clears_store`, `tests/test_api.py::test_restored_jobs_reported_by_init`.
- V.21: Closing the app never deletes partial files: close (title bar or WM) suspends (`DownloadManager.suspend`), the running job becomes `paused` with its `.part` kept; only an explicit cancel cleans up.
  Guard: `tests/test_resume.py::test_suspend_keeps_partial_and_pauses` (mutation-checked: routing suspend through cancel fails 3 tests), `tests/test_api.py::test_close_suspends_instead_of_cancelling`; real smoke in `docs/live/e2e_testing.md`.
- V.22: ETA = remaining bytes ÷ rate over the most recent half of what was downloaded (from when the download had half its current size to now); a new file restarts the window; a stall gives no ETA, not a huge one.
  Guard: `tests/test_eta.py`, `tests/test_manager_progress.py::test_eta_comes_from_half_window_not_yt_dlp` (fails if wired back to yt-dlp's ETA).

## §T Tasks

| # | Task | Files | Depends | Est | Status |
|---|------|-------|---------|-----|--------|
| T.1 | urls, formats, settings + tests | `src/vd98/{urls,formats,settings}.py` | — | M | done |
| T.2 | manager + tests | `src/vd98/manager.py` | T.1 | M | done |
| T.3 | api + window + web UI | `src/vd98/{api,app}.py`, `src/vd98/web/` | T.2 | L | done |
| T.4 | CI, README, desktop entry, GH repo | `.github/`, `README.md`, `scripts/` | T.3 | S | done |
| T.5 | Agentic repo prep (this setup) | `SPEC.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `docs/` | T.4 | L | done |
| T.6 | Format whole tree with `ruff format`, add format gate to CI | `src/`, `tests/`, `.github/workflows/ci.yml` | T.5 | S | done |
| T.7 | Fix settings type robustness: B.1, B.4 | `src/vd98/settings.py`, `src/vd98/formats.py`, `src/vd98/api.py` | T.5 | S | todo |
| T.8 | Fix manager races/gaps: B.2, B.3, B.5, B.6 | `src/vd98/manager.py` | T.5 | M | todo |
| T.9 | Grep guards for V.2, V.9; test V.8 path-escape branch | `tests/` | T.5 | S | todo |
| T.10 | Fix UI bugs: B.8, B.9, B.10 | `src/vd98/web/app.js` | T.5 | M | todo |
| T.11 | URL hardening: B.7 | `src/vd98/urls.py` | T.5 | S | todo |
| T.12 | install-desktop.sh: escape sed replacement, add uninstall, ffmpeg check | `scripts/install-desktop.sh` | T.5 | S | todo |
| T.13 | CI pinning: pin uv version; consider SHA-pinned actions (D.4) | `.github/workflows/ci.yml` | T.6 | S | todo |
| T.14 | Effect-level secret protection: sandbox denyRead, staged-content scan (pre-commit + CI), deny rules, guard shrunk to nudge + file-tool paths, sandbox probe | `.claude/settings.json`, `.claude/hooks/guard.py`, `scripts/check_secrets.py`, `scripts/sandbox_probe.sh`, `.githooks/pre-commit`, `.github/workflows/ci.yml` | T.5 | L | doing |
| T.15 | `%` and `Size` columns (size `~` when estimated) | `src/vd98/manager.py`, `src/vd98/web/{index.html,app.js,app.css}` | T.3 | S | done |
| T.16 | Smoothed ETA over the most recent half of the download (V.22) | `src/vd98/eta.py`, `src/vd98/manager.py` | T.3 | S | done |
| T.17 | Resume downloads after an accidental close: persisted queue, close = suspend keeping partials, restore as paused, Resume / Resume All (V.20, V.21) | `src/vd98/queue_store.py`, `src/vd98/manager.py`, `src/vd98/api.py`, `src/vd98/app.py`, `src/vd98/web/` | T.3 | M | done |

## §B Bugs / backprop

Found 2026-10-06 by T.5 research; each reproduced or read in code before recording.

| # | Date | Symptom | Cause | Fix | Guard |
|---|------|---------|-------|-----|-------|
| B.1 | 2026-10-06 | settings file `{"preset": []}` → `settings.load` raises `TypeError: unhashable type: 'list'` | `data.get("preset") in PRESETS` on unhashable value, `src/vd98/settings.py` `_clean` | open → T.7 | V.6 |
| B.2 | 2026-10-06 | `wait_idle` may return True while job still queued | `add` clears `_idle` under lock but `queue.put` after release; worker can set idle in between, `src/vd98/manager.py` `add` / `_worker` | open → T.8 | V.3 (new test needed) |
| B.3 | 2026-10-06 | Cancel during processing (or before first hook) returns True, job may end `done` | cancel flag checked only in progress hook, `src/vd98/manager.py` `_on_hook` | open → T.8; UI already disables Cancel in processing | V.4 |
| B.4 | 2026-10-06 | `Api.cancel("x")` / `Api.remove(None)` raise instead of returning False; `preset_opts([])` raises `TypeError` not `ValueError`, uncaught by `Api.add` | `int(job_id)` unguarded `src/vd98/api.py` `cancel`/`remove`; dict lookup on unhashable `src/vd98/formats.py` `preset_opts` | API part fixed 2026-10-06 (`Api._job_id`, PR #3 review; xfail removed, now a regression test); `preset_opts([])` part still open → T.7 | V.11 |
| B.5 | 2026-10-06 | queued→cancelled never fires `on_progress` | `cancel` sets status directly, skips `_update`, `src/vd98/manager.py` `cancel` | open → T.8 | V.10 |
| B.6 | 2026-10-06 | Cancel cleanup misses `<file>.ytdl`, `-Frag*`, finished `.fNNN` intermediates | candidates = tmpfilenames + `filename + ".part"` only, `src/vd98/manager.py` `_cleanup_partials` | open → T.8 | V.8 |
| B.7 | 2026-10-06 | `normalize_url("mailto:a@b")` → `https://mailto:a@b`; `\x00` accepted | scheme-less branch prepends `https://` to anything without `://`; only whitespace rejected, `src/vd98/urls.py` `normalize_url` | open → T.11 | V.1 |
| B.8 | 2026-10-06 | Enter with empty URL: warning dialog opens and closes instantly | URL keydown calls `addUrl` → `showDialog`; same Enter bubbles to document handler → `hideDialog`, `src/vd98/web/app.js` `wire` | open → T.10 | unguarded |
| B.9 | 2026-10-06 | Double-click finished row likely does not open folder; opens current `download_dir` not job folder | click handler re-renders rows before dblclick lands; handler ignores `job.dest_dir`, `src/vd98/web/app.js` `wire` | open → T.10 | unguarded |
| B.10 | 2026-10-06 | UI dead if `init`/`about` rejects at startup | `start` awaits without try; `wire()` never runs, `src/vd98/web/app.js` `start` | open → T.10 | unguarded |
| B.11 | 2026-10-06 | `git status` + newline + `git add -A` passed the guard (Codex review) | `shlex` treats `\n` as whitespace, so commands on separate lines formed one segment and the `status` exemption returned early, `.claude/hooks/guard.py` `split_segments` | fixed T.5: newline is punctuation, not whitespace; quoted newlines stay inside the word | V.12 |
| B.12 | 2026-10-06 | Guard blocked prose: heredoc text containing the bare word "secret" (agent's own edit script) | every word checked as a path; bare `secret` matched `SECRET_DIRS`, `.claude/hooks/guard.py` `is_secret_path` | fixed T.5: `secret`/`secrets` dirs match only in path form (contains `/`) | V.12 |
| B.13 | 2026-10-06 | `cat .envrc`, `cat .env_prod`, `python3 -c 'open(".env")'` passed the guard (Codex review) | `.env` matched only exact or `.env.` prefix; inline interpreter code was one opaque word, `.claude/hooks/guard.py` `is_secret_path` / `check_segment` | fixed T.5: `.env*` prefix; code after `-c`/`-e`/`--eval` scanned for path tokens; `.gitignore` → `.env*` | V.12 |
| B.14 | 2026-10-06 | CSS `@import "https://…"` passed the offline-UI guard (Codex review) | regex covered `src=`/`href=`/`url(` only, `tests/test_layout.py` `test_ui_has_no_remote_assets` | fixed T.5: also `@import "…"`, `fetch(`/`import(` with http(s) | V.14 |
| B.15 | 2026-10-06 | `python3 - <<'EOF'` with a body opening `.env` passed the guard; data heredocs naming `secret/` in path form (reviewer prompts, `git commit -F -` bodies) were blocked | each heredoc body line became its own segment and its first word was never checked; data and code heredocs were not told apart, `.claude/hooks/guard.py` `check_bash` | fixed T.5: quoted heredoc fed to `cat`/`tee`/`git commit -F -` → body dropped (`strip_data_heredocs`); every other heredoc body scanned as code (`heredoc_bodies`). Same rules ported upstream to the agentic-repo-prep guide template | V.12 |
| B.17 | 2026-10-06 | Body of `cat > /tmp/run.sh <<'EOF'` dropped as data although the same command then ran the file (`sh /tmp/run.sh`), hiding a secret read (found by Codex reviewing the upstream port) | data-sink test looked only at the heredoc's own line, `.claude/hooks/guard.py` `strip_data_heredocs` | fixed T.5: body dropped only if nothing follows the heredoc and no earlier text names the written file; a file run by a later tool call stays out of scope (D.11) | V.12 |
| B.16 | 2026-10-06 | User report: window can't be dragged by the title bar; edges can't be resized (KDE/GNOME Wayland) | pywebview's drag-region JS calls `QWidget.move()`, which Wayland ignores (clients can't position windows); frameless window has no compositor borders to resize; `src/vd98/web/index.html` `pywebview-drag-region`, `src/vd98/app.py` `frameless=True` | fixed T.5: title-bar `mousedown` → `Api.start_move` → `QWindow.startSystemMove()`; 8 edge handles → `start_resize` → `startSystemResize(edges)`, dispatched to the GUI thread (`src/vd98/chrome.py` `WindowChrome`); double-click title bar toggles maximize | V.15 |
| B.18 | 2026-10-06 | `bash -lc 'cat .env'` / `sh -ec '…'` not inspected by the guard (Codex, PR #1 round 1) | guard looked for a standalone `-c` only, `.claude/hooks/guard.py` `check_segment` | superseded by T.14: the hook no longer parses shell; probe case "bash -lc string" BLOCKED by the sandbox | V.16 |
| B.19 | 2026-10-06 | Globs expanding to secret files (`cat ./.*`, `git add -f ./*`) not seen by the guard (Codex, PR #1 round 1) | guard checked literal words, not expansions | superseded by T.14: probe cases "glob ./.*", "glob *.pem" BLOCKED; staged `-f` keys caught by `check_secrets.py` | V.16, V.17 |
| B.20 | 2026-10-06 | A heredoc operator inside a comment made the guard skip lines bash runs (upstream review round 2, same code here) | text search for `<<'EOF'` instead of bash's parse | superseded by T.14: heredoc exemption gone with the parser; probe case "heredoc fed to python" BLOCKED | V.16 |
| B.21 | 2026-10-06 | Grep/Glob with a masked-extension glob (`*.p?x`, `secr?t/*`) passed the file-tool check; `.pfx`/`.kdbx` missing from Read deny rules (Codex, PR #2 round 1) | literal string check in `guard.py` `is_secret_path`; deny list incomplete | fixed: globs with literal parts matched against `SECRET_NAME_EXAMPLES` (pure wildcards allowed: names aren't contents); Read/Edit deny for `.pfx`, `.kdbx`, Edit for `.pem`, `.key` (installed by the user: files locked) | V.18 |
| B.22 | 2026-10-06 | A credential in a staged file over 2 MB was accepted (Codex, PR #2 round 1) | `check_secrets.py` skipped content past `MAX_BYTES` | fixed: every blob scanned in full (repo scan 0.04 s); `test_large_files_are_scanned_too` | V.17 |
| B.23 | 2026-10-06 | `git -c core.hooksPath=… commit` / `-n` / `--no-verify` skipped the pre-commit scan (Codex, PR #2 round 1) | only `--no-verify` was denied | fixed as a nudge: guard `skips_precommit` + deny rules. Not a boundary: CI's `--all` scan is the backstop, so a skipped local scan can still put a secret on a pushed branch before CI runs | V.17, V.19 |
| B.24 | 2026-10-06 | `sandbox_probe.sh check` would overwrite and delete a real `.env.late` (Codex, PR #2 round 1) | fixed fixture name | fixed: `.env.probe-late-$$`, skipped if it exists | V.16 |
| B.25 | 2026-10-06 | `env git add -A` / `sudo …` / `nice -n 5 …` got no staging nudge (Codex, PR #2 round 1) | `git_call` required `git` as the first word | fixed: `_strip_prefixes` looks through wrappers and `VAR=x` | V.19 |
| B.26 | 2026-10-06 | WM close refused when a suspend timed out (e.g. ffmpeg converting) (Codex, PR #3 round 1) | closing handler returned `suspend()`'s result; pywebview cancels the close on `False`, `src/vd98/app.py` | fixed: `Api._on_window_closing` suspends and returns `None`; `test_window_closing_never_cancels_the_close` | V.21 |
| B.27 | 2026-10-06 | An older queue snapshot could overwrite a newer save, dropping a just-added job from the resume queue (Codex, PR #3 round 1) | snapshot taken before acquiring `_persist_lock`, `src/vd98/manager.py` `_persist` | fixed: snapshot inside the lock (order `_persist_lock` → `_lock`); `test_older_snapshot_never_overwrites_newer_one` forces the interleaving and failed before the fix | V.20 |
| B.28 | 2026-10-06 | ETA stayed finite (and grew) during a stall that followed progress (Codex, PR #3 round 1) | stall only detected when no bytes arrived since the window's reference sample, `src/vd98/eta.py` | fixed: no new bytes for `STALL_SECONDS` (5 s) → no ETA; a 1 s hiccup keeps it | V.22 |
| B.29 | 2026-10-06 | `resume(1.9)` / `True` truncated to job 1 (Codex, PR #3 round 1) | `int(job_id)` in `Api` | fixed with B.4's API part: `Api._job_id` accepts ints and digit strings only | V.11 |
| B.30 | 2026-10-06 | Grep/Glob/Read with a bare relative path `secret` / `secrets` (no slash) passed the file-tool check (Codex, PR #3 round 1) | leftover Bash-prose exemption: the last path part only counted as the folder when the value contained `/`, `.claude/hooks/guard.py` `is_secret_path` | fixed: every path part is checked (the shell parser that needed the exemption is gone); `test_bare_relative_secret_dir_blocked` (4 cases failed before), words that merely contain "secret" stay allowed. Installed by the user (hook locked) | V.18 |
| B.31 | 2026-10-06 | One saved URL like `http://[` made `QueueStore.load()` raise, so restore failed at startup (Codex, PR #3 round 2) | `urlsplit` raises a plain `ValueError` ("Invalid IPv6 URL"); `_clean` caught only `InvalidURL`, `src/vd98/queue_store.py`, `src/vd98/urls.py` | fixed: `normalize_url` turns parse errors into `InvalidURL`; `_clean` also catches `ValueError`/`TypeError`; `test_unparseable_saved_url_skips_entry_not_startup` | V.20, V.1 |
| B.32 | 2026-10-06 | During a stall the UI showed yt-dlp's stale ETA after all, undoing B.28 (Codex, PR #3 round 2) | the manager fell back to `d["eta"]` whenever the smoothed ETA was `None`, including in a stall, `src/vd98/manager.py` `_on_hook` | fixed: `HalfWindowEta.stalled()`; fall back to yt-dlp only before there are enough samples, never during a stall; `test_stall_does_not_fall_back_to_yt_dlp_eta` | V.22 |
| B.33 | 2026-10-06 | Queue file world-readable (0644) while it stores full URLs, which can carry access tokens (Codex, PR #3 round 2) | default umask on `mkdir` / `write_text`, `src/vd98/queue_store.py` `save` | fixed: dir 0700, file written 0600 via `os.open`; `test_queue_file_is_private` | V.20 |
| B.34 | 2026-10-06 | After a kill (not a normal close) Cancel could not find the `.part`: the saved entry predated its discovery (Codex, PR #3 round 2) | paths reached the store only on status changes, `src/vd98/manager.py` `_on_hook` | fixed: save once when a new partial path first appears; `test_new_partial_path_saved_before_any_status_change` | V.20, V.8 |
| B.35 | 2026-10-06 | Read/Grep on a harmless-looking name that is a symlink to a secret file or folder passed the file-tool check (Codex, PR #3 round 2, finding 5) | path checked as written, never resolved, `.claude/hooks/guard.py:230` `check` | fixed: the literal path is resolved against the payload `cwd` (`real_path`) and the target checked too; `test_symlink_to_secret_file_blocked`, `::test_symlink_to_secret_dir_blocked` (failed before), `::test_ordinary_symlink_allowed`. Installed by the user (hook locked) | V.18 |
| B.36 | 2026-10-06 | `GIT_CONFIG_KEY_0=core.hooksPath … git commit` / `GIT_CONFIG_PARAMETERS` skipped the pre-commit scan without a nudge (Codex, PR #3 round 2, finding 6) | only `-c` global options were inspected, `.claude/hooks/guard.py:194` `skips_precommit` | fixed as a nudge: `env_skips_precommit` on the leading assignments of a `git commit`; `test_hookspath_overrides_nudged` (2 env cases failed before) | V.17, V.19 |
| B.37 | 2026-10-06 | `git config core.hooksPath /dev/null` (or `--unset`) turns the local scan off for every later commit; CI ran only on PRs and `main`, so a pushed feature branch carried a secret to GitHub unscanned (Codex, PR #2 round 2, finding 4) | nudge covered per-command skips only, `.claude/hooks/guard.py:194` `skips_precommit`; `.github/workflows/ci.yml:5` `branches: [main]` | fixed: guard nudges `config_skips_precommit` (3 cases failed before; `.githooks`, `--get`, plain read allowed); CI on `push` to every branch. A fresh clone without `core.hooksPath` still has no local scan (README step); CI is the backstop | V.17, V.19 |
| B.38 | 2026-10-06 | A branch could weaken its own secret scan by editing `scripts/check_secrets.py` or the CI step (Codex, PR #2 round 2, finding 2; the claimed shell writes to `.claude/hooks`, `.claude/settings.json`, `.githooks` are refused by the sandbox, checked with `os.access`) | CI ran only the branch's copy of the scanner, `.github/workflows/ci.yml:14` | fixed: CI also runs `main`'s `scripts/check_secrets.py` (`python3 -I` from `$RUNNER_TEMP`); skipped while `main` has none. A changed workflow file is still visible in review only | V.17 |
| B.39 | 2026-10-06 | `sandbox_probe.sh check` reported all BLOCKED when `setup` had never run (Codex, PR #2 round 2, finding 5) | inside the sandbox a missing fixture and a hidden one look the same; `attempt` counted "no marker" as BLOCKED, `scripts/sandbox_probe.sh:50` `check` | fixed: `setup` writes `$(git rev-parse --git-dir)/sandbox-probe-setup`, `check` exits 2 without it (shown: "NO SETUP … nothing tested", exit 2), `cleanup` removes it | V.16 |
| B.40 | 2026-10-06 | The sandbox block lists no nested `.envrc`, `secret`, `secrets` entries (Codex, PR #2 round 2, finding 1) | `.claude/settings.json:63` `sandbox.filesystem.denyRead` has root-level forms only; nested reads were BLOCKED in the probe only because the `Read(**/…)` deny rules merge into `denyRead` | fixed: `./**/.envrc`, `./**/secret`, `./**/secrets` added to the sandbox block itself so it stands alone (installed by the user; settings locked); the live session config lists them | V.16 |
| B.41 | 2026-10-06 | `env GIT_CONFIG_KEY_0=core.hooksPath … git commit` (assignments after a wrapper) skipped the pre-commit scan without a nudge (Codex, PR #2 round 3, finding 6) | the scan stopped at the first non-assignment word, `.claude/hooks/guard.py:218` `env_skips_precommit` | fixed: every `NAME=value` before the `git` word counts; `test_hookspath_overrides_nudged` (`env …`, `sudo -E …` failed before). Installed by the user (hook locked) | V.17, V.19 |
| B.42 | 2026-10-06 | A project-local SSH private key (`id_ed25519`, …) was readable by shell commands and not gitignored (Codex, PR #2 round 3, finding 3) | the guard and `check_secrets.py` knew the names, `.claude/settings.json:63` `sandbox.filesystem.denyRead` and `.gitignore` did not | fixed: `./id_*` and `./**/id_*` (rsa, ed25519, ecdsa, dsa) in the sandbox block (installed by the user), names in `.gitignore` (`.pub` stays allowed); probe case "ssh key name" | V.12, V.16 |
| B.43 | 2026-10-06 | `sandbox_probe.sh setup` could overwrite a real file at a fixture path other than `.env`, and `cleanup` then deleted it (Codex, PR #2 round 3, finding 5) | only `.env` was checked for an existing non-fixture file, `scripts/sandbox_probe.sh:23` `setup` | fixed: every fixture path is checked; an existing file without the marker stops setup (exit 2) | V.16 |
| B.44 | 2026-10-06 | SPEC claimed "a branch can't weaken its own scan", but a branch can edit or delete the workflow that runs the scan (Codex, PR #2 round 3, finding 1); also the scan misses generic `password = …` values (finding 4) | the workflow is branch-controlled, `.github/workflows/ci.yml:6`; `check_secrets.py` is pattern-based by design | doc fix: V.17 states both limits and what actually protects `main` (branch protection requires the CI check). Not fixable in-repo; server-side push protection would be the next step | V.17 |
| B.45 | 2026-10-06 | The window closes, but `uv run vd98` started from the `!` prompt did not seem to return afterwards (user GUI check on `main` 2029353; issue #5) | unknown. Hypotheses, unverified: the title-bar path suspends twice (`src/vd98/api.py:160` `close` → `destroy()` → `closing` event → `:150` `_on_window_closing`, up to 2 × 3 s); the closing handler may block the Qt GUI thread; a yt-dlp/ffmpeg child or WebEngine teardown may outlive the window | open → issue #5: measure click-to-exit on both close paths, idle and downloading | V.21 |

## §D Deferred / design questions

- D.1: `Api.open_folder(path)` accepts any existing dir from JS; JS never passes `path`. Options: drop param · restrict to job `dest_dir`s. Open.
- D.2: Overlapping 500 ms polls (no in-flight guard, `src/vd98/web/app.js` `start`). Harmless today. Open.
- D.3: Concurrent errors → each dialog replaces previous; only last shown. Queue dialogs? Open.
- D.4: SHA-pin GitHub Actions vs tag-pin. Private repo, low risk. Open (T.13).
- D.5: V.1 checks submitted URL only; yt-dlp redirects + localhost/private IPs allowed. Local app, user-driven → accept? Open.
- D.6: Maximize state tracked in JS only (`src/vd98/web/app.js` `maximized`); desyncs if WM maximizes (now also reachable by dragging to a screen edge, V.15). Open.
- D.7: `cancel_all` runs twice on exit (`Api.close` + `window.events.closing`, `src/vd98/app.py`). Idempotent, harmless. Open.
- D.8: Vendored MS Sans Serif webfonts ship inside 98.css package (MIT); no separate font attribution in README. Add credit line? Open.
- D.9: README says settings in `~/.config/video-downloader-98/`; code honours `$XDG_CONFIG_HOME`. Reword README? Open.
- D.10: Each `DownloadManager` leaks a daemon worker (tests create many). No `shutdown()`. Open.
- D.11: `.claude/hooks/guard.py` inspects words, not effects: a command reaching a secret without naming it (`grep -R TOKEN .`, a script file that opens one) passes. Options: accept (repo has no secrets, C.6) · enable Claude Code OS sandbox. Recommendation: accept for now (guard + deny rules stop accidents; a block means stop and ask); enable sandbox if a secret is ever added. **Decided 2026-10-06 (user):** after three review rounds kept finding holes in text parsing, prototype effect-level enforcement instead: sandbox for shell reads, deny rules for file tools, staged-content scan for commits (T.14, V.16–V.19).
- D.12: `~/.codex/auth.json` (Codex login) is readable from inside the sandbox, because Codex runs there and needs it (`~/.codex` in user `allowWrite`); a shell read could put it in the agent's context, against V.12 (Codex, PR #2 round 2, finding 3). Options: accept and document (the reviewer stays sandboxed, so it can't read project secrets) · log Codex in with an API key and pass it masked via `sandbox.credentials` (no token file to read) · run reviews outside the sandbox (`excludedCommands`, gives a second agent full read access). Recommendation: API key masked if the user's plan allows it, else accept. **Decided 2026-10-06 (user):** accept for shell reads (the subscription login has no API key; OpenAI bills API keys per use; a `keyring` store is expected to be unreachable from the sandbox, as `gh`'s is; untested). File tools are blocked from `~/.codex` / `$CODEX_HOME` by `.claude/hooks/guard.py` `private_path` (`tests/test_guard.py::test_codex_login_unreachable_by_file_tools`), not by a Read deny rule: those merge into the sandbox's `denyRead` and would lock Codex out of its own login.
