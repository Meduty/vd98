"""Progress fields for the % / Size columns and the smoothed ETA (SPEC T.15, T.16)."""

from typing import ClassVar

from vd98.manager import DownloadManager


class ScriptedYDL:
    """Fake yt_dlp.YoutubeDL that replays a list of progress-hook dicts."""

    hooks: ClassVar[list] = []

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
        return {"title": "t"}


class FakeClock:
    """Each hook call reads the clock once; returns 0, 1, 2, ... seconds."""

    def __init__(self):
        self.t = -1.0

    def __call__(self):
        self.t += 1.0
        return self.t


def run(hooks, tmp_path, clock=None):
    ydl = type("YDL", (ScriptedYDL,), {"hooks": hooks})
    m = DownloadManager(ydl_factory=ydl, clock=clock or FakeClock())
    snapshots = []
    m.on_progress = snapshots.append
    m.add("https://example.com/v", "best", str(tmp_path))
    assert m.wait_idle(5)
    return snapshots


def downloading(done, total=None, estimate=None, eta=None):
    d = {"status": "downloading", "downloaded_bytes": done, "eta": eta}
    if total is not None:
        d["total_bytes"] = total
    if estimate is not None:
        d["total_bytes_estimate"] = estimate
    return d


def during(snaps, done):
    """The snapshot taken while downloading at `done` bytes (not the final 'done' one)."""
    return [
        x
        for x in snaps
        if x["status"] == "downloading" and x["downloaded_bytes"] == done
    ][-1]


def test_exact_size_reported(tmp_path):
    s = during(run([downloading(250, total=1000)], tmp_path), 250)
    assert (s["total_bytes"], s["size_estimated"], s["percent"]) == (1000, False, 25.0)


def test_estimated_size_flagged(tmp_path):
    s = during(run([downloading(250, estimate=1000)], tmp_path), 250)
    assert (s["total_bytes"], s["size_estimated"]) == (1000, True)


def test_eta_comes_from_half_window_not_yt_dlp(tmp_path):
    """yt-dlp says 999 s; at a steady 100 B/s with 600 B left, the smoothed ETA is 6 s."""
    hooks = [downloading(i * 100, total=1000, eta=999) for i in range(5)]
    assert during(run(hooks, tmp_path), 400)["eta"] == 6


def test_falls_back_to_yt_dlp_eta_until_two_samples(tmp_path):
    snaps = run([downloading(100, total=1000, eta=42)], tmp_path)
    assert during(snaps, 100)["eta"] == 42


def test_done_clears_eta_keeps_size(tmp_path):
    hooks = [downloading(500, total=1000), {"status": "finished"}]
    snaps = run(hooks, tmp_path)
    final = snaps[-1]
    assert (
        final["status"] == "done"
        and final["eta"] is None
        and final["total_bytes"] == 1000
    )
