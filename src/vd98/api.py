"""Bridge exposed to the web UI as `window.pywebview.api`.

pywebview walks public attributes of this object, so internals stay underscored.
Every method returns plain JSON-able data; errors come back as {"error": msg}.
"""

import shutil
import subprocess
from importlib.metadata import version
from pathlib import Path

import webview

from . import settings as settings_mod
from .formats import preset_list
from .manager import DownloadManager


class Api:
    def __init__(self, manager: DownloadManager | None = None, settings_path: Path | None = None):
        self._manager = manager or DownloadManager()
        self._settings_path = settings_path
        self._settings = settings_mod.load(settings_path)
        self._window = None

    def _attach(self, window) -> None:
        self._window = window

    # -- queue ------------------------------------------------------------
    def add(self, url, preset):
        try:
            job = self._manager.add(url, preset, self._settings["download_dir"])
        except ValueError as exc:
            return {"error": str(exc)}
        if preset != self._settings["preset"]:
            self.save_settings({"preset": preset})
        return job

    def cancel(self, job_id):
        return self._manager.cancel(int(job_id))

    def remove(self, job_id):
        return self._manager.remove(int(job_id))

    def clear_finished(self):
        self._manager.clear_finished()
        return True

    def get_state(self):
        return {"jobs": self._manager.jobs(), "settings": dict(self._settings)}

    def init(self):
        return {**self.get_state(), "presets": preset_list(), "ffmpeg": bool(shutil.which("ffmpeg"))}

    # -- settings ---------------------------------------------------------
    def save_settings(self, patch):
        if not isinstance(patch, dict):
            return {"error": "Invalid settings."}
        self._settings = settings_mod.save(patch, self._settings_path, base=self._settings)
        return dict(self._settings)

    def choose_folder(self):
        if not self._window:
            return None
        picked = self._window.create_file_dialog(
            webview.FileDialog.FOLDER, directory=self._settings["download_dir"]
        )
        if not picked:
            return None
        return self.save_settings({"download_dir": picked[0]})

    def open_folder(self, path=None):
        target = Path(path or self._settings["download_dir"])
        if target.is_file():
            target = target.parent
        if not target.is_dir() or not shutil.which("xdg-open"):
            return False
        subprocess.Popen(["xdg-open", str(target)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True

    # -- window chrome (custom 98.css title bar) --------------------------
    def minimize(self):
        if self._window:
            self._window.minimize()

    def maximize(self, on):
        if self._window:
            self._window.maximize() if on else self._window.restore()

    def close(self):
        self._manager.cancel_all()
        if self._window:
            self._window.destroy()

    def about(self):
        return {"app": version("vd98"), "yt_dlp": version("yt-dlp")}
