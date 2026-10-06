"""Quality presets mapped to yt-dlp options."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    key: str
    label: str
    opts: dict = field(default_factory=dict)


def _video(height: int | None) -> dict:
    cap = f"[height<={height}]" if height else ""
    return {
        "format": f"bv*{cap}+ba/b{cap}/b",
        "merge_output_format": "mp4",
    }


def _audio(codec: str) -> dict:
    return {
        "format": "ba/b",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": codec, "preferredquality": "192"}
        ],
    }


PRESETS: dict[str, Preset] = {
    p.key: p
    for p in (
        Preset("best", "Best quality (MP4)", _video(None)),
        Preset("1080p", "1080p (MP4)", _video(1080)),
        Preset("720p", "720p (MP4)", _video(720)),
        Preset("480p", "480p (MP4)", _video(480)),
        Preset("mp3", "Audio only (MP3)", _audio("mp3")),
        Preset("m4a", "Audio only (M4A)", _audio("m4a")),
    )
}

DEFAULT_PRESET = "best"


def preset_opts(key: str) -> dict:
    """Return a fresh copy of yt-dlp options for a preset key."""
    try:
        preset = PRESETS[key]
    except KeyError:
        raise ValueError(f"Unknown format preset: {key!r}") from None
    opts = dict(preset.opts)
    if "postprocessors" in opts:
        opts["postprocessors"] = [dict(pp) for pp in opts["postprocessors"]]
    return opts


def preset_list() -> list[dict]:
    return [{"key": p.key, "label": p.label} for p in PRESETS.values()]
