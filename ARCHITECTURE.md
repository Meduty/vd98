# ARCHITECTURE — Video Downloader 98

> **Status: LIVING** — must match `src/vd98/`. **Scope:** code map, patterns, walkthrough. **Reconciled:** 2026-10-06.
> Line numbers rot; symbol names win. Contract and invariants live in [SPEC.md](SPEC.md).

Three layers in one process:

```
web UI (HTML/CSS/JS, 98.css)  --pywebview js_api-->  Api (bridge)  -->  DownloadManager (worker thread)  -->  yt-dlp + ffmpeg
         ^  polls get_state() every 500 ms                 |
         +-------------------------------------------------+
```

## Systems

### 1. Core: download queue

Owns jobs, one worker thread, yt-dlp calls, cancel, partial cleanup. No GUI imports.

| Concern | File / symbol |
|---|---|
| Job record + public dict | `src/vd98/manager.py:23` `Job`, `Job.public` |
| Queue, worker, state machine | `src/vd98/manager.py:66` `DownloadManager`, `_worker` :131, `_run` :145 |
| Progress → percent/speed/eta | `src/vd98/manager.py:183` `_on_hook`; post-processing `_on_pp_hook` :210 |
| Thread-safe state writes, terminal guard | `src/vd98/manager.py:214` `_update` |
| Cancel + `.part` cleanup | `cancel` :91, `_cleanup_partials` :227 |
| yt-dlp error → short message | `src/vd98/manager.py:60` `clean_error` |
| URL validation | `src/vd98/urls.py:12` `normalize_url` |
| Format presets → yt-dlp opts | `src/vd98/formats.py` `PRESETS`, `preset_opts`, `preset_list` |
| Settings JSON | `src/vd98/settings.py` `load`, `save`, `config_path` |
| Unfinished-jobs queue across restarts | `src/vd98/queue_store.py` `QueueStore`, `state_path`; manager `suspend`, `restore`, `resume`, `_persist` |
| Smoothed ETA | `src/vd98/eta.py` `HalfWindowEta`; fed from `_on_hook` with the injected clock |

### 2. Bridge: `Api`

Plain-data methods JS can call. Holds manager, settings, window ref (underscored so pywebview does not expose them).

| Concern | File / symbol |
|---|---|
| Queue ops for JS | `src/vd98/api.py:35` `add`, `cancel` :44, `remove` :47, `clear_finished` :50 |
| State snapshot for polling | `get_state` :54, `init` :57 |
| Settings + folder picker | `save_settings` :65, `choose_folder` :73 |
| Open folder in file manager (only subprocess call) | `open_folder` :83 |
| Custom title-bar buttons | `minimize` :117, `maximize` :121, `close` :125 |
| Version info | `about` :130 |

### 3. Shell: window

| Concern | File / symbol |
|---|---|
| Console script `vd98` | `pyproject.toml` `[project.scripts]` → `src/vd98/__init__.py` `main` |
| Window creation (frameless, Qt) | `src/vd98/app.py:12` `run` |
| Move / resize via window manager (Wayland-safe), GUI-thread dispatch | `src/vd98/chrome.py` `WindowChrome`, `edges_for`; bridge `Api.start_move` / `start_resize` |

### 4. UI: `src/vd98/web/`

| Concern | File / symbol |
|---|---|
| Markup: title bar, menus, form, queue table, status bar, modal | `index.html` |
| Startup, wiring, polling | `app.js` `start` :317, `wire` :236, `setInterval(refresh, 500)` :339 |
| Render queue rows | `app.js` `render` :78, `cell`, `progressCell` |
| Status-change side effects (sounds, dialogs) | `app.js` `announce` :109 |
| Menus | `app.js` `wireMenus`; styles `app.css` `.menubar` |
| Sounds (synthesized, no assets) | `sounds.js` `Sounds` |
| Win98 widgets | `vendor/98.css` (vendored, frozen — SPEC C.11) |

## Patterns

