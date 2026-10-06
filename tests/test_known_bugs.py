"""Known bugs from SPEC §B, pinned as strict xfails.

Each test asserts the intended behaviour. strict=True makes a fix that
forgets to remove the marker fail loudly, so §B and the code stay in sync.
"""

import json

import pytest

from vd98 import settings
from vd98.api import Api
from vd98.formats import preset_opts
from vd98.manager import DownloadManager
from vd98.urls import InvalidURL, normalize_url


class NullYDL:
    def __init__(self, params):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        return {"title": "t"}


@pytest.mark.xfail(strict=True, reason="SPEC B.1: unhashable preset crashes load (V.6)")
def test_b1_load_survives_unhashable_preset(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"preset": []}))
    assert settings.load(p) == settings.defaults()


@pytest.mark.xfail(strict=True, reason="SPEC B.4: preset_opts raises TypeError (V.7)")
def test_b4_preset_opts_unhashable_is_value_error():
    with pytest.raises(ValueError):
        preset_opts([])


@pytest.mark.xfail(strict=True, reason="SPEC B.4: Api.cancel raises on non-int id (V.11)")
def test_b4_api_cancel_bad_id_returns_false(tmp_path):
    api = Api(DownloadManager(ydl_factory=NullYDL), settings_path=tmp_path / "s.json")
    assert api.cancel("not-a-number") is False


@pytest.mark.xfail(strict=True, reason="SPEC B.5: queued->cancelled skips on_progress")
def test_b5_cancel_queued_fires_on_progress(tmp_path):
    import threading

    gate = threading.Event()

    class SlowYDL(NullYDL):
        def extract_info(self, url, download=True):
            gate.wait(5)
            return {"title": "t"}

    m = DownloadManager(ydl_factory=SlowYDL)
    seen = []
    m.on_progress = lambda j: seen.append((j["id"], j["status"]))
    m.add("https://example.com/1", "best", str(tmp_path))
    second = m.add("https://example.com/2", "best", str(tmp_path))
    m.cancel(second["id"])
    gate.set()
    m.wait_idle(5)
    assert (second["id"], "cancelled") in seen


@pytest.mark.xfail(strict=True, reason="SPEC B.7: mailto: rewritten to https (V.1)")
def test_b7_mailto_rejected():
    with pytest.raises(InvalidURL):
        normalize_url("mailto:a@b")


@pytest.mark.xfail(strict=True, reason="SPEC B.7: control chars accepted (V.1)")
def test_b7_control_chars_rejected():
    with pytest.raises(InvalidURL):
        normalize_url("https://x.com/\x00")
