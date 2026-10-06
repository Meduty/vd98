"""PR #3 review round 1: close path, queue-save ordering, job-id parsing (V.11, V.20, V.21)."""

import threading

import pytest

from vd98.api import Api
from vd98.manager import DownloadManager
from vd98.queue_store import QueueStore


class ParkedYDL:
    """Never finishes: keeps the worker busy so later jobs stay queued."""

    gate = threading.Event()

    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        for h in self.params["progress_hooks"]:
            h({"status": "downloading", "downloaded_bytes": 1, "total_bytes": 10})
        type(self).gate.wait(30)
        return {"title": "t"}


def test_older_snapshot_never_overwrites_newer_one(tmp_path):
    """Finding 2: snapshot taken outside the save lock let a stale save land last."""
    store = QueueStore(tmp_path / "q.json")
    m = DownloadManager(ydl_factory=ParkedYDL, store=store)
    a = m.add("https://example.com/a", "best", str(tmp_path))
    deadline = threading.Event()
    for _ in range(200):  # wait until job a is running (its status save is done)
        if m.get(a["id"])["status"] == "downloading":
            break
        deadline.wait(0.01)

    original = m._unfinished
    snapped, release = threading.Event(), threading.Event()
    calls = []

    def slow_first_snapshot():
        snap = original()
        calls.append(len(snap))
        if len(calls) == 1:  # pause the first save between snapshot and write
            snapped.set()
            release.wait(0.5)
        return snap

    m._unfinished = slow_first_snapshot
    older = threading.Thread(target=m._persist)
    older.start()
    assert snapped.wait(5)
    m.add("https://example.com/b", "best", str(tmp_path))  # newer save
    release.set()
    older.join(5)
    assert {e["url"] for e in store.load()} == {
        "https://example.com/a",
        "https://example.com/b",
    }


class NullYDL:
    def __init__(self, params):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        return {"title": "t"}


def make_api(tmp_path, manager=None):
    api = Api(
        manager or DownloadManager(ydl_factory=NullYDL),
        settings_path=tmp_path / "s.json",
    )
    api.save_settings({"download_dir": str(tmp_path)})
    return api


def test_window_closing_never_cancels_the_close(tmp_path):
    """Finding 1: returning suspend()'s False from the closing event cancels the close."""

    class SlowToStop(DownloadManager):
        def suspend(self, timeout=5.0):
            return False  # e.g. ffmpeg still converting

    api = make_api(tmp_path, SlowToStop(ydl_factory=NullYDL))
    assert api._on_window_closing() is None


@pytest.mark.parametrize("bad", ["x", None, 1.9, True, [], "1.5", ""])
def test_bad_job_ids_are_falsy_not_errors(tmp_path, bad):
    """Finding 7 / B.4: V.11 says bad input from JS is falsy, never an exception."""
    api = make_api(tmp_path)
    # job 1 exists: 1.9 or True must not be truncated into hitting it
    api.add("https://example.com/v", "best")
    api._manager.wait_idle(5)
    assert api.cancel(bad) is False
    assert api.remove(bad) is False
    assert api.resume(bad) is False


def test_numeric_string_ids_still_work(tmp_path):
    api = make_api(tmp_path)
    job = api.add("https://example.com/v", "best")
    api._manager.wait_idle(5)
    assert api.remove(str(job["id"])) is True
