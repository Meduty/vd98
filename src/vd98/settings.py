"""Persistent user settings stored as JSON in the XDG config dir."""

import json
import os
from pathlib import Path

from .formats import DEFAULT_PRESET, PRESETS

APP_DIR = "video-downloader-98"


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_DIR / "settings.json"


def default_download_dir() -> str:
    downloads = Path.home() / "Downloads"
    return str(downloads if downloads.is_dir() else Path.home())


def defaults() -> dict:
    return {
        "download_dir": default_download_dir(),
        "preset": DEFAULT_PRESET,
        "sound": True,
    }


def _clean(data: dict, base: dict | None = None) -> dict:
    """Keep valid values from data; fall back to base (or defaults) per key."""
    out = dict(base) if base else defaults()
    if (
        isinstance(data.get("download_dir"), str)
        and Path(data["download_dir"]).is_dir()
    ):
        out["download_dir"] = data["download_dir"]
    if data.get("preset") in PRESETS:
        out["preset"] = data["preset"]
    if isinstance(data.get("sound"), bool):
        out["sound"] = data["sound"]
    return out


def load(path: Path | None = None) -> dict:
    path = path or config_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults()
    return _clean(data) if isinstance(data, dict) else defaults()


def save(settings: dict, path: Path | None = None, base: dict | None = None) -> dict:
    path = path or config_path()
    clean = _clean(settings, base)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(clean, indent=2), encoding="utf-8")
    tmp.replace(path)
    return clean
