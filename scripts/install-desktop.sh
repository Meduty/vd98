#!/usr/bin/env bash
# Install a launcher for Video Downloader 98 into the user's application menu.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
uv_bin="$(command -v uv)" || { echo "uv not found on PATH" >&2; exit 1; }

(cd "$repo" && "$uv_bin" sync --no-dev)

mkdir -p "$apps" "$icons"
cp "$repo/src/vd98/web/icon.svg" "$icons/vd98.svg"
sed -e "s|@EXEC@|\"$uv_bin\" run --no-dev --project \"$repo\" vd98|" \
    -e "s|@ICON@|vd98|" \
    "$repo/packaging/vd98.desktop" > "$apps/vd98.desktop"
update-desktop-database "$apps" 2>/dev/null || true

echo "Installed: $apps/vd98.desktop"
