"""Bridge exposed to the web UI as `window.pywebview.api`.

pywebview walks public attributes of this object, so internals stay underscored.
Every method returns plain JSON-able data; errors come back as {"error": msg}.
"""

import shutil
import subprocess
import threading
from importlib.metadata import version
from pathlib import Path

import webview

from . import settings as settings_mod
from .formats import preset_list
from .manager import DownloadManager
from .queue_store import QueueStore


class Api:
    def __init__(
        self, manager: DownloadManager | None = None, settings_path: Path | None = None
    ):
        self._manager = manager or DownloadManager(store=QueueStore())
        self._settings_path = settings_path
        self._settings = settings_mod.load(settings_path)
        self._window = None
        self._chrome = None
        self._chrome_lock = threading.Lock()
        # downloads interrupted last time come back as paused (V.20); none run on their own
        self._restored = self._manager.restore()

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

    @staticmethod
    def _job_id(value) -> int | None:
        """A job id from JS, or None. Only real ints and digit strings: 1.9 must not
        become job 1, and True must not become job 1 either (V.11, B.4)."""
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def cancel(self, job_id):
        jid = self._job_id(job_id)
        return False if jid is None else self._manager.cancel(jid)

    def remove(self, job_id):
        jid = self._job_id(job_id)
        return False if jid is None else self._manager.remove(jid)

    def resume(self, job_id):
        jid = self._job_id(job_id)
        return False if jid is None else self._manager.resume(jid)

    def resume_all(self):
        return self._manager.resume_all()

    def clear_finished(self):
        self._manager.clear_finished()
        return True

    def get_state(self):
        return {"jobs": self._manager.jobs(), "settings": dict(self._settings)}

    def init(self):
        return {
            **self.get_state(),
            "presets": preset_list(),
            "ffmpeg": bool(shutil.which("ffmpeg")),
            "restored": self._restored,
        }

    # -- settings ---------------------------------------------------------
    def save_settings(self, patch):
        if not isinstance(patch, dict):
            return {"error": "Invalid settings."}
        self._settings = settings_mod.save(
            patch, self._settings_path, base=self._settings
        )
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
        subprocess.Popen(
            ["xdg-open", str(target)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True

    # -- window chrome (custom 98.css title bar) --------------------------
    def _window_chrome(self):
        """Lazily create the GUI-thread move/resize bridge once the Qt window exists."""
        native = getattr(self._window, "native", None)
        if native is None:
            return None
        with self._chrome_lock:
            if self._chrome is None:
                from .chrome import WindowChrome  # Qt import only when a window exists

                self._chrome = WindowChrome(native)
        return self._chrome

    def start_move(self):
        chrome = self._window_chrome()
        return bool(chrome and chrome.request_move())

    def start_resize(self, edge):
        chrome = self._window_chrome()
        return bool(chrome and chrome.request_resize(edge))

    def minimize(self):
        if self._window:
            self._window.minimize()

    def maximize(self, on):
        if self._window:
            self._window.maximize() if on else self._window.restore()

    def _on_window_closing(self):
        """pywebview `closing` handler for a WM close (not our title-bar button).

        Suspends like close() (V.21) but always returns None: returning False cancels
        the close, and suspend() returns False when a job is still converting (PR #3
        review). The user asked to close; the worker is a daemon and stops with us.
        Deliberately has no return statement.
        """
        self._manager.suspend(timeout=3)

    def close(self):
        # suspend, don't cancel: partial files stay and jobs resume next start (V.21)
        self._manager.suspend(timeout=3)
        if self._window:
            self._window.destroy()

    def about(self):
        return {"app": version("vd98"), "yt_dlp": version("yt-dlp")}
