"""Guards for repo layout invariants (SPEC V.13, V.14)."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "vd98" / "web"


def test_frozen_paths_exist():
    """SPEC V.13 / C.11: frozen paths stay where installers, docs and licenses expect them."""
    assert (WEB / "vendor" / "98.css").is_file()
    assert (WEB / "vendor" / "98.css.LICENSE").is_file()
    assert (ROOT / "scripts" / "install-desktop.sh").is_file()
    assert 'vd98 = "vd98:main"' in (ROOT / "pyproject.toml").read_text()
    from vd98 import settings

    assert settings.APP_DIR == "video-downloader-98"


def test_ui_has_no_remote_assets():
    """SPEC V.14: the UI loads nothing over the network."""
    remote = re.compile(r"""(src|href)\s*=\s*["']https?://|url\(\s*["']?https?://""")
    for path in [*WEB.glob("*.html"), *WEB.glob("*.css"), *WEB.glob("*.js")]:
        assert not remote.search(path.read_text()), f"remote asset in {path.name}"
