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
- C.5: State: in-memory job list only (lost on exit). Persistent: `$XDG_CONFIG_HOME/video-downloader-98/settings.json`, fallback `~/.config/…` (`src/vd98/settings.py` `config_path`). Keys: `download_dir`, `preset`, `sound`.
- C.6: Secrets: none. No tokens, keys, signing. Guard anyway (V.12).
- C.7: Privacy: no telemetry. Network only to URLs user submits (via yt-dlp).
- C.8: Platform: Linux only. Desktop launcher user-local via `scripts/install-desktop.sh`; bakes absolute uv + repo path.
- C.9: CI: GitHub Actions `.github/workflows/ci.yml` on push to main + PR: `uv sync --locked` → `ruff check` → `ruff format --check` → `pytest -q`. Actions tag-pinned; uv version unpinned.
- C.10: Language: English UI + docs.
- C.11: Frozen paths (never move/rename): `src/vd98/web/vendor/`, script name `vd98`, `scripts/install-desktop.sh`, settings dir name `APP_DIR = "video-downloader-98"` (`src/vd98/settings.py`). Reason: license notice + `index.html` refs; installed launchers; README; user data location.
- C.12: Agents: Claude Code (`CLAUDE.md`, `.claude/`) + Codex CLI (`AGENTS.md`). Cross-model reviewer = Codex.

## §I Interfaces

Python core:
- I.1: `normalize_url(raw) -> str`, raises `InvalidURL(ValueError)` — `src/vd98/urls.py:12`.
- I.2: `preset_opts(key) -> dict` (fresh copy), raises `ValueError` on unknown key; `preset_list() -> [{key, label}]` — `src/vd98/formats.py:49`, `:61`.
- I.3: `settings.load(path=None) -> dict`; `settings.save(settings, path=None, base=None) -> dict` (invalid keys fall back to `base` or defaults, atomic tmp+replace) — `src/vd98/settings.py:45`, `:54`.
- I.4: `DownloadManager(ydl_factory=yt_dlp.YoutubeDL)` — `src/vd98/manager.py:66`. Starts one daemon worker in ctor. Methods: `add(url, preset, dest_dir) -> job` raises `ValueError` (:79); `cancel(id) -> bool` (:91); `cancel_all()` (:101); `remove(id) -> bool` terminal only (:105); `clear_finished()` (:113); `get(id) -> job|None` (:118); `jobs() -> [job]` (:123); `wait_idle(timeout) -> bool` (:127); attr `on_progress(job)` called outside lock.
- I.5: Job dict: `id, url, preset, dest_dir, title, status, percent, speed, eta, filename, error` — `src/vd98/manager.py:23` `Job.public`.

JS bridge `Api` (`src/vd98/api.py:19`, exposed as `window.pywebview.api`; JS caller in `src/vd98/web/app.js`):
- I.6: `add(url, preset) -> job | {error}` — caller `addUrl`.
- I.7: `cancel(id) -> bool`, `remove(id) -> bool`, `clear_finished() -> true`.
- I.8: `get_state() -> {jobs, settings}` — polled every 500 ms by `refresh`.
- I.9: `init() -> {jobs, settings, presets, ffmpeg}` — caller `start`.
- I.10: `save_settings(patch) -> settings | {error}`; `choose_folder() -> settings | None`.
- I.11: `open_folder(path=None) -> bool` — `xdg-open` on dir (file → parent).
- I.12: `minimize()`, `maximize(on)`, `close()` (cancels all jobs, destroys window); `about() -> {app, yt_dlp}`.

## §V Invariants

- V.1: Only http/https URLs reach yt-dlp. Non-http(s) scheme → `InvalidURL` before any job exists.
  Guard: `tests/test_urls.py::test_rejects_bad_urls`, `tests/test_manager.py::test_add_rejects_invalid_input`. (Gap: B.7.)
- V.2: No shell. `subprocess` only with arg list; only call site `xdg-open <existing dir>` in `Api.open_folder`.
  Guard: `tests/test_api.py::test_open_folder_rejects_missing_dir` (partial; no grep guard → T.9).
- V.3: One worker thread per `DownloadManager`; downloads strictly sequential.
  Guard: `tests/test_manager.py::test_sequential_single_worker`.
- V.4: Job status ∈ {queued, downloading, processing, done, error, cancelled}. Terminal = {done, error, cancelled}; terminal status never changes.
  Guard: `tests/test_manager.py::test_terminal_state_is_final`, `::test_terminal_set`.
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
- V.12: No secrets in git: `.env*`, `*.pem`, `*.key`, `*.jks`, `*.keystore`, `secret/` untracked + gitignored.
  Guard: `.claude/hooks/guard.py` PreToolUse hook + `.claude/settings.json` deny rules; `tests/test_guard.py`.
- V.13: Frozen paths C.11 exist at their path.
  Guard: `tests/test_layout.py::test_frozen_paths_exist`.
- V.14: UI works offline: no `http(s)://` resource loads in `src/vd98/web/*.html|*.css` outside vendor.
  Guard: `tests/test_layout.py::test_ui_has_no_remote_assets`.

## §T Tasks

