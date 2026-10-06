---
paths:
  - "tests/**"
---
# Test rules

> After editing: `uv run pytest -q` and paste the tail.

- Offline only (V.5): fake `ydl_factory`, `tmp_path` for files, no real `~/.config` (pass `settings_path`).
- Name tests after the behaviour or §V they guard; reference the §V/§B id in the docstring or `reason=`.
- New guard → prove it bites: break the condition once, show the failure, restore.
- Known bugs: strict xfail in `tests/test_known_bugs.py` with `reason="SPEC B.n: …"`. Fixing the bug removes the marker in the same commit.
- Never delete, skip or weaken an existing assertion to get green; if the spec was wrong, record a §B row and change the test with it.
- Threads: always `wait_idle(timeout)` / `Event.wait(timeout)`; no bare sleeps for sync.
