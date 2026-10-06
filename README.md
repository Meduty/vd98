# Video Downloader 98

A local desktop app that downloads videos from the web, dressed up like it's 1998.

Paste a link, pick a format, press **Download**. Under the hood it uses
[yt-dlp](https://github.com/yt-dlp/yt-dlp), so it works with YouTube, Vimeo,
Twitch VODs, Reddit, X, news sites, direct `.mp4` / HLS links and
[well over a thousand other sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

## Features

- Classic Windows 98 look (via [98.css](https://github.com/jdan/98.css)), custom title bar, menus, dialogs
- Download queue (one at a time) with progress, speed and ETA
- Cancel running or queued downloads; partial files are cleaned up
- Format presets: Best, 1080p, 720p, 480p (MP4), audio-only MP3 / M4A
- Original synthesized retro sound cues (toggle with *Sounds*)
- Remembers download folder, format and sound setting

Single videos only: playlist URLs download just the linked video.
DRM-protected services (Netflix, Disney+, Spotify, ...) are not supported.

## Requirements

- Linux with Python 3.12 (managed automatically by [uv](https://docs.astral.sh/uv/))
- `ffmpeg` on your `PATH` (merging best video+audio, MP3/M4A conversion)

```bash
sudo dnf install ffmpeg      # Fedora / Nobara
sudo apt install ffmpeg      # Debian / Ubuntu
```

## Run

```bash
uv run vd98
```

Add it to your application menu:

```bash
./scripts/install-desktop.sh
```

## Keyboard

| Key | Action |
| --- | --- |
| Enter (in URL box) | Download |
| Ctrl+Shift+V | Paste URL from clipboard |
| Delete | Remove selected finished item |
| Esc | Close menu / dialog |

Double-click a finished download to open its folder.

## Keeping yt-dlp fresh

Sites change often. When downloads start failing, update the engine:

```bash
uv lock --upgrade-package yt-dlp && uv sync
```

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
```

Layout:

| Path | What |
| --- | --- |
| `src/vd98/manager.py` | Download queue, worker thread, yt-dlp progress hooks, cancel |
| `src/vd98/formats.py` | Format presets → yt-dlp options |
| `src/vd98/urls.py` | URL validation (http/https only) |
| `src/vd98/settings.py` | JSON settings in `~/.config/video-downloader-98/` |
| `src/vd98/api.py` | Bridge exposed to the web UI |
| `src/vd98/app.py` | pywebview window (Qt backend) |
| `src/vd98/web/` | HTML/CSS/JS UI, vendored 98.css |
| `SPEC.md` | Goals, invariants, task log |

## Legal

Only download content you own or have permission to save. Respect each site's
terms of service and copyright law in your country.

## Credits

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Unlicense)
- [98.css](https://github.com/jdan/98.css) by Jordan Scales (MIT, see `src/vd98/web/vendor/98.css.LICENSE`)
- [pywebview](https://pywebview.flowrl.com/) (BSD-3-Clause)

Licensed under the MIT License.
