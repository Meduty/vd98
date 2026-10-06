from vd98.api import Api
from vd98.manager import DownloadManager


class NullYDL:
    def __init__(self, params):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        return {"title": "t"}


def make_api(tmp_path):
    api = Api(DownloadManager(ydl_factory=NullYDL), settings_path=tmp_path / "s.json")
    api.save_settings({"download_dir": str(tmp_path)})
    return api


def test_add_returns_error_dict_for_bad_url(tmp_path):
    assert make_api(tmp_path).add("file:///etc/passwd", "best") == {"error": "Only http:// and https:// links are supported."}


def test_add_remembers_preset(tmp_path):
    api = make_api(tmp_path)
    job = api.add("https://example.com/v", "mp3")
    assert job["status"] in {"queued", "downloading", "done"}
    assert api.get_state()["settings"]["preset"] == "mp3"
    assert Api(DownloadManager(ydl_factory=NullYDL), tmp_path / "s.json").get_state()["settings"]["preset"] == "mp3"


def test_save_settings_rejects_garbage(tmp_path):
    api = make_api(tmp_path)
    assert "error" in api.save_settings("nope")
    assert api.save_settings({"download_dir": "/no/such", "sound": False})["download_dir"] == str(tmp_path)


def test_open_folder_rejects_missing_dir(tmp_path):
    assert make_api(tmp_path).open_folder(str(tmp_path / "missing")) is False


def test_init_lists_presets(tmp_path):
    data = make_api(tmp_path).init()
    assert data["presets"][0]["key"] == "best"
    assert "ffmpeg" in data


def test_about_versions(tmp_path):
    info = make_api(tmp_path).about()
    assert info["app"] and info["yt_dlp"]
