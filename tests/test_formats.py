import pytest

from vd98.formats import DEFAULT_PRESET, PRESETS, preset_list, preset_opts


def test_default_preset_exists():
    assert DEFAULT_PRESET in PRESETS


def test_video_presets_cap_height_and_merge_mp4():
    opts = preset_opts("720p")
    assert "height<=720" in opts["format"]
    assert opts["merge_output_format"] == "mp4"


def test_audio_preset_extracts_audio():
    opts = preset_opts("mp3")
    assert opts["postprocessors"][0]["key"] == "FFmpegExtractAudio"
    assert opts["postprocessors"][0]["preferredcodec"] == "mp3"


def test_preset_opts_returns_copy():
    preset_opts("mp3")["postprocessors"][0]["preferredcodec"] = "evil"
    assert preset_opts("mp3")["postprocessors"][0]["preferredcodec"] == "mp3"


def test_unknown_preset_rejected():
    with pytest.raises(ValueError):
        preset_opts("8k-hdr-bluray")


def test_preset_list_shape():
    assert {"key": "best", "label": PRESETS["best"].label} in preset_list()
