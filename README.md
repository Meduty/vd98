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

## How to install

Linux only. Developed and tested on Nobara (Fedora-based) in a Wayland session; X11 should work
the same but hasn't been tried.

**1. Install the prerequisites:** `git`, `ffmpeg` and [uv](https://docs.astral.sh/uv/).
uv fetches the right Python (3.12) by itself.

```bash
sudo dnf install git ffmpeg          # Fedora / Nobara
sudo apt install git ffmpeg          # Debian / Ubuntu
curl -LsSf https://astral.sh/uv/install.sh | sh   # uv (or: pipx install uv)
```

`ffmpeg` is needed to merge best-quality video with its audio and to convert to MP3/M4A.
Without it the app still starts, but warns you and those formats fail.

**2. Get the code** (the repository is private, so you need access to it):

```bash
gh repo clone Meduty/video-downloader      # or: git clone https://github.com/Meduty/video-downloader.git
cd video-downloader
```

Keep the folder where it is after step 4: the menu launcher points at it.

**3. Install the dependencies and start it once:**

```bash
uv sync --no-dev
uv run vd98
```

The first `uv sync` downloads Python 3.12, yt-dlp and Qt WebEngine (about 600 MB on disk, once).

**4. Optional: add it to your application menu:**

```bash
./scripts/install-desktop.sh
```

This creates `~/.local/share/applications/vd98.desktop` and an icon in
`~/.local/share/icons/hicolor/scalable/apps/vd98.svg`. "Video Downloader 98" then shows up in
your app launcher.

### Update

```bash
cd video-downloader
git pull
uv sync --no-dev
```

### Uninstall

```bash
rm ~/.local/share/applications/vd98.desktop ~/.local/share/icons/hicolor/scalable/apps/vd98.svg
rm -r ~/.config/video-downloader-98      # saved settings (download folder, format, sound)
rm -r video-downloader                   # the code itself
```

Downloaded videos stay in your download folder.

## Run

```bash
uv run vd98          # from the repo folder, or use the menu entry from step 4
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
git config core.hooksPath .githooks   # once per clone: refuse commits that add secrets
uv run pytest
uv run ruff check .
```

Working with an AI agent (Claude Code) in this repo uses its OS sandbox (see `CLAUDE.md`).
On Linux that needs `bubblewrap` and `socat` (`sudo dnf install bubblewrap socat`). The settings
refuse to start without them rather than running unsandboxed.

Layout:

| Path | What |
| --- | --- |
| `src/vd98/manager.py` | Download queue, worker thread, yt-dlp progress hooks, cancel |
| `src/vd98/formats.py` | Format presets → yt-dlp options |
| `src/vd98/urls.py` | URL validation (http/https only) |
| `src/vd98/settings.py` | JSON settings in `~/.config/video-downloader-98/` |
| `src/vd98/api.py` | Bridge exposed to the web UI |
| `src/vd98/app.py` | pywebview window (Qt backend) |
| `src/vd98/chrome.py` | Window drag/resize through the window manager (works on Wayland) |
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