- **Injectable engine.** `DownloadManager(ydl_factory=…)`; tests pass a fake context-manager class. Example: `tests/test_manager.py` `FakeYDL`, `make_manager`.
- **Validate at the edge, raise `ValueError`.** Core raises (`normalize_url`, `preset_opts`, `DownloadManager.add`); `Api` converts to `{"error": msg}`. Example: `src/vd98/api.py` `Api.add`.
- **Snapshot under lock, callback outside.** `_update` copies `job.public()` under `self._lock`, then calls `on_progress`. Example: `src/vd98/manager.py` `_update`.
- **Poll, don't push.** UI never receives Python→JS calls; it polls `get_state` and diffs statuses in `announce`. Example: `src/vd98/web/app.js` `refresh`.
- **Remote text only via `textContent`.** Example: `app.js` `cell`, `showDialog` (SPEC V.9).
- **Settings clean per key.** Invalid value → fallback to current/default per key. Example: `src/vd98/settings.py` `_clean`.
- **Known bugs pinned as strict xfail.** Example: `tests/test_known_bugs.py`.

## Where do I find X?

| I want to… | Go to |
|---|---|
| Add a format preset | `src/vd98/formats.py` `PRESETS` (+ test in `tests/test_formats.py`) |
| Change download options (template, playlist, logging) | `src/vd98/manager.py` `_run` `opts.update(...)` |
| Change progress math | `src/vd98/manager.py` `_on_hook` |
| Expose a new action to the UI | `src/vd98/api.py` new method → call from `src/vd98/web/app.js`; add to SPEC §I |
| Add a setting | `src/vd98/settings.py` `defaults` + `_clean`; UI in `app.js` `start`/`wire` |
| Add a menu item | `src/vd98/web/index.html` `.menu-list` `<li data-action>` + `app.js` `ACTIONS` |
| Change a sound | `src/vd98/web/sounds.js` |
| Change window size/flags | `src/vd98/app.py` `run` |
| Change how drag/resize works | `src/vd98/chrome.py`; handles `.rs` in `src/vd98/web/index.html` + `app.css`; wiring in `app.js` `wire` |
| Change CI gates | `.github/workflows/ci.yml` |
| Install launcher | `scripts/install-desktop.sh`, `packaging/vd98.desktop` |

## End-to-end: user pastes URL, presses Download

1. Enter/click → `addUrl` (`src/vd98/web/app.js:142`) trims input, calls `api.add(url, preset)` (:150).
2. pywebview runs `Api.add` (`src/vd98/api.py:32`) on a bridge thread.
3. `DownloadManager.add` (`src/vd98/manager.py:79`): `normalize_url` (`src/vd98/urls.py:12`), `preset_opts` check, dir check, create `Job` under lock, `queue.put`.
4. `Api.add` saves preset if changed (`save_settings` :65) and returns job dict → JS sets `selectedId`, plays start sound.
5. Worker `_worker` (`manager.py:131`) takes id, sets `downloading`, calls `_run` (:145).
6. `_run` builds opts (preset + `paths`, `outtmpl`, `noplaylist=True` :150, hooks :155), calls `ydl.extract_info(url, download=True)` (:160).
7. yt-dlp calls `_on_hook` (:183) per chunk → `_update` (:214) sets percent/speed/eta; ffmpeg step fires `_on_pp_hook` (:210) → `processing`.
8. `_run` sets `done` + `filename` from `requested_downloads`; exceptions map to `cancelled` (with `_cleanup_partials` :227) or `error` (`clean_error` :60).
9. Meanwhile JS `refresh` (`app.js:130`) polls `get_state` every 500 ms (:339) → `announce` (:109) plays done/error sound, opens error dialog → `render` (:78) rebuilds rows.

## Known violations

- Known violation: `Api` promises never to raise (docstring `src/vd98/api.py:4`) but `cancel`/`remove` do `int(job_id)` unguarded. Planned fix: SPEC T.7 (B.4).
- Known violation: UI logic in one 300-line `app.js` closure (render, state diff, menus, wiring). Acceptable at this size; split if it grows past ~400 lines.
- Known violation: state-change detection (`announce`) lives in the UI, not the core; a second UI would duplicate it. No fix planned (single UI).
