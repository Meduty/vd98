"""PR #3 review round 2 (V.20, V.22): bad saved URL, stale ETA, file modes, kill safety."""

import json
import stat
import threading
from typing import ClassVar

from vd98.manager import DownloadManager
from vd98.queue_store import QueueStore


def entry(tmp_path, url):
    return {"url": url, "preset": "best", "dest_dir": str(tmp_path)}


def test_unparseable_saved_url_skips_entry_not_startup(tmp_path):
    """Finding 1: urlsplit raises plain ValueError for 'http://[' and load() aborted."""
    p = tmp_path / "q.json"
    good = entry(tmp_path, "https://example.com/ok")
    p.write_text(json.dumps([entry(tmp_path, "http://["), good]))
    loaded = QueueStore(p).load()
    assert [e["url"] for e in loaded] == ["https://example.com/ok"]


def test_queue_file_is_private(tmp_path):
    """Finding 3: saved URLs may carry tokens; the file must not be world-readable."""
    store = QueueStore(tmp_path / "state" / "q.json")
    assert store.save([entry(tmp_path, "https://example.com/v?token=abc")])
    file_mode = stat.S_IMODE(store.path.stat().st_mode)
    dir_mode = stat.S_IMODE(store.path.parent.stat().st_mode)
    assert file_mode & 0o077 == 0, oct(file_mode)
    assert dir_mode & 0o077 == 0, oct(dir_mode)


class ScriptedYDL:
    hooks: ClassVar[list] = []  # replaced per test
    park = None

    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        for d in type(self).hooks:
            for h in self.params["progress_hooks"]:
                h(dict(d))
        if type(self).park is not None:
            type(self).park.wait(10)
        return {"title": "t"}


class TickClock:
    def __init__(self):
        self.t = -1.0

    def __call__(self):
        self.t += 1.0
        return self.t


def test_stall_does_not_fall_back_to_yt_dlp_eta(tmp_path):
    """Finding 2: smoothed ETA None during a stall made the manager show yt-dlp's stale ETA."""
    hooks = [
        {
            "status": "downloading",
            "downloaded_bytes": b,
            "total_bytes": 1000,
            "eta": 999,
        }
        for b in (100, 200)
    ]
    hooks += [
        {
            "status": "downloading",
            "downloaded_bytes": 200,
            "total_bytes": 1000,
            "eta": 999,
        }
    ] * 8
    ydl = type("YDL", (ScriptedYDL,), {"hooks": hooks, "park": None})
    m = DownloadManager(ydl_factory=ydl, clock=TickClock())
    snaps = []
    m.on_progress = snaps.append
    m.add("https://example.com/v", "best", str(tmp_path))
    assert m.wait_idle(5)
    last_downloading = [s for s in snaps if s["status"] == "downloading"][-1]
    assert last_downloading["eta"] is None


def test_new_partial_path_saved_before_any_status_change(tmp_path):
    """Finding 4: after a kill, the saved entry must already know the .part path."""
    part = str(tmp_path / "clip.mp4.part")
    hooks = [
        {
            "status": "downloading",
            "downloaded_bytes": 1,
            "total_bytes": 10,
            "tmpfilename": part,
            "filename": str(tmp_path / "clip.mp4"),
        }
    ]
    park = threading.Event()
    ydl = type("YDL", (ScriptedYDL,), {"hooks": hooks, "park": park})
    store = QueueStore(tmp_path / "q.json")
    m = DownloadManager(ydl_factory=ydl, store=store)
    m.add("https://example.com/v", "best", str(tmp_path))
    try:
        for _ in range(200):  # the hook runs on the worker; poll the saved file
            saved = store.load()
            if saved and saved[0]["tmpfiles"]:
                break
            threading.Event().wait(0.01)
        assert saved and saved[0]["tmpfiles"] == [part]
    finally:
        park.set()
