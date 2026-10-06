"""URL validation before anything reaches yt-dlp."""

from urllib.parse import urlsplit

MAX_URL_LEN = 4096


class InvalidURL(ValueError):
    pass


def normalize_url(raw: str) -> str:
    """Return a cleaned http(s) URL or raise InvalidURL."""
    if not isinstance(raw, str):
        raise InvalidURL("URL must be text.")
    url = raw.strip()
    if not url:
        raise InvalidURL("Please enter a URL.")
    if len(url) > MAX_URL_LEN:
        raise InvalidURL("URL is too long.")
    if any(c.isspace() for c in url):
        raise InvalidURL("URL must not contain spaces.")
    if "://" not in url:
        url = "https://" + url
    try:
        parts = urlsplit(url)
        hostname = parts.hostname  # may raise too (e.g. a malformed port)
    except ValueError:  # e.g. "http://[": "Invalid IPv6 URL"
        raise InvalidURL("URL could not be parsed.") from None
    if parts.scheme.lower() not in ("http", "https"):
        raise InvalidURL("Only http:// and https:// links are supported.")
    if not hostname:
        raise InvalidURL("URL has no host name.")
    return url
