"""Unfinished downloads persisted across app restarts (SPEC V.20).

Lives in the XDG *state* directory (not config): it is data the app produces, safe to
delete, and changes on every status change. Loading never raises: a missing, corrupt or
partly invalid file yields the valid entries only, like settings.load (V.6).
"""

import json
import os
from pathlib import Path

from .formats import PRESETS
from .urls import InvalidURL, normalize_url

APP_DIR = "video-downloader-98"

DEFAULTS = {
    "title": "",
    "filename": "",
    "tmpfiles": [],
    "percent": 0.0,
    "total_bytes": None,
    "size_estimated": False,
}


def state_path() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / APP_DIR / "queue.json"


def _clean(raw) -> dict | None:
    """A validated entry, or None if it can't be resumed safely."""
    if not isinstance(raw, dict):
        return None
    try:
        url = normalize_url(raw.get("url"))
    except InvalidURL:
        return None
    preset = raw.get("preset")
    if not isinstance(preset, str) or preset not in PRESETS:
        return None
    dest = raw.get("dest_dir")
    if not isinstance(dest, str) or not Path(dest).is_dir():
        return None
    out = {"url": url, "preset": preset, "dest_dir": dest, **DEFAULTS}
    if isinstance(raw.get("title"), str):
        out["title"] = raw["title"]
    if isinstance(raw.get("filename"), str):
        out["filename"] = raw["filename"]
    tmpfiles = raw.get("tmpfiles", [])
    if not (isinstance(tmpfiles, list) and all(isinstance(t, str) for t in tmpfiles)):
        return None
    out["tmpfiles"] = list(tmpfiles)
    if isinstance(raw.get("percent"), (int, float)) and not isinstance(
        raw.get("percent"), bool
    ):
        out["percent"] = float(min(max(raw["percent"], 0.0), 100.0))
    if isinstance(raw.get("total_bytes"), int) and not isinstance(
        raw.get("total_bytes"), bool
    ):
        out["total_bytes"] = raw["total_bytes"]
    if isinstance(raw.get("size_estimated"), bool):
        out["size_estimated"] = raw["size_estimated"]
    return out


class QueueStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else state_path()

    def load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(data, list):
            return []
        return [e for e in (_clean(raw) for raw in data) if e is not None]

    def save(self, entries: list[dict]) -> bool:
        """Write atomically; False (never an exception) if the disk says no."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            return False
        return True
