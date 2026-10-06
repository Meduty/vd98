import json

from vd98 import settings


def test_missing_file_gives_defaults(tmp_path):
    assert settings.load(tmp_path / "nope.json") == settings.defaults()


def test_corrupt_file_gives_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    assert settings.load(p) == settings.defaults()


def test_non_dict_gives_defaults(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("[1, 2]")
    assert settings.load(p) == settings.defaults()


def test_roundtrip(tmp_path):
    p = tmp_path / "sub" / "s.json"
    saved = settings.save({"download_dir": str(tmp_path), "preset": "mp3", "sound": False}, p)
    assert settings.load(p) == saved == {"download_dir": str(tmp_path), "preset": "mp3", "sound": False}


def test_invalid_values_replaced(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"download_dir": "/no/such/dir", "preset": "bogus", "sound": "yes"}))
    assert settings.load(p) == settings.defaults()


def test_xdg_config_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.config_path() == tmp_path / settings.APP_DIR / "settings.json"
