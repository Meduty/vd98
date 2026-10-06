import threading

import pytest
from yt_dlp.utils import DownloadError

from vd98.manager import TERMINAL, DownloadManager


class FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL driven by a per-test script."""

    script = None  # callable(fake, url) -> info dict

    def __init__(self, params):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def hook(self, **d):
        for h in self.params.get("progress_hooks", []):
            h(d)

    def extract_info(self, url, download=True):
        return type(self).script(self, url)


def make_manager(script, tmp_path):
    ydl = type("YDL", (FakeYDL,), {"script": staticmethod(script)})
    return DownloadManager(ydl_factory=ydl)


def ok_script(fake, url):
    info = {"title": "Clip", "id": "abc"}
    fake.hook(
        status="downloading",
        downloaded_bytes=50,
        total_bytes=100,
        speed=1024.0,
        eta=3,
        info_dict=info,
        tmpfilename="x.part",
        filename="x.mp4",
    )
    fake.hook(status="finished", info_dict=info, filename="x.mp4")
    return {**info, "requested_downloads": [{"filepath": "/tmp/x.mp4"}]}


def test_successful_download(tmp_path):
    seen = []
    m = make_manager(ok_script, tmp_path)
    m.on_progress = lambda job: seen.append(job["percent"])
    job = m.add("https://example.com/v", "best", str(tmp_path))
    assert m.wait_idle(5)
    final = m.get(job["id"])
    assert final["status"] == "done"
    assert final["title"] == "Clip"
    assert final["filename"] == "/tmp/x.mp4"
    assert final["percent"] == 100
    assert 50 in seen


def test_opts_passed_to_ydl(tmp_path):
    captured = {}

    def script(fake, url):
        captured.update(fake.params, url=url)
        return {"title": "t"}

    m = make_manager(script, tmp_path)
    m.add("https://example.com/v", "mp3", str(tmp_path))
    m.wait_idle(5)
    assert captured["url"] == "https://example.com/v"
    assert captured["noplaylist"] is True
    assert captured["paths"] == {"home": str(tmp_path)}
    assert captured["postprocessors"][0]["preferredcodec"] == "mp3"


def test_download_error_reported(tmp_path):
    def script(fake, url):
        raise DownloadError(
            "\x1b[0;31mERROR:\x1b[0m [generic] Unsupported URL: https://x"
        )

    m = make_manager(script, tmp_path)
    job = m.add("https://example.com/v", "best", str(tmp_path))
    m.wait_idle(5)
    final = m.get(job["id"])
    assert final["status"] == "error"
    assert final["error"] == "Unsupported URL: https://x"


def test_cancel_running_download_removes_partial(tmp_path):
    started, release = threading.Event(), threading.Event()
    part = tmp_path / "clip.mp4.part"

    def script(fake, url):
        part.write_bytes(b"partial")
        fake.hook(
            status="downloading",
            downloaded_bytes=1,
            total_bytes=10,
            tmpfilename=str(part),
            filename=str(tmp_path / "clip.mp4"),
        )
        started.set()
        release.wait(5)
        fake.hook(
            status="downloading",
            downloaded_bytes=2,
            total_bytes=10,
            tmpfilename=str(part),
            filename=str(tmp_path / "clip.mp4"),
        )
        return {"title": "never"}

    m = make_manager(script, tmp_path)
    job = m.add("https://example.com/v", "best", str(tmp_path))
    assert started.wait(5)
    m.cancel(job["id"])
    release.set()
    m.wait_idle(5)
    assert m.get(job["id"])["status"] == "cancelled"
    assert not part.exists()


def test_cancel_queued_job_never_runs(tmp_path):
    calls = []
    gate = threading.Event()

    def script(fake, url):
        calls.append(url)
        gate.wait(5)
        return {"title": "t"}

    m = make_manager(script, tmp_path)
    m.add("https://example.com/1", "best", str(tmp_path))
    second = m.add("https://example.com/2", "best", str(tmp_path))
    m.cancel(second["id"])
    gate.set()
    m.wait_idle(5)
    assert calls == ["https://example.com/1"]
    assert m.get(second["id"])["status"] == "cancelled"


def test_sequential_single_worker(tmp_path):
    active, peak = [0], [0]
    lock = threading.Lock()

    def script(fake, url):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        threading.Event().wait(0.02)
        with lock:
            active[0] -= 1
        return {"title": url}

    m = make_manager(script, tmp_path)
    for i in range(4):
        m.add(f"https://example.com/{i}", "best", str(tmp_path))
    m.wait_idle(5)
    assert peak[0] == 1
    assert all(j["status"] == "done" for j in m.jobs())


def test_terminal_state_is_final(tmp_path):
    m = make_manager(ok_script, tmp_path)
    job = m.add("https://example.com/v", "best", str(tmp_path))
    m.wait_idle(5)
    m.cancel(job["id"])
    assert m.get(job["id"])["status"] == "done"


def test_remove_and_clear_finished(tmp_path):
    m = make_manager(ok_script, tmp_path)
    a = m.add("https://example.com/a", "best", str(tmp_path))
    m.add("https://example.com/b", "best", str(tmp_path))
    m.wait_idle(5)
    assert m.remove(a["id"]) is True
    assert m.get(a["id"]) is None
    m.clear_finished()
    assert m.jobs() == []


def test_remove_active_job_refused(tmp_path):
    started, release = threading.Event(), threading.Event()

    def script(fake, url):
        started.set()
        release.wait(5)
        return {"title": "t"}

    m = make_manager(script, tmp_path)
    job = m.add("https://example.com/v", "best", str(tmp_path))
    started.wait(5)
    assert m.remove(job["id"]) is False
    release.set()
    m.wait_idle(5)


@pytest.mark.parametrize(
    "url,preset", [("file:///etc/passwd", "best"), ("https://x.com", "nope")]
)
def test_add_rejects_invalid_input(tmp_path, url, preset):
    m = make_manager(ok_script, tmp_path)
    with pytest.raises(ValueError):
        m.add(url, preset, str(tmp_path))
    assert m.jobs() == []


def test_add_rejects_missing_dir(tmp_path):
    m = make_manager(ok_script, tmp_path)
    with pytest.raises(ValueError):
        m.add("https://x.com/v", "best", str(tmp_path / "missing"))


def test_fragment_progress(tmp_path):
    def script(fake, url):
        fake.hook(
            status="downloading",
            fragment_index=3,
            fragment_count=4,
            downloaded_bytes=10,
        )
        return {"title": "t"}

    seen = []
    m = make_manager(script, tmp_path)
    m.on_progress = lambda j: seen.append(j["percent"])
    m.add("https://x.com/v", "best", str(tmp_path))
    m.wait_idle(5)
    assert 75 in seen


def test_terminal_set():
    assert TERMINAL == {"done", "error", "cancelled"}
