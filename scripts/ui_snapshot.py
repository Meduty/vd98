"""Render the web UI offscreen with a mocked js_api and save a PNG.

Used to verify UI changes where the live window cannot be captured
(e.g. Wayland). See docs/live/e2e_testing.md.

    QT_QPA_PLATFORM=offscreen uv run python scripts/ui_snapshot.py OUT.png [JS]

Optional JS runs after load (e.g. open a menu) before the capture.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, QUrl
from PyQt6.QtWebEngineCore import QWebEngineScript
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QApplication

INDEX = Path(__file__).resolve().parents[1] / "src" / "vd98" / "web" / "index.html"

MOCK_API = r"""
const jobs = [
  {id: 1, url: 'https://example.com/1', title: 'Short clip', status: 'done', percent: 100, speed: null, eta: null, error: ''},
  {id: 2, url: 'https://example.com/2', title: 'A much longer video title that should be cut off with an ellipsis', status: 'downloading', percent: 43.5, speed: 3.6e6, eta: 84, error: ''},
  {id: 3, url: 'https://example.com/3', title: '', status: 'queued', percent: 0, speed: null, eta: null, error: ''},
  {id: 4, url: 'https://example.com/4', title: '', status: 'error', percent: 0, speed: null, eta: null, error: 'Unsupported URL'},
];
const settings = {download_dir: '/home/user/Downloads', preset: 'best', sound: false};
const presets = [{key: 'best', label: 'Best quality (MP4)'}, {key: 'mp3', label: 'Audio only (MP3)'}];
window.pywebview = {api: {
  init: async () => ({jobs, settings, presets, ffmpeg: true}),
  get_state: async () => ({jobs, settings}),
  about: async () => ({app: '0.0.0', yt_dlp: 'mock'}),
  save_settings: async (p) => Object.assign(settings, p),
  add: async () => ({error: 'mock'}), cancel: async () => true, remove: async () => true,
  clear_finished: async () => true, open_folder: async () => true, choose_folder: async () => null,
  minimize: async () => {}, maximize: async () => {}, close: async () => {},
  start_move: async () => true, start_resize: async () => true,
}};
"""


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out, extra_js = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else "")
    app = QApplication(sys.argv[:1])
    view = QWebEngineView()
    view.resize(720, 520)
    script = QWebEngineScript()
    script.setSourceCode(MOCK_API)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    view.page().scripts().insert(script)
    view.load(QUrl.fromLocalFile(str(INDEX)))
    view.show()

    def capture() -> None:
        if extra_js:
            view.page().runJavaScript(extra_js)
        QTimer.singleShot(500, lambda: (view.grab().save(out), app.quit()))

    QTimer.singleShot(2500, capture)
    app.exec()


if __name__ == "__main__":
    main()
