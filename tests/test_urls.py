import pytest

from vd98.urls import InvalidURL, normalize_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://example.com/v.mp4", "https://example.com/v.mp4"),
        ("  http://example.com/watch?v=1 \n", "http://example.com/watch?v=1"),
        ("example.com/video", "https://example.com/video"),
        ("HTTPS://Example.com/x", "HTTPS://Example.com/x"),
    ],
)
def test_accepts_http_urls(raw, expected):
    assert normalize_url(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "file:///etc/passwd",
        "ftp://host/x",
        "javascript:alert(1)://x",
        "https://",
        "https://exa mple.com",
        "https://x.com/" + "a" * 5000,
        None,
    ],
)
def test_rejects_bad_urls(raw):
    with pytest.raises(InvalidURL):
        normalize_url(raw)
