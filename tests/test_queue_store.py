"""Persisted queue of unfinished downloads (SPEC T.17, V.20)."""

import json

from vd98.queue_store import QueueStore, state_path


def entry(tmp_path, **over):
    e = {
        "url": "https://example.com/v",
        "preset": "best",
        "dest_dir": str(tmp_path),
        "title": "Clip",
        "filename": str(tmp_path / "Clip [x].mp4"),
        "tmpfiles": [str(tmp_path / "Clip [x].mp4.part")],
        "percent": 42.5,
        "total_bytes": 1000,
        "size_estimated": False,
    }
    e.update(over)
    return e


def test_missing_file_is_empty(tmp_path):
    assert QueueStore(tmp_path / "nope.json").load() == []


def test_corrupt_or_wrong_shape_is_empty(tmp_path):
    p = tmp_path / "q.json"
    for text in ["{not json", "{}", "[1, 2]", '"x"']:
        p.write_text(text)
        assert QueueStore(p).load() == [], text


def test_roundtrip(tmp_path):
    store = QueueStore(tmp_path / "sub" / "q.json")
    assert store.save([entry(tmp_path)]) is True
    assert store.load() == [entry(tmp_path)]


def test_invalid_entries_dropped_valid_kept(tmp_path):
    p = tmp_path / "q.json"
    good = entry(tmp_path)
    p.write_text(
        json.dumps(
            [
                good,
                entry(tmp_path, url="file:///etc/passwd"),  # not http(s) (V.1)
                entry(tmp_path, preset=[]),  # unhashable / unknown preset
                entry(tmp_path, dest_dir=str(tmp_path / "gone")),  # folder vanished
                entry(tmp_path, tmpfiles="x"),  # wrong type
                "not a dict",
            ]
        )
    )
    assert QueueStore(p).load() == [good]


def test_optional_fields_defaulted(tmp_path):
    p = tmp_path / "q.json"
    p.write_text(
        json.dumps(
            [
                {
                    "url": "https://example.com/v",
                    "preset": "mp3",
                    "dest_dir": str(tmp_path),
                }
            ]
        )
    )
    (loaded,) = QueueStore(p).load()
    assert (
        loaded["title"] == "" and loaded["tmpfiles"] == [] and loaded["percent"] == 0.0
    )


def test_save_failure_does_not_raise(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    store = QueueStore(blocker / "q.json")  # parent is a file: mkdir fails
    assert store.save([entry(tmp_path)]) is False


def test_atomic_write_leaves_no_tmp(tmp_path):
    store = QueueStore(tmp_path / "q.json")
    store.save([entry(tmp_path)])
    assert [p.name for p in tmp_path.iterdir() if p.name.startswith("q")] == ["q.json"]


def test_state_path_honours_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    assert state_path() == tmp_path / "video-downloader-98" / "queue.json"
