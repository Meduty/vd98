"""Create the pywebview window and start the GUI loop."""

from pathlib import Path

import webview

from .api import Api

WEB_DIR = Path(__file__).parent / "web"


def run() -> None:
    api = Api()
    window = webview.create_window(
        "Video Downloader 98",
        url=str(WEB_DIR / "index.html"),
        js_api=api,
        width=720,
        height=520,
        min_size=(560, 400),
        frameless=True,
        easy_drag=False,
        background_color="#008080",
    )
    api._attach(window)
    # window closed by the WM (not our title-bar button): same suspend, partials kept (V.21)
    window.events.closing += lambda: api._manager.suspend(timeout=3)
    webview.start(gui="qt", private_mode=True)
