---
name: repo-backprop
description: Bug to spec to test to fix for this repo. Use when a test fails unexpectedly, a bug is reported, or a build run classifies a failure as "spec wrong" or "unspecified edge case".
---
# repo-backprop

1. Reproduce: smallest command or test that shows the bug; paste output.
2. Trace cause to `path:line` + symbol. Read every copy of the logic.
3. Decide the invariant: existing §V that should have caught it, or a new §V.
4. Via `repo-spec`: add §B row (date, symptom, cause, fix, guard) and add/strengthen the §V.
5. Write the guard test named after the §V; show it failing.
   Not fixing now → add it to `tests/test_known_bugs.py` as `xfail(strict=True, reason="SPEC B.n: …")`
   and open `gh issue create --label bug`.
6. Fix (or hand to `repo-build`), show test passing, full gates green.
7. Commit message: `fix: backprop §B.n + §V.m: <cause>`.
