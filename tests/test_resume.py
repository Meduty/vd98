"""Suspend on close, restore as paused, resume later (SPEC T.17, V.4, V.20, V.21)."""

import threading

from vd98.manager import TERMINAL, DownloadManager
from vd98.queue_store import QueueStore


class BlockingYDL:
    """Writes a .part, reports progress, then waits until released or cancelled."""

    started = None  # threading.Event set per test
    release = None
    seen_urls: list

    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def hook(self, **d):
        for h in self.params["progress_hooks"]:
            h(d)

    def extract_info(self, url, download=True):
        cls = type(self)
        cls.seen_urls.append(url)
        home = self.params["paths"]["home"]
        part = f"{home}/clip-{len(cls.seen_urls)}.mp4.part"
        with open(part, "ab") as fh:
            fh.write(b"x" * 100)
        common = {
            "tmpfilename": part,
            "filename": part[: -len(".part")],
            "total_bytes": 1000,
        }
        self.hook(
            status="downloading",
            downloaded_bytes=100,
            info_dict={"title": "Clip"},
            **common,
        )
        cls.started.set()
        while not cls.release.wait(0.01):
            self.hook(
                status="downloading", downloaded_bytes=100, **common
            )  # raises on cancel
        self.hook(status="finished", filename=common["filename"])
        return {
            "title": "Clip",
            "requested_downloads": [{"filepath": common["filename"]}],
        }


def ydl_class():
    return type(
        "YDL",
        (BlockingYDL,),
        {"started": threading.Event(), "release": threading.Event(), "seen_urls": []},
    )


def make(tmp_path, ydl):
    store = QueueStore(tmp_path / "state" / "queue.json")
    return DownloadManager(ydl_factory=ydl, store=store), store


def test_suspend_keeps_partial_and_pauses(tmp_path):
    ydl = ydl_class()
    m, store = make(tmp_path, ydl)
    running = m.add("https://example.com/a", "best", str(tmp_path))
    queued = m.add("https://example.com/b", "mp3", str(tmp_path))
    assert ydl.started.wait(5)
    assert m.suspend(timeout=5) is True
    assert m.get(running["id"])["status"] == "paused"
    assert m.get(queued["id"])["status"] == "paused"
    assert (tmp_path / "clip-1.mp4.part").exists()  # V.21: close never deletes partials
    saved = {e["url"]: e for e in store.load()}
    assert set(saved) == {"https://example.com/a", "https://example.com/b"}
    assert saved["https://example.com/a"]["tmpfiles"] == [
        str(tmp_path / "clip-1.mp4.part")
    ]
    assert saved["https://example.com/a"]["percent"] == 10.0


def test_restore_then_resume_finishes_and_clears_store(tmp_path):
    first = ydl_class()
    m1, store = make(tmp_path, first)
    m1.add("https://example.com/a", "best", str(tmp_path))
    assert first.started.wait(5)
    m1.suspend(timeout=5)

    second = ydl_class()
    m2 = DownloadManager(ydl_factory=second, store=store)
    restored = m2.restore()
    assert restored == 1
    (job,) = m2.jobs()
    assert job["status"] == "paused" and job["url"] == "https://example.com/a"
    assert job["title"] == "Clip" and job["percent"] == 10.0
    assert second.seen_urls == []  # nothing runs until the user resumes

    assert m2.resume(job["id"]) is True
    assert second.started.wait(5)
    second.release.set()
    assert m2.wait_idle(5)
    assert m2.get(job["id"])["status"] == "done"
    assert store.load() == []  # finished jobs are not kept


def test_resume_all_and_cancel_paused_removes_partials(tmp_path):
    first = ydl_class()
    m1, store = make(tmp_path, first)
    m1.add("https://example.com/a", "best", str(tmp_path))
    m1.add("https://example.com/b", "best", str(tmp_path))
    assert first.started.wait(5)
    m1.suspend(timeout=5)

    m2 = DownloadManager(ydl_factory=ydl_class(), store=store)
    assert m2.restore() == 2
    a, b = sorted(m2.jobs(), key=lambda j: j["url"])
    assert m2.cancel(a["id"]) is True  # paused -> cancelled, partial cleaned up
    assert m2.get(a["id"])["status"] == "cancelled"
    assert m2.get(b["id"])["status"] == "paused"  # only the cancelled one is touched
    assert not (tmp_path / "clip-1.mp4.part").exists()
    assert [e["url"] for e in store.load()] == ["https://example.com/b"]
    assert m2.resume_all() == 1


def test_paused_is_not_terminal():
    assert "paused" not in TERMINAL


def test_manager_without_store_still_works(tmp_path):
    ydl = ydl_class()
    m = DownloadManager(ydl_factory=ydl)
    m.add("https://example.com/a", "best", str(tmp_path))
    assert ydl.started.wait(5)
    assert m.suspend(timeout=5) is True
    assert m.restore() == 0
