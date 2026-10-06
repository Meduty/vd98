# FORMAT — house style for SPEC.md

> **Status: LIVING** — governs `SPEC.md`. **Reconciled:** 2026-10-06.

1. Dense wording: drop articles and filler. Never compress identifiers, paths, commands or error text.
2. Cite `path:line` or `path` + symbol (`src/vd98/manager.py` `DownloadManager.cancel`). Line numbers rot; symbol wins on conflict.
3. IDs only go up. Retired entry: ~~strike through~~ + reason. Never renumber, never delete.
4. One entry reads alone: no "see above", no pronouns pointing at other entries.
5. One rule per entry. Two rules → two IDs.
6. Every §V names its guard (test function or hook path) or says `Guard: unguarded`.
7. §T estimates: S (<1h) · M (1–3h) · L (3–6h). Bigger → split.
8. §T status: `todo` · `doing` · `done` · `dropped`.
9. §B row: date · symptom · cause · fix · guarding §V. Fix may be `open → T.n`.
10. §D: question + options + decision. Resolved inline (`**Decided 2026-10-06:** …`), never deleted.
11. Dates absolute, ISO `YYYY-MM-DD`.
12. SPEC changes only via the `spec` skill (`.claude/skills/spec/SKILL.md`).
