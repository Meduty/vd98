---
paths:
  - "src/vd98/manager.py"
  - "src/vd98/urls.py"
  - "src/vd98/formats.py"
  - "src/vd98/settings.py"
---
# Core rules

> Before editing: read ARCHITECTURE "Core: download queue" + SPEC V.1, V.3, V.4, V.6, V.7, V.8, V.10 and open §B rows B.1–B.7.
> After editing: `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`; download path touched → real smoke (`docs/live/e2e_testing.md`).

- No GUI imports (`webview`, Qt) in core modules.
- Job state changes only via `DownloadManager._update`, under `self._lock`; never call `on_progress` while holding the lock.
- Terminal statuses (`done`, `error`, `cancelled`) never change (V.4).
- Validation raises `ValueError` (or subclass); the bridge turns it into `{error}`.
- New yt-dlp option → set it in `_run` `opts.update(...)`, assert it in `tests/test_manager.py::test_opts_passed_to_ydl`.
- File deletion only for `.part`/`.ytdl` inside the job `dest_dir` (V.8).
- Tests use a fake `ydl_factory`; never the network (V.5).
