> **Status: LIVING** — must match `scripts/ui_snapshot.py`, `src/vd98/manager.py`.
> **Scope:** how "done" is verified in the running app. **Reconciled:** 2026-10-06.

# End-to-end verification

Unit tests do not prove the app works. Every change that touches the UI or the
download path also needs the matching check below, with output shown.

Use a scratch directory (`$SCRATCH`) for every artifact; never the repo.

## UI change → offscreen snapshot, then read it

The live window cannot be screen-captured on this Wayland desktop, so render the
real `index.html` offscreen with a mocked `js_api`:

```bash
QT_QPA_PLATFORM=offscreen uv run python scripts/ui_snapshot.py "$SCRATCH/ui.png"
# open a menu / click before capture:
QT_QPA_PLATFORM=offscreen uv run python scripts/ui_snapshot.py "$SCRATCH/menu.png" \
  'document.querySelector("[data-menu=file]").click()'
```

Then **open the PNG and look at it** (Read tool). Check: 98.css chrome, rows,
progress bars, no overlap, empty-state text hidden when rows exist.
Mock data lives in `MOCK_API` in `scripts/ui_snapshot.py`; extend it when the
`Api` surface (SPEC §I) changes.

Not covered offscreen: window drag, minimize/maximize/close, folder dialog,
sounds. If touched, launch `uv run vd98` and ask the user to click through.

Window chrome checklist (SPEC V.15; the live window can't be captured or driven on Wayland):
1. Press and hold on the blue title bar, move the mouse: the window follows.
2. Drag each edge and corner (cursor changes on the outer few pixels): the window resizes.
3. Double-click the title bar: maximizes; again: restores. Resize handles are off while maximized.
4. Title-bar buttons still minimize / maximize / close; clicking them doesn't start a drag.
`tests/test_chrome.py` covers the thread hand-off and edge names, not the compositor.

## Download path change → real smoke

Short, freely available test video ("Me at the zoo", 19 s):

```bash
uv run python - "$SCRATCH" <<'PY'
import sys
from vd98.manager import DownloadManager
m = DownloadManager()
for preset in ("480p", "mp3"):
    m.add("https://www.youtube.com/watch?v=jNQXAC9IVRw", preset, sys.argv[1])
m.add("https://example.com/", "best", sys.argv[1])   # expect error: Unsupported URL
m.wait_idle(240)
for j in m.jobs():
    print(j["status"], j["percent"], j["filename"], j["error"])
PY
ls -la "$SCRATCH"
```

Expect: two `done` rows with `.mp4` and `.mp3` files present, one `error` row
with `Unsupported URL: https://example.com/`.

Cancel path: start a large video (`https://www.youtube.com/watch?v=aqz-KE-bpKQ`,
preset `best`), cancel once `percent > 1`, expect status `cancelled` and no
`.part` files left in `$SCRATCH`.

Network-dependent; never part of `pytest` (SPEC V.5).
