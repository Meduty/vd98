# SPEC — Video Downloader 98

## §G Goals
- G1 Local Linux desktop app: paste URL → video file on disk.
- G2 Win98 look (98.css in pywebview window).
- G3 Queue, format presets, retro sounds. Single video per URL (no playlists).

## §C Constraints
- C1 Engine = yt-dlp Python lib. ffmpeg on PATH for merge/audio extract.
- C2 No DRM bypass. DRM/unsupported → clear error in UI.
- C3 Offline UI: all CSS/JS vendored, no CDN at runtime.

## §I Interfaces (js_api, `vd98.api.Api`)
add(url, preset) → job | {error}; cancel(id); remove(id); clear_finished();
get_state() → {jobs, settings}; choose_folder(); open_folder(); save_settings(patch); about().

## §V Invariants
- V1 Only http/https URLs accepted. Anything else rejected before yt-dlp.
- V2 No shell. subprocess only with arg list, only `xdg-open <existing dir>`.
- V3 One worker thread; downloads sequential.
- V4 Job state ∈ {queued, downloading, processing, done, error, cancelled}; terminal states never change.
- V5 Tests offline: manager tested with fake YoutubeDL factory.
- V6 Corrupt/missing settings file → defaults, never crash.
- V7 Unknown preset rejected.

## §T Tasks
| id | task | status |
|----|------|--------|
| T1 | urls, formats, settings + tests | done |
| T2 | manager + tests | done |
| T3 | api + window + web UI | done |
| T4 | CI, README, desktop entry, GH repo | done |

## §B Bugs
| id | bug | invariant |
|----|-----|-----------|
