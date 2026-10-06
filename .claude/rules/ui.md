---
paths:
  - "src/vd98/web/**"
  - "src/vd98/api.py"
  - "src/vd98/app.py"
---
# UI + bridge rules

> Before editing: read ARCHITECTURE "Bridge" + "UI" + SPEC §I, V.9, V.11, V.14 and open §B rows B.8–B.10.
> After editing: gates green, then `QT_QPA_PLATFORM=offscreen uv run python scripts/ui_snapshot.py $SCRATCH/ui.png` and **Read the PNG**. Window chrome, dialogs, sounds → ask the user to click through `uv run vd98`.

- Remote strings via `textContent` / attributes only; never `innerHTML` (V.9).
- No remote assets: everything under `src/vd98/web/`; 98.css stays in `vendor/` (V.14, C.11).
- Use 98.css classes before writing custom CSS; custom styles go in `app.css`.
- `Api` methods return JSON-able data and `{error}` instead of raising (V.11); private attrs start with `_`.
- New `Api` method → SPEC §I entry + `MOCK_API` stub in `scripts/ui_snapshot.py` + test in `tests/test_api.py`.
- Only subprocess: `xdg-open` with an arg list on an existing dir (V.2).
- UI polls `get_state`; do not add Python→JS pushes without a SPEC §D decision.
- Sounds stay synthesized in `sounds.js`; no audio files, no copied OS sounds.
