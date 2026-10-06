> **Status: LIVING** — must match `scripts/ui_snapshot.py`, `scripts/sandbox_probe.sh`, `src/vd98/manager.py`.
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

## Secret protection change → sandbox probe

Settings, `guard.py`, `check_secrets.py` or the sandbox config touched (SPEC V.16–V.19):

1. **Human**, outside the sandbox: `! scripts/sandbox_probe.sh setup`. This creates fake, gitignored
   fixtures (`.env`, `secret/probe.txt`, `probe-fixture/server.pem`) carrying a marker string.
2. **Agent**, inside the sandbox: `scripts/sandbox_probe.sh check`. Expected result: every
   attempt says `BLOCKED` **except** `file created mid-session`, which says `LEAKED`. That
   one is the documented per-command limit (V.16). Any other `LEAKED` line, or a control line
   that isn't `OK`, is a regression. The script therefore exits 1 even when the result is as
   expected. Inside the sandbox, `secret/probe.txt` shows as `hidden`; that's normal.
3. **Human**: `! scripts/sandbox_probe.sh cleanup`.

The probe prints BLOCKED/LEAKED only, never file contents.

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

Resume path (SPEC V.20, V.21): same large video, preset `720p`, with
`DownloadManager(store=QueueStore(<scratch>/state/queue.json))`.
1. Once `percent >= 3`, call `suspend(timeout=10)`. Expect `True`, status
   `paused`, the `.part` file kept, and 1 saved entry.
2. Create a new manager on the same store and call `restore()`. Expect `1`, and
   the job `paused` at its old percent.
3. Call `resume(id)`. Expect the `.part` file to grow from its old size (yt-dlp
   continues, it doesn't restart).
4. Call `cancel`. Expect `cancelled` and no `.part` left.

Run 2026-10-06 (inside the sandbox):
- suspended at 14.6% of 71.3 MB with the `.part` at 10,422,070 B;
- restored at 14.6%;
- after resuming, the `.part` reached 12,518,198 B and 17.6%;
- cancel left 0 `.part` files.

GUI check for the user: start a download, close the window, reopen. Expect a
"Restored 1 paused download." status, the row `Paused` with its old %/Size,
and Resume enabled when the row is selected.

Network-dependent; never part of `pytest` (SPEC V.5).