| # | Task | Files | Depends | Est | Status |
|---|------|-------|---------|-----|--------|
| T.1 | urls, formats, settings + tests | `src/vd98/{urls,formats,settings}.py` | — | M | done |
| T.2 | manager + tests | `src/vd98/manager.py` | T.1 | M | done |
| T.3 | api + window + web UI | `src/vd98/{api,app}.py`, `src/vd98/web/` | T.2 | L | done |
| T.4 | CI, README, desktop entry, GH repo | `.github/`, `README.md`, `scripts/` | T.3 | S | done |
| T.5 | Agentic repo prep (this setup) | `SPEC.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/`, `docs/` | T.4 | L | doing |
| T.6 | Format whole tree with `ruff format`, add format gate to CI | `src/`, `tests/`, `.github/workflows/ci.yml` | T.5 | S | done |
| T.7 | Fix settings type robustness: B.1, B.4 | `src/vd98/settings.py`, `src/vd98/formats.py`, `src/vd98/api.py` | T.5 | S | todo |
| T.8 | Fix manager races/gaps: B.2, B.3, B.5, B.6 | `src/vd98/manager.py` | T.5 | M | todo |
| T.9 | Grep guards for V.2, V.9; test V.8 path-escape branch | `tests/` | T.5 | S | todo |
| T.10 | Fix UI bugs: B.8, B.9, B.10 | `src/vd98/web/app.js` | T.5 | M | todo |
| T.11 | URL hardening: B.7 | `src/vd98/urls.py` | T.5 | S | todo |
| T.12 | install-desktop.sh: escape sed replacement, add uninstall, ffmpeg check | `scripts/install-desktop.sh` | T.5 | S | todo |
| T.13 | CI pinning: pin uv version; consider SHA-pinned actions (D.4) | `.github/workflows/ci.yml` | T.6 | S | todo |

## §B Bugs / backprop

Found 2026-10-06 by T.5 research; each reproduced or read in code before recording.

| # | Date | Symptom | Cause | Fix | Guard |
|---|------|---------|-------|-----|-------|
| B.1 | 2026-10-06 | settings file `{"preset": []}` → `settings.load` raises `TypeError: unhashable type: 'list'` | `data.get("preset") in PRESETS` on unhashable value, `src/vd98/settings.py` `_clean` | open → T.7 | V.6 |
| B.2 | 2026-10-06 | `wait_idle` may return True while job still queued | `add` clears `_idle` under lock but `queue.put` after release; worker can set idle in between, `src/vd98/manager.py` `add` / `_worker` | open → T.8 | V.3 (new test needed) |
| B.3 | 2026-10-06 | Cancel during processing (or before first hook) returns True, job may end `done` | cancel flag checked only in progress hook, `src/vd98/manager.py` `_on_hook` | open → T.8; UI already disables Cancel in processing | V.4 |
| B.4 | 2026-10-06 | `Api.cancel("x")` / `Api.remove(None)` raise instead of returning False; `preset_opts([])` raises `TypeError` not `ValueError`, uncaught by `Api.add` | `int(job_id)` unguarded `src/vd98/api.py` `cancel`/`remove`; dict lookup on unhashable `src/vd98/formats.py` `preset_opts` | open → T.7 | V.11 |
| B.5 | 2026-10-06 | queued→cancelled never fires `on_progress` | `cancel` sets status directly, skips `_update`, `src/vd98/manager.py` `cancel` | open → T.8 | V.10 |
| B.6 | 2026-10-06 | Cancel cleanup misses `<file>.ytdl`, `-Frag*`, finished `.fNNN` intermediates | candidates = tmpfilenames + `filename + ".part"` only, `src/vd98/manager.py` `_cleanup_partials` | open → T.8 | V.8 |
| B.7 | 2026-10-06 | `normalize_url("mailto:a@b")` → `https://mailto:a@b`; `\x00` accepted | scheme-less branch prepends `https://` to anything without `://`; only whitespace rejected, `src/vd98/urls.py` `normalize_url` | open → T.11 | V.1 |
| B.8 | 2026-10-06 | Enter with empty URL: warning dialog opens and closes instantly | URL keydown calls `addUrl` → `showDialog`; same Enter bubbles to document handler → `hideDialog`, `src/vd98/web/app.js` `wire` | open → T.10 | unguarded |
| B.9 | 2026-10-06 | Double-click finished row likely does not open folder; opens current `download_dir` not job folder | click handler re-renders rows before dblclick lands; handler ignores `job.dest_dir`, `src/vd98/web/app.js` `wire` | open → T.10 | unguarded |
| B.10 | 2026-10-06 | UI dead if `init`/`about` rejects at startup | `start` awaits without try; `wire()` never runs, `src/vd98/web/app.js` `start` | open → T.10 | unguarded |

## §D Deferred / design questions

- D.1: `Api.open_folder(path)` accepts any existing dir from JS; JS never passes `path`. Options: drop param · restrict to job `dest_dir`s. Open.
- D.2: Overlapping 500 ms polls (no in-flight guard, `src/vd98/web/app.js` `start`). Harmless today. Open.
- D.3: Concurrent errors → each dialog replaces previous; only last shown. Queue dialogs? Open.
- D.4: SHA-pin GitHub Actions vs tag-pin. Private repo, low risk. Open (T.13).
- D.5: V.1 checks submitted URL only; yt-dlp redirects + localhost/private IPs allowed. Local app, user-driven → accept? Open.
- D.6: Maximize state tracked in JS only (`src/vd98/web/app.js` `maximized`); desyncs if WM maximizes. Open.
- D.7: `cancel_all` runs twice on exit (`Api.close` + `window.events.closing`, `src/vd98/app.py`). Idempotent, harmless. Open.
- D.8: Vendored MS Sans Serif webfonts ship inside 98.css package (MIT); no separate font attribution in README. Add credit line? Open.
- D.9: README says settings in `~/.config/video-downloader-98/`; code honours `$XDG_CONFIG_HOME`. Reword README? Open.
- D.10: Each `DownloadManager` leaks a daemon worker (tests create many). No `shutdown()`. Open.
